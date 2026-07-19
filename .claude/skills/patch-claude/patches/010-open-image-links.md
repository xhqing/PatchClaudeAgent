---
id: 010-open-image-links
title: 让 markdown 图片链接可在 VSCode 打开（openFile 走 vscode.open）
target: extension.js
default_status: needs-reapply
---

# 010 让 markdown 图片链接可在 VSCode 打开

## 背景

CC VSCE 会话里 assistant 输出的 markdown 文件链接，点文本/代码文件能正常在当前工作区打开，但**点图片等二进制文件没反应**。

根因（已读 extension.js 源码确认）：`async openFile(e,t)`（处理 webview `open_file` 请求）用 `vscode.window.showTextDocument(uri)` 打开文件——该方法只能打开**文本文档**，对 PNG/JPG 等二进制图片会失败；该调用后**没有 `.catch()`**，失败被静默吞掉，用户看到「点了没反应」。

## 修复思路

在 `showTextDocument` 调用前插入一个图片分支：遇到图片扩展名就走 `vscode.commands.executeCommand("vscode.open", uri)`（VSCode 内置命令，用内置图片查看器打开），其它文件保留原 `showTextDocument` 逻辑（代码文件的 `revealRange` 行号定位不受影响）。复用 `openFile` 作用域内已有的 path 变量（解析后的绝对路径，如 `r`）与 uri 变量（`ge.Uri.file(r)`，如 `n`），不引入新依赖。

openFile 的相关结构（2.1.214）：

```js
let n=ge.Uri.file(r);try{if(Oi.statSync(r).isDirectory()){ge.commands.executeCommand("revealInExplorer",n);return}}catch{}ge.window.showTextDocument(n).then((i)=>{if(t?.searchText){...revealRange...}})
```

补丁在 directory 分支的 `}}catch{}` 与 `ge.window.showTextDocument(n)` 之间插入图片 try 分支。

## 改动 1：extension.js（openFile 加图片分支）

### file: extension.js
### type: locate
### idempotent: `executeCommand("vscode.open",`

### locator:
```python
def locate(src):
    import re
    # 第 1 步：directory 分支核心 —— revealInExplorer 调用后紧跟 }}catch{} + 同 ns/uri 的 showTextDocument。
    # 要求 revealInExplorer 与 showTextDocument 用同一个 ns 与 uri，锁死 openFile 方法，不会误伤别处。
    pat1 = re.compile(
        r'executeCommand\("revealInExplorer",(?P<uri>\w+)\);return\}\}catch\{\}'
        r'(?P<ns>\w+)\.window\.showTextDocument\((?P=uri)\)\.then\('
    )
    m1 = pat1.search(src)
    if not m1:
        return {"found": False, "reason": "openFile 的 revealInExplorer→showTextDocument 核心结构未命中，上游疑似重构"}
    ns, uri = m1.group("ns"), m1.group("uri")
    # 第 2 步：在核心前 200 字内找 statSync(PATH)（directory 判定用），捕获 path 变量。
    pre = src[max(0, m1.start() - 200):m1.start()]
    m2 = re.search(r'statSync\((?P<path>\w+)\)', pre)
    if not m2:
        return {"found": False, "reason": "openFile 找到 revealInExplorer 但其前方无 statSync(PATH)，结构异常"}
    path = m2.group("path")
    # 构造本版本真实 old / new
    sep = "}}catch{}"                       # close-if } + close-try } + 空 catch 块 {}
    old = sep + ns + ".window.showTextDocument(" + uri + ").then("
    branch = (
        "try{if(/\\.(png|jpe?g|gif|webp|bmp|ico|svg|tiff?|avif)$/i.test(" + path + "))"
        "{" + ns + '.commands.executeCommand("vscode.open",' + uri + ");return}}catch{}"
    )
    new = sep + branch + ns + ".window.showTextDocument(" + uri + ").then("
    hit = src.count(old)
    if hit != 1:
        return {"found": False, "reason": "定位到 old 但命中 " + str(hit) + " 次（!=1），需人工重定位"}
    return {"found": True, "old": old, "new": new, "hit_count": hit,
            "reason": "openFile 图片分支：扩展名走 vscode.open（ns=" + ns + "/uri=" + uri + "/path=" + path + ")"}
```

#### 设计说明

定位器用**两步法**动态提取本版本的三个混淆符号，跨版本自适应、不写死任何混淆名：

- **第 1 步**锚定 directory 分支核心 `executeCommand("revealInExplorer",URI);return}}catch{}NS.window.showTextDocument(URI).then(`——`revealInExplorer` 是 VSCode 公开命令名（稳定），`showTextDocument` 是 VSCode 公开 API（稳定）。用命名组 + 反向引用 `(?P=ns)`/`(?P=uri)` 强制两次调用用同一个命名空间与 uri 变量，锁死 openFile 方法、不会误伤别的 `showTextDocument` 调用（全文件共 5 处）。捕获 ns（如 `ge`）、uri（如 `n`）。
- **第 2 步**在核心前 200 字内回找 `statSync(PATH)`，捕获 path 变量（如 `r`）。directory 判定 `Oi.statSync(r).isDirectory()` 与 revealInExplorer 调用紧邻，200 字窗口足够覆盖；且只取 PATH 组、不依赖 `Oi` 这个模块别名（它可能变）。

构造的 old 串是 directory 分支结尾分隔 `}}catch{}` + `NS.window.showTextDocument(URI).then(`，唯一命中（已验证 hit_count==1）。new 在该分隔处插入图片 try 分支：

```js
try{if(/\.(png|jpe?g|gif|webp|bmp|ico|svg|tiff?|avif)$/i.test(r)){ge.commands.executeCommand("vscode.open",n);return}}catch{}
```

正则用 `\.(png|jpe?g|...|avif)$/i` 直接测 path 结尾，**绕开 `Tn.extname`**——压缩后的 extension.js 里 `Tn.extname` 出现 0 次（被压没了），而 `Tn.join`/`Tn.isAbsolute` 还在，故用正则测路径结尾比依赖 extname 更稳。图片分支自包 `try{...}catch{}`，失败（如非预期路径格式）静默落回后面的 `showTextDocument`，不破坏原逻辑。

#### verify

- 定位器 `found=True` 且 `hit_count==1`
- 替换后 `executeCommand("vscode.open",` 出现（幂等标记）
- `node --check extension.js` 通过
- 行为：① 点 markdown 图片链接 → VSCode 编辑器区用图片查看器显示；② 点文本/代码文件链接 → 仍正常打开，带行号时 `revealRange` 定位不受影响（原逻辑未坏）

#### 失败处理

- **核心结构未命中**（revealInExplorer→showTextDocument 链断）：上游重构了 openFile。搜 `revealInExplorer`（全文件唯一）重看 directory 分支与 showTextDocument 的衔接方式，更新第 1 步正则。
- **命中核心但前方无 statSync(PATH)**：directory 判定改写（如换 fs API）。在核心前扩大窗口或换关键词（`isDirectory`/`existsSync`）重定位 path 变量。
- **hit_count≠1**：`}}catch{}NS.window.showTextDocument(URI).then(` 出现多次——极不可能（仅 openFile 这一处）。加更靠前上下文消歧。

## 范围边界

- 仅作用于 openFile 的 `open_file` 路径。其它打开文件的入口（若有）不在本补丁范围。
- 图片用 VSCode 内置查看器打开（`vscode.open` 命令的默认行为）；不改变图片在磁盘上的存储。
- 非图片二进制文件（如 `.pdf`、`.zip`）仍走原 `showTextDocument`（VSCode 对其的默认行为不变）；如需扩展更多二进制类型，往正则的扩展名组里加。

## 已验证版本

- `2.1.214`：本机预验证通过（2026-07-18）——定位器 found=True、hit_count==1、捕获 ns=ge/uri=n/path=r，`node --check` 通过，净增 125 字符，幂等标记 `executeCommand("vscode.open",` 应用前缺失/应用后命中。运行时行为（点图片链接打开、点文本链接仍带行号定位）待 reload window 后实测。
