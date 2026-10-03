---
id: 014-model-picker-glm-names
title: 模型选择器与指示器显示 GLM 真名（v2；v3 已回滚待查）
targets: [webview/index.js]
default_status: needs-reapply
---

# 014 模型选择器与指示器显示 GLM 真名（v2）

CC VSCE 经 cc-bridge（GLM 桥）上游时，`MODEL_MAP` 把 Claude 模型名改写为 GLM 模型名（如 `claude-opus-4-8->glm-5.3`、`claude-opus-4-7->glm-5.3-flash`）。界面上的模型选择器（命令菜单 `Switch model…` 的指示器 + IQe 弹窗列表）仍显示 Claude 名，与实际服务的 GLM 模型语义错位。

版本演进：

- **v1**（已被取代）：只改写 `displayName`，两个漏洞——opus 别名项不映射、description 误导字样残留。
- **v2**（当前生效）：2026-08-30 修 v1 两漏洞——补家族别名（opus/sonnet/haiku）映射，displayName + description 一起改写，换新哨兵 `ccGlmMap2` + 新函数名 `ccGlm2`/`ccGlmM2`。
- **v3**（**2026-09-04 晚间已回滚，根因待查**）：尝试「新哨兵 `ccGlmMap3` + 重声明同名函数 `ccGlm2`/`ccGlmM2` 覆盖 v2 实现」，内容为补 `claude-opus-4-6→deepseek-v4-flash` 映射 + filter 隐藏 Default 项 + description 模板改 `cc-bridge · <名>`。应用后 webview 白屏（面板完全不显示，扩展宿主正常、无 console 报错日志），回滚 v3 块后恢复。**教训：v1→v2 换函数名的「新名字」模式经线上验证安全；v3 的「同名重声明覆盖」模式在 webview 环境炸（具体炸点未定位，静态分析无明显 Syntax/运行时问题，`node --check` 通过、行为级单测通过）——该模式禁止再用，v3 需求（4-6 映射 + 隐藏 Default）日后按 v2 模式重做：新哨兵 `ccGlmMap3` + 新函数名 `ccGlm3`/`ccGlmM3`，014 改动 2/3 与 015 的锚、调用点同步升级**。

v2 对策（全部显示层，选择逻辑零改动）：

- **映射表补家族别名**：`opus→glm-5.3`、`sonnet→glm-4.7`、`haiku→glm-4.6`（按本机 `ANTHROPIC_DEFAULT_OPUS_MODEL=claude-opus-4-8` 等默认指向对齐）；前缀匹配天然覆盖 `opus[1m]` / `sonnet[1m]` 变体。
- **ccGlmM2 同时改写 displayName + description**：命中映射的项 description 统一改为 `"GLM (cc-bridge) · <glm 名>"`，清掉 Opus 误导字样；未映射项（fable / default 等）原样。
- **换新哨兵 `ccGlmMap2` + 新函数名 `ccGlm2` / `ccGlmM2`**：append 块内容变了必须换新哨兵引擎才重新追加（v1 块留在文件尾部被 v2 声明覆盖，函数声明后者胜出，无害——同 008 演进模式）。

## 改动 1：webview/index.js 末尾追加映射表与辅助函数（v2）

### file: webview/index.js
### type: append
### idempotent: ccGlmMap2

```javascript
// === patch-claude 014 v2: 模型选择器显示 GLM 真名（ccGlm 桥映射显示层）勿删 ===
var ccGlmMap2 = {
  "claude-opus-4-8": "glm-5.3",
  "claude-opus-4-7": "glm-5.3-flash",
  "claude-haiku-4-5": "glm-4.6",
  "claude-sonnet-5": "glm-4.7",
  "opus": "glm-5.3",
  "sonnet": "glm-4.7",
  "haiku": "glm-4.6",
};
function ccGlm2(modelValue) {
  if (!modelValue || modelValue === "default") return undefined;
  var hit;
  for (var k in ccGlmMap2) {
    if (modelValue === k || modelValue.indexOf(k) === 0) { hit = ccGlmMap2[k]; break; }
  }
  return hit;
}
function ccGlmM2(list) {
  if (!Array.isArray(list)) return list;
  return list.map(function (m) {
    var g = ccGlm2(m && m.value);
    if (!g) return m;
    return Object.assign({}, m, { displayName: g, description: "GLM (cc-bridge) · " + g });
  });
}
// === end patch-claude 014 v2 ===
```

#### 设计说明

- `ccGlm2(v)`：模型选择值 → GLM 真名；未映射 / default 返回 `undefined`（调用方 `??` 回退官方显示）。前缀匹配兜底 `claude-opus-4-8[1m]` / `opus[1m]` 带后缀变体。家族别名（opus/sonnet/haiku）与全名并列——注意前缀匹配方向是 `modelValue.indexOf(k)===0`（值以键开头），`claude-opus-4-8` 不会误命中 `opus` 键。
- `ccGlmM2(list)`：模型列表浅拷贝改写，命中项 `displayName`=GLM 真名、`description`=统一 GLM 简述（覆盖 binary 模板的 Opus 字样）；未映射项原样返回。
- `idempotent: ccGlmMap2`——v2 变量名是本块独有稳定串。**若日后改映射内容，需换新哨兵（如 `ccGlmMap3`）与映射一起更新**；v1 的 `ccGlmMap`/`ccGlm`/`ccGlmM` 块保留无害（不再被引用）。
- **勿用「同名重声明覆盖」升级**（2026-09-04 v3 事故教训）：v3 曾以新哨兵 + 重声明同名 `ccGlm2`/`ccGlmM2` 的方式升级，应用后 webview 白屏，回滚恢复。升级一律走「新函数名」模式（`ccGlm3`/`ccGlmM3`），调用点（本补丁改动 2/3、015 改动 4）同步升级。

#### verify

- 追加后 `ccGlmMap2` 在文件中出现、结尾标记 `end patch-claude 014 v2` 存在
- `node --check` 通过

#### 失败处理

`ccGlmMap2` 已存在则跳过（幂等）。

## 改动 2：命令菜单 Switch model 指示器调用升级为 ccGlm2

### file: webview/index.js
### type: locate
### idempotent: =ccGlm2(ae)??xbe

### locator:
```python
def locate(src):
    # 态 A：v2 已在（幂等）——动态符号版 v2 调用已存在
    if re.search(r'[A-Za-z_$][\w$]*=ccGlm2\([A-Za-z_$][\w$]*\)\?\?', src):
        return {"found": True, "old": "", "new": "", "no_change": True}
    # 态 B：v1 升级——ht=ccGlm(ae)??xbe(ae, → ccGlm2
    m1 = re.search(r'([A-Za-z_$][\w$]*)=ccGlm\(([A-Za-z_$][\w$]*)\)\?\?([A-Za-z_$][\w$]*)\(\2,', src)
    if m1:
        old = m1.group(0)
        new = (m1.group(1) + '=ccGlm2(' + m1.group(2) + ')??' + m1.group(3)
               + '(' + m1.group(2) + ',')
        return {"found": True, "old": old, "new": new, "hit_count": src.count(old)}
    # 态 C：fresh——原始形态（v1 改动2 的锚链），直接注入 ccGlm2 版
    if 'id:"model",label:"Switch model' not in src:
        return {"found": False, "reason": "Switch model 菜单动作锚点消失"}
    if "lastServedModel.value" not in src:
        return {"found": False, "reason": "lastServedModel 信号消失"}
    pat = re.compile(
        r'([a-zA-Z_$][\w$]*)=([a-zA-Z_$][\w$]*)\(([a-zA-Z_$][\w$]*),'
        r'([a-zA-Z_$][\w$]*)\.lastServedModel\.value,([a-zA-Z_$][\w$]*)\);'
        r'([a-zA-Z_$][\w$]*)\.commandRegistry\.registerAction\(\{id:"model"'
    )
    m = pat.search(src)
    if not m:
        return {"found": False, "reason": "未匹配到指示器赋值+registerAction(id:model) 链"}
    ht, fn, a1, obj, a3 = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
    old = (ht + '=' + fn + '(' + a1 + ',' + obj + '.lastServedModel.value,' + a3 + ');')
    new = (ht + '=ccGlm2(' + a1 + ')??' + fn + '(' + a1 + ',' + obj
           + '.lastServedModel.value,' + a3 + ');')
    return {"found": True, "old": old, "new": new, "hit_count": src.count(old)}
```

#### 设计说明

原始代码 `ht=xbe(ae,t.lastServedModel.value,je)` 渲染进命令菜单 `Switch model…` 行尾指示器。三态定位器：v2 已在 → no_change（引擎判 verified）；v1 态 → 只把 `ccGlm` 换 `ccGlm2`（动态符号，`\2` 反向引用锁同一实参）；fresh → 按原始锚链注入 `ccGlm2(...)??` 前缀。**只改显示，不改选择逻辑**。

#### verify

- 定位器 found=True（no_change 或 hit_count==1）
- `node --check` 通过

#### 失败处理

- 三态都不命中 → broken，按 `id:"model"` 前 400 字窗口重新定位指示器赋值。

## 改动 3：IQe 弹窗列表项调用升级为 ccGlmM2（displayName + description 改写）

### file: webview/index.js
### type: locate
### idempotent: availableModels:ccGlmM2(

### locator:
```python
def locate(src):
    # 态 A：v2 已在（幂等）
    if "availableModels:ccGlmM2(" in src:
        return {"found": True, "old": "", "new": "", "no_change": True}
    # 态 B：v1 升级——ccGlmM( → ccGlmM2(
    pat1 = re.compile(
        r'availableModels:ccGlmM\(([A-Za-z_$][\w$]*)\.claudeConfig\.value\?\.models\),'
        r'unavailableModels:ccGlmM\(\1\.claudeConfig\.value\?\.unavailable_models\),')
    c = list(pat1.finditer(src))
    if len(c) == 1:
        t = c[0].group(1)
        old = c[0].group(0)
        new = ('availableModels:ccGlmM2(' + t + '.claudeConfig.value?.models),'
               'unavailableModels:ccGlmM2(' + t + '.claudeConfig.value?.unavailable_models),')
        return {"found": True, "old": old, "new": new, "hit_count": 1}
    # 态 C：fresh——原始 props 形态
    if "function IQe(" not in src:
        return {"found": False, "reason": "模型选择弹窗组件 IQe 消失"}
    patf = re.compile(
        r'availableModels:([A-Za-z_$][\w$]*)\.claudeConfig\.value\?\.models,'
        r'unavailableModels:\1\.claudeConfig\.value\?\.unavailable_models,currentModel:')
    cf = list(patf.finditer(src))
    if len(cf) != 1:
        return {"found": False, "reason": "IQe props 锚点命中 %d 次（!=1）" % len(cf)}
    t = cf[0].group(1)
    old = ('availableModels:' + t + '.claudeConfig.value?.models,'
           'unavailableModels:' + t + '.claudeConfig.value?.unavailable_models,')
    new = ('availableModels:ccGlmM2(' + t + '.claudeConfig.value?.models),'
           'unavailableModels:ccGlmM2(' + t + '.claudeConfig.value?.unavailable_models),')
    return {"found": True, "old": old, "new": new, "hit_count": src.count(old)}
```

#### 设计说明

IQe 渲染处把 `claudeConfig` 的模型表传给 `availableModels` / `unavailableModels`；列表项渲染 `h.displayName` 与 `h.description`（`LQe(h)`）。包 `ccGlmM2()` 后命中项两项一起变 GLM 名——用户在弹窗里看到「glm-5.3-flash + GLM (cc-bridge) · glm-5.3-flash」，不再有 Opus 字样。`h.value` 仍是官方 id、setModel 写 settings.json 不变（纯显示层）。

三态定位器同改动 2：v2 已在 → no_change；v1 态 → 函数名升级（`\1` 反向引用锁同一 session）；fresh → 原始 props 直接包 ccGlmM2。

#### verify

- 定位器 found=True（no_change 或 hit_count==1）；替换后 `availableModels:ccGlmM2(` 出现
- `node --check` 通过

#### 失败处理

- `function IQe(` 消失且三态都不命中 → broken，按 `modelList` / `Select a model` 文案重定位。

## 维护备忘

- 桥侧 `~/.cc-bridge/glm.env` 的 MODEL_MAP 变更后：更新改动 1 的 ccGlmMap2 + **换新哨兵**（如 `ccGlmMap3`）+ **换新函数名**（`ccGlm3`/`ccGlmM3`，勿用同名重声明——见 v3 事故）+ 同步升级改动 2/3 与 015 的调用点 + 重打补丁。
- **待办需求（v3 遗留，待按新函数名模式重做）**：① `claude-opus-4-6` 显示为 `deepseek-v4-flash`（本机 settings.json availableModels 含此项，v2 表无此键故原样显示「Opus 4.6」）；② 弹窗列表隐藏 Default 项（binary `oSo()` 构造、`lJe()` 转 `value:"default"`，在 ccGlmM 后继版本里 filter 掉）。
- 家族别名（opus/sonnet/haiku）映射的是**本机 env 默认指向**（`ANTHROPIC_DEFAULT_OPUS_MODEL=claude-opus-4-8` 等）；若 env 默认指向换型号，别名目标要跟着改。
- v1 块（`ccGlmMap`/`ccGlm`/`ccGlmM`）与 v1 调用点残留会被本补丁改动 2/3 原位升级；若文件里仍有 `=ccGlm(` / `availableModels:ccGlmM(` 残留说明升级未完成，重跑引擎即可。
- 本补丁纯显示层、不动 extension.js 主进程——settings.json 写入的仍是官方模型 id。

## 已验证版本

- `2.1.226`：v2 verified（2026-08-30 应用并线上验证；2026-09-04 晚 v3 事故后回滚回 v2 状态，字符数 4832515 与 v2 完全一致、`node --check` 通过）。
- `2.1.226`：v3（2026-09-04 应用后 webview 白屏，**当晚回滚作废**——同名重声明覆盖模式在 webview 环境炸，具体炸点未定位；v3 需求见维护备忘「待办需求」）。
- `2.1.226`：v1（2026-08-30 上午，已被 v2 取代；v1 缺别名与 description 改写）。
