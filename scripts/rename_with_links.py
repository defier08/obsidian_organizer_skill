# -*- coding: utf-8 -*-
"""
rename_with_links.py — 工作流 F 的确定性执行器：改名/移动 + 全库链接重写。

用法（Windows，统一用 python -X utf8 运行）：
  python rename_with_links.py --dry-run --rename "10-领域/编程/Vue/03-Vue3/疑问.md" "Vue3-疑问记录.md"
  python rename_with_links.py --rename <旧相对路径> <新文件名> [--rename ...]
  （不传 --vault 时从本目录 config.json 读 vault_root）

对应 SKILL.md 工作流 F 第 2 步的规则（全部固化于此，禁止在模型层另起炉灶）：
  1. 幂等：源不存在 / 目标已存在 → 跳过并提示（防半途冲突）
  2. 长名先于短名替换，避免互相污染（按旧文件名长度降序）
  3. 同名文件按路径区分目标：链接带路径时，路径必须命中该旧文件的真实目录才替换
  4. 完整目标名匹配：只匹配 [[ 链接内、旧名后紧跟 ] | # 的位置，防止子串误伤
  5. 只改链接不碰 frontmatter：正则要求 [[ 前缀；显式跳过文件头 YAML frontmatter 区域
  6. 无路径裸链接且旧名存在多个同名文件（或唯一同名不在计划内）→ 报歧义、跳过，提示改为带路径链接
  7. --dry-run：只打印计划，不写任何文件、不改任何名

退出码：0 = 全部执行/计划完成；2 = 参数或配置错误；1 = 存在歧义跳过。
"""
import io
import json
import os
import re
import sys

SKIP_DIRS = {'.git', '.obsidian', '.trash', '.agents', '.claude', '.opencode',
             'copilot', '.codebuddy', '.preview', 'node_modules'}
SKIP_FILES = {'待记录缓冲区.md', '_taxonomy.generated.md'}


def log(*a):
    sys.stdout.write(' '.join(str(x) for x in a) + '\n')


def read(p):
    try:
        return io.open(p, encoding='utf-8').read()
    except Exception:
        return ''


def write(p, s):
    io.open(p, 'w', encoding='utf-8', newline='\n').write(s)


def vault_root():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
            if f.endswith('.md') and f not in SKIP_FILES:
                yield os.path.join(r, f)


def norm_rel(p, root):
    return os.path.relpath(p, root).replace('\\', '/')


def build_index(root):
    """basename(去.md) -> [相对路径列表]，用于同名检测与路径归属判断。"""
    idx = {}
    for p in walk_md(root):
        base = os.path.basename(p)[:-3]
        idx.setdefault(base, []).append(norm_rel(p, root))
    return idx


def split_frontmatter(text):
    """若文本以 --- 开头，返回 (frontmatter区, 正文区)；否则 ('', text)。"""
    if text.startswith('---\n'):
        end = text.find('\n---\n', 4)
        if end != -1:
            return text[:end + 1], text[end + 1:]
    return '', text


def parse_args(argv):
    dry_run = False
    root = None
    renames = []  # [(old_rel, new_name_without_md)]
    i = 0
    while i < len(argv):
        if argv[i] == '--dry-run':
            dry_run = True
            i += 1
        elif argv[i] == '--vault' and i + 1 < len(argv):
            root = argv[i + 1]
            i += 2
        elif argv[i] == '--rename' and i + 2 < len(argv):
            renames.append((argv[i + 1].replace('\\', '/'), argv[i + 2]))
            i += 3
        else:
            i += 1
    return dry_run, root, renames


def main():
    dry_run, arg_root, renames = parse_args(sys.argv[1:])
    if not renames:
        log(__doc__)
        sys.exit(2)
    root = arg_root or vault_root()
    if not root or not os.path.isdir(root):
        log('未找到 Vault 根（检查 config.json 的 vault_root 或传 --vault <路径>）。')
        sys.exit(2)

    idx = build_index(root)
    plan = []  # (old_rel, new_rel)
    for old_rel, new_name in renames:
        old_rel = old_rel.strip('/')
        new_name = new_name.strip().replace('.md', '')
        if not new_name:
            log(f'  [跳过] 新名为空: {old_rel}')
            continue
        old_path = os.path.join(root, old_rel.replace('/', os.sep))
        if not os.path.isfile(old_path):
            log(f'  [跳过] 源不存在: {old_rel}')
            continue
        dst_path = os.path.join(os.path.dirname(old_path), new_name + '.md')
        if os.path.exists(dst_path):
            log(f'  [跳过] 目标已存在: {norm_rel(dst_path, root)}')
            continue
        plan.append((old_rel, norm_rel(dst_path, root)))

    if not plan:
        log('无可执行改名。')
        sys.exit(0)

    # 长名先于短名替换（按旧文件名长度降序），避免互相污染
    plan.sort(key=lambda x: -len(os.path.basename(x[0])[:-3]))
    plan_old_rels = {r for r, _ in plan}
    plan_old_names = {os.path.basename(r)[:-3] for r, _ in plan}

    # ---------- 链接重写 ----------
    ambiguous = []
    total_hits = 0
    for p in walk_md(root):
        text = read(p)
        if not text:
            continue
        fm, body = split_frontmatter(text)
        new_body = body
        rel = norm_rel(p, root)
        for old_rel, new_rel in plan:
            old_name = os.path.basename(old_rel)[:-3]
            new_name = os.path.basename(new_rel)[:-3]
            old_dir = os.path.dirname(old_rel)
            # 完整目标名匹配：[[ 必须存在，旧名后紧跟 ] | #
            pat = re.compile(r'\[\[([^\]|#]*/)?' + re.escape(old_name) + r'(?=[\]|#])')
            replaced = [0]  # 只统计实际替换次数（repl 返回新串才算）

            def repl(m, _old_name=old_name, _new_name=new_name, _old_dir=old_dir,
                     _old_rel=old_rel, _plan_old_rels=plan_old_rels, _idx=idx,
                     _rel=rel, _ambiguous=ambiguous, _replaced=replaced):
                prefix = m.group(1)  # 链接路径前缀（含尾部 /），可能为 None
                if prefix is None:
                    # 无路径裸链接：仅当旧名唯一 且 该文件正在被改名 → 安全替换
                    same = _idx.get(_old_name, [])
                    if len(same) == 1 and same[0] in _plan_old_rels:
                        _replaced[0] += 1
                        return _new_name
                    _ambiguous.append(f'{_rel}: [[{_old_name}]] 同名/未计划，跳过，请改为带路径链接')
                    return m.group(0)
                # 带路径：路径参与匹配——与 Obsidian 解析一致，真实目录以链接路径结尾即命中
                # （如 [[部署配置/旧名]] 命中 .../luo3煤炭封存/部署配置/旧名.md）
                link_dir = prefix.rstrip('/')
                if link_dir == _old_dir or (_old_dir and _old_dir.endswith(link_dir)):
                    _replaced[0] += 1
                    return prefix + _new_name
                return m.group(0)

            new_body = pat.sub(repl, new_body)
            n = replaced[0]
            if n:
                total_hits += n
                log(f'  [{"计划-" if dry_run else ""}重写] {rel}: 链接到 {old_name} 实际替换 {n} 处')
        if new_body != body and not dry_run:
            write(p, fm + new_body)

    # ---------- 改名（dry-run 只输出） ----------
    log('===== 改名 =====')
    for old_rel, new_rel in plan:
        if dry_run:
            log(f'  [计划] {old_rel} -> {new_rel}')
        else:
            os.rename(os.path.join(root, old_rel.replace('/', os.sep)),
                      os.path.join(root, new_rel.replace('/', os.sep)))
            log(f'  [改名] {old_rel} -> {new_rel}')

    if ambiguous:
        log('===== 歧义跳过（需人工处理）=====')
        for a in sorted(set(ambiguous)):
            log('  ' + a)
        log('提示：把裸链接改为带路径 [[目录/新名]] 后再跑一次。')
        sys.exit(1)

    log(f'链接重写总计命中 {total_hits} 处。')
    if dry_run:
        log('（--dry-run：以上为计划，未写任何文件）')
    else:
        log('完成。请运行 scripts/verify_links.py 验证残留断链 = 0。')
    sys.exit(0)


if __name__ == '__main__':
    main()
