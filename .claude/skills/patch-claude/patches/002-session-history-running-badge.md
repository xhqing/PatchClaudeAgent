---
id: 002-session-history-running-badge
title: 历史会话列表项显示运行中标记
targets: [webview/index.js, webview/index.css]
default_status: needs-reapply
---

# 002 历史会话列表项显示运行中标记

多个对话任务并行运行时，在"Session history"抽屉的每个会话列表项上显示运行状态标记：真在跑 → 闪烁圆点 + "Running"；等待输入 → "Waiting"。

## 背景

- 历史抽屉由顶部按钮 `ariaLabel:"Session history"`（组件 `wQe`，`onClick:()=>a(!s)`）切换，抽屉组件 `gQe`，列表项组件 `eLt`。
- 每个 session 对象有 `busy.value`（真在跑=true）和 `pendingInput.value`（等输入=true），由 sessionStates 实时刷新（偏移 ~3166565 / ~4800688）。语义：busy && !pendingInput = "running"，pendingInput = "waiting_input"。
- 原列表项（`eLt`）只渲染 标题 / worktree pill / 时间 / 重命名+删除按钮，**不读取 busy.value**——这是缺口。

## 改动 1：webview/index.js（插入标记节点）

### file: webview/index.js
### type: locate
### idempotent_marker: ccRunDot

### locator:

```python
def locate(src):
    # 前置：历史会话功能仍在，且 session 对象仍带 busy/pendingInput 信号
    if 'ariaLabel:"Session history"' not in src:
        return {"found": False, "reason": "Session history 锚点消失"}
    if "busy.value" not in src or "pendingInput.value" not in src:
        return {"found": False, "reason": "session busy/pendingInput 信号消失"}
    # 用结构化正则动态提取本版本混淆符号名，不写死 gn/mQe/OD/r
    pat = re.compile(
        r'b\("span",\{className:([a-zA-Z_$][\w$]*)\.sessionName,'
        r'children:([a-zA-Z_$][\w$]*)\(([a-zA-Z_$][\w$]*)\(t\),([a-zA-Z_$][\w$]*)\)\}\)'
    )
    m = pat.search(src)
    if not m:
        return {"found": False, "reason": "未匹配到会话标题 span 渲染模式"}
    gn, mQe, OD, r = m.group(1), m.group(2), m.group(3), m.group(4)
    # 拼出本版本真实 old / new（纯字符串拼接，避免 f-string 花括号转义）
    old = ('b("span",{className:' + gn + '.sessionName,children:'
           + mQe + '(' + OD + '(t),' + r + ')})')
    insert = (',b("span",{className:"ccRunDot"+(t.busy.value?" ccRunning"'
              ':" ccWaiting"),style:{display:(t.busy.value||t.pendingInput'
              '.value)?"inline-flex":"none"},children:[b("span",{className'
              ':"ccRunDotI"}),(t.pendingInput.value?"Waiting":"Running")]})')
    new = old + insert
    return {"found": True, "old": old, "new": new, "hit_count": src.count(old)}
```

#### 设计说明

定位器用结构化正则匹配「会话标题 span 渲染」这个**语义结构**，动态提取本版本的样式对象名(`gn`)、标题高亮函数(`mQe`)、标题取值(`OD`)、搜索词(`r`)，再拼出 old 与 new。不写死任何混淆符号名，因此跨版本自适应。稳定锚点是 `ariaLabel:"Session history"` 和 `.sessionName` 字段名（CSS 模块字段名，混淆名前缀稳定）。

插入的标记节点：在 sessionName span 后逗号接一个条件 span，读 `t.busy.value`/`t.pendingInput.value`，busy 或 pendingInput 任一为真才 inline-flex 显示，否则 display:none；圆点 `.ccRunDotI` + 文字 Running/Waiting。

#### verify

- 定位器返回 found=True、hit_count==1
- 替换后 new 在文件、old 残留计算正确
- `node --check` 通过（JS 语法合法）

#### 失败处理

- `Session history` 锚点消失 → broken，上游重构了历史抽屉，需人工复核。
- `busy.value`/`pendingInput.value` 消失 → broken，session 对象接口变了，需更新定位器取值字段。
- 正则未匹配 → broken，标题 span 渲染结构变了，需更新正则（参考 `.sessionName` 字段名重新定位）。
- hit_count≠1 → broken，多处同名结构，需在定位器里加更窄的上下文消歧。

## 改动 2：webview/index.css（追加自创类规则）

### file: webview/index.css
### type: append

```css
/* === patch-claude: 历史会话列表项运行状态标记（自创类，勿删）=== */
@keyframes ccRunPulse{0%,100%{opacity:1}50%{opacity:.25}}
.ccRunDot{display:inline-flex;align-items:center;gap:4px;margin-left:8px;font-size:11px;line-height:1;vertical-align:middle;white-space:nowrap}
.ccRunDot .ccRunDotI{display:inline-block;width:7px;height:7px;border-radius:50%;animation:ccRunPulse 1.1s ease-in-out infinite}
.ccRunDot.ccRunning{color:#7dd3fc}
.ccRunDot.ccRunning .ccRunDotI{background:#7dd3fc}
.ccRunDot.ccWaiting{color:#fcd34d}
.ccRunDot.ccWaiting .ccRunDotI{background:#fcd34d;animation-duration:2s}
/* === end patch-claude === */
```

#### precheck / verify

- precheck：marker `ccRunPulse` 不在文件中（未重复追加）
- verify：追加后 `ccRunPulse` 出现 1 次、`.ccRunDot{` 存在、结尾标记存在

#### 失败处理

CSS 是纯追加、独立自创类，几乎不会失败。若 `ccRunPulse` 已存在则跳过（幂等）。

## 已验证版本

- `2.1.195`：verified（2026-06-28，node --check 通过）
