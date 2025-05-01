"""
常量定义模块 - 存储全局常量和默认值
"""

import os
from pathlib import Path

# 版本信息
VERSION = "0.1.0"

# 默认配置路径
DEFAULT_CONFIG_DIR = os.path.expanduser("~/.config/sf-ai-commit")
DEFAULT_CONFIG_PATH = os.path.join(DEFAULT_CONFIG_DIR, "config.yaml")

# Git相关
GIT_DIFF_ENCODING = "utf-8"
GIT_DEFAULT_REPO_PATH = "."
GIT_DEFAULT_DIFF_MAX_LINES = 20  # 默认显示差异内容的最大行数，0表示不限制

# LLM相关
DEFAULT_LLM_HOST_URL = "http://127.0.0.1:11434/v1/chat/completions"
DEFAULT_LLM_MODEL = "qwen2.5-coder"
DEFAULT_LLM_TIMEOUT = 30
DEFAULT_LLM_TEMPERATURE = 0.7
DEFAULT_EDITOR = "nvim"

# 提交消息相关
MAX_LINE_LENGTH = 72

# 提交类型与关键词模式映射
COMMIT_TYPE_PATTERNS = {
    "feat": [
        r"\badd\s+new\b",
        r"\bimplemented?\b",
        r"\bnew\s+feature\b",
        r"\b新增\b",
        r"\b实现\b",
        r"\b添加功能\b"
    ],
    "fix": [
        r"\bfix(ed|ing)?\b",
        r"\bbug\b",
        r"\bissue\b",
        r"\berror\b",
        r"\b修复\b",
        r"\b解决问题\b"
    ],
    "docs": [
        r"\bdocument(s|ation)?\b",
        r"\bdoc[s]?\b",
        r"\bcomment[s]?\b",
        r"\b文档\b",
        r"\b注释\b"
    ],
    "style": [
        r"\bstyle\b",
        r"\bformat\b",
        r"\blint\b",
        r"\b样式\b",
        r"\b格式化\b"
    ],
    "refactor": [
        r"\brefactor\b",
        r"\brestructure\b",
        r"\bclean\b",
        r"\b重构\b",
        r"\b优化代码\b"
    ],
    "perf": [
        r"\bperformance\b",
        r"\boptimize\b",
        r"\bfast(er)?\b",
        r"\b性能\b",
        r"\b优化性能\b"
    ],
    "test": [
        r"\btest[s]?\b",
        r"\bspec[s]?\b",
        r"\b测试\b"
    ]
}

# 提交消息体模板
COMMIT_BODY_TEMPLATES = {
    "feat": """功能描述：
- 实现的功能点
- 新增的主要文件
- 核心实现逻辑

影响范围：
- 涉及的模块
- 依赖关系
- 配置变更""",

    "fix": """问题描述：
- 修复的问题
- 产生原因
- 解决方案

影响范围：
- 修改的文件
- 相关依赖
- 注意事项""",

    "refactor": """重构说明：
- 重构原因
- 主要变更
- 改进效果

影响范围：
- 重构的模块
- 接口变化
- 兼容性说明""",

    "docs": """文档更新：
- 更新内容
- 补充说明
- 使用示例""",

    "style": """格式优化：
- 改进内容
- 代码规范
- 自动化工具""",

    "perf": """性能优化：
- 优化指标
- 改进方案
- 性能提升"""
}

# 提示词模板
DEFAULT_PROMPT_TEMPLATE = """
你是一个专业的Git提交消息生成助手。我需要你根据以下Git变更信息生成规范的提交消息。

## 分析任务：
1. 首先分析变更的总体性质，确定最主要的变更类型
2. 识别变更涉及的主要模块或功能区域作为可选的scope
3. 提取变更的核心目的，作为描述部分

请生成符合Conventional Commits规范的提交消息，格式为：
<type>[optional scope]: <description>

type必须是以下之一：
- feat: 新功能（例如：添加新特性、实现新功能）
- fix: 修复问题（例如：修复bug、解决异常）
- docs: 文档更新（例如：更新说明文档、添加注释）
- style: 代码格式（例如：格式化代码、修复lint问题）
- refactor: 代码重构（例如：重构设计、优化结构）
- perf: 性能优化（例如：提升性能、优化算法）
- test: 测试相关（例如：添加测试、完善测试）
- build: 构建相关（例如：更新依赖、修改配置）
- ci: CI/CD相关（例如：修改工作流、更新配置）
- chore: 其他修改（例如：常规维护、工具更新）

## 要求：
1. description使用动词开头，采用现在时态的祈使语气
2. 简明扼要地描述变更的主要内容
3. 不要以句号结尾
4. 根据变更内容推断合适的type和可选的scope
5. 只返回一行提交消息，不要包含额外的解释或注释

## 输出示例：
- feat(auth): add user authentication system
- fix(api): handle null response in getUser endpoint
- refactor(core): simplify data processing logic
- feat(api)!: breaking change in API response format

## 变更梗概：

(这部分总结了当前变更中添加/修改/删除了多少文件，主要涉及哪些模块，代码增减了多少行。)

{diff_summary}

## 重要变更：

(这部分列出了主要的变化文件，总结了它们的用途和变更类型（新增、修改、删除等）。)

{important_changes}

## 详细差异：

(这部分提供了具体文件的代码变更详情，包括变更的具体内容和意图。)

{diff_details}
"""

DETAILED_PROMPT_EXTENSION = """
除了提交消息的标题行外，请同时生成符合Conventional Commits规范的完整消息，包括：

1. 消息体：
   - 详细说明变更的目的、内容和实现方式
   - 按照段落组织，每段说明一个方面
   - 使用空行分隔不同段落
   - 每行长度不超过72个字符

2. 页脚（如果需要）：
   - 破坏性变更需要使用"BREAKING CHANGE:"前缀
   - 可以引用相关问题或任务（例如："Refs: #123"）
   - 可以添加其他元数据（例如："Reviewed-by: Z"）

完整格式示例：
```
fix: prevent racing of requests

Introduce a request id and a reference to latest request. Dismiss
incoming responses other than from latest request.

Remove timeouts which were used to mitigate the racing issue but are
obsolete now.

BREAKING CHANGE: The API now requires a request ID parameter.
Reviewed-by: Z
Refs: #123
```

格式要求：

1. 消息体与主题行之间空一行
2. 每行不超过72个字符
3. 使用列表形式展示详细信息
4. 破坏性变更以"BREAKING CHANGE:"开头
5. 简洁模式下：简短标题 + 分点列出的主要变更
6. 详细模式下：添加每个变更点的详细说明

请确保消息结构清晰，正文与标题行之间有一个空行，每部分表达充分但简洁。
"""

VERBOSE_PROMPT_TEMPLATE = """
====== 实际发送给LLM的提示词 ======

{full_prompt}

====== 提示词结束 ======
"""

# 用户交互相关
CONFIRM_OPTIONS = ["确认", "取消", "编辑", "重新生成"]
DEFAULT_MAX_MESSAGE_LENGTH = 100

# 错误码和消息
ERROR_CONFIG_NOT_FOUND = "配置文件不存在: {}"
ERROR_CONFIG_INVALID = "配置文件格式无效: {}"
ERROR_GIT_REPO_NOT_FOUND = "Git仓库未找到: {}"
ERROR_GIT_NO_STAGED_CHANGES = "没有暂存的变更，请先使用 'git add' 添加变更"
ERROR_LLM_CONNECTION = "连接LLM API失败: {}"
ERROR_LLM_RESPONSE = "LLM响应无效: {}"
ERROR_EDITOR_NOT_FOUND = "找不到编辑器: {}"
ERROR_EDITOR_FALLBACK = "找不到指定的编辑器: {}，已回退到系统默认编辑器"