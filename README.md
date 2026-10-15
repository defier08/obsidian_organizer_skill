# Obsidian Vault Organizer

按四层知识模型管理 Obsidian Vault 的 AI 工作流 Skill。**零个人内容、零预置分类表**——完全由你的 Vault 本身驱动，直接拿去用即可。

## 四层知识模型

```
L0 原始记录 → L1 知识点 → L2 疑问追问 → L3 项目应用组合
 (快照存档)     (学什么)     (想通什么)      (做出什么)
```

- **L0 原始记录**：说"记录"时，把被选中轮次的对话原文（用户提问逐字 + AI 助手回答原文 + 产出）快照进 `00-原始记录/`，只追加、不合并、不修改
- **L1 知识**按**知识域**归位（技术栈/学科），不由"什么时候学的"决定
- **L2 疑问**物理上靠近产生它的 L1 知识（一疑问一文件）
- **L3 项目**通过 `[[wikilink]]` 链接回 L1/L2，不复制、不暂存知识

## 工作原理（扫描驱动，无需配置分类）

本 Skill **不附带任何预设分类表**（如技术栈→目录映射）。每次归类/审计时：

1. 自动扫描 `vault_root` 的实际目录结构，以目录名为关键词建立归类索引
2. 新笔记按关键词匹配到现有目录
3. 无匹配时自动建议新建目录——**归类索引按 Vault 实际结构现场生成（运行态）**，结构变了自动跟随；需要审计/人工微调时可落盘到 `_taxonomy.generated.md`（可选快照，由 AI 维护，非脚本自动生成）

## 待记录缓冲区（跨会话）

连续问了好几个问题才说"记录"时，助手无法判断该记哪几个。本 Skill 用 Vault 内的缓冲区解决：

- 每轮"提问 → 解答"后自动登记一项到 `<resource_root>/待记录缓冲区.md`（默认 `30-资源/待记录缓冲区.md`），编号跨会话连续
- 说"记录"时先列出最近 10 轮的待记录清单，由你选择范围，**不会直接写入**
- 缓冲区读写一律经 `scripts/pending_buffer.py`；格式异常的行会被显式列出并告警，不会静默丢失

## 安装

1. 将本目录（`obsidian-vault-organizer/`）放入你的技能目录（如 `~/.agents/skills/` 或对应工具的 skills 目录）
2. 复制 `config.example.json` 为 `config.json`，填入你的 Vault 路径：

```json
{
  "vault_root": "/path/to/your/obsidian/vault",
  "resource_root": "",
  "l0_root": "",
  "l1_root": "",
  "l3_root": "",
  "attachment_dir": "",
  "template_dir": ""
}
```

| 字段 | 含义 | 留空时 |
|------|------|--------|
| `vault_root` | 你的 Obsidian Vault 根路径（**绝对路径**） | 必填 |
| `resource_root` | 资源根目录名（缓冲区/快照所在） | 默认 `30-资源/` |
| `l0_root` | L0 原始记录根目录名 | 自动探测，兜底 `00-原始记录/` |
| `l1_root` | L1 知识根目录名 | 自动探测，兜底 `10-领域/` |
| `l3_root` | L3 项目根目录名 | 自动探测，兜底 `20-项目/` |
| `attachment_dir` | 附件目录名 | 兜底 `30-资源/媒体附件/` |
| `template_dir` | 模板目录名 | 兜底 `99-模板/` |

> `config.json` 含个人路径，已被 `.gitignore` 忽略，不会提交。
>
> **只有 `vault_root`（以及可选的 `resource_root`）会被 `scripts/` 读取**；其余字段是给 AI 做归类与探测的提示值，一律按**目录名（相对 `vault_root`）**填写，不要写成绝对路径。

## 使用方式

说"记录一下 / 这个文件放哪 / 检查下结构 / 建个项目目录 / 整理一下"即可自动触发：

- **归类**：判断 L0/L1/L2/L3，按自动分类索引给出目标路径 + 理由
- **记录**：新笔记自动带 frontmatter（title/date/tags/aliases），代码保留围栏代码块，可视化配图 SVG + HTML 双落盘并嵌入（详见 SKILL.md「写入规则」）
- **审计**：对照四层模型扫描目录，报告 🔴/🟡/🔵 问题并给出移动方案
- **整理**：体检全库（空壳/重复/命名/断链）→ 预览方案 → 改名与链接同步，**残留断链 = 0 才算完成**
- **Scaffold**：为新项目建立目录骨架 + MOC（骨架见 `references/project-scaffold.md`，可按个人习惯调整）

## 目录结构

```
obsidian-vault-organizer/
├── SKILL.md                    # 工作流定义（通用方法论）
├── references/
│   └── project-scaffold.md     # L3 项目骨架示例
├── scripts/
│   ├── vault_common.py         # 脚本层共用：配置读取 / 读取语义 / 退出码 / 跳过清单 / 资源根
│   ├── health-check.py         # 健康体检：空壳/重复/命名/根目录散落/断链/读取失败
│   ├── verify_links.py         # 链接验证：改名/移动后残留断链 = 0
│   ├── rename_with_links.py    # 工作流 F：改名 + 链接重写一体（原子写 + 自动备份）
│   └── pending_buffer.py       # 工作流 D：待记录缓冲区（强制 gate）
├── config.example.json         # 配置模板（分享用）
├── config.json                 # 你的本地配置（已 gitignore）
└── .gitignore
```

### 退出码约定（全部脚本一致）

| 退出码 | 含义 |
|---|---|
| `0` | 无硬问题 |
| `1` | 有发现（真断链 / 读取失败 / 目标缺失）——属正常结果，**不是脚本崩溃** |
| `2` | 参数或配置错误 |

> 脚本共用同目录的 `vault_common.py`：请**整目录一起使用**，不要单独复制某一个脚本。
>
> 归类索引生成后落在你的 Vault 内（`_taxonomy.generated.md`），属于你的数据，不随 Skill 分发。
>
> 改名或改写笔记前，脚本会把原件自动备份到 `<vault_root>/.organizer-backup/<时间戳>/`；回滚即用备份覆盖回原路径（该目录不参与扫描）。
