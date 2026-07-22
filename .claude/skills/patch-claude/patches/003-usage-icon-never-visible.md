---
id: 003-usage-icon-never-visible
title: 用量图标永不显示
target: webview/index.js
default_status: needs-reapply
---

# 003 用量图标永不显示

proxy 模式下 `totalTokens` 绝大多数时候为 0（native-binary 不稳定把 usage 透传给 webview 的 `updateUsage`），用量图标几乎恒显示 `0 / 1M tokens · 100% remaining`，无意义且占输入框左下角位置。本补丁让用量饼图组件（混淆名随版本变，2.1.217 为 `MXe`）永远 `return null`（不渲染），用量图标（饼图 + popup + compact 按钮）彻底消失。compact 仍可用 `/compact` 命令触发。

## 改动 1：IXe 永不渲染

### file: webview/index.js
### type: locate

### locator:
```python
def locate(src):
    import re
    # 主稳定锚：CSS 明文类名 usageContainer（用量饼图组件独有）。
    # 守卫块紧邻 return E("div",{className:<MOD>.usageContainer 渲染，
    # 用前瞻锁定上下文、不纳入替换，避免误伤文件里其它 return null 结构。
    # 动态捕获覆盖变量名（旧版 Bme / 2.1.217 为 Hme，随版本变），不写死任何混淆符号。
    # 幂等态：守卫块已是无条件 return null
    idem = re.compile(r'if\((\w+)===null\)\{return null\}(?=return E\("div",\{className:\w+\.usageContainer)')
    m = idem.search(src)
    if m:
        return {"found": True, "old": m.group(0), "new": m.group(0),
                "no_change": True, "reason": "用量组件永不渲染已应用（幂等）"}
    # 应用态：官方双 if 守卫（t===0 与 c>=N），前瞻锁定紧跟 usageContainer 渲染
    pat = re.compile(r'if\((\w+)===null\)\{if\((\w+)===0\)return null;if\((\w+)>=(\d+)\)return null\}(?=return E\("div",\{className:\w+\.usageContainer)')
    m = pat.search(src)
    if not m:
        return {"found": False, "reason": "用量组件守卫块未命中（usageContainer 渲染锚点前无双 if 守卫），上游疑似重构"}
    var, tok, pct, thr = m.groups()
    old = m.group(0)
    new = f'if({var}===null){{return null}}'
    return {"found": True, "old": old, "new": new, "hit_count": len(pat.findall(src)),
            "reason": f"用量组件 {var} 恒 null → 永远 return null（守卫 {tok}===0/{pct}>={thr} 失效）"}
```

#### 设计说明

用量饼图组件内有一个全局覆盖变量（仅声明、无赋值，恒为 `null`；混淆名随版本变：旧版 `Bme`、`2.1.217` 为 `Hme`）。官方在 `if(<var>===null){...}` 块内用 `if(t===0)return null;if(c>=N)return null` 双守卫控制显隐（`t` 为 usedTokens、`c` 为剩余百分比、`N` 为阈值，2.1.217 为 50）。本补丁把块内改成无条件 `return null`——覆盖变量恒 null → 永远 `return null` → 组件不渲染任何内容（饼图、popup、compact 按钮全消失），直接跳过后面的 `return E("div",...)`。

定位器以 CSS 明文类名 `usageContainer`（用量组件独有）为主稳定锚，用前瞻 `(?=return E("div",{className:\w+\.usageContainer)` 锁定「守卫块紧邻该渲染」的上下文，正则动态捕获 `var`/`t`/`c`/`N` 四个符号，**不写死任何混淆名**——这是从旧版（写死 `Bme`）在 2.1.217 失效后升级的跨版本自适应方案。双分支：
- **幂等态**：守卫块已是 `if(<var>===null){return null}` 且紧邻 usageContainer 渲染 → no_change。
- **应用态**：匹配官方双 if 守卫，替换为 `if(<var>===null){return null}`。从官方态升级即收敛。

#### verify

- locator `found=True`
- 替换后 `if(Bme===null){return null}` 出现，原 `if(t===0)return null` / `if(c>=N)return null` 在 Bme 块内消失
- `node --check` 通过

### 失败处理

- **未命中**：上游改用量组件显隐逻辑（如守卫结构重写、类名 `usageContainer` 改名）→ broken。重定位手法：搜明文 `usageContainer` 锁定用量饼图组件函数，再看其 `if(<var>===null){...}` 守卫块与紧邻的 `return E("div",{className:<MOD>.usageContainer` 渲染关系，据实更新正则（仍以 `usageContainer` 明文为主锚）。

## 已验证版本

- 起因：proxy 模式 `totalTokens` 几乎恒 0，用量图标恒显 `0 / 1M tokens · 100% remaining`，无意义，故让其永不渲染。
- `2.1.211` / `2.1.214` / `2.1.215`：写死 `Bme` 的旧定位器 verified。
- `2.1.217`：上游混淆名 `Bme→Hme`、组件 `IXe→MXe`，旧定位器写死符号名失效（broken）；改为以 CSS 明文 `usageContainer` 为主锚 + 前瞻锁定渲染 + 动态捕获符号名，重新 verified。
