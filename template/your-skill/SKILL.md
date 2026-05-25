---
name: your-skill
description: "Load when user says... (描述用户意图，以 Load when 开头，50 词以内)"
depends: []
metadata:
  author: ""
  models: ["gpt", "claude"]
  review_status: draft
---

<!--
  ====================================================
  SKILL.md — 核心入口文件
  原则:
  - < 5000 tokens
  - 写意图，不写指令序列
  - Gotchas (陷阱/反例) 放在末尾
  - 长篇内容剥离到 references/ scripts/ assets/
  ====================================================
-->

## 策略

<!-- 此处写核心策略：模型应该以什么思路来完成这个任务 -->

## 边界条件

<!-- 此处写关键限制/注意事项 -->

## Gotchas

<!-- Agent 每次在边缘情况失败后，在此追加一条 gotcha -->

- 已知陷阱 1：...
- 已知陷阱 2：...
