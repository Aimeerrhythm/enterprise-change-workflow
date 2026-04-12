#!/bin/bash
# scan-mq-topology.sh — Map RocketMQ topic publisher/consumer relationships
# Usage: ./scan-mq-topology.sh <project_root>
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 <project_root>" >&2
  exit 1
fi

PROJECT_ROOT="$1"
[ ! -d "$PROJECT_ROOT" ] && echo "Error: '$PROJECT_ROOT' not a directory" >&2 && exit 1

TMPDIR_MQ=$(mktemp -d)
trap 'rm -rf "$TMPDIR_MQ"' EXIT

# Infer domain from file path (module name before /src/, or package path)
infer_domain() {
  local rel="${1#$PROJECT_ROOT/}"
  local module=$(echo "$rel" | sed -E 's|/src/.*||' | sed -E 's|.*/||')
  if [ -n "$module" ] && [ "$module" != "$rel" ]; then echo "$module"; return; fi
  echo "${rel##*/java/}" | sed 's|/[^/]*\.java$||' | tr '/' '.' || echo "unknown"
}

# Step 1: Find consumers (@RocketMQMessageListener)
echo "Scanning MQ consumers..." >&2
find "$PROJECT_ROOT" -name '*.java' -not -path '*/test/*' -not -path '*/target/*' -print0 | \
while IFS= read -r -d '' file; do
  grep -q '@RocketMQMessageListener' "$file" 2>/dev/null || continue
  classname=$(basename "$file" .java)
  # Extract topic = "LITERAL" or topic = CONSTANT
  topic=$(grep -A 10 '@RocketMQMessageListener' "$file" | \
    grep -oE 'topic\s*=\s*"[^"]*"' | head -1 | sed -E 's/topic\s*=\s*"([^"]*)"/\1/')
  if [ -z "$topic" ]; then
    topic=$(grep -A 10 '@RocketMQMessageListener' "$file" | \
      grep -oE 'topic\s*=\s*[A-Za-z_][A-Za-z0-9_.]*' | head -1 | sed -E 's/topic\s*=\s*//')
  fi
  [ -z "$topic" ] && topic="<unknown>"
  action=$(echo "$classname" | sed -E 's/Listener$//;s/Consumer$//;s/([A-Z])/ \1/g' | \
    sed 's/^ //' | tr '[:upper:]' '[:lower:]')
  echo "$topic|$classname|$file|$action"
done > "$TMPDIR_MQ/consumers.txt"
echo "Found $(wc -l < "$TMPDIR_MQ/consumers.txt" | tr -d ' ') consumers" >&2

# Step 2: Find publishers (send/asyncSend/sendMessage calls)
echo "Scanning MQ publishers..." >&2
find "$PROJECT_ROOT" -name '*.java' -not -path '*/test/*' -not -path '*/target/*' -print0 | \
while IFS= read -r -d '' file; do
  grep -qE '\.(send|asyncSend|sendMessage|syncSend|sendOneWay)\s*\(' "$file" 2>/dev/null || continue
  classname=$(basename "$file" .java)
  grep -nE '\.(send|asyncSend|sendMessage|syncSend|sendOneWay)\s*\(' "$file" 2>/dev/null | \
  while IFS=: read -r lineno _line; do
    topic=""
    for offset in 0 -1 -2 -3; do
      check=$((lineno + offset)); [ "$check" -lt 1 ] && continue
      found=$(sed -n "${check}p" "$file" | grep -oE '"[A-Z][A-Z0-9_]+"' | head -1 | tr -d '"')
      if [ -n "$found" ]; then topic="$found"; break; fi
    done
    [ -z "$topic" ] && topic="<unknown>"
    echo "$topic|$classname|$file"
  done
done | sort -u > "$TMPDIR_MQ/publishers.txt"
echo "Found $(wc -l < "$TMPDIR_MQ/publishers.txt" | tr -d ' ') publisher refs" >&2

# Step 3: Output Markdown table
echo "| Topic | Publisher Domain | Publisher Class | Consumer Domain | Consumer Listener | Business Action |"
echo "|-------|-----------------|----------------|-----------------|-------------------|-----------------|"

# Match consumers to publishers
while IFS='|' read -r topic consumer_class consumer_file action; do
  consumer_domain=$(infer_domain "$consumer_file")
  pub_found=false
  while IFS='|' read -r pub_topic pub_class pub_file; do
    if [ "$pub_topic" = "$topic" ]; then
      echo "| $topic | $(infer_domain "$pub_file") | $pub_class | $consumer_domain | $consumer_class | $action |"
      pub_found=true
    fi
  done < "$TMPDIR_MQ/publishers.txt"
  [ "$pub_found" = false ] && echo "| $topic | <unknown> | <unknown> | $consumer_domain | $consumer_class | $action |"
done < "$TMPDIR_MQ/consumers.txt"

# Publishers with no matching consumer
while IFS='|' read -r pub_topic pub_class pub_file; do
  grep -q "^${pub_topic}|" "$TMPDIR_MQ/consumers.txt" 2>/dev/null || \
    echo "| $pub_topic | $(infer_domain "$pub_file") | $pub_class | <no consumer> | <no consumer> | - |"
done < "$TMPDIR_MQ/publishers.txt"
echo "Done." >&2
