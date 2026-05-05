"""Chain eval harness — orchestrate multi-step skill eval via Anthropic API.

Usage:
    python -m tests.eval.chain.harness --chain c1_p0_single_plan_review
    python -m tests.eval.chain.harness --chain c1_p0_single_plan_review --runs 3
    python -m tests.eval.chain.harness --all
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import yaml

from .skill_loader import load_skill_prompt
from .context_builder import build_context
from .assertions import run_assertions, validate_assertion_refs

CHAIN_DIR = Path(__file__).parent / "chains"
RESULTS_DIR = Path(__file__).parent / "results"
# tool_schema paths are resolved relative to tests/eval/
EVAL_DIR = Path(__file__).parent.parent

# anthropic is an optional runtime dependency; None when not installed (unit tests mock CLIENT)
try:
    import anthropic
    CLIENT = anthropic.Anthropic()
except ImportError:  # pragma: no cover
    anthropic = None  # type: ignore[assignment]
    CLIENT = None  # type: ignore[assignment]

# Cheaper model for generation steps; individual steps can override with step['model']
DEFAULT_MODEL = "claude-sonnet-4-6-20250514"


def load_chain(chain_id: str) -> dict:
    path = CHAIN_DIR / f"{chain_id}.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_step(step: dict, prior_artifacts: dict[str, dict[str, str]]) -> dict[str, str]:
    """Execute one skill step via the Anthropic API and return captured artifacts."""
    skill_name = step["skill"]
    extra_files = step.get("skill_files")
    skill_prompt = load_skill_prompt(skill_name, extra_files=extra_files)

    context = build_context(step.get("context") or {}, prior_artifacts)

    eval_instruction = step.get("eval_instruction", "")
    system_prompt = (
        f"{skill_prompt}\n\n"
        "IMPORTANT EVAL INSTRUCTION: You are in an evaluation environment without "
        "file system access. Do NOT call Write, Read, Edit, or any file system tools. "
        "Do NOT call AskUserQuestion.\n"
        f"{eval_instruction}\n\n"
        f"## Simulated Project Context\n{context}"
    )

    messages: list[dict] = [{"role": "user", "content": step["input"]}]

    for qa in step.get("mock_user_answers") or []:
        messages.append({"role": "assistant", "content": qa["question_pattern"]})
        messages.append({"role": "user", "content": qa["answer"]})

    kwargs: dict = {
        "model": step.get("model", DEFAULT_MODEL),
        "max_tokens": step.get("max_tokens", 8000),
        "temperature": 0,
        "system": system_prompt,
        "messages": messages,
    }

    tool_schema_ref = step.get("tool_schema")
    if tool_schema_ref:
        tools_path = EVAL_DIR / tool_schema_ref
        with open(tools_path, encoding="utf-8") as f:
            tool_def = json.load(f)
        kwargs["tools"] = [{"name": tool_def["name"], "input_schema": tool_def["input_schema"]}]
        kwargs["tool_choice"] = {"type": "any"}

    response = CLIENT.messages.create(**kwargs)

    artifacts: dict[str, str] = {}
    for block in response.content:
        if block.type == "tool_use":
            artifacts["tool_result"] = json.dumps(block.input, ensure_ascii=False)
            for key, value in block.input.items():
                artifacts[f"field:{key}"] = str(value)
        elif block.type == "text":
            artifacts["text_output"] = block.text

    return artifacts


def run_chain(chain_def: dict) -> dict:
    """Execute a full chain, collecting artifacts at each step, then run assertions."""
    all_artifacts: dict[str, dict[str, str]] = {}
    results: dict = {"chain": chain_def["name"], "steps": [], "assertions": []}

    for step in chain_def["steps"]:
        skill_name = step["skill"]
        print(f"  Running: {skill_name}...", end=" ", flush=True)

        t0 = time.time()
        artifacts = run_step(step, all_artifacts)
        duration = time.time() - t0

        all_artifacts[skill_name] = artifacts
        results["steps"].append({
            "skill": skill_name,
            "duration_s": round(duration, 1),
            "artifact_keys": list(artifacts.keys()),
        })
        print(f"done ({duration:.1f}s)")

    assertion_defs = chain_def.get("assertions") or []
    if assertion_defs:
        try:
            validate_assertion_refs(assertion_defs, all_artifacts)
        except ValueError as exc:
            # Pre-flight validation failure — mark all assertions as failed
            for adef in assertion_defs:
                results["assertions"].append({
                    "name": adef["name"],
                    "passed": False,
                    "error": str(exc),
                })
            return results

    results["assertions"] = run_assertions(assertion_defs, all_artifacts)
    return results


def _save_results(chain_id: str, result: dict) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    out = RESULTS_DIR / f"{chain_id}-{ts}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Results saved: {out}")


def _print_summary(result: dict) -> None:
    passed = sum(1 for a in result["assertions"] if a["passed"])
    total = len(result["assertions"])
    print(f"\n  Assertions: {passed}/{total} passed")
    for a in result["assertions"]:
        status = "✓" if a["passed"] else "✗"
        error = f"  [{a['error']}]" if a.get("error") else ""
        print(f"    {status} {a['name']}{error}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run L3 chain evals")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--chain", help="Chain ID to run (e.g. c1_p0_single_plan_review)")
    group.add_argument("--all", action="store_true", help="Run all chains in chains/")
    parser.add_argument("--runs", type=int, default=1, help="Number of times to run each chain")
    args = parser.parse_args()

    chain_ids = (
        [p.stem for p in sorted(CHAIN_DIR.glob("*.yaml"))]
        if args.all
        else [args.chain]
    )

    for chain_id in chain_ids:
        print(f"\nChain: {chain_id}")
        chain_def = load_chain(chain_id)
        for run_n in range(args.runs):
            if args.runs > 1:
                print(f"  Run {run_n + 1}/{args.runs}")
            result = run_chain(chain_def)
            _save_results(chain_id, result)
            _print_summary(result)


if __name__ == "__main__":
    main()
