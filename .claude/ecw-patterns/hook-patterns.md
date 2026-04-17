# Hook 实现参考模式

> 从 ECC (everything-claude-code) 提炼的关键模式，已本地化为 ECW Python 版本

## 1. Dispatcher 模式

**来源**: [ECC bash-hook-dispatcher.js](https://github.com/affaan-m/everything-claude-code/blob/main/scripts/hooks/bash-hook-dispatcher.js)

**原理**: hooks.json 只注册一个 dispatcher → dispatcher 内部串联多个子模块 → 按 profile 过滤哪些子模块执行

**ECW 实现方案**:

```python
# hooks/dispatcher.py — PreToolUse 统一入口
import importlib
import json
import sys

# 子模块注册表：(模块名, 适用 profiles, matcher 函数)
SUB_HOOKS = [
    ("verify_completion", ["minimal", "standard", "strict"], lambda inp: is_task_complete(inp)),
    ("config_protect",    ["minimal", "standard", "strict"], lambda inp: is_edit_or_write(inp)),
    ("secret_scan",       ["standard", "strict"],            lambda inp: is_edit_or_write(inp)),
    ("bash_preflight",    ["standard", "strict"],            lambda inp: is_bash(inp)),
]

def get_profile():
    """从 session-state 或环境变量读取当前风险等级 → 映射为 profile"""
    # P0→strict, P1→standard, P2→standard, P3→minimal
    ...

def main():
    input_data = json.load(sys.stdin)
    profile = get_profile()
    
    for module_name, profiles, matcher in SUB_HOOKS:
        if profile not in profiles:
            continue
        if not matcher(input_data):
            continue
        module = importlib.import_module(f"hooks.{module_name}")
        result, message = module.check(input_data)
        if result == "block":
            print(json.dumps({"result": "block", "reason": message}))
            return
    
    print(json.dumps({"result": "continue"}))
```

**hooks.json 注册（简化后）**:
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "*",
        "hooks": [{"type": "command", "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/dispatcher.py\"", "timeout": 150}]
      }
    ]
  }
}
```

## 2. Profile 门控

**来源**: [ECC hook-flags.js](https://github.com/affaan-m/everything-claude-code/blob/main/scripts/lib/hook-flags.js)

**ECW 映射**:

| 风险等级 | Profile | 执行哪些检查 |
|---------|---------|------------|
| P0 | strict | 全部：completion + config + secret + bash + quality + fact-force |
| P1 | standard | 多数：completion + config + secret + bash + quality |
| P2 | standard | 同 P1 |
| P3 | minimal | 仅基础：completion + config |

**风险等级获取优先级**:
1. 环境变量 `ECW_RISK_LEVEL`
2. `.claude/ecw/state/session-state.md` 中的 risk_level 字段
3. 默认 `standard`

## 3. SessionStart 注入

**来源**: [ECC session-start.js](https://github.com/affaan-m/everything-claude-code/blob/main/scripts/hooks/session-start.js)

**ECW 实现方案**:

```python
# hooks/session-start.py
def main():
    input_data = json.load(sys.stdin)
    cwd = input_data.get("cwd", "")
    
    context_parts = []
    
    # 1. 检测 session-state
    state_file = os.path.join(cwd, ".claude/ecw/state/session-state.md")
    if os.path.exists(state_file):
        content = read_file(state_file)
        context_parts.append(f"# ECW Session State (auto-loaded)\n{content}")
    
    # 2. 检测最新 session-data 检查点
    data_dir = os.path.join(cwd, ".claude/ecw/session-data/")
    if os.path.isdir(data_dir):
        files = sorted(glob.glob(f"{data_dir}/*.md"), key=os.path.getmtime, reverse=True)
        if files:
            summary = f"Available checkpoints: {', '.join(os.path.basename(f) for f in files[:5])}"
            context_parts.append(summary)
    
    # 3. 注入 ecw.yml 关键配置
    ecw_yml = os.path.join(cwd, ".claude/ecw/ecw.yml")
    if os.path.exists(ecw_yml):
        # 提取 project name, language, type
        ...
    
    # 4. 检测未完成 TaskList
    context_parts.append("Check TaskList for pending work from previous session.")
    
    result = {
        "hookSpecificOutput": {
            "additionalContext": "\n\n".join(context_parts)
        }
    }
    print(json.dumps(result, ensure_ascii=False))
```

## 4. Stop 持久化

**来源**: [ECC session-end.js](https://github.com/affaan-m/everything-claude-code/blob/main/scripts/hooks/session-end.js)

**关键技术**: Marker-based 幂等更新

```python
def update_marker_section(content, marker_name, new_content):
    """替换 <!-- ECW:{marker}:START --> 和 <!-- ECW:{marker}:END --> 之间的内容"""
    start_marker = f"<!-- ECW:{marker_name}:START -->"
    end_marker = f"<!-- ECW:{marker_name}:END -->"
    
    if start_marker in content:
        # 替换已有内容
        pattern = re.compile(
            re.escape(start_marker) + r".*?" + re.escape(end_marker),
            re.DOTALL
        )
        return pattern.sub(f"{start_marker}\n{new_content}\n{end_marker}", content)
    else:
        # 追加新 section
        return content + f"\n\n{start_marker}\n{new_content}\n{end_marker}\n"
```

## 5. 配置保护

**来源**: [ECC config-protection.js](https://github.com/affaan-m/everything-claude-code/blob/main/scripts/hooks/config-protection.js)

**ECW 保护文件列表**:
```python
PROTECTED_FILES = {
    "ecw.yml",
    "domain-registry.md",
    "change-risk-classification.md",
    "ecw-path-mappings.md",
    "cross-domain-rules.md",
    "cross-domain-calls.md",
    "mq-topology.md",
    "shared-resources.md",
    "external-systems.md",
    "e2e-paths.md",
}

def check(input_data):
    file_path = input_data.get("tool_input", {}).get("file_path", "")
    basename = os.path.basename(file_path)
    if basename in PROTECTED_FILES:
        return ("block", f"阻止修改 ECW 配置文件 {basename}。请修改源代码或业务逻辑，而非配置。"
                         f"如需修改配置，请用户手动操作或设置 ECW_ALLOW_CONFIG_EDIT=1。")
    return ("continue", "")
```

## 6. Secret 扫描

**来源**: [ECC governance-capture.js](https://github.com/affaan-m/everything-claude-code/blob/main/scripts/hooks/governance-capture.js)

**检测模式**:
```python
SECRET_PATTERNS = [
    (r'(?:AKIA|ASIA)[A-Z0-9]{16}', "AWS Access Key"),
    (r'(?:secret|password|token|api_key)\s*[=:]\s*["\']?[^\s"\']{8,}', "Generic Secret"),
    (r'-----BEGIN (?:RSA |EC )?PRIVATE KEY-----', "Private Key"),
    (r'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}', "JWT Token"),
    (r'gh[pousr]_[A-Za-z0-9_]{36,}', "GitHub Token"),
]
```
