#!/usr/bin/env python3
"""
从本机备份恢复某个版本的扩展原文件。
备份目录默认为 ~/.claude/patch-backups/<version>/（由 apply-patches.py 首次打补丁前当场生成）。
若新目录无备份，回退查 skill 目录下旧的 rollback/<version>/（历史遗留，含扩展原始文件）。

用法：
  python3 rollback.py <version> [target_rel]   # 恢复某版本全部/指定文件
  python3 rollback.py --list                   # 列出可用备份
"""
import os, sys, shutil

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 本机即时生成的备份（新方案，不入库）
ROLLBACK_DIR = os.path.expanduser("~/.claude/patch-backups")
# 旧方案遗留备份目录（skill 内，含扩展原始文件，仅本机留存，不入库）
LEGACY_ROLLBACK_DIR = os.path.join(SKILL_DIR, "rollback")
EXTENSIONS_ROOT = os.path.expanduser("~/.vscode/extensions")

def _backup_dir_for(version):
    """返回该版本实际存在的备份目录：优先新目录 patch-backups，回退旧目录 skill/rollback。"""
    for base in (ROLLBACK_DIR, LEGACY_ROLLBACK_DIR):
        d = os.path.join(base, version)
        if os.path.isdir(d) and os.listdir(d):
            return d, base
    return None, None

def list_backups():
    any_found = False
    for base, label in ((ROLLBACK_DIR, "~/.claude/patch-backups"),
                        (LEGACY_ROLLBACK_DIR, "skill/rollback (旧)")):
        if not os.path.isdir(base):
            continue
        for v in sorted(os.listdir(base)):
            d = os.path.join(base, v)
            if os.path.isdir(d) and os.listdir(d):
                any_found = True
                print(f"[{label}] {v}/")
                for f in os.listdir(d):
                    print(f"  {f}")
    if not any_found:
        print("无本机备份。运行 apply-patches.py 应用补丁后会自动生成备份。")

def restore(version, target_rel=None):
    bdir, base = _backup_dir_for(version)
    if not bdir:
        die(f"无版本 {version} 的本机备份（既不在 {ROLLBACK_DIR} 也不在 {LEGACY_ROLLBACK_DIR}）。\n"
            f"请先在装有该版本扩展的机器上运行 apply-patches.py 生成备份。")
    vm = None
    try:
        import json
        vm = json.load(open(os.path.join(SKILL_DIR, "version-map.json"), encoding="utf-8"))
    except Exception: pass
    ext_dirname = None
    if vm:
        ext_dirname = vm.get("versions", {}).get(version, {}).get("ext_dir")
    if not ext_dirname:
        # 兜底：按版本号拼
        ext_dirname = f"anthropic.claude-code-{version}-darwin-arm64"
    ext_dir = os.path.join(EXTENSIONS_ROOT, ext_dirname)
    if not os.path.isdir(ext_dir):
        die(f"扩展目录不存在（可能已升级/移除）: {ext_dir}\n备份文件留在 {bdir}，可手动取用。")

    restored = 0
    for fname in sorted(os.listdir(bdir)):
        rel = fname.replace("__", "/")
        if target_rel and rel != target_rel:
            continue
        dst = os.path.join(ext_dir, rel)
        shutil.copy2(os.path.join(bdir, fname), dst)
        print(f"已恢复: {rel}  ←  {os.path.relpath(os.path.join(bdir, fname), os.path.expanduser('~'))}")
        restored += 1
    if restored == 0:
        print(f"版本 {version} 下未匹配到要恢复的文件: {target_rel or '(全部)'}")
    else:
        print(f"\n共恢复 {restored} 个文件。请重载 VSCode 窗口使其生效。")
        print("提示：回滚后对应补丁状态已失效，可重跑 apply-patches.py 重新应用。")

def die(msg):
    print("ERROR:", msg, file=sys.stderr); sys.exit(1)

def main():
    args = sys.argv[1:]
    if not args or args[0] == "--list":
        list_backups(); return
    version = args[0]
    target_rel = args[1] if len(args) > 1 else None
    restore(version, target_rel)

if __name__ == "__main__":
    main()
