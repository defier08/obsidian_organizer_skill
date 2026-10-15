#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
obsidian-vault-organizer / scripts/pending_buffer.py
待记录缓冲区脚本化（工作流 D 的强制 gate）。

用途：
  - 无参数 / --list      : 列出缓冲区中所有"待记录"项（写入前必须运行此步）
  - --all                : 列出全部项（含已记录）
  - --title T [--summary S] [--target P] [--snapshot <问答原文临时文件>]
                         : 登记新项（推荐写法：标题可含任意字符，不会被拆分错位）
  - --add "标题|摘要|目标笔记" [--snapshot PATH]
                         : 登记新项（兼容旧写法；分段超过 3 段时报错，请改用 --title）
  - --done N             : 将编号 N 标记为已记录
  - --clear N1,N2,...    : 清除指定编号条目（整行移除，多选）
  - --vault <路径>       : 手动指定 Vault 根（默认读同目录 config.json 的 vault_root）

约定：
  - 缓冲区文件 = {vault_root}/{resource_root}/待记录缓冲区.md，是唯一权威来源
    （resource_root 默认 30-资源，可在 config.json 覆盖）
  - 快照目录 = {vault_root}/{resource_root}/待记录快照/（L0 全量记录的唯一权威来源）
  - 编号跨会话连续（取全文件最大编号 + 1）
  - 表格行格式：| N | 标题 | 摘要 | 目标笔记 | 快照 | 状态 |
    （兼容旧 5 列格式，首次运行自动升级为 6 列；全角竖线 ｜ 会被归一化）
  - 写入统一 UTF-8 + LF，且先落临时文件再原子替换；同一时刻只应有本脚本在写

退出码（与 scripts/vault_common.py 的约定一致）：
  0 = 正常；1 = 业务性失败（Vault 不可用、缓冲区读失败、编号不存在）；
  2 = 参数用法错误（动作参数冲突、--add 分段过多、缺少必填）
"""
import argparse
import os
import re
import shutil
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vault_common as vc  # noqa: E402  （与本脚本同目录，共用配置与读取语义）

ROW_RE = re.compile(r"^\|\s*(\d+)\s*\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|\s*$")
ROW_RE5 = re.compile(r"^\|\s*(\d+)\s*\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|\s*$")
FULLWIDTH_PIPE = "\uff5c"  # ｜
WINDOW = 10  # 缓冲区滑动窗口兜底默认值（config.json 的 buffer_window 优先；CLI --window 最高优先）：保留最近 N 个对话的快照


def buffer_path(vault):
    return vc.buffer_path(vault)


def strip_eol(line):
    """去掉行尾换行。

    注意：这里**不**做全角竖线替换——全角竖线可能本身就是单元格内容（如标题里的 ｜），
    无条件替换会把内容误当成列分隔符。真正的容错交给 match_row 按需重试。
    """
    return line.rstrip("\r\n")


def looks_like_row(s):
    """疑似表格数据行但解析不出来（用于「未识别行」告警）。

    判据放宽为「以竖线开头 **或** 含 ≥2 个竖线」：一行被换行写坏后，往往就不再
    「以 | 结尾」，若坚持首尾都是竖线，这类断裂行会既不显示也不告警——这正是
    过去静默丢项的成因。放宽后普通说明文字（不含竖线）仍不会被误判。
    """
    t = s.strip().replace(FULLWIDTH_PIPE, "|")
    if not (t.startswith("|") or t.count("|") >= 2):
        return False
    core = t.replace("|", "").replace("-", "").replace(":", "").replace(" ", "")
    if core == "":
        return False  # 分隔行
    if "编号" in t and "标题" in t:
        return False  # 表头
    return True


def read_lines(path):
    """返回 (lines, err)。

    err 非空时调用方必须中止：绝不能把「读失败」当成「空缓冲区」，
    否则后续写入会直接覆盖掉原有内容。
    """
    text, err = vc.read_text(path)
    if err == "missing":
        return [], None
    if err:
        return [], err
    return text.splitlines(keepends=True), None


def ensure_lf(lines):
    return [ln if ln.endswith("\n") else ln + "\n" for ln in lines]


def write_buffer(vault, lines):
    """统一写缓冲区：父目录不存在则创建、UTF-8 + LF、原子替换。"""
    path = buffer_path(vault)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    vc.write_text(path, "".join(ensure_lf(lines)))


def _match(s):
    """按 6 列（优先）或 5 列匹配一行，返回 6 元组或 None。"""
    m = ROW_RE.match(s)
    if m:
        return (int(m.group(1)), m.group(2).strip(), m.group(3).strip(),
                m.group(4).strip(), m.group(5).strip(), m.group(6).strip())
    m5 = ROW_RE5.match(s)
    if m5:
        return (int(m5.group(1)), m5.group(2).strip(), m5.group(3).strip(),
                m5.group(4).strip(), "", m5.group(5).strip())
    return None


def match_row(s):
    """解析一行，返回 (编号, 标题, 摘要, 目标, 快照, 状态)；无法解析返回 None。

    容错策略：先按原样匹配，失败且行内出现全角竖线时，再把全角当分隔符重试一次
    ——这样「内容里合法的 ｜」不会被误拆，而「手写全角分隔符」也能被认出来。
    """
    got = _match(s)
    if got is None and FULLWIDTH_PIPE in s:
        got = _match(s.replace(FULLWIDTH_PIPE, "|"))
    return got


def upgrade_table_to_six(lines):
    """把旧 5 列表头/分隔行/数据行统一升级为 6 列（在状态列前插入快照列），返回新 lines。

    只改写「半角竖线」形态的行；含全角内容/分隔的行原样保留（由 match_row 容错解析）。
    """
    out = []
    for ln in lines:
        s = strip_eol(ln)
        m6 = ROW_RE.match(s)
        m5 = ROW_RE5.match(s)
        core = s.replace("|", "").replace("-", "").replace(":", "").replace(" ", "").strip()
        is_sep = s.startswith("|") and s.endswith("|") and core == ""
        if m5 and not m6:
            parts = s.split("|")
            parts.insert(-2, " - ")
            s = "|".join(parts)
        elif re.match(r"^\|\s*编号\s*\|", s) and "快照" not in s:
            s = s.replace("| 状态 |", "| 快照 | 状态 |", 1)
        elif is_sep and s.count("|") != 7:
            s = "|---|---|---|---|---|---|"
        out.append(s + "\n")
    return out


def parse_rows(lines):
    """返回 (rows, unrecognized)。

    rows: [(编号, 标题, 摘要, 目标笔记, 快照, 状态, 行号)]
    unrecognized: [(行号, 原文)] —— 表格形态但无法解析的行，不再静默丢弃。
    """
    rows = []
    unrecognized = []
    for i, line in enumerate(lines):
        s = strip_eol(line)
        got = match_row(s)
        if got:
            rows.append(got + (i,))
            continue
        if looks_like_row(s):
            unrecognized.append((i + 1, s.strip()))
    return rows, unrecognized


def max_id(rows):
    return max((r[0] for r in rows), default=0)


def find_latest_session_index(lines):
    idx = -1
    for i, line in enumerate(lines):
        if line.startswith("## 会话："):
            idx = i
    return idx


def filter_latest_session(lines, rows):
    """默认只保留「最新会话段」里的行（最后一个 `## 会话：` 之后）。

    缓冲区跨会话持久，旧会话条目可能已滑出上下文；默认不列出它们。
    用会话段这一「文件里真实存在的结构」做窗口，比靠模型自己数轮次可靠。
    """
    last = -1
    for i, line in enumerate(lines):
        if line.startswith("## 会话："):
            last = i
    if last < 0:
        return rows
    return [r for r in rows if r[6] > last]


def list_pending(lines, show_all, session_only=False, window=WINDOW):
    rows, unrecognized = parse_rows(lines)
    pending = [r for r in rows if not (r[5].startswith("✅") or r[5].startswith("已记录"))]
    if show_all:
        out_rows = rows
    elif session_only:
        out_rows = filter_latest_session(lines, pending)
    else:
        out_rows = filter_recent_pending(pending, window)
    if not out_rows and not unrecognized:
        if show_all:
            print("待记录缓冲区为空。")
        elif pending:
            print(f"最近 {window} 个窗口内暂无待记录项；另有 {len(pending)} 项来自更早会话"
                  f"（用 --all 查看，或说“记录刚才讲的X”补记）。")
        else:
            print("待记录缓冲区为空。")
    elif out_rows:
        label = "全部" if show_all else ("本会话段" if session_only else f"待记录(最近{window}轮)")
        print(f"待记录缓冲区（{label} {len(out_rows)} 项）：")
        for r in out_rows:
            status = f"（{r[5]}）" if show_all else ""
            snap = "〔快照已存〕" if r[4] and r[4] != "-" else "〔无原文〕"
            print(f"{r[0]}. {r[1]} — {r[2]}{snap}{status}")
        if not show_all:
            print("\n要记录哪些？回复“全部”/编号（如 1,3）/“都不记”/“记录刚才讲的X”")
    if unrecognized:
        print(f"\n⚠️ 未识别行 {len(unrecognized)} 行（格式不符、已跳过解析，请人工修正）：")
        for ln_no, raw in unrecognized[:10]:
            print(f"  第 {ln_no} 行: {raw}")
        if len(unrecognized) > 10:
            print(f"  ... 共 {len(unrecognized)} 行")
        vc.warn("缓冲区有 %d 行表格无法解析，可能导致登记项不可见，请修正格式。" % len(unrecognized))


def sanitize_cell(text):
    """单元格净化：清除换行/制表符等控制字符、压缩空白，再把竖线统一为全角 ｜。

    单元格必须是**单行**的一段——任何换行都会把整行表格拆成两行、破坏列结构，
    所以「换行」和「竖线」都必须在这里处理掉，只替换竖线是不够的。
    """
    t = re.sub(r"[\r\n\t\v\f]+", " ", str(text if text is not None else ""))
    t = "".join(ch for ch in t if ord(ch) >= 32)
    t = re.sub(r" {2,}", " ", t)
    return t.replace("|", FULLWIDTH_PIPE).strip()


def filter_recent_pending(pending, window=WINDOW):
    """默认窗口：取编号最大的 window 个 pending 项（取代仅会话段窗口）。"""
    if len(pending) <= window:
        return pending
    keep = set(sorted(r[0] for r in pending)[-window:])
    return [r for r in pending if r[0] in keep]


def rolling_cleanup(vault, lines, window=WINDOW):
    """登记后滚动清理：条目总数 > window 时，移除最旧的超出项并删其快照文件。

    优先清理已记录(✅)项以保留待记录项；返回清理后的 lines（无变化则原样返回）。
    """
    rows, _ = parse_rows(lines)
    if len(rows) <= window:
        return lines
    to_drop = len(rows) - window
    ordered = sorted(rows, key=lambda r: r[0])  # 旧→新
    drop_ids = set()
    for r in ordered:
        if len(drop_ids) >= to_drop:
            break
        if r[5].startswith("✅") or r[5].startswith("已记录"):
            drop_ids.add(r[0])
    for r in ordered:
        if len(drop_ids) >= to_drop:
            break
        if r[0] not in drop_ids:
            drop_ids.add(r[0])
    # 删除被移除项指向的快照文件（快照列记为相对 vault 的 "资源根/待记录快照/xxx.md"）
    for r in rows:
        if r[0] in drop_ids and r[4] and r[4] != "-":
            p = r[4]
            if not os.path.isabs(p):
                p = os.path.join(vault, *p.split("/"))
            if os.path.isfile(p):
                try:
                    os.remove(p)
                except OSError as e:
                    vc.warn("删除快照失败: %s (%s)" % (p, e))
    out = []
    for line in lines:
        got = match_row(strip_eol(line))
        if got and got[0] in drop_ids:
            continue
        out.append(line)
    return out


def add_entry(lines, vault, title, summary, target, snapshot_src=None, no_snapshot=False, window=WINDOW):
    today = date.today().isoformat()
    title = sanitize_cell(title)
    summary = sanitize_cell(summary)
    target = sanitize_cell(target)
    if not title:
        vc.warn("登记失败：标题净化后为空（只含空白或控制字符）。")
        sys.exit(vc.EXIT_USAGE)
    rows, _ = parse_rows(lines)
    new_id = max_id(rows) + 1
    res = vc.resolve_resource_root()
    snapshot_col = "-"
    if snapshot_src:
        if not os.path.exists(snapshot_src):
            vc.warn("快照文件不存在: %s，登记继续但快照列留空。" % snapshot_src)
        else:
            snap_dir = vc.snapshot_dir(vault)
            os.makedirs(snap_dir, exist_ok=True)
            slug = re.sub(r'[\\/:*?"<>|\uff5c\s]+', "_", title)[:24].strip("_") or "item"
            snap_name = f"{today}-{new_id:03d}-{slug}.md"
            shutil.copy2(snapshot_src, os.path.join(snap_dir, snap_name))
            snapshot_col = res + "/" + vc.SNAPSHOT_DIR_NAME + "/" + snap_name
    if no_snapshot:
        vc.warn("登记以 --no-snapshot 兜底：#%d 记〔无原文〕，记录时该轮将无原文可落盘 L0。" % new_id)
    row = f"| {new_id} | {title} | {summary} | {target or '待定'} | {snapshot_col} | 未记录 |"
    idx = find_latest_session_index(lines)
    if idx >= 0:
        m = re.match(r"^## 会话：(20\d{2}-\d{2}-\d{2})", strip_eol(lines[idx]).strip())
        if m and m.group(1) == today:
            ins = idx + 1
            for j in range(idx + 1, len(lines)):
                if match_row(strip_eol(lines[j])):
                    ins = j + 1
            lines.insert(ins, row + "\n")
        else:
            lines.extend(["\n", f"## 会话：{today}\n", "\n",
                          "| 编号 | 标题（用户问题） | 核心结论摘要 | 目标笔记 | 快照 | 状态 |\n",
                          "|---|---|---|---|---|---|\n", row + "\n"])
    else:
        header = ["---\n", "created: " + today + "\n", "tags: [待记录缓冲区, 工作流]\n", "---\n",
                  "\n", "# 待记录缓冲区\n", "\n",
                  "> 本文件为 obsidian-vault-organizer 工作流 D 的落盘缓冲区，跨会话续用；记录后请移除已记录行。\n",
                  "> 快照目录：" + res + "/" + vc.SNAPSHOT_DIR_NAME +
                  "/（登记时落盘的本轮问答原文，L0 全量记录的唯一权威来源）\n",
                  "\n", f"## 会话：{today}\n", "\n",
                  "| 编号 | 标题（用户问题） | 核心结论摘要 | 目标笔记 | 快照 | 状态 |\n",
                  "|---|---|---|---|---|---|\n", row + "\n"]
        lines = header + lines
    # 写前自检：先在内存里确认新行能被解析出来，避免把坏行写进文件（损坏缓冲区）
    preview_rows, _ = parse_rows(lines)
    if not any(r[0] == new_id for r in preview_rows):
        vc.warn("登记失败：#%d 无法被解析（单元格内容破坏了表格结构），本次未写入任何内容。" % new_id)
        vc.warn("缓冲区文件未被修改：%s" % buffer_path(vault))
        sys.exit(vc.EXIT_FINDINGS)
    lines = rolling_cleanup(vault, lines, window)
    write_buffer(vault, lines)
    # 写后回读自检：确认落盘内容里确实能读到该编号（防写入/编码层面的意外）
    written, err = read_lines(buffer_path(vault))
    if err:
        vc.warn("登记后回读缓冲区失败（%s）：%s" % (err, buffer_path(vault)))
        sys.exit(vc.EXIT_FINDINGS)
    after_rows, after_bad = parse_rows(written)
    if not any(r[0] == new_id for r in after_rows):
        vc.warn("登记自检失败：#%d 写入后无法被解析，请检查缓冲区文件：%s" % (new_id, buffer_path(vault)))
        sys.exit(vc.EXIT_FINDINGS)
    if after_bad:
        vc.warn("缓冲区仍有 %d 行无法解析（本次登记项本身可读）：%s"
                % (len(after_bad), "; ".join("第 %d 行: %s" % (n, s) for n, s in after_bad[:3])))
    print(f"已登记 #{new_id}: {title}" + (f"（快照: {snapshot_col}）" if snapshot_col != "-" else ""))


def mark_done(lines, vault, num):
    rows, _ = parse_rows(lines)
    if not any(r[0] == num for r in rows):
        print(f"未找到编号 {num}，可先运行 --list 确认。")
        sys.exit(vc.EXIT_FINDINGS)
    today = date.today().isoformat()
    new_lines = []
    changed = False
    for line in lines:
        got = match_row(strip_eol(line))
        if got and got[0] == num:
            # 按解析结果重建整行：不依赖原行分隔符形态，同时顺手规范化
            line = (f"| {got[0]} | {got[1]} | {got[2]} | {got[3]} | {got[4]} "
                    f"| ✅ 已记录（{today}） |\n")
            changed = True
        new_lines.append(line)
    if changed:
        write_buffer(vault, new_lines)
        print(f"编号 {num} 已标记为已记录（{today}）。")
    else:
        print(f"未找到编号 {num}。")


def clear_entries(lines, vault, nums):
    """清除指定编号条目（整行移除，支持多选）。nums 为编号列表。"""
    rows, _ = parse_rows(lines)
    existing = {r[0] for r in rows}
    nums = [n for n in nums if n > 0]
    missing = [n for n in nums if n not in existing]
    if not nums:
        vc.warn("--clear 需要至少一个编号，格式：--clear 1,3,5")
        sys.exit(vc.EXIT_USAGE)
    if missing:
        vc.warn("未找到编号: " + ", ".join(str(n) for n in missing))
        if all(n in missing for n in nums):
            sys.exit(vc.EXIT_FINDINGS)
    keep = []
    removed = []
    for line in lines:
        got = match_row(strip_eol(line))
        if got and got[0] in nums:
            removed.append(got[0])
        else:
            keep.append(line)
    if removed:
        write_buffer(vault, keep)
        print(f"已清除 {len(removed)} 项: {', '.join(str(n) for n in sorted(removed))}")
    else:
        print("没有条目被清除。")


def main():
    ap = argparse.ArgumentParser(description="待记录缓冲区脚本化 gate")
    ap.add_argument("--list", action="store_true", help="列出待记录项（默认）")
    ap.add_argument("--all", action="store_true", help="列出全部项")
    ap.add_argument("--add", metavar="标题|摘要|目标笔记",
                    help="登记新项（兼容旧写法；标题含竖线时请改用 --title/--summary/--target）")
    ap.add_argument("--title", metavar="T", help="登记新项：标题（推荐，不受竖线影响）")
    ap.add_argument("--summary", metavar="S", help="登记新项：核心结论摘要（配合 --title）")
    ap.add_argument("--target", metavar="P", help="登记新项：预计写入的目标笔记（配合 --title）")
    ap.add_argument("--snapshot", metavar="PATH",
                    help="本轮问答原文临时文件（必带）：登记时复制到快照目录，L0 全量落盘的唯一权威来源")
    ap.add_argument("--no-snapshot", action="store_true",
                    help="极端兜底：确实无法取得本轮原文时才用，记〔无原文〕并告警（默认快照必带）")
    ap.add_argument("--session", action="store_true",
                    help="--list 时仅列当前会话段（兼容旧行为；默认列最近 WINDOW 个 pending）")
    ap.add_argument("--window", type=int, metavar="N",
                    help="临时覆盖滑动窗口大小（默认 config.json 的 buffer_window 或 %d）：影响列出与滚动清理" % WINDOW)
    ap.add_argument("--done", type=int, metavar="N", help="标记编号 N 为已记录")
    ap.add_argument("--clear", metavar="N[,N...]", action="append",
                    help="清除指定编号条目（多选：逗号分隔或重复参数）")
    ap.add_argument("--vault", help="Vault 根路径（默认读 config.json）")
    args = ap.parse_args()
    cfg = vc.load_config()
    config_window = cfg.get("buffer_window")
    if not (isinstance(config_window, int) and config_window > 0):
        config_window = None
    window = args.window if (args.window and args.window > 0) else (config_window or WINDOW)

    vault = vc.resolve_vault_root(args.vault)
    if not vault or not os.path.isdir(vault):
        vc.warn("无法定位 Vault 根路径：请检查 config.json 的 vault_root 或使用 --vault <路径>")
        sys.exit(vc.EXIT_FINDINGS)

    # 动作互斥：同时传多个动作参数时显式报错，不再静默只执行其中一个
    actions = [name for name, on in (
        ("登记（--add/--title）", bool(args.add) or bool(args.title)),
        ("--done", args.done is not None),
        ("--clear", bool(args.clear)),
    ) if on]
    if len(actions) > 1:
        vc.warn("动作参数冲突：" + "、".join(actions) + " 只能选一个")
        sys.exit(vc.EXIT_USAGE)
    if (args.summary or args.target) and not args.title:
        vc.warn("--summary / --target 需要与 --title 搭配使用")
        sys.exit(vc.EXIT_USAGE)

    path = buffer_path(vault)
    lines, err = read_lines(path)
    if err:
        vc.warn("缓冲区文件读取失败（%s）：%s" % (err, path))
        vc.warn("已中止且未做任何写入——避免把读失败当成空缓冲区而覆盖原文件。")
        sys.exit(vc.EXIT_FINDINGS)

    upgraded = upgrade_table_to_six(lines)
    if upgraded != lines:
        write_buffer(vault, upgraded)
        lines = upgraded

    is_list_only = not (args.title or args.add or args.clear or args.done is not None)
    _, unrecognized = parse_rows(lines)
    if unrecognized and not is_list_only:
        # --list 场景由 list_pending 负责展示 + 告警，这里不重复喊同一件事
        vc.warn("缓冲区有 %d 行表格无法解析（可能造成登记项不可见）：%s"
                % (len(unrecognized), "; ".join("第 %d 行: %s" % (n, s) for n, s in unrecognized[:3])))

    if args.title or args.add:
        if args.title:
            title = args.title.strip()
            summary = (args.summary or "").strip()
            target = (args.target or "").strip()
        else:
            parts = [p.strip() for p in args.add.split("|")]
            if len(parts) > 3:
                vc.warn("--add 被拆成 %d 段（最多 3 段：标题|摘要|目标笔记），标题里可能含竖线。"
                        % len(parts))
                vc.warn("请改用 --title \"...\" --summary \"...\" --target \"...\"。")
                sys.exit(vc.EXIT_USAGE)
            title = parts[0] if len(parts) > 0 else ""
            summary = parts[1] if len(parts) > 1 else ""
            target = parts[2] if len(parts) > 2 else ""
        if not title:
            vc.warn("登记需要标题：--title \"...\" 或 --add \"标题|摘要|目标笔记\"")
            sys.exit(vc.EXIT_USAGE)
        if args.snapshot and args.no_snapshot:
            vc.warn("--snapshot 与 --no-snapshot 互斥，只能选一个")
            sys.exit(vc.EXIT_USAGE)
        if not args.snapshot and not args.no_snapshot:
            vc.warn("登记必须带全量原文快照：请先把本轮问答写入临时 .md 并以 --snapshot <临时文件> 传入；"
                    "确实无法取得原文时才用 --no-snapshot（记〔无原文〕并告警）。")
            sys.exit(vc.EXIT_USAGE)
        add_entry(lines, vault, title, summary, target, args.snapshot, args.no_snapshot, window)
    elif args.clear:
        nums = []
        for c in args.clear:
            for part in c.split(","):
                part = part.strip()
                if part.isdigit():
                    nums.append(int(part))
                else:
                    vc.warn("忽略无效编号: %r" % part)
        clear_entries(lines, vault, nums)
    elif args.done is not None:
        mark_done(lines, vault, args.done)
    else:
        list_pending(lines, show_all=args.all, session_only=args.session, window=window)


if __name__ == "__main__":
    main()
