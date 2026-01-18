# Marketplace Plugin Structure

## Directory Layout

```
.claude-plugin/
├── marketplace.json                          # Main marketplace definition
├── plugins/
│   └── uipath/                              # Plugin name (kebab-case)
│       ├── .claude-plugin/
│       │   └── plugin.json                  # Plugin metadata
│       ├── commands/                        # Executable commands
│       │   ├── uipath.md                   # /uipath command
│       │   ├── create-agent.md             # /uipath:create-agent command
│       │   ├── run.md                      # /uipath:run command
│       │   ├── create-eval.md              # /uipath:create-eval command
│       │   ├── eval.md                     # /uipath:eval command
│       │   └── list.md                     # /uipath:list command
│       ├── hooks/                          # Optional: context detection
│       │   ├── detect-uipath-context.sh
│       │   ├── get-uipath-context.sh
│       │   └── init-uipath-context.sh
│       ├── templates/                      # Optional: project templates
│       │   ├── pyproject.toml.template
│       │   ├── requirements.txt.template
│       │   ├── setup.sh
│       │   └── setup.ps1
│       └── README.md                       # Plugin description
├── .gitignore                               # Git ignore rules
└── STRUCTURE.md                             # This file
```

## Files Explained

### marketplace.json
Defines the marketplace and its plugins.

```json
{
  "name": "uipath-marketplace",          // Marketplace identifier
  "owner": {                              // Maintainer information
    "name": "UiPath",
    "email": "support@uipath.com"
  },
  "plugins": [                            // List of plugins in marketplace
    {
      "name": "uipath",                  // Plugin identifier
      "source": "./plugins/uipath",      // Where plugin is located
      "description": "Create, run, and evaluate UiPath coded agents",
      "version": "1.0.0",                 // Version number
      "keywords": ["uipath", "automation", "rpa", "agent"]
    }
  ]
}
```

### plugin.json
Plugin metadata that Claude Code reads.

```json
{
  "name": "uipath",                      // Plugin ID (must match source)
  "displayName": "UiPath SDK Assistant",  // User-friendly name
  "description": "Create, run, and evaluate UiPath coded agents",
  "version": "1.0.0",                     // Semantic versioning
  "commands": [                           // Available commands
    {
      "name": "uipath",                   // Command name
      "displayName": "UiPath Menu",       // Display name
      "aliases": [],                      // Alternative names
      "description": "Main menu with all UiPath commands"
    }
  ]
}
```

### Commands (.claude/commands/*.md)

Each `.md` file is a command. Format:

```markdown
---
description: What this command does
allowed-tools: Bash, Read, Write, Glob, AskUserQuestion
argument-hint: [optional-args]
contextAware: true
autoDetect: true
---

# Command Title

Description of what the command does.

The content after the frontmatter is the prompt that Claude uses.
```

### Hooks (Optional)
Scripts that run automatically to detect context or setup.

### Templates (Optional)
Files that are copied/used when creating new projects.

## Plugin Naming

**Important:** Plugin names must match across all files:

- `marketplace.json`: `"source": "./plugins/uipath"`
- `plugin.json`: `"name": "uipath"`
- Directory name: `uipath/`

## Installation Flow

### User's perspective:

1. Add marketplace:
   ```bash
   /plugin marketplace add owner/repo
   ```

2. Install plugin:
   ```bash
   /plugin install uipath@uipath-marketplace
   ```

3. Use command:
   ```bash
   /uipath
   ```

### What happens behind the scenes:

1. Claude Code clones/fetches the marketplace repo
2. Reads `marketplace.json` to find the plugin
3. Copies plugin from `./plugins/uipath/` to cache
4. Reads `plugin.json` to register commands
5. Copies `commands/*.md` files to user's command registry
6. Commands become available globally

## Cloning and Caching

**Important limitation:** Plugins are copied to cache, not symlinked.

```
~/.claude/plugins/cache/
└── uipath-marketplace/
    └── uipath/
        ├── .claude-plugin/
        │   └── plugin.json
        ├── commands/
        ├── hooks/
        └── templates/
```

This means:
- ✅ Plugin works offline after installation
- ✅ Updates happen when user reinstalls
- ❌ Can't reference files outside plugin directory
- ❌ Can't use relative paths to shared code

## Publishing to GitHub

### Repository Structure

```
github.com/uipath/claude-code-extension
├── .claude-plugin/
│   └── marketplace.json
├── plugins/
│   └── uipath/
│       ├── .claude-plugin/
│       │   └── plugin.json
│       ├── commands/
│       ├── hooks/
│       └── templates/
├── MARKETPLACE_SETUP.md
├── README.md
└── LICENSE
```

### Installation from GitHub

Users install with:

```bash
/plugin marketplace add uipath/claude-code-extension
/plugin install uipath-sdk-assistant@uipath-marketplace
```

Claude Code automatically:
1. Resolves `uipath/claude-code-extension` to GitHub URL
2. Clones the repository
3. Reads `marketplace.json`
4. Installs the plugin

## Version Management

Update these files when releasing new versions:

1. `.claude-plugin/marketplace.json`:
   ```json
   {
     "plugins": [
       {
         "version": "1.0.1"
       }
     ]
   }
   ```

2. `.claude-plugin/plugins/uipath/.claude-plugin/plugin.json`:
   ```json
   {
     "version": "1.0.1"
   }
   ```

## Validation

Check your marketplace setup:

```bash
# From project root
/plugin validate ./.claude-plugin

# From marketplace directory
/plugin validate .
```

Valid output:
```
✓ Marketplace is valid
✓ Plugin 'uipath-sdk-assistant' is valid
✓ All commands registered
```

## Common Issues

### Plugin not found
- Ensure `name` matches in both `marketplace.json` and `plugin.json`
- Ensure directory name matches plugin name

### Commands not showing
- Check `plugin.json` has `commands` array
- Verify command names match `.md` filenames
- Validate marketplace structure

### Can't find shared code
- Copy files into each plugin that needs them
- Don't try to reference `../shared/`
- Use symlinks only for development

## Best Practices

1. **Use semantic versioning**: 1.0.0, 1.0.1, 1.1.0, 2.0.0
2. **Keep plugins small**: One focused purpose
3. **Document thoroughly**: README + inline help
4. **Test locally first**: Before publishing
5. **Use meaningful names**: kebab-case, descriptive
6. **Include examples**: Show how to use
7. **Provide support**: Links to docs/issues
8. **Update regularly**: Fix bugs, add features

## For More Information

- [Claude Code Docs](https://code.claude.com/docs/en/plugin-marketplaces)
- [MARKETPLACE_SETUP.md](../../MARKETPLACE_SETUP.md) - Testing and publishing
- [plugin.json](./plugins/uipath-sdk-assistant/.claude-plugin/plugin.json) - Example config
