# -*- coding: utf-8 -*-
"""
Obsidian Vault 健康体检：空壳文件 / 相似重复 / 命名不合规 / 根目录散落 / 断链 一键扫描。

用法（Windows，统一用 python -X utf8 运行）：
  python health-check.py                 # 全库体检（Vault 路径从本目录 config.json 读取）
  python health-check.py --vault <路径>  # 指定 Vault 根
  python health-check.py --dir <子路径>  # 只体检某个子目录（相对 Vault 根）
  python health-check.py --head <文件路径> [N]   # 输出文件头部摘要（N 字符，默认 200）

输出为精简汇总，供模型逐项决策；大清单只列前若干条并给总数。
"""
import io
import json
import os
import re
import sys
import difflib

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


def walk_md(root, sub=None):
    base = root if sub is None else os.path.join(root, sub)
    for r, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if f.endswith('.md'):
                yield os.path.join(r, f)


def body_len(p):
    c = read(p)
    if not c:
        return 0
    lines = c.split('\n')
    if lines and lines[0].strip() == '---':
        i = 1
        while i < len(lines) and lines[i].strip() != '---':
            i += 1
        lines = lines[i + 1:]
    return len(''.join(lines).strip())


def norm(name):
    n = re.sub(r'[（(].*?[)）]', '', name)
    n = re.sub(r'[^a-z0-9\u4e00-\u9fff]', '', n.lower())
    return n


def scan_empty(root, sub):
    hits = []
    for p in walk_md(root, sub):
        bl = body_len(p)
        if bl == 0:
            hits.append((p, 0))
        elif bl < 80:
            hits.append((p, bl))
    return hits


def scan_dup(root, sub):
    """规范化后同名 / 高度相似（ratio>0.85）的文件对"""
    entries = []
    for p in walk_md(root, sub):
        n = norm(os.path.basename(p)[:-3])
        if n:
            entries.append((n, p))
    # 完全同名（规范化后）
    groups = {}
    for n, p in entries:
        groups.setdefault(n, []).append(p)
    pairs = []
    for n, ps in groups.items():
        if len(ps) > 1:
            pairs.append(('同名', n, ps))
    # 高度相似
    shown = set()
    for i in range(len(entries)):
        for j in range(i + 1, len(entries)):
            a, ap = entries[i]
            b, bp = entries[j]
            if a == b:
                continue
            if difflib.SequenceMatcher(None, a, b).ratio() > 0.85:
                key = tuple(sorted([ap, bp]))
                if key not in shown:
                    shown.add(key)
                    pairs.append(('相似', f'{a} <-> {b}', [ap, bp]))
    return pairs


def scan_naming(root, sub):
    """目录内多数文件共享某前缀（>=50% 且目录 >=4 篇），列出不合规文件"""
    hits = []
    base = root if sub is None else os.path.join(root, sub)
    for r, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        mds = [f[:-3] for f in files if f.endswith('.md')]
        if len(mds) < 4:
            continue
        firsts = {}
        for n in mds:
            tok = re.split(r'[-_]', n, maxsplit=1)[0]
            firsts[tok] = firsts.get(tok, 0) + 1
        prefix, cnt = max(firsts.items(), key=lambda kv: kv[1])
        if cnt >= len(mds) * 0.5:
            bad = [n for n in mds if not n.startswith(prefix)]
            for n in bad:
                hits.append((os.path.join(r, n + '.md'), f'目录规范前缀 "{prefix}-"，该文件不合规'))
    return hits


def scan_root_scatter(root):
    hits = [p for p in walk_md(root) if os.path.dirname(p) == root]
    return hits


def scan_links(root, sub=None):
    """断链：指向不存在 .md 的 [[链接]]（跳过 ![[ 嵌入、非 md 目标、模板占位符形态）"""
    all_names = set()
    for p in walk_md(root):
        all_names.add(os.path.basename(p)[:-3])
    bad = []
    for p in walk_md(root, sub):
        c = read(p)
        for m in re.finditer(r'(?<!\!)\[\[([^\]]+)\]\]', c):
            link = m.group(1).strip()
            target = link.split('#')[0].split('|')[0].split('/')[-1].replace('.md', '').strip()
            if not target:
                continue
            if not re.search(r'\.(png|jpg|jpeg|gif|svg|pdf|webp|mp3|mp4)$', target, re.I) \
               and target not in all_names:
                bad.append((os.path.relpath(p, root), m.group(1)))
    return bad


def main():
    args = sys.argv[1:]
    if args and args[0] == '--head':
        path = args[1]
        n = int(args[2]) if len(args) > 2 else 200
        c = read(path)
        if not c:
            log('空文件或不可读:', path)
            return
        lines = c.split('\n')
        if lines and lines[0].strip() == '---':
            i = 1
            while i < len(lines) and lines[i].strip() != '---':
                i += 1
            lines = lines[i + 1:]
        head = '\n'.join(l for l in lines if l.strip())[:n]
        log('===== 头部摘要:', path, '=====')
        log(head)
        return

    root = None
    sub = None
    i = 0
    while i < len(args):
        if args[i] == '--vault' and i + 1 < len(args):
            root = args[i + 1]
            i += 2
        elif args[i] == '--dir' and i + 1 < len(args):
            sub = args[i + 1]
            i += 2
        else:
            i += 1
    if not root:
        root = vault_root()
    if not root or not os.path.isdir(root):
        log('未找到 Vault 根（检查 config.json 的 vault_root 或传 --vault）。')
        return
    log(f'===== Vault 健康体检: {root}' + (f' (子目录 {sub})' if sub else '') + ' =====')

    log('\n[1] 空壳文件（正文 < 80 字符）')
    empty = scan_empty(root, sub)
    if not empty:
        log('  无')
    for p, bl in empty[:20]:
        log(f'  {os.path.relpath(p, root)} ({bl} 字符)')
    if len(empty) > 20:
        log(f'  ... 共 {len(empty)} 个')

    log('\n[2] 重复/相似文件（规范化同名或相似度 > 0.85）')
    dups = scan_dup(root, sub)
    if not dups:
        log('  无')
    for kind, name, ps in dups[:30]:
        log(f'  [{kind}] {name}')
        for p in ps:
            log(f'      {os.path.relpath(p, root)}')
    if len(dups) > 30:
        log(f'  ... 共 {len(dups)} 组')

    log('\n[3] 命名不合规（目录有规范前缀但文件不遵循）')
    naming = scan_naming(root, sub)
    if not naming:
        log('  无')
    for p, why in naming[:20]:
        log(f'  {os.path.relpath(p, root)} — {why}')
    if len(naming) > 20:
        log(f'  ... 共 {len(naming)} 个')

    if sub is None:
        log('\n[4] Vault 根目录散落文件')
        scatter = scan_root_scatter(root)
        if not scatter:
            log('  无')
        for p in scatter:
            log(f'  {os.path.basename(p)}')

    log('\n[5] 断链统计（指向不存在 .md 的 [[链接]]）')
    bad = scan_links(root, sub)
    if not bad:
        log('  0 个')
    else:
        log(f'  共 {len(bad)} 个，前 20 条:')
        for rel, link in bad[:20]:
            log(f'  {rel} -> {link}')
    log('\n===== 体检完成 =====')


if __name__ == '__main__':
    main()
