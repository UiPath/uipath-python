#!/bin/bash
# Automatically create .claude/cpr.sh on session start
# This allows commands to access plugin files regardless of installation location

set -e

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"
CPR_SCRIPT="$PROJECT_DIR/.claude/cpr.sh"

# If cpr.sh already exists, we're done
if [ -f "$CPR_SCRIPT" ]; then
    exit 0
fi

# Create .claude directory if it doesn't exist
mkdir -p "$PROJECT_DIR/.claude"

# Create the plugin root resolver script
cat > "$CPR_SCRIPT" << 'EOF'
#!/bin/bash
# Claude Plugin Root resolver - finds plugin directory even when installed to cache

# Try CLAUDE_PLUGIN_ROOT first
if [ -n "$CLAUDE_PLUGIN_ROOT" ]; then
    echo "$CLAUDE_PLUGIN_ROOT"
    exit 0
fi

# Fallback: query installed plugins (handle both "uipath" and "uipath@marketplace")
if [ -f ~/.claude/plugins/installed_plugins.json ]; then
    PLUGIN_PATH=$(jq -r '.plugins | to_entries[] | select(.key == "uipath" or (.key | test("^uipath@"))) | .value[0].installPath' ~/.claude/plugins/installed_plugins.json 2>/dev/null | head -1)
    if [ -n "$PLUGIN_PATH" ]; then
        echo "$PLUGIN_PATH"
        exit 0
    fi
fi

# Last resort: use current directory if we have uipath plugin structure
if [ -f "./.claude-plugin/plugin.json" ]; then
    if jq -e '.name == "uipath" or (.name | test("^uipath@"))' ./.claude-plugin/plugin.json >/dev/null 2>&1; then
        echo "."
        exit 0
    fi
fi

# Fallback to workspace
echo "${CLAUDE_PROJECT_DIR:-.}"
EOF

chmod +x "$CPR_SCRIPT"
