---
id: 009-session-reload-button
title: 会话面板加「刷新当前会话」按钮（仅重载当前 webview，不动其它面板）
targets: [webview/index.js, webview/index.css]
default_status: needs-reapply
---

# 009 会话面板加「刷新当前会话」按钮

## 需求

每个会话面板（侧边栏 / 编辑器区打开的 Claude Code 聊天面板）顶部工具栏多一个刷新按钮，点击后**只重新加载当前这个 webview**，不影响其它窗口 / 面板。VSCode 自带的 `Developer: Reload Webviews` 会一次性刷掉所有 webview，本补丁要的是「按实例触发、只刷这一个」。

## reload 路径选择：前端 `window.location.reload()`（不改主进程）

经过对 extension.js 的探查（2.1.214），主进程侧所有 webview 的 `onDidReceiveMessage` 回调**不在 extension.js 里做 type 分发**，而是统一转发 `Y?.fromClient(msg)` 给 `go` 通信层处理：

```
e.webview.onDidReceiveMessage((X)=>{this.output.info(`Received message from webview: ${JSON.stringify(X)}`),Y?.fromClient(X)},null,this.disposables)
```

若走「前端 postMessage → 主进程重设 `webview.html`」的原方案，需要改 extension.js 的两个会话面板入口（`resolveWebviewView` 侧边栏、`setupPanel` 编辑器区），且这两处回调文本还与 `resolveSessionListView` 的回调相同需消歧，定位器复杂、首次动 2.6MB 核心文件风险高。

**改用前端 `window.location.reload()`，理由：**

1. **天然只刷当前面板**：webview 本质是一个页面，`location.reload()` 只重载当前这个 webview 的页面，不会触碰其它 webview 实例。这正是「只刷单个会话」的关键——不依赖主进程。
2. **历史自动恢复**：会话历史由主进程 / 后端（CLI）持有，webview 只是展示层。reload 重新加载页面后，前端重新初始化、重新经通信层向后端拉取当前会话的消息，历史自动回来——这是 CC 自带的初始化机制，不需要补丁介入。
3. **`acquireVsCodeApi()` 可再次调用**：该 API 的「每实例一次」限制是针对**同一页面上下文**；reload 后是全新的页面上下文（旧状态清空），重新调用合法。探查确认 `acquireVsCodeApi` 在 index.js 仅出现 1 次（初始化函数 `SLt()` 内），reload 后顺着重走该初始化即可。
4. **`window.location` 已被 CC 自身使用**（index.js 内 `window.location` 出现 2 次），说明该全局在 webview 内可用、可靠。
5. **零改动主进程**：本补丁只动前端 `index.js`（注入按钮）+ `index.css`（点击动画），与现有 001–008 补丁同文件、同 locate/append 机制，自愈移植性有保障。

**CSP 不受影响**：reload 重新加载的是同一份 html（nonce 不变），内容安全策略不变。

**待实测确认（见下方验收）**：reload 时若该会话正有流式回复进行中，流是否中断。两种 reload 路径（前端 location.reload / 主进程重设 html）对流式的影响本质相同（都重建前端），此处选更简的前端方案。

## 改动 1：webview/index.js（在 New session 按钮后注入刷新按钮）

### file: webview/index.js
### type: locate
### idempotent: `ccReloadBtn`

### locator:

```python
def locate(src):
    # 前置：工具栏的 New session 按钮还在（稳定 aria-label 明文）
    if 'ariaLabel:"New session"' not in src:
        return {"found": False, "reason": "工具栏 New session 按钮锚点消失，header 工具栏可能被重构"}
    # 匹配 New session 按钮整体，动态捕获本版本的按钮组件名（不写死 yf/hZe）
    pat = re.compile(
        r'b\((\w+),\{ariaLabel:"New session",iconSize:20,'
        r'onClick:[^}]*\},children:b\((\w+),\{\}\)\}\)'
    )
    m = pat.search(src)
    if not m:
        return {"found": False, "reason": "未匹配到 New session 按钮结构（ariaLabel/iconSize/onClick/children）"}
    btn = m.group(1)
    old = m.group(0)
    # Lucide refresh-cw 描边图标（Lucide 原生 24x24 坐标系；viewBox -1 -1 26 26；stroke-width 1.3）。
    # 同时对齐 CC 工具栏图标的「线宽」与「圆形大小」两项（2.1.217 实测 CC 图标后反推）：
    #
    # 【CC 图标画法】fZe / mZe 是 fill 填充轮廓体系（svg fill:none + path fill:currentColor，
    #   viewBox 0 0 20 20），轮廓宽 = 外圆 R7.5 - 内圆 R6.5 = 1.0 单位 = 1px；圆形外缘半径 7.5px
    #   （fill 轮廓边界即路径，无外扩）。
    # 【线宽对齐】本补丁用 stroke 体系，要 1px 线宽：strokeWidth 渲染值需 = 1。
    # 【圆形大小对齐】关键差异——stroke 中心对齐会外扩半个线宽：Lucide 圆弧半径 9（24 坐标），
    #   若用默认 viewBox 0 0 24 24，外缘半径 = (9 + Sw/2) * 20/24，恒大于 CC 的 7.5px，圆形偏大
    #   （用户实测反馈「圆形明显比左边大」，即此）。注意：两边边界框占比都是 75%，但 stroke 外扩
    #   使 refresh 的视觉圆形比 CC 大半个线宽——「边界框相同」不等于「视觉圆形相同」。
    #
    # 解法：保持 Lucide 原始 path 不动（不手算缩放坐标，避免贝塞尔点算错导致变形），改用放大且
    #   居中的 viewBox 把整体等比缩小，再按比例补偿 strokeWidth：
    #   设 viewBox 边长 V、strokeWidth Sw，要求「线宽 1px + 圆外缘半径 7.5px」：
    #     Sw * 20/V = 1   且   (9 + Sw/2) * 20/V = 7.5   =>   V = 25.71, Sw = 1.286（精确解）。
    #   取最近的整数组合 viewBox -1 -1 26 26 + strokeWidth 1.3：
    #     线宽 = 1.3 * 20/26 = 1.0px（= CC）；圆外缘 = (9 + 0.65) * 20/26 = 7.42px（CC 7.5px，差 0.08px）。
    #   viewBox 以 Lucide 中心 (12,12) 为原点向四周扩到 26（min-x=min-y=-1），内容居中不偏移。
    icon_path = ('M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8 '
                 'M21 3v5h-5 M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16 '
                 'M3 21v-5h5')
    reload_btn = (
        ',b(' + btn + ',{ariaLabel:"Reload this session",iconSize:20,'
        'className:"ccReloadBtn",onClick:()=>window.location.reload(),'
        'children:b("svg",{width:"20",height:"20",viewBox:"-1 -1 26 26",fill:"none",'
        'stroke:"currentColor",strokeWidth:"1.3",strokeLinecap:"round",'
        'strokeLinejoin:"round","aria-hidden":"true",'
        'children:b("path",{d:"' + icon_path + '"})})})'
    )
    new = old + reload_btn
    return {"found": True, "old": old, "new": new, "hit_count": src.count(old)}
```

#### 设计说明

定位器锚定「New session 按钮」这个**语义结构**：`b(<按钮组件>,{ariaLabel:"New session",iconSize:20,onClick:<体>,children:b(<图标组件>,{})})`。其中：

- `ariaLabel:"New session"` 是全文件唯一的明文 aria-label（已确认 count=1），是最稳定的锚点——`New session` 是面向用户的按钮标签，跨版本几乎不会改。
- `iconSize:20` 进一步锁定这是工具栏图标按钮（与 `Learn Claude Code` 的 `iconSize:16` 区分）。
- `(\w+)` 动态捕获按钮组件名（2.1.214 为 `yf`）和图标组件名（`hZe`），**不写死任何混淆名**，跨版本自适应。
- `onClick:[^}]*\}` 宽松吞掉按钮逻辑体（容忍 CC 改写「新建会话」的内部逻辑，只要不引入嵌套花括号）。

注入的刷新按钮作为工具栏 `De` children 数组的**新末尾元素**（在 New session 按钮后加 `,b(...)`），与 Session history / New session 并排。按钮：

- `ariaLabel:"Reload this session"` 提供可访问性 + 唯一标记。
- `onClick:()=>window.location.reload()` —— 核心：只重载当前 webview。
- `children` 为内联 SVG 描边图标（Lucide refresh-cw），`stroke:"currentColor"` 跟随文字色，适配明暗主题。图标同时经 `viewBox:-1 -1 26 26` + `stroke-width:1.3` 对齐 CC 工具栏图标的「线宽 1px」与「圆形外缘半径 7.5px」两项（换算与理由见定位器注释）。注：两边边界框占比同为 75%，但 stroke 中心外扩使 refresh 视觉圆形偏大，故需放大 viewBox 缩小整体——「边界框相同」不等于「视觉圆形相同」。
- `className:"ccReloadBtn"` 作为 CSS 钩子（改动 2 挂点击旋转动画）。

#### verify

- 定位器返回 `found=True` 且 `hit_count==1`（`ariaLabel:"New session"` 全文件唯一保证）
- 替换后 `new` 串（含 `ccReloadBtn`、`window.location.reload()`、`stroke:"currentColor"`）出现在文件
- `node --check webview/index.js` 通过（JS 语法合法）
- 手动验证：reload window，会话面板顶部工具栏出现刷新按钮，点击后**只当前面板白屏重载并恢复历史**，同窗口其它面板不动

#### 失败处理

- `ariaLabel:"New session"` 消失 → broken：header 工具栏被上游重构，需在新版 bundle 里重新定位工具栏按钮组（可按 `ariaLabel:"Session history"` 顺藤找到工具栏）。
- 正则未匹配（但 `ariaLabel:"New session"` 还在）→ broken：New session 按钮的 props 结构变了（如 iconSize 写法变、onClick 体出现嵌套花括号）。按 `ariaLabel:"New session"` 上下文重新截取按钮真实片段，更新正则。
- `hit_count≠1` → broken：`ariaLabel:"New session"` 出现多次（极不可能，CC 只有一个新建会话入口）。在定位器里加更靠前的上下文消歧。

## 改动 2：webview/index.css（刷新按钮点击旋转动画）

### file: webview/index.css
### type: append

```css
/* === patch-claude: 刷新当前会话按钮点击旋转反馈（自创类，勿删）=== */
.ccReloadBtn svg{transition:transform .4s ease}
.ccReloadBtn:hover svg{transform:rotate(60deg)}
.ccReloadBtn:active svg{animation:ccReloadSpin .5s linear}
@keyframes ccReloadSpin{from{transform:rotate(0)}to{transform:rotate(360deg)}}
/* === end patch-claude === */
```

#### 设计说明

纯追加自创类规则，幂等（marker `.ccReloadBtn`）。反馈分两层：hover 时图标轻转 60°（暗示可点），**按下（active）时图标旋转一整圈**——贴合「刷新」语义，给用户明确「已触发刷新」的反馈。要求 IconButton 组件 `yf` 把 `className` 透传到根元素、SVG 是其后代；若该版本 `yf` 不透传 className，按钮仍可点、有 ariaLabel，仅丢失旋转动画（功能不受影响，属可接受降级）。

## 范围边界（不在本补丁内）

- **全屏编辑器模式（`window.IS_FULL_EDITOR===true`）**：该模式下 header 的工具栏按钮组（Session history / New session / 本刷新按钮）被 `!window.IS_FULL_EDITOR` 条件整体排除，不渲染。即全屏编辑器布局下没有本按钮入口。`window.location.reload()` 在全屏模式本身有效，只是缺按钮——如需在全屏模式也加入口，需另写补丁在全屏 header 区注入（全屏 header 无同类按钮组，注入点需另探）。绝大多数使用场景（侧边栏 `resolveWebviewView` + 编辑器面板 `setupPanel`）均为非全屏，已覆盖。
- **reload 进行中的流式回复**：是否中断取决于 CC 通信层在 webview reload 后能否续传，属运行时行为，本补丁不干预——应用后实测确认，结果回填本节。

## 验收要点（应用后实测，结果回填）

1. **只刷当前会话**：同窗口打开两个会话面板（侧边栏 + 编辑器区，或两个编辑器组），点其中一个的刷新按钮 → 只有这个面板重载，另一个不动。
2. **历史自动恢复**：reload 后该会话的对话历史重新出现，不丢消息。
3. **流式中断行为**（验收重点）：在一个会话正有流式回复时点刷新 → 观察流是中断、续传还是重发，把结果记到本节。
4. **按钮位置明显**：刷新按钮在 Session history / New session 旁边，iconSize:20 与它们一致，线条精细度协调，清晰可见可点；按下时图标旋转一圈。

## 已验证版本

- `2.1.214`：已应用（2026-07-18，index.js locate+replace、index.css append，`node --check` 通过，切片确认刷新按钮紧随 New session 按钮后；图标经渲染对照 + 视觉分析选定 Lucide refresh-cw stroke 1.5，线条精细度匹配 hZe）。**功能实测待 GUI 内确认**：reload window 后按钮可见性、只刷当前面板、历史恢复、流式中断行为——结果回填本节「验收要点」。
- `2.1.217`：图标两次微调（均同步到定位器与本机 index.js 已注入处）。① 线宽：strokeWidth 1.5 -> 1.2（用户反馈偏粗）；实测本版工具栏图标 fZe / mZe 为 fill 轮廓体系、线宽 1px（外圆 R7.5 - 内圆 R6.5 = 1.0 单位）。② 圆形大小：strokeWidth 1.2 -> 1.3 且 viewBox 0 0 24 24 -> -1 -1 26 26（用户反馈「圆形明显比左边大」）。根因：stroke 中心对齐外扩半个线宽，使圆外缘 (9+Sw/2)*20/24 > CC 的 7.5px；放大 viewBox 缩小整体、按比例补偿 stroke，使线宽 = 1.3*20/26 = 1.0px、圆外缘 = 7.42px（CC 7.5px）。功能实测仍待 GUI 内确认。
