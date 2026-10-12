#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
obsidian-vault-organizer / scripts/pending_buffer.py
待记录缓冲区脚本化（工作流 D 的强制 gate）。

用途：
  - 无参数 / --list      : 列出缓冲区中所有"待记录"项（写入前必须运行此步）
  - --all                : 列出全部项（含已记录）
  - --add "标题|摘要|目标笔记" : 登记新项（自动编号、写入今天/最新会话段）
  - --done N             : 将编号 N 标记为已记录
  - --clear N1,N2,...   : 清除指定编号条目（整行移除，多选）
  - --vault <路径>       : 手动指定 Vault 根（默认读同目录 config.json 的 vault_root）

约定：
  - 缓冲区文件 = {vault_root}/30-资源/待记录缓冲区.md，是唯一权威来源
  - 编号跨会话连续（取全文件最大编号 + 1）
  - 表格行格式：| N | 标题 | 摘要 | 目标笔记 | 状态 |
"""
import argparse
import json
import os
import re
import sys
from datetime import date

BUFFER_REL = os.path.join("30-资源", "待记录缓冲区.md")
ROW_RE = re.compile(r"^\|\s*(\d+)\s*\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|\s*$")


def get_vault_root(cli_vault):
    if cli_vault:
        return cli_vault
    cfg = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
    if os.path.exists(cfg):
        with open(cfg, encoding="utf-8") as f:
            return json.load(f).get("vault_root", "")
    return ""


def buffer_path(vault):
    return os.path.join(vault, BUFFER_REL)


def read_lines(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return f.readlines()


def parse_rows(lines):
    """返回 [(编号, 标题, 摘要, 目标笔记, 状态, 行号)]"""
    rows = []
    for i, line in enumerate(lines):
        m = ROW_RE.match(line.rstrip("\r\n"))
        if m:
            rows.append((int(m.group(1)), m.group(2).strip(), m.group(3).strip(),
                         m.group(4).strip(), m.group(5).strip(), i))
    return rows


def max_id(rows):
    return max((r[0] for r in rows), default=0)


def find_latest_session_index(lines):
    idx = -1
    for i, line in enumerate(lines):
        if line.startswith("## 会话："):
            idx = i
    return idx


def list_pending(lines, show_all):
    rows = parse_rows(lines)
    pending = [r for r in rows if not (r[4].startswith("✅") or r[4].startswith("已记录"))]
    out_rows = rows if show_all else pending
    if not out_rows:
        print("待记录缓冲区为空。")
        return
    print(f"待记录缓冲区（{'全部' if show_all else '待记录'} {len(out_rows)} 项）：")
    for r in out_rows:
        status = f"（{r[4]}）" if show_all else ""
        print(f"{r[0]}. {r[1]} — {r[2]}{status}")
    if not show_all:
        print("\n要记录哪些？回复“全部”/编号（如 1,3）/“都不记”/“记录刚才讲的X”")


def add_entry(lines, vault, title, summary, target):
    today = date.today().isoformat()
    rows = parse_rows(lines)
    new_id = max_id(rows) + 1
    row = f"| {new_id} | {title} | {summary} | {target or '待定'} | 未记录 |"
    idx = find_latest_session_index(lines)
    if idx >= 0:
        m = re.match(r"^## 会话：(20\d{2}-\d{2}-\d{2})", lines[idx].strip())
        if m and m.group(1) == today:
            ins = idx + 1
            for j in range(idx + 1, len(lines)):
                if ROW_RE.match(lines[j].rstrip("\r\n")):
                    ins = j + 1
            lines.insert(ins, row + "\n")
        else:
            lines.extend(["\n", f"## 会话：{today}\n", "\n",
                          "| 编号 | 标题（用户问题） | 核心结论摘要 | 目标笔记 | 状态 |\n",
                          "|---|---|---|---|---|\n", row + "\n"])
    else:
        header = ["---\n", "created: " + today + "\n", "tags: [待记录缓冲区, 工作流]\n", "---\n",
                  "\n", "# 待记录缓冲区\n", "\n",
                  "> 本文件为 obsidian-vault-organizer 工作流 D 的落盘缓冲区，跨会话续用；记录后请移除已记录行。\n",
                  "\n", f"## 会话：{today}\n", "\n",
                  "| 编号 | 标题（用户问题） | 核心结论摘要 | 目标笔记 | 状态 |\n",
                  "|---|---|---|---|---|\n", row + "\n"]
        lines = header + lines
    lines = [ln if ln.endswith(('\n', '\r')) else ln + '\n' for ln in lines]
    with open(buffer_path(vault), 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print(f"已登记 #{new_id}: {title}")


def mark_done(lines, vault, num):
    rows = parse_rows(lines)
    if not any(r[0] == num for r in rows):
        print(f"未找到编号 {num}，可先运行 --list 确认。")
        sys.exit(1)
    today = date.today().isoformat()
    new_lines = []
    changed = False
    for line in lines:
        m = ROW_RE.match(line.rstrip("\r\n"))
        if m and int(m.group(1)) == num:
            parts = line.rstrip("\r\n").split("|")
            parts[-2] = f" ✅ 已记录（{today}）"
            line = "|".join(parts) + "\n"
            changed = True
        new_lines.append(line)
    if changed:
        new_lines = [ln if ln.endswith(('\n', '\r')) else ln + '\n' for ln in new_lines]
        with open(buffer_path(vault), 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        print(f"编号 {num} 已标记为已记录（{today}）。")
    else:
        print(f"未找到编号 {num}。")


def clear_entries(lines, vault, nums):
    """清除指定编号条目（整行移除，支持多选）。nums 为编号列表。"""
    rows = parse_rows(lines)
    existing = {r[0] for r in rows}
    nums = [n for n in nums if n > 0]
    missing = [n for n in nums if n not in existing]
    if not nums:
        print("--clear 需要至少一个编号，格式：--clear 1,3,5")
        sys.exit(1)
    if missing:
        print(f"未找到编号: {', '.join(str(n) for n in missing)}")
        if all(n in missing for n in nums):
            sys.exit(1)
    keep = []
    removed = []
    for line in lines:
        m = ROW_RE.match(line.rstrip("\r\n"))
        if m and int(m.group(1)) in nums:
            removed.append(int(m.group(1)))
        else:
            keep.append(line)
    if removed:
        keep = [ln if ln.endswith(('\n', '\r')) else ln + '\n' for ln in keep]
        with open(buffer_path(vault), 'w', encoding='utf-8') as f:
            f.writelines(keep)
        print(f"已清除 {len(removed)} 项: {', '.join(str(n) for n in sorted(removed))}")
    else:
        print("没有条目被清除。")

def main():
    ap = argparse.ArgumentParser(description="待记录缓冲区脚本化 gate")
    ap.add_argument("--list", action="store_true", help="列出待记录项（默认）")
    ap.add_argument("--all", action="store_true", help="列出全部项")
    ap.add_argument("--add", metavar="标题|摘要|目标笔记", help="登记新项")
    ap.add_argument("--done", type=int, metavar="N", help="标记编号 N 为已记录")
    ap.add_argument("--clear", metavar="N[,N...]", action="append", help="清除指定编号条目（多选：逗号分隔或重复参数）")
    ap.add_argument("--vault", help="Vault 根路径（默认读 config.json）")
    args = ap.parse_args()

    vault = get_vault_root(args.vault)
    if not vault or not os.path.isdir(vault):
        print("无法定位 Vault 根路径：请检查 config.json 的 vault_root 或使用 --vault <路径>")
        sys.exit(1)

    lines = read_lines(buffer_path(vault))
    if args.add:
        parts = [p.strip() for p in args.add.split("|", 2)]
        title = parts[0] if len(parts) > 0 else ""
        summary = parts[1] if len(parts) > 1 else ""
        target = parts[2] if len(parts) > 2 else ""
        if not title:
            print("--add 至少需要标题，格式：--add \"标题|摘要|目标笔记\"")
            sys.exit(1)
        add_entry(lines, vault, title, summary, target)
    elif args.clear:
        nums = []
        for c in args.clear:
            for part in c.split(","):
                part = part.strip()
                if part.isdigit():
                    nums.append(int(part))
                else:
                    print(f"忽略无效编号: {part!r}")
        clear_entries(lines, vault, nums)
    elif args.done is not None:
        mark_done(lines, vault, args.done)
    else:
        list_pending(lines, show_all=args.all)


if __name__ == "__main__":
    main()