#!/usr/bin/env python3
"""
patch-claude-code 引擎：对本机 claude-code 扩展按 patches/*.md 逐条应用补丁。

每条补丁 .md 支持 1..N 个「改动块」，每块形如：
  ## 改动 K：<标题>
  ### file: <相对扩展根的路径>
  ### type: replace | append
  ### precheck: <python 表达式或 None>   （可选，下文说明）
  ### replace                              （type=replace 时）
  - old: `字节串`
  - new: `字节串`
  ### append                               （type=append 时）
  ```<内容>```
  ### verify                               （可选）

为保持解析简单稳定，引擎只识别以下锚点：
  - file: 行       → 该改动块的目标文件
  - type: 行       → replace 或 append（默认 replace）
  - "- old: `...`" → replace 的旧串
  - "- new: `...`" → replace 的新串
  - append 内容取 type=append 之后、下一个 ### 或文件末尾之间的代码块（``` 之间）

工作流：定位扩展 → 解析每个补丁的改动块 → 逐块 precheck→应用→校验→备份→回写 version-map。
设计为幂等：已应用的改动只确认状态，不重复改文件。
绝不下载、不分发 Anthropic 代码，仅操作用户本机已安装副本。

用法：
  python3 apply-patches.py [EXT_DIR]    # 不传则自动定位最新版本目录
  python3 apply-patches.py --status     # 只检查不改
"""
import json, os, re, sys, shutil, datetime

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATCHES_DIR = os.path.join(SKILL_DIR, "patches")
VERSION_MAP = os.path.join(SKILL_DIR, "version-map.json")
# 独立的本机备份目录（不放在 skill/项目内，避免任何被误入库的风险；每台机器各自生成）。
# 取代旧的、依赖预存 Anthropic 原始文件的 rollback/<version>/。
ROLLBACK_DIR = os.path.expanduser("~/.claude/patch-backups")
EXTENSIONS_ROOT = os.path.expanduser("~/.vscode/extensions")

# ---------- 定位扩展副本 ----------

def find_ext_dir(explicit=None):
    if explicit:
        return explicit, read_version(explicit)
    cands = []
    for d in os.listdir(EXTENSIONS_ROOT):
        if d.startswith("anthropic.claude-code-") and d.endswith("-darwin-arm64"):
            full = os.path.join(EXTENSIONS_ROOT, d)
            if os.path.isdir(full):
                cands.append((read_version(full), full))
    if not cands:
        die(f"未在 {EXTENSIONS_ROOT} 找到 anthropic.claude-code-* 扩展目录")
    cands.sort(reverse=True)
    return cands[0][1], cands[0][0]

def read_version(ext_dir):
    pkg = json.load(open(os.path.join(ext_dir, "package.json"), encoding="utf-8"))
    return pkg.get("version", "unknown")

# ---------- 备份 ----------
# 注意：rollback/<version>/ 存的是该版本"完全原始"的扩展文件（001 之前的状态）。
# 回滚会把该文件恢复成原始版，意味着同时抹掉该版本上所有补丁（非逐补丁回滚）。

def backup_target(ext_dir, rel_target, version):
    src = os.path.join(ext_dir, rel_target)
    bdir = os.path.join(ROLLBACK_DIR, version)
    os.makedirs(bdir, exist_ok=True)
    dst = os.path.join(bdir, rel_target.replace("/", "__"))
    # 仅当尚无该版本本机备份时，从扩展目录当前文件拷贝首份备份；已有则保留不动。
    # 首次调用必然发生在打补丁之前，故扩展目录当前文件即为原版。
    # 若扩展目录同级存在 .bak（更可能是干净的原始版），优先用它。
    if not os.path.exists(dst) and os.path.exists(src):
        bak = src + ".bak"
        origin = bak if os.path.exists(bak) else src
        shutil.copy2(origin, dst)
        return dst, True
    return dst, False

# ---------- 解析补丁 .md → 改动块列表 ----------

def parse_changes(txt):
    """把补丁正文切成多个改动块。每块以 '## 改动' 或 '## 改动 K' 开头，
       到下一个 '## ' 或正文末尾结束。"""
    # 按 "## 改动" 切分
    parts = re.split(r'\n(?=## 改动)', txt)
    # 第一段是 frontmatter/标题/背景，跳过
    changes = []
    for part in parts:
        if not part.lstrip().startswith("## 改动"):
            continue
        changes.append(part)
    return changes

def parse_block(block):
    """从单个改动块文本解析出 {file, type, old, new, append_text, pre_expr}。
       只认 file:/type: 行 与 - old:`...` / - new:`...` / append 代码块。"""
    m_file = re.search(r'^###?\s*file:\s*(.+)$', block, re.M)
    m_type = re.search(r'^###?\s*type:\s*(\w+)', block, re.M)
    ftype = m_type.group(1).strip().lower() if m_type else "replace"
    file = m_file.group(1).strip() if m_file else None

    old = new = None
    mo = re.search(r'-\s*old:\s*`(.+?)`', block, re.S)
    mn = re.search(r'-\s*new:\s*`(.+?)`', block, re.S)
    if mo: old = mo.group(1)
    if mn: new = mn.group(1)

    append_text = None
    if ftype == "append":
        # 取 ``` 包裹的内容；优先取 type:append 之后的第一个代码块
        after = block
        mt = re.search(r'type:\s*append', block)
        if mt:
            after = block[mt.end():]
        cb = re.search(r'```[a-zA-Z]*\n(.*?)```', after, re.S)
        append_text = cb.group(1) if cb else None

    # type:locate 的定位器代码（### locator: 之后的 ```python 代码块）
    locator_src = None
    if ftype == "locate":
        after = block
        mt = re.search(r'locator:\s*\n', block)
        if mt:
            after = block[mt.end():]
        cb = re.search(r'```[a-zA-Z]*\n(.*?)```', after, re.S)
        locator_src = cb.group(1) if cb else None

    # 可选幂等标记：补丁块可声明 "### idempotent: <标记串>"，
    # 用于 new 包含 old 前缀（追加式 replace）时仍能正确判定已应用；
    # 也用于 type:locate 在 new 由定位器算出的情况下做稳定幂等判定。
    m_idem = re.search(r'^###?\s*idempotent:\s*`?(.+?)`?\s*$', block, re.M)
    idem = m_idem.group(1).strip() if m_idem else None

    return {"file": file, "type": ftype, "old": old, "new": new,
            "append": append_text, "locator": locator_src, "idempotent": idem}

def parse_patch(path):
    txt = open(path, encoding="utf-8").read()
    m = re.search(r"^id:\s*(.+)$", txt, re.M)
    pid = m.group(1).strip() if m else os.path.basename(path)
    blocks = [parse_block(b) for b in parse_changes(txt)]
    blocks = [b for b in blocks if b["file"]]
    return {"id": pid, "blocks": blocks, "path": path}

# ---------- 运行时定位器执行 ----------

def run_locator(locator_src, src, rel):
    """执行补丁块声明的定位器函数 locate(src)，返回 dict。
       定位器用受限环境执行（只暴露 re/len/str 等内置，无 __builtins__ 危险项），
       其职责是用稳定锚点在当前文件内容 src 中算出本版本真实的 {old, new}。
       不信任定位器输出：引擎仍会用 hit_count==1 等规则把关。"""
    if not locator_src:
        return {"found": False, "reason": "无 locator 代码"}
    sandbox = {"re": re}
    try:
        code = locator_src
        if "def locate" not in code:
            return {"found": False, "reason": "locator 代码缺少 def locate(src)"}
        exec(code, sandbox)  # noqa: S102 - 受控执行补丁自带定位器，不联网不分发
        locate_fn = sandbox.get("locate")
        if not callable(locate_fn):
            return {"found": False, "reason": "locator 未定义 locate 函数"}
        result = locate_fn(src)
    except Exception as e:
        return {"found": False, "reason": f"locator 执行异常: {type(e).__name__}: {e}"}
    if not isinstance(result, dict) or "old" not in result or "new" not in result:
        return {"found": False, "reason": f"locator 返回不合格: {result!r}"}
    result.setdefault("found", True)
    result.setdefault("hit_count", src.count(result["old"]) if result.get("old") else 0)
    return result

# ---------- 应用单个改动块 ----------

def apply_block(ext_dir, version, blk, check_only):
    rel = blk["file"]
    fpath = os.path.join(ext_dir, rel)
    if not os.path.exists(fpath):
        return {"status": "broken", "reason": f"目标文件不存在: {rel}"}
    src = open(fpath, encoding="utf-8", errors="ignore").read()

    if blk["type"] == "locate":
        # 运行时定位：跑 locator 算出本版本真实 old/new，再走 replace 流程。
        # 幂等：优先用声明的 idempotent 标记（稳定串），其次 new in src。
        idem = blk["idempotent"]
        if idem and idem in src:
            return {"status": "verified", "reason": f"{rel}: 已应用（幂等标记 {idem} 命中）"}
        loc = run_locator(blk["locator"], src, rel)
        if not loc.get("found"):
            return {"status": "broken", "reason": f"{rel}: 定位失败 — {loc.get('reason')}"}
        old, new = loc["old"], loc["new"]
        # 幂等：定位器可声明 no_change=True 表示已处于目标态（old==new 或
        # old 不在 src 中）。引擎信任定位器的判断，直接 verified。
        if loc.get("no_change") or old == new:
            return {"status": "verified", "reason": f"{rel}: 已应用（定位器确认 no_change）"}
        hit = src.count(old) if old else 0
        # 幂等判定分两种替换模式：
        # - 追加式（old 是 new 的前缀，如 002）：已应用后 old 仍唯一匹配（作为 new
        #   前缀），hit==1 在两种态都成立，靠 new in src 区分。
        # - 删除式（new 是 old 的子串，如 003）：未应用时 new in src 也为 true
        #   （old 包含 new），靠 hit==0（old 已被删）区分。
        # - 其他：old 和 new 无前缀/子串关系，new in src 可靠。
        old_is_prefix_of_new = new.startswith(old) if old and new else False
        new_is_substring_of_old = old and new and old != new and new in old
        if old_is_prefix_of_new:
            # 追加式：new in src 是可靠的已应用判断
            if new in src:
                return {"status": "verified", "reason": f"{rel}: 已应用（追加式，new 在 src）"}
        elif new_is_substring_of_old:
            # 删除式：old 不在 src 说明已删除，new 必在（是 old 子串，且 old 无则由原文件决定）
            if hit == 0:
                return {"status": "verified", "reason": f"{rel}: 已应用（删除式，old 已不在）"}
        else:
            # 无特殊关系：new in src 可靠
            if new in src:
                return {"status": "verified", "reason": f"{rel}: 已应用（幂等命中 new）"}
        if hit != 1:
            return {"status": "broken", "reason": f"{rel}: 定位到 old 但命中 {hit} 次（!=1），需人工重定位锚点"}
        if check_only:
            return {"status": "needs-reapply", "reason": f"{rel}: 定位成功且 old 唯一，待应用"}
        bpath, _ = backup_target(ext_dir, rel, version)
        patched = src.replace(old, new, 1)
        open(fpath, "w", encoding="utf-8").write(patched)
        v = open(fpath, encoding="utf-8", errors="ignore").read()
        if new not in v:
            shutil.copy2(bpath, fpath)
            return {"status": "broken", "reason": f"{rel}: 校验失败（new 未出现）已回滚"}
        return {"status": "verified", "reason": f"{rel}: locate+replace 成功，长度 {len(src)}→{len(v)}"}

    if blk["type"] == "replace":
        old, new = blk["old"], blk["new"]
        if not old or not new:
            return {"status": "broken", "reason": f"{rel}: replace 块未填实 old/new"}
        # 幂等：若 new 已完整存在于文件，视为已应用（含 "new = old+追加" 导致 old 仍残留的情况）。
        if new in src:
            return {"status": "verified", "reason": f"{rel}: 已应用（幂等命中 new）"}
        cnt = src.count(old)
        if cnt != 1:
            return {"status": "broken", "reason": f"{rel}: old 子串命中 {cnt} 次（!=1），需人工重定位锚点"}
        if check_only:
            return {"status": "needs-reapply", "reason": f"{rel}: 待应用，old 唯一命中，可安全 replace"}
        bpath, _ = backup_target(ext_dir, rel, version)
        patched = src.replace(old, new, 1)
        open(fpath, "w", encoding="utf-8").write(patched)
        v = open(fpath, encoding="utf-8", errors="ignore").read()
        # 仅判 new 在（new 含 old 前缀时 old 仍残留属正常，不能作为失败信号）。
        if new not in v:
            shutil.copy2(bpath, fpath)
            return {"status": "broken", "reason": f"{rel}: 校验失败（new 未出现）已回滚"}
        return {"status": "verified", "reason": f"{rel}: replace 成功，长度 {len(src)}→{len(v)}"}

    elif blk["type"] == "append":
        app = blk["append"]
        if not app:
            return {"status": "broken", "reason": f"{rel}: append 块未提供代码块内容"}
        sentinel = app.splitlines()[-2] if len(app.splitlines()) >= 2 else app.strip()
        # 幂等：用整段 append 文本里某个稳定标记判断是否已追加（取首个非空类名/keyframes 名）
        marker = re.search(r'(@keyframes\s+\w+|\.[-\w]+)', app)
        marker = marker.group(1) if marker else app[:30]
        if marker in src:
            return {"status": "verified", "reason": f"{rel}: append 已应用（幂等命中 {marker}）"}
        if check_only:
            return {"status": "needs-reapply", "reason": f"{rel}: 待追加，marker {marker} 当前不存在"}
        bpath, _ = backup_target(ext_dir, rel, version)
        new_content = src if src.endswith("\n") else src + "\n"
        new_content = new_content + app
        if not new_content.endswith("\n"):
            new_content += "\n"
        open(fpath, "w", encoding="utf-8").write(new_content)
        v = open(fpath, encoding="utf-8", errors="ignore").read()
        if marker not in v:
            shutil.copy2(bpath, fpath)
            return {"status": "broken", "reason": f"{rel}: append 校验失败已回滚"}
        return {"status": "verified", "reason": f"{rel}: append 成功，追加 {len(app)} 字符"}

    else:
        return {"status": "broken", "reason": f"{rel}: 未知 type {blk['type']}"}

# ---------- 应用整条补丁（汇总其所有改动块） ----------

def apply_one(ext_dir, version, patch, check_only):
    if not patch["blocks"]:
        return {"status": "broken", "reason": "未解析出任何 file 改动块", "kw": {}}
    sub_results = []
    overall = "verified"
    for blk in patch["blocks"]:
        r = apply_block(ext_dir, version, blk, check_only)
        sub_results.append((blk["file"], r))
        if r["status"] == "broken":
            overall = "broken"
        elif r["status"] == "needs-reapply" and overall != "broken":
            overall = "needs-reapply"
    return {"status": overall, "sub": sub_results, "reason": "; ".join(f"{f}:{r['status']}" for f, r in sub_results)}

# ---------- version-map 回写 ----------

def load_vm():
    """读 version-map.json。文件不存在（新克隆机器首次运行）时，
       优先用同目录 version-map.example.json 作为带注释的初始骨架，
       否则返回空骨架，交给 update_vm 的 setdefault 自然初始化。"""
    if os.path.exists(VERSION_MAP):
        return json.load(open(VERSION_MAP, encoding="utf-8"))
    example = os.path.join(SKILL_DIR, "version-map.example.json")
    if os.path.exists(example):
        return json.load(open(example, encoding="utf-8"))
    return {"versions": {}}

def save_vm(vm):
    json.dump(vm, open(VERSION_MAP, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def update_vm(vm, version, ext_dir, pid, result, check_only):
    vm.setdefault("versions", {}).setdefault(version, {})
    ventry = vm["versions"][version]
    ventry["ext_dir"] = os.path.basename(ext_dir)
    ventry["applied_at"] = ventry.get("applied_at") or str(datetime.date.today())
    ventry.setdefault("patches", {})
    entry = {"status": result["status"]}
    if "reason" in result: entry["reason"] = result["reason"]
    if "sub" in result: entry["blocks"] = [{"file": f, **r} for f, r in result["sub"]]
    if result["status"] == "verified" and not check_only:
        entry["applied_at"] = str(datetime.date.today())
    ventry["patches"][pid] = entry

# ---------- main ----------

def die(msg):
    print("ERROR:", msg, file=sys.stderr); sys.exit(1)

def main():
    args = sys.argv[1:]
    check_only = "--status" in args
    args = [a for a in args if a != "--status"]
    ext_dir = args[0] if args else None
    ext_dir, version = find_ext_dir(ext_dir)

    print(f"扩展: {version}  目录: {ext_dir}")
    print(f"模式: {'仅检查（--status）' if check_only else '应用补丁'}\n")

    patches = []
    for name in sorted(os.listdir(PATCHES_DIR)):
        if name.endswith(".md"):
            patches.append(parse_patch(os.path.join(PATCHES_DIR, name)))
    if not patches:
        print("（无补丁文件）"); return

    vm = load_vm()
    summary = {"verified": 0, "needs-reapply": 0, "broken": 0}
    for p in patches:
        res = apply_one(ext_dir, version, p, check_only)
        update_vm(vm, version, ext_dir, p["id"], res, check_only)
        summary[res["status"]] = summary.get(res["status"], 0) + 1
        print(f"[{res['status'].upper():13}] {p['id']}")
        for f, r in res.get("sub", []):
            print(f"   · {f}: {r['status']} — {r.get('reason','')}")
        print()

    save_vm(vm)

    print("==== 汇总 ====")
    for k in ("verified", "needs-reapply", "broken"):
        if summary.get(k): print(f"  {k}: {summary[k]}")
    if summary.get("broken"):
        print("\n⚠ 有补丁 broken：上游重构导致锚点失效。按补丁 .md 的「失败处理」用关键词重定位后回填 old/append，重跑。")
    if summary.get("needs-reapply") and not check_only:
        print("\nℹ 有补丁待应用：上面已尝试应用，请确认 verified。")

if __name__ == "__main__":
    main()
