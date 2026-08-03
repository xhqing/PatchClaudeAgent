# Changelog

本项目（PatchClaudeAgent / Tinker）维护针对本机 VSCode Claude Code 扩展（`anthropic.claude-code`）的自定义补丁。本文件记录补丁 Skill 与引擎的历次变更，每条写明「为什么改」与「改了什么」，便于日后排查回归。

## 2026-08-03

### 变更

- **引擎适配新版扩展目录命名（修自动定位回归）**：自 VSCode Claude Code 扩展 2.1.220 起，扩展目录名去掉了 `-darwin-arm64` 平台后缀（新版为 `anthropic.claude-code-2.1.220`，旧版为 `...-2.1.217-darwin-arm64`）。引擎 `apply-patches.py` 的 `find_ext_dir` 原硬编码 `endswith("-darwin-arm64")`，导致不传参自动定位时找不到新版目录直接 `die`，只能靠显式传 EXT_DIR 绕过。改为只按 `anthropic.claude-code-` 前缀匹配，新老两种命名都能命中，再按 `package.json` 读到的真实版本号排序取最新。
- **SKILL.md 步骤 1 通配命令同步**：原命令 `ls -d .../anthropic.claude-code-*-darwin-arm64` 对无后缀的新版匹配失败，改为 `anthropic.claude-code-*`，并补说明（2.1.220 起去后缀、改用 universal 命名）。
- **SKILL.md 步骤 2 脚本路径改为项目内相对路径**：原示例写全局路径 `~/.claude/skills/patch-claude/scripts/apply-patches.py`，但本机并未把该 skill 装到全局（它随项目活在 `.claude/skills/patch-claude/`），照全局路径跑会找不到文件。改为 `.claude/skills/patch-claude/scripts/apply-patches.py`，并注明在项目根执行，消除文档与现状的不一致。
- **补丁移植性表格版本号更新**：002 / 007 / 008 / 010 / 011 五条补丁的「已验证」版本号统一更新到 2.1.220（原分别标 2.1.195 / 2.1.211 / 2.1.215 / 2.1.214 / 2.1.215）。

### 补丁验证

- 扩展升级 2.1.217 → 2.1.220 后，8 个生效补丁全部重新应用成功、零 broken（无需人工重定位锚点）：002 历史会话运行标记、003 usage 图标隐藏、004 鉴权失败不弹登录、005 上下文窗口读 env、007 diff 跟随明暗主题、008 浅色消除 diff 黑阴影、010 图片链接可打开、011 LaTeX 数学渲染。归档补丁 001（思考默认展开）、009（会话刷新按钮）仍停用，不参与应用。原版备份在 `~/.claude/patch-backups/2.1.220/`。

### 新增

- **CHANGELOG.md**：本文件起记。此前变更未单独记录，自本次开始按「为什么改 + 改了什么」沉淀。
