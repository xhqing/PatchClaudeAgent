---
id: 011-latex-math-rendering
title: LaTeX 数学渲染（KaTeX，行内 $...$ 与块级 $$...$$）
targets: [extension.js, webview/index.js]
default_status: needs-reapply
---

# 011 LaTeX 数学渲染（KaTeX）

## 目标

让 CC 对话面板用 [KaTeX](https://katex.org) 渲染数学公式：行内 `$...$` 与块级 `$$...$$`（兼容 LaTeX 习惯的 `\(...\)` / `\[...\]`）。助手回答里的 `E = mc^2`、`$$\sum_{i=1}^n x_i$$` 等直接显示成排版精美的公式，而非原始文本。

## 探查结论（2.1.215，已读源码确认）

### 1. CC 的 markdown 渲染管线里有 DOMPurify，且对 `<span style>` 极严

CC 用 `micromark`/`remark`/`unified` 把 markdown 转 HTML 字符串，再经 **DOMPurify 3.1.7** 净化，最后由 React `dangerouslySetInnerHTML` 写进 DOM。净化时挂了一个 `uponSanitizeAttribute` 钩子（webview/index.js 内）：

```js
if(s.attrName==="style"||s.attrName==="class"){
  if(r.tagName==="SPAN"){
    if(s.attrName==="style"){
      s.keepAttr=/^(color\:(#[0-9a-fA-F]+|var\(--vscode(...))/.test(...)  // 只留 color:...
    }
  }
}
```

即 `<span>` 上**只保留 `color:` 开头的 style**，其余一律剥离。KaTeX 的 HTML 排版大量依赖 `<span style="position:...;font-size:...;padding:...">`——若在 markdown→HTML 阶段注入，这些 style 会被剥光，公式变成一堆错位的字符。

**因此注入时机必须在 DOMPurify 净化之后**（React 把消息写进 DOM 之后），直接操作 DOM 节点调用 KaTeX，绕开净化。KaTeX 生成的 `<span style>` 在 CC 净化之后写入，浏览器照单全收，不再经过 DOMPurify。

### 2. CC 对话 webview 的 CSP 只放本机源，CDN 全禁

`extension.js` 的 `getHtmlForWebview` 拼出 CSP（`e.cspSource` = `vscode.env.cspSource`，本机资源源）：

```js
p=`style-src ${e.cspSource} 'unsafe-inline'`   // CSS：本机 + 内联
f=`font-src ${e.cspSource}`                     // 字体：仅本机（CDN 字体被禁）
m=`img-src ${e.cspSource} data:`
h=`worker-src ${e.cspSource}`
// meta: ...script-src 'nonce-${u}';...         // 脚本：仅带 nonce 的本机 index.js（CDN 脚本被禁）
```

KaTeX 要走 jsdelivr CDN（库 JS + CSS + 字体 woff2），必须放开 `style-src`/`font-src`/`script-src` 对该域的限制。

### 3. KaTeX 0.18.1 仍是 UMD，`<script>` 加载后自动挂全局

`dist/katex.min.js` 挂 `window.katex`，`dist/contrib/auto-render.min.js` 挂 `window.renderMathInElement`。注入逻辑可直接调全局函数，不必打包进 bundle。

## 方案（全 CDN，改动最小、补丁自描述）

四块改动：

1. **extension.js**：CSP 的 `style-src` 加 `https://cdn.jsdelivr.net`（允许 CDN 加载 KaTeX CSS）。
2. **extension.js**：CSP 的 `font-src` 加 `https://cdn.jsdelivr.net`（允许 CDN 加载 KaTeX 字体 woff2）。
3. **extension.js**：CSP 的 `script-src` 加 `https://cdn.jsdelivr.net`（允许 CDN 动态加载 KaTeX JS）。
4. **webview/index.js**：append 一段注入逻辑——链式加载 KaTeX（CSS→JS→auto-render），加载完后用 `renderMathInElement` 扫描 `#root`，并挂 `MutationObserver` 监听流式输出后的 DOM 变化重渲染。

**为何全走 CDN 而非内联**：KaTeX JS（~280KB）+ CSS（~22KB）+ 数十个字体 woff2 内联进补丁会让补丁文件臃肿、且字体是二进制无法纯文本补丁。CDN 方案补丁最小、KaTeX 升级只改版本号。代价是依赖联网（CC 本就联网调 API，可接受）与 `script-src` 放开一个可信域（jsdelivr 是 npm 官方镜像）。

**为何在净化后注入而非接管 markdown 管线**：见上方「探查结论 1」——净化阶段注入会被 DOMPurify 剥 style。事后操作 DOM 既绕开净化又不破坏 CC 原有渲染。

## 改动 1：extension.js（style-src 放开 jsdelivr）

### file: extension.js
### type: locate
### idempotent: `style-src ${e.cspSource} 'unsafe-inline' https://cdn.jsdelivr.net`

### locator:
```python
def locate(src):
    old = "style-src ${e.cspSource} 'unsafe-inline'"
    new = old + " https://cdn.jsdelivr.net"
    if new in src:
        return {"found": True, "old": old, "new": new, "no_change": True}
    if old not in src:
        return {"found": False, "reason": "style-src ${e.cspSource} 'unsafe-inline' 锚点消失：CC 重构了 getHtmlForWebview 的 CSP 变量 p"}
    return {"found": True, "old": old, "new": new, "hit_count": src.count(old)}
```

#### 设计说明

追加式替换（old 是 new 前缀）。锚点 `style-src ${e.cspSource} 'unsafe-inline'` 是 CSP 指令名 + VSCode 公开 API `cspSource`，全 extension.js 唯一命中（已验证 hit_count==1）。`${e.cspSource}` 在源码里是模板字符串内的字面字符，定位器按普通字符串匹配即可。已应用态靠 idempotent 标记 / `new in src` 双重判幂等。

## 改动 2：extension.js（font-src 放开 jsdelivr）

### file: extension.js
### type: locate
### idempotent: `font-src ${e.cspSource} https://cdn.jsdelivr.net`

### locator:
```python
def locate(src):
    old = "font-src ${e.cspSource}"
    new = "font-src ${e.cspSource} https://cdn.jsdelivr.net"
    if new in src:
        return {"found": True, "old": old, "new": new, "no_change": True}
    if old not in src:
        return {"found": False, "reason": "font-src ${e.cspSource} 锚点消失：CC 重构了 CSP 变量 f"}
    return {"found": True, "old": old, "new": new, "hit_count": src.count(old)}
```

#### 设计说明

放开字体源，让 KaTeX CSS 里引用的 woff2 字体能从 jsdelivr 加载。锚点唯一命中（hit_count==1）。

## 改动 3：extension.js（script-src 放开 jsdelivr）

### file: extension.js
### type: locate
### idempotent: `script-src 'nonce-${u}' https://cdn.jsdelivr.net`

### locator:
```python
def locate(src):
    old = "script-src 'nonce-${u}'"
    new = "script-src 'nonce-${u}' https://cdn.jsdelivr.net"
    if new in src:
        return {"found": True, "old": old, "new": new, "no_change": True}
    if old not in src:
        return {"found": False, "reason": "script-src 'nonce-${u}' 锚点消失：CC 重构了 CSP meta 里的 script-src"}
    return {"found": True, "old": old, "new": new, "hit_count": src.count(old)}
```

#### 设计说明

放开脚本源，让注入逻辑能动态 `<script src=cdn>` 加载 KaTeX JS。注意区分：VSCode 内置 markdown preview 的 CSP（另一处，用 `{{NONCE}}` 双花括号占位符）与 CC 对话 webview 的 CSP（用 `${u}` 单花括号变量）。本锚点 `'nonce-${u}'` 只命中 CC 对话 webview 这一处（hit_count==1），不会误改 markdown preview。

nonce 与外部源并存时，带 nonce 的本机 index.js 照常执行，CDN 脚本也允许——正是所需。

## 改动 4：webview/index.js（注入 KaTeX 加载与渲染逻辑）

### file: webview/index.js
### type: append

```js
/* .ccKatex011 — patch 011: LaTeX math via KaTeX (jsdelivr CDN) */
;!function(){
  var w=window, D=document;
  if(w.__ccKatex011)return; w.__ccKatex011=!0;
  var V="0.18.1", B="https://cdn.jsdelivr.net/npm/katex@"+V+"/dist/";
  var L=D.createElement("link"); L.rel="stylesheet"; L.href=B+"katex.min.css"; D.head.appendChild(L);
  function ls(u,ok){var s=D.createElement("script");s.src=u;s.async=!0;s.onload=ok;s.onerror=function(){console.warn("[ccKatex011] load fail:",u)};D.head.appendChild(s);}
  function render(){
    var r=D.getElementById("root");
    if(!r||!w.renderMathInElement)return !1;
    try{
      w.renderMathInElement(r,{
        delimiters:[
          {left:"$$",right:"$$",display:!0},
          {left:"\\[",right:"\\]",display:!0},
          {left:"$",right:"$",display:!1},
          {left:"\\(",right:"\\)",display:!1}
        ],
        ignoredTags:["script","noscript","style","textarea","pre","code","option"],
        ignoredClasses:["cc-no-math","cc-code-block"]
      });
    }catch(e){return !1;}
    return !0;
  }
  function boot(){
    if(!w.renderMathInElement){return setTimeout(boot,150);}
    render();
    var r=D.getElementById("root");
    if(r&&w.MutationObserver){
      var t=null;
      new w.MutationObserver(function(){
        if(t)return; t=setTimeout(function(){t=null;render();},250);
      }).observe(r,{childList:!0,subtree:!0,characterData:!0});
    }
  }
  ls(B+"katex.min.js",function(){ls(B+"contrib/auto-render.min.js",boot);});
}();
```

#### 设计说明

- **哨兵 `.ccKatex011`**：引擎对 `type:append` 自动取 append 文本里首个 `.类名` 当幂等 marker。注释首行的 `.ccKatex011` 是首个点号串（其后 `jsdelivr CDN` 等无连续 `.类名`），且原 index.js 无此串，幂等判定可靠。注释里刻意不出现别的 `.类名` 以免被抢先匹配。
- **运行时幂等 `window.__ccKatex011`**：防 index.js 被多次求值时重复加载（理论上不会，但兜底）。
- **加载链**：先 append KaTeX CSS `<link>`（样式先就位，避免公式闪现无样式）；再链式 `<script>` 加载 `katex.min.js` → `contrib/auto-render.min.js` → `boot()`。动态 `<script>` 不需要 nonce（改动 3 已放开 jsdelivr 源）。
- **`render()`**：对 `#root` 整树调 `renderMathInElement`。`delimiters` 覆盖 `$$...$$`（块）、`\[...\]`（块）、`$...$`（行内）、`\(...\)`（行内）。`ignoredTags` 含 `pre`/`code`，跳过代码块里的 `$`（如 shell `$HOME`、JS 模板串不误渲染）；`ignoredClasses` 预留 `cc-no-math`/`cc-code-block`，若 CC 代码块是自定义组件（非 `<pre><code>`）可后续把对应类名加进来。
- **`boot()` 轮询**：KaTeX JS 加载是异步的，`boot` 每 150ms 轮询 `renderMathInElement` 是否就绪；就绪后立即渲染整树，并挂 `MutationObserver`。
- **`MutationObserver` 防抖 250ms**：CC 流式输出时 React 频繁重写消息 DOM，会把 KaTeX 渲染冲掉；observer 监听 `#root` 子树变化，防抖 250ms 后重新 `render()`，让公式在流式结束后重新出现。防抖避免每次字符到达都重扫整树的性能问题。
- **绕过 DOMPurify**：`renderMathInElement` 在 CC 净化完成后运行，直接用 KaTeX 生成的 `<span style>` 覆盖文本节点，浏览器解析这些 HTML 不再经过 DOMPurify，KaTeX 排版完整保留。

#### verify

- 引擎对改动 1/2/3：定位器 `found=True`、`hit_count==1`、追加式幂等命中。
- 引擎对改动 4：append 后重读 index.js，`.ccKatex011` 出现 0 → 1（marker 命中）。
- `node --check extension.js` 与 `node --check webview/index.js` 均通过（语法正确）。
- **行为（需 reload window 后实测）**：① 让助手输出 `$E=mc^2$` → 行内渲染成公式；② 输出 `$$\int_0^1 x\,dx$$` → 块级居中公式；③ 代码块里的 `$HOME` / `$variable` 不被误渲染；④ 流式输出过程中公式在结束后出现（防抖 250ms）；⑤ 断网或 jsdelivr 不可达时，原文 `$...$` 保留、不报错（`onerror` 仅 console.warn）。

#### 失败处理

- **CSP 锚点消失（改动 1/2/3 broken）**：CC 重构 `getHtmlForWebview`。搜 `cspSource`（VSCode 公开 API，稳定）重新定位 CSP 变量定义与 meta，更新定位器 old 串。
- **`.ccKatex011` 已在 index.js（改动 4 误判已应用）**：不会发生——该哨兵是补丁特有串，原文件没有。
- **reload 后公式不渲染（CSP 拦了 CDN）**：开 webview DevTools（`Developer: Open Webview DevTools` 或开发者工具）看 Console。若报 CSP 违规（`Refused to load script/font ... because it violates CSP`），说明改动 1/2/3 没全生效——查 version-map 该版本三块是否都 verified。
- **CDN 加载失败（jsdelivr 不可达）**：Console 有 `[ccKatex011] load fail`。可换 CDN 源（改 append 内容里的 `B` 为 unpkg/staticfile 等），或改用内联方案（把 KaTeX dist 内联进 index.js，体积大但离线可用）。
- **代码块里 `$` 被误渲染**：CC 代码块若不是 `<pre><code>` 而是自定义组件，需把该组件的类名加进 `ignoredClasses`。用 DevTools 选中代码块看 className，回填 append 内容。
- **流式时公式闪烁/重复**：调大 `MutationObserver` 防抖（250→400ms）；或给已渲染节点打 `data-katex-done` 属性，render 时跳过。
- **KaTeX 升级（0.18.x→0.19）**：改 append 内容里的 `V="0.18.1"`；若 auto-render API 变更（不再是全局 `renderMathInElement`），改 `boot`/`render` 的调用方式。

## 范围边界（不在本补丁内）

- **依赖联网**：jsdelivr CDN 不可达时公式回退为原文，不影响阅读与 CC 其它功能。离线场景需另做内联方案。
- **`script-src` 放开 jsdelivr**：仅放开该单一可信域（npm 官方镜像），非 `*`。风险是 jsdelivr 被投毒波及 KaTeX 包；对自用补丁可接受，注重时可改内联。
- **仅渲染对话消息区**：作用于 `#root`（CC 对话面板）。VSCode 内置 markdown preview、其它 webview 不受影响（CSP 改动只针对 CC 对话 webview 的 `getHtmlForWebview`）。
- **不接管 CC 的 markdown 管线**：不改 micromark/remark 配置、不加数学语法扩展；纯事后 DOM 扫描。优点是不碰 CC 核心、升级兼容性好；缺点是 `$...$` 在 CC 看来仍是普通文本（如复制出来仍是原文）。
- **复杂公式渲染质量取决于 KaTeX**：KaTeX 覆盖绝大多数 LaTeX 数学语法，但不支持 `\begin{equation}` 等少数 LaTeX 环境的完整语义（KaTeX 的 support 表见其官网）。

## 已验证版本

- `2.1.215`：本机预验证通过（2026-07-19）——三个 CSP 锚点 hit_count==1、追加式幂等；KaTeX 0.18.1 三文件 CDN 可访问（`dist/katex.min.js`、`dist/contrib/auto-render.min.js`、`dist/katex.min.css` 均 HTTP 200）、UMD 全局挂载确认；append 哨兵 `.ccKatex011` 唯一。运行时渲染效果（`$...$`/`$$...$$` 渲染、代码块保护、流式防抖）待 reload window 后实测。
