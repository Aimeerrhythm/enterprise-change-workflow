# Troubleshooting

Common issues when using ECW and how to resolve them.

## Installation & Setup

### Plugin not showing in `claude plugin list`

**Symptom**: After running `claude plugin install`, the plugin does not appear.

**Fix**:
1. Verify `~/.claude/settings.json` has the correct `extraKnownMarketplaces` entry
2. Re-run `claude plugin install ecw@enterprise-change-workflow`
3. Restart the Claude Code session (plugins load at session start)

### `/ecw-init` command not recognized

**Symptom**: Claude does not recognize the `/ecw-init` command.

**Fix**:
1. Check `enabledPlugins` in `~/.claude/settings.json` includes `"ecw@enterprise-change-workflow": true`
2. Restart the session — plugins are loaded at startup, not dynamically
3. If still missing, run `claude plugin list` to confirm installation status

## Configuration Issues

### `/ecw-validate-config` shows many warnings after init

**Symptom**: Fresh `ecw-init` followed by validation shows unfilled placeholders.

**This is expected.** `ecw-init` generates template files that need to be customized:
- Replace `{{...}}` placeholders in knowledge files with actual project data
- Replace `{your_...}` placeholders in `change-risk-classification.md` with project-specific keywords
- Populate cross-domain knowledge files (`cross-domain-calls.md`, `mq-topology.md`, etc.)

Priority: Start with `domain-registry.md` and `ecw-path-mappings.md`, then populate knowledge files.

### `ecw.yml` parse error

**Symptom**: Skills fail with YAML parse errors when reading `ecw.yml`.

**Fix**:
1. Validate YAML syntax: `python3 -c "import yaml; yaml.safe_load(open('.claude/ecw/ecw.yml'))"`
2. Common issues: incorrect indentation, missing quotes around values with colons, tabs instead of spaces
3. Compare against `templates/ecw.yml` in the plugin directory for the expected structure

### Path mappings not matching

**Symptom**: `biz-impact-analysis` or `verify-completion` cannot map files to domains.

**Fix**:
1. Open `.claude/ecw/ecw-path-mappings.md` and verify paths match your project structure
2. Entries with `?` in the domain column are unresolved — fill them in
3. Paths are prefix-matched: `src/main/java/com/biz/order/` matches any file under that directory
4. Run scanning scripts to auto-discover mappings: `bash <plugin-path>/scripts/java/scan-cross-domain-calls.sh`

## Hook Issues

### verify-completion hook not firing

**Symptom**: Marking a task as complete does not trigger the verification hook.

**Diagnosis**:
1. Check `hooks/hooks.json` is valid JSON: `python3 -c "import json; json.load(open('hooks/hooks.json'))"`
2. The hook triggers on `TaskUpdate` with `status=completed` only — other TaskUpdate calls are ignored
3. Verify the plugin is installed and enabled (hook paths use `${CLAUDE_PLUGIN_ROOT}`)

### "Broken reference" blocks completion

**Symptom**: `verify-completion` reports a broken `.claude/` path reference.

**Fix**:
1. The error message shows which file contains the broken reference and which path is missing
2. Common causes:
   - Typo in the path (e.g., `.claude/ecw/sesion-state.md` instead of `session-state.md`)
   - Referenced file was moved or deleted but references were not updated
   - Template placeholder was not replaced (e.g., `{domain-id}` still in path)
3. Fix the reference in the source file, or create the missing file

### Java compilation/test check blocks completion

**Symptom**: Hook reports `mvn compile` or `mvn test` failure.

**Fix**:
1. Fix the compilation or test errors — the hook runs `mvn compile -q -T 1C` and `mvn test -q -T 1C`
2. If tests are slow, set `verification.run_tests: false` in `.claude/ecw/ecw.yml` to skip test checks
3. If `mvn` is not in PATH, the check is automatically skipped (no error)
4. Timeout defaults: compile = 120s, test = 300s (configurable via `verification.test_timeout` in ecw.yml)

### Hook error crashes silently

**Symptom**: Hook appears to not run, but no error message is shown.

**Diagnosis**:
1. Hooks output JSON to stdout — if the JSON is malformed, the hook output is silently discarded
2. Run the hook manually to see errors: `echo '{"tool_name":"TaskUpdate","tool_input":{"status":"completed"},"cwd":"/your/project"}' | python3 hooks/verify-completion.py`
3. Check Python version: hooks require Python 3.8+
4. Check PyYAML: `python3 -c "import yaml"` — if missing, some checks are skipped gracefully

## Workflow Issues

### Risk classification seems inaccurate

**Symptom**: Phase 1 predicts wrong risk level (e.g., P3 for a critical change).

**Fix**:
1. **Keyword coverage**: Review `.claude/ecw/change-risk-classification.md` — add missing domain-specific keywords
2. **Shared resources**: Review `.claude/knowledge/common/shared-resources.md` — missing entries cause under-classification
3. **Phase 3 calibration**: After completing a task, Phase 3 compares prediction vs actual impact and suggests rule adjustments. Apply these suggestions to improve future classifications

### domain-collab routes incorrectly

**Symptom**: Single-domain requirement gets routed to multi-domain analysis, or vice versa.

**Fix**:
1. Check `domain-registry.md` — domain boundaries must be clear and non-overlapping
2. Check the routing keyword table in your project `CLAUDE.md` — ambiguous keywords can trigger wrong domains
3. Phase 2 corrects Phase 1 mistakes — if Phase 1 misroutes, Phase 2 should upgrade/downgrade

### session-state.md is corrupted

**Symptom**: Session state file has garbled content or conflicting sections.

**Fix**:
1. Delete `.claude/ecw/session-state.md` — it will be regenerated when the next workflow starts
2. If session-data checkpoint files exist (under `.claude/ecw/session-data/`), they can be used to resume
3. This typically happens when a session was interrupted during a write operation

### impl-verify loops without converging

**Symptom**: impl-verify keeps finding new issues for 3+ rounds without reducing must-fix count.

**Fix**:
1. impl-verify has a 5-round maximum — it will force-exit after that
2. If findings are not reducing, check if the fixes are introducing new issues (regression)
3. Consider running `/ecw:impl-verify` manually to inspect each round's findings
4. For complex changes, address must-fix findings by category rather than one at a time

## Performance

### ECW workflow takes too long

**Symptom**: P0 full workflow (risk-classifier → domain-collab → writing-plans → spec-challenge → implementation → impl-verify → biz-impact-analysis) takes many turns.

**Mitigation**:
1. This is expected for P0 critical changes — the depth is the value
2. Use `/compact` at logical breakpoints (between Skills) to keep context manageable
3. For P2/P3 changes, the workflow is much shorter — ensure risk classification is accurate
4. If a change was over-classified, Phase 2 can downgrade it
