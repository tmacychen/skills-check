---
name: your-skill
description: "Use when [用户真实措辞/触发场景，含同义词]. NOT for: [邻近但不该触发的场景，改用 other-skill]. (≤1024 字符，≤50 词，只写触发条件，不写流程)"
version: 0.1.0
depends: []
metadata:
  author: ""
  models: ["gpt", "claude"]
  review_status: draft
  approver: ""
---

<!--
  ====================================================
  SKILL.md — 核心入口文件
  红线: < 500 行 / ~5000 tokens; 路径一律正斜杠
  原则:
  - 写意图，不写指令序列 (git log → checkout → … 属于反模式)
  - description 是路由选择器，不是文档 (禁止工作流摘要)
  - 关键规则放开头或结尾 (中间是注意力盲区)
  - 高频变动资产 (API 地址/版本/端点) 外部化到 config.json
  - 长表格 → references/  长 Schema → assets/  确定性逻辑 → scripts/
  - Gotchas (陷阱/反例) 放在末尾，每次失败后追加一条
  ====================================================
-->

## 策略

<!-- 核心策略：Agent 应以什么思路完成这个任务。
     多条可选路径时：给默认推荐 + 决策条件（不要只列选项不给默认） -->

## 边界条件

<!-- 关键限制 / 何时停止并向用户请求确认（人工审批点）/
     本技能不负责什么（NOT-for，与 description 呼应） -->

## 验证

<!-- 产出后如何验证：跑什么检查、什么算通过；
     复杂流程给一份可逐项打勾的 checklist -->

## Gotchas

<!-- Agent 每次失败后在此追加一条（Append-Mostly：只增不删，写清根因） -->

- 已知陷阱 1：…
- 已知陷阱 2：…
