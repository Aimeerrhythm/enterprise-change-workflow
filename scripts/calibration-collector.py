#!/usr/bin/env python3
"""Collect Phase 3 multi-skill calibration data for ECW.

Usage:
    python3 scripts/calibration-collector.py <project_root> <session_data_dir>

Outputs structured YAML to stdout with calibration dimensions:
  - domain_calibration: predicted vs actual domains
  - plan_calibration: predicted vs actual task count, file coverage
  - spec_challenge_calibration: acceptance rate from User Decisions table
  - requirements_calibration: requirement-dimension findings from impl-verify

All git operations and file parsing are done here (deterministic).
Phase 3 prompt reads the YAML output and performs semantic analysis.
"""

import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]


# ── STATUS section parsing ───────────────────────────────────────────────────

def _parse_status(content: str) -> dict:
    """Extract YAML from <!-- ECW:STATUS:START/END --> markers."""
    m = re.search(
        r"<!--\s*ECW:STATUS:START\s*-->(.*?)<!--\s*ECW:STATUS:END\s*-->",
        content, re.DOTALL
    )
    if not m:
        return {}
    block = m.group(1).strip()
    if yaml:
        try:
            data = yaml.safe_load(block)
            return data if isinstance(data, dict) else {}
        except Exception:
            pass
    result = {}
    for line in block.splitlines():
        line = line.strip()
        if ":" in line:
            key, _, val = line.partition(":")
            result[key.strip()] = val.strip()
    return result


# ── ecw-path-mappings.md parsing ─────────────────────────────────────────────

def _parse_path_mappings(mappings_path: Path) -> list[tuple[str, str]]:
    """Return list of (path_pattern, domain) from ecw-path-mappings.md.

    Expects a markdown table:
      | Path Pattern | Domain |
      |---|---|
      | src/payment/ | payment |
    """
    if not mappings_path.exists():
        return []
    rows = []
    in_table = False
    for line in mappings_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            in_table = False
            continue
        if re.match(r"\|[\s\-:|]+\|", stripped):
            in_table = True
            continue
        cols = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cols) < 2:
            continue
        pattern, domain = cols[0].strip(), cols[1].strip()
        if pattern.lower() in ("path pattern", "path") or not pattern or not domain:
            continue
        rows.append((pattern, domain))
    return rows


def _files_to_domains(files: list[str], mappings: list[tuple[str, str]]) -> set[str]:
    """Map changed files to their domains using path mappings."""
    domains = set()
    for filepath in files:
        for pattern, domain in mappings:
            if pattern in filepath or filepath.startswith(pattern.lstrip("/")):
                domains.add(domain)
                break
    return domains


# ── Git helpers ──────────────────────────────────────────────────────────────

def _git(cmd: list[str], cwd: str) -> str:
    try:
        result = subprocess.run(
            ["git"] + cmd,
            capture_output=True, text=True, cwd=cwd
        )
        return result.stdout.strip()
    except Exception:
        return ""


def _get_changed_files(cwd: str, baseline: str) -> list[str]:
    if baseline and baseline != "TBD":
        output = _git(["diff", "--name-only", f"{baseline}..HEAD"], cwd)
    else:
        # Fallback: find first "step 1:" commit and use its parent
        log = _git(["log", "--oneline", "--reverse"], cwd)
        baseline = _find_baseline_from_log(log)
        if baseline:
            output = _git(["diff", "--name-only", f"{baseline}~1..HEAD"], cwd)
        else:
            output = _git(["diff", "--name-only", "HEAD~1..HEAD"], cwd)
    return [f for f in output.splitlines() if f.strip()]


def _get_commit_log(cwd: str, baseline: str) -> list[str]:
    if baseline and baseline != "TBD":
        output = _git(["log", "--oneline", f"{baseline}..HEAD"], cwd)
    else:
        log = _git(["log", "--oneline"], cwd)
        output = log
    return [ln for ln in output.splitlines() if ln.strip()]


def _find_baseline_from_log(log_output: str) -> str:
    """Heuristic: find the commit hash of the first 'step 1:' commit."""
    for line in log_output.splitlines():
        if re.search(r"\bstep\s+1\s*:", line, re.IGNORECASE):
            return line.split()[0]
    return ""


# ── Plan file parsing ────────────────────────────────────────────────────────

def _find_plan_file(project_root: Path, status: dict):
    plan_path = status.get("plan_path")
    if plan_path:
        p = Path(plan_path)
        if not p.is_absolute():
            p = project_root / p
        if p.exists():
            return p

    plans_dir = project_root / ".claude" / "plans"
    if plans_dir.exists():
        candidates = sorted(plans_dir.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
        if candidates:
            return candidates[0]
    return None


def _parse_plan(plan_path: Path) -> tuple[int, list[str]]:
    """Return (task_count, file_list) from a Plan markdown file."""
    content = plan_path.read_text(encoding="utf-8", errors="ignore")
    task_count = len(re.findall(r"^#{2,4}\s+Task\s+\d+", content, re.MULTILINE))
    # Extract files from backtick-quoted paths and explicit file lists
    files = re.findall(r"`([^`]+\.[a-zA-Z]{1,6})`", content)
    # Filter to look like file paths (contain / or .)
    files = [f for f in files if ("/" in f or f.count(".") >= 1)
             and not f.startswith("http") and len(f) > 3]
    return task_count, list(dict.fromkeys(files))  # deduplicate, preserve order


# ── spec-challenge-report.md User Decisions parsing ─────────────────────────

def _parse_user_decisions(report_path: Path):
    """Parse ## User Decisions table. Returns None if absent."""
    if not report_path.exists():
        return None
    content = report_path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"##\s+User Decisions\s*\n(.*?)(?=\n##|\Z)", content, re.DOTALL | re.IGNORECASE)
    if not m:
        return None
    section = m.group(1)
    accepted = rejected = deferred = 0
    for line in section.splitlines():
        cols = [c.strip().lower() for c in line.strip("|").split("|")]
        if len(cols) < 2:
            continue
        decision = cols[1] if len(cols) > 1 else ""
        if "accept" in decision:
            accepted += 1
        elif "reject" in decision:
            rejected += 1
        elif "defer" in decision:
            deferred += 1
    if accepted + rejected + deferred == 0:
        return None
    return {"accepted": accepted, "rejected": rejected, "deferred": deferred}


# ── impl-verify-findings.md parsing ─────────────────────────────────────────

def _count_requirement_findings(findings_path: Path) -> tuple[int, list[str]]:
    """Count findings with dimension=requirements in impl-verify-findings.md."""
    if not findings_path.exists():
        return 0, []
    content = findings_path.read_text(encoding="utf-8", errors="ignore")
    gaps = []
    for line in content.splitlines():
        if re.search(r"dimension.{0,20}require", line, re.IGNORECASE):
            gaps.append(line.strip())
    return len(gaps), gaps


# ── Routing helpers ──────────────────────────────────────────────────────────

def _routing_contains(routing, *skill_keywords: str) -> bool:
    """Check if any of the skill_keywords appear in the routing list."""
    if not routing:
        return False
    if isinstance(routing, str):
        routing = [routing]
    joined = " ".join(str(s).lower() for s in routing)
    return any(kw.lower() in joined for kw in skill_keywords)


# ── Main ─────────────────────────────────────────────────────────────────────

def _format_yaml(data: dict) -> str:
    if yaml:
        return yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)
    # Minimal YAML serializer fallback
    lines = []
    for k, v in data.items():
        if isinstance(v, dict):
            lines.append(f"{k}:")
            for sk, sv in v.items():
                lines.append(f"  {sk}: {_yaml_scalar(sv)}")
        elif isinstance(v, list):
            if not v:
                lines.append(f"{k}: []")
            else:
                lines.append(f"{k}:")
                for item in v:
                    lines.append(f"  - {_yaml_scalar(item)}")
        else:
            lines.append(f"{k}: {_yaml_scalar(v)}")
    return "\n".join(lines) + "\n"


def _yaml_scalar(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    if any(c in s for c in (":", "#", "'", '"', "\n")):
        return f'"{s}"'
    return s


def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <project_root> <session_data_dir>", file=sys.stderr)
        sys.exit(1)

    project_root = Path(sys.argv[1])
    session_data_dir = Path(sys.argv[2])

    state_file = session_data_dir / "session-state.md"
    if not state_file.exists():
        print("Error: session-state.md not found", file=sys.stderr)
        sys.exit(1)

    state_content = state_file.read_text(encoding="utf-8", errors="ignore")
    status = _parse_status(state_content)

    routing = status.get("routing") or []
    if isinstance(routing, str):
        routing = [s.strip() for s in routing.split(",")]

    baseline_commit = str(status.get("baseline_commit") or "TBD").strip()
    predicted_domains = status.get("domains") or []
    if isinstance(predicted_domains, str):
        predicted_domains = [d.strip() for d in predicted_domains.strip("[]").split(",")]

    cwd = str(project_root)

    # --- Domain Calibration ---
    if not _routing_contains(routing, "domain-collab"):
        domain_cal: dict = {"skipped": True, "reason": "domain-collab not in routing chain"}
    else:
        mappings_path = project_root / ".claude" / "ecw" / "ecw-path-mappings.md"
        mappings = _parse_path_mappings(mappings_path)
        changed_files = _get_changed_files(cwd, baseline_commit)
        actual_domains = _files_to_domains(changed_files, mappings)
        predicted_set = set(d.strip() for d in predicted_domains if d.strip())
        over_predicted = sorted(predicted_set - actual_domains)
        missed = sorted(actual_domains - predicted_set)
        domain_cal = {
            "skipped": False,
            "predicted": sorted(predicted_set),
            "actual": sorted(actual_domains),
            "over_predicted": over_predicted,
            "missed": missed,
        }

    # --- Plan Calibration ---
    if not _routing_contains(routing, "writing-plans"):
        plan_cal: dict = {"skipped": True, "reason": "writing-plans not in routing chain"}
    else:
        plan_file = _find_plan_file(project_root, status)
        if not plan_file:
            plan_cal = {"skipped": True, "reason": "plan file not found"}
        else:
            planned_tasks, planned_files = _parse_plan(plan_file)
            commits = _get_commit_log(cwd, baseline_commit)
            actual_commits = len(commits)
            changed_files_for_plan = _get_changed_files(cwd, baseline_commit)
            planned_set = set(f.lstrip("/") for f in planned_files)
            actual_set = set(changed_files_for_plan)
            uncovered = sorted(f for f in actual_set
                               if not any(pf in f or f in pf for pf in planned_set))
            task_ratio = round(actual_commits / planned_tasks, 2) if planned_tasks > 0 else None
            plan_cal = {
                "skipped": False,
                "planned_tasks": planned_tasks,
                "actual_commits": actual_commits,
                "task_ratio": task_ratio,
                "planned_files": sorted(planned_set),
                "actual_files": sorted(actual_set),
                "uncovered_files": uncovered,
            }

    # --- Spec-Challenge Calibration ---
    if not _routing_contains(routing, "spec-challenge"):
        sc_cal: dict = {"skipped": True, "reason": "spec-challenge not in routing chain"}
    else:
        report_path = session_data_dir / "spec-challenge-report.md"
        decisions = _parse_user_decisions(report_path)
        if decisions is None:
            sc_cal = {"skipped": True, "reason": "no User Decisions table in spec-challenge-report.md"}
        else:
            total = decisions["accepted"] + decisions["rejected"]
            acceptance_rate = round(decisions["accepted"] / total, 2) if total > 0 else None
            sc_cal = {
                "skipped": False,
                "accepted": decisions["accepted"],
                "rejected": decisions["rejected"],
                "deferred": decisions["deferred"],
                "acceptance_rate": acceptance_rate,
            }

    # --- Requirements Calibration ---
    if not _routing_contains(routing, "requirements-elicitation"):
        req_cal: dict = {"skipped": True, "reason": "requirements-elicitation not in routing chain"}
    else:
        findings_path = session_data_dir / "impl-verify-findings.md"
        gap_count, gaps = _count_requirement_findings(findings_path)
        req_cal = {
            "skipped": False,
            "requirement_gap_count": gap_count,
            "gaps": gaps,
        }

    output = {
        "domain_calibration": domain_cal,
        "plan_calibration": plan_cal,
        "spec_challenge_calibration": sc_cal,
        "requirements_calibration": req_cal,
    }
    print(_format_yaml(output))


if __name__ == "__main__":
    main()
