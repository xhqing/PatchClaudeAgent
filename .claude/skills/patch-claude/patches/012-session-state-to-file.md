---
id: 012-session-state-to-file
title: 会话运行状态写盘供外部 watcher 读取
targets: [extension.js]
default_status: needs-reapply
---

# 012 会话运行状态写盘供外部 watcher 读取

把每个会话的实时运行状态（idle / running / thinking / waiting_input）写到固定路径文件，供外部进程（如 DayTradingAgent 的密采样守护 watcher，独立 launchd 进程）读取会话是否真在 Running。

## 背景

- `updateSessionState(e,t,r)` 是 extension.js 主进程里**唯一**的会话状态更新入口：每次会话状态变化（idle → running → thinking → waiting_input）都经过它，把 `{sessionId:e, state:t, title:r}` 存入 `sessionStates` 并广播给 webview。
- 参数 `e`=sessionId、`t`=state（字符串枚举：`"idle"` / `"running"` / `"thinking"` / `"waiting_input"` / `"active"`）、`r`=title。
- webview 侧补丁 002（历史会话 Running 标记）已用 `busy = state !== "idle"`、`pendingInput = state === "waiting_input"` 显示状态；但状态只在 extension 进程内存 + webview 内存，**不写盘、无 CLI/API 暴露**，外部进程读不到。
- DayTradingAgent watcher 需要从外部判断「会话是否真在 Running（非 idle、非 waiting_input）」来决定是否报中断——采样脚本没在跑 + 会话也没在 Running 才报。需补丁把 state 写盘，watcher 读文件 = 真·Running 状态。

## 改动 1：extension.js（updateSessionState 注入写盘）

### file: extension.js
### type: locate
### idempotent: `ccSessionStateWrite`

### locator:

```python
def locate(src):
    import re
    # 前置：注入点方法与 state 字段语义仍在
    if "updateSessionState(" not in src:
        return {"found": False, "reason": "updateSessionState 方法消失"}
    if "this.sessionStates.set(" not in src:
        return {"found": False, "reason": "sessionStates.set 语义消失"}
    # 幂等优先：若已注入（含 ccSessionStateWrite 标记），直接判 verified，不依赖正则
    # 重新匹配注入后的结构（注入会在 broadcastSessionStates() 与 } 之间插入 try 块，
    # 破坏原始正则锚点，故幂等判定必须放在正则匹配之前，否则每次重检都误报 broken）。
    if "ccSessionStateWrite" in src:
        return {"found": True, "old": "__idempotent__", "new": "__idempotent__",
                "no_change": True, "reason": "已注入写盘（幂等，ccSessionStateWrite 标记命中）"}
    # 动态提取 updateSessionState 的参数名（e,t,r）与 sessionStates.set 的字段结构。
    # 锚定稳定语义：方法名 updateSessionState + sessionId/state 字段名（混淆名前缀稳定）。
    pat = re.compile(
        r'updateSessionState\(([a-zA-Z_$][\w$]*),([a-zA-Z_$][\w$]*),([a-zA-Z_$][\w$]*)\)'
        r'\{this\.sessionStates\.set\(\1,\{sessionId:\1,state:\2,title:\3\}\)'
        r',this\.broadcastSessionStates\(\)\}'
    )
    m = pat.search(src)
    if not m:
        return {"found": False, "reason": "未匹配到 updateSessionState 定义结构"}
    old = m.group(0)
    # 注入：在 broadcastSessionStates() 之后、原 } 之前，加一段写盘。
    # 写到 ~/.claude/session_running/<sessionId>.txt，内容=state（参数 \2）。
    # 用 require("path")/require("fs") 现取（extension 里 require("fs") 原生可用、出现 35+ 次），
    # process.env.HOME 取家目录（无需 require("os")）。try/catch 兜底，写盘失败不影响原逻辑。
    inject = (
        ';try{const _ssP=require("path"),_ssF=require("fs"),'
        '_ssD=_ssP.join(process.env.HOME||"",".claude","session_running");'
        '_ssF.mkdirSync(_ssD,{recursive:!0}),'
        '_ssF.writeFileSync(_ssP.join(_ssD,' + m.group(1) + '+".txt"),' + m.group(2) + ')'
        '}catch(_ssE){}/*ccSessionStateWrite*/'
    )
    # 把原结尾 } 前插入 inject：去掉 old 末尾的 } ，加 inject 再补 }
    new = old[:-1] + inject + "}"
    return {"found": True, "old": old, "new": new, "hit_count": src.count(old)}
```

#### 设计说明

- 定位器用结构化正则锚定 `updateSessionState(<a>,<b>,<c>){this.sessionStates.set(<a>,{sessionId:<a>,state:<b>,title:<c>}),this.broadcastSessionStates()}`，动态提取三个参数名（`e/t/r` 是当前版本、混淆后可能变），拼出 old 与 inject，不写死任何混淆符号名。
- 稳定锚点：方法名 `updateSessionState`（语义名，不易被混淆）+ `sessionStates.set` + 字段名 `sessionId`/`state`/`title`（对象字段名稳定）。
- 写盘路径全局固定 `~/.claude/session_running/<sessionId>.txt`——不依赖 extension 的 cwd（VSCode workspace 根，不一定 = 某项目根），watcher 从固定路径读，跨项目通用。
- 文件名用完整 sessionId（`e` 参数）、内容=state（`t` 参数，裸字符串如 `running`）。watcher 判定只看内容是否为 `running`/`thinking`。
- 幂等：注入后含 `ccSessionStateWrite` 标记，重打补丁时定位器返回 `no_change`，不重复注入。
- try/catch 兜底：写盘失败（磁盘满 / 权限）不影响 extension 主流程。

#### verify

- 定位器返回 found=True、hit_count==1（`updateSessionState` 定义全局唯一）。
- 替换后 new 在文件、old 残留计算正确；`ccSessionStateWrite` 标记出现 1 次。
- `node --check extension.js` 通过（JS 语法合法）。

#### 失败处理

- `updateSessionState(` 消失 → broken，上游重构了状态管理，需人工复核。
- `sessionStates.set` / `sessionId`/`state`/`title` 字段消失 → broken，状态对象接口变了，需更新定位器。
- 正则未匹配 → broken，方法签名结构变了，需更新正则。
- hit_count≠1 → broken，多处同名结构，需在定位器加更窄上下文。

## 使用方（DayTradingAgent watcher）

watcher（`.claude/hooks/monitor_watcher.py`）判定逻辑配套改为：

1. 死会话自动剔除（jsonl 停更 > 30 分钟）。
2. 采样在跑（monitor_segment / ws_segment / futu_ws_segment 任一存活）→ 不报。
3. 采样没在跑 → 读 `~/.claude/session_running/<sid>.txt`：内容是 `running`/`thinking` → 会话真在 Running、不报；`waiting_input`/`idle`/文件缺失/过期 → 报中断（采样停 + 会话也没在 Running）。

## 已验证版本

- `2.1.226`：待验证（定位器 hit_count==1 确认、注入后 node --check + 实跑确认 state 文件随状态变化写入）。
