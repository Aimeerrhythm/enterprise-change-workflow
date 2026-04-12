#!/bin/bash
# scan-shared-resources.sh — Find Java classes referenced by 2+ domains
# Usage: ./scan-shared-resources.sh <project_root> <path_mappings_file>
set -euo pipefail

if [ $# -lt 2 ]; then
  echo "Usage: $0 <project_root> <path_mappings_file>" >&2
  exit 1
fi

PROJECT_ROOT="$1"; PATH_MAPPINGS="$2"
[ ! -d "$PROJECT_ROOT" ] && echo "Error: '$PROJECT_ROOT' not a directory" >&2 && exit 1
[ ! -f "$PATH_MAPPINGS" ] && echo "Error: '$PATH_MAPPINGS' not found" >&2 && exit 1

# Parse path-mappings
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

# Scan @Resource/@Inject injections, emit "class|domain|field" tuples
echo "Scanning injections..." >&2
find "$PROJECT_ROOT" -name '*.java' -not -path '*/test/*' -not -path '*/target/*' -print0 | \
while IFS= read -r -d '' file; do
  file_domain=$(resolve_domain "$file")
  [ "$file_domain" = "unknown" ] && continue
  grep -n '@Resource\|@Inject' "$file" 2>/dev/null | while IFS=: read -r lineno _; do
    for offset in 0 1 2 3; do
      candidate=$(sed -n "$((lineno + offset))p" "$file")
      if echo "$candidate" | grep -qE '^\s*(private|protected|public)?\s*\w+\s+\w+\s*;'; then
        stripped=$(echo "$candidate" | sed -E 's/^\s*(private|protected|public)?\s+//')
        callee=$(echo "$stripped" | awk '{print $1}')
        field=$(echo "$stripped" | awk '{print $2}' | tr -d ';')
        case "$callee" in String|int|Integer|long|Long|boolean|Boolean|List|Map|Set|Optional) continue ;; esac
        echo "$callee|$file_domain|$field"; break
      fi
    done
  done
done | sort -u > /tmp/ecw_shared_refs.tmp

# Aggregate by class, count distinct domains
echo "Aggregating..." >&2
declare -A RES_DOMAINS RES_FIELDS
while IFS='|' read -r classname domain field; do
  existing="${RES_DOMAINS[$classname]:-}"
  if [ -z "$existing" ]; then
    RES_DOMAINS["$classname"]="$domain"
  elif ! echo "$existing" | grep -qw "$domain"; then
    RES_DOMAINS["$classname"]="$existing, $domain"
  fi
  ef="${RES_FIELDS[$classname]:-}"
  if [ -z "$ef" ]; then
    RES_FIELDS["$classname"]="$field"
  elif ! echo "$ef" | grep -qw "$field"; then
    RES_FIELDS["$classname"]="$ef, $field"
  fi
done < /tmp/ecw_shared_refs.tmp

infer_type() {
  case "$1" in
    *Facade) echo "Facade";; *Service) echo "Service";; *Manager) echo "Manager";;
    *Mapper) echo "Mapper";; *Utils|*Util|*Helper) echo "Utils";; *) echo "Other";;
  esac
}

echo "| Resource Name | Type | Consumer Domains | Consumer Count | Key Methods |"
echo "|---------------|------|------------------|----------------|-------------|"
for classname in "${!RES_DOMAINS[@]}"; do
  domains="${RES_DOMAINS[$classname]}"
  count=$(echo "$domains" | tr ',' '\n' | sed 's/^ *//' | sort -u | wc -l | tr -d ' ')
  if [ "$count" -ge 2 ]; then
    fields="${RES_FIELDS[$classname]}"
    short=$(echo "$fields" | tr ',' '\n' | head -3 | tr '\n' ',' | sed 's/,$//')
    fc=$(echo "$fields" | tr ',' '\n' | wc -l | tr -d ' ')
    [ "$fc" -gt 3 ] && short="$short, ..."
    echo "| $classname | $(infer_type "$classname") | $domains | $count | $short |"
  fi
done | sort -t'|' -k5 -rn

rm -f /tmp/ecw_shared_refs.tmp
echo "Done." >&2
