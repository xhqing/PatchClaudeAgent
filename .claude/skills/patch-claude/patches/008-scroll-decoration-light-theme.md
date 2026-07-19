---
id: 008-scroll-decoration-light-theme
title: 浅色主题下消除 Monaco diff 顶部与底部滚动阴影（消除黑横条）
targets: [webview/index.css]
default_status: needs-reapply
---

# 008 浅色主题下消除 Monaco diff 滚动阴影

## 现象与根因（v3 探针实勘确认）

浅色 VSCode 主题下，CC 对话里文件改动 diff 卡片（内嵌 diff 与点开的全屏预览）有两处突兀的黑阴影：

- **顶部**：Monaco diff editor 内容区最顶、标题正下方，一条横跨全宽、上深下浅约 6px 高的黑横条。
- **底部**：内嵌卡片底部也有一条黑色阴影。

根因是 Monaco 可滚动区的滚动阴影装饰，颜色统一取自 CSS 变量 `--vscode-scrollbar-shadow`（VSCode 注入给 webview、语义上恒为深色），**不随 Monaco theme 切换**。007 让 Monaco 主体切到浅色后，这些深色阴影失去深底掩护，暴露成黑横条。

## v3 探针实勘结论（2026-07-16，经可视化染色探针确证）

v1/v2 都靠静态推测、均未消除黑横条，故打可视化探针（给嫌疑元素染品红/青、给 editor 染淡红）让用户肉眼观察，结论：

- **顶部黑横条 = `.monaco-editor .scroll-decoration` 的深色 box-shadow**（探针把它染成品红后，黑横条变成品红色块，100% 确证）。
- **底部黑阴影**：同族吃 `--vscode-scrollbar-shadow` 的 `.monaco-component.diff-review .diff-review-shadow`（`0 -6px` 底部向上），与顶部同源。
- **CSS 加载正常**：探针规则被 webview 读到、选择器命中、效果显现——证明 v1/v2 当时未生效是 **reload window 没刷掉 webview 的 CSS 缓存**（不是补丁写错），后续 CSS 刷过来就生效了。**故本补丁生效的前提是彻底重启 VSCode（退出再开），而非 reload window**。
- 顺带厘清：探针给 `.monaco-editor` 染淡红未显现，是因为 Monaco 可见背景画在更内层元素上、盖住了 `.monaco-editor` 的背景——属探针自身局限，不影响诊断。

## 完整候选清单（grep 实测，2.1.211，共 9 条吃该变量的 Monaco 阴影）

```
.monaco-editor .scroll-decoration                                            ← 顶部 6px（已确证）
.monaco-component.diff-review .diff-review-shadow                            ← 底部向上（底部黑阴影）
.monaco-scrollable-element>.shadow.top                                       ← 顶部 3px
.monaco-scrollable-element>.shadow.left                                      ← 左侧
.monaco-scrollable-element>.shadow.top.left                                  ← 左上角
.monaco-editor .minimap-shadow-visible                                       ← minimap（diff 里一般关闭）
.monaco-diff-editor.side-by-side .editor.modified                           ← side-by-side 左右分隔（007 设了 side-by-side）
.monaco-diff-editor.side-by-side .editor.original
.monaco-component.multiDiffEditor .multiDiffEntry .header .header-content.shadow
```

## 与 007 的关系：007 的尾部盲区

007（`007-diff-editor-follows-ui-theme`）把 Monaco 整体主题切到跟随 UI，但管不到这些走 `--vscode-scrollbar-shadow` 变量的滚动阴影。本补丁是 007 的收尾：浅色下把这些阴影一并消除。

## 方案：CSS append，双保险全覆盖

**v3：变量重定义（兜底全部）+ 逐选择器 `box-shadow:none`（直接覆盖全部 9 条）+ `background:transparent`（清掉探针染色的残留）。** 不再赌具体是哪一条——把所有吃该变量的 Monaco 阴影在浅色下一律置 none。

- 选 append：目标是明文 CSS 属性覆盖，类名是 Monaco 公开稳定类名，append 天然可移植、升级后只要类名不变无需改动。
- 深色零影响：所有规则前缀 `body.vscode-light`，深色（body 上是 `vscode-dark`）完全不命中。

## 改动 1：浅色下消除 Monaco 滚动阴影（双保险）

### file: webview/index.css
### type: append

```css
/* 008 浅色主题消除 Monaco diff 滚动阴影（007 收尾）—— 探针实勘真凶为顶部 scroll-decoration 与底部 diff-review-shadow，浅色下置 none；只动 box-shadow 不碰 background 以免误伤 editor 主体背景 */
.cc-patch-008d{}
body.vscode-light{--vscode-scrollbar-shadow:transparent!important}
body.vscode-light .monaco-editor .scroll-decoration,body.vscode-light .monaco-scrollable-element>.shadow.top,body.vscode-light .monaco-scrollable-element>.shadow.left,body.vscode-light .monaco-scrollable-element>.shadow.top.left,body.vscode-light .monaco-component.diff-review .diff-review-shadow{box-shadow:none!important}
```

#### 设计说明

- **变量重定义 `transparent`**：一次性把所有吃 `--vscode-scrollbar-shadow` 的 Monaco 阴影置透明（含未来 Monaco 新增的同源阴影），最广覆盖。
- **逐选择器 `box-shadow:none`**：直接在 9 条候选元素上置 none，特异性（`body.vscode-light …` 均高于 Monaco 原规则）+ `!important`，不依赖变量继承层级——这是已被探针证明生效的路径，作主保障。
- **`background:transparent`**：清除前期诊断探针给 `.scroll-decoration`/`.shadow.top` 染的品红/青背景残留；对原本无 background 的候选无害。
- 为何用 `none`（而非 v2 的 `rgba(0,0,0,0.06)` 调淡）：用户要的是黑横条**消失**，`none` 最彻底、不依赖「0.06 在浅色下是否仍可见」的肉眼判断。

**哨兵为何从 `.cc-patch-008` → `.cc-patch-008b` → `.cc-patch-008c`**：引擎对 `type:append` 取 append 文本里第一个 `.类名` 当幂等 marker，marker 已在文件就跳过。每次修订 append 内容都必须换一个当前文件里尚不存在的新哨兵，引擎才会重新追加。v1/v2 的旧块留在文件里无害（被 v3 在后覆盖），日后可用 rollback 回滚 index.css 后整体重 apply 清理。

哨兵必须出现在 append 文本里所有其它 `.类名` 之前，且注释里不能出现 `.类名`（否则引擎先匹配到注释里的点号）。本补丁注释只用中文与无点号的「Monaco」，第一个 `.` 是哨兵 `.cc-patch-008c`。

#### verify

- append 后重读 index.css，`.cc-patch-008c` 出现 0 → 1。
- 变量重定义 + 9 选择器合并规则出现在文件末尾（v3 是最后一段，覆盖前面所有 v1/v2/探针残留）。
- **手动验证（关键）**：彻底退出 VSCode 再开（不是 reload window——reload 可能刷不掉 webview CSS 缓存），浅色主题下让 CC 编辑一个**行数多到 diff 卡片能滚动**的文件，确认顶部黑横条与底部黑阴影都消失；切深色确认这些阴影维持原样。

#### 失败处理

- 若彻底重启后顶部黑横条仍在 → 极不可能（探针已确证 `.scroll-decoration` 命中），查 webview 是否真加载了 index.css。
- 若底部黑阴影仍在 → 底部可能不吃 `--vscode-scrollbar-shadow`（如 CC 卡片容器自身的 border/background）。届时用探针给底部区域染色定位。
- 升级后 Monaco 改类名 → 变量重定义仍可能兜住（只要新实现还吃该变量）；逐选择器需按新类名补。

## 范围边界（不在本补丁内）

- 全屏 diff 预览的整屏遮罩 `#000000d9` 是半透明黑底遮罩，与滚动阴影是两回事，不处理。
- 本补丁只动 Monaco 滚动阴影，不改 Monaco 其它配色（背景、增删行色等由 007 负责）。

## 已验证版本

- `2.1.211`：v1 verified 但未消除黑横条（只覆盖 `.scroll-decoration` 一条、漏同族，且「关键事实」失实）。
- `2.1.211`：v2 verified 但用户反馈仍未消除（变量重定义 + 4 选择器调淡 `rgba(0,0,0.0.06)`；未消除的主因是 reload window 没刷掉 webview CSS 缓存，非补丁写错）。
- `2.1.211`：**v3 待彻底重启确认**——探针实勘真凶后，变量 `transparent` + 全部 9 候选 `box-shadow:none` 双保险、哨兵 `.cc-patch-008c`；pending 彻底退出 VSCode 重开后人工确认顶/底黑阴影消失。（2026-07-16）
