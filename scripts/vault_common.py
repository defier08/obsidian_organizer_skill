# -*- coding: utf-8 -*-
"""
obsidian-vault-organizer / scripts/vault_common.py

脚本层唯一的基础模块：配置读取、文件读取语义、跳过清单、退出码与资源根解析。

约定：
  - 本模块必须与其它脚本同处 scripts/ 目录，脚本内以 `import vault_common as vc` 引用
  - 只使用标准库；不含个人路径、用户名或特定 AI 产品名
  - 配置来自 skill 根目录（scripts/ 的上一级）的 config.json

退出码约定（全部脚本一致）：
  0 = 无硬问题
  1 = 有发现（真断链 / 读失败 / 目标缺失）——属正常结果，不是脚本崩溃
  2 = 参数或配置错误
"""
import io
import json
import os
import sys
import tempfile

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2

# 工具自动生成目录 + 本 skill 自身产物目录：一律不参与扫描
SKIP_DIRS = {
    '.git', '.obsidian', '.trash', '.agents', '.claude', '.opencode',
    'copilot', '.codebuddy', '.preview', 'node_modules',
    '待记录快照', '.organizer-backup',
}
# 本 skill 自身的产物文件：不参与四层模型，体检/断链扫描一律豁免
SKIP_FILES = {'待记录缓冲区.md', '_taxonomy.generated.md'}
PLACEHOLDERS = {'文件名', '概念', '链接', '别名', '标题', '笔记名', '相关笔记1', '相关笔记2'}

DEFAULT_RESOURCE_ROOT = '30-资源'
BUFFER_NAME = '待记录缓冲区.md'
SNAPSHOT_DIR_NAME = '待记录快照'

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(SKILL_ROOT, 'config.json')


def log(*a):
    sys.stdout.write(' '.join(str(x) for x in a) + '\n')


def warn(msg):
    """统一告警出口：只写 stderr，不中断主流程。"""
    sys.stderr.write('WARN: ' + str(msg) + '\n')


def read_text(path):
    """返回 (正文, 错误原因)。

    文件不存在 → (None, 'missing')
    读取/解码失败 → (None, '<原因>')
    正常 → (正文, None)

    注意：读失败绝不返回空串——调用方需据此区分「真空文件」与「读不到」。
    """
    if not os.path.isfile(path):
        return None, 'missing'
    last = None
    for enc in ('utf-8-sig', 'gbk'):
        try:
            with io.open(path, encoding=enc) as f:
                text = f.read()
        except UnicodeDecodeError as e:
            last = '%s 解码失败: %s' % (enc, e)
            continue
        except OSError as e:
            return None, '读取失败: %s' % e
        if enc != 'utf-8-sig':
            warn('非 UTF-8 文件，已按 %s 读取（建议转为 UTF-8）: %s' % (enc, path))
        return text, None
    return None, last


def write_text(path, text):
    """原子写：临时文件 + os.replace，避免写一半中断把文件截断。

    统一以 LF 写入与 UTF-8 编码，避免 Windows 下产出 CRLF 造成整文件 diff 噪声。
    """
    d = os.path.dirname(path) or '.'
    fd, tmp = tempfile.mkstemp(dir=d, prefix='.vault-common-tmp-', suffix='.md')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def split_frontmatter(text):
    """文本以 --- 开头时返回 (frontmatter 区含结尾换行, 正文)；否则 ('', text)。"""
    if text.startswith('---\n'):
        end = text.find('\n---\n', 4)
        if end != -1:
            return text[:end + 1], text[end + 1:]
    return '', text


def load_config():
    """读取 skill 根目录的 config.json；缺失或损坏时返回 {} 并告警。"""
    if not os.path.isfile(CONFIG_PATH):
        return {}
    text, err = read_text(CONFIG_PATH)
    if err:
        warn('config.json 不可用（%s），按未配置处理: %s' % (err, CONFIG_PATH))
        return {}
    try:
        data = json.loads(text)
    except ValueError as e:
        warn('config.json 解析失败（%s），按未配置处理: %s' % (e, CONFIG_PATH))
        return {}
    return data if isinstance(data, dict) else {}


def resolve_vault_root(cli_vault=None, cfg=None):
    """vault_root 是唯一被脚本读取的路径字段（绝对路径）。"""
    if cli_vault:
        return cli_vault
    cfg = load_config() if cfg is None else cfg
    v = str(cfg.get('vault_root') or '').strip()
    return v or None


def resolve_resource_root(cfg=None):
    """资源根（缓冲区/快照所在目录），相对 vault_root 或绝对路径；默认 30-资源。"""
    cfg = load_config() if cfg is None else cfg
    raw = str(cfg.get('resource_root') or '').strip().replace('\\', '/').strip('/')
    return raw or DEFAULT_RESOURCE_ROOT


def under_vault(vault_root, rel):
    """把相对路径挂到 vault_root 下；rel 为绝对路径时原样返回。"""
    rel = rel.replace('\\', '/')
    if os.path.isabs(rel):
        return rel
    return os.path.join(vault_root, *[p for p in rel.split('/') if p])


def buffer_path(vault_root, cfg=None):
    return under_vault(vault_root, resolve_resource_root(cfg) + '/' + BUFFER_NAME)


def snapshot_dir(vault_root, cfg=None):
    return under_vault(vault_root, resolve_resource_root(cfg) + '/' + SNAPSHOT_DIR_NAME)


def walk_md(root, sub=None):
    base = root if sub is None else os.path.join(root, sub)
    for r, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if f.endswith('.md') and f not in SKIP_FILES:
                yield os.path.join(r, f)


def norm_rel(p, root):
    return os.path.relpath(p, root).replace('\\', '/')


def strip_md(name):
    """只去掉结尾的 .md，不做全局替换（避免 a.md.notes → a.notes 这类误伤）。"""
    return name[:-3] if name.endswith('.md') else name
