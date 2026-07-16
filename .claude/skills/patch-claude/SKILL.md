---
name: patch-claude
description: 维护并重新应用针对本机 VSCode Claude Code 扩展的自定义补丁。当扩展升级后思考块等定制项失效、或用户要求"重新打补丁/检查补丁状态/更新补丁 Skill"时触发。包含前置检查、锚点重定位、失败回写 Skill 的自愈闭环。
---

# patch-claude —— 自维护补丁 Skill（自用）

本 Skill 用于维护针对 **本机** 安装的 `anthropic.claude-code` VSCode 扩展的自定义补丁。每次扩展升级（版本号变化）后，重新应用这些补丁，恢复用户定制的界面/交互行为。


## 目录结构

```
patch-claude/              ← 仓库只含原创逻辑，可多设备同步
├── SKILL.md                    ← 本文件（智能体工作流 + 合规边界）
├── .gitignore                  ← 排除 Anthropic 原始文件与本机产物
├── patches/                    ← 补丁清单，每个补丁一个 .md，自描述自验证
│   ├── 001-default-expand-thinking.md
│   └── 002-session-history-running-badge.md
└── scripts/
    ├── apply-patches.py        ← 核心引擎：定位→应用→校验→回写状态
    └── rollback.py             ← 用本机备份回滚单条或全部补丁
```

**不入库（.gitignore 排除）**：

- `rollback/` —— 从扩展拷出的 Anthropic 原始文件（专有，仅本机自用，绝不进 git）。
- `~/.claude/patch-backups/` —— 引擎首次打补丁前当场从本机扩展拷出的原始文件备份（本机生成，各设备各自有，与 `rollback/` 互为回滚源）。
- `version-map.json` —— 引擎回写的本机版本/补丁状态（各设备版本不同，本机生成）。

引擎运行时定位机制：补丁 `.md` 不再存死字节串 `old/new`，而是声明一段 `type:locate` 定位器（Python，受限沙箱执行）。引擎在本机运行时用**稳定锚点**算出当前版本真实的 `old/new` 再替换，因此跨版本/跨设备自适应——只要锚点结构未变。`type:append`（纯追加自创类，天然可移植）与 `type:replace`（仅限确有稳定 old 串时兼容）保持不变。

## 工作流

收到"检查/重打补丁"请求时，**不要手动改文件**，而是调用引擎脚本，让它产出结构化报告。

### 步骤 1：定位当前扩展副本

扩展目录名含版本号，升级后会变。用通配定位：

```bash
EXT_DIR=$(ls -d ~/.vscode/extensions/anthropic.claude-code-*-darwin-arm64)
```

若存在多个版本目录，取版本号最大的那个；若用户刚升级完旧的还在，提示用户旧目录可清理。

读 `package.json` 的 `version` 字段，与 `version-map.json` 比对：
- 版本相同且全部 `verified` → 报告"补丁已是最新，无需操作"。
- 版本变化或有 `needs-reapply`/`broken` → 进入步骤 2。

### 步骤 2：运行引擎，逐补丁应用

```bash
python3 ~/.claude/skills/patch-claude/scripts/apply-patches.py "$EXT_DIR"
```

引擎对每个补丁文件依次执行：
1. **定位**：`type:locate` 块跑定位器（受限沙箱），用稳定锚点算出当前版本真实 `old/new`；`type:replace`/`append` 按补丁声明的内容处理。定位器返回 `found=False` 或异常 → 标记 `broken`，绝不硬改。
2. **幂等**：已应用则直接 `verified`（定位器算出的 `new` 已在文件、或声明的 `idempotent_marker` 命中），不重复改文件。
3. **应用**：`hit_count==1` 才做替换；命中数 ≠ 1 → `broken`。
4. **校验**：替换后再读一次确认 `new` 出现；失败则从本机备份回滚文件。
5. **备份**：首次对某文件打补丁前，从**本机扩展当前文件**拷一份原始备份到 `~/.claude/patch-backups/<version>/`（已有则跳过，不入库）。
6. **回写状态**：应用结果写回 `version-map.json`（`verified` / `needs-reapply` / `broken` + 失败原因）。

### 步骤 3：解读报告，处理 broken 项

引擎输出每个补丁的状态。对 `broken` 项（锚点在新版本里也对不上）：
- **不要硬改。** 这是设计意图——上游重构导致定位失效。
- 进入"更新 Skill"模式：在新版本 bundle 里用 `grep` 关键词（见下方"锚点重定位工具箱"）重新定位目标，**把新锚点写回对应的补丁 .md**，状态改回 `verified`（或标记仍待人工确认）。
- 若定位后仍无法确认（变化太大），保持 `broken`，向用户报告需要人工介入。

## 锚点重定位工具箱（broken 补丁修复用）

补丁的可靠性取决于锚点的稳定性。优先用以下稳定度递减的锚点：

| 稳定度 | 锚点类型 | 示例 |
|--------|---------|------|
| 高 | schema/settings 里的配置项名 | `alwaysThinkingEnabled`、`showThinkingSummaries` |
| 高 | 明文 CSS 文件里的类名 | `webview/index.css` 中的 `.thinkingToggleOpen_aHyQPQ` |
| 中 | 可读的 React/event 字符串 | `areThinkingBlocksExpanded`、`thinkingToggle` |
| 中 | DOM 属性 / HTML 结构 | `<details ... open=` |
| 低 | 混淆变量名 | `J`、`ie`、`Z8t`、`ne`（易变，仅作上下文辅助） |

定位 useState 初值这类场景的通用手法：
```bash
# 找关键词命中位置，再看它附近 useState/ne( 的初值
grep -ob "areThinkingBlocksExpanded" "$EXT_DIR/webview/index.js"
# 然后偏移读上下文确认 ne(!1) → ne(!0) 的置换点
```

## 编写新补丁

用户提出新定制项时，新增 `patches/NNN-描述.md`，frontmatter 写 `id`/`title`/`targets`/`default_status: needs-reapply`。改动块优先用 **`type:locate`**（跨版本自适应）：

```markdown
## 改动 1：<标题>
### file: webview/index.js
### type: locate
### idempotent_marker: <稳定特征串，如 ccRunDot>

### locator:
```python
def locate(src):
    # 1. 稳定前置检查（锚点消失即返回 found=False，安全拒绝）
    # 2. 用稳定锚点定位目标，动态提取本版本混淆符号名（正则组捕获）
    # 3. 拼出本版本真实 old / new
    return {"found": True, "old": old, "new": new, "hit_count": 1}
```

#### verify
- 定位器 found=True 且 hit_count==1；替换后 new 在文件
- `node --check` 通过

#### 失败处理
- 锚点消失 / 正则未匹配 / hit_count≠1 → broken，提示人工重定位锚点
```

要点：
- **`type:locate`**：定位器在受限沙箱跑（只暴露 `re` 等内置），返回 `{found, old, new, hit_count, reason}`。引擎不信任输出：仍要求 `hit_count==1` 且替换后 `new` 实际出现，否则回滚。`idempotent_marker` 用稳定串判幂等。
- **`type:append`**：纯追加自创类/样式，天然可移植，marker 用首个 `@keyframes` 名或类名判幂等。
- **`type:replace`**：仅当确有稳定 old 串（不依赖混淆名）时用，否则优先 locate。
- 锚点稳定度见下方表格；定位器用正则捕获组动态提取混淆符号名，**不写死任何混淆名**。
- **多改动块的 idempotent 标记必须各自不同**：补丁含 ≥2 个改动块时，每块的 `### idempotent:` 要用各自唯一的稳定串（如各自改动点独有的前缀），**不能共享同一个标记**。引擎在跑定位器之前会先查 `### idempotent:`——共享标记会导致块 1 应用后、块 2 一查就误判「已应用」直接跳过，只改了块 1。007 曾因此只改了卡片 diff、漏掉全屏 diff（文件长度只 +54 而非 +108），改用各自含 `renderOverviewRuler:!1`/`:!0` 前缀的标记后修复。（引擎实际识别的字段名是 `### idempotent:`，不是 `idempotent_marker:`。）

## 不可改的范围（向用户坦诚说明）

- `resources/native-binary/` 下的 CLI 原生二进制——核心逻辑在此，Skill 无法可靠补丁。
- `extension.js` 中无清晰锚点的深层业务逻辑——强改风险高，一般拒绝定制此类。

## 已验证补丁与跨版本移植性（诚实说明）

补丁的可移植性依锚点稳定度而异，升级后某补丁 `broken` 是正常预期：

| 补丁 | 机制 | 移植性 | 说明 |
|------|------|--------|------|
| 001 思考默认展开 | `type:locate`（定位器） | **较好** | 用 `Ctrl+O` 翻转指纹 `key=="o")…setter(x=>!x)` + useState `[state,setter]=HOOK(!1)` 初值做稳定锚点，正则动态捕获混淆符号名，跨版本自适应。幂等自洽（已应用态返回 `old=new`）。已验证 `2.1.198`。 |
| 002 历史会话运行标记 | `type:locate`（定位器） | **较好** | 用 `ariaLabel:"Session history"` + `.sessionName` 字段名 + `busy.value`/`pendingInput.value` 做稳定锚点，正则动态提取混淆符号名，跨版本自适应。CSS 块纯 append 天然可移植。已验证 `2.1.195`。 |
| 007 diff 主题跟随明暗 | `type:locate`（两块） | **较好** | 用 `createDiffEditor` 的 option 序列（`renderOverviewRuler`/`scrollBeyondLastLine`/`minimap`/`automaticLayout`/`theme`，均为 Monaco 公开 API 名）做稳定锚点，按 `renderOverviewRuler:!1`/`:!0` 分卡片 / 全屏两块，锁定 `theme:"vs-dark"` 字面量。深色零影响（三元 else 仍取 `vs-dark`）。两块用各自不同的 `### idempotent:` 标记（含 `renderOverviewRuler:!?` 前缀）。已验证 `2.1.211`。 |

升级后若 001 报 broken：定位器依赖的 `Ctrl+O` 翻转指纹或 useState `!1`/`!0` 初值结构被上游重构所致。按补丁 .md「人工重定位 fallback」逆向追 `q8t` 透传层调用链人工重定位一次，再按新结构补全定位器正则。这是交互大改时才触发的兜底，常规构建（混淆名/hook 名/透传函数名变化）定位器自动适配，无需人工——这也是 001 从 `type:replace` 死字节串升级为 `locate` 的原因：靠产品级行为锚点而非混淆名，跨版本可靠性显著优于死字节串。002 同为定位器化，两者移植性现已相当。
