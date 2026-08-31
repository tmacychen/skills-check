# Agent Skill 编写最新实践综述（2026）

> 本文件汇总 2025-12 至 2026 年中的最新权威来源：Anthropic 官方规范、UC Irvine 对 238 个真实 SKILL.md 的实证研究（arXiv 2607.01456）、社区 TDD-for-Skills 方法论、面向可靠性的六项实践（Atlan, 2026-07）与 Contractual Skills 框架（arXiv 2605.22634）。
> 所有结论均标注出处，供 `how-to-write-skills-guide.md` 的理论与 `skill_validator.py` 的规则设计参考。

---

## 一、官方规范硬约束（Anthropic, 2025-12）

来源：Claude Platform Docs — Agent Skills overview & best practices

| 字段/规则 | 约束 |
|---|---|
| `name` | ≤ 64 字符；仅小写字母/数字/连字符；不得含 XML 标签；保留词 `anthropic`、`claude` 禁用；必须与目录名一致 |
| `description` | 非空；≤ 1,024 字符；不得含 XML 标签；必须同时说明"做什么 + 何时用" |
| SKILL.md 正文 | < 500 行为最优；接近上限即拆分到独立文件 |
| references/ 文件 | > 100 行应在文件顶部加目录 (TOC) —— 模型可能只部分读取 |
| 引用深度 | 避免深层嵌套引用（被引用文件再引用别的文件时，模型可能只读到一半） |

要点：

- **加载成本分层**：会话启动只预加载所有 skill 的 name+description（metadata）；SKILL.md 正文在命中后才加载；references/scripts 在实际读取时才支付成本。
- **description 是选择器**：模型可能要从 100+ 个 skill 里选一个，description 必须给足"何时选我"的信号，正文只给实现细节。
- **命名**：推荐动名词形式（gerund，如 `processing-payments`），明确描述技能提供的活动。
- **渐进披露三种组织模式**：
  1. 单文件并列（FORMS.md / reference.md / examples.md，按需加载）
  2. 按领域分目录（多领域技能按域拆分，避免加载无关上下文）
  3. 条件细节（正文写"X 发生 → 读 references/x.md"）
- **工作流写检查清单**：复杂流程给模型一份可复制到回复里逐项打勾的 checklist。
- **观察模型导航行为**：意外读取顺序 → 结构不直观；漏读引用文件 → 链接要更显眼；反复读同一文件 → 该内容应进 SKILL.md；从不读某文件 → 可能多余。
- **跨模型测试**：skill 是模型的补丁，有效性依赖底层模型，必须在所有目标模型上测试。

---

## 二、Skill Smells：238 个真实 SKILL.md 的实证研究（UC Irvine, 2026）

来源：arXiv 2607.01456 *From Anatomy to Smells: An Empirical Study of SKILL.md in Agent Skills*

核心发现：

- 对 238 个真实 skill 定性分析，归纳出 13 个高层 + 44 个低层语义组件；从 29 个来源提炼 26 条最佳实践，其违反即 26 种 "skill smell"（其中 20 种是"缺失型"）。
- **99% 以上的 SKILL.md 至少含 1 种 smell；且 smell 一旦引入，随 skill 演进几乎不会消失**（越改越多）。
- 26 种 smell 中 11 种出现在 50% 以上的文件里；**最常见的是 Rationalization Loophole (RL)：94%**；最少见的是 Lengthy Skill Name (LSN) 与 Lengthy Skill Description (LSD)。
- description 推荐结构：`[做什么] + [何时用] + [关键词]`，三者缺一即 CSD smell。

Smell 分类表：

| 类别 | Smell (缩写) | 含义 |
|---|---|---|
| 指导不足 | Stepless Workflow (TSW) | 整个工作流写成一段散文，未分解为步骤 |
| | Missing Decision Tree (MDT) | 有多种可选路径却没给决策树 |
| | Option Buffet (TOB) | 列多个替代工具却不给默认推荐 |
| | Missing Utility Script (MUS) | 适合固化为脚本的任务没提供脚本 |
| 过度规定 | Series of Commands (SOC) | 逐行规定命令序列（含硬编码路径），剥夺 Agent 自适应空间 |
| | No Validation Step (NVS) | 把产出当一次性过程，没有验证环节 |
| | Execute Without a Plan (EWP) | 复杂任务直接执行，缺中间规划/校验阶段 |
| | Never Asks Human (NAH) | 没有向人类请求反馈的机制 |
| 缺跟进护栏 | Rationalization Loophole (RL) | 没有防止 Agent 找理由跳过必要步骤的护栏 |
| | No Progress Tracking (NPT) | 多步流程没有进度跟踪机制 |
| 上下文膨胀 | Undelegated Detail (UD) | 低层实现细节内嵌在正文，未剥离到 references/scripts |
| | Lengthy Skill Body (LSB) | 正文超过 5,000 词 |
| | Lengthy Skill Name (LSN) | name > 64 字符 |
| | Lengthy Skill Description (LSD) | description > 1,024 字符 |
| | Confusing Skill Description (CSD) | description 缺"做什么/何时用/关键词"三要素之一 |
| | Backslash Path (BP) | 用反斜杠写路径（Agent 按文件系统导航，必须正斜杠） |
| 缺安全护栏 | No Guardrails (NG) | 没有阻止 Agent 尝试不恰当/不可能任务的护栏 |
| | Buried Gotchas (BG) | 关键警告没用推荐的 gotcha 标题凸显 |
| | Missing Usage Rules (MUR) | 缺少"何时/如何使用"的规则 |
| | Missing Caveats (MC) | 缺少常见注意事项及解法 |
| | XML in Description (XID) | description 含 XML 标签，可注入意外指令 |
| 上下文接地不足 | Missing Example (ME) | 缺少帮助 Agent 获得足够上下文的例子 |
| | Time Sensitive Skill (TSS) | 含时效信息，过期后误导 |
| | Unclear Skill Name (USN) | 名字看不出技能能力（如名为 `dig`） |

对本项目 validator 的直接启发：name/description 长度与 XML、反斜杠路径、验证闭环、防合理化护栏，均可做静态启发式检测（见 §六 映射表）。

---

## 三、TDD for Skills：RED → GREEN → REFACTOR（社区, 2025-2026）

来源：millionco/expect `skill-writing`、sickn33/agentic-awesome-skills `writing-skills`、ovargas/virtual-team、guanyang/open-agent-hub 等多个独立仓库的收敛实践

**铁律：NO SKILL WITHOUT FAILING TEST FIRST**（没有先失败的测试就不写 Skill）。写 skill 与写代码同构——未测试的 skill 就是未测试的代码，上线必坏。

| TDD 阶段 | Skill 等价操作 |
|---|---|
| RED | **不带 skill** 让子代理跑目标任务，逐字记录它做错什么、用了什么借口、跳过了哪步 |
| GREEN | 针对这些**真实失败**写最小 skill，复跑验证行为改变 |
| REFACTOR | 找出 Agent 新发明的合理化借口 → 堵住漏洞 → 再测 |

配套技术（纪律型 skill 专用）：

1. **显式封死每条漏洞**：不只陈述规则，逐条禁止具体绕行方式（"保留代码当参考"、"适配现有代码"都算违规）。
2. **"精神与字面"原则前置**：明确写出"违反规则字面就是违反规则精神"，一次切断整类辩解。
3. **合理化对照表 (Rationalization Table)**：RED 阶段捕获的每条借口进表，`| 借口 | 现实 |` 两列。
4. **红旗清单 (Red Flags)**：列出"当你冒出这些念头时 → 停下重来"。
5. **强措辞**：纪律规则用 ALWAYS/NEVER/MANDATORY，弱措辞（should/better/generally）= 留漏洞。
6. **承诺一致性**：引用 Agent 已声称的标准（"你声称遵循 TDD，先写代码就不是 TDD"）。
7. **合法逃生舱**：真有例外就显式枚举（"以下场景除外，其余一律无例外"），堵死"这次情况特殊"。
8. **description 写"违反前症状"**：在 Agent 违规*之前*触发 skill（"Use when implementing any feature, before writing code"），而不是事后。

Description 反模式（多来源一致）：

| 反模式 | 例子 | 后果 |
|---|---|---|
| 工作流泄漏 (workflow leakage) | "3-phase process: plan, execute, verify" | Agent 从 description 提取了计划，**跳过加载正文** |
| 纯抽象 | "Use when reviewing code" | 无触发短语，"look at my changes" 匹配不上 |
| 术语先行 | "Use when roundtable returns ITERATE verdict" | 用户从不说这种话 |
| 过宽 | "Use when writing or modifying code" | 每个编码任务都误触发 |
| 过窄 | "Use before design phase only" | 把多阶段有用的技能锁死在一个时刻 |

**重叠问题**：多个 skill 域重叠时，每个 description 必须写明"为什么选我 / 何时改用 X"（"NOT for: … use X instead"）。

**指令预算**：模型稳定遵循的指令约 150 条，系统提示已烧掉约 50 条；每加一条指令都在稀释所有指令的遵循率。高频加载的 skill 正文目标 < 200 词核心指令，普通 < 500 词。

**多阶段架构**：3 个阶段以上的 skill 必须拆成 orchestrator（只负责分发与阶段流转）+ phase commands（由子代理调用）；orchestrator 永不把 phase 内容拉进自己上下文。

---

## 四、可靠性六项实践（Atlan, 2026-07）

来源：Atlan *Agent Skill Best Practices: What Most Guides Skip*（2026-07-16）

"几乎所有指南（包括 Anthropic 自己的）都停在第五项；跳过第六项，skill 仍会对着一张过期的表自信地给出错误答案。"

| # | 实践 | 防止什么 | 关键动作 |
|---|---|---|---|
| 1 | 渐进披露 | SKILL.md 膨胀烧上下文 | 正文 < 500 行；细节剥离；references > 100 行加 TOC |
| 2 | 可发现的 description | skill 永不触发 | [做什么]+[何时用]+[关键词]；含用户真实措辞；写 NOT-for 边界 |
| 3 | 单一目的 scope | 过宽难精确激活 | 一个 skill 一个内聚任务；不因"相关"就扩域 |
| 4 | 像代码一样版本化 | 回归无法回滚 | SKILL.md 进版本控制、打 tag、**审批人与作者分离** |
| 5 | 真实任务测试 | 未测试的静默失败 | **≥3 个来自真实历史任务**的场景（非虚构）；覆盖所有部署模型；**数据/schema 变化时重测**（不只是改指令时） |
| 6 | **数据可信度验证** | 完美执行 × 坏数据 = 自信的错答 | 每个数据源有具名 owner；owner 认证其"当前性"（不只是"测试时能跑"）；经治理路径（MCP 等）访问而非硬编码查询；定义源变化时的重验证触发器 |

补充数据点：

- SkillsBench（86 任务 × 11 域）：精选 skill 平均提升通过率 16.2 分，但 84 任务中 16 个出现负向变化——**skill 也可能让结果变差**（action at a distance 的量化证据）。
- 社区 skill 中 26.1% 携带安全漏洞（任意代码执行、凭据泄露、指令注入、数据外泄、registry 投毒）；安装 skill 应像装生产软件一样做审计。
- 建议每季度或数据 schema/模型阵容/任务模式变化时重跑整套审计；用触发率（PreToolUse hook 遥测）跟踪路由质量，不要编造数据。
- 落地顺序建议：先 3+5（scope + 测试，判断 skill 是否值得保留）→ 6（数据可信，最高影响的缺口）→ 1/2/4。

---

## 五、Contractual Skills：企业级任务契约（arXiv 2605.22634, 2026）

来源：*Contractual Skills: A GovernSpec Design Framework for Enterprise AI Agents*

把 SKILL.md 从"自由格式提示片段"升级为**可读的任务契约**，显式字段：输入边界、权限、人工审批点、证据要求、输出契约、质量判据、验证步骤、交接/暂停规则。

实证结果：

- 8 个公开 skill 的契约化改写 A/B（48 任务 × 6 模型 × 2 次重复，1152 输出）：平均质量 4.692 → 4.914，**关键错误率 0.083 → 0.013**（降 6 倍多）。
- 契约化 skill 不能替代工具级护栏；高风险工具尝试的减少效果因模型而异。

定位：契约字段让模型、维护者、评估者指向同一组字段（"什么输入必需 / 什么动作允许 / 什么证据足够 / 输出形状 / 何时暂停交人"），价值在于**显式化与可评审**，而非让模型天生安全。对个人/小团队 skill 可只借鉴其"验证步骤 + 人工审批点 + 输出契约"三件套。

---

## 六、对本项目 validator 的映射表

| 新规则 | 来源 | 检测方式 | 级别 |
|---|---|---|---|
| description ≤ 1,024 字符（官方硬上限） | Anthropic 规范 | 长度统计 | fail（超上限） |
| name ≤ 64 字符、保留词 `anthropic`/`claude` 禁用 | Anthropic 规范 | 正则 | fail |
| description 含 XML 标签 (XID) | arXiv 2607.01456 | 正则 `<[a-zA-Z/][^>]*>` | fail |
| description 工作流泄漏 | TDD 社区 / 官方 | 检测 "process:"/"phase"/"step \d" 等工作流结构词 + 数字流程 | warn |
| 正文反斜杠路径 (BP) | arXiv 2607.01456 | 检测 `\\` 出现在路径样式的字符串中 | warn |
| 正文行数红线 > 500 行 | Anthropic 最佳实践 | 行数统计 | warn（原 5000-token 估算保留为补充） |
| 验证闭环 (NVS/EWP) | arXiv 2607.01456 | 多步工作流词出现但无 verify/validate/check/确认 类词 | warn |
| 防合理化护栏 (RL) | arXiv 2607.01456 / TDD 社区 | 含 ALWAYS/NEVER/MUST 类纪律规则但无例外枚举/红旗/对照表 | warn |
| references 长文件缺 TOC | Anthropic 最佳实践 | references/*.md > 100 行且顶部无目录式标题列表 | warn |
