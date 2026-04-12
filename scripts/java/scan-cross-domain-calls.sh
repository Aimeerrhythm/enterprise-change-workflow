#!/bin/bash
# scan-cross-domain-calls.sh — Scan Java project for cross-domain @Resource/@Inject dependencies
# Usage: ./scan-cross-domain-calls.sh <project_root> <path_mappings_file>
set -euo pipefail

if [ $# -lt 2 ]; then
  echo "Usage: $0 <project_root> <path_mappings_file>" >&2
  exit 1
fi

PROJECT_ROOT="$1"; PATH_MAPPINGS="$2"
[ ! -d "$PROJECT_ROOT" ] && echo "Error: '$PROJECT_ROOT' not a directory" >&2 && exit 1
[ ! -f "$PATH_MAPPINGS" ] && echo "Error: '$PATH_MAPPINGS' not found" >&2 && exit 1

# Parse path-mappings: Markdown table rows "| path | domain | ..."
declare -A DIR_TO_DOMAIN
while IFS='|' read -r _ dir_col domain_col _rest; do
  dir=$(echo "$dir_col" | xargs); domain=$(echo "$domain_col" | xargs)
  [ -z "$dir" ] || [ -z "$domain" ] || [[ "$dir" == -* ]] || [[ "$dir" == "Path"* ]] || [[ "$dir" == "Directory"* ]] && continue
  DIR_TO_DOMAIN["$dir"]="$domain"
done < "$PATH_MAPPINGS"
[ ${#DIR_TO_DOMAIN[@]} -eq 0 ] && echo "Warning: no mappings found" >&2 && exit 0

resolve_domain() {
  local rel_path="${1#$PROJECT_ROOT/}" best_match="" best_len=0
  for dir in "${!DIR_TO_DOMAIN[@]}"; do
    if [[ "$rel_path" == "$dir"* ]] && [ ${#dir} -gt $best_len ]; then
      best_match="$dir"; best_len=${#dir}
    fi
  done
  [ -n "$best_match" ] && echo "${DIR_TO_DOMAIN[$best_match]}" || echo "unknown"
}

# Build class-name -> file-path index
echo "Building class index..." >&2
declare -A CLASS_TO_FILE
while IFS= read -r jfile; do
  CLASS_TO_FILE[$(basename "$jfile" .java)]="$jfile"
done < <(find "$PROJECT_ROOT" -name '*.java' -not -path '*/test/*' -not -path '*/target/*')
echo "Indexed ${#CLASS_TO_FILE[@]} classes" >&2

# Find @Resource/@Inject and detect cross-domain calls
echo "Scanning for cross-domain injections..." >&2
echo "| Caller Domain | Caller Class | Callee Domain | Callee Class | Method | Call Type |"
echo "|---------------|--------------|---------------|--------------|--------|-----------|"

find "$PROJECT_ROOT" -name '*.java' -not -path '*/test/*' -not -path '*/target/*' -print0 | \
while IFS= read -r -d '' file; do
  caller_class=$(basename "$file" .java)
  caller_domain=$(resolve_domain "$file")
  grep -n '@Resource\|@Inject' "$file" 2>/dev/null | while IFS=: read -r lineno _; do
    ann_line=$(sed -n "${lineno}p" "$file")
    echo "$ann_line" | grep -q '@Resource' && call_type="@Resource" || call_type="@Inject"
    decl_line=""
    for offset in 0 1 2 3; do
      candidate=$(sed -n "$((lineno + offset))p" "$file")
      if echo "$candidate" | grep -qE '^\s*(private|protected|public)?\s*\w+\s+\w+\s*;'; then
        decl_line="$candidate"; break
      fi
    done
    [ -z "$decl_line" ] && continue
    stripped=$(echo "$decl_line" | sed -E 's/^\s*(private|protected|public)?\s+//')
    callee_class=$(echo "$stripped" | awk '{print $1}')
    field_name=$(echo "$stripped" | awk '{print $2}' | tr -d ';')
    case "$callee_class" in String|int|Integer|long|Long|boolean|Boolean|List|Map|Set|Optional) continue ;; esac
    callee_file="${CLASS_TO_FILE[$callee_class]:-}"
    [ -z "$callee_file" ] && callee_domain="unknown" || callee_domain=$(resolve_domain "$callee_file")
    if [ "$caller_domain" != "$callee_domain" ] && [ "$callee_domain" != "unknown" ]; then
      echo "| $caller_domain | $caller_class | $callee_domain | $callee_class | $field_name | $call_type |"
    fi
  done
done
echo "Done." >&2
