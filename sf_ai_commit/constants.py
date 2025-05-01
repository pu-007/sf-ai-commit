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

# LLM相关
DEFAULT_LLM_HOST_URL = "http://127.0.0.1:11434/v1/chat/completions"
DEFAULT_LLM_MODEL = "qwen2.5-coder"
DEFAULT_LLM_TIMEOUT = 30
DEFAULT_LLM_TEMPERATURE = 0.7
DEFAULT_EDITOR = "nvim"

# 提示词模板
DEFAULT_PROMPT_TEMPLATE = """
你是一个Git提交消息生成助手。
请根据以下Git差异生成符合Conventional Commits规范的提交消息。
格式应为: <type>[optional scope]: <description>

类型(type)应该是以下之一:
- feat: 新功能
- fix: 修复bug
- docs: 文档变更
- style: 代码风格变更(不影响代码功能)
- refactor: 代码重构
- perf: 性能优化
- test: 测试相关
- build: 构建系统或外部依赖变更
- ci: CI配置文件和脚本变更
- chore: 其他变更

保持描述简洁、清晰，使用现在时态和祈使句。
不要以句号结尾。

差异内容：
{diff_summary}
"""

DETAILED_PROMPT_EXTENSION = """
在上面基础上增加详细的消息体，包含以下内容:
1. 变更的原因或目的
2. 变更的主要内容
3. 可能的影响或注意事项

消息体应与主题行之间空一行，且每行不超过72个字符。
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