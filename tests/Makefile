PYTHON ?= python3

.PHONY: lint lint-md lint-py test-hook test-contracts test-simulator eval-quick eval-full eval-domain-collab eval-tdd eval-impl-verify eval-all-skills all clean _check-api-key

# Layer 1: 静态结构验证（<3s, $0）
lint: lint-md lint-py
	$(PYTHON) static/lint_skills.py

# Markdown 格式检查（需要 markdownlint-cli: npm install -g markdownlint-cli）
lint-md:
	@command -v markdownlint >/dev/null 2>&1 && \
		markdownlint --config ../.markdownlint.json \
			../skills/*/SKILL.md ../agents/*.md ../commands/*.md \
			../templates/rules/**/*.md ../CONTRIBUTING.md 2>&1 || \
		echo "SKIP: markdownlint not installed (npm install -g markdownlint-cli)"

# Python 代码质量检查（需要 ruff: pip install ruff）
lint-py:
	@command -v ruff >/dev/null 2>&1 && \
		ruff check --config ../ruff.toml ../hooks/*.py ../tests/static/**/*.py 2>&1 || \
		echo "SKIP: ruff not installed (pip install ruff)"

# Layer 1b: hook 单元测试（<10s, $0）
test-hook:
	$(PYTHON) -m pytest static/hooks/ -v

# Layer 1c: 数据契约验证（<5s, $0）
test-contracts:
	$(PYTHON) -m pytest static/consistency/test_data_contracts.py -v

# Layer 1.5: 工作流模拟器（<5s, $0）
test-simulator:
	$(PYTHON) -m pytest static/consistency/test_workflow_simulator.py -v

# Layer 2: risk-classifier P0 场景行为 Eval（~2min, ~$0.50）
# 成功后创建 eval-cleared.stamp，解锁 SKILL.md 行为变更的 git commit
eval-quick: _check-api-key
	cd eval && npx promptfoo eval --filter-pattern "s0[1-8]-*" && \
	mkdir -p ../.claude/ecw/state && \
	touch ../.claude/ecw/state/eval-cleared.stamp

# Layer 2: risk-classifier 全部场景行为 Eval（~5min, ~$1.50）
eval-full: _check-api-key
	cd eval && npx promptfoo eval

# Layer 2b: domain-collab 行为 Eval（~2min, ~$0.50）
eval-domain-collab: _check-api-key
	cd eval/domain-collab && npx promptfoo eval

# Layer 2b: tdd 行为 Eval（~2min, ~$0.50）
eval-tdd: _check-api-key
	cd eval/tdd && npx promptfoo eval

# Layer 2b: impl-verify 行为 Eval（~2min, ~$0.50）
eval-impl-verify: _check-api-key
	cd eval/impl-verify && npx promptfoo eval

# Layer 2b: 全部 Skill 行为 Eval
eval-all-skills: eval-full eval-domain-collab eval-tdd eval-impl-verify

# 日常开发：静态 + hook 测试 + 契约 + 模拟器 + P0 场景
all: lint test-hook test-contracts test-simulator eval-quick

# 清理缓存
clean:
	rm -rf .pytest_cache static/__pycache__ eval/.promptfoo

_check-api-key:
	@test -n "$$ANTHROPIC_API_KEY" || (echo "ERROR: ANTHROPIC_API_KEY not set. Run: export ANTHROPIC_API_KEY=your-key" && exit 1)
