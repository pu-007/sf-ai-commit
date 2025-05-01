"""
消息生成器模块 - 负责生成和格式化符合Conventional Commits的消息
"""

import re
import logging
from typing import Dict, Any, Tuple, Optional, List

from sf_ai_commit.constants import (
    COMMIT_TYPE_PATTERNS,
    COMMIT_BODY_TEMPLATES,
    MAX_LINE_LENGTH
)

class MessageGenerator:
    """生成符合Conventional Commits的消息"""
    
    # Conventional Commits类型列表
    VALID_TYPES = [
        "feat", "fix", "docs", "style", "refactor", 
        "perf", "test", "build", "ci", "chore"
    ]
    
    # Conventional Commits格式的正则表达式
    CONVENTIONAL_PATTERN = r"^([\w]+)(\([\w\-\.]+\))?!?: (.+)$"
    
    def __init__(self):
        """初始化消息生成器"""
        self.logger = logging.getLogger(__name__)
        
    def format_message(self, llm_response: str, diff_info: Dict[str, Any], detailed: bool = False) -> str:
        """
        格式化LLM响应为标准格式
        
        Args:
            llm_response: LLM生成的原始响应
            diff_info: Git差异分析信息
            detailed: 是否需要详细消息
            
        Returns:
            格式化后的提交消息，包含以下部分：
            - 符合 Conventional Commits 规范的主题行
            - 详细的变更说明（如果detailed=True）
            - 涉及的重要文件列表
            - 重大变更警告（如果有）
            - 相关问题或任务的引用（如果有）
        """
        # 移除前后空白
        message = llm_response.strip()
        
        # 如果消息为空，基于变更信息生成默认消息
        if not message:
            return self._generate_default_message(diff_info)
        
        # 解析并改进主题行
        first_line = self._extract_subject_line(message)
        commit_type, scope = self.parse_type_and_scope(first_line)
        
        # 验证并优化commit_type
        if commit_type not in self.VALID_TYPES:
            # 尝试使用AI和代码变更信息共同推断正确的类型
            commit_type = self._refine_commit_type(commit_type, diff_info, message)
            # 更新第一行
            first_line = self._update_commit_type(first_line, commit_type)
        
        # 对新文件添加特殊处理
        if self._is_new_file_only_commit(diff_info):
            commit_type = self._refine_type_for_new_file(diff_info, commit_type)
            first_line = self._update_commit_type(first_line, commit_type)
        
        # 如果没有作用域，尝试从变更信息中推断
        if not scope:
            scope = self._infer_scope_from_changes(diff_info)
            if scope:
                first_line = self._add_scope_to_message(first_line, scope)
        
        # 如果不需要详细信息，但需要基本的变更点，生成简洁版本
        if not detailed:
            # 提取关键变更点，生成简短的变更列表
            change_points = self._extract_key_changes(diff_info)
            if change_points:
                return first_line + "\n\n" + change_points
            return first_line
            
        # 生成详细的消息体
        message_body = self._generate_detailed_body(
            message,
            diff_info,
            commit_type
        )
        
        # 组合最终消息
        formatted_message = first_line
        if message_body:
            formatted_message += "\n\n" + message_body
            
        return formatted_message
    
    def parse_type_and_scope(self, message: str) -> Tuple[str, Optional[str]]:
        """
        解析消息中的类型和作用域
        
        Args:
            message: 提交消息
            
        Returns:
            (类型, 作用域) 元组，如果没有作用域则为None
        """
        match = re.match(self.CONVENTIONAL_PATTERN, message)
        
        if match:
            type_value = match.group(1)
            scope_value = match.group(2)
            
            # 移除作用域的括号
            if scope_value:
                scope_value = scope_value[1:-1]  # 移除 '(' 和 ')'
                
            return (type_value, scope_value)
            
        # 如果不匹配，返回默认值
        return ("chore", None)
    
    def ensure_conventional_format(self, message: str) -> str:
        """
        确保消息符合Conventional Commits格式
        
        如果消息已经符合格式，则直接返回
        否则尝试识别消息中的类型并重新格式化
        
        Args:
            message: 原始消息
            
        Returns:
            格式化后的消息
        """
        # 检查是否已经符合格式
        if self._is_conventional_format(message):
            return message
            
        # 尝试从消息中提取类型
        lower_message = message.lower()
        detected_type = None
        
        # 检查消息是否以有效类型开头
        for valid_type in self.VALID_TYPES:
            # 检查是否以类型+冒号开头
            if lower_message.startswith(f"{valid_type}:"):
                return f"{valid_type}: {message[len(valid_type)+1:].strip()}"
                
            # 检查消息是否提到了有效类型
            if valid_type in lower_message[:20]:  # 只检查前20个字符
                detected_type = valid_type
                break
        
        # 根据消息内容推断类型
        if not detected_type:
            detected_type = self._infer_type_from_content(message)
            
        # 格式化消息
        return f"{detected_type}: {message}"
    
    def _is_conventional_format(self, message: str) -> bool:
        """
        检查消息是否符合Conventional Commits格式
        
        Args:
            message: 提交消息
            
        Returns:
            如果符合格式则为True，否则为False
        """
        return bool(re.match(self.CONVENTIONAL_PATTERN, message))
    
    def _extract_subject_line(self, message: str) -> str:
        """
        从LLM响应中提取并规范化主题行
        
        Args:
            message: 原始消息
            
        Returns:
            规范化的主题行
        """
        # 获取第一个非空行
        lines = [line.strip() for line in message.split('\n') if line.strip()]
        if not lines:
            return "chore: update files"
            
        first_line = lines[0]
        
        # 确保符合格式要求
        if not self._is_conventional_format(first_line):
            first_line = self.ensure_conventional_format(first_line)
            
        # 确保长度符合规范
        if len(first_line) > 72:
            # 尝试在标点符号处截断
            cutoff_points = [i for i, c in enumerate(first_line) if c in ',.;，。：；']
            if cutoff_points and max(cutoff_points) > 20:  # 确保不会截得太短
                first_line = first_line[:max(p for p in cutoff_points if p <= 72)] + '...'
            else:
                first_line = first_line[:69] + '...'
                
        return first_line
        
    def _add_scope_to_message(self, message: str, scope: str) -> str:
        """
        向提交消息添加作用域
        
        Args:
            message: 原始消息
            scope: 要添加的作用域
            
        Returns:
            添加作用域后的消息
        """
        type_match = re.match(r'^(\w+)(\([\w\-\.]+\))?!?: (.+)$', message)
        if not type_match:
            return message
            
        commit_type = type_match.group(1)
        description = type_match.group(3)
        
        return f"{commit_type}({scope}): {description}"
        
    def _infer_scope_from_changes(self, diff_info: Dict[str, Any]) -> Optional[str]:
        """
        从变更信息中推断合适的作用域
        
        策略：
        1. 如果变更集中在某个目录，使用该目录名
        2. 如果是特定类型的文件（如配置、文档），使用对应的类型名
        3. 如果涉及特定功能模块，使用模块名
        
        Args:
            diff_info: 变更信息字典
            
        Returns:
            推断出的作用域，如果无法推断则返回None
        """
        if not diff_info.get("files"):
            return None
            
        # 获取所有变更文件
        files = diff_info["files"]
        
        # 检查是否都在同一个目录下
        directories = set()
        for file_stat in files:
            path = file_stat["path"]
            directory = path.split("/")[0] if "/" in path else path
            directories.add(directory)
            
        # 如果都在同一个目录下
        if len(directories) == 1:
            return next(iter(directories))
            
        # 检查文件类型分布
        type_counts = {}
        for file_stat in files:
            file_type = file_stat.get("file_type", "other")
            type_counts[file_type] = type_counts.get(file_type, 0) + 1
            
        # 如果主要是某种类型的文件
        if type_counts:
            main_type = max(type_counts.items(), key=lambda x: x[1])[0]
            if type_counts[main_type] >= len(files) * 0.7:  # 如果超过70%的文件属于同一类型
                return main_type
                
        # 如果有重要变更
        important_changes = diff_info.get("important_changes", [])
        if important_changes:
            # 使用最重要的变更文件所在的目录
            main_change = important_changes[0]
            path = main_change.get("path", "")
            if not path:
                return None
            return path.split("/")[0] if "/" in path else "core"
            
        return None
        
    def _generate_default_message(self, diff_info: Dict[str, Any]) -> str:
        """
        根据变更信息生成默认的提交消息
        
        Args:
            diff_info: 变更信息字典
            
        Returns:
            生成的默认消息
        """
        # 检查是否为首次提交
        is_first_commit = False
        repo_info = diff_info.get("repo_info", {})
        if repo_info.get("is_empty", False):
            is_first_commit = True
            self.logger.debug("检测到首次提交")
            
        if is_first_commit:
            return "chore: initial commit"
        
        # 检查是否只有一个文件
        total_files = diff_info.get("total_files", 0)
        if total_files == 1 and diff_info.get("files"):
            file_stats = diff_info["files"][0]
            path = file_stats["path"]
            extension = file_stats.get("extension", "")
            
            # 对于特定文件类型生成特定消息
            if path.lower() == ".gitignore":
                return "chore: add gitignore file"
            elif path.lower() == "license" or path.lower().startswith("license."):
                return "docs: add license file"
            elif path.lower() == "readme.md" or path.lower() == "readme":
                return "docs: add readme file"
            elif extension in ["md", "txt", "rst"]:
                return f"docs: add {path}"
            elif file_stats.get("change_type") == "added":
                return f"feat: add {path}"
                
        # 检查是否有重要变更
        important_changes = diff_info.get("important_changes", [])
        if important_changes and isinstance(important_changes, list) and len(important_changes) > 0:
            # 确保至少有一个变更，并且是有效的字典
            main_change = important_changes[0]
            if isinstance(main_change, dict):
                change_type = main_change.get("change_type", "")
                path = main_change.get("path", "")
                
                if path:  # 确保路径不为空
                    # 根据变更类型生成消息
                    if change_type == "added":
                        # 为特定类型的文件生成特定的消息
                        if path.lower() == ".gitignore":
                            return "chore: add gitignore file"
                        elif path.lower().endswith((".md", ".rst", ".txt")) and "readme" in path.lower():
                            return "docs: add readme file"
                        elif path.lower().startswith("license"):
                            return "docs: add license file"
                        elif "test" in path.lower():
                            return f"test: add {path}"
                        elif path.lower().endswith((".json", ".yaml", ".yml", ".toml", ".xml")):
                            return f"chore: add {path} configuration"
                        return f"feat: add {path}"
                    elif change_type in ["renamed", "moved"]:
                        return f"refactor: move {path}"
                    elif change_type == "deleted":
                        return f"chore: remove {path}"
                
        # 根据文件类型分布生成消息
        stats = diff_info.get("stats", {})
        by_type = stats.get("by_type", {})
        if by_type:
            main_type = max(by_type.items(), key=lambda x: len(x[1]["files"]))[0]
            if main_type == "test":
                return "test: update test cases"
            elif main_type == "docs":
                return "docs: update documentation"
            elif main_type == "config":
                return "chore: update configuration"
                
        # 默认消息
        return "chore: update files"
        
    def _generate_detailed_body(self, message: str, diff_info: Dict[str, Any], commit_type: str) -> str:
        """
        生成详细的提交消息体
        
        Args:
            message: 原始消息
            diff_info: 变更信息字典
            commit_type: 提交类型
            
        Returns:
            格式化的消息体
        """
        body_lines = []
        
        # 添加原始消息体（如果有）
        original_body = self._extract_message_body(message)
        if original_body:
            body_lines.extend(original_body)
            body_lines.append("")
            
        # 添加变更摘要
        body_lines.extend(self._generate_changes_summary(diff_info, commit_type))
        
        # 处理特殊类型的提交
        if commit_type == "feat":
            body_lines.extend(self._format_feature_details(diff_info))
        elif commit_type == "fix":
            body_lines.extend(self._format_fix_details(diff_info))
        elif commit_type == "refactor":
            body_lines.extend(self._format_refactor_details(diff_info))
            
        # 添加重要变更警告
        breaking_changes = self._detect_breaking_changes(diff_info)
        if breaking_changes:
            body_lines.append("")
            body_lines.append("BREAKING CHANGE:")
            body_lines.extend(breaking_changes)
            
        return "\n".join(self._wrap_lines(body_lines))
        
    def _extract_message_body(self, message: str) -> List[str]:
        """
        从完整消息中提取消息体部分
        
        Args:
            message: 完整的提交消息
            
        Returns:
            消息体行列表
        """
        lines = message.split('\n')
        if len(lines) <= 1:
            return []
            
        # 跳过第一行（主题行）和后面的空行
        body_lines = []
        started = False
        for line in lines[1:]:
            if not started and not line.strip():
                continue
            started = True
            body_lines.append(line)
            
        return body_lines
        
    def _generate_changes_summary(self, diff_info: Dict[str, Any], commit_type: str) -> List[str]:
        """
        生成变更摘要
        
        Args:
            diff_info: 变更信息字典
            commit_type: 提交类型
            
        Returns:
            摘要行列表
        """
        summary_lines = []
        
        # 添加重要变更
        important_changes = diff_info.get("important_changes", [])
        if important_changes and isinstance(important_changes, list) and len(important_changes) > 0:
            summary_lines.append("主要变更：")
            
            # 确保最多显示3个重要变更，并且每个都是有效的字典
            valid_changes = [c for c in important_changes[:3] if isinstance(c, dict) and c.get("path")]
            
            if valid_changes:
                for change in valid_changes:
                    path = change.get("path", "unknown")
                    summary_lines.append(f"- {path}")
                    
                    # 安全访问摘要信息
                    summary = change.get("summary", [])
                    if summary and isinstance(summary, list):
                        for detail in summary:
                            if isinstance(detail, str):
                                summary_lines.append(f"  • {detail}")
                
                summary_lines.append("")
            else:
                summary_lines.append("- 文件已变更")
                summary_lines.append("")
            
        # 按文件类型分组显示变更
        if diff_info.get("stats", {}).get("by_type"):
            summary_lines.append("变更类型：")
            for file_type, type_stats in diff_info["stats"]["by_type"].items():
                count = len(type_stats["files"])
                type_desc = {
                    "source": "源代码文件",
                    "test": "测试文件",
                    "docs": "文档",
                    "config": "配置文件",
                    "resource": "资源文件"
                }.get(file_type, file_type)
                summary_lines.append(f"- {type_desc}: {count}个文件")
                
        return summary_lines
        
    def _wrap_lines(self, lines: List[str]) -> List[str]:
        """
        将长行按照最大行长度换行
        
        Args:
            lines: 原始行列表
            
        Returns:
            处理后的行列表
        """
        wrapped_lines = []
        for line in lines:
            if len(line) <= MAX_LINE_LENGTH or line.startswith(('- ', '• ')):
                wrapped_lines.append(line)
                continue
                
            # 分割长行
            current_line = ""
            for word in line.split():
                if len(current_line) + len(word) + 1 <= MAX_LINE_LENGTH:
                    current_line = f"{current_line} {word}".strip()
                else:
                    wrapped_lines.append(current_line)
                    current_line = word
            if current_line:
                wrapped_lines.append(current_line)
                
        return wrapped_lines
        
    def _detect_breaking_changes(self, diff_info: Dict[str, Any]) -> List[str]:
        """
        检测是否包含破坏性变更
        
        Args:
            diff_info: 变更信息字典
            
        Returns:
            破坏性变更说明列表
        """
        breaking_changes = []
        
        # 检查删除或重命名的公共API
        for file_stat in diff_info.get("files", []):
            if file_stat.get("change_type") in ["deleted", "renamed", "moved"]:
                if "api" in file_stat["path"].lower() or "public" in file_stat["path"].lower():
                    breaking_changes.append(f"- 变更了公共API: {file_stat['path']}")
                    
        # 检查配置文件的重大变更
        for file_stat in diff_info.get("files", []):
            if file_stat.get("change_type") == "modified":
                if file_stat["path"].endswith((".json", ".yaml", ".yml", ".env")):
                    # 如果配置文件变更超过50%，可能是破坏性变更
                    changes = file_stat.get("insertions", 0) + file_stat.get("deletions", 0)
                    if changes > 50:
                        breaking_changes.append(f"- 配置文件有重大变更: {file_stat['path']}")
                        
        return breaking_changes
        
    def _format_feature_details(self, diff_info: Dict[str, Any]) -> List[str]:
        """
        格式化功能特性的详细信息
        
        Args:
            diff_info: 变更信息字典
            
        Returns:
            详细信息行列表
        """
        details = []
        details.append("\n功能描述：")
        
        # 获取新增的主要文件
        new_files = [f for f in diff_info.get("files", []) if f.get("change_type") == "added"]
        if new_files:
            details.append("新增文件：")
            for file_stat in new_files[:3]:  # 最多显示3个
                details.append(f"- {file_stat['path']}")
                
        # 显示重要的代码变更
        for change in diff_info.get("important_changes", []):
            if change.get("code_preview"):
                details.append("\n核心实现：")
                details.append("```")
                details.extend(change["code_preview"][:1])  # 只显示第一个代码块
                details.append("```")
                break
                
        return details
        
    def _format_fix_details(self, diff_info: Dict[str, Any]) -> List[str]:
        """
        格式化错误修复的详细信息
        
        Args:
            diff_info: 变更信息字典
            
        Returns:
            详细信息行列表
        """
        details = []
        details.append("\n修复内容：")
        
        # 显示修改的文件
        modified_files = [f for f in diff_info.get("files", [])
                        if f.get("change_type") in ["modified", "added"]]
        if modified_files:
            for file_stat in modified_files[:3]:
                details.append(f"- 更新 {file_stat['path']}")
                if file_stat.get("code_preview"):
                    details.append("  变更示例：")
                    details.append("  ```")
                    details.extend("  " + line for line in file_stat["code_preview"][0].split("\n")[:3])
                    details.append("  ```")
                    
        return details
        
    def _format_refactor_details(self, diff_info: Dict[str, Any]) -> List[str]:
        """
        格式化重构变更的详细信息
        
        Args:
            diff_info: 变更信息字典
            
        Returns:
            详细信息行列表
        """
        details = []
        details.append("\n重构内容：")
        
        # 显示文件移动和重命名
        moved_files = [f for f in diff_info.get("files", [])
                      if f.get("change_type") in ["moved", "renamed", "moved_modified", "renamed_modified"]]
        if moved_files:
            details.append("文件重组织：")
            for file_stat in moved_files:
                details.append(f"- {file_stat['path']}")
                
        # 显示主要的代码变更
        if diff_info.get("important_changes"):
            details.append("\n核心变更：")
            for change in diff_info["important_changes"][:2]:
                details.append(f"- {change['path']}")
                if change.get("summary"):
                    for detail in change["summary"]:
                        details.append(f"  • {detail}")
                        
        return details
        
    def _update_commit_type(self, message: str, new_type: str) -> str:
        """
        更新提交消息的类型部分
        
        Args:
            message: 原始提交消息
            new_type: 新的提交类型
            
        Returns:
            更新类型后的消息
        """
        match = re.match(self.CONVENTIONAL_PATTERN, message)
        if not match:
            return f"{new_type}: {message}"
            
        scope_part = match.group(2) or ""
        description = match.group(3)
        
        return f"{new_type}{scope_part}: {description}"
    
    def _refine_commit_type(self, suggested_type: str, diff_info: Dict[str, Any], message: str) -> str:
        """
        结合AI识别和代码分析优化提交类型
        
        Args:
            suggested_type: AI建议的类型
            diff_info: 变更信息字典
            message: 完整提交消息
            
        Returns:
            优化后的提交类型
        """
        # 如果AI建议的类型是有效的，优先使用
        if suggested_type in self.VALID_TYPES:
            return suggested_type
            
        # 从消息内容推断类型
        inferred_from_message = self._infer_type_from_content(message)
        
        # 从变更内容推断类型
        change_types = set()
        for file_stat in diff_info.get("files", []):
            change_type = file_stat.get("change_type", "")
            change_types.add(change_type)
            
        # 基于变更类型推断
        if "added" in change_types and len(diff_info.get("files", [])) > 0:
            # 新增文件超过50%，可能是新功能
            added_count = sum(1 for f in diff_info.get("files", []) if f.get("change_type") == "added")
            if added_count / len(diff_info.get("files", [])) > 0.5:
                return "feat"
                
        if any(t in change_types for t in ["renamed", "moved", "renamed_modified", "moved_modified"]):
            # 如果主要是重命名和移动，可能是重构
            return "refactor"
            
        # 检查是否为测试相关
        test_files = [f for f in diff_info.get("files", []) if "test" in f.get("path", "").lower()]
        if test_files and len(test_files) / len(diff_info.get("files", [])) > 0.5:
            return "test"
            
        # 检查是否为文档相关
        doc_files = [f for f in diff_info.get("files", []) if f.get("path", "").lower().endswith((".md", ".txt", ".doc"))]
        if doc_files and len(doc_files) / len(diff_info.get("files", [])) > 0.5:
            return "docs"
            
        # 从消息内容中推断，如果不确定则返回默认类型
        return inferred_from_message
        
    def _extract_key_changes(self, diff_info: Dict[str, Any]) -> str:
        """
        从变更信息中提取关键变更点，生成简洁的列表
        
        Args:
            diff_info: 变更信息字典
            
        Returns:
            关键变更点列表字符串
        """
        if not diff_info or not diff_info.get("files"):
            return ""
            
        change_points = []
        
        # 添加重要变更
        important_changes = diff_info.get("important_changes", [])
        for change in important_changes[:3]:  # 最多取前3个重要变更
            path = change.get("path", "")
            change_type = change.get("change_type", "")
            
            if change_type == "added":
                change_points.append(f"- 新增: {path}")
            elif change_type in ["renamed", "moved"]:
                change_points.append(f"- 移动/重命名: {path}")
            elif change_type == "deleted":
                change_points.append(f"- 删除: {path}")
            else:
                # 如果有详细摘要，使用摘要
                if change.get("summary"):
                    summary_text = " ".join(change.get("summary", [])[:1])  # 只取第一行摘要
                    change_points.append(f"- 修改 {path}: {summary_text}")
                else:
                    changes = change.get("insertions", 0) + change.get("deletions", 0)
                    change_points.append(f"- 修改 {path} ({changes} 行变更)")
        
        # 如果没有重要变更，则按文件类型分组显示
        if not change_points and diff_info.get("stats", {}).get("by_type"):
            change_points.append("变更内容:")
            for file_type, type_stats in diff_info.get("stats", {}).get("by_type", {}).items():
                count = len(type_stats.get("files", []))
                insertions = type_stats.get("insertions", 0)
                deletions = type_stats.get("deletions", 0)
                
                type_desc = {
                    "source": "源代码",
                    "test": "测试",
                    "docs": "文档",
                    "config": "配置",
                    "resource": "资源"
                }.get(file_type, file_type)
                
                change_points.append(f"- {type_desc}: {count}个文件 (+{insertions} -{deletions})")
        
        return "\n".join(change_points)
    
    def _infer_type_from_content(self, message: str) -> str:
        """
        从消息内容推断提交类型
        
        考虑因素：
        1. 消息关键词
        2. 变更的文件类型
        3. 变更的内容特征
        
        Args:
            message: 提交消息
            
        Returns:
            推断的类型
        """
        lower_message = message.lower()
        
        # 按优先级检查每种类型的模式
        for commit_type, patterns in COMMIT_TYPE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, lower_message):
                    return commit_type
                    
        # 如果无法从消息中推断，结合上下文继续分析
        if "test" in lower_message or "spec" in lower_message:
            return "test"
        elif "文档" in lower_message or "注释" in lower_message:
            return "docs"
        elif "优化" in lower_message or "重构" in lower_message:
            return "refactor"
        elif "配置" in lower_message or "设置" in lower_message:
            return "chore"
        elif "bug" in lower_message or "修复" in lower_message:
            return "fix"
        elif "新" in lower_message or "add" in lower_message:
            return "feat"
            
        # 默认类型
        return "chore"
        
    def _is_new_file_only_commit(self, diff_info: Dict[str, Any]) -> bool:
        """
        判断是否只有新增文件的提交
        
        Args:
            diff_info: 变更信息
            
        Returns:
            如果所有变更都是新增文件，返回True
        """
        # 获取文件列表
        files = diff_info.get("files", [])
        if not files:
            return False
            
        # 检查是否所有文件都是新增的
        for file_stat in files:
            if file_stat.get("change_type") != "added":
                return False
                
        return True
    
    def _refine_type_for_new_file(self, diff_info: Dict[str, Any], current_type: str) -> str:
        """
        为新文件提交优化提交类型
        
        Args:
            diff_info: 变更信息
            current_type: 当前提交类型
            
        Returns:
            优化后的提交类型
        """
        # 如果当前类型已经基于变更特性进行了推断，保留它
        if current_type != "chore":
            return current_type
            
        # 获取重要变更
        important_changes = diff_info.get("important_changes", [])
        if not important_changes:
            return current_type
            
        # 检查第一个重要的新文件
        main_change = important_changes[0]
        path = main_change.get("path", "")
        summary = main_change.get("summary", [])
        
        # 根据文件特征和自动摘要优化类型
        # 文档文件
        if path.lower().endswith((".md", ".rst", ".txt", ".pdf", ".docx")):
            return "docs"
            
        # 测试文件
        if "test" in path.lower() or any("test" in item.lower() for item in summary):
            return "test"
            
        # 配置文件
        if path.lower().endswith((".json", ".yaml", ".yml", ".toml", ".xml", ".ini", ".conf", ".cfg")):
            return "chore"
            
        # 样式文件
        if path.lower().endswith((".css", ".scss", ".sass", ".less", ".style")):
            return "style"
            
        # 构建文件
        if any(name in path.lower() for name in ["makefile", "dockerfile", "jenkinsfile", "package.json", "setup.py"]):
            return "build"
            
        # CI 配置
        if ".github/" in path.lower() or ".gitlab-ci" in path.lower() or "travis" in path.lower():
            return "ci"
            
        # 源代码文件，默认为功能增加
        if path.lower().endswith((".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp", ".go", ".rs")):
            return "feat"
            
        # 保持默认类型
        return current_type