#!/bin/bash
# generate-repo-map.sh — 自动生成代码结构索引（Repo Map）
# Usage: ./generate-repo-map.sh <project_root> <ecw_yml_path>
set -euo pipefail

if [ $# -lt 2 ]; then
  echo "Usage: $0 <project_root> <ecw_yml_path>" >&2
  exit 1
fi

PROJECT_ROOT="$1"; ECW_YML="$2"
[ ! -d "$PROJECT_ROOT" ] && echo "Error: '$PROJECT_ROOT' not a directory" >&2 && exit 1
[ ! -f "$ECW_YML" ] && echo "Error: '$ECW_YML' not found" >&2 && exit 1

# 从 ecw.yml 提取配置
REPOMAP_OUTPUT=".claude/ecw/knowledge-ops/repo-map.md"
GROUP_BY_DIR=$(grep 'repomap_group_by_dir:' "$ECW_YML" | head -1 | sed -E 's/.*:[[:space:]]*([a-z]*).*/\1/' | xargs)
PROJECT_NAME=$(grep '^ *name:' "$ECW_YML" | head -1 | sed -E 's/.*:[[:space:]]*"?([^"]*)"?.*/\1/' | xargs)

[ -z "$GROUP_BY_DIR" ] && GROUP_BY_DIR="true"
[ -z "$PROJECT_NAME" ] && PROJECT_NAME="Project"

OUTPUT="$PROJECT_ROOT/$REPOMAP_OUTPUT"
mkdir -p "$(dirname "$OUTPUT")"

echo "# $PROJECT_NAME Repo Map" > "$OUTPUT"
echo "" >> "$OUTPUT"
echo "> 自动生成，勿手动编辑。运行 \`bash scripts/java/generate-repo-map.sh <project_root> <ecw_yml_path>\` 刷新。" >> "$OUTPUT"
echo "> 生成时间: $(date '+%Y-%m-%d %H:%M')" >> "$OUTPUT"
echo "" >> "$OUTPUT"

# 提取 component_types（多行 YAML 数组解析）
declare -a COMPONENT_NAMES
declare -a COMPONENT_PATTERNS
declare -a COMPONENT_PATHS

in_component_types=false
current_name=""
current_pattern=""
current_path=""

while IFS= read -r line; do
  if [[ "$line" =~ ^component_types: ]]; then
    in_component_types=true
    continue
  fi

  if $in_component_types; then
    # 遇到非缩进行或新的顶级 key，退出 component_types 段
    if [[ "$line" =~ ^[a-z_]+: ]] && [[ ! "$line" =~ ^[[:space:]] ]]; then
      # 保存最后一个组件
      if [ -n "$current_name" ]; then
        COMPONENT_NAMES+=("$current_name")
        COMPONENT_PATTERNS+=("$current_pattern")
        COMPONENT_PATHS+=("$current_path")
      fi
      break
    fi

    # 提取 name（兼容 bash 3，用 sed 代替 BASH_REMATCH）
    if echo "$line" | grep -q '\- *name:'; then
      # 保存上一个组件
      if [ -n "$current_name" ]; then
        COMPONENT_NAMES+=("$current_name")
        COMPONENT_PATTERNS+=("$current_pattern")
        COMPONENT_PATHS+=("$current_path")
      fi
      current_name=$(echo "$line" | sed -E 's/.*name:[[:space:]]*"?([^"]*)"?.*/\1/' | xargs)
      current_pattern=""
      current_path=""
    fi

    # 提取 grep_pattern
    if echo "$line" | grep -q 'grep_pattern:'; then
      current_pattern=$(echo "$line" | sed -E 's/.*grep_pattern:[[:space:]]*"?([^"]*)"?.*/\1/' | xargs)
    fi

    # 提取 search_path
    if echo "$line" | grep -q 'search_path:'; then
      current_path=$(echo "$line" | sed -E 's/.*search_path:[[:space:]]*"?([^"]*)"?.*/\1/' | xargs)
    fi
  fi
done < "$ECW_YML"

# 保存最后一个组件（如果 EOF 前没有遇到新的顶级 key）
if [ -n "$current_name" ]; then
  COMPONENT_NAMES+=("$current_name")
  COMPONENT_PATTERNS+=("$current_pattern")
  COMPONENT_PATHS+=("$current_path")
fi

if [ ${#COMPONENT_NAMES[@]} -eq 0 ]; then
  echo "Warning: no component_types found in ecw.yml" >&2
  echo "无组件类型定义" >> "$OUTPUT"
  exit 0
fi

echo "检测到 ${#COMPONENT_NAMES[@]} 个组件类型" >&2

total_classes=0

# 为每个组件类型生成章节
for i in "${!COMPONENT_NAMES[@]}"; do
  name="${COMPONENT_NAMES[$i]}"
  pattern="${COMPONENT_PATTERNS[$i]}"
  path="${COMPONENT_PATHS[$i]}"

  echo "## $name" >> "$OUTPUT"
  echo "" >> "$OUTPUT"

  search_dir="$PROJECT_ROOT/$path"
  if [ ! -d "$search_dir" ]; then
    echo "> 目录不存在: $path" >> "$OUTPUT"
    echo "" >> "$OUTPUT"
    continue
  fi

  # 根据 pattern 推断文件名模式（简化：假设 Java 项目，类名 = 文件名）
  # pattern 格式: "class {name}" → 匹配 *{name}.java
  file_pattern="*${name}.java"

  # 查找匹配文件
  files=$(find "$search_dir" -name "$file_pattern" -not -path '*/test/*' -not -path '*/target/*' 2>/dev/null | sort)

  if [ -z "$files" ]; then
    echo "> 未找到匹配文件" >> "$OUTPUT"
    echo "" >> "$OUTPUT"
    continue
  fi

  # 按是否分组输出
  if [ "$GROUP_BY_DIR" = "true" ]; then
    # 按父目录分组（兼容 bash 3.x，不使用 declare -A）
    group_tmp=$(mktemp -d)
    while IFS= read -r file; do
      parent_dir=$(dirname "$file")
      relative_parent="${parent_dir#$search_dir/}"
      [ "$relative_parent" = "$parent_dir" ] && relative_parent="."
      # 用文件系统模拟关联数组：目录名做 key，文件路径追加写入
      safe_key=$(echo "$relative_parent" | tr '/' '_')
      [ "$safe_key" = "." ] && safe_key="_root"
      echo "$file" >> "$group_tmp/$safe_key"
      # 记录原始目录名
      echo "$relative_parent" > "$group_tmp/${safe_key}.dir"
    done <<< "$files"

    for key_file in $(ls "$group_tmp"/*.dir 2>/dev/null | sort); do
      dir=$(cat "$key_file")
      safe_key=$(basename "$key_file" .dir)
      if [ "$dir" != "." ]; then
        echo "### $dir" >> "$OUTPUT"
      fi
      while IFS= read -r file; do
        [ -z "$file" ] && continue
        classname=$(basename "$file" .java)

        # 提取方法签名（仅 Java，提取 public 方法）
        methods=$(grep -E '^\s+public\s+(static\s+)?[A-Za-z<>]+\s+[a-zA-Z_][a-zA-Z0-9_]*\s*\(' "$file" 2>/dev/null | \
                  sed 's/(.*//' | awk '{print $NF}' | tr '\n' ',' | sed 's/,$//' | sed 's/,/, /g')

        if [ -n "$methods" ]; then
          echo "- **$classname**: $methods" >> "$OUTPUT"
        else
          echo "- **$classname**" >> "$OUTPUT"
        fi
        total_classes=$((total_classes + 1))
      done < "$group_tmp/$safe_key"
      echo "" >> "$OUTPUT"
    done
    rm -rf "$group_tmp"
  else
    # 平铺输出
    while IFS= read -r file; do
      classname=$(basename "$file" .java)

      # 提取方法签名
      methods=$(grep -E '^\s+public\s+(static\s+)?[A-Za-z<>]+\s+[a-zA-Z_][a-zA-Z0-9_]*\s*\(' "$file" 2>/dev/null | \
                sed 's/(.*//' | awk '{print $NF}' | tr '\n' ',' | sed 's/,$//' | sed 's/,/, /g')

      if [ -n "$methods" ]; then
        echo "- **$classname**: $methods" >> "$OUTPUT"
      else
        echo "- **$classname**" >> "$OUTPUT"
      fi
      total_classes=$((total_classes + 1))
    done <<< "$files"
    echo "" >> "$OUTPUT"
  fi
done

echo "---" >> "$OUTPUT"
echo "总计: $total_classes 个类" >> "$OUTPUT"

echo "Repo Map 已生成: $OUTPUT" >&2
echo "总计: $total_classes 个类" >&2
