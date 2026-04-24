# Terminal Adapter Reference

Automate opening terminal split panes for child sessions. Detect terminal type and use the appropriate method.

## Detection Logic

```
1. Check $TERM_PROGRAM environment variable:
   - "ghostty" → use Ghostty adapter
   - "iTerm.app" → use iTerm2 adapter
   - Other values → fallback to manual adapter

2. Check if tmux is running:
   - $TMUX is set → use tmux adapter

3. Check workspace.yml terminal.adapter override:
   - If explicitly set → use that adapter

4. Fallback: manual adapter (just print commands)
```

## Ghostty Adapter (macOS, verified ✅)

**Strategy**: Write a launcher script during `create`, open new tab via `Cmd+T`, paste only the short script path. Long commands fail due to input method interference — use script file instead.

**Step 1 — Write launcher script** (during `create` Step 8):

```bash
cat > {workspace}/.claude/ecw/start.sh << 'EOF'
#!/bin/bash
cd "{workspace_path}"
claude "/ecw:workspace run '{requirement}'"
EOF
chmod +x {workspace}/.claude/ecw/start.sh
```

**Step 2 — Open new tab and run**:

```applescript
tell application "Ghostty" to activate
delay 1.0
tell application "System Events"
    tell process "ghostty"
        set frontmost to true
        delay 0.5
        keystroke "t" using {command down}
        delay 1.5
        set the clipboard to "bash {workspace}/.claude/ecw/start.sh"
        delay 0.3
        keystroke "v" using {command down}
        delay 0.3
        keystroke return
    end tell
end tell
```

**Critical notes**:
- Must `activate` Ghostty first — focus must be on Ghostty before `keystroke`
- Use `Cmd+T` keystroke, NOT `click menu item "New Tab"` (menu click opens new window)
- Use clipboard paste, NOT `keystroke` for text — input methods corrupt direct keystroke
- Paste only the short script path, NOT the full claude command

## iTerm2 Adapter (macOS)

```applescript
tell application "iTerm2"
    tell current session of current tab of current window
        set newSession to (split horizontally with default profile)
        tell newSession
            write text "{command}"
        end tell
    end tell
end tell
```

## tmux Adapter (cross-platform)

```bash
tmux split-window -h "cd {service_path} && claude '...' --name {service}-worker --permission-mode acceptEdits"
```

## Manual Adapter (fallback)

Print commands for user to run in new terminal windows (language follows output_language):

```
1. cd {workspace}/{service} && claude "Read .claude/ecw/workspace-task.md and execute." --name {service}-worker --permission-mode acceptEdits
```
