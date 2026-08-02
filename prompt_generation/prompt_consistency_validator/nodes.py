"""Business nodes for the prompt_consistency_validator agent."""

import logging
from typing import Any, Dict

from langchain_core.runnables import RunnableConfig

from app.agents.prompt_generation.prompt_consistency_validator.state import PromptConsistencyValidatorState

logger = logging.getLogger(__name__)
MAX_AUTOMATIC_REPAIRS = 3

# 本文件由 scripts/generate_agent.py 刷新骨架。
# 中文注意：
# - 只在 <agent-node ...> 代码块内部编写业务逻辑。
# - 节点名是 DSL 的稳定标识；节点名不变，刷新时保留对应代码块。
# - 新 DSL 删除某个节点名时，对应代码块会被删除，不会因为里面有人写过代码而保留。

# <agent-node name="prepare_context">
# 中文注意：
# 1. 节点名 "prepare_context" 是 DSL 的稳定标识，不要随手改名。
# 2. 只要 DSL 里还保留这个节点名，刷新骨架时会保留本代码块里的业务逻辑。
# 3. 如果新 DSL 删除了这个节点名，生成器会删除整个代码块，即使里面写过业务代码。
class PrepareContextNode:
    """Handle the prepare context stage."""

    def __call__(
        self,
        state: PromptConsistencyValidatorState,
        config: RunnableConfig | None = None,
    ) -> Dict[str, Any]:
        """Isolate the document, impact set and Prompt IR for validation."""

        # prompt/model/temperature 来自本地 Agent manifest 和 Workflow 节点配置，
        # 由运行时经 Workflow state 注入。
        # 这里可以读取 state["system_prompt"], state["model"], state["temperature"]。
        return {
            "prepared_context": {
                "scene_document": dict(state.get("scene_document") or {}),
                "impact_set": dict(state.get("impact_set") or {}),
                "resolved_prompt_ir": dict(state.get("resolved_prompt_ir") or {}),
            }
        }
# </agent-node>


# <agent-node name="collect_invariants">
# 中文注意：
# 1. 节点名 "collect_invariants" 是 DSL 的稳定标识，不要随手改名。
# 2. 只要 DSL 里还保留这个节点名，刷新骨架时会保留本代码块里的业务逻辑。
# 3. 如果新 DSL 删除了这个节点名，生成器会删除整个代码块，即使里面写过业务代码。
class CollectInvariantsNode:
    """Handle the collect invariants stage."""

    def __call__(
        self,
        state: PromptConsistencyValidatorState,
        config: RunnableConfig | None = None,
    ) -> Dict[str, Any]:
        """Collect the deterministic invariants used by prompt validation."""

        from app.domains.prompt_generation.domain import collect_required_paths

        context = dict(state.get("prepared_context") or {})
        document = context.get("scene_document") or {}
        prompt_ir = context.get("resolved_prompt_ir") or {}
        positive = list(prompt_ir.get("positive_terms") or [])
        negative = list(prompt_ir.get("compiled_negative_terms") or [])
        positive_keys = {
            term_key(item.get("value")) for item in positive if isinstance(item, dict)
        }
        negative_keys = {
            term_key(item.get("value")) for item in negative if isinstance(item, dict)
        }
        covered = set(prompt_ir.get("covered_paths") or [])
        constraint_entries = (prompt_ir.get("constraint_overlay") or {}).get("entries") or {}
        constraint_paths = [
            f"/constraint_overlay/{constraint_id}"
            for constraint_id, entry in constraint_entries.items()
            if isinstance(entry, dict)
            and entry.get("status") == "active"
            and str(entry.get("value") or "").strip()
        ]
        required_paths = [*collect_required_paths(document), *constraint_paths]
        context["validation_inputs"] = {
            "positive": positive,
            "negative": negative,
            "conflicts": sorted(key for key in positive_keys & negative_keys if key),
            "covered": sorted(covered),
            "required_paths": required_paths,
            "missing_paths": [path for path in required_paths if path not in covered],
            "removed": [
                term_key(value)
                for value in (context.get("impact_set") or {}).get("removed_identity_terms") or []
                if value
            ],
        }
        return {"prepared_context": context}
# </agent-node>


# <agent-node name="validate_prompt">
def term_key(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().replace("_", " ").split())


class ValidatePromptNode:
    """Handle the validate prompt stage."""

    def __call__(
        self,
        state: PromptConsistencyValidatorState,
        config: RunnableConfig | None = None,
    ) -> Dict[str, Any]:
        """Validate PromptIR against document and target-language invariants."""

        from langchain_core.messages import AIMessage

        from app.domains.prompt_generation.domain import collect_required_paths, contains_cjk
        from app.domains.prompt_generation.models import ValidationIssue, ValidationReport

        state = {**state, **dict(state.get("prepared_context") or {})}
        document = state.get("scene_document") or {}
        prompt_ir = state.get("resolved_prompt_ir") or {}
        validation_inputs = state.get("validation_inputs")
        if validation_inputs is None:
            positive = prompt_ir.get("positive_terms") or []
            negative = prompt_ir.get("compiled_negative_terms") or []
            positive_keys = {
                term_key(item.get("value"))
                for item in positive
                if isinstance(item, dict)
            }
            negative_keys = {
                term_key(item.get("value"))
                for item in negative
                if isinstance(item, dict)
            }
            conflicts = sorted(key for key in positive_keys & negative_keys if key)
            covered = set(prompt_ir.get("covered_paths") or [])
            constraint_entries = (
                (prompt_ir.get("constraint_overlay") or {}).get("entries") or {}
            )
            constraint_paths = [
                f"/constraint_overlay/{constraint_id}"
                for constraint_id, entry in constraint_entries.items()
                if isinstance(entry, dict)
                and entry.get("status") == "active"
                and str(entry.get("value") or "").strip()
            ]
            required_paths = [*collect_required_paths(document), *constraint_paths]
            missing_paths = [path for path in required_paths if path not in covered]
            removed = [
                term_key(value)
                for value in (state.get("impact_set") or {}).get("removed_identity_terms") or []
                if value
            ]
        else:
            positive = validation_inputs.get("positive") or []
            negative = validation_inputs.get("negative") or []
            conflicts = list(validation_inputs.get("conflicts") or [])
            covered = set(validation_inputs.get("covered") or [])
            required_paths = list(validation_inputs.get("required_paths") or [])
            missing_paths = list(validation_inputs.get("missing_paths") or [])
            removed = list(validation_inputs.get("removed") or [])
        residual_terms = [
            item.get("value")
            for item in positive
            if isinstance(item, dict)
            and any(
                old == term_key(item.get("value")) or old in term_key(item.get("value"))
                for old in removed
            )
        ]
        non_english_items = [
            item
            for item in [*positive, *negative]
            if isinstance(item, dict) and contains_cjk(item.get("value"))
        ]
        participant_ids = set((document.get("participants") or {}).keys())
        orphan_identity_terms = [
            item.get("value")
            for item in prompt_ir.get("identity_terms") or []
            if isinstance(item, dict)
            and item.get("participant_id")
            and item.get("participant_id") not in participant_ids
        ]

        issues = []
        if missing_paths:
            issues.append(
                ValidationIssue(
                    code="missing_required_paths",
                    severity="recoverable",
                    message="Prompt IR does not cover all required scene facts.",
                    affected_paths=missing_paths,
                    suggested_action="repair_missing_paths",
                )
            )
        if conflicts:
            issues.append(
                ValidationIssue(
                    code="positive_negative_conflict",
                    severity="recoverable",
                    message="A semantic term appears in both prompt polarities.",
                    suggested_action="remove_conflicting_terms",
                )
            )
        if residual_terms:
            issues.append(
                ValidationIssue(
                    code="removed_identity_residue",
                    severity="recoverable",
                    message="Prompt IR contains a removed character identity.",
                    suggested_action="remove_identity_residue",
                )
            )
        if non_english_items:
            issues.append(
                ValidationIssue(
                    code="non_target_language",
                    severity="recoverable",
                    message="Prompt IR contains non-English renderer phrases.",
                    affected_paths=[
                        str(item.get("source_path") or "") for item in non_english_items
                    ],
                    suggested_action="normalize_prompt_language",
                )
            )
        if orphan_identity_terms:
            issues.append(
                ValidationIssue(
                    code="unbound_identity_term",
                    severity="blocking",
                    message="An identity term is not bound to a scene participant.",
                )
            )

        report_model = ValidationReport(
            valid=not issues,
            issues=issues,
            missing_paths=missing_paths,
            conflicting_terms=conflicts,
            removed_identity_residue=residual_terms,
            required_path_count=len(required_paths),
            covered_path_count=len(covered),
        )
        report = report_model.model_dump(mode="python")
        report.update(
            {
                "issue_codes": [issue.code for issue in issues],
                "non_target_language_terms": [
                    item.get("value") for item in non_english_items
                ],
                "orphan_identity_terms": orphan_identity_terms,
                "blocked": report_model.blocked,
            }
        )
        return {
            "validation_report": report,
            "needs_repair": report_model.needs_repair and not report_model.blocked,
            "has_blocking_errors": report_model.blocked,
            "messages": [
                AIMessage(
                    content=(
                        "Prompt IR consistency check passed."
                        if not issues
                        else f"Found {len(issues)} consistency issues."
                    ),
                    name="prompt_consistency_validator",
                )
            ],
        }
# </agent-node>


# <agent-node name="finalize_validation">
# 中文注意：
# 1. 节点名 "finalize_validation" 是 DSL 的稳定标识，不要随手改名。
# 2. 只要 DSL 里还保留这个节点名，刷新骨架时会保留本代码块里的业务逻辑。
# 3. 如果新 DSL 删除了这个节点名，生成器会删除整个代码块，即使里面写过业务代码。
class FinalizeValidationNode:
    """Handle the finalize validation stage."""

    def __call__(
        self,
        state: PromptConsistencyValidatorState,
        config: RunnableConfig | None = None,
    ) -> Dict[str, Any]:
        """Validate and normalize the consistency report."""

        from app.domains.prompt_generation.models import ValidationReport

        raw_report = dict(state.get("validation_report") or {})
        core_report = {
            key: value
            for key, value in raw_report.items()
            if key in ValidationReport.model_fields
        }
        report = ValidationReport.model_validate(core_report)
        normalized_report = {
            **raw_report,
            **report.model_dump(mode="python"),
        }
        issue_codes = set(normalized_report.get("issue_codes") or [])
        affected_parts = []
        if any(code in issue_codes for code in {"removed_identity_residue", "unbound_identity_term"}):
            affected_parts.append("character")
        if any(code in issue_codes for code in {"non_target_language", "positive_negative_conflict", "missing_required_paths"}):
            affected_parts.append("visual")
        if report.blocked:
            next_step = "ask_user" if normalized_report.get("missing_paths") else "reanalyze_request"
        elif "character" in affected_parts and "visual" not in affected_parts:
            next_step = "regenerate_character_prompt"
        elif "visual" in affected_parts and "character" not in affected_parts:
            next_step = "regenerate_visual_prompt"
        elif report.needs_repair:
            next_step = "recompile_document"
        else:
            next_step = "finish"
        retry_count = int(state.get("retry_count") or 0) + (0 if next_step == "finish" else 1)
        if next_step != "finish" and retry_count >= MAX_AUTOMATIC_REPAIRS:
            logger.warning(
                "PROMPT_CHECKER_STOPPING_AUTOMATIC_REPAIR retry_count=%s issue_codes=%s",
                retry_count,
                sorted(issue_codes),
            )
            next_step = "ask_user"
        logger.warning(
            "PROMPT_CHECKER_DECISION next_step=%s retry_count=%s issue_codes=%s "
            "missing_paths=%s covered=%s required=%s conflicts=%s "
            "document_version=%s positive_terms=%s negative_terms=%s",
            next_step,
            retry_count,
            sorted(issue_codes),
            sorted(normalized_report.get("missing_paths") or []),
            normalized_report.get("covered_path_count", 0),
            normalized_report.get("required_path_count", 0),
            normalized_report.get("conflicting_terms") or [],
            (state.get("scene_document") or {}).get("version"),
            "unknown",
            "unknown",
        )
        return {
            "validation_report": normalized_report,
            "needs_repair": report.needs_repair,
            "has_blocking_errors": report.blocked,
            "validation_route": "repair" if report.needs_repair and not report.blocked else "render",
            "check_result": {"valid": not bool(normalized_report.get("issues")), "issue_codes": sorted(issue_codes)},
            "check_passed": not bool(normalized_report.get("issues")),
            "next_step": next_step,
            "problem_summary": "; ".join(issue.get("message", "") for issue in normalized_report.get("issues", [])),
            "clarification_request": (
                "???????????????"
                + "; ".join(issue.get("message", "") for issue in normalized_report.get("issues", []))
                if next_step == "ask_user"
                else ""
            ),
            "problem_details": normalized_report.get("issues", []),
            "affected_parts": affected_parts,
            "retry_count": retry_count,
        }
# </agent-node>


# Transitional callable aliases for existing integrations.
prepare_context_node = PrepareContextNode()
collect_invariants_node = CollectInvariantsNode()
validate_prompt_node = ValidatePromptNode()
finalize_validation_node = FinalizeValidationNode()
