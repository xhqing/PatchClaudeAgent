# Changelog

本项目（PatchClaudeAgent / Tinker）维护针对本机 VSCode Claude Code 扩展（`anthropic.claude-code`）的自定义补丁。本文件记录补丁 Skill 与引擎的历次变更，每条写明「为什么改」与「改了什么」，便于日后排查回归。

## 2026-09-04

### 回滚（patch 014 v3：应用后 webview 白屏，当晚回滚恢复 v2）

- **为什么改**：上一条记录的 014 v3（同名重声明覆盖升级）应用后用户报告 VSC 里的 CC 面板完全不显示。排查：扩展宿主日志（window4/5/6，22:11–22:40）显示扩展激活正常（`Claude code extension is now active`、MCP Server、AuthManager 均无异常），但 webview 连 `time_to_interactive` 初始化消息都没有（对比补丁前 window3 21:53 有完整 webview 消息流）——判定 webview JS 渲染早期崩溃。文件完整性核对无异常（字符数 4833458 = v2 态 4832515 + 追加 943，`node --check` 通过，v3 块内容读回正常），排除写入损坏 / 编码丢字节 / 截断；静态分析未找到语法或运行时炸点（顶层同名 function 重声明在 sloppy/strict/module 下均合法，v3 函数体各路径与 v2 行为等价），根因未定位。
- **改了什么**：① 已安装扩展 `webview/index.js` 精确删除 v3 块（截断到 v2 块结尾标记），回滚后字符数 4832515 与 v2 态完全一致、`node --check` 通过；② `patches/014-model-picker-glm-names.md` 回退到 v2（改动 1 恢复 v2 append 块、哨兵 `ccGlmMap2`），版本演进段保留 v3 事故记录与教训——**升级一律走「新函数名」模式（v1→v2 已线上验证），禁止「同名重声明覆盖」**；v3 两需求（`claude-opus-4-6→deepseek-v4-flash`、隐藏 Default 项）记入维护备忘「待办需求」+ TODO 待按新函数名模式重做；③ SKILL.md 014 行、README / README_cn 的 014/015 行同步回 v2 表述并附 v3 事故简注。
- **实测验证**：回滚后文件长度、尾部内容（`end patch-claude 014 v2`）、`node --check` 三项核对通过；待用户重载窗口确认 CC 面板恢复显示。

### 变更（patch 014 升级 v3：模型列表 Opus 4.6 显示 deepseek-v4-flash + 隐藏 Default 项）【当晚已回滚，见上条】

- **为什么改**：用户报告（2026-09-04）模型选择弹窗列表还有两个与桥接语义错位的残留项。① 本机 `~/.claude/settings.json` 的 `availableModels` 含 `claude-opus-4-6`（binary 侧 `vw_()` 构造，label「Opus 4.6」，value 与已成功改写的 Opus 4.8 项同构为 `claude-opus-4-6`），v2 映射表无此键 → 该项原样显示「Opus 4.6」；用户指定其显示名为 `deepseek-v4-flash`。② binary 侧 `oSo()` 构造的 Default 项（`{value:null,label:"Default"}`，经 `lJe()` 转 `value:"default"`）出现在列表首位，用户要求不显示。
- **改了什么**：`patches/014-model-picker-glm-names.md` 改动 1 升级为 v3 append 块（新哨兵 `ccGlmMap3`，v2 块保留无害）：映射表补 `"claude-opus-4-6": "deepseek-v4-flash"`；`ccGlmM2` 重声明覆盖——先 filter 掉 `value==="default"` 的项再 map 改写；description 模板从 `"GLM (cc-bridge) · <名>"` 改为 `"cc-bridge · <名>"`（v3 起映射含非 GLM 名，描述再写 GLM 字样自相矛盾）。**有意不换函数名 `ccGlm2`/`ccGlmM2`**（重声明后者胜出，同 v1→v2 模式）——015 依赖这两个名字与 `availableModels:ccGlmM2(` 锚串、`ccGlmMap2` 存在性检查，换名会迫使 015 多处联动改锚；调用点零改动自动获得 v3 行为。改动 2/3 与 015 不动。README / README_cn 的 014 行（标题改「桥接真名」、效果补两项）与 015 行（「GLM 名」→「桥接真名」）同步更新。
- **实测验证**：干跑 `--status`（改动 1 needs-reapply、改动 2/3 与 015 幂等 verified）；引擎真实应用 verified: 11（追加 943 字符）；`node --check` 通过；模拟 binary 列表数据行为测试——Default 项被移除、`claude-opus-4-6` 项显示 `deepseek-v4-flash`、`glm-5.3`/`glm-5.3-flash`/opus 别名改写不变、指示器 `ccGlm2("claude-opus-4-6")` 返回 `deepseek-v4-flash`、`ccGlm2("default")` 回退 undefined；v1/v2/v3 三块共存按序加载验证覆盖语义正确。

## 2026-08-30

### 修复（patch 015 补改动 2g/2g-2：footer 模型与 Effort 按钮文字在背景块内水平居中）

- **为什么改**：用户反馈（附截图）`glm-5.3`、`Max` 两按钮文字在浅灰背景块内偏左、不居中，观感不规范。根因：官方 CSS `.inputFooterV2 .footerButton{padding:0 8px 0 0}` 左 0 右 8px——官方 footer 按钮左侧都带 26px 的 svg 图标占位，文字自然「居中」；注入的两按钮只有纯文字 span、无图标，文字直接贴左边缘。
- **改了什么**：`patches/015-footer-model-effort-buttons.md` 新增**改动 2g**（模型按钮）与 **2g-2**（Effort 按钮）两块：各自在按钮 JSX 的 `className` 后前插内联 `style:{paddingLeft:"8px"}`，左右各 8px 对称、文字居中；内联 style 不依赖 CSS 模块混淆名、跨版本稳定。改动 4 生成器同步直出带 padding 形态（fresh 一次到位），生成器内 `style` 置于 `onClick` 之前、与 2g 注入结果形态一致。两块幂等标记分别锚定 `onClick:ccOpenMdl` / `onClick:()=>ccEffSet`，互不为子串。
- **实测验证**：干跑两链路（本机存量：块 9/10 各 +26 字符；fresh：块 0/1/6/7 应用 + 生成器直出，`paddingLeft` 命中 2、`node --check` 通过）；引擎真实应用（verified: 11，长度 4832463→4832515）；`node --check` 通过；幂等重跑 11/11 verified。SKILL.md 015 行同步为十一块。

### 修复（patch 015 补改动 2f：Effort 弹窗移除「Effort」标题条目——不可选、冗余）

- **为什么改**：用户指出（附截图）Effort 弹窗顶部那行「Effort」不是可选项、不需要列出来。它是 v2 注入的 `menuHeader` 标题条目（照搬官方菜单分组样式），但该弹窗从 footer 的 Effort 按钮弹出、只含一组档位，语境已明确，标题纯属冗余。
- **改了什么**：`patches/015-footer-model-effort-buttons.md` 新增**改动 2f**（两态：无标题版已在→no_change / 带标题版在→正则匹配 `menuHeader`+`"Effort"` 条目整段删除，`children:[` 直连 `ccEff.lv.map`），幂等标记 `children:[ccEff.lv.map`（fresh 原生 0 次）；改动 4 的 wrapper 生成器同步删除标题行，fresh 机器直出无标题版。**块序**：2f 排在改动 4 之后（引擎按文件内顺序应用，2f 依赖改动 4 的产物）。九块标记互不为子串。
- **实测验证**：干跑两条链路（fresh 备份全链路注入：块 0/1/6/7 应用、2/3/4/5/8 幂等，无标题版在位、`node --check` 通过；本机存量：块 0-7 幂等、2f 删除标题 -103 字符）；引擎真实应用（verified: 11，长度 4832566→4832463）；`node --check` 通过；`children:"Effort"` 残留 0；幂等重跑 11/11 verified。SKILL.md 015 行同步为九块（含 2f 描述）。

### 修复（patch 015 补改动 2e：Effort 弹窗状态 ccEffOpen 漏传 props——补传后按钮 toggle 闭环）

- **为什么改**：用户要求 Effort 按钮与模型按钮一样首点展开、再点收回。检查发现比 toggle 更深的 bug：改动 3 给 bQe 签名注入了 `ccEffOpen,ccEffSet` 解构，但改动 2 的 props 注入只传了 `ccEffSet`——`ccEffOpen` 从未进 props，bQe 体内它恒 `undefined`（React 组件解构缺省值），后果：弹窗条件 `ccEffOpen&&E(...)` 恒假、按钮 `onClick:()=>ccEffSet(!ccEffOpen)` 的 `!ccEffOpen=!undefined=!0` 恒真——按钮每次点击都是「设为开」，状态与显示永远对不上。
- **改了什么**：`patches/015-footer-model-effort-buttons.md` 新增**改动 2e**（两态：`,ccEffOpen,ccEffSet,session:` 已在→no_change / `ccEffSet,session:` → 前插 `ccEffOpen,`），幂等标记 `,ccEffOpen,ccEffSet,session:`（原生 0 次、注入后唯一、与签名处 `,ccEffOpen,ccEffSet}){` 互不为子串）；改动 2 的 fresh 态同步直出完整形态。补传后按钮 onClick（本就是 `ccEffSet(!ccEffOpen)` toggle 写法）语义闭环：关→开、开→关；`ccEffOpen` 在 OQe 渲染作用域被弹窗条件读取追踪，重渲染后 props 闭包新鲜。
- **实测验证**：引擎重跑——前七块幂等 verified、2e locate+replace 成功（长度 +10：`ccEffOpen,` 11 字符）；`node --check` 通过；`,ccEffOpen,ccEffSet,session:` 在位；幂等重跑 11/11 verified。SKILL.md 015 行同步为八块（含 2e 描述）。

### 修复（patch 015 补改动 2d：模型按钮 ccOpenMdl 只开不收——升级为 toggle，弹窗开着再点按钮即收回）

- **为什么改**：用户实测报告——footer 模型按钮首次点击能展开模型列表，但列表开着时再点按钮收不回。根因：`ccOpenMdl:()=>{z(!0)}` 是「只开」写法（抄的官方入口——命令菜单 `Switch model` 行也是 `z(!0)`）；官方关闭弹窗走三条路（scrim 遮罩点击 `fr()`、Escape、选中模型后自动关），都不含「再点入口」。官方场景下没问题（菜单行点击后菜单自身先关），但 footer 按钮常驻在 scrim 下层（scrim 是 `position:fixed;z-index:0` 的兄弟节点，弹窗开着时点按钮命中按钮本身、不穿透到 scrim），`z(!0)` 在弹窗已开时是无效写。
- **改了什么**：`patches/015-footer-model-effort-buttons.md` 新增**改动 2d**（三态定位器：toggle 已在→no_change / v2 只开形态 `z(!0)},ccEffSet,session:` → `z(Z!==!0)` / v1 形态一步到位），幂等标记 `ccOpenMdl:()=>{z(Z!==!0)}`（自造形态 `!==!0` 压缩器不产出，原生 0 次）；改动 2 的 v1 升级与 fresh 态同步直出 toggle 形态（新机器不再经只开中间态）。语义：`z(Z!==!0)` 等价 `z(!Z)`——开→关、关→开；闭包新鲜性由 OQe 重渲染保证（`Z` 被 `IQe isOpen:Z` 追踪，Z 变化即重渲染、新 props 闭包捕获新 Z）。维护备忘同步（七块标记互异；2d 静态标记写死本机符号 `z`/`Z`，跨版本混淆名变化时引擎静态查不到但定位器动态符号仍正确判 no_change）。
- **实测验证**：引擎重跑——前六块幂等 verified、2d locate+replace 成功（长度 +4：`(!0)`→`(Z!==!0)`）；`node --check` 通过；`ccOpenMdl:()=>{z(Z!==!0)},ccEffSet,session:` 在位；幂等重跑 11/11 verified。

### 修复（patch 015 补改动 2c：v1 残留的 footer 模型按钮 ccGlm 调用升级——选 opus 别名项时按钮显示官方名与列表不一致）

- **为什么改**：v2 应用后用户实测报告——模型弹窗列表里各项已正常显示 GLM 真名（走 014 v2 的 `ccGlmM2`），但选完（如选 `opus` 别名项，实际落 `claude-opus-4-8`）后输入框下面的模型按钮仍显示 `claude-opus-4-8` 而非 `glm-5.3`。根因：本机走的是 v1→v2 升级路径，015 改动 2 的 v1 路径只修正 setter 并追加 `ccEffSet`，**不动 v1 已注入的 `ccMdl` IIFE**——里面的 `ccGlm(ms)` 仍是 v1 函数（映射表无 `opus`/`sonnet`/`haiku` 家族别名键），选别名项时查表不中 → 回退官方 displayName（ANTHROPIC_DEFAULT_OPUS_MODEL 的原始 id）。fresh 机器不受影响（改动 2 直接生成 `ccGlm2` 版）。
- **改了什么**：`patches/015-footer-model-effort-buttons.md` 新增**改动 2c**（插在改动 3 之前，三态定位器：v2 已在→no_change / v1 残留 `return ccGlm(ms)??(` → `return ccGlm2(ms)??(` / 异常形态 broken），幂等标记 `return ccGlm2(`；`ms` 是本补丁注入的自有变量名（非混淆符号、跨版本稳定），该串在 v1 注入物中唯一。维护备忘同步（六块标记互异）。
- **实测验证**：引擎重跑——前五块幂等 verified、2c locate+replace 成功（长度 +1：`ccGlm`→`ccGlm2`）；`node --check` 通过；注入点 `return ccGlm2(ms)??` 在位；幂等重跑 11/11 verified。

### 变更（patch 014 / 015 升级 v2：修三个问题——GLM 名不显示、模型按钮误开命令面板、Effort 无直选列表）

- **为什么改**：v1 上线后用户报告三个问题（2026-08-30）：① 模型选择弹窗里 `claude-opus-4-8` 项没有显示成 `glm-5.3`——根因是 `~/.claude/settings.json` 的 `availableModels` 里手写的 `"opus"` 是官方别名项，native binary 侧 `REu()` 把它构造成 `{value:"opus", label:<ANTHROPIC_DEFAULT_OPUS_MODEL 原始 id>, description:"Custom Opus model"}`，其 `value` 是 `"opus"` 而非 `"claude-opus-4-8"`，v1 的 ccGlmMap 查表不中；且各模型项 `description` 来自 binary 模板（如 "Opus 4.8 · Previous Opus version"），v1 只改 displayName、Opus 误导字样残留；② footer 模型按钮点击弹出的是**命令面板**而非模型选择弹窗——v1 定位器取「渲染点之前第一个 `isOpen:` 状态」实际命中命令面板（qXe）的 setter 而非模型弹窗（IQe）的；③ Effort 按钮只能循环切下一档、无列表直选（官方本就没有独立 Effort 弹窗 UI）。
- **改了什么**：
  - **`patches/014-model-picker-glm-names.md` 重写为 v2**：换新哨兵 `ccGlmMap2` 与新函数名 `ccGlm2`/`ccGlmM2`（append 块内容变了必须换新哨兵引擎才重新追加，v1 块留文件尾部无害——同 008 演进模式）；映射表补家族别名 `opus→glm-5.3`、`sonnet→glm-4.7`、`haiku→glm-4.6`（对齐本机 env 默认指向），前缀匹配天然覆盖 `opus[1m]` 变体；`ccGlmM2` 同时改写 displayName + description（命中项 description 统一为 `"GLM (cc-bridge) · <glm 名>"`，清掉 Opus 字样）。三改动块全为**三态兼容定位器**（v2 已在→no_change / v1 态升级 / fresh 注入），同一补丁通吃三种机器状态。
  - **`patches/015-footer-model-effort-buttons.md` 重写为 v2**（三改动块扩为五改动块）：① OQe 体内四连 useState 后追加 `[ccEffOpen,ccEffSet]=ie(!1)` 弹窗状态（定位器用「后 30000 字内含 `availableModels:ccGlmM2(`」锁定 OQe 而非全文第一个四连）；② footer 渲染点 props 注入——`ccOpenMdl` setter 修正为从 IQe 渲染点（014 v2 注入的 `availableModels:ccGlmM2(` 是产品级唯一锚）之前最近一次 `[Z,z]=ie(!1)` 定义提取，追加 `ccEffSet`；2b `ccEff` IIFE 从 `{cur,next}` 升级为 `{cur,lv}`（弹窗需要完整档位数组）；③ bQe 签名解构追加 `ccEffOpen,ccEffSet`；④ footer JSX 把 v1 循环切档按钮整体替换为 wrapper（relative div）+ 自建 Effort 弹窗——复用官方 menuPopup CSS 模块类名（`menuPopup`/`menuHeader`/`menuItemV2`/`menuItemSelected`/`menuItemLabel`/`menuItemCheckRight`）与 IQe 同款勾选图标，`position:absolute;bottom:calc(100% + 8px)` 向上浮出，点击档位 `setEffortLevel` 选中并收起。五块全三态定位器。
  - **同步**：SKILL.md 补丁表补 012/014/015 三行、002/007/008/010/011 五行已验证版本补 `2.1.226`；README 中英补丁表补 014/015 两行、补 Version 徽章；VERSION 2.1.220→2.1.226（以本次已验证的扩展版本为准）。
- **实测验证**：引擎真实应用——014 三块（append +818 字符、两调用点 v1 升级）与 015 五块全 verified，其余 002~012 幂等 verified 共 11/11；`node --check` 通过；幂等重跑 11/11 全 verified；注入点计数抽查全对（`ccGlmMap2`×3、`availableModels:ccGlmM2(`×1、`ccOpenMdl:()=>{z(!0)},ccEffSet,session:`×1——setter 已是模型弹窗的 `z` 而非命令面板的 `N`、`title:"Select effort level"`×1、`return{cur:O5(cu),lv:lv}`×1、`us.menuPopup+" "+us.menuPopupV2` 弹窗样式在位）。**fresh 全链路**（备份原始文件干跑 014 三块 + 015 五块）`node --check` 通过，全新机器一次到位。

### 新增（patch 015 输入框 footer 常驻模型与 Effort 按钮）

- **为什么加**：当前模型名与 Effort 档位藏在命令菜单里（`Switch model…` / `Effort (Max)` 行），看当前值、切一次都要先开菜单——用户要求把这两项放到输入框下面的 footer 常驻位置，不仅随时能切、还能实时看到当前值。配合补丁 014，footer 模型按钮直接显示 GLM 真名（如 glm-5.3-flash），与桥侧实际服务模型一致。
- **改了什么**：新增 `patches/015-footer-model-effort-buttons.md`，三改动块全在 `webview/index.js`、全 `type:locate`：① 在 footer 渲染点向组件传三个新 props——`ccMdl`（当前模型显示名，GLM 真名优先）、`ccEff`（`{cur,next}` 当前档与下一档）、`ccOpenMdl`（打开模型选择弹窗的回调，复用命令菜单 `Switch model…` 的同一个弹窗 setter）；② footer 组件签名解构注入这三个 props（锚 `onTerminalCollaborator` 末位参数）；③ footer JSX 在命令菜单按钮与用量按钮之间的接缝注入两个 `footerButton` 按钮——模型按钮点击开弹窗（弹窗内含 014 的 GLM 真名与勾选态）、Effort 按钮点击 `setEffortLevel(下一档)` 循环切档。**实时性机制**：两按钮的当前值在响应式包裹组件渲染时以 IIFE 算好、读的 `.value` 落在其响应式作用域内被追踪（与 footer 右侧「Auto」模式按钮同机制），模型 / Effort 变化即重渲染刷新文字。
- **依赖与防护**：015 依赖 014 的 `ccGlm`——改动 1 定位器内建依赖检查（`ccGlmMap` 缺失返回 found=False），fresh 机器按文件名序先 014 后 015 天然满足。三块幂等标记互异且互不为子串。已在 2.1.226 应用：三块 verified、`node --check` 通过、幂等重跑 verified 11/11。
- **边界**：Effort 循环不含 ultracode 虚拟档（需时走命令菜单原 Effort 行）；不支持 effort 的模型（如部分 haiku）不渲染 Effort 按钮；模型按钮未映射时显示官方名、点击仍可开弹窗。

### 新增（patch 014 模型选择器显示 GLM 真名）

- **为什么加**：CC VSCE 经 cc-bridge（GLM 桥）上游，`MODEL_MAP` 把 Claude 模型名改写为 GLM 模型名（本机新增 `claude-opus-4-7->glm-5.3-flash` 映射对后，选 Opus 4.7 实际服务 glm-5.3-flash、选 Opus 4.8 实际服务 glm-5.3）。界面选择器仍显示 Claude 名，与实际服务的模型语义错位——用户要心里记着「Opus 4.7 其实是 flash」。在显示层把名字对齐后，体感就是直接选 GLM 模型。
- **改了什么**：新增 `patches/014-model-picker-glm-names.md`，三改动块全在 `webview/index.js`：① `type:append` 在文件末尾追加 `ccGlmMap` 映射表（与 glm.env 的 MODEL_MAP 保持同步，维护约定写在补丁内）+ `ccGlm()`（模型值→GLM 名，未命中返回 undefined）与 `ccGlmM()`（模型列表浅拷贝改写 displayName）两个辅助函数，幂等标记 `ccGlmMap`；② `type:locate` 把命令菜单 `Switch model…` 指示器的赋值 `ht=xbe(ae,…)` 包成 `ht=ccGlm(ae)??xbe(ae,…)`——锚点为 `id:"model"` 动作注册链 + `lastServedModel.value` 字段名（产品级语义锚，正则动态提取混淆符号），命中映射显示 GLM 名、未命中保持官方显示；③ `type:locate` 把 IQe 弹窗渲染处 `availableModels:…models,unavailableModels:…` 各包一层 `ccGlmM()`——弹窗列表项 displayName 直接显示 GLM 真名，`h.value` 仍是官方 id、setModel 写 settings.json 不变（纯显示层，选择逻辑零改动）。已在 2.1.226 应用：三块 verified、`node --check` 通过、幂等重跑 verified 10/10。
- **配套**：桥侧同步两处——CC-Bridge `glm-bridge/adapter.js` 的 MODEL_MAX_TOKENS 补 `glm-5.3-flash: 131072`（记 CC-Bridge CHANGELOG），本机 `~/.cc-bridge/glm.env` 的 MODEL_MAP 加 `claude-opus-4-7->glm-5.3-flash` 并重启桥（本机配置不记仓库 CHANGELOG）；端到端实测 opus-4-7 请求经桥返回 `model: glm-5.3-flash`、opus-4-8 回归仍 `glm-5.3`。

### 修复（apply 引擎：append 幂等标记优先用补丁显式声明，修复自动提取误判）

- **为什么改**：应用 014 时发现引擎 append 分支**无视补丁声明的 `### idempotent:`**，固定用正则 `(@keyframes\s+\w+|\.[-\w]+)` 从 append 文本自动提取 marker——该正则本意抓 CSS 类名 / keyframes 名（008/011 等 CSS 追加块的场景），但在 JS append 文本上会命中**字符串字面量内部**（014 的 `"glm-5.3"` 里的 `.3`），而 `.3` 在 bundle 里早已存在 → 误判「已应用」跳过追加。后果严重：同补丁的 locate 块（改动 2/3）照常插入了 `ccGlm(ae)`/`ccGlmM(` 调用，函数定义却没进文件——webview 运行时会 ReferenceError。本次实跑即踩中：首次运行三块全报 verified，实际文件 `ccGlmMap` 出现 0 次（当场发现并修复，未造成运行故障）。
- **改了什么**：`apply-patches.py` append 分支的 marker 改为 `blk["idempotent"] or 自动提取`——与 locate 分支行为对齐（显式声明优先）；未声明时保留原自动提取兜底，并加注释说明「append 文本无 CSS 类名/keyframes 时必须显式声明 idempotent」。修复后重跑：改动 1 真正追加 701 字符，幂等重跑三块全 verified；008/011 等既有 append 补丁回归正常（仍命中各自自动提取的 CSS 类名标记）。
- **防回归**：014 的补丁 .md 在改动 1 写明 `### idempotent: ccGlmMap`（此前 append 块没写过这个字段，SKILL.md 的 append 要点里也没要求）——后续新写 JS 类 append 补丁时同样必须显式声明。

## 2026-08-17

### 变更（Visitors 徽章更名 Visits/day (14d)：alt 文本与 xhqing 集中统计新 label 对齐）

- **为什么改**：用户要求（2026-08-17）访问量徽章名需表达「最近半月日均访问量」口径——xhqing 集中统计侧的 badge JSON label 已从 `Visitors` 改为 `Visits/day (14d)`（`Visits/day` 是 shields.io 表达日均的惯例写法、`(14d)` 标注 14 天滚动窗口），各仓 README 的徽章 alt 文本同步对齐，避免 alt 与徽章实际显示文字脱节。
- **改了什么**：README 徽章区 `alt="Visitors"` → `alt="Visits/day (14d)"`，仅改 alt 文本，endpoint URL、数据源、徽章口径均不变（口径改动记 xhqing 仓库 CHANGELOG，本仓只改 alt）。

## 2026-08-12

### 变更（Visitors 徽章 alt 文本首字母大写：README 访问量徽章命名统一）

- **为什么改**：用户指令（2026-08-16）「Visitors 徽章全局统一，首字母大写」——配合全局 `~/.claude/CLAUDE.md`「徽章英文首字母必须大写」新规，集中统计上线时挂的访问量徽章 `alt="visitors"` 为小写存量，与 badge JSON label（`Visits/day`）及大写规范不一致，本次一次收口。
- **改了什么**：README（EN/CN）徽章区 visitors 徽章 `alt="visitors"` → `alt="Visitors"`，仅改 alt 显示文本，endpoint URL 与数据源不变。

### 新增（README 访问量徽章——舰队集中式访问统计）

- **为什么改**：全舰队上线集中式「真去重」访问统计（图片徽章方案无法去重，走官方 Traffic API 路线）：统计集中部署在 xhqing 仓库（`scripts/update_traffic.py` + 每日 GitHub Action），各 fleet 仓库只需在 README 挂徽章、零运行负担。
- **改了什么**：README（EN/CN）徽章区新增 visitors 徽章（shields.io endpoint 指向 `xhqing/xhqing` 仓库 `traffic/badges/<repo>.json`，由每日采集的官方 Traffic API 数据更新）。徽章数字含义：按日去重访客的累计（GitHub 只提供每日 uniques，跨天不去重），自 2026-08-16 起累计。

### 新增

- **patch 012 会话状态写盘（session-state-to-file）**：新增补丁，把每个会话的实时 `state`（idle/running/thinking/waiting_input）写到 `~/.claude/session_running/<sessionId>.txt`。**为什么加**：DayTradingAgent 的密采样守护 watcher（独立 launchd 进程）要判断「盯盘会话是否真在 Running」来决定报不报中断，但会话 Running 标签（补丁 002 显示的那个）的状态源自 session 对象的 `busy=state!="idle"` / `pendingInput=state=="waiting_input"`，**只在 extension.js 进程内存、不写盘、无 CLI/API 暴露**，外部进程原读不到——watcher 只能靠 jsonl 停更阈值猜会话死活，在采样段间 jsonl 停更时误报。补丁 012 把这个内存状态落到磁盘，watcher 读它 = 读会话 Running 标签的地面真相，根治阈值误报。**改了什么**：`type: locate` 定位 extension.js 的 `updateSessionState(e,t,r)` 方法（唯一的会话状态更新入口），动态提取三个参数名（跨版本自适应混淆符号），在原 `this.broadcastSessionStates()` 后注入写盘——`require("fs")` 原生可用、`process.env.HOME` 取家目录、写 `<sessionId>.txt` 内容=state、try/catch 兜底（写盘失败不影响主流程）、`ccSessionStateWrite` 幂等标记。路径选全局固定 `~/.claude/session_running/`（不依赖 extension 的 cwd）。已在 2.1.226 通过 apply 引擎应用（长度 +235 字节、node --check 通过、写盘逻辑 node 实跑验证通过）；DayTradingAgent watcher 配套改为读 state 文件判定、state 文件缺失时 fallback 到原 jsonl 判定（过渡期兼容）。

## 2026-08-03

### 变更

- **引擎适配新版扩展目录命名（修自动定位回归）**：自 VSCode Claude Code 扩展 2.1.220 起，扩展目录名去掉了 `-darwin-arm64` 平台后缀（新版为 `anthropic.claude-code-2.1.220`，旧版为 `...-2.1.217-darwin-arm64`）。引擎 `apply-patches.py` 的 `find_ext_dir` 原硬编码 `endswith("-darwin-arm64")`，导致不传参自动定位时找不到新版目录直接 `die`，只能靠显式传 EXT_DIR 绕过。改为只按 `anthropic.claude-code-` 前缀匹配，新老两种命名都能命中，再按 `package.json` 读到的真实版本号排序取最新。
- **SKILL.md 步骤 1 通配命令同步**：原命令 `ls -d .../anthropic.claude-code-*-darwin-arm64` 对无后缀的新版匹配失败，改为 `anthropic.claude-code-*`，并补说明（2.1.220 起去后缀、改用 universal 命名）。
- **SKILL.md 步骤 2 脚本路径改为项目内相对路径**：原示例写全局路径 `~/.claude/skills/patch-claude/scripts/apply-patches.py`，但本机并未把该 skill 装到全局（它随项目活在 `.claude/skills/patch-claude/`），照全局路径跑会找不到文件。改为 `.claude/skills/patch-claude/scripts/apply-patches.py`，并注明在项目根执行，消除文档与现状的不一致。
- **补丁移植性表格版本号更新**：002 / 007 / 008 / 010 / 011 五条补丁的「已验证」版本号统一更新到 2.1.220（原分别标 2.1.195 / 2.1.211 / 2.1.215 / 2.1.214 / 2.1.215）。

### 补丁验证

- 扩展升级 2.1.217 → 2.1.220 后，8 个生效补丁全部重新应用成功、零 broken（无需人工重定位锚点）：002 历史会话运行标记、003 usage 图标隐藏、004 鉴权失败不弹登录、005 上下文窗口读 env、007 diff 跟随明暗主题、008 浅色消除 diff 黑阴影、010 图片链接可打开、011 LaTeX 数学渲染。归档补丁 001（思考默认展开）、009（会话刷新按钮）仍停用，不参与应用。原版备份在 `~/.claude/patch-backups/2.1.220/`。

### 新增

- **CHANGELOG.md**：本文件起记。此前变更未单独记录，自本次开始按「为什么改 + 改了什么」沉淀。
- **VERSION 文件**：确立项目版本号唯一权威源。项目本身无独立版本号，其「版本」即当前适配并验证过的 VSCode Claude Code 扩展版本（2.1.220）——SKILL.md 补丁移植性表格的「已验证」、CHANGELOG 的记录都以它为锚。新增根目录 `VERSION` 文件，后续各文件版本号向它看齐、可机械核对，也供 commit skill 的版本滞后 / 一致性检测使用。
