PYTHON ?= python3

.PHONY: lint lint-md lint-py test-hook eval-quick eval-full all clean _check-api-key

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
		ruff check --config ../ruff.toml ../hooks/*.py ../tests/static/*.py 2>&1 || \
		echo "SKIP: ruff not installed (pip install ruff)"

# Layer 1b: hook 单元测试（<10s, $0）
test-hook:
	$(PYTHON) -m pytest static/test_verify_completion.py static/test_dispatcher.py static/test_post_edit_check.py static/test_config_protect.py static/test_secret_scan.py static/test_bash_preflight.py static/test_hooks_json.py -v

# Layer 2: P0 场景行为 Eval（~2min, ~$0.50）
eval-quick: _check-api-key
	cd eval && npx promptfoo eval --filter-pattern "s0[1-8]-*"

# Layer 2: 全部 15 场景行为 Eval（~5min, ~$1.50）
eval-full: _check-api-key
	cd eval && npx promptfoo eval

# 日常开发：静态 + hook 测试 + P0 场景
all: lint test-hook eval-quick

# 清理缓存
clean:
	rm -rf .pytest_cache static/__pycache__ eval/.promptfoo

_check-api-key:
	@test -n "$$ANTHROPIC_API_KEY" || (echo "ERROR: ANTHROPIC_API_KEY not set. Run: export ANTHROPIC_API_KEY=your-key" && exit 1)
