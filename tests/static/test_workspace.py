"""Tests for workspace skill — Phase gate integrity, coordination protocol,
lifecycle safety rules, anti-pattern enforcement, and file contract compliance.
"""
from __future__ import annotations

import json
import re

import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SKILL_DIR = ROOT / "skills" / "workspace"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def skill_md():
    return (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def skill_lower(skill_md):
    return skill_md.lower()


@pytest.fixture(scope="module")
def lifecycle_md():
    return (SKILL_DIR / "lifecycle-commands.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def lifecycle_lower(lifecycle_md):
    return lifecycle_md.lower()


@pytest.fixture(scope="module")
def coordination_md():
    return (SKILL_DIR / "coordination-protocol.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def terminal_md():
    return (SKILL_DIR / "terminal-adapters.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def anti_patterns_md():
    return (SKILL_DIR / "prompts" / "anti-patterns.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def analysis_task_template_md():
    return (SKILL_DIR / "workspace-analysis-task-template.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# TestWorkspaceSubcommands — sub-command surface
# ---------------------------------------------------------------------------

class TestWorkspaceSubcommands:
    """SKILL.md must document all five sub-commands."""

    def test_has_create_subcommand(self, skill_md):
        assert "create" in skill_md.lower()

    def test_has_run_subcommand(self, skill_md):
        assert "run" in skill_md.lower()

    def test_has_status_subcommand(self, skill_md):
        assert "status" in skill_md.lower()

    def test_has_push_subcommand(self, skill_md):
        assert "push" in skill_md.lower()

    def test_has_destroy_subcommand(self, skill_md):
        assert "destroy" in skill_md.lower()

    def test_manual_trigger_only(self, skill_lower):
        """Workspace must NOT be auto-triggered by risk-classifier."""
        assert "manual" in skill_lower
        assert re.search(r'not auto.?trigger|manual only', skill_lower)


# ---------------------------------------------------------------------------
# TestPhaseGateArchitecture — 6-phase gate enforcement
# ---------------------------------------------------------------------------

class TestPhaseGateArchitecture:
    """SKILL.md must specify all 6 phases with gate-in / gate-out artifacts."""

    def test_has_preflight_phase(self, skill_lower):
        assert "pre-flight" in skill_lower or "preflight" in skill_lower

    def test_has_six_phases(self, skill_md):
        phases = re.findall(r'phase\s*[1-6]', skill_md.lower())
        assert len(set(phases)) >= 6, f"Expected 6 distinct phases, found: {set(phases)}"

    def test_gate_in_mentioned(self, skill_lower):
        assert "gate-in" in skill_lower

    def test_gate_out_mentioned(self, skill_lower):
        assert "gate-out" in skill_lower

    def test_phase1_cross_service_plan_artifact(self, skill_md):
        """Phase 1 must write cross-service-plan.md."""
        assert "cross-service-plan.md" in skill_md

    def test_phase2_analysis_report_artifact(self, skill_md):
        """Phase 2 gate-out must check analysis-report.md for all services."""
        assert "analysis-report.md" in skill_md

    def test_phase3_confirmed_contract_artifact(self, skill_md):
        """Phase 3 must write confirmed-contract.md per service."""
        assert "confirmed-contract.md" in skill_md

    def test_phase4_status_json_artifact(self, skill_md):
        """Phase 4 gate-out must verify status.json per service."""
        assert "status.json" in skill_md

    def test_enforce_previous_artifact_before_next_phase(self, skill_lower):
        """Must require previous artifact to exist before entering next phase."""
        assert re.search(r'(must exist|verify.{0,30}exist|exists.{0,30}before|stop.{0,30}missing)', skill_lower)

    def test_session_state_updated_each_phase(self, skill_lower):
        """Each phase must update session-state.md."""
        assert "session-state.md" in skill_lower
        assert re.search(r'update session.?state', skill_lower)


# ---------------------------------------------------------------------------
# TestPhase1Constraints — code-free information constraint
# ---------------------------------------------------------------------------

class TestPhase1Constraints:
    """Phase 1 must enforce code-free information constraint."""

    def test_no_code_reading_in_phase1(self, skill_lower):
        """Phase 1 must prohibit code reading tools."""
        assert re.search(r'phase 1.{0,300}no.{0,30}(read|bash|glob|grep|explore)', skill_lower) or \
               re.search(r'(no read|no bash|no glob|no grep|no explore).{0,300}phase 1', skill_lower) or \
               re.search(r'code.?free.{0,200}phase 1', skill_lower) or \
               re.search(r'phase 1.{0,200}code.?free', skill_lower)

    def test_workspace_yml_only_source_in_phase1(self, skill_lower):
        """Phase 1 information source must be workspace.yml only."""
        assert re.search(r'workspace\.yml.{0,100}only|only.{0,30}workspace\.yml|only.{0,30}information source', skill_lower)

    def test_no_class_method_in_phase1_output(self, skill_lower):
        """Phase 1 output must not contain class/method names."""
        assert re.search(r'class name|method name|field name|sql.{0,30}(violation|phase 1)', skill_lower) or \
               re.search(r'phase 1.{0,200}(violation|class|method)', skill_lower)

    def test_unclear_interaction_pattern_flag(self, skill_lower):
        """Phase 1 must allow marking interaction type as 'unclear' for Phase 2."""
        assert "unclear" in skill_lower


# ---------------------------------------------------------------------------
# TestPhase3ContractAlignment — contract conflict resolution rules
# ---------------------------------------------------------------------------

class TestPhase3ContractAlignment:
    """Phase 3 must enforce single-path contract with user-driven conflict resolution."""

    def test_mq_contract_cross_validation(self, skill_lower):
        """Phase 3 must validate MQ topic/DTO producer-consumer consistency."""
        assert re.search(r'mq contracts|mq.{0,50}(topic|dto)', skill_lower) or \
               re.search(r'(producer|consumer).{0,100}(topic|dto).{0,100}(mq|match)', skill_lower)

    def test_dubbo_contract_cross_validation(self, skill_lower):
        """Phase 3 must validate Dubbo interface signature consistency."""
        assert re.search(r'dubbo contracts|dubbo.{0,50}(interface|signature|provider)', skill_lower)

    def test_conflict_requires_user_decision(self, skill_lower):
        """Contract conflicts must surface to user via AskUserQuestion."""
        assert re.search(r'conflict.{0,200}askuserquestion|askuserquestion.{0,200}conflict', skill_lower)

    def test_no_options_in_confirmed_contract(self, skill_lower):
        """confirmed-contract.md must not contain 'A or B' choices."""
        assert re.search(r'multiple implementation options', skill_lower) or \
               re.search(r'(do not|not|never|exclusion).{0,100}(a or b|choice|option).{0,100}confirmed.?contract', skill_lower)

    def test_execution_order_in_contract(self, skill_lower):
        """confirmed-contract.md must include execution order / layer assignment."""
        assert re.search(r'execution.?order|layer.?assign', skill_lower)


# ---------------------------------------------------------------------------
# TestPhase5CrossServiceVerification — cross-service checks
# ---------------------------------------------------------------------------

class TestPhase5CrossServiceVerification:
    """Phase 5 must perform MQ and Dubbo cross-service compatibility checks."""

    def test_mq_field_name_check(self, skill_lower):
        """Phase 5 must verify MQ DTO field names match between producer/consumer."""
        assert re.search(r'field name.{0,100}(match|exact|producer|consumer)', skill_lower) or \
               re.search(r'mq.{0,200}field.{0,30}(match|check|exact)', skill_lower)

    def test_mq_field_type_check(self, skill_lower):
        """Phase 5 must verify MQ DTO field types match."""
        assert re.search(r'field type.{0,100}(match|producer|consumer)', skill_lower) or \
               re.search(r'mq.{0,200}type.{0,30}(match|check)', skill_lower)

    def test_mq_topic_name_check(self, skill_lower):
        """Phase 5 must verify topic names match between producer and consumer."""
        assert re.search(r'topic.{0,30}name.{0,50}(match|producer|consumer)', skill_lower)

    def test_dubbo_method_signature_check(self, skill_lower):
        """Phase 5 must verify Dubbo method signatures match."""
        assert re.search(r'provider interface method signature|dubbo.{0,200}(signature|method)', skill_lower)


# ---------------------------------------------------------------------------
# TestCoordinationProtocol — status.json and polling
# ---------------------------------------------------------------------------

class TestCoordinationProtocol:
    """coordination-protocol.md must define correct schemas and polling."""

    def test_status_json_has_service_field(self, coordination_md):
        assert '"service"' in coordination_md

    def test_status_json_has_status_field(self, coordination_md):
        assert '"status"' in coordination_md

    def test_status_json_has_summary_field(self, coordination_md):
        assert '"summary"' in coordination_md

    def test_status_json_has_files_changed_field(self, coordination_md):
        assert '"files_changed"' in coordination_md

    def test_status_json_has_commits_field(self, coordination_md):
        assert '"commits"' in coordination_md

    def test_status_json_has_error_field(self, coordination_md):
        assert '"error"' in coordination_md

    def test_status_values_documented(self, coordination_md):
        """Must document completed/failed/blocked status values."""
        lower = coordination_md.lower()
        assert "completed" in lower
        assert "failed" in lower
        assert "blocked" in lower

    def test_api_ready_json_schema(self, coordination_md):
        """Dubbo api-ready.json schema must be defined."""
        assert "api-ready.json" in coordination_md
        assert '"api_module"' in coordination_md
        assert '"version"' in coordination_md

    def test_polling_timeout_120_minutes(self, coordination_md):
        """Polling timeout must be 120 minutes."""
        lower = coordination_md.lower()
        assert "120" in coordination_md
        assert re.search(r'120.{0,20}minute|timeout.{0,50}120', lower)

    def test_polling_iterations_1440(self, coordination_md):
        """Polling loop must use 1440 iterations (1440 x 5s = 120min)."""
        assert "1440" in coordination_md

    def test_polling_interval_5_seconds(self, coordination_md):
        """Polling sleep interval must be 5 seconds."""
        assert "sleep 5" in coordination_md or "5 seconds" in coordination_md.lower()

    def test_timeout_handling_documented(self, coordination_md):
        """Must document timeout handling — options in SKILL.md or here."""
        lower = coordination_md.lower()
        skill_lower = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8").lower()
        assert re.search(r'timeout.{0,200}(continue|skip|abort)', lower) or \
               re.search(r'timeout.{0,200}(continue|skip|abort)', skill_lower)

    def test_skill_md_references_coordination_protocol(self, skill_lower):
        """SKILL.md must reference coordination-protocol.md."""
        assert "coordination-protocol.md" in skill_lower

    def test_child_session_state_in_artifact_locations(self, coordination_md):
        """coordination-protocol.md Artifact Locations must list child session-state.md.

        Child sessions write session-state.md at the workspace wf-id path so the
        coordinator can observe per-service ECW flow progress at a known location.
        """
        lower = coordination_md.lower()
        assert "session-state.md" in lower, \
            "child session-state.md missing from coordination-protocol.md Artifact Locations"
        assert re.search(r'session-state\.md.{0,80}child|child.{0,80}session-state\.md', lower), \
            "child session-state.md not clearly attributed to child session in artifact table"


# ---------------------------------------------------------------------------
# TestLifecycleCommands — create / destroy safety
# ---------------------------------------------------------------------------

class TestLifecycleCreate:
    """create command must follow safe, ordered steps."""

    def test_requires_requirement_text(self, lifecycle_lower):
        """create must extract and validate requirement text — empty blocks progression."""
        assert re.search(r'requirement.{0,100}(required|empty|blocks|cannot|must)', lifecycle_lower)

    def test_service_discovery_validates_git_repo(self, lifecycle_lower):
        """Service discovery must validate each directory is a git repository."""
        assert re.search(r'(\.git|git repo).{0,100}(valid|check|confirm)', lifecycle_lower) or \
               re.search(r'(valid|check|confirm).{0,100}(\.git|git repo)', lifecycle_lower)

    def test_branch_conflict_detection(self, lifecycle_lower):
        """Must detect branch conflicts before creating worktrees."""
        assert re.search(r'branch.{0,50}(conflict|already.?checked.?out|exist)', lifecycle_lower)

    def test_user_confirmation_mandatory(self, lifecycle_lower):
        """User confirmation step must be mandatory before any destructive action."""
        assert re.search(r'mandatory|confirmation.{0,50}(step|mandatory)', lifecycle_lower) or \
               re.search(r'askuserquestion.{0,200}confirm', lifecycle_lower)

    def test_worktree_based_on_origin(self, lifecycle_lower):
        """Worktrees must be created from origin/{base_branch}, not local branch."""
        assert re.search(r'origin.{0,20}base.?branch|origin/.{0,30}(always|guarantee|latest)', lifecycle_lower)

    def test_settings_local_json_written_first(self, lifecycle_lower):
        """settings.local.json must be written before other ECW files."""
        assert "settings.local.json" in lifecycle_lower
        assert re.search(r'(first|before).{0,100}settings.local.json|settings.local.json.{0,100}(first|before)', lifecycle_lower)

    def test_gitignore_updated_for_session_artifacts(self, lifecycle_lower):
        """Service .gitignore must be updated to exclude ECW session artifacts."""
        assert ".gitignore" in lifecycle_lower
        assert re.search(r'session.?data|ecw/state', lifecycle_lower)

    def test_workspace_path_in_parent_workspaces_dir(self, lifecycle_lower):
        """Workspace directory must be created inside parent workspaces/ directory."""
        assert re.search(r'workspaces/.{0,40}name|parent.{0,100}workspaces', lifecycle_lower) or \
               "workspaces/" in lifecycle_lower


class TestLifecycleDestroy:
    """destroy command must include safety checks."""

    def test_warns_uncommitted_changes(self, lifecycle_lower):
        """destroy must warn about uncommitted or unpushed changes."""
        assert re.search(r'(uncommit|unpush).{0,100}(warn|check|safety)', lifecycle_lower) or \
               re.search(r'(warn|check|safety).{0,100}(uncommit|unpush)', lifecycle_lower)

    def test_requires_user_confirmation(self, lifecycle_lower):
        """destroy must require explicit user confirmation."""
        assert re.search(r'destroy.{0,500}askuserquestion|askuserquestion.{0,200}confirm', lifecycle_lower)

    def test_removes_git_worktrees(self, lifecycle_lower):
        """destroy must call git worktree remove."""
        assert "worktree remove" in lifecycle_lower or \
               re.search(r'git.{0,30}worktree.{0,30}remove', lifecycle_lower)


# ---------------------------------------------------------------------------
# TestTerminalAdapters — terminal detection and clipboard safety
# ---------------------------------------------------------------------------

class TestTerminalAdapters:
    """terminal-adapters.md must cover detection logic and safe input method."""

    def test_ghostty_adapter_defined(self, terminal_md):
        assert "ghostty" in terminal_md.lower()

    def test_iterm2_adapter_defined(self, terminal_md):
        assert "iterm2" in terminal_md.lower() or "iterm" in terminal_md.lower()

    def test_tmux_adapter_defined(self, terminal_md):
        assert "tmux" in terminal_md.lower()

    def test_manual_fallback_adapter_defined(self, terminal_md):
        assert "manual" in terminal_md.lower() and "fallback" in terminal_md.lower()

    def test_detection_uses_term_program(self, terminal_md):
        """Must detect terminal type via $TERM_PROGRAM."""
        assert "TERM_PROGRAM" in terminal_md

    def test_clipboard_paste_not_keystroke(self, terminal_md):
        """Ghostty adapter must use clipboard paste, not direct keystroke."""
        lower = terminal_md.lower()
        assert "clipboard" in lower
        assert re.search(r'(not|avoid).{0,30}keystroke|keystroke.{0,30}(corrupt|fail|input method)', lower) or \
               re.search(r'clipboard.{0,100}(instead|not.{0,30}keystroke)', lower)

    def test_workspace_yml_adapter_override(self, terminal_md):
        """Must support terminal.adapter override in workspace.yml."""
        assert re.search(r'workspace\.yml.{0,100}(override|adapter)', terminal_md.lower()) or \
               re.search(r'(override|adapter).{0,100}workspace\.yml', terminal_md.lower())

    def test_skill_md_references_terminal_adapters(self, skill_lower):
        """SKILL.md must reference terminal-adapters.md."""
        assert "terminal-adapters.md" in skill_lower


# ---------------------------------------------------------------------------
# TestAntiPatterns — never-rules enforcement
# ---------------------------------------------------------------------------

class TestAntiPatterns:
    """anti-patterns.md and SKILL.md must encode critical never-rules."""

    def test_no_code_reading_in_phase1_anti_pattern(self, anti_patterns_md):
        """Anti-patterns must prohibit code reading in Phase 1."""
        lower = anti_patterns_md.lower()
        assert re.search(r'(never|no).{0,60}(read|bash|glob|grep|explore).{0,60}phase 1', lower) or \
               re.search(r'phase 1.{0,100}(never|code.?reading|no read)', lower)

    def test_no_implementation_tasks_by_coordinator_anti_pattern(self, anti_patterns_md):
        """Anti-patterns must prohibit coordinator writing implementation tasks."""
        lower = anti_patterns_md.lower()
        assert re.search(r'never.{0,60}(implementation task|writing.?plan|task.{0,30}decomp)', lower) or \
               re.search(r'(child session|coordinator).{0,100}(own|must not|never).{0,60}task', lower)

    def test_no_paraphrase_requirement_anti_pattern(self, anti_patterns_md):
        """Anti-patterns must prohibit paraphrasing the original requirement."""
        lower = anti_patterns_md.lower()
        assert re.search(r'(never|no).{0,40}paraphrase|paraphrase.{0,50}(never|not|lose)', lower)

    def test_no_silent_conflict_resolution_anti_pattern(self, anti_patterns_md):
        """Anti-patterns must prohibit resolving contract conflicts without user."""
        lower = anti_patterns_md.lower()
        assert re.search(r'(never|no).{0,60}(conflict.{0,30}without.{0,30}user|pick one side|resolve.{0,30}conflict)', lower) or \
               re.search(r'(user|human).{0,50}(judgment|decide|decision).{0,50}conflict', lower)

    def test_no_dubbo_parallel_without_api_ready_anti_pattern(self, anti_patterns_md):
        """Anti-patterns must prohibit running Dubbo Provider+Consumer in parallel without api-ready.json."""
        lower = anti_patterns_md.lower()
        assert re.search(r'(never|no).{0,60}(parallel.{0,30}dubbo|dubbo.{0,30}parallel)', lower) or \
               re.search(r'api.?ready\.json.{0,100}(consumer|dubbo|non.?blocking)', lower)

    def test_no_phase4_new_scripts_anti_pattern(self, anti_patterns_md):
        """Anti-patterns must prohibit coordinator generating Phase 4 start scripts."""
        lower = anti_patterns_md.lower()
        assert re.search(r'(never|no).{0,60}(phase 4.{0,30}(start|script)|new.{0,30}script.{0,30}phase 4)', lower) or \
               re.search(r'analysis session.{0,100}(continue|auto)', lower)

    def test_no_keystroke_on_macos_anti_pattern(self, anti_patterns_md):
        """Anti-patterns must prohibit keystroke on macOS."""
        lower = anti_patterns_md.lower()
        assert re.search(r'(never|no).{0,30}keystroke', lower)

    def test_no_assume_terminal_type_anti_pattern(self, anti_patterns_md):
        """Anti-patterns must prohibit assuming terminal type."""
        lower = anti_patterns_md.lower()
        assert re.search(r'(never|no).{0,30}assume.{0,30}terminal', lower)

    def test_skill_md_references_anti_patterns(self, skill_lower):
        """SKILL.md must reference anti-patterns.md."""
        assert "anti-patterns.md" in skill_lower


# ---------------------------------------------------------------------------
# TestOutputLanguageCompliance — UTF-8 encoding rules
# ---------------------------------------------------------------------------

class TestOutputLanguageCompliance:
    """SKILL.md must specify output_language handling and UTF-8 encoding."""

    def test_output_language_field_documented(self, skill_lower):
        assert "output_language" in skill_lower

    def test_utf8_native_encoding_required(self, skill_lower):
        """Must require native UTF-8, prohibit Unicode escape sequences."""
        assert re.search(r'native.{0,30}utf.?8|utf.?8.{0,30}native', skill_lower)
        assert re.search(r'(no|never|not).{0,40}(unicode escape|\\u[0-9a-f]{4}|escape sequence)', skill_lower)

    def test_output_language_passed_to_child_sessions(self, skill_lower):
        """output_language must be passed explicitly to child session prompts."""
        assert re.search(r'output.?language.{0,100}(pass|explicit|child session|prompt)', skill_lower) or \
               re.search(r'(pass|explicit).{0,100}output.?language', skill_lower)


# ---------------------------------------------------------------------------
# TestDataContractCompliance — contracts match SKILL.md content
# ---------------------------------------------------------------------------

class TestDataContractCompliance:
    """Artifacts declared in data_contracts.yaml must actually appear in SKILL.md."""

    @pytest.fixture(autouse=True)
    def load_yaml(self):
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not installed")
        contracts_path = ROOT / "tests" / "static" / "data_contracts.yaml"
        if not contracts_path.exists():
            pytest.skip("data_contracts.yaml not found")
        with open(contracts_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self.workspace_contract = data.get("skills", {}).get("workspace", {})
        self.skill_content = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")

    def test_workspace_skill_defined_in_contracts(self):
        """workspace skill must have a contract entry."""
        assert self.workspace_contract, "workspace not found in data_contracts.yaml"

    def test_cross_service_plan_path_in_skill_md(self):
        """cross-service-plan path pattern must appear in SKILL.md."""
        writes = self.workspace_contract.get("writes", [])
        cross_plan = next((w for w in writes if w.get("key") == "cross-service-plan"), None)
        assert cross_plan is not None, "cross-service-plan not in workspace writes"
        pattern = cross_plan["path_pattern"].split("{")[0].rstrip("/")
        assert pattern in self.skill_content, f"path pattern '{pattern}' not in SKILL.md"

    def test_workspace_analysis_task_path_in_skill_md(self):
        """workspace-analysis-task path pattern must appear in SKILL.md."""
        writes = self.workspace_contract.get("writes", [])
        task = next((w for w in writes if w.get("key") == "workspace-analysis-task"), None)
        assert task is not None
        assert "workspace-analysis-task.md" in self.skill_content

    def test_confirmed_contract_path_in_skill_md(self):
        """confirmed-contract path pattern must appear in SKILL.md."""
        writes = self.workspace_contract.get("writes", [])
        contract = next((w for w in writes if w.get("key") == "confirmed-contract"), None)
        assert contract is not None
        assert "confirmed-contract.md" in self.skill_content

    def test_workspace_yml_read_in_skill_md(self):
        """workspace.yml read must be documented in SKILL.md."""
        reads = self.workspace_contract.get("reads", [])
        ws_yml = next((r for r in reads if r.get("key") == "workspace-yml"), None)
        assert ws_yml is not None
        assert "workspace.yml" in self.skill_content

    def test_analysis_report_read_in_skill_md(self):
        """analysis-report read must be documented in SKILL.md."""
        reads = self.workspace_contract.get("reads", [])
        report = next((r for r in reads if r.get("key") == "analysis-report"), None)
        assert report is not None
        assert "analysis-report.md" in self.skill_content

    def test_subagent_dispatches_documented(self):
        """SKILL.md must describe child session dispatch for phase2-analysis and phase4-impl."""
        dispatches = self.workspace_contract.get("subagent_dispatches", [])
        phases = {d["phase"] for d in dispatches}
        assert "phase2-analysis" in phases, "phase2-analysis dispatch not in contract"
        assert "phase4-impl" in phases, "phase4-impl dispatch not in contract"

    def test_ask_user_question_in_skill_md(self):
        """Contract says ask_user_question: true — SKILL.md must use AskUserQuestion."""
        assert self.workspace_contract.get("ask_user_question") is True
        assert "askuserquestion" in self.skill_content.lower()


# ---------------------------------------------------------------------------
# TestWorkspaceArtifactSchema — workspace artifacts in artifact-schemas.md
# ---------------------------------------------------------------------------

class TestWorkspaceArtifactSchema:
    """Workspace-specific artifacts must be documented in artifact-schemas.md."""

    WORKSPACE_ARTIFACTS = [
        "cross-service-plan.md",
        "confirmed-contract.md",
        "status.json",
    ]

    @pytest.fixture(autouse=True)
    def load_schema(self):
        schema_path = ROOT / "templates" / "artifact-schemas.md"
        if not schema_path.exists():
            pytest.skip("artifact-schemas.md not found")
        self.schema_content = schema_path.read_text(encoding="utf-8")

    def test_cross_service_plan_in_schema(self):
        assert "cross-service-plan.md" in self.schema_content

    def test_confirmed_contract_in_schema(self):
        assert "confirmed-contract.md" in self.schema_content

    def test_status_json_in_schema(self):
        assert "status.json" in self.schema_content


# ---------------------------------------------------------------------------
# TestStatusJsonSchemaValidation — SKILL.md must embed gate-out validation
# ---------------------------------------------------------------------------

class TestStatusJsonGateOutValidation:
    """Phase 4 gate-out must validate all required status.json fields."""

    REQUIRED_STATUS_FIELDS = ["service", "status", "summary", "files_changed", "commits", "error"]

    def test_all_required_fields_in_gate_out(self, skill_md):
        """Phase 4 gate-out must reference all status.json required fields."""
        for field in self.REQUIRED_STATUS_FIELDS:
            assert field in skill_md, f"Required status.json field '{field}' not in SKILL.md gate-out"

    def test_gate_out_uses_validation_command(self, skill_lower):
        """Phase 4 gate-out must show a concrete validation command."""
        assert re.search(r'python3|jq|missing', skill_lower)


# ---------------------------------------------------------------------------
# TestAnalysisTaskTemplate — child session wf-id and session-state behavior
# ---------------------------------------------------------------------------

class TestAnalysisTaskTemplate:
    """workspace-analysis-task-template.md must enforce workspace wf-id usage."""

    def test_wf_id_override_instruction_present(self, analysis_task_template_md):
        """Phase 4 must instruct child session to use workspace wf-id, not a new timestamp.

        Without this override, risk-classifier generates its own timestamp wf-id and writes
        session-state.md to an unknown path, making child session progress invisible to coordinator.
        """
        lower = analysis_task_template_md.lower()
        assert re.search(
            r'wf.?id.{0,100}(override|workspace|do not generate|not.{0,20}timestamp|not.{0,20}new)',
            lower,
        ) or re.search(
            r'(override|workspace wf.?id|do not generate).{0,100}wf.?id',
            lower,
        ), "wf-id override instruction missing from Phase 4 of workspace-analysis-task-template.md"

    def test_child_session_state_path_uses_workspace_wf_id(self, analysis_task_template_md):
        """Child session must write session-state.md under the workspace wf-id path."""
        assert re.search(
            r'\.claude/ecw/session-data/\{wf-id\}/session-state\.md',
            analysis_task_template_md,
        ), "child session-state.md path with {wf-id} not found in template Phase 4"

    def test_no_coordinator_session_state_update(self, analysis_task_template_md):
        """Child session must NOT update coordinator's session-state.md."""
        lower = analysis_task_template_md.lower()
        assert re.search(
            r'(do not|not).{0,30}(coordinator.{0,30}session.?state|update.{0,30}coordinator)',
            lower,
        ), "template must explicitly forbid child session from updating coordinator's session-state.md"
