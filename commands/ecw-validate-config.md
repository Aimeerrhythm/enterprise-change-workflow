---
name: ecw-validate-config
description: Validate ECW configuration files for completeness and correctness. Checks for unfilled placeholders, missing files, and broken references.
---

# ECW Validate Config

You are running the `/ecw-validate-config` command. Your job is to check the project's ECW configuration for completeness and correctness, then output a structured report. Follow every step below in order.

---

## Step 1: Locate Configuration

Check if `.claude/ecw/` directory exists. If not, report:

```
ECW 未初始化。请先运行 /ecw-init 初始化项目配置。
```

Then stop.

If the directory exists, read `ecw.yml`:

```bash
cat .claude/ecw/ecw.yml
```

Parse the `paths` section to get all configured paths. Fall back to defaults if paths section is missing.

---

## Step 2: Check ecw.yml

Read `.claude/ecw/ecw.yml` and check:

### 2a: Unfilled Placeholders

Search for template placeholders that haven't been replaced:
- `"Your Project Name"` in `project.name`
- Any `{...}` patterns in values
- `component_types` still commented out (only default `Service` entry exists)

### 2b: Language Consistency

- `project.language` should match files in the project root (pom.xml → java, go.mod → go, etc.)
- `scan_patterns` values should be appropriate for the declared language

### 2c: Path Validity

For each path in the `paths` section, check if the referenced file/directory exists:
- `domain_registry`
- `risk_factors`
- `path_mappings`
- `knowledge_root`
- `knowledge_common`
- `calibration_log` (optional, may not exist yet — not an error)

---

## Step 3: Check domain-registry.md

Read the domain registry file (path from ecw.yml or default `.claude/ecw/domain-registry.md`).

### 3a: Empty Check

If the file contains no domain blocks (only template header), flag:
- "域注册表为空，尚未注册任何业务域"

### 3b: Per-Domain Validation

For each registered domain, extract:
- Domain ID
- Knowledge Root path
- Entry Document path
- Code Root path

Check:
- **Knowledge Root exists?** — `ls {knowledge_root}/ 2>/dev/null`
- **Entry Document exists?** — check if the file exists at the specified path
- **Code Root exists?** — `ls {code_root}/ 2>/dev/null`
- **Contains placeholder?** — any `{{...}}` or `{your_...}` patterns remaining

---

## Step 4: Check ecw-path-mappings.md

Read the path mappings file (path from ecw.yml or default `.claude/ecw/ecw-path-mappings.md`).

### 4a: Empty Check

If the file has no mapping rows (only header), flag:
- "路径映射表为空，biz-impact-analysis 和完成验证 hook 的域匹配将依赖启发式规则"

### 4b: Path Existence

For each mapping row (`| path_prefix | domain |`):
- Check if `path_prefix` directory exists in the project
- Check if `domain` is registered in domain-registry.md

Flag mismatches:
- Path doesn't exist → "路径 `{path}` 不存在"
- Domain not registered → "域 `{domain}` 未在 domain-registry.md 中注册"

---

## Step 5: Check change-risk-classification.md

Read the risk classification file.

### 5a: Placeholder Check

Search for unfilled placeholders:
- `{your_...}` patterns
- `{{...}}` patterns
- `TODO` / `TBD` markers

---

## Step 6: Check Knowledge Structure

### 6a: Knowledge Root

Check if the knowledge root directory exists. If not, flag:
- "知识根目录 `{path}` 不存在"

### 6b: Common Knowledge

Check if `knowledge_common` directory exists. If exists, check for the standard files:
- `cross-domain-rules.md`
- `cross-domain-calls.md`
- `mq-topology.md`
- `shared-resources.md`
- `external-systems.md`
- `e2e-paths.md`

For each: check if it exists AND if its content is still the template placeholder (file size < 200 bytes or contains only headers).

### 6c: Domain Knowledge

For each registered domain in domain-registry, check its knowledge directory:
- Does the directory exist?
- Does `00-index.md` (or configured entry doc) exist?
- Are there any `.md` files with actual content?

---

## Step 7: Output Report

Output a structured validation report:

```markdown
## ECW 配置验证报告

### 总览

| 检查项 | 状态 |
|--------|------|
| ecw.yml | {pass/warn/fail} |
| domain-registry.md | {pass/warn/fail} |
| ecw-path-mappings.md | {pass/warn/fail} |
| change-risk-classification.md | {pass/warn/fail} |
| 知识文件结构 | {pass/warn/fail} |

### 问题清单

**必须修复（影响 ECW 功能）：**

{numbered list of critical issues, or "无"}

**建议修复（提升准确性）：**

{numbered list of warnings, or "无"}

### 域健康度

| 域 | 注册 | 知识目录 | 入口文档 | 代码目录 | 路径映射 |
|----|------|---------|---------|---------|---------|
| {domain} | {ok/missing} | {ok/missing} | {ok/missing} | {ok/missing} | {ok/missing} |

### 建议操作

{prioritized list of actions to fix the issues found}
```

Status definitions:
- **pass** — 配置完整，无问题
- **warn** — 配置存在但有待完善项（占位符、空文件）
- **fail** — 配置缺失或严重错误

---

## Error Handling

- If a file cannot be read, log the error and continue checking other files.
- If ecw.yml cannot be parsed, report the parse error and fall back to default paths for remaining checks.
