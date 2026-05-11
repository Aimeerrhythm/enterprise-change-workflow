#!/bin/bash
# ECW hook runner — dynamically resolves the ECW plugin path at runtime.
# Written to .claude/ecw/hook-runner.sh during ecw-init / ecw-upgrade.
#
# Usage: bash hook-runner.sh <hook-script-name>
# Example: bash hook-runner.sh session-start.py

ECW_CACHE="${HOME}/.claude/plugins/cache/enterprise-change-workflow/ecw"

if [ ! -d "$ECW_CACHE" ]; then
  exit 0
fi

LATEST=$(ls "$ECW_CACHE" | grep -E '^[0-9]' | sort -V | tail -1)

if [ -z "$LATEST" ]; then
  exit 0
fi

HOOK_SCRIPT="$ECW_CACHE/$LATEST/hooks/$1"

if [ ! -f "$HOOK_SCRIPT" ]; then
  exit 0
fi

exec python3 "$HOOK_SCRIPT"
