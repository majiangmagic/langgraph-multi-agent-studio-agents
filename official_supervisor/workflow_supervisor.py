"""Constrained Supervisor Agent for workflows with explicit conditional edges."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool, tool
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from app.agents.official_supervisor.state import SupervisorState
from app.runtime.langgraph.events import emit_event
from app.runtime.llm.provider import ai_provider


class JsonSafeConverter:
    """Convert runtime values into JSON-safe control context values."""

    @classmethod
    def convert(cls, value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, dict):
            return {str(key): cls.convert(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [cls.convert(item) for item in value]
        if isinstance(value, BaseMessage):
            return {"type": value.type, "content": str(value.content)}
        return str(value)


@tool
def request_user_input(
    question: str,
    options: Optional[list[str]] = None,
    context: str = "",
) -> str:
    """Pause the workflow and request information required to continue."""

    return "The workflow will pause and pass the user's answer back to you."


class SupervisorAgentConfigResolver:
    """Resolve the local Agent configuration assigned to a Supervisor node."""

    @staticmethod
    def resolve(
        agents: list[Dict[str, Any]],
        node_name: str,
    ) -> Dict[str, Any]:
        for config in agents:
            identifier = str(config.get("id") or "")
            if identifier.endswith(f":{node_name}") or config.get("name") == node_name:
                return config
        raise ValueError(f"Supervisor node '{node_name}' has no local Agent config")


class SupervisorToolCallReader:
    """Read the latest structured decision made by the Supervisor model."""

    @staticmethod
    def latest(state: SupervisorState) -> Dict[str, Any]:
        for message in reversed(state.get("messages") or []):
            if isinstance(message, AIMessage) and message.tool_calls:
                return message.tool_calls[0]
        raise ValueError(
            "Supervisor must select exactly one routing or clarification tool"
        )


class SupervisorControlContextBuilder:
    """Build the execution report supplied to the Supervisor model."""

    def __init__(self, worker_names: list[str]) -> None:
        self.worker_names = worker_names

    def build(self, state: SupervisorState) -> Dict[str, Any]:
        worker_runs = {name: 0 for name in self.worker_names}
        worker_reports: Dict[str, Dict[str, Any]] = {}
        last_worker = None

        for message in state.get("messages") or []:
            if not isinstance(message, AIMessage):
                continue
            for tool_call in message.tool_calls:
                tool_name = str(tool_call.get("name") or "")
                if not tool_name.startswith("route_to_"):
                    continue
                worker_name = tool_name.removeprefix("route_to_")
                if worker_name in worker_runs:
                    worker_runs[worker_name] += 1
                    last_worker = worker_name

        agents = state.get("agents") or {}
        for worker_name, agent in agents.items():
            results = agent.get("results") or {}
            has_result = any(
                value not in (None, "", [], {}) for value in results.values()
            )
            if worker_name in worker_runs and has_result:
                worker_runs[worker_name] = max(worker_runs[worker_name], 1)

            status = agent.get("status")
            error = agent.get("error")
            has_report = has_result or error or status not in (None, "", "idle")
            if worker_name in worker_runs and has_report:
                worker_reports[worker_name] = {
                    "status": status,
                    "error": error,
                    "results": JsonSafeConverter.convert(results),
                }

        last_agent = agents.get(last_worker or "") or {}
        last_report = None
        if last_worker:
            last_report = {
                "status": last_agent.get("status"),
                "error": last_agent.get("error"),
                "results": JsonSafeConverter.convert(last_agent.get("results")),
            }

        return {
            "worker_runs": {
                name: count for name, count in worker_runs.items() if count
            },
            # Directly connected workers do not create Supervisor route messages.
            # Include every completed report so the Supervisor sees stage outputs.
            "worker_reports": worker_reports,
            "last_worker": last_worker,
            "last_report": last_report,
        }


@dataclass(frozen=True)
class SupervisorToolSet:
    """Routing tools and their outer Workflow node targets."""

    tools: list[BaseTool]
    route_targets: Dict[str, str]


class SupervisorToolFactory:
    """Create the constrained tools exposed to the Supervisor model."""

    @staticmethod
    def create_route_tool(target: str) -> BaseTool:
        tool_name = "finish_workflow" if target == "END" else f"route_to_{target}"
        description = (
            "Finish the workflow and return its current final result"
            if target == "END"
            else f"Select workflow node '{target}' as the next step"
        )

        @tool(tool_name, description=description)
        def route() -> str:
            return f"Selected next workflow node: {target}"

        return route

    @classmethod
    def create(
        cls,
        worker_names: list[str],
        allow_finish_workflow: bool,
    ) -> SupervisorToolSet:
        route_targets = {
            **{f"route_to_{worker_name}": worker_name for worker_name in worker_names},
            **({"finish_workflow": "END"} if allow_finish_workflow else {}),
        }
        route_names = [
            *worker_names,
            *(["END"] if allow_finish_workflow else []),
        ]
        tools = [
            request_user_input,
            *[cls.create_route_tool(name) for name in route_names],
        ]
        return SupervisorToolSet(tools=tools, route_targets=route_targets)


class SupervisorMessageBuilder:
    """Build model messages from Agent configuration and Workflow state."""

    def __init__(
        self,
        system_prompt: str,
        worker_names: list[str],
        worker_descriptions: str,
        max_retries_per_node: int,
        allow_finish_workflow: bool,
    ) -> None:
        self.system_prompt = system_prompt
        self.worker_descriptions = worker_descriptions
        self.max_worker_runs = max_retries_per_node + 1
        self.allow_finish_workflow = allow_finish_workflow
        self.control_context_builder = SupervisorControlContextBuilder(worker_names)

    def build(self, state: SupervisorState) -> list[BaseMessage]:
        control_context = self.control_context_builder.build(state)
        memory_lines = [
            f"- {memory.get('content')}"
            for memory in state.get("long_term_memories") or []
            if isinstance(memory, dict) and memory.get("content")
        ]
        memory_section = (
            "\nLong-term memories:\n" + "\n".join(memory_lines)
            if memory_lines
            else ""
        )
        finish_policy = (
            "Call finish_workflow only when the final output is ready."
            if self.allow_finish_workflow
            else "This node cannot finish the workflow; completion is controlled "
            "by declared graph edges."
        )
        policy = f"""

You supervise an explicit LangGraph workflow. Select the next node by calling
exactly one route_to_* tool. {finish_policy} Available workers:
{self.worker_descriptions}

- Inspect the latest worker result before selecting the next node.
- Inspect worker_reports for outputs produced by directly connected stage nodes.
- Do not run a worker more than {self.max_worker_runs} times per turn.
- If required user information is missing, call request_user_input.
- Do not fabricate business output or bypass the declared workflow order.

Current control state:
{json.dumps(control_context, ensure_ascii=False)}
"""
        return [
            SystemMessage(
                content=f"{self.system_prompt}{policy}{memory_section}"
            ),
            *state.get("messages", []),
        ]


class SupervisorDecisionNode:
    """Ask the model for exactly one constrained routing decision."""

    def __init__(self, model: Any, message_builder: SupervisorMessageBuilder) -> None:
        self.model = model
        self.message_builder = message_builder

    async def __call__(self, state: SupervisorState) -> Dict[str, Any]:
        response = await self.model.ainvoke(self.message_builder.build(state))
        if not isinstance(response, AIMessage) or len(response.tool_calls) != 1:
            raise ValueError(
                "Supervisor must call exactly one routing or clarification tool"
            )
        return {"messages": [response], "next_node": ""}


class SupervisorDecisionRouter:
    """Route a Supervisor decision to clarification or route selection."""

    def __call__(self, state: SupervisorState) -> str:
        tool_name = str(SupervisorToolCallReader.latest(state).get("name") or "")
        return "clarify" if tool_name == "request_user_input" else "select_route"


class SupervisorClarificationNode:
    """Pause the graph and return the user's answer to the Supervisor model."""

    def __call__(self, state: SupervisorState) -> Dict[str, Any]:
        tool_call = SupervisorToolCallReader.latest(state)
        arguments = tool_call.get("args") or {}
        payload = {
            "kind": "workflow.clarification",
            "question": str(arguments.get("question") or "").strip(),
            "options": [
                str(option)
                for option in (arguments.get("options") or [])
                if str(option).strip()
            ][:4],
            "context": str(arguments.get("context") or "").strip(),
        }
        emit_event(
            {
                "object": "workflow.event",
                "type": "workflow.interrupted",
                "interrupt": payload,
            }
        )
        answer = interrupt(payload)
        return {
            "messages": [
                ToolMessage(
                    content=json.dumps(
                        {
                            "status": "user_replied",
                            "answer": JsonSafeConverter.convert(answer),
                        },
                        ensure_ascii=False,
                    ),
                    name="request_user_input",
                    tool_call_id=str(
                        tool_call.get("id") or "request-user-input"
                    ),
                )
            ]
        }


class SupervisorRouteSelectionNode:
    """Validate the selected tool and write its target to ``next_node``."""

    def __init__(self, route_targets: Dict[str, str]) -> None:
        self.route_targets = route_targets

    def __call__(self, state: SupervisorState) -> Dict[str, Any]:
        tool_call = SupervisorToolCallReader.latest(state)
        tool_name = str(tool_call.get("name") or "")
        if tool_name not in self.route_targets:
            raise ValueError(f"Unknown Supervisor routing tool: {tool_name}")

        target = self.route_targets[tool_name]
        return {
            "next_node": target,
            "messages": [
                ToolMessage(
                    content=f"Selected next workflow node: {target}",
                    name=tool_name,
                    tool_call_id=str(tool_call.get("id") or tool_name),
                )
            ],
        }


class WorkflowSupervisorGraphBuilder:
    """Assemble the constrained Supervisor Agent with native LangGraph APIs."""

    def __init__(
        self,
        *,
        node_name: str,
        agents: list[Dict[str, Any]],
        worker_names: list[str],
        max_retries_per_node: int = 2,
        allow_finish_workflow: bool = True,
    ) -> None:
        self.node_name = node_name
        self.agents = agents
        self.worker_names = worker_names
        self.max_retries_per_node = max_retries_per_node
        self.allow_finish_workflow = allow_finish_workflow

    def build_graph(self):
        supervisor_config = SupervisorAgentConfigResolver.resolve(
            self.agents,
            self.node_name,
        )
        worker_configs = {
            str(config.get("id") or "").rsplit(":", 1)[-1]: config
            for config in self.agents
        }
        worker_descriptions = "\n".join(
            f"- {worker_name}: "
            f"{worker_configs.get(worker_name, {}).get('description') or worker_name}"
            for worker_name in self.worker_names
        )
        tool_set = SupervisorToolFactory.create(
            self.worker_names,
            self.allow_finish_workflow,
        )
        model = ai_provider.get_model(
            model_name=supervisor_config.get("model") or ai_provider.SUPERVISOR_MODEL,
            temperature=supervisor_config.get("temperature", 0.2),
        ).bind_tools(tool_set.tools)
        message_builder = SupervisorMessageBuilder(
            system_prompt=str(
                supervisor_config.get("system_prompt") or ""
            ).strip(),
            worker_names=self.worker_names,
            worker_descriptions=worker_descriptions,
            max_retries_per_node=self.max_retries_per_node,
            allow_finish_workflow=self.allow_finish_workflow,
        )

        graph = StateGraph(SupervisorState)
        graph.add_node(
            "decide",
            SupervisorDecisionNode(model, message_builder),
        )
        graph.add_node("clarify", SupervisorClarificationNode())
        graph.add_node(
            "select_route",
            SupervisorRouteSelectionNode(tool_set.route_targets),
        )
        graph.set_entry_point("decide")
        graph.add_conditional_edges(
            "decide",
            SupervisorDecisionRouter(),
            {"clarify": "clarify", "select_route": "select_route"},
        )
        graph.add_edge("clarify", "decide")
        graph.add_edge("select_route", END)
        return graph.compile()


def create_workflow_supervisor_graph(
    *,
    node_name: str,
    agents: list[Dict[str, Any]],
    worker_names: list[str],
    max_retries_per_node: int = 2,
    allow_finish_workflow: bool = True,
):
    """Create a Supervisor Agent that writes its choice to ``next_node``."""

    return WorkflowSupervisorGraphBuilder(
        node_name=node_name,
        agents=agents,
        worker_names=worker_names,
        max_retries_per_node=max_retries_per_node,
        allow_finish_workflow=allow_finish_workflow,
    ).build_graph()
