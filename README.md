<div align="center">
  <img src="assets/logo.svg" alt="PatchClaudeAgent" width="640">
</div>

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE.md)
[![Built with Claude Code](https://img.shields.io/badge/Built%20with-Claude%20Code-19C37D.svg)](https://claude.com/claude-code)
[![Type](https://img.shields.io/badge/Type-AI%20Agent-FF1493.svg)](#)

</div>

# PatchClaudeAgent

> 🧑‍🔧 **Tinker** — the maintenance tinker who keeps your patches alive. Every time the VSCode Claude Code extension upgrades, Tinker re-locates the anchors and re-applies your custom patches through a self-healing engine.
> 🧠 **Brain**: GLM-5.2 (powered by z.ai)

[简体中文](README_cn.md)

PatchClaudeAgent is a self-maintaining patch skill for the locally installed `anthropic.claude-code` VSCode extension. Every time the extension upgrades, the patches are reapplied automatically through a locator-based engine, restoring your custom UI/interaction tweaks without hand-editing minified bundles.

> The repository contains only original patch logic — never Anthropic's proprietary source files.

## Features

Current patches (each is a self-describing, self-verifying `.md` in `patches/`):

| # | Patch | Effect |
|---|-------|--------|
| 001 | Default-expand thinking | Thinking blocks start expanded instead of collapsed |
| 002 | Session-history running badge | Show a running indicator on busy sessions in history |
| 003 | Usage icon never visible | Hide the usage pie-chart icon in proxy mode |
| 004 | Suppress login on auth fail | Don't pop the login page when the token is exhausted |
| 005 | Context window from env | Read `CONTEXT_WINDOW` from `.env` instead of the built-in model table |
| 007 | Diff editor follows UI theme | Monaco diff cards follow the VSCode light/dark theme (no more dark diffs in light theme) |
| 008 | Light-theme diff shadow fix | Remove Monaco's dark scroll decorations (top black bar) and the card's dark truncation gradient (bottom shadow) in light theme |
| 009 | Session reload button | Add a per-panel reload button that refreshes only the current webview |
| 010 | Open image links | Markdown image links open in VSCode's built-in image viewer |
| 011 | LaTeX math rendering | Render inline `$...$` and block `$$...$$` math via KaTeX in the conversation panel (library and fonts via jsdelivr CDN; requires network) |

> Note: 006 (precise usage display) has been archived, so numbering jumps from 005 to 007.

## How it works

```
patch-claude/
├── SKILL.md                 # Agent workflow + compliance boundary
├── patches/                 # One self-describing .md per patch
└── scripts/
    ├── apply-patches.py     # Core engine: locate -> apply -> verify -> write-back
    └── rollback.py          # Roll back one or all patches from local backup
```

Each patch declares a `type:locate` locator (Python, sandboxed) that computes the real `old`/`new` strings from **stable anchors** at runtime, so patches adapt across versions and devices as long as the anchor structure holds. The engine never trusts its own output: a patch is applied only when `hit_count == 1` and the `new` string actually appears after replacement — otherwise it rolls back from a local backup and marks the patch `broken`.

## Usage

```bash
# 1. Locate the installed extension
EXT_DIR=$(ls -d ~/.vscode/extensions/anthropic.claude-code-*-darwin-arm64)

# 2. Apply / verify all patches
python3 .claude/skills/patch-claude/scripts/apply-patches.py "$EXT_DIR"

# 3. Roll back if needed
python3 .claude/skills/patch-claude/scripts/rollback.py
```

When a patch reports `broken` after an upgrade, the agent re-locates the anchor in the new bundle and rewrites the patch's locator — that self-healing loop is the point of this skill.

## Compliance boundary

- Contains **only original** patch definitions and engine code.
- **Never** includes Anthropic's original bundled files (`rollback/`, `~/.claude/patch-backups/`) or machine-local state (`version-map.json`) — these stay on-device and are excluded from the repository.

## License & Attribution

Copyright (c) 2026 All Contributors. Licensed under the [MIT License](LICENSE.md).

**Attribution:** If you derive from or redistribute this project, please retain the copyright notice and license file, and credit the source: [PatchClaudeAgent](https://github.com/xhqing/PatchClaudeAgent).
