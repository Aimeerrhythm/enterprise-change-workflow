#!/bin/bash
# check-freshness.sh — 检测知识库文档中引用的 Java 类名是否在代码中存在，检测 last-verified 超期
# Usage: ./check-freshness.sh <project_root> <ecw_yml_path>
set -uo pipefail

if [ $# -lt 2 ]; then
  echo "Usage: $0 <project_root> <ecw_yml_path>" >&2
  exit 1
fi

PROJECT_ROOT="$1"; ECW_YML="$2"
[ ! -d "$PROJECT_ROOT" ] && echo "Error: '$PROJECT_ROOT' not a directory" >&2 && exit 1
[ ! -f "$ECW_YML" ] && echo "Error: '$ECW_YML' not found" >&2 && exit 1

# 从 ecw.yml 提取配置
KNOWLEDGE_ROOT=$(grep 'knowledge_root:' "$ECW_YML" | head -1 | sed -E 's/.*:[[:space:]]*"?([^"]*)"?.*/\1/' | xargs)
STALE_DAYS=$(grep 'stale_days:' "$ECW_YML" | head -1 | sed -E 's/.*:[[:space:]]*([0-9]*).*/\1/' | xargs)
[ -z "$KNOWLEDGE_ROOT" ] && KNOWLEDGE_ROOT=".claude/knowledge/"
[ -z "$STALE_DAYS" ] && STALE_DAYS=90

STALE_REFS_PATH=".claude/ecw/state/stale-refs.md"

KNOWLEDGE_DIR="$PROJECT_ROOT/$KNOWLEDGE_ROOT"
[ ! -d "$KNOWLEDGE_DIR" ] && echo "Warning: knowledge directory '$KNOWLEDGE_DIR' not found" >&2 && exit 0

# 提取 component_types 的 search_path（多行 YAML 数组解析）
CODE_DIRS=""
in_component_types=false
while IFS= read -r line; do
  if [[ "$line" =~ ^component_types: ]]; then
    in_component_types=true
    continue
  fi
  if $in_component_types; then
    # 遇到非缩进行或新的顶级 key，退出 component_types 段
    if [[ "$line" =~ ^[a-z_]+: ]] && [[ ! "$line" =~ ^[[:space:]] ]]; then
      break
    fi
    # 提取 search_path 值（兼容 bash 3，用 sed 代替 BASH_REMATCH）
    if echo "$line" | grep -q 'search_path:'; then
      path=$(echo "$line" | sed -E 's/.*search_path:[[:space:]]*"?([^"]*)"?.*/\1/' | xargs)
      if [ -n "$path" ]; then
        CODE_DIRS="$CODE_DIRS $PROJECT_ROOT/$path"
      fi
    fi
  fi
done < "$ECW_YML"

# 如果没有提取到 search_path，回退到扫描常见 Java 目录
if [ -z "$CODE_DIRS" ]; then
  CODE_DIRS=$(find "$PROJECT_ROOT" -type d -name 'src' -not -path '*/target/*' -not -path '*/node_modules/*' 2>/dev/null | head -10 | tr '\n' ' ')
fi

stale_ref_count=0
stale_date_count=0
file_count=0
pass_count=0

echo "=== 知识库新鲜度检测报告 ===" >&2
echo "检测时间: $(date '+%Y-%m-%d %H:%M')" >&2
echo "过期阈值: ${STALE_DAYS} 天" >&2
echo "知识库目录: $KNOWLEDGE_DIR" >&2
echo "代码目录: $CODE_DIRS" >&2
echo "" >&2

# 预建代码中所有 Java 类名索引（一次性扫描）
java_classes_file=$(mktemp)
for code_dir in $CODE_DIRS; do
  if [ -d "$code_dir" ]; then
    find "$code_dir" -name "*.java" -not -path '*/test/*' -not -path '*/target/*' -exec basename {} .java \; 2>/dev/null
  fi
done | sort -u > "$java_classes_file"

echo "已索引 $(wc -l < "$java_classes_file" | xargs) 个 Java 类" >&2
echo "" >&2

# 输出 markdown 表头（stdout，供 ecw-init 捕获）
echo "| 文档 | 问题类型 | 详情 |"
echo "|------|---------|------|"

for mdfile in $(find "$KNOWLEDGE_DIR" -name "*.md" | sort); do
  relpath="${mdfile#$PROJECT_ROOT/}"
  file_count=$((file_count + 1))
  file_has_issue=false

  # 1. 提取完整类名（必须以大写开头，至少两个大写字母的驼峰，以特定后缀结尾）
  class_names=$(grep -oE '\b[A-Z][a-zA-Z]{2,}(BizServiceImpl|BizService|ManagerImpl|Manager|FacadeImpl|Facade|ExtMapper|Mapper|Helper|StrategyImpl|Strategy|Component|ServiceImpl|Controller|Repository|Handler)\b' "$mdfile" 2>/dev/null | sort -u)

  for class in $class_names; do
    # 跳过明显是泛称而非具体类名的（长度过短）
    char_count=${#class}
    if [ "$char_count" -lt 15 ]; then
      continue
    fi

    if ! grep -qx "$class" "$java_classes_file"; then
      echo "| $relpath | 过时引用 | 类 \`$class\` 未找到 |"
      file_has_issue=true
      stale_ref_count=$((stale_ref_count + 1))
    fi
  done

  # 2. 检查 last-verified 日期
  verified_date=$(grep -oE 'last-verified:[[:space:]]*[0-9]{4}-[0-9]{2}-[0-9]{2}' "$mdfile" 2>/dev/null | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' | head -1)
  if [ -n "$verified_date" ]; then
    if date --version >/dev/null 2>&1; then
      # GNU date
      verified_ts=$(date -d "$verified_date" +%s 2>/dev/null || echo "")
    else
      # BSD date (macOS)
      verified_ts=$(date -j -f "%Y-%m-%d" "$verified_date" "+%s" 2>/dev/null || echo "")
    fi

    if [ -n "$verified_ts" ]; then
      now_ts=$(date "+%s")
      days_ago=$(( (now_ts - verified_ts) / 86400 ))
      if [ "$days_ago" -gt "$STALE_DAYS" ]; then
        echo "| $relpath | 待验证 | last-verified: ${verified_date} (${days_ago} 天前) |"
        file_has_issue=true
        stale_date_count=$((stale_date_count + 1))
      fi
    fi
  fi

  if [ "$file_has_issue" = false ]; then
    pass_count=$((pass_count + 1))
  fi
done

rm -f "$java_classes_file"

echo "" >&2
echo "=== 检测汇总 ===" >&2
echo "  总文件数: $file_count" >&2
echo "  ⚠ 疑似过时引用: $stale_ref_count 条" >&2
echo "  ⏰ 待验证文档: $stale_date_count 个" >&2
echo "  ✅ 通过: $pass_count 个" >&2
