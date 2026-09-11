# -*- coding: utf-8 -*-
"""
Obsidian Vault 断链验证：列出所有指向不存在 .md 的 [[链接]]。

用法（Windows，统一用 python -X utf8 运行）：
  python verify_links.py                        # Vault 路径从本目录 config.json 读取
  python verify_links.py --vault <路径>          # 指定 Vault 根
  python verify_links.py --targets <名1> <名2>   # 只检查这些目标是否存在被引用（改名后验证用）

判定规则：
  - 跳过 ![[ 嵌入链接（图片附件嵌入正常显示）
  - 跳过指向 .png/.jpg/.pdf 等非 md 目标的链接
  - 模板占位符形态（[[文件名]]/[[概念]]/[[链接]]）也统计但归为"疑似占位"
退出码：0 = 无真断链；1 = 存在真断链（供脚本联动判断）。
"""
import io
import json
import os
import re
import sys

SKIP_DIRS = {'.git', '.obsidian', '.trash', '.agents', '.claude', '.opencode',
             'copilot', '.codebuddy', '.preview', 'node_modules'}


def log(*a):
    sys.stdout.write(' '.join(str(x) for x in a) + '\n')


def read(p):
    try:
        return io.open(p, encoding='utf-8').read()
    except Exception:
        return ''


def vault_root():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # skill 根目录（config.json 所在）
    cfg = os.path.join(here, 'config.json')
    if os.path.exists(cfg):
        try:
            c = json.load(io.open(cfg, encoding='utf-8'))
            if c.get('vault_root'):
                return c['vault_root']
        except Exception:
            pass
    return None


def walk_md(root):
    for r, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if f.endswith('.md'):
                yield os.path.join(r, f)


PLACEHOLDERS = {'文件名', '概念', '链接', '别名', '标题'}


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
        root = vault_root()
    if not root or not os.path.isdir(root):
        log('未找到 Vault 根（检查 config.json 的 vault_root 或传 --vault）。')
        sys.exit(2)

    all_names = set()
    for p in walk_md(root):
        all_names.add(os.path.basename(p)[:-3])

    if targets is not None:
        log('===== 目标存在性检查 =====')
        miss = [t for t in targets if t not in all_names]
        for t in sorted(miss):
            log('  ⚠️ 目标不存在:', t)
        log('  缺失', len(miss), '个 / 共', len(targets), '个')
        sys.exit(1 if miss else 0)

    log(f'===== 断链验证: {root} =====')
    bad = []
    placeholder = []
    for p in walk_md(root):
        c = read(p)
        for m in re.finditer(r'(?<!\!)\[\[([^\]]+)\]\]', c):
            link = m.group(1).strip()
            target = link.split('#')[0].split('|')[0].split('/')[-1].replace('.md', '').strip()
            if not target:
                continue
            if re.search(r'\.(png|jpg|jpeg|gif|svg|pdf|webp|mp3|mp4)$', target, re.I):
                continue
            if target in all_names:
                continue
            if target in PLACEHOLDERS or re.fullmatch(r'[A-Za-z]', target):
                placeholder.append((os.path.relpath(p, root), m.group(1)))
            else:
                bad.append((os.path.relpath(p, root), m.group(1)))

    log(f'真断链 {len(bad)} 个:')
    for rel, link in bad[:40]:
        log(f'  {rel} -> {link}')
    if len(bad) > 40:
        log(f'  ... 共 {len(bad)} 个')
    log(f'\n疑似占位符（模板/学习路径未建卡片，通常无害）{len(placeholder)} 个:')
    for rel, link in placeholder[:10]:
        log(f'  {rel} -> {link}')
    log('\n===== 验证完成 =====')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
