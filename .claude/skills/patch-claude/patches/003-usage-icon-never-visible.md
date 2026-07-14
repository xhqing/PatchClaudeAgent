---
id: 003-usage-icon-never-visible
title: 用量图标永不显示
target: webview/index.js
default_status: needs-reapply
---

# 003 用量图标永不显示

proxy 模式下 `totalTokens` 绝大多数时候为 0（native-binary 不稳定把 usage 透传给 webview 的 `updateUsage`），用量图标几乎恒显示 `0 / 1M tokens · 100% remaining`，无意义且占输入框左下角位置。本补丁让 `IXe` 组件永远 `return null`（不渲染），用量图标（饼图 + popup + compact 按钮）彻底消失。compact 仍可用 `/compact` 命令触发。

## 改动 1：IXe 永不渲染

### file: webview/index.js
### type: locate

### locator:
```python
def locate(src):
    import re
    # 幂等：已应用态（Bme 块内直接 return null，无 if(t===0) 守卫）
    if 'if(Bme===null){return null}' in src:
        return {"found": True, "old": "if(Bme===null){return null}",
                "new": "if(Bme===null){return null}", "no_change": True,
                "reason": "IXe 永不渲染已应用（幂等）"}
    # 官方/旧补丁态：if(Bme===null){if(t===0)return null[;if(<c>>=<N>)return null]}
    pat = re.compile(r'if\(Bme===null\)\{if\(t===0\)return null(?:;if\(\w+>=\d+\)return null)?\}')
    m = pat.search(src)
    if not m:
        return {"found": False, "reason": "IXe Bme return null 结构未命中，上游疑似重构"}
    old = m.group(0)
    new = 'if(Bme===null){return null}'
    return {"found": True, "old": old, "new": new, "hit_count": 1,
            "reason": "IXe → 永不渲染（Bme 恒 null → 永远 return null）"}
```

#### 设计说明

`IXe` 内 `Bme` 全局恒为 `null`（仅声明无赋值）。官方/旧补丁在 `if(Bme===null){...}` 块内用 `if(t===0)return null[;if(c>=N)return null]` 控制显隐。本补丁把块内改成无条件 `return null`——`Bme` 恒 null → 永远 `return null` → `IXe` 不渲染任何内容（饼图、popup、compact 按钮全消失），直接跳过后面的 `return E("div",...)`。

定位器双分支：
- **幂等态**：`if(Bme===null){return null}` 已在 src → no_change。
- **应用态**：匹配官方双 if 或旧补丁单 if 结构（`if(t===0)return null` 可选跟 `;if(<c>>=<N>)return null`），替换为 `if(Bme===null){return null}`。从官方或"始终显示"旧补丁升级都能收敛。

#### verify

- locator `found=True`
- 替换后 `if(Bme===null){return null}` 出现，原 `if(t===0)return null` / `if(c>=N)return null` 在 Bme 块内消失
- `node --check` 通过

### 失败处理

- **未命中**：上游改 `IXe` 显隐逻辑（如换变量名、改条件结构）→ broken，搜 `Bme` 或 `return null` 在含 `usedTokens`/`contextWindow` 参数的函数体重定位。

## 已验证版本

- `2.1.201`：待应用（从"始终显示"反转为"永不显示"，因 proxy 模式 totalTokens 几乎恒 0，用量图标无意义）。
