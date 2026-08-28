# Obsidian Vault Organizer

按三层知识模型管理 Obsidian Vault 的 AI 工作流 Skill。**零个人内容、零预置分类表**——完全由你的 Vault 本身驱动，直接拿去用即可。

## 三层知识模型

```
L1 原始知识点 → L2 疑问追问 → L3 项目应用组合
   (学什么)       (想通什么)       (做出什么)
```

- L1 知识按**知识域**归位（技术栈/学科），不由"什么时候学的"决定
- L2 疑问物理上靠近产生它的 L1 知识
- L3 项目通过 `[[wikilink]]` 链接回 L1/L2，不复制、不暂存知识

## 工作原理（扫描驱动，无需配置分类）

本 Skill **不附带任何预设分类表**（如技术栈→目录映射）。每次归类/审计时：

1. 自动扫描 `vault_root` 的实际目录结构，以目录名为关键词建立归类索引
2. 新笔记按关键词匹配到现有目录
3. 无匹配时自动建议新建目录，并回写索引——**taxonomy 随你的记录增量生成**，Vault 结构变了它自动跟随

## 安装

1. 将本目录（`obsidian-vault-organizer/`）放入你的技能目录（如 `~/.agents/skills/` 或豆包等工具的 skills 目录）
2. 复制 `config.example.json` 为 `config.json`，填入你的 Vault 路径：

```json
{
  "vault_root": "/path/to/your/obsidian/vault",
  "l1_root": "",
  "l3_root": "",
  "attachment_dir": "",
  "template_dir": ""
}
```

| 字段 | 含义 | 留空时 |
|------|------|--------|
| `vault_root` | 你的 Obsidian Vault 根路径（必填） | — |
| `l1_root` | L1 知识根目录名 | 自动探测，兜底 `10-领域/` |
| `l3_root` | L3 项目根目录名 | 自动探测，兜底 `20-项目/` |
| `attachment_dir` | 附件目录名 | 兜底 `30-资源/媒体附件/` |
| `template_dir` | 模板目录名 | 兜底 `99-模板/` |

> `config.json` 含个人路径，已被 `.gitignore` 忽略，不会提交。

## 使用方式

说"记录一下 / 这个文件放哪 / 检查下结构 / 建个项目目录"即可自动触发：

- **归类**：判断 L1/L2/L3，按自动分类索引给出目标路径 + 理由
- **审计**：对照三层模型扫描目录，报告 🔴/🟡/🔵 问题并给出移动方案
- **Scaffold**：为新项目建立目录骨架 + MOC（骨架见 `references/project-scaffold.md`，可按个人习惯调整）

## 目录结构

```
obsidian-vault-organizer/
├── SKILL.md                    # 工作流定义（通用方法论）
├── references/
│   └── project-scaffold.md     # L3 项目骨架示例
├── config.example.json         # 配置模板（分享用）
├── config.json                 # 你的本地配置（已 gitignore）
└── .gitignore
```

> 归类索引生成后落在你的 Vault 内（`_taxonomy.generated.md`），属于你的数据，不随 Skill 分发。
