#!/usr/bin/env bash
#
# release.sh — ECW 统一发版脚本
#
# 用法:
#   ./scripts/release.sh <version>           # 交互式，需确认后 push
#   ./scripts/release.sh <version> --force   # 跳过确认直接 push
#
# 示例:
#   ./scripts/release.sh 0.3.2
#   ./scripts/release.sh 0.3.2 --force
#
# 执行步骤:
#   1. 校验版本格式 (semver)、工作区干净、在 main 分支
#   2. 更新 package.json, .claude-plugin/plugin.json, README.md badge
#   3. 生成 CHANGELOG.md 占位 section (若尚无该版本条目)
#   4. git add + commit + tag
#   5. push to origin (含 tags)
#
set -euo pipefail

# ── 颜色 ────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

info()  { printf "${CYAN}[info]${NC}  %s\n" "$*"; }
ok()    { printf "${GREEN}[ok]${NC}    %s\n" "$*"; }
warn()  { printf "${YELLOW}[warn]${NC}  %s\n" "$*"; }
die()   { printf "${RED}[error]${NC} %s\n" "$*" >&2; exit 1; }

# ── 参数解析 ─────────────────────────────────────────
VERSION="${1:-}"
FORCE=false
[[ "${2:-}" == "--force" ]] && FORCE=true

if [[ -z "$VERSION" ]]; then
  echo "用法: $0 <version> [--force]"
  echo "示例: $0 0.3.2"
  exit 1
fi

# semver 校验 (x.y.z，允许可选 -pre.tag)
if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$ ]]; then
  die "版本号格式无效: $VERSION (期望 semver: x.y.z)"
fi

# ── 项目根目录 ───────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

# ── 前置检查 ─────────────────────────────────────────
# 工作区必须干净
if [[ -n "$(git status --porcelain)" ]]; then
  die "工作区不干净，请先提交或 stash 所有变更"
fi

# 必须在 main 分支
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$BRANCH" != "main" ]]; then
  die "当前分支是 $BRANCH，release 必须在 main 分支执行"
fi

# tag 不能已存在
if git rev-parse "v$VERSION" >/dev/null 2>&1; then
  die "Tag v$VERSION 已存在，请选择新版本号"
fi

# 读取当前版本
OLD_VERSION="$(python3 -c "import json; print(json.load(open('package.json'))['version'])")"
info "当前版本: $OLD_VERSION → 目标版本: $VERSION"

# ── 1. 更新 package.json ────────────────────────────
info "更新 package.json"
python3 -c "
import json, pathlib
p = pathlib.Path('package.json')
d = json.loads(p.read_text())
d['version'] = '$VERSION'
p.write_text(json.dumps(d, indent=2, ensure_ascii=False) + '\n')
"
ok "package.json → $VERSION"

# ── 2. 更新 .claude-plugin/plugin.json ──────────────
PLUGIN_JSON=".claude-plugin/plugin.json"
if [[ -f "$PLUGIN_JSON" ]]; then
  info "更新 $PLUGIN_JSON"
  python3 -c "
import json, pathlib
p = pathlib.Path('$PLUGIN_JSON')
d = json.loads(p.read_text())
d['version'] = '$VERSION'
p.write_text(json.dumps(d, indent=2, ensure_ascii=False) + '\n')
"
  ok "$PLUGIN_JSON → $VERSION"
else
  warn "$PLUGIN_JSON 不存在，跳过"
fi

# ── 3. 更新 README.md version badge ─────────────────
info "更新 README.md version badge"
# 匹配 shields.io version badge: version-x.y.z-color
sed -i '' -E "s/version-[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?-blue/version-${VERSION}-blue/g" README.md
ok "README.md badge → $VERSION"

# ── 4. 更新 CHANGELOG.md ────────────────────────────
info "更新 CHANGELOG.md"
TODAY="$(date +%Y-%m-%d)"

# 检查是否已有该版本条目
if grep -qF "## [$VERSION]" CHANGELOG.md; then
  warn "CHANGELOG.md 已包含 [$VERSION] 条目，跳过生成"
else
  # 在第一个 ## [...] 之前插入新版本 section
  python3 -c "
import re, pathlib

p = pathlib.Path('CHANGELOG.md')
content = p.read_text()

new_section = '''## [$VERSION] - $TODAY

### 新增

- TODO

### 修复

- TODO

### 增强

- TODO

'''

# 找到第一个版本标题行 (## [x.y.z])
match = re.search(r'^## \[', content, re.MULTILINE)
if match:
    pos = match.start()
    content = content[:pos] + new_section + content[pos:]
else:
    content += '\n' + new_section

p.write_text(content)
"
  ok "CHANGELOG.md 添加 [$VERSION] section (请编辑 TODO 内容)"
fi

# 更新底部链接引用
REPO_URL="https://github.com/Aimeerrhythm/enterprise-change-workflow"
LINK_LINE="[$VERSION]: ${REPO_URL}/releases/tag/v${VERSION}"

if ! grep -qF "[$VERSION]:" CHANGELOG.md; then
  # 追加到文件末尾（链接引用区域）
  echo "$LINK_LINE" >> CHANGELOG.md
  ok "CHANGELOG.md 添加 [$VERSION] 链接引用"
fi

# 补全所有已有 tag 但缺失链接引用的版本
for tag in $(git tag -l 'v*' | sort -V); do
  tag_ver="${tag#v}"
  if grep -qF "## [$tag_ver]" CHANGELOG.md && ! grep -qF "[$tag_ver]:" CHANGELOG.md; then
    echo "[$tag_ver]: ${REPO_URL}/releases/tag/${tag}" >> CHANGELOG.md
    ok "CHANGELOG.md 补全 [$tag_ver] 链接引用"
  fi
done

# ── 5. 汇总变更 ─────────────────────────────────────
echo ""
info "变更文件:"
git diff --stat
echo ""
git diff --no-color

# ── 6. 提交 + Tag ───────────────────────────────────
echo ""
if [[ "$FORCE" != true ]]; then
  printf "${YELLOW}确认发布 v$VERSION? [y/N]${NC} "
  read -r CONFIRM
  if [[ "$CONFIRM" != "y" && "$CONFIRM" != "Y" ]]; then
    # 回滚所有变更
    git checkout -- .
    die "已取消"
  fi
fi

git add package.json "$PLUGIN_JSON" README.md CHANGELOG.md
git commit -m "release: v$VERSION"
git tag -a "v$VERSION" -m "v$VERSION"
ok "已提交并创建 tag v$VERSION"

# ── 7. Push ──────────────────────────────────────────
info "推送到 origin..."
git push origin main --follow-tags
ok "已推送 main + tag v$VERSION"

echo ""
printf "${GREEN}=== 发布完成: v$VERSION ===${NC}\n"
echo ""
echo "后续步骤:"
echo "  1. 编辑 CHANGELOG.md 中的 TODO 内容（如果有）"
echo "  2. 在 GitHub 创建 Release: ${REPO_URL}/releases/new?tag=v${VERSION}"
echo "  3. 用户侧执行: claude plugin update ecw@enterprise-change-workflow"
