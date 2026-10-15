# -*- coding: utf-8 -*-
"""
Obsidian Vault 健康体检：空壳文件 / 相似重复 / 命名不合规 / 根目录散落 / 断链 一键扫描。

用法（Windows，统一用 python -X utf8 运行）：
  python health-check.py                 # 全库体检（Vault 路径从本目录 config.json 读取）
  python health-check.py --vault <路径>  # 指定 Vault 根
  python health-check.py --dir <子路径>  # 只体检某个子目录（相对 Vault 根）
  python health-check.py --head <文件路径> [N]   # 输出文件头部摘要（N 字符，默认 200）

输出为精简汇总，供模型逐项决策；大清单只列前若干条并给总数。

退出码（与 scripts/vault_common.py 的约定一致）：
  0 = 无硬问题（空壳/重复/命名/散落只是报告项，不影响退出码）
  1 = 有硬问题：真断链数量 > 0，或存在读取失败的文件
  2 = 参数或配置错误（如 --head 条数非法、找不到 Vault 根）
"""
import difflib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vault_common as vc  # noqa: E402  （与本脚本同目录，共用配置与读取语义）

log = vc.log
walk_md = vc.walk_md
PLACEHOLDERS = vc.PLACEHOLDERS


def body_text_len(text):
    """正文字符数（剥离 YAML frontmatter）。"""
    _, body = vc.split_frontmatter(text)
    return len(body.strip())


def norm(name):
    n = re.sub(r'[（(].*?[)）]', '', name)
    n = re.sub(r'[^a-z0-9\u4e00-\u9fff]', '', n.lower())
    return n


def scan_empty(root, sub):
    """返回 (空壳/过短文件, 读失败列表)。

    读失败不再被当成「空文件」——两者混同会产生假阳性空壳报告。
    """
    hits = []
    failed = []
    for p in walk_md(root, sub):
        text, err = vc.read_text(p)
        if err:
            if err != 'missing':
                failed.append((vc.norm_rel(p, root), err))
            continue
        bl = body_text_len(text)
        if bl == 0:
            hits.append((p, 0))
        elif bl < 80:
            hits.append((p, bl))
    return hits, failed


def scan_dup(root, sub):
    """规范化后同名 / 高度相似（ratio>0.85）的文件对。

    相似度比较先按「名称长度区间」分桶预筛（并兼顾相邻桶），只在桶内做
    SequenceMatcher，避免原实现对全库两两比较的 O(n²) 开销。
    """
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
    # 高度相似：按长度区间分桶，桶内 + 相邻桶比较
    buckets = {}
    for n, p in entries:
        buckets.setdefault(len(n) // 4, []).append((n, p))
    shown = set()
    for k in sorted(buckets):
        items = buckets[k] + buckets.get(k + 1, [])
        for i in range(len(items)):
            a, ap = items[i]
            for j in range(i + 1, len(items)):
                b, bp = items[j]
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
        dirs[:] = [d for d in dirs if d not in vc.SKIP_DIRS]
        mds = [f[:-3] for f in files if f.endswith('.md') and f not in vc.SKIP_FILES]
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
    """断链：指向不存在 .md 的 [[链接]]（跳过 ![[ 嵌入、非 md 目标、模板占位符形态）。
    与 verify_links.py 对齐：带路径链接校验路径真伪；无路径链接按 basename + 同名歧义处理。
    返回 (断链列表, 读失败列表)——读失败的文件不再被静默当作「无链接」。"""
    idx = {}
    for p in walk_md(root):
        base = os.path.basename(p)[:-3]
        rel = os.path.relpath(p, root).replace('\\', '/')
        idx.setdefault(base, []).append(rel)
    bad = []
    failed = []
    for p in walk_md(root, sub):
        c, err = vc.read_text(p)
        if err:
            if err != 'missing':
                failed.append((vc.norm_rel(p, root), err))
            continue
        for m in re.finditer(r'(?<!\!)\[\[([^\]]+)\]\]', c):
            link = m.group(1).strip()
            target = link.split('#')[0].split('|')[0].strip()
            if not target:
                continue
            if re.search(r'\.(png|jpg|jpeg|gif|svg|pdf|webp|mp3|mp4|html)$', target, re.I):
                continue
            if '/' in target:
                # 带路径：Obsidian 解析——basename 唯一时任何路径写法都有效；
                # 多个同名文件时路径参与区分（真实相对路径去 .md 后以链接 target 结尾）
                t_no_md = target[:-4] if target.endswith('.md') else target
                if t_no_md.endswith('/'):
                    # Obsidian 文件夹链接 [[目录/]]：目录真实存在即有效
                    if os.path.isdir(os.path.join(root, t_no_md.replace('/', os.sep))):
                        continue
                    bad.append((os.path.relpath(p, root), m.group(1)))
                    continue
                name = t_no_md.rsplit('/', 1)[-1]
                same = idx.get(name, [])
                if not same:
                    bad.append((os.path.relpath(p, root), m.group(1)))
                elif len(same) > 1 and not any(r[:-3].endswith(t_no_md) for r in same):
                    bad.append((os.path.relpath(p, root), m.group(1)))
            else:
                name = target.replace('.md', '')
                if name not in idx and name not in PLACEHOLDERS:
                    bad.append((os.path.relpath(p, root), m.group(1)))
    return bad, failed


def main():
    args = sys.argv[1:]
    if any(a in ('-h', '--help') for a in args):
        log(__doc__)
        return vc.EXIT_OK

    root = None
    sub = None
    head_path = None
    head_n = 200
    i = 0
    while i < len(args):
        a = args[i]
        if a == '--vault' and i + 1 < len(args):
            root = args[i + 1]
            i += 2
        elif a == '--dir' and i + 1 < len(args):
            sub = args[i + 1]
            i += 2
        elif a == '--head' and i + 1 < len(args):
            head_path = args[i + 1]
            if i + 2 < len(args) and not args[i + 2].startswith('-'):
                raw = args[i + 2]
                if not raw.isdigit():
                    log(f'--head 的字符数必须是数字，收到: {raw}')
                    log('用法: python health-check.py --head <文件路径> [字符数]')
                    return vc.EXIT_USAGE
                head_n = int(raw)
                i += 3
            else:
                i += 2
        else:
            log(f'未知参数: {a}')
            log('用法: python health-check.py [--vault <路径>] [--dir <子路径>] [--head <文件路径> [字符数]]')
            return vc.EXIT_USAGE

    if head_path:
        text, err = vc.read_text(head_path)
        if err == 'missing':
            log('文件不存在:', head_path)
            return vc.EXIT_USAGE
        if err:
            log('文件不可读:', head_path, '—', err)
            return vc.EXIT_FINDINGS
        _, body = vc.split_frontmatter(text)
        head = '\n'.join(l for l in body.split('\n') if l.strip())[:head_n]
        log('===== 头部摘要:', head_path, '=====')
        log(head)
        return vc.EXIT_OK

    root = root or vc.resolve_vault_root()
    if not root or not os.path.isdir(root):
        log('未找到 Vault 根（检查 config.json 的 vault_root 或传 --vault）。')
        return vc.EXIT_USAGE
    log(f'===== Vault 健康体检: {root}' + (f' (子目录 {sub})' if sub else '') + ' =====')

    log('\n[1] 空壳文件（正文 < 80 字符）')
    empty, failed = scan_empty(root, sub)
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
    bad, link_failed = scan_links(root, sub)
    failed.extend(link_failed)
    if not bad:
        log('  0 个')
    else:
        log(f'  共 {len(bad)} 个，前 20 条:')
        for rel, link in bad[:20]:
            log(f'  {rel} -> {link}')

    unreadable = sorted({rel for rel, _ in failed})
    if unreadable:
        log('\n[6] 读取失败的文件（未参与以上判断，请检查权限/编码）')
        for rel in unreadable[:20]:
            log(f'  {rel} — {[w for r, w in failed if r == rel][0]}')
        if len(unreadable) > 20:
            log(f'  ... 共 {len(unreadable)} 个')

    log('\n===== 体检完成 =====')
    if bad or unreadable:
        log(f'结论：有硬问题（真断链 {len(bad)} 个 / 读取失败 {len(unreadable)} 个）→ 退出码 1')
        return vc.EXIT_FINDINGS
    log('结论：无硬问题 → 退出码 0（空壳/重复/命名等仅为报告项，不视为失败）')
    return vc.EXIT_OK


if __name__ == '__main__':
    sys.exit(main())
