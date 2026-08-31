# Agent Skill 编写实战指南

> 面向想为自己（AI Agent）编写高质量技能的开发者。
> 本指南在《Agent Skill Authoring Specification》与 Perplexity 实践的基础上，融入了 2026 年的最新来源：
> Anthropic 官方规范、UC Irvine 对 238 个真实 SKILL.md 的实证研究（skill smells）、社区 TDD-for-Skills 方法论、可靠性六项实践（Atlan 2026-07）与 Contractual Skills 框架。
> 完整出处与细节见 `docs/2026-latest-skill-practices.md`。

---

## 一、核心认知：Skill 不是什么

| 误解 ❌ | 真相 ✅ |
|---|---|
| Skill 是一份详细的操作说明书 | Skill 是**结构化行为上下文补丁** |
| Skill 是像传统代码一样去写 | Skill 是像**设计提示词**一样去设计，但要像写代码一样**先测再写** |
| Skill 内容越多越好 | **每个 Skill 都是一种税**——多余 token = 成本 ↑ + 注意力分散 ↑ |

**黄金法则**：每写一句话，问自己——*"如果没有这句话，Agent 真的会犯错吗？"* 如果不会，删掉。

**指令预算**（2026 社区共识）：模型稳定遵循的指令约 150 条，系统提示已烧掉约 50 条。每加一条指令都在稀释**所有**指令的遵循率——对"删"要毫不留情。

---

## 二、铁律：TDD for Skills

**NO SKILL WITHOUT FAILING TEST FIRST** —— 没有先失败的测试就不写 Skill。未测试的 skill 就是未测试的代码，上线必坏。

| 阶段 | 操作 |
|---|---|
| **RED** | **不带 skill** 让 Agent 跑目标任务，逐字记录它做错什么、用了什么借口、跳过了哪步 |
| **GREEN** | 针对这些**真实失败**写最小 skill；复跑，验证行为确实改变 |
| **REFACTOR** | 找出 Agent 新发明的合理化借口 → 堵住漏洞 → 再测 |

要点：

- Skill 解决的是 RED 阶段观察到的**具体失败**，不是想象中的失败
- 评估集（正样本/负样本/邻域混淆）在 RED 之前就准备好，这就是 EDD（Evals-Driven Development）
- 复测不只在改指令时，**数据/schema/模型阵容变化时也要重测**

---

## 三、目录结构标准（Hub-and-Spoke 架构）

每个 Skill 必须是一个**目录**，而非单个文件：

```
your-skill-name/          # 全小写、连字符；≤64 字符；禁用保留词 anthropic/claude
├── SKILL.md              # 核心入口：元数据 + 高价值核心指令（< 500 行 / ~5000 tokens）
├── scripts/              # 可直接运行的脚本（禁止让 Agent 现场发明代码）
├── references/           # 深度资料（按需加载；>100 行的文件顶部加目录 TOC）
├── assets/               # 模板、Schema 等静态资产
└── config.json           # 初始化配置 + 高频变动资产（API 地址、版本、端点）
```

**结构约束**（官方 + 实证）：

- `name` 必须与目录名一致
- 路径一律**正斜杠**（Agent 按文件系统导航，反斜杠路径是高频 smell）
- 避免深层嵌套引用：A 引用 B、B 再引用 C 时，C 常被只读一半——引用保持一层
- references/ 超过 100 行，顶部必须有 TOC（模型可能只部分读取）
- 多领域技能按域分目录，避免加载无关上下文
- 复杂领域（如税法）建 2-3 层树状结构，严禁平铺

**三层上下文成本**：

```
Index 层 (~100 tokens)     ← 全局常驻，仅做路由触发（name + description）
  │
  ▼ 路由命中 → load_skill
Load 层 (< 5,000 tokens)   ← SKILL.md 正文，条件加载
  │
  ▼ 运行时按需 Read
Runtime 层 (无上限)         ← scripts/ references/，用完即走
```

---

## 四、Description：路由触发器（最难的一行）

description 是**选择器**：模型可能要从 100+ 个 skill 里挑一个，它必须给足"何时选我"的信号。

### 硬约束（官方规范）

- 非空，**≤ 1,024 字符**，不得含 XML 标签
- 公式：`[做什么] + [何时用] + [关键词]`，三者缺一即不合格
- 以 "Load when..." / "Use when..." 开头，描述**触发场景**，不是流程总结
- 目标 50 词以内（≤1024 字符是上限不是目标）

### 写法

- 包含用户**真实会说的措辞**（从 RED 阶段/生产查询采样）
- 含同义词（timeout/hang/freeze）、相关工具与文件名
- 多 skill 域重叠时，必须写 **NOT-for 边界**："NOT for: 重型多阶段分析（用 advanced-code-review）"
- 纪律型 skill：写**违反前症状**，在 Agent 违规*之前*触发（"before writing implementation code"，而不是"当你忘了写测试时"）

### 反模式（触发任意一条即重写）

| 反模式 | 例子 | 后果 |
|---|---|---|
| 工作流泄漏 | "3-phase process: plan, execute, verify" | Agent 从 description 提取计划，**跳过加载正文** |
| 纯抽象 | "Use when reviewing code" | "look at my changes" 匹配不上 |
| 术语先行 | "Use when roundtable returns ITERATE verdict" | 用户从不说这种话 |
| 过宽 | "Use when writing or modifying code" | 每个编码任务都误触发 |
| 过窄 | "Use before design phase only" | 多阶段有用的技能被锁死在一刻 |
| 废话开场 | "This skill helps to..." / "本技能旨在..." | 信号密度为零 |

---

## 五、正文写法

### 写意图，不写指令序列

- ❌ `git log → git checkout → git cherry-pick`（轨道化常识 + Series of Commands smell）
- ✅ "Cherry-pick the commit onto a clean branch. Resolve conflicts preserving intent. If it can't land cleanly, explain why."

### 必须有验证闭环（2026 实证高频缺失项）

- 复杂任务：先规划 → 执行 → **验证**，不能把产出当一次性过程
- 复杂工作流给一份**可打勾的 checklist**
- 明确何时**暂停交人**（人工审批点），而不是 Agent 自己拍板

### 多条路径必须有决策树

列出多个替代工具却不给默认推荐 = "Option Buffet" smell。给默认 + 决策条件。

### 纪律规则必须防合理化（见 §六）

### 语言纪律

- 每个工具/命令**精确命名**，禁止 "appropriate" / "relevant" / "when needed" 这类模糊词
- 禁止 "Be thorough" / "要小心" 这类无操作含义的形容词
- 多段论证只留一句 why；规则放开头或结尾（中间是注意力盲区）
- 关键警告必须用 `## Gotchas` 或同等显眼的标题（"Buried Gotchas" 是高频 smell）

---

## 六、防合理化（Rationalization-Proofing）

**实证结论：Rationalization Loophole 出现在 94% 的真实 skill 里**——缺"防止 Agent 找理由跳过必要步骤"的护栏是最普遍的缺陷，且一旦引入几乎从不被修复。

纪律型/关键流程型 skill 必做五件事：

1. **"精神与字面"原则前置**：明确写出"违反规则字面就是违反规则精神"，一次切断整类辩解
2. **强措辞**：ALWAYS / NEVER / MANDATORY；弱措辞（should / better / 一般地）= 留漏洞
3. **合理化对照表**：RED 阶段捕获的每条借口逐条进表

   | 借口 | 现实 |
   |---|---|
   | "太简单不用测" | 简单代码也会坏，测试只要 30 秒 |
   | "我稍后补测试" | 事后通过的测试证明不了任何东西 |
   | "这次情况特殊" | 没有例外。除非命中显式列出的逃生舱 |

4. **红旗清单**：列出"当你冒出这些念头时 → 停下重来"
5. **合法逃生舱**：真有例外就显式枚举，然后一句"其余一律无例外"

元策略：每发现一条新借口 → 原文记录 → 进对照表 + 红旗清单 → 重测，直到 Agent 找不到任何有效的合理化。

---

## 七、Skill Smells 自查清单（2026 实证，26 种中的高频项）

> UC Irvine 研究：99%+ 的真实 SKILL.md 至少含 1 种 smell，且随演进越改越多。写完逐条过，触发任意一条即修复。

| # | Smell | 自查问题 |
|---|---|---|
| 1 | Rationalization Loophole (94%) | 关键步骤有没有被"找理由跳过"的护栏？ |
| 2 | Stepless Workflow | 工作流是不是一段未分解的散文？ |
| 3 | Series of Commands | 是否在逐行规定命令序列而非描述目标？ |
| 4 | Missing Decision Tree | 多路径没有决策树/默认推荐？ |
| 5 | No Validation Step | 产出后没有验证环节？ |
| 6 | Execute Without a Plan | 复杂任务直接执行、无中间校验？ |
| 7 | Never Asks Human | 高风险决策没有暂停交人的机制？ |
| 8 | No Progress Tracking | 多步流程没有进度跟踪？ |
| 9 | Undelegated Detail | 低层细节堆在正文没剥离？ |
| 10 | Lengthy Body / Name / Description | 正文 >5000 词、name >64 字符、description >1024 字符？ |
| 11 | Confusing Description | 缺"做什么/何时用/关键词"之一？ |
| 12 | Backslash Path | 路径用了反斜杠？ |
| 13 | No Guardrails | 没有阻止不恰当/不可能任务的护栏？ |
| 14 | Buried Gotchas | 关键警告没用显眼标题？ |
| 15 | Missing Example | 没有任何上下文示例？ |
| 16 | Time Sensitive | 含会过期的时效信息？ |
| 17 | XML in Description | description 含 XML 标签（可注入指令）？ |
| 18 | Unclear Skill Name | 名字看不出能力（如 `dig`）？ |
| 19 | Missing Utility Script | 确定性任务没固化为脚本？ |
| 20 | Option Buffet | 列多个替代工具不给默认？ |

完整 26 种分类见 `docs/2026-latest-skill-practices.md` §二。

---

## 八、资产剥离

写完 SKILL.md 正文后检查：

- 有长篇表格？→ 挪到 `references/`
- 有 JSON Schema？→ 挪到 `assets/`
- 有可执行的确定性逻辑？→ 固化到 `scripts/`（让脚本**被执行**，而不是被读进上下文）
- 有大量边界 case？→ 挪到 `SPECIAL_CASES.md`
- 有 API 地址/版本/端点等高频变动资产？→ 挪到 `config.json`
- 脚本与正文的分工要写清楚："这个脚本是执行的，那个文档是阅读的"

保持 SKILL.md 本身精炼：正文 < 500 行（~5000 tokens）是红线，接近上限就拆。

---

## 九、可靠性六项实践（2026-07）

> 几乎所有指南都停在第五项；跳过第六项，skill 仍会**自信地**给出错误答案。

| # | 实践 | 关键动作 |
|---|---|---|
| 1 | 渐进披露 | 正文 < 500 行；细节剥离；references > 100 行加 TOC |
| 2 | 可发现的 description | 触发公式 + 真实措辞 + NOT-for 边界 |
| 3 | 单一目的 scope | 一个 skill 一个内聚任务，不因"相关"扩域 |
| 4 | 像代码一样版本化 | 进版本控制、打 tag、**审批人与作者分离** |
| 5 | 真实任务测试 | ≥3 个来自**真实历史任务**的场景（非虚构）；覆盖所有部署模型；**数据/schema 变化时重测** |
| 6 | 数据可信度 | 每个数据源有具名 owner 并认证其"当前性"；经治理路径（MCP 等）访问而非硬编码查询；定义源变化时的重验证触发器 |

量化警示：SkillsBench 中精选 skill 平均提升通过率 16.2 分，但 84 个任务里 **16 个变差了**——skill 也可能通过路由干扰让别的任务回归（action at a distance 的实证）。

---

## 十、验证防线（四层测试）

产出后通过以下测试才允许合并：

1. **路由测试**：负样本（邻域混淆）不得错误激活此 skill；正样本必须激活
2. **渐进读取检查**：模型只在需要时才去读 `references/`（观察实际读取路径，意外顺序 = 结构不直观）
3. **LLM Judge 评估**：用最强模型对 Agent 端到端输出打分
4. **跨模型回归**：在 GPT、Claude（Sonnet/Opus 等）所有目标模型上跑通，无远距离干扰

**观察模型导航行为**（迭代依据，不是假设）：

| 观察 | 含义 |
|---|---|
| 意外读取顺序 | 结构不如想象的直观 |
| 漏读引用文件 | 链接要更显眼/更靠前 |
| 反复读同一文件 | 该内容应上移到 SKILL.md |
| 从不读某文件 | 可能多余，删掉 |

**合并前检查清单**：

- [ ] RED 阶段已记录不带 skill 时的逐字失败
- [ ] GREEN 阶段复跑验证行为改变
- [ ] description 以 "Use/Load when" 开头，只含触发条件，无工作流摘要
- [ ] frontmatter 含 `name`（= 目录名，≤64 字符，无保留词）和 `description`（≤1024 字符，无 XML）
- [ ] 正文 < 500 行；关键规则在开头或结尾
- [ ] 有验证闭环、有 Gotchas 章节、≥1 组好/坏示例
- [ ] 每个工具/命令精确命名，无模糊措辞
- [ ] 纪律规则有强措辞 + 对照表 + 红旗清单 + 逃生舱
- [ ] 3+ 阶段的工作流已拆 orchestrator / phase commands
- [ ] 路径全正斜杠；高频变动资产已外部化

---

## 十一、维护：Append-Mostly + 版本化

Skill 生命在于维护，遵循**只增不删**（追加式）原则，不要大改主文件：

| 场景 | 动作 |
|:---|:---|
| Agent 在某个场景失败了 | → 尾部追加一条 Gotcha（含根因） |
| Agent 用了新借口跳过步骤 | → 原文记录 → 进合理化对照表 + 红旗清单 → 重测 |
| Agent 在不该加载时加载了 | → 收紧 description + 添加负样本 eval |
| Agent 在该加载时没加载 | → 添加触发关键词 + 正样本 eval |
| 数据 schema / 模型阵容变化 | → 重跑全部 eval |
| 系统提示变更 | → 检查冲突或重复 |

版本化纪律：

- 每个版本记录**审批人**（与作者分离），回归可分钟级回滚
- description 合并后不要随意改——它影响的是**所有** skill 的路由格局（action at a distance）；必须改时，配套提交 eval 变更
- 每季度（或任务模式变化时）重跑一次全套审计

---

## 十二、一句话总结

> **Skill 是"如果缺了它 Agent 会犯错"的高价值上下文补丁：先测后写（RED→GREEN→REFACTOR），用目录结构渐进加载，用触发式 description 保证路由精度，用护栏防合理化，用评估集保证数据可信，用 Append-Mostly 持续进化。多余的全删掉。**
