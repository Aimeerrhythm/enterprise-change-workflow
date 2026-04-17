PYTHON ?= python3

.PHONY: lint test-hook eval-quick eval-full all clean _check-api-key

# Layer 1: 静态结构验证（<3s, $0）
lint:
	$(PYTHON) static/lint_skills.py

# Layer 1b: hook 单元测试（<10s, $0）
test-hook:
	$(PYTHON) -m pytest static/test_verify_completion.py static/test_dispatcher.py static/test_post_edit_check.py static/test_hooks_json.py static/test_session_start.py static/test_stop_persist.py static/test_session_end.py static/test_pre_compact.py static/test_marker_utils.py static/test_compact_suggest.py -v

# Layer 2: risk-classifier P0 场景行为 Eval（~2min, ~$0.50）
eval-quick: _check-api-key
	cd eval && npx promptfoo eval --filter-pattern "s0[1-8]-*"

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

# 日常开发：静态 + hook 测试 + P0 场景
all: lint test-hook eval-quick

# 清理缓存
clean:
	rm -rf .pytest_cache static/__pycache__ eval/.promptfoo

_check-api-key:
	@test -n "$$ANTHROPIC_API_KEY" || (echo "ERROR: ANTHROPIC_API_KEY not set. Run: export ANTHROPIC_API_KEY=your-key" && exit 1)
