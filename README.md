# Skill Validator

> 对 Agent Skill 目录结构进行自动合规检查。支持中英文技能检测。
>
> *"I have only made this letter longer because I have not had the time to make it shorter."* — Blaise Pascal
>
> **写一个简短的 Skill 很难。正是这种难度造就了它的价值。**

## 功能

对任意 Skill 目录执行 **20 项** 合规检查，涵盖：

| 检查 | 说明 | 场景 |
|---|---|---|
| **目录命名规范** | 全小写、连字符、≤64 字符、禁用保留词 `anthropic`/`claude` | 所有 Skill |
| **目录结构完整性** | Hub-and-Spoke 结构（scripts/ references/ assets/ evals/） | 所有 Skill |
| **Frontmatter 质量** | description 是否存在、是否为触发句式 | 所有 Skill |
| **官方硬约束** | description ≤1024 字符、无 XML 标签、无工作流泄漏（N-phase/plan-execute-verify） | 所有 Skill |
| **正文质量** | Token 估算、>500 行红线、教程式写作检测、Markdown 表格剥离提示 | 中英文 Skill |
| **轨道化常识检测** | 是否包含模型已掌握的常识（pip 命令、Git 教程、基础语法等） | 中英文 Skill |
| **硬编码资产检测** | API Key、URL、Token、MCP 服务地址等是否硬编码在 SKILL.md | 中英文 Skill |
| **评估集检查** | 是否有 `evals/` 目录，以及 `positive.json` / `negative.json` | 所有 Skill |
| **Gotchas 飞轮检查** | 是否有 `gotchas/` 目录或 `## Gotchas` 章节 | 所有 Skill |
| **单文件依赖检查** | 是否整个 Skill 只有一个 `SKILL.md` 文件（应拆分） | 所有 Skill |
| **文件尺寸红线** | 单文件 > 100KB 报警 | 所有 Skill |
| **中文常识灌输检测** | 长篇中文解释性文字（模型已掌握的基础知识） | 中文 Skill |
| **反斜杠路径检测** | 路径必须正斜杠（Agent 按文件系统导航，BP smell） | 所有 Skill |
| **验证闭环检测** | 多步工作流是否含验证环节（NVS/EWP smell） | 中英文 Skill |
| **合理化漏洞检测** | 强纪律规则（ALWAYS/NEVER/必须）是否配防跳过护栏（RL smell，出现于 94% 真实 skill） | 中英文 Skill |
| **references TOC 检测** | references/ 长文件（>100 行）顶部是否有目录 TOC | 所有 Skill |
| **跨模型兼容性标注** | 通过 `--models` 参数标注目标编排模型族 | 可选 |

## 安装

```bash
# 无需安装，直接运行
python3 skill_validator.py --help
```

## 用法

```bash
# 检查单个 Skill
python3 skill_validator.py ./my-skill

# 批量检查父目录下所有 Skill
python3 skill_validator.py ./skills/

# 指定检查语言
python3 skill_validator.py ./my-skill --lang zh    # 仅中文规则
python3 skill_validator.py ./my-skill --lang en    # 仅英文规则
python3 skill_validator.py ./my-skill --lang mixed # 中英文规则全跑

# 默认 auto: 自动检测语言
python3 skill_validator.py ./my-skill --lang auto

# JSON 输出 (CI 使用)
python3 skill_validator.py ./my-skill --json
```

### 语言模式

| 模式 | 行为 |
|---|---|
| `auto`（默认） | 根据 SKILL.md 中文字占比自动判定语言 |
| `en` | 仅运行英文规则 |
| `zh` | 仅运行中文规则 |
| `mixed` | 运行所有中英文规则 |

自动检测阈值：
- 中文字符 > 15% → 中文
- 中文字符 < 5% → 英文
- 之间 → 混用

### 跨模型兼容性标注

```bash
# 标注此 Skill 兼容的编排模型族
python3 skill_validator.py ./my-skill --models gpt claude
python3 skill_validator.py ./my-skill --models all
```

可选值：`gpt`, `claude`, `sonnet`, `opus`, `all`。
该参数仅在输出头部显示标注信息，不影响检查逻辑。

## 输出

```
============================================================
检查: my-skill
============================================================
  ✓ 目录命名规范
  ✓ Hub-and-Spoke 目录结构完整性
  ⚠ SKILL.md Frontmatter & Description
      → description 以'本技能旨在...'开头（中文废话模式）
  ✗ 反模式检测: 轨道化常识
      → 检测到 '教导基础 Git 命令' — 模型预训练已掌握，建议删除
```

### 状态

| 图标 | 含义 |
|---|---|
| ✅ ✓ | 通过 |
| ⚠ | 警告（建议性） |
| ✗ | 失败（需修复） |

## 退出码

- **0** — 所有检查通过（无失败项）
- **1** — 存在失败项

## 反模式说明

> 检查规则来源：Perplexity 实践 + 2026 最新权威来源（Anthropic 官方规范、UC Irvine 对 238 个真实 SKILL.md 的 skill smells 实证研究、社区 TDD-for-Skills、可靠性六项实践）。出处与完整 26 种 skill smells 分类见 `docs/2026-latest-skill-practices.md`。

### 轨道化常识（Railroading）

指在 SKILL.md 中教导 AI 模型已经通过预训练掌握的基础知识。典型表现：

```
# 英文
"To create a function, use the def keyword..."
"Install packages with pip install..."

# 中文
"要定义一个函数，可以使用 def 关键字..."
"使用 pip 安装依赖..."
```

### 常识灌输（Chinese Common Knowledge Common）

中文独有反模式：长篇解释性文字，如"Git 是一个版本控制系统"、"Python 是一种编程语言"等模型预训练已掌握的内容。

### 硬编码资产

API 端点、密钥、Token、配置地址等高变动信息直接写在 SKILL.md 中。应外部化到 `config.json`。

## 项目

```text
how-to-make-skills/
├── skill_validator.py              # 主程序 (20 项检查)
├── how-to-write-skills-guide.md    # Agent Skill 编写指南 (含 2026 最新实践)
├── template/your-skill/            # Skill 目录模板
│   ├── SKILL.md                    #   核心入口 (含 验证/Gotchas 章节)
│   ├── evals/                      #   评估集 (positive.json + negative.json)
│   ├── scripts/                    #   确定性脚本
│   ├── references/                 #   按需加载的深度资料 (>100 行需 TOC)
│   ├── assets/                     #   模板/Schema
│   └── config.json                 #   初始化配置 + 高频变动资产
├── docs/
│   ├── 2026-latest-skill-practices.md   # 2026 最新实践综述 (带出处)
│   └── perplexity-agent-skills-guide-summary.md  # Perplexity 原文摘要
└── README.md                       # 本文件
```

## License

MIT
