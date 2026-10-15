# -*- coding: utf-8 -*-
"""
Obsidian Vault 断链验证：列出所有指向不存在 .md 的 [[链接]]。

用法（Windows，统一用 python -X utf8 运行）：
  python verify_links.py                        # Vault 路径从本目录 config.json 读取
  python verify_links.py --vault <路径>          # 指定 Vault 根
  python verify_links.py --targets <名1> <名2>   # 只检查这些目标是否存在（改名后验证用）

校验规则（与 SKILL.md 工作流 F 第 2 步对齐）：
  - 带路径的链接 [[路径/目标]]：校验「路径 + 文件名」是否真实存在（路径真伪），
    不再退化为 basename 级判断 —— 同名文件也能区分
  - 无路径的链接 [[目标]]：按 basename 查；若存在多个同名文件 → 标记「同名歧义」（提示，不算断链）
  - 跳过 ![[ 嵌入链接（图片附件嵌入正常显示）
  - 跳过指向 .png/.jpg/.pdf 等非 md 目标的链接
  - 模板占位符形态（[[文件名]]/[[概念]]/[[链接]]）统计为"疑似占位"

退出码（与 scripts/vault_common.py 的约定一致）：
  0 = 无真断链；1 = 存在真断链或读取失败的文件；2 = 参数或配置错误。
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vault_common as vc  # noqa: E402  （与本脚本同目录，共用配置与读取语义）

log = vc.log
walk_md = vc.walk_md
PLACEHOLDERS = vc.PLACEHOLDERS
norm_rel = vc.norm_rel


def build_index(root):
    """basename(去.md) -> [相对路径列表]（含 .md 后缀），支持路径真伪与同名检测。"""
    idx = {}
    for p in walk_md(root):
        base = os.path.basename(p)[:-3]
        idx.setdefault(base, []).append(norm_rel(p, root))
    return idx


def resolve_target(link):
    """从链接文本解析出链接目标（去别名/锚点），返回 (target, has_path)。"""
    t = link.split('#')[0].split('|')[0].strip()
    return t, ('/' in t)


def main():
    args = sys.argv[1:]
    root = None
    targets = None
    i = 0
    while i < len(args):
        if args[i] == '--vault' and i + 1 < len(args):
            root = args[i + 1]
            i += 2
        elif args[i] == '--targets':
            targets = set(args[i + 1:])
            break
        else:
            i += 1
    if not root:
        root = vc.resolve_vault_root()
    if not root or not os.path.isdir(root):
        log('未找到 Vault 根（检查 config.json 的 vault_root 或传 --vault）。')
        sys.exit(vc.EXIT_USAGE)

    idx = build_index(root)

    if targets is not None:
        log('===== 目标存在性检查 =====')
        miss = []
        ambig = []
        for t in sorted(targets):
            t = vc.strip_md(t)
            same = idx.get(t, [])
            if not same:
                miss.append(t)
            elif len(same) > 1:
                ambig.append((t, same))
        for t in sorted(miss):
            log('  ⚠️ 目标不存在:', t)
        for t, same in ambig:
            log(f'  ⚠️ 同名歧义: {t} -> {len(same)} 个文件，请用带路径形式区分')
        log('  缺失', len(miss), '个 / 歧义', len(ambig), '个 / 共', len(targets), '个')
        sys.exit(vc.EXIT_FINDINGS if miss else vc.EXIT_OK)

    log(f'===== 断链验证: {root} =====')
    bad = []
    placeholder = []
    ambiguous = []
    unreadable = []
    for p in walk_md(root):
        c, err = vc.read_text(p)
        if err:
            if err != 'missing':
                unreadable.append((norm_rel(p, root), err))
            continue
        for m in re.finditer(r'(?<!\!)\[\[([^\]]+)\]\]', c):
            link = m.group(1).strip()
            target, has_path = resolve_target(link)
            if not target:
                continue
            if re.search(r'\.(png|jpg|jpeg|gif|svg|pdf|webp|mp3|mp4|html)$', target, re.I):
                continue
            if has_path:
                # 带路径：Obsidian 解析——basename 唯一时任何路径写法都有效（按末段解析）；
                # 存在多个同名文件时，路径才参与区分（真实相对路径去 .md 后以链接 target 结尾）
                t_no_md = target[:-4] if target.endswith('.md') else target
                if t_no_md.endswith('/'):
                    # Obsidian 文件夹链接 [[目录/]]：目录真实存在即有效
                    if os.path.isdir(os.path.join(root, t_no_md.replace('/', os.sep))):
                        continue
                    bad.append((os.path.relpath(p, root), link))
                    continue
                name = t_no_md.rsplit('/', 1)[-1]
                same = idx.get(name, [])
                if not same:
                    bad.append((os.path.relpath(p, root), link))
                    continue
                if len(same) == 1:
                    continue
                if any(r[:-3].endswith(t_no_md) for r in same):
                    continue
                bad.append((os.path.relpath(p, root), link))
            else:
                # 无路径：basename 查找
                name = vc.strip_md(target)
                same = idx.get(name, [])
                if not same:
                    if name in PLACEHOLDERS or re.fullmatch(r'[A-Za-z]', name):
                        placeholder.append((os.path.relpath(p, root), link))
                    else:
                        bad.append((os.path.relpath(p, root), link))
                elif len(same) > 1:
                    ambiguous.append((os.path.relpath(p, root), link, same))

    log(f'真断链 {len(bad)} 个:')
    for rel, link in bad[:40]:
        log(f'  {rel} -> {link}')
    if len(bad) > 40:
        log(f'  ... 共 {len(bad)} 个')
    log(f'\n同名歧义（带路径后可消除）{len(ambiguous)} 个:')
    for rel, link, same in ambiguous[:10]:
        log(f'  {rel} -> {link} （{len(same)} 个同名文件）')
    log(f'\n疑似占位符（模板/学习路径未建卡片，通常无害）{len(placeholder)} 个:')
    for rel, link in placeholder[:10]:
        log(f'  {rel} -> {link}')
    if unreadable:
        log(f'\n读取失败的文件（未参与断链判断，请检查权限/编码）{len(unreadable)} 个:')
        for rel, why in unreadable[:20]:
            log(f'  {rel} — {why}')
    log('\n===== 验证完成 =====')
    log(f'结论：真断链 {len(bad)} 个 / 读取失败 {len(unreadable)} 个')
    sys.exit(vc.EXIT_FINDINGS if (bad or unreadable) else vc.EXIT_OK)


if __name__ == '__main__':
    main()
