# Perplexity Agent Skills 设计、优化与维护指南 — 摘要

> 原文：[Designing, Refining, and Maintaining Agent Skills at Perplexity](https://research.perplexity.ai/articles/designing-refining-and-maintaining-agent-skills-at-perplexity)
> 来源：Perplexity Research，May 1, 2026

---

## 一、核心观点：Skill 不是传统代码

编写 Skill 与编写传统软件有本质区别。传统软件工程的最佳实践（如 Python 的 Zen of Python）在 Skill 创作中很多是反模式：

| Zen of Python | Zen of Skills |
|:---|---:|
| Simple is better than complex | **A Skill is a folder, not a file. Complexity is the feature.** |
| Explicit is better than implicit | **Activation is implicit pattern matching. Progressive disclosure.** |
| Sparse is better than dense | **Context is expensive. Maximum signal per token.** |
| Special cases aren't special enough to break the rules | **Gotchas ARE the special cases (they're the highest-value content).** |
| If the implementation is easy to explain, it may be a good idea | **If it's easy to explain, the model already knows it. Delete it.** |

---

## 二、什么是 Skill

一个 Skill 至少是四件事：

### 1. Skill 是一个目录（Directory）

Skill 不是单个 `SKILL.md` 文件，而是一个目录，包含：

- **SKILL.md** — 前置元数据 + 指令正文
- **scripts/** — 确定性逻辑（模型每次运行都会重新发明的东西，用代码固化）
- **references/** — 条件加载的文档（如"API 返回非 200 时读取 api-errors.md"）
- **assets/** — 模板、schema、数据
- **config.json** — 首次运行用户设置

**层次结构（Hierarchy）**：复杂领域可以用多级目录组织。例如，美国所得税 Skill 使用三级嵌套来组织 1,945 条 IRS 税法——如果不分层直接把所有内容塞给模型，性能比不加载 Skill 还差。

### 2. Skill 是一种格式（Format）

核心 `SKILL.md` 必须有：

- **name**：全小写、无空格、可用连字符，必须与目录名一致
- **description**：这是**路由触发器**，不是内部文档。应写"Load when..."而不是"这是一个做 X 的 Skill"
- **depends**：层次依赖
- **metadata**：审查和评估用
- Agent 系统可自定义 frontmatter 字段，或使用辅助 JSON/YAML 配置文件

### 3. Skill 是可调用的（Invocable）

Agent 在运行时加载 Skill。不同系统的加载策略不同：

1. Computer 调用 `load_skill(name="...")`
2. 复制 Skill 目录到隔离沙箱
3. 递归自动加载 `depends` 中的依赖
4. 剥离 frontmatter，Agent 只看到正文和附加文件

### 4. Skill 是渐进式的（Progressive）

Perplexity Computer 有三种上下文成本层级：

| 层级 | 加载内容 | 预算 | 何时支付 |
|:---:|:---|:---:|:---|
| **Index** | 每个非隐藏 Skill 的 `name: description` | ~100 tokens / Skill | 每个会话、每个用户、始终支付 |
| **Load** | 完整 SKILL.md 正文 | ~5,000 tokens | 加载 Skill 时 |
| **Runtime** | scripts/ references/ assets/ 等 | 无上限 | Agent 实际读取时 |

- **Index 层级**：门槛最高，description 必须极其精炼
- **Load 层级**：正文不超过 5,000 tokens，每句话都要有用
- **Runtime 层级**：最宽松，适合放条件分支逻辑

---

## 三、什么时候需要 Skill

### 需要 Skill 的情况
- Agent 在没有特殊上下文时会犯错
- 需要跨运行保持高度一致性和确定性
- 知识是持久的但不在训练数据中（如内部工作流、数据截止日期）
- 个人 taste / 风格偏好（如设计师指定的字体和排版规范）

### 不需要 Skill 的情况
- 模型已经知道怎么做（如一系列 git 命令顺序执行→适合文档，不适合 Skill）
- 重复系统提示中的内容
- 变化太快，维护跟不上（如频繁变更的远程 MCP 端点）

### 每个 Skill 都是税

> 每一句话都应该通过测试："没有这句指令，Agent 会犯错吗？" 如果答案是"不会"，这句就不该存在。

---

## 四、如何构建 Skill

### Step 0：先写评测（Evals）

在写任何 Skill 代码之前，先准备评测用例：

- **真实用户查询**：从生产环境或核心用户群采样
- **已知失败案例**：Agent 因为 Skill 不存在而失败的场景
- **邻域混淆**：接近你的领域边界但应路由到其他 Skill 的案例

需要同时有正例和反例。反例（negative examples）特别重要。

### Step 1：写 Description（最难的一行）

这是路由触发器，不是文档。

- 以 "Load when..." 开头
- 目标 50 词以内
- 描述用户的意图（最好来自真实查询），而不是总结工作流
- **坏例子**："此 Skill 用于监控 PR 状态"
- **好例子**："Load when the user says 'babysit', 'watch CI', 'make sure this lands'"

### Step 2：写正文（Body）

- **跳过显而易见的步骤**：不需要写 `git log → git checkout → git cherry-pick` 这样的命令序列
- **写意图，不写指令序列**：如 "Cherry-pick the commit onto a clean branch. Resolve conflicts preserving intent. If it can't land cleanly, explain why."
- **关注 Gotchas（陷阱）**：这是最高信号密度的内容——告诉模型"不要做什么"
- **条件性或重内容**：移到 spokes 目录（references/ scripts/ 等），实现渐进式加载

### Step 3：利用层级结构

- `scripts/` — 确定性逻辑，模型不用每次重新发明
- `references/` — 条件加载的文档
- `assets/` — 模板（如 report-template.md、输出 schema）
- `config.json` — 首次运行用户设置

### Step 4：迭代

- 在分支上做多次迭代
- 用 hero query 集跑多轮 eval
- 描述中的小词改动对路由影响很大（包括对其他 Skill 的溢出效应）
- 尽量**一次性提交**完整变更集 + 评测集

### Step 5：发布（Ship）

---

## 五、如何维护 Skill

### Gotchas 飞轮

Skill 是 **append-mostly** 的，gotchas 部分随着时间积累最多价值：

| 场景 | 动作 |
|:---|:---|
| Agent 在某个场景失败了 | → 添加一个 gotcha |
| Agent 在不该加载时加载了 Skill | → 收紧 description + 添加反例 eval |
| Agent 在该加载时没加载 | → 添加关键词 + 正例 eval |
| 系统提示变更 | → 检查冲突或重复 |

**不要在 Skill 合并后随意修改 description**。如果必须改，要写配套的 evals。

### 评测套件

Perplexity 维护多套 eval：

1. **Skill loading / file reads** — 检查精确率、召回率、禁止加载检测
2. **渐进式加载** — Agent 加载 Skill 后是否读取了正确的附属文件
3. **端到端任务完成** — 完整 agent 循环 + LLM judge 评分
4. **跨模型评测** — Skill 需要在不同模型（GPT、Claude Opus、Claude Sonnet）上表现一致

---

## 六、最终要点

- **写的 Skill 越多，就越擅长写 Skill**
- 任何你每周/每日做的重复性任务，都值得写成 Skill 来回收时间
- 事后总结、PR 审查等都可以用 Agent Skill 完成初稿
- **少即是多**：一个容易写的 Skill 很可能太长，或者根本不该存在
- **新 Skill 可能会破坏已有的 Skill**——即使你没动过它们（action at a distance）
- 工具一直在进化，善用所有可用工具

---

> "I have only made this letter longer because I have not had the time to make it shorter." — Blaise Pascal, 1657
>
> 写一个简短的 Skill 很难。正是这种难度造就了它的价值。
