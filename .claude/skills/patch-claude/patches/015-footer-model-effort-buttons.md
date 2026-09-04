---
id: 015-footer-model-effort-buttons
title: 输入框 footer 常驻模型与 Effort 按钮（v2：各自独立弹窗直选）
targets: [webview/index.js]
default_status: needs-reapply
---

# 015 输入框 footer 常驻模型与 Effort 按钮（v2：各自独立弹窗直选）

当前模型名与 Effort 档位藏在命令菜单（`Switch model…` / `Effort (Max)`）里，要看当前值、切一次都要开菜单。本补丁在输入框 footer（命令菜单按钮与用量按钮之间）注入两个常驻按钮，**各自弹出独立列表、点击即选中**：

- **模型按钮**：实时显示当前模型的 GLM 真名（依赖补丁 014 v2 的 `ccGlm2`，未映射显示官方名），**点击打开官方模型选择弹窗**（IQe，含全部候选、勾选态、014 v2 的 GLM 名显示）；
- **Effort 按钮**：实时显示当前档位，**点击弹出独立的 Effort 档位列表**（自建弹窗，复用官方 menuPopup 样式与勾选图标），列表项点击即 `setEffortLevel` 选中并收起。

v1 的两处缺陷（2026-08-30 用户报告）：① 模型按钮的 `ccOpenMdl` 回调提取到了**命令面板**（qXe）的 setter 而非模型弹窗（IQe）的——v1 定位器取「渲染点之前第一个 `isOpen:` 状态」，实际第一个是命令面板；② Effort 按钮只能循环切下一档、无列表直选。v2 对策：

- **setter 锚定修正**：模型弹窗渲染点用 014 v2 注入的 `availableModels:ccGlmM2(` 锚定（产品级唯一锚），setter 从**渲染点之前**最近一次 `[Z,z]=ie(!1)` 定义提取；
- **Effort 独立弹窗**：新增 `[ccEffOpen,ccEffSet]=ie(!1)` 状态（挂在响应式包裹组件 OQe 体内），footer 按钮 toggle 它；弹窗 JSX 用官方 CSS 模块的 `menuPopup`/`menuHeader`/`menuItemV2`/`menuItemSelected`/`menuItemCheckRight` 类名，视觉与官方弹窗一致；
- **三态兼容定位器**：每块定位器按「v2 已在（no_change）→ v1 态升级 → fresh 注入」三段判定，v1 机器原地升级、新机器一次到位，同一补丁文件通吃。

实时性机制（与 v1 相同）：footer 组件 `bQe` 的渲染点位于响应式包裹组件（`ti(...)` 包装、下称 OQe）体内；两按钮的当前值在 **OQe 渲染时**以 IIFE 算好、作为 `ccMdl` / `ccEff` props 传入——IIFE 里读的 `.value` 落在 OQe 的响应式渲染作用域内被追踪（与 footer 右侧「Auto」模式按钮同机制），任一变化 → OQe 重渲染 → 按钮文字实时刷新。

**依赖补丁 014 v2**（`ccGlm2` / `ccGlmM2` 定义与调用点）。014 未应用时改动 1 定位器返回 found=False（broken），属预期依赖检查。

## 改动 1：OQe 体内四连 useState 后追加 Effort 弹窗状态

### file: webview/index.js
### type: locate
### idempotent: ,[ccEffOpen,ccEffSet]=ie(!1)

### locator:
```python
def locate(src):
    if "ccGlmMap2" not in src:
        return {"found": False, "reason": "补丁 014 v2 未应用（ccGlmMap2 缺失）——先应用 014"}
    # 四连 useState（OQe 体内的弹窗/面板状态群）：校验其后 30000 字内出现
    # 014 v2 注入的 IQe 渲染锚，锁定是 OQe 而非全文第一个四连。
    for m in re.finditer(r'\[[A-Za-z_$][\w$]*,[A-Za-z_$][\w$]*\]=ie\(!1\),\[[A-Za-z_$][\w$]*,[A-Za-z_$][\w$]*\]=ie\(!1\),\[[A-Za-z_$][\w$]*,[A-Za-z_$][\w$]*\]=ie\(!1\),\[[A-Za-z_$][\w$]*,[A-Za-z_$][\w$]*\]=ie\(!1\)', src):
        if 'availableModels:ccGlmM2(' in src[m.start():m.start()+30000]:
            return {"found": True, "old": m.group(0),
                    "new": m.group(0) + ',[ccEffOpen,ccEffSet]=ie(!1)',
                    "hit_count": src.count(m.group(0))}
    return {"found": False, "reason": "未找到 OQe 四连 useState"}
```

#### 设计说明

OQe 体内四连 `ie(!1)` 状态（`[k,D]`/`[R,N]`/`[V,G]`/`[Z,z]`）之后追加 Effort 弹窗开关状态。全文件多处四连 `ie(!1)`，用「后 30000 字内含 IQe 渲染锚」锁定 OQe 的那一组（IQe 渲染点在 OQe 体内、位于状态声明之后）。

#### verify

- 定位器 found=True 且 hit_count==1
- `node --check` 通过

#### 失败处理

- 014 v2 未应用 → broken（依赖检查）。
- 四连 useState 结构变化 → broken，按 IQe 渲染点向前重定位状态声明群。

## 改动 2：OQe 渲染点向 footer 传 ccOpenMdl（修正 setter）与 ccEffSet

### file: webview/index.js
### type: locate
### idempotent: ccEffSet,session:

### locator:
```python
def locate(src):
    # 模型弹窗渲染点：014 v2 注入的 ccGlmM2( 是产品级唯一锚
    m = re.search(r'b\([A-Za-z_$][\w$]*,\{isOpen:([A-Za-z_$][\w$]*),onClose:[A-Za-z_$][\w$]*,availableModels:ccGlmM2\(', src)
    if not m:
        return {"found": False, "reason": "IQe 渲染点（ccGlmM2 形态）未找到——014 v2 改动 3 先应用"}
    zst = m.group(1)
    mset = None
    for cand in re.finditer(r'\[' + re.escape(zst) + r',([A-Za-z_$][\w$]*)\]=ie\(!1\)', src[:m.start()+200]):
        mset = cand
    if not mset:
        return {"found": False, "reason": "弹窗 setter 提取失败（渲染点前无定义）"}
    zset = mset.group(1)
    # 态 A：v2d 已在（toggle 形态，幂等，双保险——引擎先查静态标记）
    if re.search(r'ccOpenMdl:\(\)=>\{' + re.escape(zset) + r'\(' + re.escape(zst) + r'!==!0\)\},ccEffSet,session:', src):
        return {"found": True, "old": "", "new": "", "no_change": True}
    # 态 B：v1 升级——v1 的 ccOpenMdl 用了错误 setter（命令面板的），修正为 zset、
    # 直接生成 toggle 形态并追加 ccEffSet（v2 只开形态由改动 2d 负责升级）
    mopen = re.search(r'ccOpenMdl:\(\)=>\{([A-Za-z_$][\w$]*)\(!0\)\},session:', src)
    if mopen:
        old = 'ccOpenMdl:()=>{' + mopen.group(1) + '(!0)},session:'
        new = 'ccOpenMdl:()=>{' + zset + '(' + zst + '!==!0)},ccEffSet,session:'
        return {"found": True, "old": old, "new": new, "hit_count": src.count(old)}
    # 态 C：fresh——footer 渲染点注入完整 props（ccMdl / ccEff{cur,lv} / ccOpenMdl / ccEffSet）
    mmenu = re.search(r'title:"Show command menu \(/\)"', src)
    if not mmenu:
        return {"found": False, "reason": "命令菜单按钮锚点消失"}
    fpos = src.rfind("function ", 0, mmenu.start())
    mfn = re.compile(r'function ([A-Za-z_$][\w$]*)\(\{session:').match(src, fpos)
    if not mfn:
        return {"found": False, "reason": "footer 组件签名不匹配"}
    foot = mfn.group(1)
    old0 = 'b(' + foot + ',{session:'
    if src.count(old0) != 1:
        return {"found": False, "reason": "footer 渲染点命中 %d 次（!=1）" % src.count(old0)}
    rpos = src.find(old0)
    cands = list(re.finditer(r'function\s*(?:([A-Za-z_$][\w$]*)\s*)?\(\{session:([A-Za-z_$][\w$]*)', src[:rpos]))
    if not cands:
        return {"found": False, "reason": "未找到包裹组件（OQe）签名"}
    T = cands[-1].group(2)
    mo5 = re.search(r'function ([A-Za-z_$][\w$]*)\((\w+)\)\{return \2\?(\w+)\[\2\]\?\?"Auto":"Auto"\}', src)
    if not mo5:
        return {"found": False, "reason": "O5 effort 显示函数锚点消失"}
    o5 = mo5.group(1)
    cc_mdl = ('ccMdl:(()=>{let ms=' + T + '.modelSelection.value;'
              'return ccGlm2(ms)??(' + T + '.claudeConfig.value?.models??[])'
              '.find((ccm)=>ccm.value===ms)?.displayName??"default"})(),')
    cc_eff = ('ccEff:(()=>{let mo=(' + T + '.claudeConfig.value?.models??[])'
              '.find((ccm)=>ccm.value===' + T + '.modelSelection.value);'
              'if(!(mo&&mo.supportsEffort))return null;'
              'let lv=mo.supportedEffortLevels??["low","medium","high"],cu=' + T + '.effortLevel.value;'
              'return{cur:' + o5 + '(cu),lv:lv}})(),')
    new = ('b(' + foot + ',{' + cc_mdl + cc_eff
           + 'ccOpenMdl:()=>{' + zset + '(' + zst + '!==!0)},ccEffOpen,ccEffSet,session:')
    return {"found": True, "old": old0, "new": new, "hit_count": 1}
```

#### 设计说明

- **v1 缺陷修复**：v1 取「渲染点之前第一个 `isOpen:` 状态」实际命中命令面板（qXe，`isOpen:R`/`N`）。v2 用 `availableModels:ccGlmM2(` 直接锚定 IQe 渲染点（该串由 014 v2 改动 3 注入、全文唯一），setter 取**渲染点之前**最近一次 `[zst,X]=ie(!1)` 定义（IQe 渲染在 OQe 体内，其状态声明必在渲染点之前）。
- `ccEff` props 在 fresh 态直接生成 `{cur,lv}` 形态（弹窗需要完整档位列表，不再是 v1 的 `{cur,next}`）；`lv` 回退 `["low","medium","high"]` 兜底。
- `ccMdl&&` / `ccEff&&` 守卫在改动 4 的 JSX 侧，不支持 effort 的模型不渲染 Effort 按钮。

#### verify

- 定位器 found=True（no_change 或 hit_count==1）
- `node --check` 通过

#### 失败处理

- IQe 渲染锚消失 → broken，按 `function IQe(` 重定位渲染点。
- fresh 态 footer 渲染点命中 ≠1 → broken，按 `Show command menu (/)` 重定位。

## 改动 2b：ccEff props 升级为 lv 形态（v1 机器专用）

### file: webview/index.js
### type: locate
### idempotent: ,lv:lv}})(),

### locator:
```python
def locate(src):
    mo5 = re.search(r'function ([A-Za-z_$][\w$]*)\((\w+)\)\{return \2\?(\w+)\[\2\]\?\?"Auto":"Auto"\}', src)
    if not mo5:
        return {"found": False, "reason": "O5 effort 显示函数锚点消失"}
    o5 = mo5.group(1)
    v2sig = 'return{cur:' + o5 + '(cu),lv:lv}'
    # 态 A：v2 已在（fresh 态改动 2 直接生成 lv 形态，也落到这里）
    if v2sig in src:
        return {"found": True, "old": "", "new": "", "no_change": True}
    # 态 B：v1 的 {cur,next} 形态 → {cur,lv}
    old = 'return{cur:' + o5 + '(cu),next:lv[(lv.indexOf(cu)+1)%lv.length]??lv[0]}'
    if old in src:
        return {"found": True, "old": old, "new": v2sig, "hit_count": src.count(old)}
    return {"found": False, "reason": "ccEff props 非 v1 形态且 v2 形态不在（结构变化）"}
```

#### 设计说明

v1 的 `ccEff` 是 `{cur,next}`（循环切档用），v2 弹窗需要完整档位数组。本块把 v1 形态原地升级；fresh 机器改动 2 已直接生成 lv 形态，本块定位器判 no_change 跳过。幂等标记用静态串 `,lv:lv}})(),`（不含混淆符号，v1/fresh 态均不存在、v2 态唯一）。

#### verify

- 定位器 found=True（no_change 或 hit_count==1）
- `node --check` 通过

## 改动 2c：ccMdl 调用升级为 ccGlm2（v1 残留机器专用）

### file: webview/index.js
### type: locate
### idempotent: return ccGlm2(

### locator:
```python
def locate(src):
    if "ccGlmMap2" not in src:
        return {"found": False, "reason": "补丁 014 v2 未应用（ccGlmMap2 缺失）——先应用 014"}
    # 态 A：v2 已在（fresh 态改动 2 直接生成 ccGlm2 版）
    if "return ccGlm2(" in src:
        return {"found": True, "old": "", "new": "", "no_change": True}
    # 态 B：v1 残留——ccMdl IIFE 里调的还是 v1 的 ccGlm（无家族别名映射，
    # 选 opus 别名项时查表不中、回退官方 displayName），升级为 ccGlm2
    old = "return ccGlm(ms)??("
    if old in src:
        return {"found": True, "old": old, "new": "return ccGlm2(ms)??(", "hit_count": src.count(old)}
    return {"found": False, "reason": "ccMdl 调用形态异常（非 v1 残留也非 v2）"}
```

#### 设计说明

v1 机器升级 v2 时，改动 2 的 v1 路径只修正 setter（N→z）并追加 `ccEffSet`，不动 v1 已注入的 `ccMdl` IIFE——里面的 `ccGlm(ms)` 是 v1 函数（映射表无 `opus`/`sonnet`/`haiku` 别名键），选 `"opus"` 别名项时查表不中，footer 按钮回退显示官方 displayName（即 ANTHROPIC_DEFAULT_OPUS_MODEL 的原始 id，如 `claude-opus-4-8`），而模型列表因走 `ccGlmM2` 正常显示 GLM 名——两边不一致（2026-08-30 用户报告）。本块把这个残留调用升级为 `ccGlm2`。`ms` 是本补丁注入代码的自有变量名（非混淆符号，跨版本稳定）；`return ccGlm(ms)??(` 在 v1 注入物中唯一（v1 的 `ccGlmM` 内部调用形态是 `ccGlm(m && m.value)`、014 的指示器调用已被 014 v2 改动 2 升级，均不冲突）。

#### verify

- 定位器 found=True（no_change 或 hit_count==1）
- `node --check` 通过

#### 失败处理

- 两态都不命中 → broken，按 `ccMdl:(()=>{let` 前缀重定位调用形态。

## 改动 2d：ccOpenMdl 升级为 toggle（弹窗开着再点按钮收回）

### file: webview/index.js
### type: locate
### idempotent: ccOpenMdl:()=>{z(Z!==!0)}

### locator:
```python
def locate(src):
    # 模型弹窗渲染点与状态符号（同改动 2 的锚）
    m = re.search(r'b\([A-Za-z_$][\w$]*,\{isOpen:([A-Za-z_$][\w$]*),onClose:[A-Za-z_$][\w$]*,availableModels:ccGlmM2\(', src)
    if not m:
        return {"found": False, "reason": "IQe 渲染点（ccGlmM2 形态）未找到——014 v2 改动 3 先应用"}
    zst = m.group(1)
    mset = None
    for cand in re.finditer(r'\[' + re.escape(zst) + r',([A-Za-z_$][\w$]*)\]=ie\(!1\)', src[:m.start()+200]):
        mset = cand
    if not mset:
        return {"found": False, "reason": "弹窗 setter 提取失败（渲染点前无定义）"}
    zset = mset.group(1)
    # 态 A：v2d 已在（toggle 形态，幂等）
    sig = 'ccOpenMdl:()=>{' + zset + '(' + zst + '!==!0)}'
    if sig in src:
        return {"found": True, "old": "", "new": "", "no_change": True}
    # 态 B：v2 的只开形态（z(!0)）→ toggle
    old = 'ccOpenMdl:()=>{' + zset + '(!0)},ccEffSet,session:'
    if old in src:
        return {"found": True, "old": old, "new": sig + ',ccEffSet,session:', "hit_count": src.count(old)}
    # 态 C：v1 形态（错误 setter N + 只开）→ 一步到位 toggle + ccEffSet
    mopen = re.search(r'ccOpenMdl:\(\)=>\{([A-Za-z_$][\w$]*)\(!0\)\},session:', src)
    if mopen:
        old = 'ccOpenMdl:()=>{' + mopen.group(1) + '(!0)},session:'
        return {"found": True, "old": old, "new": sig + ',ccEffSet,session:', "hit_count": src.count(old)}
    return {"found": False, "reason": "ccOpenMdl 形态异常（非 v2 只开也非 v1）"}
```

#### 设计说明

**为什么 toggle**：官方关闭模型弹窗的三条路——scrim 遮罩点击（`(R||Hi||Bo||Z)&&b("div",{scrim,onClick:fr})`）、Escape、选中模型后自动 `t()`（`onClick:()=>{r(h),t()}`）——都不含「再点入口按钮」。官方入口（命令菜单 `Switch model` 行、`"Model",()=>{z(!0)}`）都是 `z(!0)` 只开不关，官方交互下没问题（菜单行点击后菜单自身先关）。但 footer 模型按钮常驻在 scrim 下层（scrim 是 `position:fixed;z-index:0` 的兄弟节点，弹窗开着时点按钮命中按钮本身、不会穿透到 scrim），`z(!0)` 在弹窗已开时是无效写——按钮就永远收不回弹窗。改为 `z(Z!==!0)`（等价 `z(!Z)`，但 `!==!0` 是压缩器不产出的自造形态、天然幂等唯一）：开→关、关→开。闭包新鲜性：`Z` 在 OQe 渲染作用域被 `IQe isOpen:Z` 读取追踪，Z 变化 → OQe 重渲染 → 新 props 闭包捕获新 Z，点击瞬间读到的是最新值。

**幂等标记**用完整形态 `ccOpenMdl:()=>{z(Z!==!0)}`（本机 2.1.226 实测：原生与打补丁后文件均 0 次、替换后 1 次）。定位器内部用动态符号（`zset`/`zst`）匹配实际形态，静态标记只是引擎快查用——若未来版本混淆名变化，定位器态 A 的动态 `sig` 查不到、引擎跑到 locator 仍能正确判 no_change。

#### verify

- 定位器 found=True（no_change 或 hit_count==1）
- `node --check` 通过

#### 失败处理

- 两态都不命中 → broken，按 `ccOpenMdl:` 前缀重定位当前形态。

## 改动 2e：props 补传 ccEffOpen（弹窗状态传入 footer 组件）

### file: webview/index.js
### type: locate
### idempotent: ,ccEffOpen,ccEffSet,session:

### locator:
```python
def locate(src):
    # 态 A：v2e 已在（幂等）
    if ",ccEffOpen,ccEffSet,session:" in src:
        return {"found": True, "old": "", "new": "", "no_change": True}
    # 态 B：v2 漏传形态——props 只有 ccEffSet 没有 ccEffOpen
    old = "ccEffSet,session:"
    if old in src:
        return {"found": True, "old": old, "new": "ccEffOpen,ccEffSet,session:", "hit_count": src.count(old)}
    return {"found": False, "reason": "props 段形态异常（无 ccEffSet）——015 未应用或结构变化"}
```

#### 设计说明

**为什么补**：改动 3 给 bQe 签名注入了 `ccEffOpen,ccEffSet` 解构，但改动 2 的 props 注入只传了 `ccEffSet`——`ccEffOpen` 从未进 props，bQe 体内它恒 `undefined`：弹窗条件 `ccEffOpen&&E(...)` 恒假、按钮 `onClick:()=>ccEffSet(!ccEffOpen)` 恒「设为开」。补传后 toggle 语义闭环（`!ccEffOpen` 开↔关）。幂等标记 `,ccEffOpen,ccEffSet,session:` 是注入后形态（原生 0 次、注入后唯一；与签名处 `,ccEffOpen,ccEffSet}){` 互不为子串）。fresh 机器上改动 2 的 fresh 态**必须同步直出本形态**（见改动 2 locator 态 C 的 `ccEffOpen,ccEffSet,session:`——若 fresh 态漏传，本块态 B 兜底补上）。

#### verify

- 定位器 found=True（no_change 或 hit_count==1）
- `node --check` 通过

#### 失败处理

- 两态都不命中 → broken，按 `ccEffSet` 在 props 段重定位。

## 改动 3：bQe 签名解构注入五个 props

### file: webview/index.js
### type: locate
### idempotent: ,ccEffOpen,ccEffSet}){

### locator:
```python
def locate(src):
    # 态 A：v2 已在（幂等）
    if ',ccEffOpen,ccEffSet}){' in src:
        return {"found": True, "old": "", "new": "", "no_change": True}
    # 态 B：v1 签名（v1 已注入 ccMdl,ccEff,ccOpenMdl）→ 追加两个
    if src.count(',ccMdl,ccEff,ccOpenMdl}){') == 1:
        return {"found": True, "old": ',ccMdl,ccEff,ccOpenMdl}){',
                "new": ',ccMdl,ccEff,ccOpenMdl,ccEffOpen,ccEffSet}){', "hit_count": 1}
    # 态 C：fresh——签名末位参数后注入完整五个
    mmenu = re.search(r'title:"Show command menu \(/\)"', src)
    if not mmenu:
        return {"found": False, "reason": "命令菜单按钮锚点消失"}
    fpos = src.rfind("function ", 0, mmenu.start())
    mfn = re.compile(r'function ([A-Za-z_$][\w$]*)\(\{session:([A-Za-z_$][\w$]*),').match(src, fpos)
    if not mfn:
        return {"found": False, "reason": "footer 组件签名不匹配"}
    body = src[mfn.start():mmenu.start()]
    mend = re.search(r'onTerminalCollaborator:([A-Za-z_$][\w$]*)\}\)\{', body)
    if not mend:
        return {"found": False, "reason": "签名末尾锚点不匹配"}
    old = 'onTerminalCollaborator:' + mend.group(1) + '}){'
    new = 'onTerminalCollaborator:' + mend.group(1) + ',ccMdl,ccEff,ccOpenMdl,ccEffOpen,ccEffSet}){'
    return {"found": True, "old": old, "new": new, "hit_count": src.count(old)}
```

#### 设计说明

`onTerminalCollaborator` 是 footer 签名（bQe）末位参数（VSCode 公开功能名，稳定锚点）。三态：v2 已在 → no_change；v1 态 → 在 `,ccMdl,ccEff,ccOpenMdl}){` 后追加（该串全文唯一且与 fresh 态锚互斥——v1 态 `onTerminalCollaborator:X}){` 已被 v1 替换掉）；fresh → 按末位参数注入完整五 props。解构后 bQe 体内可直接引用。

#### verify

- 定位器 found=True（no_change 或 hit_count==1）
- `node --check` 通过

#### 失败处理

三态都不命中 → broken，按 footer 签名结构重定位末位参数。

## 改动 4：footer JSX——模型按钮 + Effort 独立弹窗

### file: webview/index.js
### type: locate
### idempotent: title:"Select effort level"

### locator:
```python
def locate(src):
    # 态 A：v2 已在（幂等）
    if 'title:"Select effort level"' in src:
        return {"found": True, "old": "", "new": "", "no_change": True}
    mmenu = re.search(r'title:"Show command menu \(/\)"', src)
    if not mmenu:
        return {"found": False, "reason": "命令菜单按钮锚点消失"}
    fpos = src.rfind("function ", 0, mmenu.start())
    es = re.compile(r'function [A-Za-z_$][\w$]*\(\{session:([A-Za-z_$][\w$]*),').match(src, fpos).group(1)
    # 态 B：v1 Effort 按钮在 → 整体替换为 wrapper+弹窗（rd 从按钮自身提取）
    m4 = re.search(r'ccEff&&b\("button",\{type:"button",className:([A-Za-z_$][\w$]*)\.footerButton,onClick:\(\)=>\{[A-Za-z_$][\w$]*\.setEffortLevel\(ccEff\.next\)\},title:"Cycle effort level",children:b\("span",\{children:ccEff\.cur\}\)\}\)', src)
    # CSS/图标符号提取
    mo5 = re.search(r'function ([A-Za-z_$][\w$]*)\((\w+)\)\{return \2\?(\w+)\[\2\]\?\?"Auto":"Auto"\}', src)
    if not mo5:
        return {"found": False, "reason": "O5 effort 显示函数锚点消失"}
    o5 = mo5.group(1)
    mus = None
    for cm in re.finditer(r'([A-Za-z_$][\w$]*)=\{container:"[^"]+",menuPopup:"', src):
        mus = cm.group(1); break
    if not mus:
        return {"found": False, "reason": "menuPopup CSS 模块未找到"}
    miq = re.search(r'function IQe\(', src)
    if not miq:
        return {"found": False, "reason": "IQe 消失"}
    myic = re.search(r'children:o===h\.value&&b\(([A-Za-z_$][\w$]*),\{\}\)', src[miq.start():miq.start()+7000])
    if not myic:
        return {"found": False, "reason": "勾选图标符号提取失败"}
    yic = myic.group(1)
    wrapper = ('ccEff&&E("div",{style:{position:"relative",display:"flex"},children:['
        'b("button",{type:"button",className:' + 'ccRD' + '.footerButton,'
        'style:{paddingLeft:"8px"},onClick:()=>ccEffSet(!ccEffOpen),title:"Select effort level",'
        'children:b("span",{children:ccEff.cur})}),'
        'ccEffOpen&&E("div",{className:' + mus + '.menuPopup+" "+' + mus + '.menuPopupV2,'
        'style:{position:"absolute",bottom:"calc(100% + 8px)",left:0,zIndex:50,minWidth:"180px"},children:['
        'ccEff.lv.map((ccv)=>E("button",{type:"button",'
        'className:' + mus + '.menuItemV2+" "+(ccv===' + es + '.effortLevel.value?' + mus + '.menuItemSelected:""),'
        'onClick:()=>{' + es + '.setEffortLevel(ccv),ccEffSet(!1)},children:['
        'b("span",{className:' + mus + '.menuItemLabel,children:' + o5 + '(ccv)}),'
        'b("span",{className:' + mus + '.menuItemCheckRight,children:ccv===' + es + '.effortLevel.value&&b(' + yic + ',{})})'
        ']},ccv))]})]})')
    if m4:
        wrapper = wrapper.replace('ccRD', m4.group(1))
        return {"found": True, "old": m4.group(0), "new": wrapper, "hit_count": src.count(m4.group(0))}
    # 态 C：fresh——接缝处一次注入模型按钮 + wrapper（rd 从 menuButton 提取）
    body = src[fpos:mmenu.start()+1200]
    mcss = re.search(r'className:([A-Za-z_$][\w$]*)\.menuButton', body)
    if not mcss:
        return {"found": False, "reason": "footer CSS 对象提取失败"}
    rd = mcss.group(1)
    wrapper = wrapper.replace('ccRD', rd)
    mseam = re.search(r'children:b\(([A-Za-z_$][\w$]*),\{\}\)\}\),b\(([A-Za-z_$][\w$]*),\{usedTokens:', body)
    if not mseam:
        return {"found": False, "reason": "JSX 接缝提取失败"}
    old = 'children:b(' + mseam.group(1) + ',{})}),' + 'b(' + mseam.group(2) + ',{usedTokens:'
    if src.count(old) != 1:
        return {"found": False, "reason": "fresh 接缝命中 %d 次（!=1）" % src.count(old)}
    mdlbtn = ('ccMdl&&b("button",{type:"button",className:' + rd + '.footerButton,'
              'style:{paddingLeft:"8px"},onClick:ccOpenMdl,title:"Switch model (click to pick)",children:b("span",{children:ccMdl})}),')
    new = 'children:b(' + mseam.group(1) + ',{})}),' + mdlbtn + wrapper + ',b(' + mseam.group(2) + ',{usedTokens:'
    return {"found": True, "old": old, "new": new, "hit_count": 1}
```

#### 设计说明

- **wrapper 结构**：`ccEff&&E("div",{position:relative})` 包住 Effort 按钮 + 弹窗；按钮 `onClick:()=>ccEffSet(!ccEffOpen)` toggle；弹窗 `ccEffOpen&&` 条件渲染，`position:absolute;bottom:"calc(100% + 8px)"` 向上浮出（footer 在输入框下方，弹窗必须朝上开）。
- **弹窗内容**：`ccEff.lv.map` 直接渲染全部档位按钮，**无标题条目**（v2 初版曾带 `menuHeader`「Effort」标题，2026-08-30 用户指出它不可选、冗余，补丁 2f 对存量机器删除、本生成器同步直出无标题版）；当前档加 `menuItemSelected` 高亮 + 右侧勾选图标 `yic`（从 IQe 内勾选渲染动态提取，与官方勾选同款）；点击档位 `setEffortLevel(ccv)` 后 `ccEffSet(!1)` 收起。
- **样式来源**：全部类名取自官方 menuPopup CSS 模块（`us` 对象，含 `menuPopup`/`menuPopupV2`/`menuHeader`/`menuHeaderTitle`/`menuItemV2`/`menuItemSelected`/`menuItemLabel`/`menuItemCheckRight`），深浅色主题自动跟随；按钮复用 `footerButton`（`rd` 从 v1 按钮自身或 `menuButton` 提取，两态符号一致）。
- **态 B**：v1 的循环切档按钮整体替换（正则含 `ccEff.next` 特征，v2 态不匹配）；**态 C**：fresh 机器接缝处一次注入模型按钮 + wrapper。
- **v2 幂等标记**：`title:"Select effort level"`（v1 的 `Cycle effort level` 不冲突）。

#### verify

- 定位器 found=True（no_change 或 hit_count==1）
- 替换后 `title:"Select effort level"` 与 `ccEff.lv.map` 出现；`node --check` 通过

#### 失败处理

- IQe / CSS 模块 / 勾选图标符号提取失败 → broken，按各自锚点重定位。
- fresh 接缝命中 ≠1 → broken，footer JSX 结构变化。

## 改动 2f：Effort 弹窗移除「Effort」标题条目（弹窗本体即语境，标题冗余）

### file: webview/index.js
### type: locate
### idempotent: children:[ccEff.lv.map

### locator:
```python
def locate(src):
    # 态 A：无标题版已在（幂等）——2f 应用后弹窗 children 直接从 ccEff.lv.map 开始
    if 'children:[ccEff.lv.map' in src:
        return {"found": True, "old": "", "new": "", "no_change": True}
    # 态 B：带标题版在 → 删掉 menuHeader 标题条目，children:[ 直连 ccEff.lv.map
    m = re.search(r'children:\[b\("div",\{className:[A-Za-z_$][\w$]*\.menuHeader,children:b\("span",\{className:[A-Za-z_$][\w$]*\.menuHeaderTitle,children:"Effort"\}\)\}\),ccEff\.lv\.map', src)
    if not m:
        return {"found": False, "reason": "带标题 Effort 弹窗形态未找到（015 v2 未应用或 header 结构变化）"}
    return {"found": True, "old": m.group(0), "new": "children:[ccEff.lv.map", "hit_count": 1}
```

#### 设计说明

- 用户反馈（2026-08-30）：弹窗顶部的「Effort」标题条目不是可选项、多余——弹窗从 footer 的 Effort 按钮弹出，语境已明确，无需再立标题。
- 删除对象：改动 4 注入的 `menuHeader` 条目（`b("div",{className:us.menuHeader,children:b("span",{className:us.menuHeaderTitle,children:"Effort"})})`），保留 `children:[` 后直连 `ccEff.lv.map`。
- 幂等标记 `children:[ccEff.lv.map`：fresh 原生 0 次（改动 4 生成器已同步直出无标题版，fresh 链路一次到位）。
- 正则用 `[A-Za-z_$][\w$]*` 动态匹配 CSS 模块符号（`us` 等），跨版本混淆名变化自适应。

#### verify

- 定位器 found=True（no_change 或命中 1 次）
- 替换后 `children:[ccEff.lv.map` 在位、`children:"Effort"` 消失；`node --check` 通过

#### 失败处理

- 带标题形态未找到 → broken，按 `children:"Effort"` 关键词重新定位 header 条目结构。

## 改动 2g：footer 两按钮文字水平居中（paddingLeft 补位）

### file: webview/index.js
### type: locate
### idempotent: style:{paddingLeft:"8px"},onClick:ccOpenMdl

### locator:
```python
def locate(src):
    PAD = 'style:{paddingLeft:"8px"},'
    # 态 A：模型按钮已带 paddingLeft（幂等——2g 应用后两按钮都带）
    if PAD + 'onClick:ccOpenMdl' in src:
        return {"found": True, "old": "", "new": "", "no_change": True}
    # 态 B：存量无 padding 形态 → 两处分别前插
    oldm = ',onClick:ccOpenMdl,title:"Switch model (click to pick)"'
    if oldm not in src:
        return {"found": False, "reason": "模型按钮形态未找到（015 未应用或结构变化）"}
    olde = ',onClick:()=>ccEffSet(!ccEffOpen),title:"Select effort level"'
    if olde not in src:
        return {"found": False, "reason": "Effort 按钮形态未找到（015 未应用或结构变化）"}
    return {"found": True, "old": oldm, "new": ',' + PAD + 'onClick:ccOpenMdl,title:"Switch model (click to pick)"', "hit_count": src.count(oldm)}
```

> 上方定位器只处理模型按钮；Effort 按钮的 paddingLeft 由**改动 2g-2** 独立块处理（引擎一补丁多块、每块一个替换，幂等标记各自独立）。

## 改动 2g-2：Effort 按钮 paddingLeft（独立块）

### file: webview/index.js
### type: locate
### idempotent: style:{paddingLeft:"8px"},onClick:()=>ccEffSet

### locator:
```python
def locate(src):
    PAD = 'style:{paddingLeft:"8px"},'
    if PAD + 'onClick:()=>ccEffSet' in src:
        return {"found": True, "old": "", "new": "", "no_change": True}
    olde = ',onClick:()=>ccEffSet(!ccEffOpen),title:"Select effort level"'
    if olde not in src:
        return {"found": False, "reason": "Effort 按钮形态未找到（015 未应用或结构变化）"}
    return {"found": True, "old": olde, "new": ',' + PAD + 'onClick:()=>ccEffSet(!ccEffOpen),title:"Select effort level"', "hit_count": src.count(olde)}
```

#### 设计说明

- 用户反馈（2026-08-30，附截图）：两按钮文字在背景块内偏左、不居中。根因：官方 CSS `.inputFooterV2 .footerButton{padding:0 8px 0 0}`（左 0 右 8px），官方按钮左侧有 26px svg 图标补位所以视觉平衡；我们注入的按钮只有纯文字 span、无图标 → 文字贴左边缘。
- 修法：内联 `style:{paddingLeft:"8px"}` 覆盖，左右各 8px、文字居中。内联 style 不依赖 CSS 模块混淆名，跨版本稳定。
- 两块幂等标记分别含 `onClick:ccOpenMdl` / `onClick:()=>ccEffSet` 各自锚定，互不为子串、与其余九块不冲突。
- 改动 4 生成器已同步直出带 paddingLeft 形态（fresh 链路一次到位）。

#### verify

- 定位器 found=True（no_change 或 hit_count==1）
- 替换后两处 `style:{paddingLeft:"8px"}` 在位；`node --check` 通过

#### 失败处理

- 按钮形态未找到 → broken，按 `title:"Switch model (click to pick)"` / `title:"Select effort level"` 重定位。

## 维护备忘

- **依赖顺序**：015 依赖 014 v2（`ccGlm2` 定义 + `ccGlmM2(` 渲染锚）。引擎按文件名序应用（014 在 015 前）；改动 1/2/2c/2d 内建依赖检查，014 缺失时报 broken。
- **幂等标记**：十一块标记各不相同（`,[ccEffOpen,ccEffSet]=ie(!1)` / `ccEffSet,session:` / `,lv:lv}})(),` / `return ccGlm2(` / `ccOpenMdl:()=>{z(Z!==!0)}` / `,ccEffOpen,ccEffSet,session:` / `,ccEffOpen,ccEffSet}){` / `title:"Select effort level"` / `children:[ccEff.lv.map` / `style:{paddingLeft:"8px"},onClick:ccOpenMdl` / `style:{paddingLeft:"8px"},onClick:()=>ccEffSet`），互不为子串；v1 态与 fresh 态均不含全部九个标记（引擎先查标记后跑 locator，不会误判已应用）。**注意**改动 2d 的静态标记写死本机符号 `z`/`Z`——跨版本混淆名变化时该静态查不到，但定位器态 A 用动态符号判 no_change 仍正确（引擎静态标记不中就会跑 locator）。
- **三态定位器**：本补丁五个改动块都是「v2 幂等 → v1 升级 → fresh 注入」三段判定——2.1.226 的 v1 机器原地升级，全新机器一次到位，不需中间版本。
- Effort 弹窗不含 ultracode 虚拟档（`ccEff.lv` 只含 `supportedEffortLevels`）；需 ultracode 时走命令菜单原 `Effort` 行。
- 弹窗无点击外部关闭（官方弹窗有 overlay，自建弹窗用完点档位即收，或再点按钮收起）。

## 已验证版本

- `2.1.226`：v2 verified（2026-08-30，五改动块三态干跑全过：本机 v1→v2 升级 / fresh 全链路注入 / v2 幂等复跑；`node --check` 通过）。同日补改动 2c（v1 残留的 `ccMdl` IIFE 调 `ccGlm` 未升级——选 opus 别名项时 footer 按钮回退官方名、与列表不一致，用户报告后补块升级为 `ccGlm2`），六块全 verified。同日再补改动 2d（`ccOpenMdl` 只开不收——弹窗开着再点按钮无效，用户报告后升级 toggle 形态 `z(Z!==!0)`，改动 2 fresh 态同步直出 toggle）、改动 2e（props 漏传 `ccEffOpen`——签名解构了但 props 只传 `ccEffSet`，bQe 体内 `ccEffOpen` 恒 undefined、Effort 弹窗条件恒假，补传后 toggle 闭环），八块全 verified。同日又补改动 2f（Effort 弹窗顶部「Effort」标题条目不可选、冗余——用户指出后删条目，改动 4 生成器同步直出无标题版），九块全 verified。同日又补改动 2g/2g-2（footer 两按钮文字偏左不居中——官方 `.inputFooterV2 .footerButton{padding:0 8px 0 0}` 左 0 右 8px、官方按钮左侧有 26px svg 补位而注入按钮纯文字无图标，内联 `style:{paddingLeft:"8px"}` 补位居中，改动 4 生成器同步直出），十一块全 verified。
- `2.1.226`：v1（2026-08-30 上午，已被 v2 取代；v1 缺陷：ccOpenMdl 提取到命令面板 setter、Effort 仅循环切档）。
