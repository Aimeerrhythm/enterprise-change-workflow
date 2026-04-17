# ECW 编码约定

> 所有改进 session 必须遵循此文件。这是跨 session 一致性的保障。

## Hook 开发约定

- **语言**: Python 3.8+（与 verify-completion.py 一致）
- **入口**: `def main():`，从 `sys.stdin` 读 JSON
- **错误处理**: `try/except` 包裹 main()，异常时 `print(json.dumps({"result": "continue"}))` + `sys.exit(0)` 不阻塞
- **输出**: JSON 到 stdout，格式参考现有 hook：
  - 放行: `{"result": "continue"}`
  - 放行+提示: `{"result": "continue", "systemMessage": "..."}`
  - 阻断: `{"result": "block", "reason": "..."}`
- **日志**: 写 stderr (`sys.stderr.write`)，不写 stdout
- **stdin 读取**: `json.load(sys.stdin)` + `try/except` 处理格式错误
- **子模块注册**: 通过 dispatcher.py 串联，不直接注册到 hooks.json
- **测试**: 每个 hook 文件对应 `tests/static/test_{name}.py`

## SKILL.md 修改约定

- 新增 subagent dispatch **必须**指定 `model: {haiku|sonnet|opus}`
  - haiku: 机械性任务、简单格式化、轻量检查
  - sonnet: 标准实现、代码审查、验证分析
  - opus: 架构设计、复杂推理、跨域分析
- 新增步骤**必须**包含错误处理：
  - 失败 → Ledger 记录 `[FAILED: {agent_name}, reason: {brief}]` + 用户通知 + 降级路径
- 循环结构**必须**有终止条件：
  - 最大轮次上限 + 无改善升级规则
- 检查点写入时机：每个 Round/Phase 完成后**立即** Write 到 session-data/
- Timeout 建议值：haiku agent 60s, sonnet agent 180s, opus agent 300s

## 文件格式约定

- **session-state.md**: 使用 marker-based 区域更新
  - `<!-- ECW:LEDGER:START -->` / `<!-- ECW:LEDGER:END -->`
  - `<!-- ECW:STATUS:START -->` / `<!-- ECW:STATUS:END -->`
  - 更新时仅替换 marker 内容，保留文件其余部分
- **ecw.yml 扩展**: 新配置节加到文件末尾，不打乱现有节结构
- **agent 文件**: YAML frontmatter 包含 `name`, `model`, `tools` 字段
- **知识文件读取**: 存在性检查 → 缺失时标注 `[degraded: {file} not found]` 并继续

## 命名约定

- Hook 文件: `hooks/{功能名}.py` (如 `session-start.py`, `config-protect.py`)
- Dispatcher 子模块函数: `check_{功能名}(input_data, config)` → 返回 `(result_str, message_str)`
- 测试文件: `tests/static/test_{功能名}.py`
- Agent 文件: `agents/{角色名}.md` (如 `agents/implementer.md`)
- 规则文件: `templates/rules/{language}/{topic}.md`

## Git 分支约定

- 分支名: `wave{N}/{类别简称}` (如 `wave1/hooks-infra`, `wave2/session-hooks`)
- Commit: conventional commits 格式 `feat(hooks): add session-start hook`
- 每个 issue 完成后独立 commit，不要攒到最后一次性提交
