---
name: knowledge-repomap
description: Auto-generate code structure index (Repo Map). Extracts class names and method signatures for component types defined in ecw.yml (e.g., Facade/BizService/Manager), grouped by domain or directory. Recommended during ecw-init and after major refactors.
---

# Code Structure Index Generator (Repo Map)

You are a code structure indexing tool. When user invokes this Skill, automatically scan project code and generate a structured index of class names and method signatures.

## Prerequisites

Check if `.claude/ecw/ecw.yml` exists:
- Exists → Read `component_types`, `knowledge_maintenance.repomap_group_by_dir`, `project.name`
- Not exists → Prompt user to run `/ecw-init` first

## Generation Steps

### Step 1: Read Configuration

Extract from `ecw.yml`:
- `component_types[]` — Component types to scan (name, grep_pattern, search_path)
- Output file: `.claude/ecw/knowledge-ops/repo-map.md` (fixed convention)
- `repomap_group_by_dir` — Whether to group by subdirectory (default true)
- `project.name` — Project name (for title)

### Step 2: Run Generation Script

Based on `project.language`:

**Java projects**:
```bash
bash scripts/java/generate-repo-map.sh <project_root> <ecw_yml_path>
```

The script will:
1. Extract component types from `component_types`
2. Find matching files under corresponding `search_path`
3. Extract class names and public method signatures
4. Group output based on `repomap_group_by_dir` setting
5. Write to `.claude/ecw/knowledge-ops/repo-map.md`

**Other languages**:
- Currently Java only
- Prompt user: Repo Map generation not yet supported for this language, create manually or contribute a script

### Step 3: Verify Output

Read the generated repo-map file, check:
- File was created successfully
- Total class count is reasonable (> 0)
- Each component type has matching results

### Step 4: Output Summary

```markdown
## Repo Map Generation Complete

- Output path: `.claude/ecw/knowledge-ops/repo-map.md`
- Scanned component types: <component_types list>
- Total: X classes
- Grouping: <by directory / flat>

The generated Repo Map can be used for:
1. Quick code entry point location (Facade, Controller)
2. Understanding overall project structure
3. Supplementary navigation alongside knowledge base

Suggestions:
- Run `/ecw:knowledge-repomap` to refresh after code structure changes
- Can be integrated into CI/CD pipeline for automatic generation
```

## ECW Workflow Integration

Recommended usage timing:
1. **During ecw-init** — Generate Repo Map alongside knowledge base initialization (runs automatically with other scanners)
2. **After major refactors** — Regenerate when class names/structure changed significantly
3. **Periodic maintenance** — Refresh monthly or quarterly to keep index current

Relationship between Repo Map and knowledge base:
- **Knowledge base** — Records business logic, constraints, why
- **Repo Map** — Provides code structure skeleton, quick location

They complement each other; Repo Map is the zero-maintenance navigation layer.

## Notes

- Repo Map is auto-generated, should not be manually edited (file header marks "do not edit manually")
- If project has no `ecw.yml`, prompt user to run `/ecw-init`
- On generation failure, check if `component_types` configuration is correct
- Large projects (>1000 classes) may take 10-30 seconds to generate
