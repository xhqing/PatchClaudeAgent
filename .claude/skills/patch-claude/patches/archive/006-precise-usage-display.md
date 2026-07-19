---
id: 006-precise-usage-display
title: 使用量指示器精确化（连续弧饼图 + 具体 token 数）
target: webview/index.js
default_status: needs-reapply
---

# 006 使用量指示器精确化（已废弃归档）

> ⚠️ **已废弃归档（2026-07-16）——被 003 取代，已移出 patches/**。003 让用量组件整体 `return null`，饼图随之消失，本补丁的「精确化饼图」目标在 003 下永远不可见。叠加 2.1.211 上游重构：用量组件改名 `DXe`（`IXe` 这个名字被复用为 Plan 图标组件），`LXe` 也变成 Plan 图标，本补丁的 `IXe`/`LXe`/饼图锚点全部失效——改动1 幂等被 React 自带的 `strokeDashoffset` SVG 属性表误判命中、伪装「已应用」，实则连续弧从未注入（`strokeDasharray:"31.42"` 出现 0 次）；改动2 `function IXe(...)` 签名未命中、broken。已从 `patches/` 移至 `archive/`，引擎不再处理。保留备查，勿复用其锚点。

上游 `IXe` 的饼图 `LXe` 只有 3 档预定义图标（`J9t` 把百分比映射到 50/75/99 三个固定 SVG path），使用率 <62.5% 一律画半圆，视觉误导。popup 文本只显示"X% remaining"百分比，不带具体 token 数。

本补丁：
1. 把 `IXe` 里的 `LXe` 调用换成内联连续弧 SVG（`stroke-dasharray` 按真实百分比画弧，任意百分比都精确）。
2. popup 文本加上 `usedTokens / contextWindow` 具体数值。

## 改动 1：饼图改连续弧

### file: webview/index.js
### type: locate

### locator:
```python
def locate(src):
    # 幂等：已应用态（连续弧 SVG 用 strokeDashoffset；官方 LXe path 无此属性）
    if 'strokeDashoffset' in src:
        return {"found": True, "old": "strokeDashoffset", "new": "strokeDashoffset",
                "no_change": True, "reason": "连续弧 SVG 已应用（strokeDashoffset 命中，幂等）"}
    # 官方态：匹配 IXe 内的 LXe 调用：<b>(LXe,{percentage:<l>,className:<AC>.pie})
    pat = re.compile(r'(\w+)\(LXe,\{percentage:(\w+),className:(\w+)\.pie\}\)')
    m = pat.search(src)
    if not m:
        return {"found": False, "reason": "LXe 调用未命中且无 strokeDashoffset，IXe 渲染疑似重构"}
    b_var, l_var, ac_var = m.group(1), m.group(2), m.group(3)
    old = m.group(0)
    # 连续弧：底色整圆(淡) + 已用弧(strokeDashoffset 按百分比)
    # r=5（原 path 圆心 10,10 半径 5），周长 2π*5≈31.42
    # strokeDashoffset = 周长*(1-l/100)，l=已用百分比；rotate(-90) 从顶部起笔
    new = (b_var + '("svg",{width:"20",height:"20",viewBox:"0 0 20 20",fill:"none",className:'
           + ac_var + '.pie,style:{display:"block"},children:['
           + b_var + '("circle",{cx:"10",cy:"10",r:"5",stroke:"currentColor",strokeOpacity:"0.15",strokeWidth:"1.5",fill:"none"}),'
           + b_var + '("circle",{cx:"10",cy:"10",r:"5",stroke:"var(--app-claude-clay-button-orange)",strokeWidth:"1.5",strokeLinecap:"round",fill:"none",strokeDasharray:"31.42",strokeDashoffset:String(31.42*(1-' + l_var + '/100)),transform:"rotate(-90 10 10)"})'
           ']})')
    return {"found": True, "old": old, "new": new, "hit_count": src.count(old),
            "reason": "createElement=" + b_var + " usedPct=" + l_var}
```

#### 设计说明

定位 `b(LXe,{percentage:<l>,className:<AC>.pie})` 调用点（LXe 稳，`b`/`l`/`AC` 动态提取），整段替换为内联 SVG。SVG 用两个 circle：底色圆（currentColor + opacity 0.15，等价原 Q9t 底弧但画整圆更简洁）+ 已用弧（橙色，`strokeDasharray=31.42` 周长，`strokeDashoffset=31.42*(1-l/100)` 按已用百分比缩进，`rotate(-90)` 让弧从 12 点钟起笔）。

r=5 依据原 `X9t` path（从 (10,5) 起，圆心 (10,10)）。颜色沿用原 `LXe` 的 `var(--app-claude-clay-button-orange)`。

只替换 IXe 内的调用点，不动 `LXe`/`J9t`/`Q9t`/`X9t` 定义（即使别处还用 LXe 也不受影响，只是 IXe 不再调它）。

#### verify

- `old` 命中 1 次
- 替换后 `strokeDashoffset` 出现
- `node --check` 通过

### 失败处理

- **LXe 调用未命中**：IXe 渲染重构 → broken，搜 `percentage:` + `.pie` 重新定位。

## 改动 2：popup 文本加具体 token 数

### file: webview/index.js
### type: locate

### locator:
```python
def locate(src):
    # 1. IXe 签名 → usedTokens / contextWindow 别名
    msig = re.search(
        r'function IXe\(\{usedTokens:(\w+),contextWindow:(\w+),'
        r'onCompact:(\w+),buttonClassName:(\w+)\}\)', src)
    if not msig:
        return {"found": False, "reason": "IXe 签名未命中"}
    e_var, t_var = msig.group(1), msig.group(2)
    # 幂等：M/K 态（popup 含 toFixed(1).replace + "% remaining"）
    if 'toFixed(1).replace' in src and '"% remaining"' in src:
        return {"found": True, "old": "toFixed(1).replace", "new": "toFixed(1).replace",
                "no_change": True, "reason": "popup M/K 已应用（toFixed(1).replace 命中，幂等）"}
    # 官方态：popup 文本 [Math.round(<c>),"% of context remaining until auto-compact."]
    pat = re.compile(r'\[Math\.round\((\w+)\),"% of context remaining until auto-compact\."\]')
    m = pat.search(src)
    if not m:
        return {"found": False, "reason": "popup remaining 文本未命中（非 M/K 态也非官方态）"}
    c_var = m.group(1)
    old = m.group(0)
    # M/K 格式化：>=1e6 用 M、>=1e3 用 K（去尾 .0），<1k 原数
    def _mk(v):
        return ('(' + v + '>=1e6?(' + v + '/1e6).toFixed(1).replace(/\\.0$/,"")+"M":'
                + v + '>=1e3?(' + v + '/1e3).toFixed(1).replace(/\\.0$/,"")+"K":""+Math.round(' + v + '))')
    # 文本：已用(M/K) / 总量(M/K) tokens · X% remaining
    new = ('[' + _mk(e_var) + '," / ",' + _mk(t_var) +
           '," tokens  ·  ",Math.round(' + c_var + '),"% remaining"]')
    return {"found": True, "old": old, "new": new, "hit_count": src.count(old),
            "reason": "used=" + e_var + " ctx=" + t_var + " remain=" + c_var + " fmt=M/K"}
```

#### 设计说明

定位器先从 `IXe` 签名提取 `usedTokens`(`e`) 和 `contextWindow`(`t`) 别名，再定位 popup 的 `[Math.round(<c>),"% of context remaining until auto-compact."]`，替换为 M/K 格式化版 `[<e 的 M/K>," / ",<t 的 M/K>," tokens  ·  ",Math.round(c),"% remaining"]`。`_mk(v)`：`v>=1e6` 用 M、`v>=1e3` 用 K（`toFixed(1)` 去尾 `.0`），否则原数。

效果：原 "82% of context remaining until auto-compact." → "13K / 1M tokens  ·  82% remaining"。

`t` 是 `IXe` 收到的 contextWindow（005 补丁写死为 .env 的 CONTEXT_WINDOW，当前 1000000 → 显示 1M）。占比计算仍用原始数字（`usedTokens / contextWindow`），M/K 仅影响显示。

#### verify

- `old` 命中 1 次
- 替换后 `toFixed(1).replace`（M/K 格式化）出现
- `node --check` 通过

### 失败处理

- **IXe 签名未命中**：组件重构 → broken。
- **popup 文本未命中**：文案改写 → broken，搜 `context remaining` 重新定位。

## 跨版本移植性

- **大概率免人工**：常规构建（`b`/`l`/`e`/`t`/`c` 别名变化）——定位器动态捕获。
- **可能 broken**：上游重构 IXe 渲染结构、改 popup 文案、或换饼图实现——按 fallback 重定位。

## 已验证版本

- `2.1.201`：已应用（改动2 popup 从 toLocaleString 改为 M/K 格式化，配合 005 写死的 contextWindow=1000000，显示 `0 / 1M tokens · 100% remaining`）。
