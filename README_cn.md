<div align="center">
  <img src="assets/logo.svg" alt="PatchClaudeAgent" width="640">
</div>

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE.md)
[![Built with Claude Code](https://img.shields.io/badge/Built%20with-Claude%20Code-19C37D.svg)](https://claude.com/claude-code)
[![Type](https://img.shields.io/badge/Type-AI%20Agent-FF1493.svg)](#)

</div>

# PatchClaudeAgent

> 🧑‍🔧 **Tinker**（修补匠）—— 让你的补丁长存的维护匠人。每次 VSCode Claude Code 扩展升级后，Tinker 重新定位锚点，通过自愈引擎重新打上你定制的补丁。
> 🧠 **大脑**：GLM-5.2（由 z.ai 提供）

[English](README.md)

PatchClaudeAgent 是一个针对本机安装的 `anthropic.claude-code` VSCode 扩展的自维护补丁 Skill。每次扩展升级后，通过基于定位器的引擎自动重新应用补丁，恢复你定制的界面/交互行为，无需手动改混淆后的 bundle。

> 仓库只含原创补丁逻辑，绝不含 Anthropic 专有源文件。

## 功能

当前补丁（每个是 `patches/` 下一个自描述、自验证的 `.md`）：

| 编号 | 补丁 | 效果 |
|------|------|------|
| 001 | 思考默认展开 | 思考块默认展开而非折叠 |
| 002 | 历史会话运行标记 | 历史中忙碌会话显示运行标记 |
| 003 | 用量图标永不显示 | proxy 模式下隐藏用量饼图图标 |
| 004 | token 用尽不弹登录 | token 用尽时不弹出登录页 |
| 005 | 从 env 读 context window | 从 `.env` 读 `CONTEXT_WINDOW`，替代内置模型表 |
| 007 | diff 主题跟随明暗 | Monaco diff 卡片跟随 VSCode 明暗主题（浅色下不再显示深底 diff）|
| 008 | 浅色 diff 阴影修复 | 消除浅色下 Monaco 的深色滚动阴影（顶部黑横条）与卡片截断渐变（底部黑阴影） |
| 009 | 会话刷新按钮 | 加一个只重载当前面板的刷新按钮 |
| 010 | 打开图片链接 | markdown 图片链接用 VSCode 内置图片查看器打开 |
| 011 | LaTeX 数学渲染 | 对话面板用 KaTeX 渲染行内 `$...$` 与块级 `$$...$$` 公式（库与字体走 jsdelivr CDN，需联网） |

> 注：006（用量精确显示）已归档，故编号自 005 跳至 007。

## 工作原理

```
patch-claude/
├── SKILL.md                 # 智能体工作流 + 合规边界
├── patches/                 # 每个补丁一个自描述 .md
└── scripts/
    ├── apply-patches.py     # 核心引擎：定位 → 应用 → 校验 → 回写状态
    └── rollback.py          # 用本机备份回滚单条或全部补丁
```

每个补丁声明一段 `type:locate` 定位器（Python，受限沙箱执行），在运行时用**稳定锚点**算出当前版本真实的 `old`/`new`，因此跨版本、跨设备自适应——只要锚点结构未变。引擎不信任自身输出：只有 `hit_count == 1` 且替换后 `new` 确实出现才应用，否则从本机备份回滚并标记为 `broken`。

## 用法

```bash
# 1. 定位已安装的扩展
EXT_DIR=$(ls -d ~/.vscode/extensions/anthropic.claude-code-*-darwin-arm64)

# 2. 应用 / 校验全部补丁
python3 .claude/skills/patch-claude/scripts/apply-patches.py "$EXT_DIR"

# 3. 需要时回滚
python3 .claude/skills/patch-claude/scripts/rollback.py
```

升级后若某补丁报 `broken`，智能体在新版本 bundle 里重新定位锚点并把新锚点写回补丁——这套自愈闭环正是本 Skill 的意义。

## 合规边界

- 只含**原创**补丁定义与引擎代码。
- **绝不**含 Anthropic 原始 bundle 文件（`rollback/`、`~/.claude/patch-backups/`）或本机状态（`version-map.json`）——这些留在本机，不进入仓库。

## 版权与署名

Copyright (c) 2026 All Contributors。采用 [MIT 许可证](LICENSE.md) 授权。

**署名方式：** 若你基于本项目派生或再分发，请保留版权声明与许可证文件，并注明来源：[PatchClaudeAgent](https://github.com/xhqing/PatchClaudeAgent)。
