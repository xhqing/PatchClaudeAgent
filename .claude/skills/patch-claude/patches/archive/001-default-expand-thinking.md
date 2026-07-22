---
id: 001-default-expand-thinking
title: 思考过程默认展开
target: webview/index.js
default_status: needs-reapply
---

# 001 思考过程默认展开

让 Claude 回答时 thinking 块默认展开而非折叠。

## 背景

控制展开/折叠的 React state `areThinkingBlocksExpanded` 由 `useState`（混淆别名每版本变，2.1.198 为 `ne`）创建，初值硬编码 `!1`（false=折叠），不持久化。变量驱动下游 `<details>` 的 `open=`。原生快捷键 `Ctrl+O` 可切换全部展开/折叠。

## 锚点策略（定位器化，跨版本自适应）

不再用死字节串 old/new（混淆名每版本变，必然 broken）。改用 `type:locate` 定位器，以**稳定语义指纹**动态算出本版本真实 old/new：

1. **Ctrl+O 翻转指纹**（高稳定）：`key==="o")<X>.preventDefault(),<SETTER>(<arg>)=>!<arg>`。这是思考展开态独有的快捷键处理——`Ctrl+O` 调用 setter 翻转当前值。从中动态提取 setter 名。
2. **setter 反推定义点**：setter 是某 `useState` 解构第二项，匹配 `[<state>,<setter>]=<HOOK>(!1)`，HOOK 名由正则捕获组动态提取，不写死。
3. **语义消歧**：若 `[<state>,<setter>]=<HOOK>(!1)` 多候选，仅保留其后 300 字符内紧跟含 `key==="o"` 翻转函数者，确保抓的是思考展开态而非同名 state。
4. **幂等自洽**：找不到 `!1` 态时，改找 `[<state>,<setter>]=<HOOK>(!0)`（已应用态），返回 `old=new` 恒等串。引擎检测到 `new in src` 直接判 verified，不改文件——无需静态 idempotent 标记。

> 该机制依赖：① `Ctrl+O` 快捷键翻转展开态这一交互未变；② 思考态仍是 `useState` 解构 + `!1`/`!0` 初值。两者都是产品行为级稳定锚点，远比混淆名可靠。

## 改动 1：useState 初值 false→true

### file: webview/index.js
### type: locate

### locator:
```python
def locate(src):
    # 1. Ctrl+O 翻转指纹 → 提取 setter 名（思考展开态独有快捷键处理）
    m = re.search(r'key==="o"\)[^,]*,(\w+)\(\((\w+)\)=>!\2\)', src)
    if not m:
        return {"found": False, "reason": "Ctrl+O 翻转指纹未命中（key==\"o\")...setter(x=>!x)），思考展开机制疑似重构"}
    setter, flip_arg = m.group(1), m.group(2)
    if setter == flip_arg:
        return {"found": False, "reason": f"setter 与翻转参数同名异常: {setter}"}

    # 2a. 未应用态：[state,setter]=HOOK(!1)
    pat_false = re.compile(r'\[(\w+),(' + re.escape(setter) + r')\]=(\w+)\(!1\)')
    cand = list(pat_false.finditer(src))
    if len(cand) > 1:
        cand = [c for c in cand
                if re.search(r'function\s+\w+\s*\(\w+\)\{[^}]{0,120}?key==="o"', src[c.end():c.end()+300])]
    if len(cand) == 1:
        old = cand[0].group(0)
        return {"found": True, "old": old, "new": old.replace("(!1)", "(!0)", 1),
                "reason": f"未应用态; setter={setter}; state={cand[0].group(1)}; hook={cand[0].group(3)}"}

    # 2b. 已应用态(幂等)：[state,setter]=HOOK(!0) → old=new 恒等，引擎走 new in src 判 verified
    pat_true = re.compile(r'\[(\w+),(' + re.escape(setter) + r')\]=(\w+)\(!0\)')
    cand_t = list(pat_true.finditer(src))
    if len(cand_t) > 1:
        cand_t = [c for c in cand_t
                  if re.search(r'function\s+\w+\s*\(\w+\)\{[^}]{0,120}?key==="o"', src[c.end():c.end()+300])]
    if len(cand_t) == 1:
        s = cand_t[0].group(0)
        return {"found": True, "old": s, "new": s,
                "reason": f"已应用态(幂等); setter={setter}; state={cand_t[0].group(1)}"}

    return {"found": False, "reason": f"setter={setter} 既无唯一 !1 也无唯一 !0 定义点（!1 候选 {len(cand)}，!0 候选 {len(cand_t)}），需人工重定位"}
```

### verify（引擎自动把关，无需手填）

- 定位器返回 `found=True` 且 `old` 在文件命中 1 次（引擎 `hit_count==1` 校验）
- 替换后 `new` 实际出现（引擎回读校验，失败自动回滚备份）
- 幂等：已应用文件返回 `old=new`，引擎 `new in src` 直接 verified，不重复改文件
- `!1`→`!0` 两字符等长置换，文件长度不变

### 失败处理

- **指纹未命中**（`key==="o")...setter(x=>!x)` 消失）：上游重构了 Ctrl+O 或思考展开交互，定位器返回 `found=False`，引擎标记 `broken`。进入下方「人工重定位 fallback」。
- **setter 既无 !1 也无 !0 唯一定义点**：多候选消歧失败或 state 改名，标记 `broken` 并记录候选数，提示人工消歧。

## 人工重定位 fallback（broken 时用）

定位器化后正常情况免人工。仅当定位器 broken（指纹/定义点结构被上游重构）时，按下述手工流程重定位一次：

prop 链 `areThinkingBlocksExpanded` 全是透传（无法反推定义点），可靠路径是逆向追调用：

1. 找接收 `areThinkingBlocksExpanded:r,setAreThinkingBlocksExpanded:s` 的透传层函数（2.1.198 为 `q8t(e,t,i,n,o=!1,r,s,a,l)`，函数名每版本变）。
2. 找其调用点 `q8t(...,J,ie,...)`（位置形参 r=J、s=ie）。
3. 该调用所在闭包（如 `function Gs(K,Ee)`）的外层组件函数体里，搜 `[J,ie]=SOMEHOOK(!1)` 即定义点。
4. 语义确认：定义点紧邻有 `Ctrl+O` 翻转函数 `ie(x=>!x)`。
5. 若只是混淆名/结构微调，把新指纹规律补进上方定位器正则；若交互大改，保持 broken 并报告。

## 跨版本移植性（诚实说明）

本补丁已从 `type:replace`（死字节串，弱移植）升级为 `type:locate`（定位器化，较好移植）。移植性取决于 Ctrl+O 翻转指纹 + useState `!1`/`!0` 初值这两个产品级行为锚点：

- **大概率免人工**：常规构建（混淆名变化、hook 名变化、透传层函数改名）—— 定位器动态捕获，自动适配。
- **仍可能 broken 的情形**：上游重构思考展开交互（换快捷键、改 state 架构、移除 useState）—— 此时定位器安全拒绝（`found=False`），按 fallback 手工重定位一次即可，定位器正则按新结构补全。

## 已验证版本

- `2.1.198`：verified（2026-07-03 升级为 `type:locate`；定位器经未打补丁/已打补丁双场景离线验证：未应用态 `old=[J,ie]=ne(!1)` 命中 1 次正确替换，已应用态幂等自洽返回 `old=new` 引擎判 verified 不改文件）。
- `2.1.197`：verified（2026-07-01，当时为 `type:replace` 死字节串 `Y8t`，手工重定位后由引擎应用）。
- `2.1.195`：曾标记 verified 但经核查文件内仍为 `ne(!1)`（new `ne(!0)` 不在文件），即补丁未实际应用，属引擎幂等判定误报。此误报已记录；该版本目录现已可清理。
