#!/usr/bin/env python3
"""
Skill Validator — 对 Agent Skill 目录结构进行自动合规检查。
支持中英文技能检查。

用法:
    python3 skill_validator.py <path_to_skill_directory>
    python3 skill_validator.py /path/to/skills/   # 批量检查所有子目录

检查项:
    [01] 目录命名规范 (全小写、连字符)
    [02] Hub-and-Spoke 目录结构完整性
    [03] SKILL.md 是否存在
    [04] SKILL.md Frontmatter (description) 质量
    [05] Description 是否为触发句式
    [06] SKILL.md 正文 token 估算 (是否超过 5000)
    [07] 反模式: 单文件依赖 (检查是否整个 skill 只有一个 md 文件)
    [08] 反模式: 轨道化常识 (关键词启发式检测)
    [09] 反模式: 描述废话检测
    [10] 反模式: 硬编码敏感资产检测
    [11] 资产剥离: 检查是否有长表格/长配置内嵌在 SKILL.md 中
    [12] 负样本检查: 是否有评估集或 SPECIAL_CASES.md
    [13] 文件尺寸安全红线
    [14] 中文反模式: 常识灌输、教程式写作、分步教程检测
    [15] 官方硬约束: name ≤64 字符/保留词, description ≤1024 字符/无 XML/无工作流泄漏
    [16] 正文行数红线 (<500 行, 官方建议)
    [17] 反模式: 反斜杠路径 (BP smell, 路径必须正斜杠)
    [18] 反模式: 无验证闭环 (NVS/EWP smell, 多步工作流缺验证环节)
    [19] 反模式: 合理化漏洞 (RL smell, 强纪律规则缺防跳过护栏)
    [20] 渐进披露: references/ 长文件 (>100 行) 缺顶部 TOC
"""

import argparse
import os
import re
import sys
from pathlib import Path


# ── 颜色输出 ──────────────────────────────────────────────
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

OK = f"{GREEN}✓{RESET}"
WARN = f"{YELLOW}⚠{RESET}"
FAIL = f"{RED}✗{RESET}"
INFO = f"{CYAN}ℹ{RESET}"


# ── 辅助函数 ──────────────────────────────────────────────

def rough_token_count(text: str) -> int:
    """极简 token 估算 (中文 ~2字/token, 英文 ~4字符/token)"""
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]', text))
    ascii_text = re.sub(r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]', '', text)
    ascii_tokens = len(ascii_text) / 4
    cn_tokens = chinese_chars / 2
    return int(cn_tokens + ascii_tokens)


def read_file_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def find_long_lines(text: str, min_len: int = 120) -> list:
    """找出超长行 (可能含内嵌表格或配置)"""
    return [line for line in text.splitlines() if len(line.strip()) > min_len]


def contains_markdown_table(text: str) -> bool:
    """检测是否含 Markdown 表格"""
    return bool(re.search(r'^\|.+\|$', text, re.MULTILINE))


def detect_language(text: str) -> str:
    """自动检测文本语言: 'zh' (中文为主), 'en' (英文为主), 'mixed' (混用)"""
    if not text.strip():
        return 'en'
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    total_printable = len(re.findall(r'\S', text))
    if total_printable == 0:
        return 'en'
    ratio = chinese_chars / total_printable
    if ratio > 0.15:
        return 'zh'
    elif ratio < 0.05:
        return 'en'
    else:
        return 'mixed'

# ── 检查项 ────────────────────────────────────────────────

class CheckResult:
    def __init__(self, name: str):
        self.name = name
        self.status = OK
        self.messages = []

    def ok(self, msg: str = ""):
        self.status = OK
        if msg:
            self.messages.append(("ok", msg))
        return self

    def warn(self, msg: str):
        if self.status != FAIL:
            self.status = WARN
        self.messages.append(("warn", msg))
        return self

    def fail(self, msg: str):
        self.status = FAIL
        self.messages.append(("fail", msg))
        return self

    def __str__(self):
        icon = self.status
        lines = [f"  {icon} {BOLD}{self.name}{RESET}"]
        for kind, msg in self.messages:
            prefix = {"ok": f"    {GREEN}→{RESET}", "warn": f"    {YELLOW}→{RESET}", "fail": f"    {RED}→{RESET}"}[kind]
            lines.append(f"  {prefix} {msg}")
        return "\n".join(lines)


def check_naming(dirname: str) -> CheckResult:
    r = CheckResult("目录命名规范")
    if not re.match(r'^[a-z0-9]+(-[a-z0-9]+)*$', dirname):
        return r.fail(f"目录名 '{dirname}' 不是全小写连字符格式 (例: my-skill-name)")
    # 官方规范: name ≤ 64 字符; 禁用保留词 anthropic / claude
    if len(dirname) > 64:
        r.fail(f"目录名 {len(dirname)} 字符 > 64 (官方硬上限)")
    if "anthropic" in dirname or "claude" in dirname:
        r.fail("目录名含保留词 anthropic/claude (官方禁用)")
    return r.ok(f"✓ 目录名 '{dirname}' 符合规范")


def check_directory_structure(skill_dir: Path) -> CheckResult:
    r = CheckResult("Hub-and-Spoke 目录结构完整性")
    required = ["SKILL.md"]
    optional = ["scripts", "references", "assets", "config.json"]

    for item in required:
        if not (skill_dir / item).exists():
            r.fail(f"缺少必需文件: {item}")

    if r.status == OK:
        r.ok("SKILL.md 存在")

    # 检查可选目录
    found_optional = []
    for item in optional:
        if (skill_dir / item).exists():
            found_optional.append(item)
    if found_optional:
        r.ok(f"可选组件: {', '.join(found_optional)}")
    else:
        r.warn("无可选组件 (scripts/ references/ assets/ config.json) — 简单技能可接受")

    return r


def check_frontmatter(skill_md: Path, lang: str = 'mixed') -> CheckResult:
    r = CheckResult("SKILL.md Frontmatter & Description")
    content = read_file_safe(skill_md)
    if not content.strip():
        return r.fail("SKILL.md 为空")

    # 解析 frontmatter (--- 包裹的 YAML)
    fm_match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if not fm_match:
        return r.warn("未找到 Frontmatter (--- 包裹的元数据块)")

    fm_text = fm_match.group(1)
    desc_match = re.search(r'^description\s*:\s*(.+)$', fm_text, re.MULTILINE)
    if not desc_match:
        return r.fail("Frontmatter 中缺少 description 字段")

    desc = desc_match.group(1).strip().strip('"').strip("'")
    desc_tokens = rough_token_count(desc)

    # 官方硬约束 (2026): description ≤ 1,024 字符; 不得含 XML 标签
    if len(desc) > 1024:
        r.fail(f"description {len(desc)} 字符 > 1024 (官方硬上限)")
    if re.search(r'<[a-zA-Z/][^>]*>', desc):
        r.fail("description 含 XML 标签 (XID smell — 可注入意外指令，官方禁用)")

    r.ok(f"description 已找到 ({desc_tokens} tokens)")

    # 检查是否以 Load when / Use when (2026 社区惯例) 或 加载当 开头
    if not (desc.lower().startswith("load when") or desc.lower().startswith("use when") or desc.startswith("加载当")):
        r.warn(f"description 不以 'Load when'/'Use when' 或 '加载当' 开头 (当前: {desc[:60]}...)")

    # 检查长度
    if desc_tokens > 60:
        r.warn(f"description 约 {desc_tokens} tokens (超过 60)，建议精简")

    # 工作流泄漏 (2026 社区共识): Agent 会从 description 提取计划并跳过加载正文
    workflow_leak_patterns = [
        (r'(?i)(\d+)\s*[-–]\s*(phase|step)', "description 含 N-phase/N-step 工作流摘要"),
        (r'(?i)\b(plan\s*[,，]\s*execute\s*[,，]\s*verify)', "description 含 plan/execute/verify 流程摘要"),
        (r'(?i)(workflow|pipeline)\s*[:：]', "description 含 workflow/pipeline 摘要"),
    ]
    for pat, msg in workflow_leak_patterns:
        if re.search(pat, desc):
            r.warn(f"{msg} — Agent 会直接照做而跳过加载正文，description 应只写触发条件")

    # 检查废话模式 — 根据语言选择规则
    garbage_patterns = []
    if lang in ('en', 'mixed'):
        garbage_patterns += [
            (r'(?i)this skill (helps|provides|allows|enables)', "反模式3: 以 'This skill helps/provides...' 开头"),
        ]
    if lang in ('zh', 'mixed'):
        garbage_patterns += [
            (r'(?i)技能(可以|用于|帮助|提供)', "description 使用了面向人类的简介句式"),
            (r'该技能用于', "description 以'该技能用于...'开头（中文废话模式）"),
            (r'本技能旨在', "description 以'本技能旨在...'开头（中文废话模式）"),
            (r'此技能提供', "description 以'此技能提供...'开头（中文废话模式）"),
            (r'这个技能的作用是', "description 以'这个技能的作用是...'开头（中文废话模式）"),
            (r'该技能可以帮助用户', "description 以'该技能可以帮助用户...'开头（中文废话模式）"),
        ]
    for pat, msg in garbage_patterns:
        if re.search(pat, desc):
            r.fail(msg)

    return r


def check_body_quality(skill_md: Path, lang: str = 'mixed') -> CheckResult:
    r = CheckResult("SKILL.md 正文质量检查")
    content = read_file_safe(skill_md)
    body = content
    # 去掉 frontmatter
    body = re.sub(r'^---\s*\n.*?\n---\s*\n', '', body, count=1, flags=re.DOTALL)
    if not body.strip():
        return r.warn("Frontmatter 后无正文内容")

    tokens = rough_token_count(body)
    r.ok(f"正文约 {tokens} tokens")

    # 超过 5000 tokens 警告
    if tokens > 5000:
        r.warn(f"正文 {tokens} tokens > 5000，应剥离部分内容到 references/ 或 assets/")

    # 正文行数红线 (2026 官方建议): < 500 行为最优
    body_lines = len(body.splitlines())
    if body_lines > 500:
        r.warn(f"正文 {body_lines} 行 > 500 (官方建议上限)，应拆分内容到独立文件")

    # 长表格检测
    if contains_markdown_table(body):
        r.warn("正文含 Markdown 表格 — 如为长配置表，建议剥离到 references/ 或 assets/")

    # 超长配置行
    long_lines = find_long_lines(body, 150)
    if len(long_lines) > 5:
        r.warn(f"发现 {len(long_lines)} 行超长内容 (>150字符)，可能是内嵌配置/Schema，建议剥离")

    # ── 中文专项检查 (仅在 zh/mixed 时运行) ──────────────────
    if lang in ('zh', 'mixed'):
        # (1) 中文常识灌输检测: 大于500个中文字符的连续段落且不含代码块
        body_no_code = re.sub(r'```.*?```', '', body, flags=re.DOTALL)
        body_no_code = re.sub(r'`[^`]+`', '', body_no_code)
        # 按空行分割段落
        paragraphs = re.split(r'\n\s*\n', body_no_code)
        for para in paragraphs:
            cn_chars = len(re.findall(r'[\u4e00-\u9fff]', para))
            if cn_chars > 500:
                # 取中文内容的前30个字符作为摘要
                cn_preview = ''.join(re.findall(r'[\u4e00-\u9fff]', para))[:30]
                r.warn(f"中文常识灌输: 发现 {cn_chars} 个中文字符的连续段落 (不含代码块)，"
                       f"建议精简或删除基础概念说明 (摘要: 「{cn_preview}...」)")
                break  # 一条警告即可

        # (2) 教程式写作检测: '首先', '然后', '最后' 等流程词
        tutorial_markers = ['首先', '然后', '最后', '第一步', '第二步', '接下来', '首先，']
        found_markers = [m for m in tutorial_markers if m in body]
        if len(found_markers) >= 3:
            r.warn(f"教程式写作: 检测到流程词 {found_markers} — 正文呈现教程结构，建议改用触发式描述")

        # (3) 分步教程检测: 步骤一/步骤二/第一步/第二步
        step_pattern = re.search(r'(步骤[一二三四五六七八九十]|第[一二三四五六七八九十]步)', body)
        if step_pattern:
            r.warn(f"分步教程: 检测到「{step_pattern.group(1)}」类分步描述 — Skill 应避免步骤式教学")

    return r


def check_railroading(skill_md: Path, lang: str = 'mixed') -> CheckResult:
    """反模式2: 轨道化常识 — 检测是否在教模型基础命令/语法"""
    r = CheckResult("反模式检测: 轨道化常识")
    content = read_file_safe(skill_md).lower()

    # ── 英文轨道化模式 ──
    en_signals = [
        (r'(?i)git (add|commit|push|pull|clone|checkout)', "教导基础 Git 命令"),
        (r'(?i)cd\s+', "教导 cd 命令"),
        (r'(?i)ls\s+(-la|-l|-a)', "教导 ls 命令"),
        (r'(?i)chmod\s+\d{3}', "教导 chmod 命令"),
        (r'(?i)pip (install|uninstall)', "教导 pip 命令"),
        (r'(?i)npm (install|run build|run dev)', "教导 npm 命令"),
        (r'(?i)mkdir\s+-p', "教导 mkdir 命令"),
        (r'(?i)rm\s+-rf', "教导 rm 命令"),
        (r'(?m)^\s*(def |function |class |import )\w', "教导基础编程语法 (def/function/class/import)"),
    ]

    # ── 中文轨道化模式 ──
    zh_signals = [
        (r'git clone|git commit|git push|git pull', "教导 Git 基本操作 (中文上下文)"),
        (r'pip install', "教导 pip 安装依赖"),
        (r'执行以下命令', "教导执行命令行操作"),
        (r'输入命令', "教导输入命令"),
        (r'创建目录|创建文件|创建文件夹', "教导创建目录/文件"),
        (r'删除文件|删除目录', "教导删除文件/目录操作"),
        (r'更改权限|chmod', "教导更改权限"),
        (r'运行脚本|python3', "教导运行脚本"),
        (r'定义函数|定义方法', "教导定义函数/方法"),
        (r'创建一个类|定义类', "教导创建类"),
        (r'导入模块|导入库', "教导导入模块/库"),
        (r'打印输出|print\s*\(', "教导打印输出"),
        (r'for\s+\w+\s+in\b|for\s*循环|遍历(列表|数组|字典|字符串|集合|文件|目录|数据|元素)', "教导遍历/循环操作"),
        (r'安装依赖|安装包', "教导安装依赖/包"),
        (r'打开终端|打开命令行', "教导打开终端/命令行"),
    ]

    # 根据语言选择要检查的模式
    chinese_note = " (中文上下文)"
    for pat, desc in en_signals:
        if re.search(pat, content):
            r.warn(f"检测到 '{desc}' — 模型预训练已掌握，建议删除")

    if lang in ('zh', 'mixed'):
        for pat, desc in zh_signals:
            if re.search(pat, content):
                r.warn(f"检测到 '{desc}' — 模型预训练已掌握，建议删除")

    if r.status == OK:
        r.ok("未检测到轨道化常识 (好)")

    return r


def check_hardcoded_assets(skill_dir: Path, lang: str = 'mixed') -> CheckResult:
    """反模式5: 检查是否有硬编码的高频变动资产"""
    r = CheckResult("反模式检测: 硬编码敏感资产")

    # 仅检查 SKILL.md
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return r.fail("SKILL.md 不存在")

    content = read_file_safe(skill_md)

    # 双语通用模式 (无论中英文都检查)
    universal_patterns = [
        (r'(?i)api[-_]?version\s*[=:]\s*["\']?v?\d+\.\d+\.\d+', "硬编码 API 版本号"),
        (r'(?i)(openai|claude|gemini|gpt-4|gpt-3)\s*[-_]\s*api\s*-?\s*key', "API Key 模式"),
        (r'(?i)https?://api\.[a-z]+\.(com|cn)/v\d+', "硬编码 API 端点 URL"),
        (r'(?i)mcp[-_]?server\s+[-:]\s+[a-z]', "MCP 节点工具"),
        (r'''["\'][A-Z_]+_KEY["\']''', "环境变量占位符 KEY"),
        (r'''["\'][A-Z_]+_URL["\']''', "环境变量占位符 URL"),
        (r'''["\'][A-Z_]+_ENDPOINT["\']''', "环境变量占位符 ENDPOINT"),
        (r'''["\'][A-Z_]+_TOKEN["\']''', "环境变量占位符 TOKEN"),
    ]

    # 中文特有模式
    zh_patterns = [
        (r'(?i)(API版本|接口版本)\s*[=:]\s*["\']?v?\d+\.\d+', "硬编码 API 版本号 (中文)"),
        (r'(?i)(密钥|api密钥|access_key)\s*[=:]\s*["\']?\S+', "硬编码密钥 (中文)"),
        (r'(?i)(接口地址|api地址)\s*[=:]\s*["\']?https?://', "硬编码 API 地址 (中文)"),
        (r'(?i)(MCP服务|工具名)\s*[=:]\s*["\']?\S+', "MCP 服务/工具名 (中文)"),
    ]

    for pat, desc in universal_patterns:
        if re.search(pat, content):
            r.warn(f"检测到 {desc} — 高频变动，建议外部化到 config.json")

    if lang in ('zh', 'mixed'):
        for pat, desc in zh_patterns:
            if re.search(pat, content):
                r.warn(f"检测到 {desc} — 高频变动，建议外部化到 config.json")

    if r.status == OK:
        r.ok("未检测到硬编码敏感资产 (好)")

    return r


def check_eval_set(skill_dir: Path) -> CheckResult:
    """检查是否有评估集或负样本"""
    r = CheckResult("评估集 & 负样本检查")
    skill_md = skill_dir / "SKILL.md"
    found = False

    # 检查是否有 SPECIAL_CASES.md
    special_cases = skill_dir / "SPECIAL_CASES.md"
    if special_cases.exists():
        r.ok("存在 SPECIAL_CASES.md (好)")
        found = True

    # 检查是否有评估目录
    eval_dir = skill_dir / "evals"
    if eval_dir.exists():
        r.ok("存在 evals/ 目录 (好)")
        found = True
        # 检查是否同时有正反例
        pos = eval_dir / "positive.json"
        neg = eval_dir / "negative.json"
        if pos.exists() and neg.exists():
            r.ok("evals/ 同时包含 positive.json 和 negative.json (好)")
        elif pos.exists():
            r.warn("evals/ 只有 positive.json, 缺少 negative.json (反例更重要)")
        elif neg.exists():
            r.warn("evals/ 只有 negative.json, 缺少 positive.json")
    else:
        r.warn("没有 evals/ 目录 — 建议添加正反例 JSON 文件")

    # 检查 SKILL.md 中是否包含正/负样本
    # (只认明确的评估用例标记; 正文里一般性的「禁止/forbidden」业务规则不算负样本)
    if skill_md.exists():
        content = read_file_safe(skill_md)
        if re.search(r'(?i)(正样本|负样本|正反例|positive sample|negative sample)', content):
            r.ok("SKILL.md 中内嵌了评估用例")
            found = True

    if not found:
        r.warn("未找到显式的评估集或负样本 (建议在 SKILL.md 或 evals/ 中添加)")

    return r


def check_gotchas_flywheel(skill_dir: Path) -> CheckResult:
    """检查 Gotchas 维护飞轮机制 (gotchas/ 目录或 gotcha 条目)"""
    r = CheckResult("Gotchas 飞轮维护检查")
    skill_md = skill_dir / "SKILL.md"

    # 检查是否有 gotchas/ 目录
    gotchas_dir = skill_dir / "gotchas"
    if gotchas_dir.exists():
        gotcha_files = list(gotchas_dir.glob("*.md"))
        r.ok(f"存在 gotchas/ 目录 ({len(gotcha_files)} 个文件)")

    # 检查 SKILL.md 中是否包含 gotcha 相关标记
    if skill_md.exists():
        content = read_file_safe(skill_md)
        gotcha_patterns = [
            (r'(?i)## Gotchas?\s*\n', "存在 '## Gotchas' 章节"),
            (r'(?i)(陷阱|坑|注意|不要|避免|禁止)', "包含 gotcha 关键词 (陷阱/坑/注意/不要/避免/禁止)"),
            (r'(?i)#+ 已知失败|#+ 常见错误|#+ 边界情况', "存在已知失败/常见错误/边界情况章节"),
        ]
        found_any = False
        for pat, desc in gotcha_patterns:
            if re.search(pat, content):
                r.ok(f"{desc}")
                found_any = True
                break

        if not found_any and not gotchas_dir.exists():
            r.warn("未发现 Gotcha 机制 — Agent 失败时应在尾部追加 gotcha 条目")

    if r.status == OK and not gotchas_dir.exists() and skill_md.exists():
        pass  # 已在上面 warn 过

    if r.status == OK:
        r.ok("Gotcha 机制正常")

    return r


def check_flat_layout(skill_dir: Path) -> CheckResult:
    """反模式1: 单文件依赖 — 检查是否所有内容都堆在一个 md 文件里"""
    r = CheckResult("反模式检测: 单文件依赖")

    md_files = list(skill_dir.glob("*.md"))
    all_items = [f for f in skill_dir.iterdir() if f.name not in (".", "..") and not f.name.startswith(".")]

    # 如果只有 SKILL.md 一个文件，且没有子目录
    if len(md_files) == 1 and not any(f.is_dir() for f in all_items):
        return r.warn("整个 Skill 只有一个 SKILL.md 文件 — 简单技能可接受，复杂场景需拆分")

    return r.ok(f"目录结构完整 ({len(md_files)} 个 .md 文件, {len([f for f in all_items if f.is_dir()])} 个子目录)")


def check_file_size_redlines(skill_dir: Path) -> CheckResult:
    """检查文件尺寸红线"""
    r = CheckResult("文件尺寸安全红线")
    over_sized = []

    for f in skill_dir.rglob("*"):
        if f.is_file():
            size = f.stat().st_size
            if size > 100_000:  # 100KB
                over_sized.append((f.relative_to(skill_dir), size))

    if over_sized:
        for name, size in over_sized:
            r.warn(f"{name} 达 {size/1024:.0f} KB — 超大文件可能导致加载异常")
    else:
        r.ok("所有文件尺寸在安全范围内")

    return r


def check_chinese_common_knowledge(skill_md: Path, lang: str = 'mixed') -> CheckResult:
    """反模式: 中文常识灌输 — 检测长篇中文解释性文字 (模型预训练已掌握的内容)"""
    r = CheckResult("反模式检测: 中文常识灌输")

    if lang == 'en':
        r.ok("跳过 (英文技能 — 无需检查中文常识灌输)")
        return r

    content = read_file_safe(skill_md)
    body = content
    body = re.sub(r'^---\s*\n.*?\n---\s*\n', '', body, count=1, flags=re.DOTALL)
    if not body.strip():
        return r.warn("无正文内容可检查")

    # (a) 检测含 >200 中文字符且解释基础概念的段落
    basic_concept_patterns = [
        # 中文常见基础概念解释
        (r'(?i)(API|应用程序接口).{0,30}(是指|是|指的是|是一种|用于|用来|定义)',
         "解释 API 基本概念"),
        (r'(?i)(HTTP|HTTPS).{0,30}(是指|是|指的是|是一种|协议|用于)',
         "解释 HTTP/HTTPS 基本概念"),
        (r'(?i)(数据库|database).{0,30}(是指|是|指的是|用于存储|用来存储|保存数据)',
         "解释数据库基本概念"),
        (r'(?i)(操作系统|OS|operating system).{0,30}(是指|是|指的是|管理|控制)',
         "解释操作系统基本概念"),
        (r'(?i)(变量|variable).{0,30}(是指|是|指的是|存储数据|存放|保存)',
         "解释变量基本概念"),
        (r'(?i)(函数|function).{0,30}(是指|是|指的是|一段代码|一组|封装)',
         "解释函数基本概念"),
        (r'(?i)(类|class).{0,30}(是指|是|指的是|面向对象|模板|蓝图)',
         "解释类/面向对象基本概念"),
        (r'(?i)(JSON|XML|YAML).{0,30}(是指|是|指的是|格式|数据交换|配置文件)',
         "解释数据格式基本概念"),
        (r'(?i)(URL|URI).{0,30}(是指|是|指的是|地址|统一资源|定位)',
         "解释 URL/URI 基本概念"),
        (r'(?i)(TCP|IP|UDP).{0,30}(是指|是|指的是|协议|传输|通信)',
         "解释网络协议基本概念"),
        (r'(?i)(什么是|什么是 |何为|何为 ).{2,30}(？|\?|？\s|$|\n)',
         "基础概念自问自答 (什么是XXX)"),
    ]

    paragraphs = re.split(r'\n\s*\n', body)
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', para))
        if chinese_chars <= 200:
            continue

        for pat, desc in basic_concept_patterns:
            if re.search(pat, para, re.DOTALL):
                preview = para[:80].replace('\n', ' ').strip()
                r.warn(f"长段落 ({chinese_chars} 中文字符) 含基础概念解释: {desc} — 开头: \"{preview}...\"")
                break  # 每个段落只报一次

    # (b) 检测教学/解释性语气标记
    teaching_tone_patterns = [
        (r'所谓.{2,30}是指', "使用 '所谓...是指' 教学句式"),
        (r'简单来说[,，].{5,}', "使用 '简单来说' 教学句式"),
        (r'顾名思义[,，].{5,}', "使用 '顾名思义' 教学句式"),
        (r'(需要|要|请).{0,20}(注意|记住|理解|明白|知道)',
         "使用 '需要/请...注意/记住' 教学语气"),
        (r'指的是.{10,}', "使用 '指的是' 解释句式"),
        (r'我们来(看|解释|介绍|学习|了解)',
         "使用 '我们来...' 教学引导句式"),
        (r'首先[,，].{0,30}(需要|要|我们)',
         "使用 '首先...需要/我们' 教程结构"),
    ]

    for pat, desc in teaching_tone_patterns:
        for m in re.finditer(pat, body):
            start = max(0, m.start() - 20)
            preview = body[start:m.end() + 20].replace('\n', ' ').strip()
            r.warn(f"检测到教学语气: {desc} — 上下文: \"{preview}\"")

    if r.status == OK:
        r.ok("未检测到中文常识灌输 (好)")

    return r


def check_backslash_paths(skill_md: Path) -> CheckResult:
    """反模式: 反斜杠路径 (BP smell) — Agent 按文件系统导航, 路径必须正斜杠"""
    r = CheckResult("反模式检测: 反斜杠路径")

    content = read_file_safe(skill_md)
    if not content.strip():
        return r.ok("跳过 (SKILL.md 为空)")

    # 去掉代码块中的 Windows 风格说明性文字后, 仍找 "目录/文件" 样式的反斜杠路径
    body = re.sub(r'^---\s*\n.*?\n---\s*\n', '', content, count=1, flags=re.DOTALL)
    hits = []
    for i, line in enumerate(body.splitlines(), 1):
        # 剔除 Windows 盘符路径 (C:\ 形式 — 通常是文档示例) 后再匹配,
        # 避免同一行里真正的反斜杠路径被整行误排除
        line_clean = re.sub(r'[A-Za-z]:\\', '', line)
        # 排除 Markdown 转义 (\\) 与 JSON 字符串转义场景, 只匹配目录段/文件名样式的反斜杠
        if re.search(r'[\w.-]+\\[\w.-]+(?:\\|/|\s|[`)\],;。]|$)', line_clean):
            hits.append((i, line.strip()[:80]))
    if hits:
        for ln, preview in hits[:3]:
            r.warn(f"第 {ln} 行疑似反斜杠路径 — Agent 按文件系统导航, 必须用正斜杠: \"{preview}\"")
        if len(hits) > 3:
            r.warn(f"…共 {len(hits)} 处")
        return r

    return r.ok("未检测到反斜杠路径 (好)")


def check_verification_loop(skill_md: Path, lang: str = 'mixed') -> CheckResult:
    """反模式: 无验证闭环 (NVS/EWP smell) — 多步工作流应含验证环节"""
    r = CheckResult("反模式检测: 无验证闭环")

    content = read_file_safe(skill_md)
    body = re.sub(r'^---\s*\n.*?\n---\s*\n', '', content, count=1, flags=re.DOTALL)
    if not body.strip():
        return r.ok("跳过 (无正文)")

    # 检测是否呈现多步工作流
    en_step_signals = re.findall(r'(?i)(\bstep\s*\d+|\bphase\s*\d+|then\s+\w+\s+\w+|after\s+that|#\s*\d+[.、])', body)
    zh_step_signals = re.findall(r'(步骤[一二三四五六七八九十]|第[一二三四五六七八九十]步|然后|最后)', body)
    workflow_like = len(en_step_signals) + len(zh_step_signals) >= 3

    if not workflow_like:
        return r.ok("未呈现多步工作流 (跳过)")

    # 检测是否有验证/确认环节
    verify_patterns = [
        r'(?i)(verify|validate|validation|check that|assert|confirm)',
        r'(验证|校验|检查是否|确认.{0,10}(通过|成功|正确)|测试是否)',
        r'(?i)(test|run the test|pass the test|lint|build)',
    ]
    if any(re.search(p, body) for p in verify_patterns):
        return r.ok("多步工作流含验证环节 (好)")

    r.warn("检测到多步工作流但无验证环节 (NVS/EWP smell) — 产出后应跑什么检查、什么算通过，需写明")
    return r


def check_rationalization_loophole(skill_md: Path, lang: str = 'mixed') -> CheckResult:
    """反模式: 合理化漏洞 (RL smell, 出现于 94% 真实 skill) —
    含强纪律规则 (ALWAYS/NEVER/MUST/必须/禁止) 时应配防跳过护栏:
    例外枚举/红旗清单/对照表/无例外声明"""
    r = CheckResult("反模式检测: 合理化漏洞 (RL)")

    content = read_file_safe(skill_md)
    body = re.sub(r'^---\s*\n.*?\n---\s*\n', '', content, count=1, flags=re.DOTALL)
    if not body.strip():
        return r.ok("跳过 (无正文)")

    # 是否声明了强纪律规则
    discipline_patterns = [
        r'(?i)\bALWAYS\b',
        r'(?i)\bNEVER\b',
        r'(?i)\bMUST\b',
        r'(?i)\bMANDATORY\b',
        r'必须|禁止|绝不|不得|无例外',
    ]
    discipline_hits = sum(len(re.findall(p, body)) for p in discipline_patterns)
    if discipline_hits < 2:
        return r.ok("未声明强纪律规则 (跳过)")

    # 是否配有防合理化护栏
    guardrail_patterns = [
        (r'(?i)(no exceptions|nothing else|其余一律|无例外)', "显式'无例外'声明"),
        (r'(?i)(when (not )?to use|when not to|例外|除外|逃生舱|escape hatch)', "例外/逃生舱枚举"),
        (r'(?i)(red flags?|红旗|stop and (restart|start over)|停下重来)', "红旗清单"),
        (r'(?i)(rationaliz|借口|借口对照|合理化)', "合理化对照表"),
        (r'(?i)(spirit (and|vs|or) letter|字面.{0,6}(精神|就是)|违反.{0,6}(字面|文字))', "'精神与字面'原则"),
    ]
    found = [desc for pat, desc in guardrail_patterns if re.search(pat, body)]
    if found:
        r.ok(f"强纪律规则配有护栏: {', '.join(found)}")
        return r

    r.warn(f"声明了 {discipline_hits} 处强纪律规则但无防跳过护栏 (RL smell, 出现于 94% 真实 skill) — "
           f"建议补充: 显式例外枚举 + 红旗清单 + '无例外'声明")
    return r


def check_reference_toc(skill_dir: Path) -> CheckResult:
    """渐进披露: references/ 长文件 (>100 行) 顶部应有目录 TOC —
    模型可能只部分读取, TOC 让它看到全貌"""
    r = CheckResult("渐进披露: references/ 长文件 TOC")

    ref_dir = skill_dir / "references"
    if not ref_dir.is_dir():
        return r.ok("无 references/ 目录 (跳过)")

    md_files = sorted(ref_dir.glob("*.md"))
    if not md_files:
        return r.ok("references/ 无 Markdown 文件 (跳过)")

    missing = []
    for f in md_files:
        lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        if len(lines) < 100:
            continue
        # 检查前 30 行内是否有 TOC 特征: >=3 个指向本文件锚点的 Markdown 链接
        head = "\n".join(lines[:30])
        anchors = re.findall(r'\]\(#[^)]+\)', head)
        if len(anchors) < 3:
            missing.append(f"{f.name} ({len(lines)} 行)")

    if missing:
        for name in missing:
            r.warn(f"{name} 超过 100 行但顶部无目录 (TOC) — 模型可能只部分读取, 应在文件顶部列出章节")
        return r

    return r.ok("references/ 长文件均含 TOC (好)")


# ── 主流程 ────────────────────────────────────────────────

def validate_skill(skill_dir: Path, lang: str = 'auto') -> list:
    """对一个 Skill 目录执行全部检查"""
    results = []

    dirname = skill_dir.name
    results.append(check_naming(dirname))
    results.append(check_directory_structure(skill_dir))

    skill_md = skill_dir / "SKILL.md"
    if skill_md.exists():
        content = read_file_safe(skill_md)
        # 自动检测语言
        if lang == 'auto':
            detected = detect_language(content)
            lang = detected

        results.append(check_frontmatter(skill_md, lang))
        results.append(check_body_quality(skill_md, lang))
        results.append(check_railroading(skill_md, lang))
        results.append(check_hardcoded_assets(skill_dir, lang))
        results.append(check_eval_set(skill_dir))
        results.append(check_gotchas_flywheel(skill_dir))
        results.append(check_flat_layout(skill_dir))
        results.append(check_file_size_redlines(skill_dir))
        results.append(check_chinese_common_knowledge(skill_md, lang))
        results.append(check_backslash_paths(skill_md))
        results.append(check_verification_loop(skill_md, lang))
        results.append(check_rationalization_loophole(skill_md, lang))
        results.append(check_reference_toc(skill_dir))

    return results


def print_summary(all_results: dict):
    """打印汇总表"""
    print(f"\n{'='*60}")
    print(f"{BOLD}检查汇总{RESET}")
    print(f"{'='*60}")

    total_ok = 0
    total_warn = 0
    total_fail = 0

    for dirname, results in all_results.items():
        n_ok = sum(1 for r in results if r.status == OK)
        n_warn = sum(1 for r in results if r.status == WARN)
        n_fail = sum(1 for r in results if r.status == FAIL)

        score_emoji = "✅" if n_fail == 0 else "❌"
        print(f"\n{BOLD}{dirname}{RESET}")
        print(f"  {score_emoji} 通过={n_ok}  警告={n_warn}  失败={n_fail}")

        total_ok += n_ok
        total_warn += n_warn
        total_fail += n_fail

    print(f"\n{'─'*60}")
    print(f"总计: 通过={total_ok}  警告={total_warn}  失败={total_fail}")
    if total_fail == 0:
        print(f"{GREEN}所有检查通过 ✅{RESET}")
    else:
        print(f"{RED}存在 {total_fail} 项未通过，建议修复 ❌{RESET}")


def main():
    parser = argparse.ArgumentParser(description="Skill Validator — Agent Skill 目录合规检查工具")
    parser.add_argument("path", nargs="?", default=".", help="Skill 目录路径 (或包含多个 skill 的父目录)")
    parser.add_argument("--lang", default="auto", choices=["auto", "en", "zh", "mixed"],
                        help="语言模式: auto (自动检测), en (仅英文规则), zh (仅中文规则), mixed (双语规则)")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式 (供 CI 使用)")
    parser.add_argument("--models", nargs="*", default=None,
                        choices=["gpt", "claude", "sonnet", "opus", "all"],
                        help="指定目标编排模型族进行兼容性标注 (用于报告头部)")
    args = parser.parse_args()

    target = Path(args.path).resolve()

    if not target.exists():
        print(f"{FAIL} 路径不存在: {target}")
        sys.exit(1)

    # 收集待检查的 skill 目录
    skills_to_check = []

    # 如果目标包含 SKILL.md，视为单个 skill
    if (target / "SKILL.md").exists():
        skills_to_check.append(target)
    else:
        # 否则，尝试把所有直接子目录视为 skill
        for item in sorted(target.iterdir()):
            if item.is_dir() and not item.name.startswith("."):
                skills_to_check.append(item)

    if not skills_to_check:
        print(f"{FAIL} 未找到包含 SKILL.md 的 Skill 目录")
        sys.exit(1)

    # 输出 --models 信息 (如果有)
    if args.models:
        models_str = ", ".join(args.models)
        print(f"\n{BOLD}目标模型族:{RESET} {models_str}")

    all_results = {}

    for skill_dir in skills_to_check:
        dirname = skill_dir.name
        print(f"\n{'='*60}")
        print(f"{BOLD}检查: {dirname}{RESET}")
        print(f"{'='*60}")

        results = validate_skill(skill_dir, lang=args.lang)
        all_results[dirname] = results

        for r in results:
            print(r)

    print_summary(all_results)

    # JSON 输出模式
    if args.json:
        import json
        output = {}
        for dirname, results in all_results.items():
            output[dirname] = [
                {"check": r.name, "status": str(r.status), "messages": [m[1] for m in r.messages]}
                for r in results
            ]
        print(f"\n{json.dumps(output, ensure_ascii=False, indent=2)}")

    # 退出码
    any_fail = any(
        any(r.status == FAIL for r in results)
        for results in all_results.values()
    )
    sys.exit(1 if any_fail else 0)


if __name__ == "__main__":
    main()
