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

## v4 静态排查修正（2026-07-20，用户反馈底部黑阴影仍在）

2.1.215 上 007/008 均已正确应用（theme 跟随表达式命中 2 处、`"vs-dark"` 残留 0；008 哨兵 `.cc-patch-008d` 在 index.css），但用户反馈浅色下 diff 卡片**底部黑阴影仍在**。静态排查 index.css 定位到真凶：

- **底部 30px 黑阴影 ≠ `.diff-review-shadow`**（v3 误判）。`.diff-review-shadow` 是 Monaco **diff review 浮层**（点 diff 行后弹出的逐行 review 面板）的阴影，不是内嵌卡片底部的固定装饰——所以 v3 覆盖它对内嵌卡片底部无效。
- **底部真凶 = `.truncationGradient_xxx`**：CC 自己的 React 组件，给 `max-height:200px` 的内嵌 diff 卡片做截断淡出。`position:absolute;bottom:0;left:0;right:0;height:30px`，`background:linear-gradient(#0000 0%,#1e1e1e 100%)` **写死深色、不吃任何 CSS 变量**。深色主题下与 Monaco 深底融合不可见；007 切浅底后暴露成卡片底部 30px 黑阴影。全文件仅此一处用 `#1e1e1e` 做 gradient，单一真凶。
- **修法**：浅色下把该渐变终点从 `#1e1e1e` 改成 `#fff`（匹配 Monaco `vs` 主题硬编码白底），保留淡出效果。选择器用属性包含 `[class*=truncationGradient]` 规避混淆后缀 `_s6OFow` 跨版本变化。详见下方「改动 1」v4 append 块。

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

> 另有一类**不吃该变量**的底部黑阴影源（v4 发现）：CC 自身的 `.truncationGradient_xxx`（截断淡出遮罩，`linear-gradient(#0000,#1e1e1e)` 写死深色），是内嵌卡片底部 30px 黑阴影的真凶。它不吃 `--vscode-scrollbar-shadow`，变量重定义兜不到，需单独用属性选择器覆盖（见 v4 append 块）。
>
> 注：清单第 2 条 `.diff-review-shadow` 是 Monaco **review 浮层**的阴影（点 diff 行弹出的逐行面板），**不是内嵌卡片底部**——v3 曾据「底部向上」误判它为卡片底部黑阴影之源，实际不是。

## 与 007 的关系：007 的尾部盲区

007（`007-diff-editor-follows-ui-theme`）把 Monaco 整体主题切到跟随 UI，但管不到这些走 `--vscode-scrollbar-shadow` 变量的滚动阴影。本补丁是 007 的收尾：浅色下把这些阴影一并消除。

## 方案：CSS append，多保险全覆盖

**v4：变量重定义（兜底全部吃变量的滚动阴影）+ 逐选择器 `box-shadow:none`（直接覆盖顶/底/侧滚动阴影）+ `[class*=truncationGradient]` 渐变到白（根治底部截断遮罩写死深色）。** 滚动阴影不再赌具体哪一条——把所有吃 `--vscode-scrollbar-shadow` 的 Monaco 阴影在浅色下一律置 none；底部截断遮罩因不吃变量、单独覆盖。

- 选 append：目标是明文 CSS 属性覆盖，类名是 Monaco 公开稳定类名 + 属性包含选择器，append 天然可移植、升级后只要类名前缀不变无需改动。
- 深色零影响：所有规则前缀 `body.vscode-light`，深色（body 上是 `vscode-dark`）完全不命中。

## 改动 1：浅色下消除 Monaco 滚动阴影（双保险）

### file: webview/index.css
### type: append

```css
/* 008 v4 浅色主题消除 Monaco diff 卡片黑阴影（007 收尾）—— 顶底滚动阴影吃 scrollbar-shadow 变量浅色下置 none；底部截断渐变 truncationGradient 写死 1e1e1e 是 v3 漏网真凶浅色下改渐变到白 */
.cc-patch-008e{}
body.vscode-light{--vscode-scrollbar-shadow:transparent!important}
body.vscode-light .monaco-editor .scroll-decoration,body.vscode-light .monaco-scrollable-element>.shadow.top,body.vscode-light .monaco-scrollable-element>.shadow.left,body.vscode-light .monaco-scrollable-element>.shadow.top.left,body.vscode-light .monaco-component.diff-review .diff-review-shadow{box-shadow:none!important}
body.vscode-light [class*=truncationGradient]{background:linear-gradient(#0000 0%,#fff 100%)!important}
```

#### 设计说明

- **变量重定义 `transparent`**：一次性把所有吃 `--vscode-scrollbar-shadow` 的 Monaco 阴影置透明（含未来 Monaco 新增的同源阴影），最广覆盖。
- **逐选择器 `box-shadow:none`**：直接在 9 条候选元素上置 none，特异性（`body.vscode-light …` 均高于 Monaco 原规则）+ `!important`，不依赖变量继承层级——这是已被探针证明生效的路径，作主保障。
- **底部截断渐变 `truncationGradient` 覆盖（v4 新增，根治「卡片底部黑阴影」）**：v3 只管吃 `--vscode-scrollbar-shadow` 的滚动阴影，漏了 CC 卡片自己的截断淡出遮罩 `.truncationGradient_xxx`——它 `position:absolute;bottom:0;left:0;right:0;height:30px`，`linear-gradient(#0000 0%,#1e1e1e 100%)` **写死深色、不吃任何 CSS 变量**，是浅色下「卡片底部 30px 黑阴影」的真凶（`.diffEditorContainer` 有 `max-height:200px`，内容超长被截断时这条遮罩盖在底部做淡出）。浅色下用属性选择器 `[class*=truncationGradient]`（含子串匹配，规避混淆后缀 `_s6OFow` 跨版本变化）把渐变终点改成 `#fff`。为何写死 `#fff` 而不读 CSS 变量：007 切的是 Monaco `vs` 主题，其 editor 背景由 Monaco 内部硬编码（接近纯白）、**不随 VSCode Color Theme 变**，故 `#fff` 精确匹配；读 `--vscode-editor-background` 反而可能因用户浅色主题带微色调而与 Monaco 实底产生色差。保留淡出效果（不到 `background:none`），维持 CC 原本的截断视觉。
- 为何用 `none`（而非 v2 的 `rgba(0,0,0,0.06)` 调淡）：用户要的是黑横条**消失**，`none` 最彻底、不依赖「0.06 在浅色下是否仍可见」的肉眼判断。

**哨兵为何从 `.cc-patch-008` → `008b` → `008c` → `008d` → `008e`**：引擎对 `type:append` 取 append 文本里第一个 `.类名` 当幂等 marker，marker 已在文件就跳过。每次修订 append 内容都必须换一个当前扩展文件里尚不存在的新哨兵，引擎才会重新追加。v1/v2/v3 的旧块留在扩展 index.css 里无害（被 v4 在后覆盖），日后可用 rollback 回滚 index.css 后整体重 apply 清理。

哨兵必须出现在 append 文本里所有其它 `.类名` 之前，且注释里不能出现 `.类名`（否则引擎先匹配到注释里的点号）。本补丁 v4 注释只用中文与无点号术语（「Monaco」「scrollbar-shadow」「truncationGradient」「1e1e1e」均无点号前缀），第一个 `.` 是哨兵 `.cc-patch-008e`。

#### verify

- append 后重读 index.css，`.cc-patch-008e` 出现 0 → 1（v4 是最后一段，覆盖前面所有 v1/v2/v3 残留）。
- 变量重定义 + box-shadow 逐选择器 + truncationGradient 渐变到白 三条规则都出现在文件末尾。
- 重读确认 `[class*=truncationGradient]` 规则里含 `linear-gradient(#0000 0%,#fff 100%)`。
- **手动验证（关键）**：彻底退出 VSCode 再开（不是 reload window——reload 可能刷不掉 webview CSS 缓存），浅色主题下让 CC 编辑一个**行数多到 diff 卡片出现截断（内容超过 max-height:200px）**的文件，确认顶部黑横条与底部 30px 黑阴影都消失、底部自然淡出到白；切深色确认这些规则不命中（深色维持原样）。

#### 失败处理

- 若彻底重启后顶部黑横条仍在 → 极不可能（探针已确证 `.scroll-decoration` 命中），查 webview 是否真加载了 index.css。
- 若底部 30px 黑阴影仍在 → v4 已定位真凶为 `.truncationGradient_xxx`（写死 `#1e1e1e` 的截断渐变）；若 v4 应用后仍不消，检查 CC 是否把类名前缀 `truncationGradient` 改了（属性选择器 `[class*=truncationGradient]` 依赖该语义前缀稳定），届时 grep 新 bundle 找截断渐变的新类名、更新选择器。
- 升级后 Monaco 改类名 → 变量重定义仍可能兜住滚动阴影（只要新实现还吃该变量）；逐选择器需按新类名补。`truncationGradient` 走属性包含选择器、天然规避混淆后缀变化，只要语义前缀不变就持续命中。

## 范围边界（不在本补丁内）

- 全屏 diff 预览的整屏遮罩 `#000000d9` 是半透明黑底遮罩，与滚动阴影是两回事，不处理。
- 本补丁只动 Monaco 滚动阴影，不改 Monaco 其它配色（背景、增删行色等由 007 负责）。

## 已验证版本

- `2.1.211`：v1 verified 但未消除黑横条（只覆盖 `.scroll-decoration` 一条、漏同族，且「关键事实」失实）。
- `2.1.211`：v2 verified 但用户反馈仍未消除（变量重定义 + 4 选择器调淡 `rgba(0,0,0,0.06)`；未消除的主因是 reload window 没刷掉 webview CSS 缓存，非补丁写错）。
- `2.1.211`：v3 verified——探针实勘后，变量 `transparent` + 多候选 `box-shadow:none` 双保险、哨兵 `.cc-patch-008d`。顶部黑横条消除；**但底部 30px 黑阴影未消**——v3 误判底部真凶为 `.diff-review-shadow`（实为 Monaco review 浮层的阴影、非内嵌卡片底部），真正底部黑阴影是 CC 的 `.truncationGradient` 写死深色渐变，v3 未覆盖。（2026-07-16）
- `2.1.215`：**v4 待彻底重启确认**——静态排查定位底部真凶 `.truncationGradient_xxx`（`linear-gradient(#0000,#1e1e1e)` 写死、不吃变量），追加 `body.vscode-light [class*=truncationGradient]{background:linear-gradient(#0000 0%,#fff 100%)!important}`，哨兵升至 `.cc-patch-008e`；pending 彻底退出 VSCode 重开后人工确认底部黑阴影消失。007/008 均已在 2.1.215 正确应用（theme 跟随表达式命中 2 处、`"vs-dark"` 残留 0）。（2026-07-20）
