---
id: 007-diff-editor-follows-ui-theme
title: 文件 diff 卡片的 Monaco 主题跟随 VSCode 明暗（浅色主题下变浅底）
targets: [webview/index.js]
default_status: needs-reapply
---

# 007 文件 diff 卡片的 Monaco 主题跟随 VSCode 明暗

## 现象与根因

CC 对话里展示文件改动时会渲染 Monaco diff editor：一种是卡片里的内嵌 diff（`.diffEditorContainer_s6OFow`，max-height:200px），另一种是点开后的全屏 diff 预览。两种在**浅色 VSCode 主题**（如 Claude Light Theme、Default Light Modern）下背景仍是深色（`#1E1E1E` 系），与浅色界面格格不入。

根因不在 CSS 变量，也不在 `colorCustomizations`——而在 webview/index.js 里**创建 Monaco diff editor 时把 theme 写死成了 `"vs-dark"`**。Monaco 一旦用 `vs-dark`，editor 背景、语法高亮、diff 的增删行配色全部走深色那套，且 CSS 变量 `--vscode-editor-background` 也是 Monaco 运行时按 `vs-dark` 注入的 `#1e1e1e`。所以无论 VSCode 是浅色还是深色主题，diff 卡片恒为深底。

webview/index.js 里一共两处 `createDiffEditor` 调用，options 里都带 `theme:"vs-dark"`：

- 卡片 diff：`renderOverviewRuler:!1`（不开概览标尺），容器 `o.current`
- 全屏 diff 预览：`renderOverviewRuler:!0` 且 `wordWrap:"on"`，容器 `i.current`

## 关键事实（已查证，2.1.211）

- webview 的 `<body>` 上**实际存在** VSCode 注入的 `vscode-light` / `vscode-dark` / `vscode-high-contrast` class——CC 自己的代码就在用 `document.body.classList.contains("vscode-light")` 判断主题明暗（index.js 里可搜到）。所以运行时能可靠区分浅 / 深色。
- 用户原始建议里的 CSS 作用域 `[data-vscode-theme-kind="light"]` 在 CC 的 webview 里**并不存在**（index.css、index.js 均无该属性）——那条 CSS 方案走不通。
- webview 侧没有 `onDidChangeActiveColorTheme` / `ColorThemeKind`，也没有 host postMessage 传主题进来。因此「跟随 VSCode 主题明暗」最干净的做法是在创建 Monaco editor 的那一刻，按 body class 选 `vs`（浅）/ `vs-dark`（深）。

## 方案选择：改 theme 初值（type:locate），不走 CSS append

选择改 JS 初值、而不是在 index.css 末尾追加 CSS 覆盖，原因：

1. **真根治**：把写死的 `theme:"vs-dark"` 换成按 body class 动态选 `vs` / `vs-dark`，Monaco 会整体切换到对应主题——背景、语法配色、diff 增删行（绿 / 红）、滚动条、行号边栏全部自动正确，无需逐项写 CSS 兜底。CSS 覆盖法只能改背景色，diff 绿红仍是深色版配色叠在浅底上，不干净。
2. **深色主题零影响**：动态表达式在深色下取 `"vs-dark"`，与改之前完全一致，不会改坏深色主题（满足「别把深色也改坏」）。
3. **锚点稳定**：`createDiffEditor`、`theme`、`renderOverviewRuler`、`scrollBeyondLastLine`、`minimap`、`automaticLayout` 都是 Monaco 公开 option 名，跨版本稳定；`theme:"vs-dark"` 是字面量。比依赖 CC 混淆类名（如 `_s6OFow`）的 CSS 方案移植性更好。
4. **有语法兜底**：应用后跑 `node --check` 验证 JS 合法；引擎本身也会校验替换后 `new` 串出现，失败即从本机备份回滚。

`document.body.classList.contains("vscode-light")` 在创建 Monaco 的 `useEffect` 里求值，此时 body class 已由 VSCode 注入就绪（CC 自己也这么用），可正确读到。代价：运行中切换 VSCode 主题需 reload window 才让 diff editor 重新按新主题创建——可接受，用户主要诉求是「用浅色主题时 diff 就是浅底」。

两处都是 diff editor，都要改。两处 `theme:"vs-dark"` 的最小公共串 `automaticLayout:!0,theme:"vs-dark"` 在文件里命中 2 次，不能用单串 replace；因此拆成两个改动块，各自用 `renderOverviewRuler:!1` / `:!0` 前缀消歧，确保每块 hit_count==1。

## 改动 1：卡片 diff（renderOverviewRuler:!1）

### file: webview/index.js
### type: locate
### idempotent: `renderOverviewRuler:!1,scrollBeyondLastLine:!1,minimap:{enabled:!1},automaticLayout:!0,theme:document`

### locator:

```python
def locate(src):
    # 前置：diff editor 创建逻辑还在，且 Monaco 仍用这组 option 名
    if "createDiffEditor" not in src:
        return {"found": False, "reason": "createDiffEditor 锚点消失，Monaco diff 创建逻辑可能重构"}
    if 'theme:"vs-dark"' not in src:
        return {"found": False, "reason": "theme:\"vs-dark\" 字面量消失，CC 可能已改为跟随主题或换 theme 名"}
    # 卡片 diff 那一处：renderOverviewRuler:!1（不开概览标尺）到 theme 的确定片段
    pat = re.compile(
        r'(renderOverviewRuler:!1,scrollBeyondLastLine:!1,'
        r'minimap:\{enabled:!1\},automaticLayout:!0,)theme:"vs-dark"'
    )
    m = pat.search(src)
    if not m:
        return {"found": False, "reason": "未匹配到卡片 diff（renderOverviewRuler:!1）的 theme:\"vs-dark\" 片段"}
    prefix = m.group(1)
    old = prefix + 'theme:"vs-dark"'
    new = prefix + 'theme:document.body.classList.contains("vscode-light")?"vs":"vs-dark"'
    return {"found": True, "old": old, "new": new, "hit_count": src.count(old)}
```

#### 设计说明

定位器锚定 Monaco diff editor 的 option 序列这个**语义结构**：`renderOverviewRuler:!1,scrollBeyondLastLine:!1,minimap:{enabled:!1},automaticLayout:!0,theme:"vs-dark"`。其中 `renderOverviewRuler:!1` 把范围锁定到卡片 diff（全屏预览是 `:!0`），保证全文件唯一命中。前置检查 `createDiffEditor` 与 `theme:"vs-dark"` 任一消失即安全拒绝（found=False → broken），避免上游重构后误改。`new` 只把结尾 `theme:"vs-dark"` 换成等价的动态三元，前缀一字不动。

## 改动 2：全屏 diff 预览（renderOverviewRuler:!0）

### file: webview/index.js
### type: locate
### idempotent: `renderOverviewRuler:!0,scrollBeyondLastLine:!1,minimap:{enabled:!1},automaticLayout:!0,theme:document`

### locator:

```python
def locate(src):
    if "createDiffEditor" not in src:
        return {"found": False, "reason": "createDiffEditor 锚点消失，Monaco diff 创建逻辑可能重构"}
    if 'theme:"vs-dark"' not in src:
        return {"found": False, "reason": "theme:\"vs-dark\" 字面量消失，CC 可能已改为跟随主题或换 theme 名"}
    # 全屏预览那一处：renderOverviewRuler:!0（开概览标尺）到 theme 的确定片段
    pat = re.compile(
        r'(renderOverviewRuler:!0,scrollBeyondLastLine:!1,'
        r'minimap:\{enabled:!1\},automaticLayout:!0,)theme:"vs-dark"'
    )
    m = pat.search(src)
    if not m:
        return {"found": False, "reason": "未匹配到全屏 diff（renderOverviewRuler:!0）的 theme:\"vs-dark\" 片段"}
    prefix = m.group(1)
    old = prefix + 'theme:"vs-dark"'
    new = prefix + 'theme:document.body.classList.contains("vscode-light")?"vs":"vs-dark"'
    return {"found": True, "old": old, "new": new, "hit_count": src.count(old)}
```

#### 设计说明

与改动 1 同构，仅前缀用 `renderOverviewRuler:!0` 锁定全屏预览那一处。

**两块必须用各自不同的 idempotent 标记**（各自含 `renderOverviewRuler:!1` / `:!0` 前缀，到 `theme:document` 为止），**不能共享同一个标记**。原因：引擎在跑定位器之前会先查 `### idempotent:` 标记——若两块共享同一标记，块 1 应用后该标记就进了文件，块 2 一查便误判「已应用」直接跳过，结果只改了块 1。本补丁首跑时就踩了这个坑（文件长度只 +54 而非 +108，`theme:"vs-dark"` 还剩 1 处，全屏 diff 没改），改用各自带 `renderOverviewRuler:!?` 前缀的专属标记后，块 2 的标记只在自己那处改动后才出现，两块互不干扰、独立应用。

#### verify（两块共用）

- 定位器返回 `found=True` 且 `hit_count==1`（各自前缀在全文件唯一）
- 替换后 `new` 串（含 `document.body.classList.contains("vscode-light")?"vs":"vs-dark"`）出现在文件
- `node --check webview/index.js` 通过（JS 语法合法）
- 手动验证：reload window，浅色主题下让 CC 编辑文件，diff 卡片与全屏 diff 背景变浅、文字与增删行（绿 / 红）可读；再切深色主题确认 diff 仍为深底、未被改坏

#### 失败处理

- `createDiffEditor` 锚点消失 → broken：Monaco diff 创建逻辑被上游重构，需在新版 bundle 里重新定位 `createDiffEditor` 调用点，更新定位器的 option 序列正则。
- `theme:"vs-dark"` 字面量消失 → broken：CC 可能已自行让 theme 跟随主题（届时本补丁可作废），或改用了别的 theme 名 / 写法——先 grep `theme:` 看新写法，确认后更新定位器或标记本补丁已无需应用。
- 正则未匹配（但 `theme:"vs-dark"` 还在）→ broken：option 序列结构变了（如插入了新 option、或 `!1`/`!0` 写法变成 `false`/`true`）。按 `createDiffEditor` 上下文重新截取卡片 / 全屏两处到 `theme:` 的真实片段，更新正则。
- `hit_count≠1` → broken：某前缀在全文件出现多次（option 序列被复用到别处）。在定位器里加更靠前的上下文消歧（如卡片处的 `lightbulb`、全屏处的 `wordWrap:"on"`）。

## 范围边界（不在本补丁内）

- `.previewOverlay_vRjSkQ{background:#000000d9;...;z-index:10000}` 是全屏预览的**遮罩层**（半透明黑底），与 Monaco editor 背景是两回事。本补丁只让 Monaco editor 区变浅，不处理这层遮罩。若用户希望全屏预览的整屏遮罩也跟随主题变浅，需另写补丁单独覆盖该规则（浅色下把 `#000000d9` 换成浅色半透明）。

## 已验证版本

- `2.1.211`：verified（2026-07-16，两块改动均应用、`node --check` 通过；应用后 `theme:"vs-dark"` 归零、动态跟随表达式出现 2 处，文件 +108 字符）
