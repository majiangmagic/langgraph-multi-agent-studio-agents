"""Constrained Supervisor Agent for workflows with explicit conditional edges."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool, tool
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from app.agents.official_supervisor.state import SupervisorState
from app.runtime.langgraph.events import emit_event
from app.runtime.llm.provider import ai_provider


def json_safe(value: Any) -> Any:
    """Convert runtime values into JSON-safe control context values."""

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
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


class WorkflowSupervisor:
    """Build and run one constrained routing agent inside an outer workflow."""

    def __init__(
        self,
        *,
        node_name: str,
        agents: list[Dict[str, Any]],
        worker_names: list[str],
        allow_finish_workflow: bool,
    ) -> None:
        self.node_name = node_name
        self.worker_names = worker_names
        self.allow_finish_workflow = allow_finish_workflow
        self.supervisor_config = self.resolve_config(agents)
        self.worker_descriptions = self.describe_workers(agents)
        self.tools, self.route_targets = self.create_tools()
        self.model = ai_provider.get_model(
            model_name=(
                self.supervisor_config.get("model") or ai_provider.SUPERVISOR_MODEL
            ),
            temperature=self.supervisor_config.get("temperature", 0.2),
        ).bind_tools(self.tools)

    def resolve_config(self, agents: list[Dict[str, Any]]) -> Dict[str, Any]:
        """Resolve the local Agent configuration assigned to this node."""

        for config in agents:
            identifier = str(config.get("id") or "")
            if (
                identifier.endswith(f":{self.node_name}")
                or config.get("name") == self.node_name
            ):
                return config
        raise ValueError(
            f"Supervisor node '{self.node_name}' has no local Agent config"
        )

    def describe_workers(self, agents: list[Dict[str, Any]]) -> str:
        """Render the workers exposed by the outer workflow."""

        worker_configs = {
            str(config.get("id") or "").rsplit(":", 1)[-1]: config
            for config in agents
        }
        return "\n".join(
            f"- {worker_name}: "
            f"{worker_configs.get(worker_name, {}).get('description') or worker_name}"
            for worker_name in self.worker_names
        )

    def create_route_tool(self, target: str) -> BaseTool:
        """Create one model tool for selecting an allowed workflow target."""

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

    def create_tools(self) -> tuple[list[BaseTool], Dict[str, str]]:
        """Create constrained model tools and their workflow targets."""

        route_targets = {
            **{
                f"route_to_{worker_name}": worker_name
                for worker_name in self.worker_names
            },
            **({"finish_workflow": "END"} if self.allow_finish_workflow else {}),
        }
        targets = [
            *self.worker_names,
            *(["END"] if self.allow_finish_workflow else []),
        ]
        tools = [
            request_user_input,
            *[self.create_route_tool(target) for target in targets],
        ]
        return tools, route_targets

    def latest_tool_call(self, state: SupervisorState) -> Dict[str, Any]:
        """Read the latest structured decision made by the model."""

        for message in reversed(state.get("messages") or []):
            if isinstance(message, AIMessage) and message.tool_calls:
                return message.tool_calls[0]
        raise ValueError(
            "Supervisor must select exactly one routing or clarification tool"
        )

    def build_control_context(self, state: SupervisorState) -> Dict[str, Any]:
        """Build concise delegated Agent execution reports for the model."""

        agent_reports: Dict[str, Dict[str, Any]] = {}
        for agent_name, agent_state in (state.get("agents") or {}).items():
            results = agent_state.get("results") or {}
            status = agent_state.get("status")
            error = agent_state.get("error")
            has_results = any(
                value not in (None, "", [], {}) for value in results.values()
            )
            has_report = has_results or error or status not in (None, "", "idle")
            if not has_report:
                continue
            agent_reports[agent_name] = {
                "status": status,
                "error": error,
                "results": json_safe(results),
            }
        return {"agent_reports": agent_reports}

    def build_messages(self, state: SupervisorState) -> list[BaseMessage]:
        """Build the routing prompt from configuration and current state."""

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

- Inspect agent_reports before selecting the next Agent.
- If required user information is missing, call request_user_input.
- Do not fabricate business output or bypass the declared workflow order.

Current control state:
{json.dumps(self.build_control_context(state), ensure_ascii=False)}
"""
        system_prompt = str(
            self.supervisor_config.get("system_prompt") or ""
        ).strip()
        return [
            SystemMessage(content=f"{system_prompt}{policy}"),
            *state.get("messages", []),
        ]

    async def decide(self, state: SupervisorState) -> Dict[str, Any]:
        """Request exactly one constrained routing decision from the model."""

        response = await self.model.ainvoke(self.build_messages(state))
        if not isinstance(response, AIMessage) or len(response.tool_calls) != 1:
            raise ValueError(
                "Supervisor must call exactly one routing or clarification tool"
            )
        return {"messages": [response], "next_node": ""}

    def route_decision(self, state: SupervisorState) -> str:
        """Route the tool call to clarification or target selection."""

        tool_name = str(self.latest_tool_call(state).get("name") or "")
        return "clarify" if tool_name == "request_user_input" else "select_route"

    def clarify(self, state: SupervisorState) -> Dict[str, Any]:
        """Pause the graph and return the user's answer to the model."""

        tool_call = self.latest_tool_call(state)
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
                            "answer": json_safe(answer),
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

    def select_route(self, state: SupervisorState) -> Dict[str, Any]:
        """Validate the selected tool and publish the outer workflow target."""

        tool_call = self.latest_tool_call(state)
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

    def build_graph(self):
        """Assemble the constrained agent with native LangGraph APIs."""

        graph = StateGraph(SupervisorState)
        graph.add_node("decide", self.decide)
        graph.add_node("clarify", self.clarify)
        graph.add_node("select_route", self.select_route)
        graph.set_entry_point("decide")
        graph.add_conditional_edges(
            "decide",
            self.route_decision,
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
    """Create a Supervisor Agent that writes its choice to ``next_node``.

    ``max_retries_per_node`` remains accepted for compatibility with older
    generated workflows. Retry limits now belong to the outer workflow graph.
    """

    return WorkflowSupervisor(
        node_name=node_name,
        agents=agents,
        worker_names=worker_names,
        allow_finish_workflow=allow_finish_workflow,
    ).build_graph()
