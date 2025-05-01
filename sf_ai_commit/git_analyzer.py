"""
Git差异分析模块 - 负责分析Git仓库的变更
"""

import os
import re
import logging
import subprocess
from typing import Dict, List, Any, Optional, Tuple
from git import Repo, GitCommandError
from git.diff import Diff

from sf_ai_commit.constants import (
    GIT_DIFF_ENCODING,
    GIT_DEFAULT_REPO_PATH,
    GIT_DEFAULT_DIFF_MAX_LINES,
    ERROR_GIT_REPO_NOT_FOUND,
    ERROR_GIT_NO_STAGED_CHANGES
)
from sf_ai_commit.utils import (
    is_binary_file,
    is_binary_stream,
    analyze_diff_content,
    extract_meaningful_diff_content,
    extract_meaningful_code_lines
)

class GitAnalyzer:
    """分析Git仓库的变更"""
    
    def __init__(self, repo_path: str = GIT_DEFAULT_REPO_PATH):
        """
        初始化Git分析器
        
        Args:
            repo_path: Git仓库路径，默认为当前目录
        
        Raises:
            ValueError: 如果指定的路径不是一个有效的Git仓库
        """
        try:
            self.repo = Repo(repo_path)
            if self.repo.bare:
                raise ValueError(f"裸仓库不支持: {repo_path}")
        except Exception as e:
            raise ValueError(f"{ERROR_GIT_REPO_NOT_FOUND.format(repo_path)}: {str(e)}")
        
        self.repo_path = repo_path
        self._diff_summary = None
        self.logger = logging.getLogger(__name__)
    
    def stage_files(self, file_paths: List[str]) -> bool:
        """
        将指定的文件或文件夹添加到暂存区
        
        Args:
            file_paths: 要添加到暂存区的文件或文件夹路径列表
            
        Returns:
            成功添加返回True，否则返回False
            
        Raises:
            GitCommandError: 如果Git命令执行失败
        """
        if not file_paths:
            return True
            
        try:
            self.logger.info(f"添加文件到暂存区: {', '.join(file_paths)}")
            self.repo.git.add(*file_paths)
            return True
        except GitCommandError as e:
            self.logger.error(f"添加文件到暂存区失败: {str(e)}")
            raise RuntimeError(f"添加文件到暂存区失败: {str(e)}")
    
    def get_staged_diff(self) -> List[Diff]:
        """
        获取暂存区的差异对象列表
        
        返回索引(暂存区)和HEAD之间的差异，只处理暂存的变更。
        
        Returns:
            包含暂存区变更的差异对象列表
            
        Raises:
            ValueError: 如果没有暂存的变更
        """
        self.logger.info("获取暂存区差异")
        
        # 检查是否为空仓库（首次提交）
        is_empty = self.is_empty_repo()
        self.logger.debug(f"仓库状态: {'空仓库（首次提交）' if is_empty else '已有提交历史'}")
        
        # 初始化差异列表
        diffs = []
        
        # 获取已有文件的暂存区差异
        if not is_empty:
            try:
                # 获取索引(暂存区)和HEAD之间的差异
                diffs = list(self.repo.index.diff(self.repo.head.commit, staged=True))
                self.logger.debug(f"从索引和HEAD获取差异: {len(diffs)} 个")
            except Exception as e:
                self.logger.warning(f"获取暂存区差异时出错: {str(e)}")
        
        # 处理暂存区中的新文件
        try:
            # 使用 git status --porcelain 直接获取更可靠的状态信息
            status_output = self.repo.git.status(porcelain=True)
            self.logger.debug(f"Git状态输出: {status_output}")
            
            # 解析状态输出，提取新添加和已删除文件
            for line in status_output.splitlines():
                if not line or len(line) < 3:
                    continue
                    
                status_code = line[:2].strip()
                file_path = line[3:].strip()
                
                # 跳过未暂存文件 (如果状态码不包含 A - 新增)
                if 'A' not in status_code:
                    continue
                
                # 处理已暂存的新文件
                self.logger.debug(f"处理暂存区的新文件: {file_path} (状态: {status_code})")
                
                # 检查文件是否已经在差异列表中
                if any(getattr(diff, 'b_path', '') == file_path for diff in diffs):
                    self.logger.debug(f"文件 {file_path} 已在差异列表中，跳过")
                    continue
                
                # 获取文件的完整路径
                full_path = os.path.join(self.repo_path, file_path)
                
                # 检查文件是否存在
                if not os.path.exists(full_path):
                    self.logger.warning(f"文件 {file_path} 不存在，跳过")
                    continue
                
                # 检查是否是二进制文件
                is_binary = is_binary_file(full_path)
                
                # 为新文件创建差异内容
                if is_binary:
                    # 二进制文件使用简单的差异表示
                    diff_content = f"diff --git a/{file_path} b/{file_path}\nnew file mode 100644\nBinary files /dev/null and b/{file_path} differ\n"
                else:
                    try:
                        # 使用 git diff --cached 获取新文件的差异输出
                        diff_output = self.repo.git.diff("--cached", "--", file_path)
                        
                        if diff_output:
                            diff_content = diff_output
                        else:
                            # 手动构建差异内容
                            try:
                                with open(full_path, 'r', encoding=GIT_DIFF_ENCODING, errors='replace') as f:
                                    file_content = f.read()
                                
                                lines = file_content.splitlines()
                                diff_content = f"diff --git a/{file_path} b/{file_path}\nnew file mode 100644\n--- /dev/null\n+++ b/{file_path}\n@@ -0,0 +1,{len(lines)} @@\n"
                                for line in lines:
                                    diff_content += f"+{line}\n"
                            except UnicodeDecodeError:
                                # 如果解码失败，可能是二进制文件
                                is_binary = True
                                diff_content = f"diff --git a/{file_path} b/{file_path}\nnew file mode 100644\nBinary files /dev/null and b/{file_path} differ\n"
                    except Exception as e:
                        self.logger.warning(f"获取新文件 {file_path} 的差异时出错: {str(e)}")
                        # 使用简单的差异表示作为后备
                        diff_content = f"diff --git a/{file_path} b/{file_path}\nnew file mode 100644\n"
                
                # 创建模拟的 Diff 对象
                mock_diff = type('MockDiff', (), {
                    'a_path': '',  # 新文件没有原始路径
                    'b_path': file_path,
                    'new_file': True,
                    'renamed': False,
                    'deleted_file': False,
                    'diff': diff_content.encode(GIT_DIFF_ENCODING) if isinstance(diff_content, str) else diff_content,
                    'change_type': 'added',
                    'is_binary': is_binary
                })
                
                diffs.append(mock_diff)
        except Exception as e:
            self.logger.warning(f"处理暂存区的新文件时出错: {str(e)}")
        
        # 检查是否有暂存的变更
        if not diffs:
            self.logger.warning("没有检测到暂存的变更")
            raise ValueError(ERROR_GIT_NO_STAGED_CHANGES)
            
        self.logger.info(f"找到 {len(diffs)} 个暂存的变更")
        return diffs
    
    def analyze_diff(self) -> Dict[str, Any]:
        """
        分析差异内容，提取有用信息
        
        返回一个包含以下信息的字典：
        - 文件级别的变更统计
        - 代码块级别的具体变更
        - 变更的语义分类
        - 按文件类型分组的变更摘要
        - 重要变更的优先级排序
        
        Returns:
            包含差异分析结果的字典
        """
        files_stats = []
        total_stats = {
            "insertions": 0,
            "deletions": 0,
            "files": {
                "added": [],
                "modified": [],
                "deleted": [],
                "renamed": [],
                "moved": []
            },
            "by_type": {}  # 按文件类型分组的统计
        }
        
        try:
            # 尝试获取暂存区差异
            diffs = self.get_staged_diff()
            
            # 分析每个变更的文件
            for diff in diffs:
                try:
                    diff_stats = self._analyze_file_diff(diff)
                    files_stats.append(diff_stats)
                    
                    # 更新总体统计
                    total_stats["insertions"] += diff_stats.get("insertions", 0)
                    total_stats["deletions"] += diff_stats.get("deletions", 0)
                    
                    # 按变更类型分类文件
                    change_type = diff_stats.get("change_type", "modified")
                    # 确保变更类型有效
                    if change_type not in total_stats["files"]:
                        self.logger.warning(f"未知变更类型: {change_type}，使用 'modified' 代替")
                        change_type = "modified"
                        
                    file_info = {
                        "path": diff_stats.get("path", "unknown"),
                        "ext": diff_stats.get("extension", ""),
                        "impact_score": self._calculate_impact_score(diff_stats)
                    }
                    total_stats["files"][change_type].append(file_info)
                    
                    # 按文件类型分组统计
                    file_type = self._categorize_file_type(
                        diff_stats.get("path", ""),
                        diff_stats.get("extension", "")
                    )
                    if file_type not in total_stats["by_type"]:
                        total_stats["by_type"][file_type] = {
                            "files": [],
                            "insertions": 0,
                            "deletions": 0
                        }
                    total_stats["by_type"][file_type]["files"].append(file_info)
                    total_stats["by_type"][file_type]["insertions"] += diff_stats.get("insertions", 0)
                    total_stats["by_type"][file_type]["deletions"] += diff_stats.get("deletions", 0)
                except Exception as e:
                    self.logger.error(f"分析文件差异时出错: {str(e)}")
                    # 记录详细错误信息便于调试
                    self.logger.debug(f"文件: {diff.b_path if hasattr(diff, 'b_path') else 'unknown'}")
                    self.logger.debug(f"变更类型: {diff.change_type if hasattr(diff, 'change_type') else 'unknown'}")
                    # 继续处理下一个差异，而不是整个失败
        except ValueError as e:
            # 没有暂存的变更
            logging.error(str(e))
            return {"error": str(e), "files": [], "summary": ""}
        except Exception as e:
            # 其他未预期的错误
            error_msg = f"分析Git变更失败: {str(e)}"
            self.logger.error(error_msg)
            return {"error": error_msg, "files": [], "summary": ""}
        
        # 如果没有成功分析任何文件
        if not files_stats:
            return {"error": "无法分析任何文件变更", "files": [], "summary": ""}
        
        # 计算变更重要性并排序
        try:
            files_stats.sort(key=lambda x: self._calculate_impact_score(x), reverse=True)
        except Exception as e:
            self.logger.error(f"排序文件变更时出错: {str(e)}")
        
        # 安全地生成文本摘要和重要变更
        try:
            summary_text = self._generate_text_summary(files_stats, total_stats)
        except Exception as e:
            self.logger.error(f"生成文本摘要时出错: {str(e)}")
            summary_text = "无法生成摘要"
            
        try:
            important_changes = self._identify_important_changes(files_stats)
        except Exception as e:
            self.logger.error(f"识别重要变更时出错: {str(e)}")
            important_changes = []
            
        # 确保 important_changes 不为 None
        if important_changes is None:
            important_changes = []
        
        # 获取仓库信息
        try:
            repo_info = self.get_repo_info()
        except Exception as e:
            self.logger.error(f"获取仓库信息失败: {str(e)}")
            repo_info = {"is_empty": self.is_empty_repo()}
        
        # 整理汇总信息
        diff_summary = {
            "files": files_stats,
            "total_files": len(files_stats),
            "stats": total_stats,
            "summary": summary_text,
            "important_changes": important_changes,
            "repo_info": repo_info
        }
        
        self._diff_summary = diff_summary
        return diff_summary
    
    def _analyze_file_diff(self, diff: Diff) -> Dict[str, Any]:
        """
        分析单个文件的差异
        
        进行更深入的分析，包括：
        - 详细的变更统计
        - 代码块级别的变更分析
        - 语义级别的变更识别
        - 移动和重命名的精确检测
        - 文件类型相关的上下文分析
        
        Args:
            diff: GitPython的Diff对象或自定义模拟Diff对象
            
        Returns:
            包含文件差异分析结果的字典
        """
        # 获取文件路径 - 使用安全访问
        try:
            old_path = getattr(diff, 'a_path', '')
            new_path = getattr(diff, 'b_path', '') or old_path
            self.logger.debug(f"分析文件差异: {new_path}")
        except Exception as e:
            self.logger.error(f"获取文件路径时出错: {str(e)}")
            old_path = ""
            new_path = "unknown_file"
        
        # 详细的变更类型分析 - 使用安全访问
        try:
            if getattr(diff, 'new_file', False):
                change_type = "added"
            elif getattr(diff, 'deleted_file', False):
                change_type = "deleted"
            elif getattr(diff, 'renamed', False):
                change_type = "renamed"
                # 检测是否同时包含内容变更
                if hasattr(diff, 'diff') and diff.diff:
                    change_type = "renamed_modified"
            elif self._is_file_moved(old_path, new_path):
                change_type = "moved"
                if hasattr(diff, 'diff') and diff.diff:
                    change_type = "moved_modified"
            else:
                change_type = "modified"
        except Exception as e:
            self.logger.error(f"确定变更类型时出错: {str(e)}")
            change_type = "modified"  # 默认为修改
        
        # 初始化统计信息
        stats = {
            "insertions": 0,
            "deletions": 0,
            "modifications": 0,
            "blocks": []
        }
        
        # 检查是否已指定二进制文件标志
        is_binary = getattr(diff, 'is_binary', False)
        diff_content = ""
        code_blocks = []
        
        # 尝试分析差异内容
        try:
            if hasattr(diff, 'diff'):
                # 尝试解码差异内容
                try:
                    # 兼容处理：检查类型
                    if isinstance(diff.diff, str):
                        diff_content = diff.diff
                    elif isinstance(diff.diff, bytes):
                        diff_content = diff.diff.decode(GIT_DIFF_ENCODING, errors='replace')
                    else:
                        # 使用str()处理其他类型
                        diff_content = str(diff.diff)
                    
                    # 检查是否是二进制文件
                    if "Binary files" in diff_content:
                        is_binary = True
                    
                    if not is_binary:
                        # 使用工具函数分析差异内容获取统计和代码块
                        stats, code_blocks = analyze_diff_content(diff_content)
                        
                        # 如果统计中没有行数信息，尝试直接从git获取
                        if not stats.get("insertions") and not stats.get("deletions"):
                            try:
                                # 使用git diff --numstat获取更准确的统计数据
                                numstat_output = self.repo.git.diff("--cached", "--numstat", "--", new_path)
                                if numstat_output:
                                    parts = numstat_output.strip().split("\t")
                                    if len(parts) >= 2:
                                        try:
                                            insertions = int(parts[0]) if parts[0] != "-" else 0
                                            deletions = int(parts[1]) if parts[1] != "-" else 0
                                            stats["insertions"] = insertions
                                            stats["deletions"] = deletions
                                        except ValueError:
                                            pass
                            except Exception as e:
                                self.logger.debug(f"使用git numstat获取行数统计失败: {str(e)}")
                except Exception as e:
                    self.logger.debug(f"无法解码文件差异内容: {str(e)}")
                    diff_content = "(binary file or decode error)"
                    is_binary = True
        except Exception as e:
            self.logger.warning(f"分析差异内容时出错: {str(e)}")
        
        # 如果没有确定是否为二进制文件，尝试通过其他方式检查
        if not is_binary and new_path:
            try:
                # 检查完整路径下的文件
                full_path = os.path.join(self.repo_path, new_path)
                if os.path.exists(full_path):
                    is_binary = is_binary_file(full_path)
            except Exception as e:
                self.logger.debug(f"通过文件检查二进制类型时出错: {str(e)}")
        
        # 获取文件扩展名以识别文件类型
        _, file_ext = os.path.splitext(new_path)
        file_ext = file_ext.lstrip('.').lower() if file_ext else ""
        
        return {
            "path": new_path,
            "change_type": change_type,
            "insertions": stats.get("insertions", 0),
            "deletions": stats.get("deletions", 0),
            "extension": file_ext,
            "is_binary": is_binary,
            "diff_content": diff_content,
            "code_blocks": code_blocks
        }
    
    def _generate_text_summary(self, files_stats: List[Dict[str, Any]],
                              total_stats: Dict[str, Any]) -> str:
        """
        生成差异的文本摘要，结构化输出文件类型和数量
        
        Args:
            files_stats: 文件变更统计信息列表
            total_stats: 总体统计信息
            
        Returns:
            差异的文本摘要
        """
        summary_lines = []
        
        # 添加总体统计信息
        total_files = len(files_stats)
        
        # 确保插入和删除行数正确计算
        insertions = 0
        deletions = 0
        
        # 直接从文件统计中计算，避免使用可能不准确的total_stats
        for file_stat in files_stats:
            insertions += file_stat.get("insertions", 0)
            deletions += file_stat.get("deletions", 0)
        
        # 更新total_stats中的值，确保其他地方使用时也是正确的
        total_stats["insertions"] = insertions
        total_stats["deletions"] = deletions
        
        summary_lines.append(f"变更概览: 共 {total_files} 个文件")
        summary_lines.append(f"代码变更: +{insertions} -{deletions} 行")
        
        # 按变更类型统计文件数量
        change_type_counts = {
            "added": 0,
            "modified": 0,
            "deleted": 0,
            "renamed": 0,
            "moved": 0,
            "renamed_modified": 0,
            "moved_modified": 0
        }
        
        for file_stat in files_stats:
            change_type = file_stat.get("change_type", "modified")
            if change_type in change_type_counts:
                change_type_counts[change_type] += 1
        
        # 添加变更类型统计
        change_type_summary = []
        change_type_desc = {
            "added": "新增",
            "modified": "修改",
            "deleted": "删除",
            "renamed": "重命名",
            "moved": "移动",
            "renamed_modified": "重命名并修改",
            "moved_modified": "移动并修改"
        }
        
        for change_type, count in change_type_counts.items():
            if count > 0:
                desc = change_type_desc.get(change_type, change_type)
                change_type_summary.append(f"{desc}: {count}个")
        
        if change_type_summary:
            summary_lines.append("变更类型: " + ", ".join(change_type_summary))
        
        # 按文件类型分组显示变更
        summary_lines.append("\n按文件类型统计:")
        for file_type, type_stats in total_stats["by_type"].items():
            count = len(type_stats["files"])
            type_insertions = type_stats["insertions"]
            type_deletions = type_stats["deletions"]
            summary_lines.append(f"- {file_type}: {count}个文件 (+{type_insertions} -{type_deletions})")
        
        # 显示重命名和移动的文件
        if total_stats["files"]["renamed"] or total_stats["files"]["moved"]:
            summary_lines.append("\n文件重命名/移动:")
            # 按路径排序，让输出更一致
            renamed_moved = sorted(
                total_stats["files"]["renamed"] + total_stats["files"]["moved"],
                key=lambda x: x.get("path", "")
            )
            for file_info in renamed_moved:
                summary_lines.append(f"- {file_info['path']}")
        
        return '\n'.join(summary_lines)
    
    def get_diff_summary(self) -> Dict[str, Any]:
        """
        获取变更摘要
        
        如果尚未分析，则先执行分析
        
        Returns:
            包含差异分析结果的字典
        """
        if self._diff_summary is None:
            return self.analyze_diff()
        return self._diff_summary
    
    def commit(self, message: str) -> str:
        """
        执行Git提交操作
        
        Args:
            message: 提交消息
            
        Returns:
            新提交的SHA哈希值
            
        Raises:
            RuntimeError: 如果提交失败
        """
        try:
            self.logger.info("执行Git提交")
            # 执行提交
            commit = self.repo.index.commit(message)
            self.logger.info(f"提交成功: {commit.hexsha[:8]}")
            return commit.hexsha
        except GitCommandError as e:
            self.logger.error(f"提交失败: {str(e)}")
            raise RuntimeError(f"提交失败: {str(e)}")
        
    def is_empty_repo(self) -> bool:
        """
        检查仓库是否为空（没有提交历史）
        
        Returns:
            如果仓库为空则返回True，否则返回False
        """
        try:
            # 尝试获取HEAD引用
            self.repo.head.commit
            return False
        except (ValueError, TypeError, AttributeError) as e:
            self.logger.debug(f"检测到空仓库: {str(e)}")
            return True
    
    def get_repo_info(self) -> Dict[str, Any]:
        """
        获取仓库基本信息
        
        Returns:
            包含仓库信息的字典
        """
        try:
            active_branch = self.repo.active_branch.name
        except TypeError:
            # 处理HEAD分离状态
            active_branch = "HEAD detached"
            
        return {
            "working_dir": self.repo.working_dir,
            "active_branch": active_branch,
            "is_dirty": self.repo.is_dirty(),
            "untracked_files": self.repo.untracked_files,
            "remote_count": len(self.repo.remotes),
            "remotes": [{"name": remote.name, "url": remote.url} for remote in self.repo.remotes],
            "is_empty": self.is_empty_repo()
        }
        
    def _analyze_diff_content(self, diff_content: str) -> Tuple[Dict[str, int], List[str]]:
        """
        分析差异内容，提取代码块级别的变更信息
        
        Args:
            diff_content: 文件的差异内容
            
        Returns:
            包含统计信息的字典和代码块列表的元组
        """
        # 使用工具函数进行分析
        return analyze_diff_content(diff_content)
        
    def _calculate_impact_score(self, diff_stats: Dict[str, Any]) -> float:
        """
        计算变更的影响分数
        
        考虑因素：
        - 变更的行数
        - 文件的类型和重要性
        - 变更类型（新增/修改/删除）
        - 是否包含关键字或特殊模式
        
        Args:
            diff_stats: 文件的差异统计信息
            
        Returns:
            表示变更重要性的分数(0-100)
        """
        score = 0.0
        path = diff_stats.get("path", "")
        change_type = diff_stats.get("change_type", "")
        
        # 基础分数：根据变更行数
        total_changes = diff_stats.get("insertions", 0) + diff_stats.get("deletions", 0)
        score += min(total_changes / 10, 40)  # 最多40分
        
        # 文件类型权重
        file_type = self._categorize_file_type(path, diff_stats.get("extension", ""))
        type_weights = {
            "source": 30,      # 源代码文件
            "config": 25,      # 配置文件
            "test": 20,       # 测试文件
            "docs": 15,       # 文档
            "resource": 10,    # 资源文件
            "other": 5        # 其他文件
        }
        score += type_weights.get(file_type, 5)
        
        # 变更类型权重
        type_scores = {
            "added": 15,
            "deleted": 10,
            "modified": 20,
            "renamed": 5,
            "moved": 5,
            "renamed_modified": 25,
            "moved_modified": 25
        }
        score += type_scores.get(change_type, 10)
        
        # 关键文件加分
        important_patterns = [
            r'main\.[^/]+$',          # 主文件
            r'config\.[^/]+$',        # 配置文件
            r'requirements\.txt$',     # 依赖文件
            r'package\.json$',         # 包配置
            r'Dockerfile$',           # 容器配置
            r'\.env[^/]*$',           # 环境配置
            r'setup\.py$'             # 安装配置
        ]
        
        for pattern in important_patterns:
            if re.search(pattern, path, re.I):
                score += 10
                break
        
        return min(score, 100)  # 最高100分
    
    def _categorize_file_type(self, path: str, extension: str) -> str:
        """
        根据文件路径和扩展名分类文件类型
        
        Args:
            path: 文件路径
            extension: 文件扩展名
            
        Returns:
            文件类型分类
        """
        # 源代码文件扩展名
        source_exts = {
            'py', 'js', 'ts', 'java', 'c', 'cpp', 'go', 'rs',
            'rb', 'php', 'swift', 'kt', 'scala', 'sh', 'bash'
        }
        
        # 配置文件扩展名
        config_exts = {
            'json', 'yaml', 'yml', 'toml', 'ini', 'conf',
            'xml', 'properties', 'env'
        }
        
        # 配置文件路径模式
        config_patterns = [
            r'\.gitignore$',
            r'\.dockerignore$',
            r'\.eslintrc.*$',
            r'\.prettierrc.*$',
            r'\.babelrc.*$',
            r'\.editorconfig$',
            r'\.npmrc$',
            r'\.env\.',
            r'config\..*$',
            r'settings\..*$'
        ]
        
        # 测试文件模式
        test_patterns = [
            r'test[s]?/',
            r'test[s]?\.',
            r'_test\.',
            r'spec\.',
            r'[Tt]est[s]?\..*$'
        ]
        
        # 文档文件扩展名
        doc_exts = {
            'md', 'rst', 'txt', 'doc', 'docx', 'pdf',
            'tex', 'adoc', 'wiki'
        }
        
        # 资源文件扩展名
        resource_exts = {
            'jpg', 'jpeg', 'png', 'gif', 'svg', 'ico',
            'css', 'scss', 'sass', 'less', 'html', 'htm',
            'woff', 'woff2', 'ttf', 'eot'
        }
        
        # 首先检查特殊的配置文件模式
        for pattern in config_patterns:
            if re.search(pattern, path, re.I):
                return "config"
        
        # 检查测试文件模式
        for pattern in test_patterns:
            if re.search(pattern, path):
                return "test"
        
        # 按扩展名分类
        ext = extension.lower()
        if ext in source_exts:
            return "source"
        elif ext in config_exts:
            return "config"
        elif ext in doc_exts:
            return "docs"
        elif ext in resource_exts:
            return "resource"
        
        # 特殊文件名检查（无扩展名）
        special_files = {
            'makefile': 'source',
            'dockerfile': 'config',
            'license': 'docs',
            'readme': 'docs',
            'changelog': 'docs',
            'contributing': 'docs'
        }
        
        filename = os.path.basename(path).lower()
        for special_name, file_type in special_files.items():
            if filename == special_name:
                return file_type
        
        return "other"
    
    def _is_file_moved(self, old_path: str, new_path: str) -> bool:
        """
        检测文件是否被移动到新位置
        
        Args:
            old_path: 原始文件路径
            new_path: 新文件路径
            
        Returns:
            如果文件被移动则返回True
        """
        if not old_path or not new_path or old_path == new_path:
            return False
            
        # 获取文件名
        old_name = os.path.basename(old_path)
        new_name = os.path.basename(new_path)
        
        # 如果文件名相同但路径不同，认为是移动
        return old_name == new_name and old_path != new_path
    
    def _get_significant_blocks(self, code_blocks: List[str], max_blocks: int = 3) -> List[str]:
        """
        从代码块列表中提取最重要的几个块
        
        Args:
            code_blocks: 代码块列表
            max_blocks: 最多返回的块数
            
        Returns:
            重要代码块列表
        """
        if not code_blocks:
            return []
            
        # 计算每个代码块的重要性分数
        scored_blocks = []
        for block in code_blocks:
            score = 0
            lines = block.split('\n')
            
            # 较长的块可能更重要
            score += min(len(lines) / 5, 10)
            
            # 包含关键字的块可能更重要
            keywords = [
                'def ', 'class ', 'import ', 'from ', 'return',
                'async ', 'await ', '@', 'try:', 'with ',
                'function', '=>', 'interface', 'type', 'const'
            ]
            
            for line in lines:
                for keyword in keywords:
                    if keyword in line:
                        score += 2
                        break
            
            scored_blocks.append((score, block))
        
        # 按分数排序并返回前N个块
        scored_blocks.sort(reverse=True)
        return [block for _, block in scored_blocks[:max_blocks]]
    
    def _extract_new_file_summary(self, file_stat: Dict[str, Any]) -> List[str]:
        """
        为新添加的文件生成摘要信息
        
        Args:
            file_stat: 文件统计信息
            
        Returns:
            摘要信息列表
        """
        # 获取基本信息
        path = file_stat.get("path", "")
        extension = file_stat.get("extension", "").lower()
        content = file_stat.get("diff_content", "")
        is_binary = file_stat.get("is_binary", False)
        
        # 对于常见文件类型，保留简单规则匹配
        if path.lower() == ".gitignore":
            return ["添加Git忽略规则文件"]
        elif path.lower() in ["readme.md", "readme"]:
            return ["添加项目说明文档"]
        elif path.lower() in ["license", "license.md", "license.txt"]:
            return ["添加开源许可证文件"]
        
        # 使用简单的关键词分析进行智能推断
        summary = []
        file_type = ""
        file_purpose = ""
        
        # 确定文件类型
        if extension == "py":
            file_type = "Python"
        elif extension in ["js", "jsx"]:
            file_type = "JavaScript"
        elif extension in ["ts", "tsx"]:
            file_type = "TypeScript"
        elif extension == "html":
            file_type = "HTML"
        elif extension == "css":
            file_type = "CSS"
        elif extension in ["md", "txt"]:
            file_type = "文档"
        elif extension in ["json", "yaml", "yml", "toml"]:
            file_type = "配置"
        elif extension in ["sh", "bash", "ps1", "bat", "cmd"]:
            file_type = "脚本"
        elif is_binary:
            file_type = "二进制"
        else:
            file_type = "源代码"
            
        # 确定文件用途
        if "test" in path.lower() or content and "test" in content.lower():
            file_purpose = "测试"
        elif "config" in path.lower() or "settings" in path.lower():
            file_purpose = "配置"
        elif "util" in path.lower() or "helper" in path.lower():
            file_purpose = "工具"
        elif "component" in path.lower():
            file_purpose = "UI组件"
        elif "api" in path.lower() or "service" in path.lower():
            file_purpose = "服务/API"
        elif "model" in path.lower() or "schema" in path.lower() or "entity" in path.lower():
            file_purpose = "数据模型"
        elif "controller" in path.lower() or "handler" in path.lower():
            file_purpose = "控制器"
        else:
            # 从文件名猜测用途
            filename = path.split("/")[-1] if "/" in path else path
            basename = filename.split(".")[0] if "." in filename else filename
            file_purpose = basename.replace("_", " ").replace("-", " ")
            
        # 如果有明确的类型和用途，生成更有意义的摘要
        if file_type and file_purpose:
            summary.append(f"添加{file_type}{file_purpose}文件")
        elif file_type:
            summary.append(f"添加{file_type}文件")
        else:
            summary.append(f"添加新文件")
            
        return summary
    
    def _extract_change_summary(self, file_stat: Dict[str, Any]) -> List[str]:
        """
        提取文件变更的摘要信息
        
        Args:
            file_stat: 文件统计信息
            
        Returns:
            摘要信息列表
        """
        summary = []
        
        # 添加更有意义的变更描述
        if file_stat.get("change_type") in ["renamed", "moved"]:
            summary.append("移动或重命名文件")
        
        insertions = file_stat.get("insertions", 0)
        deletions = file_stat.get("deletions", 0)
        total_changes = insertions + deletions
        
        if total_changes > 0:
            if insertions > 0 and deletions > 0:
                if insertions > deletions * 2:
                    summary.append("大量添加新内容")
                elif deletions > insertions * 2:
                    summary.append("移除大部分代码")
                else:
                    summary.append("重构或更新实现")
            elif insertions > 0:
                summary.append("添加新功能或内容")
            elif deletions > 0:
                summary.append("移除旧代码或功能")
        
        # 根据文件类型添加更多信息
        extension = file_stat.get("extension", "").lower()
        if extension == "py":
            if file_stat.get("diff_content") and "def " in file_stat.get("diff_content", ""):
                summary.append("更新了函数/方法定义")
            if file_stat.get("diff_content") and "class " in file_stat.get("diff_content", ""):
                summary.append("修改了类定义")
        
        return summary
    
    def _identify_important_changes(self, files_stats: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        识别重要的变更，优先选择更改较大的文件，并处理同一文件的增删记录
        
        Args:
            files_stats: 文件变更统计信息列表
            
        Returns:
            重要变更列表，每个元素包含变更路径、类型、影响分数和摘要
        """
        # 防御性编程：确保返回有效列表
        if not files_stats or not isinstance(files_stats, list):
            self.logger.warning(f"无效的文件变更统计信息: {type(files_stats)}")
            return []
            
        # 过滤出有效的文件统计信息
        valid_stats = [stat for stat in files_stats if isinstance(stat, dict) and stat.get("path")]
        if not valid_stats:
            self.logger.warning("没有找到有效的文件变更统计信息")
            return []
        
        # 按文件路径对变更进行分组，处理同一文件的多个变更
        changes_by_file = {}
        for stat in valid_stats:
            path = stat.get("path", "")
            if not path:
                continue
                
            change_type = stat.get("change_type", "modified")
            impact_score = self._calculate_impact_score(stat)
            
            # 如果文件已在跟踪中，决定保留哪个变更
            if path in changes_by_file:
                existing = changes_by_file[path]
                existing_type = existing["change_type"]
                
                # 处理同一文件的增删记录，只保留最终状态
                # 如果文件先被添加后被删除，最终状态是不存在（跳过该文件）
                if change_type == "deleted" and existing_type == "added":
                    del changes_by_file[path]
                    continue
                # 如果文件先被删除后被添加，最终状态是被修改
                elif change_type == "added" and existing_type == "deleted":
                    changes_by_file[path]["change_type"] = "modified"
                    changes_by_file[path]["stat"] = stat
                # 否则保留影响分数更高的变更
                elif impact_score > existing["impact_score"]:
                    changes_by_file[path]["change_type"] = change_type
                    changes_by_file[path]["impact_score"] = impact_score
                    changes_by_file[path]["stat"] = stat
            else:
                # 新增跟踪
                changes_by_file[path] = {
                    "change_type": change_type,
                    "impact_score": impact_score,
                    "stat": stat
                }
        
        # 按影响分数排序
        sorted_changes = sorted(
            list(changes_by_file.values()),
            key=lambda x: x["impact_score"],
            reverse=True
        )
        
        # 生成重要变更列表
        important_changes = []
        # 最多返回8个重要变更，但尝试包含不同类型的文件
        file_types_included = set()
        for change_info in sorted_changes:
            if len(important_changes) >= 8:
                break
                
            stat = change_info["stat"]
            path = stat.get("path", "unknown")
            change_type = change_info["change_type"]
            
            # 尝试包含不同类型的文件
            file_ext = os.path.splitext(path)[1].lower()
            file_type = self._categorize_file_type(path, file_ext[1:] if file_ext else "")
            
            # 如果已经包含了3个同类型的文件，并且还有其他变更，跳过此类型
            if file_type in file_types_included and len(file_types_included) > 1 and len(important_changes) > 3:
                continue
                
            file_types_included.add(file_type)
            
            # 构建变更信息
            change = {
                "path": path,
                "change_type": change_type,
                "impact_score": change_info["impact_score"],
            }
            
            # 添加文件内容推测的用途
            try:
                # 为不同类型的变更生成适当的摘要
                if change_type == "added":
                    # 对于新文件，尝试根据文件类型和内容推测用途
                    change["summary"] = self._extract_new_file_summary(stat)
                else:
                    # 对于修改的文件，提取变更的内容
                    change["summary"] = self._extract_change_summary(stat)
                    
                # 确保summary是有意义的
                if not change.get("summary"):
                    change["summary"] = [f"{file_type}文件已{change_type_desc.get(change_type, change_type)}"]
            except Exception as e:
                self.logger.warning(f"生成变更摘要时出错: {str(e)}")
                change["summary"] = [f"文件已{change_type_desc.get(change_type, change_type)}"]
            
            # 添加diff内容预览
            if not stat.get("is_binary", False) and "diff_content" in stat:
                diff_content = stat.get("diff_content", "")
                if diff_content:
                    # 获取有意义的diff片段
                    change["diff_preview"] = self._extract_meaningful_diff_preview(diff_content)
            
            # 添加处理好的变更
            important_changes.append(change)
        
        return important_changes
    
    def __init__(self, repo_path: str = GIT_DEFAULT_REPO_PATH):
        """
        初始化Git分析器
        
        Args:
            repo_path: Git仓库路径，默认为当前目录
        
        Raises:
            ValueError: 如果指定的路径不是一个有效的Git仓库
        """
        try:
            self.repo = Repo(repo_path)
            if self.repo.bare:
                raise ValueError(f"裸仓库不支持: {repo_path}")
        except Exception as e:
            raise ValueError(f"{ERROR_GIT_REPO_NOT_FOUND.format(repo_path)}: {str(e)}")
        
        self.repo_path = repo_path
        self._diff_summary = None
        self.logger = logging.getLogger(__name__)
        
        # 加载配置，用于diff行数限制等设置
        from sf_ai_commit.config import ConfigManager
        self.config = ConfigManager().config
        
    def _extract_meaningful_diff_preview(self, diff_content: str) -> str:
        """
        从diff内容中提取有意义的预览
        
        Args:
            diff_content: 差异内容
            
        Returns:
            有意义的差异预览
        """
        if not diff_content:
            return ""
            
        # 从配置中获取显示行数设置
        max_lines = self.config.get("preferences", {}).get("diff_max_lines", 20)
            
        # 使用工具函数提取有意义的diff内容
        meaningful_lines = extract_meaningful_diff_content(diff_content, max_lines)
        return "\n".join(meaningful_lines)