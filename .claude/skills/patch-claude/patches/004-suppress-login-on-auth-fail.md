---
id: 004-suppress-login-on-auth-fail
title: token 用尽时不弹登录界面
target: webview/index.js
default_status: needs-reapply
---

# 004 token 用尽时不弹登录界面

当 Claude 扩展遇到 `authentication_failed` 错误（token 用尽 / 认证失效）时，上游会调用 `this.context.showLogin()` 弹出登录界面。用户用本地代理 + API key 跑扩展、不登录，token 用尽时弹登录页是干扰而非引导——本补丁把这次 `showLogin()` 调用改成 `void 0`（什么都不做），抑制弹窗。

## 背景

webview 收到 `type==="assistant"` 且 `error==="authentication_failed"` 的消息时，原逻辑：

```js
else if(e.type==="assistant"){if(e.error==="authentication_failed")this.context.showLogin();if(e.message&&Array.isArray(e.message.content)){...}}
```

- `e` 是消息对象（混淆名，每版本可能变）
- `authentication_failed` 是产品级错误码字符串，全文件唯一出现
- `this.context.showLogin()` 弹登录页

与 [[vscode-claude-disable-login-prompt]] 是两件事：那条用 `claudeCode.disableLoginPrompt` 设置项挡 OAuth 登录弹窗（设置层，扩展无关）；本补丁挡的是 token 用尽时由 webview 代码主动触发的 `showLogin()`（代码层，需随升级重打）。两者互补，都留着。

调用处上下文稳定：`authentication_failed` 只在 `if(<var>.error==="authentication_failed")this.context.showLogin()` 这一处出现，是可靠的定位锚点。

## 改动 1：showLogin() 调用替换为 void 0

### file: webview/index.js
### type: locate
### idempotent: `/*PATCHED: suppress login popup on token exhaustion*/`

### locator:
```python
def locate(src):
    # 1. 未应用态：if(<var>.error==="authentication_failed")this.context.showLogin();
    #    （含尾分号，整个 showLogin() 语句被整体替换）
    pat = re.compile(
        r'if\((\w+)\.error==="authentication_failed"\)this\.context\.showLogin\(\);')
    cand = list(pat.finditer(src))
    if len(cand) == 1:
        var = cand[0].group(1)
        old = cand[0].group(0)
        # 保留 === 不变，把 this.context.showLogin(); 换成 void 0; + 注释
        # new 末尾不带分号：void 0; 已自带语句结束，注释充当尾部
        new = ('if(' + var + '.error==="authentication_failed")void 0; '
               '/*PATCHED: suppress login popup on token exhaustion*/')
        return {"found": True, "old": old, "new": new,
                "hit_count": src.count(old),
                "reason": "未应用态; msg_var=" + var}

    # 2. 已应用态(幂等)：匹配 new 形态，返回 old=new 恒等，引擎走 new in src 判 verified
    pat_done = re.compile(
        r'if\((\w+)\.error==="authentication_failed"\)void 0; '
        r'/\*PATCHED: suppress login popup on token exhaustion\*/')
    cand_t = list(pat_done.finditer(src))
    if len(cand_t) == 1:
        s = cand_t[0].group(0)
        return {"found": True, "old": s, "new": s,
                "reason": "已应用态(幂等); msg_var=" + cand_t[0].group(1)}

    return {"found": False,
            "reason": f"authentication_failed showLogin 锚点未命中（未应用 {len(cand)}，已应用 {len(cand_t)}），上游疑似改写错误码或登录处理逻辑"}
```

#### 设计说明

定位器用产品级稳定锚点，不写死任何混淆名：

1. **错误码字符串 `authentication_failed`** —— 全文件唯一出现，是本补丁最稳的锚点。
2. **`this.context.showLogin()` 调用** —— 紧跟错误码判断，`showLogin` 是方法语义名稳定。
3. 动态捕获消息对象变量名 `<var>`（2.1.201 为 `e`），构造 new 时回填，保证 old/new 在本版本精确匹配。

**保持 `===` 不变**：原 shell 脚本曾把 `===` 顺带改成 `==`（字符串比较等价，无功能差异）。定位器化后保留 `===`，只动 `this.context.showLogin();`→`void 0;`+注释，改动最小、最语义化。old 含 `showLogin()` 的尾分号、new 末尾用注释充当语句尾（不带分号）——这样替换后正合法、不留多余 `;`。

幂等标记用独特注释串 `/*PATCHED: suppress login popup on token exhaustion*/`，全文件唯一，不会误命中他处。引擎优先查幂等标记命中即 verified，故即便某版本目录残留原脚本的 `==` 形态产物，只要注释在就会判 verified（不会 broken）；真正走定位器替换只发生在升级后干净原版上。

> 注：2.1.201 当前文件由原脚本打过、形态为 `===`+`void 0`+注释（巧合与 new 一致），定位器已应用态正则直接命中，幂等 verified，无需改文件。

#### verify（引擎自动把关）

- 定位器 `found=True` 且 `old` 命中 1 次（引擎 `hit_count==1`）
- 替换后 `new` 出现（含幂等注释），引擎回读校验，失败自动回滚备份
- 幂等：注释串命中 → verified 不重复改文件

### 失败处理

- **未应用与已应用都 0 命中**：上游改了错误码字面量（如不在用 `authentication_failed`）、改了登录触发路径（不再调 `this.context.showLogin()`）、或重构消息处理结构 → broken，按 fallback 重定位。
- **多候选**：`authentication_failed` 应唯一，若出现多处需更窄上下文消歧 → broken。

## 人工重定位 fallback（broken 时用）

1. 搜 `authentication_failed` 定位错误处理处（2.1.201 唯一一处）。
2. 确认其后紧跟 `this.context.showLogin()` 调用；若上游换成别的弹登录方法（如 `this.showLogin()` / `forceLogin`），按新方法名补正则。
3. 若错误码改名（如 `auth_failed` / `token_exhausted`），在 [[vscode-claude-disable-login-prompt]] 记录新码，并更新定位器正则的字面量。
4. 若上游彻底移除「token 用尽弹登录」逻辑（自然不弹了），本补丁可考虑退役。

## 跨版本移植性

- **大概率免人工**：常规构建（消息对象混淆名 `e` 变化、`this.context` 别名变化）—— 定位器动态捕获自动适配。
- **可能 broken**：上游改错误码字符串、改登录触发方法、重构 assistant 消息错误处理 —— 定位器安全拒绝，按 fallback 重定位一次。

## 来源

原为独立 shell 脚本 `~/patch-claude-login.sh`（遍历所有扩展版本目录打补丁）。2026-07-04 纳入 [[patch-claude-skill]] 体系为 004，改造为定位器化补丁，由引擎统一管理（只打最新版，升级后自动重打）。原脚本可保留作为历史/备用，或确认体系稳定后删除。

## 已验证版本

- `2.1.201`：待应用（2026-07-04 新增；定位器在原版备份上 `old` 命中 1 次、msg_var=e；幂等正则在已打补丁文件上命中 1 次。注：当前 2.1.201 文件曾被原 shell 脚本打过 `==` 形态补丁，引擎首次运行会识别为未应用态并以 `===` 形态重打，自动收敛统一）。
