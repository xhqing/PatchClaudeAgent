---
id: 005-context-window-from-env
title: 用量条总量写死为 .env 的 CONTEXT_WINDOW
target: webview/index.js
default_status: needs-reapply
---

# 005 用量条总量写死为 .env 的 CONTEXT_WINDOW

proxy 模式下 native-binary（CLI）丢弃 API 响应里的 `modelUsage`（非 Anthropic 标准字段），webview 的 `usageData.contextWindow` 恒为 0，官方表达式 `contextWindow - maxOutputTokens - 13000` 会算出负数（0 − 0 − 13000 = −13000）。

本补丁把 IXe 调用处的 `contextWindow` 直接写死为一个值——**该值在重打补丁时从 `~/.claude-proxy/.env` 的 `CONTEXT_WINDOW`（pair #1，无后缀）读取**。改 .env + 重打补丁，webview 的总量跟着变（native-binary 运行时不透传 modelUsage，只能 patch 期同步，这是 2.1.201 的硬限制）。

当前所有 pair 均为 1000000（1M）。若以后不同模型配不同 `CONTEXT_WINDOW_n`，需升级为按 `currentMainLoopModel` 查表（见 git 历史里删除的旧 005-context-window-override）。

## 改动 1：contextWindow 写死为 .env 的 CONTEXT_WINDOW

### file: webview/index.js
### type: locate

### locator:
```python
def locate(src):
    import re, os
    # 读 ~/.claude-proxy/.env 的 CONTEXT_WINDOW（pair #1，无 _n 后缀）
    env_path = os.path.expanduser('~/.claude-proxy/.env')
    cw = 1000000
    if os.path.exists(env_path):
        for line in open(env_path, encoding='utf-8'):
            line = line.strip()
            if line.startswith('CONTEXT_WINDOW=') and not line.startswith('CONTEXT_WINDOW_'):
                try:
                    cw = int(line.split('=', 1)[1].strip().strip('"').strip("'"))
                except Exception:
                    pass
                break
    # 分支 1：已写死态（IXe 调用处 contextWindow:<数字>,onCompact）——支持改 .env 后重打更新值
    m_fixed = re.search(r'contextWindow:(\d+),onCompact', src)
    if m_fixed:
        old = m_fixed.group(0)
        if int(m_fixed.group(1)) == cw:
            return {"found": True, "old": old, "new": old, "no_change": True,
                    "reason": f"已写死 contextWindow={cw}（幂等）"}
        return {"found": True, "old": old, "new": f"contextWindow:{cw},onCompact",
                "hit_count": 1,
                "reason": f"更新写死值 {m_fixed.group(1)} → {cw}（from .env）"}
    # 分支 2：官方态（contextWindow:<e>.usageData.value.contextWindow-<e>.usageData.value.maxOutputTokens-<N>）
    pat = re.compile(
        r'contextWindow:([a-zA-Z_$][\w$]*)\.usageData\.value\.contextWindow-'
        r'\1\.usageData\.value\.maxOutputTokens-(\d+)')
    cand = list(pat.finditer(src))
    if len(cand) == 1:
        m = cand[0]
        return {"found": True, "old": m.group(0), "new": f"contextWindow:{cw}",
                "hit_count": 1,
                "reason": f"session={m.group(1)} margin={m.group(2)} → 写死 contextWindow={cw}（from .env）"}
    return {"found": False, "reason": f"既非写死态也非官方态（官方命中 {len(cand)}）"}
```

#### 设计说明

定位器双分支：

- **分支 1（已写死态）**：匹配 IXe 调用处的 `contextWindow:<数字>,onCompact`（`,onCompact` 消歧，避开 usageData 初始化的 `contextWindow:0`）。若当前值已等于 .env 的 `CONTEXT_WINDOW` → 幂等 `no_change`；否则更新为新值。**这一分支让"改 .env + 重打"能真正更新 webview 的写死值**（否则 webview 已是旧写死值、官方表达式不在，单分支定位器会 broken）。
- **分支 2（官方态）**：匹配官方 `contextWindow:<e>.usageData.value.contextWindow-<e>.usageData.value.maxOutputTokens-<N>`（`\1` 保证 session 别名一致），首次应用或扩展更新后走这条。

`cw` 重打时从 `~/.claude-proxy/.env` 的 `CONTEXT_WINDOW` 读（pair #1，排除 `CONTEXT_WINDOW_n` 后缀变体）。写死时不减 maxOutput、不减 13000 预留，总量直接显示配置值（占比 = usedTokens / cw）。

#### verify

- locator `found=True`
- 写死态：`contextWindow:<cw>,onCompact` 出现
- 官方态：原 `usageData.value.contextWindow-...maxOutputTokens-...` 消失，`contextWindow:<cw>` 出现
- `node --check` 通过

### 失败处理

- **两分支都不命中**：上游改了 IXe 调用结构 → broken，搜 `contextWindow:` 在含 `usedTokens`/`onCompact` 的调用处重定位。

## 已验证版本

- `2.1.201`：已应用（撤回旧模型表后，改为从 .env 读 CONTEXT_WINDOW 写死；当前 .env `CONTEXT_WINDOW=1000000`）。配合 006 的 M/K 格式化，popup 显示 `0 / 1M tokens · 100% remaining`。
