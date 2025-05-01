"""
Git差异分析模块 - 负责分析Git仓库的变更
"""

import os
import re
import logging
from typing import Dict, List, Any, Optional, Tuple
from git import Repo, GitCommandError
from git.diff import Diff

from sf_ai_commit.constants import (
    GIT_DIFF_ENCODING,
    GIT_DEFAULT_REPO_PATH,
    ERROR_GIT_REPO_NOT_FOUND,
    ERROR_GIT_NO_STAGED_CHANGES
)

def is_binary_string(content: bytes) -> bool:
    """
    判断内容是否是二进制字符串
    
    Args:
        content: 待检查的内容
        
    Returns:
        如果内容包含空字节或不可打印字符比例较高则返回True
    """
    # 检查是否包含空字节，这通常表明是二进制数据
    if b'\x00' in content:
        return True
        
    # 检查不可打印字符比例
    printable_chars = 0
    for byte in content:
        # ASCII 可打印字符范围大致为 32-126 加上 9(Tab)、10(LF)、13(CR)
        if (32 <= byte <= 126) or byte in (9, 10, 13):
            printable_chars += 1
    
    # 如果可打印字符少于75%，可能是二进制文件
    return printable_chars / len(content) < 0.75 if content else False

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
        
        # 获取索引(暂存区)和HEAD之间的差异
        if not is_empty:
            diffs = list(self.repo.index.diff(self.repo.head.commit, staged=True))
        else:
            # 首次提交，没有历史提交可比较
            diffs = []
            self.logger.debug("首次提交，没有历史差异可比较")
        
        # 检查未跟踪但已暂存的文件（新添加的文件）
        # 处理新添加的文件
        try:
            index_entries = self.repo.index.entries
            self.logger.debug(f"处理暂存区的新文件，共 {len(index_entries)} 个条目")
            
            # 设置 head_tree
            head_tree = None if is_empty else self.repo.head.commit.tree
            if is_empty:
                self.logger.debug("首次提交，没有 HEAD 引用")
            
            for entry in index_entries:
                path = entry[0]
                try:
                    # 检查文件是否在 HEAD 中存在
                    if head_tree is not None:
                        head_tree[path]
                        continue  # 如果存在则跳过，因为已经在 diff 中了
                except (KeyError, AttributeError):
                    pass  # 文件不在 HEAD 中，继续处理
                
                # 处理新文件
                try:
                    # 简化新文件处理逻辑，使用git命令获取差异而不是读取文件内容
                    self.logger.debug(f"处理新文件: {path}")
                    
                    # 使用git show获取新文件内容和差异信息
                    try:
                        # 使用git diff --cached 获取暂存区的差异
                        diff_output = self.repo.git.diff("--cached", "--", path, no_prefix=False)
                        
                        # 如果diff输出为空（对于新文件可能发生），使用简单格式构建差异信息
                        if not diff_output:
                            # 检查文件是否是二进制文件
                            is_binary = False
                            try:
                                # 使用git命令检查是否是二进制文件
                                self.repo.git.check_attr("binary", "--", path)
                                is_binary = True
                            except:
                                pass
                                
                            if is_binary:
                                diff_output = f"diff --git a/{path} b/{path}\nnew file mode 100644\nBinary files /dev/null and b/{path} differ\n"
                            else:
                                diff_output = f"diff --git a/{path} b/{path}\nnew file mode 100644\n"
                        
                        # 创建模拟的 Diff 对象
                        mock_diff = type('MockDiff', (), {
                            'a_path': path,
                            'b_path': path,
                            'new_file': True,
                            'renamed': False,
                            'deleted_file': False,
                            'diff': diff_output.encode(GIT_DIFF_ENCODING) if isinstance(diff_output, str) else diff_output,
                            'change_type': 'added'
                        })
                        diffs.append(mock_diff)
                    except Exception as e:
                        self.logger.warning(f"获取新文件 {path} 的差异时出错: {str(e)}")
                    else:
                        # 首次提交的情况
                        self.logger.debug(f"处理首次提交的新文件: {path}")
                        
                        # 直接获取文件内容
                        try:
                            # 获取文件内容
                            file_path = os.path.join(self.repo_path, path)
                            
                            # 使用file命令检查文件类型
                            import subprocess
                            file_type_output = subprocess.check_output(['file', '-b', file_path], universal_newlines=True)
                            is_binary = 'text' not in file_type_output.lower()
                            
                            # 创建适当的差异内容
                            if is_binary:
                                diff_content = f'diff --git a/{path} b/{path}\nnew file mode 100644\nBinary files /dev/null and b/{path} differ\n'
                            else:
                                # 使用git命令生成差异内容
                                try:
                                    # 使用cat-file命令获取blob内容
                                    blob_id = self.repo.index[path].hexsha
                                    blob_content = self.repo.git.cat_file("blob", blob_id)
                                    
                                    # 创建差异输出
                                    lines = blob_content.splitlines()
                                    diff_content = f'diff --git a/{path} b/{path}\nnew file mode 100644\n--- /dev/null\n+++ b/{path}\n@@ -0,0 +1,{len(lines)} @@\n'
                                    for line in lines:
                                        diff_content += f'+{line}\n'
                                except Exception as e:
                                    self.logger.debug(f"使用git方式获取内容失败: {str(e)}")
                                    # 如果git方式失败，使用直接读取文件的备选方案
                                    with open(file_path, 'r', encoding=GIT_DIFF_ENCODING, errors='replace') as f:
                                        file_content = f.read()
                                    
                                    lines = file_content.splitlines()
                                    diff_content = f'diff --git a/{path} b/{path}\nnew file mode 100644\n--- /dev/null\n+++ b/{path}\n@@ -0,0 +1,{len(lines)} @@\n'
                                    for line in lines:
                                        diff_content += f'+{line}\n'
                            
                            # 创建一个模拟的 Diff 对象
                            mock_diff = type('MockDiff', (), {
                                'a_path': path,
                                'b_path': path,
                                'new_file': True,
                                'renamed': False,
                                'deleted_file': False,
                                'diff': diff_content.encode(GIT_DIFF_ENCODING) if isinstance(diff_content, str) else diff_content,
                                'change_type': 'added'
                            })
                            diffs.append(mock_diff)
                        except Exception as e:
                            self.logger.warning(f"处理首次提交的新文件 {path} 时出错: {str(e)}")
                except Exception as e:
                    self.logger.warning(f"处理新文件 {path} 时出错: {str(e)}")
        except Exception as e:
            self.logger.warning(f"处理新文件时出错: {str(e)}")
        
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
        
        is_binary = False
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
                        diff_content = diff.diff.decode(GIT_DIFF_ENCODING)
                    else:
                        # 使用str()处理其他类型
                        diff_content = str(diff.diff)
                        
                    # 分析差异内容获取统计和代码块
                    stats, code_blocks = self._analyze_diff_content(diff_content)
                except Exception as e:
                    self.logger.debug(f"无法解码文件差异内容: {str(e)}")
                    diff_content = "(binary file or decode error)"
                    is_binary = True
        except Exception as e:
            self.logger.warning(f"分析差异内容时出错: {str(e)}")
        
        # 检查文件内容以确定是否是二进制文件 - 使用安全访问
        if not is_binary:
            try:
                b_blob = getattr(diff, 'b_blob', None)
                a_blob = getattr(diff, 'a_blob', None)
                blob = b_blob if b_blob else a_blob
                
                if blob and hasattr(blob, 'data_stream'):
                    try:
                        # 读取文件的前8KB来判断是否为二进制文件
                        content_sample = blob.data_stream.read(8192)
                        is_binary = is_binary_string(content_sample)
                        # 需要重置流以供后续使用
                        blob.data_stream.close()
                    except Exception as e:
                        self.logger.debug(f"读取文件内容时出错: {str(e)}")
                        is_binary = True
            except Exception as e:
                self.logger.debug(f"判断文件类型时出错: {str(e)}")
                is_binary = True
        
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
        生成差异的文本摘要
        
        Args:
            files_stats: 文件变更统计信息列表
            total_insertions: 总插入行数
            total_deletions: 总删除行数
            
        Returns:
            差异的文本摘要
        """
        summary_lines = []
        
        # 添加总体统计信息
        total_files = len(files_stats)
        insertions = total_stats["insertions"]
        deletions = total_stats["deletions"]
        
        summary_lines.append(f"变更概览: 共 {total_files} 个文件")
        summary_lines.append(f"代码变更: +{insertions} -{deletions} 行")
        
        # 按文件类型分组显示变更
        summary_lines.append("\n按文件类型统计:")
        for file_type, type_stats in total_stats["by_type"].items():
            count = len(type_stats["files"])
            type_insertions = type_stats["insertions"]
            type_deletions = type_stats["deletions"]
            summary_lines.append(f"- {file_type}: {count}个文件 (+{type_insertions} -{type_deletions})")
        
        # 显示重要变更
        if total_stats["files"]["renamed"] or total_stats["files"]["moved"]:
            summary_lines.append("\n文件重命名/移动:")
            for file_info in total_stats["files"]["renamed"] + total_stats["files"]["moved"]:
                summary_lines.append(f"- {file_info['path']}")
        
        # 按变更类型显示文件
        change_type_desc = {
            "added": "新增",
            "modified": "修改",
            "deleted": "删除",
            "renamed": "重命名",
            "moved": "移动",
            "renamed_modified": "重命名并修改",
            "moved_modified": "移动并修改"
        }
        
        # 获取最重要的变更
        important_files = sorted(
            [f for f in files_stats if f["change_type"] != "deleted"],
            key=lambda x: self._calculate_impact_score(x),
            reverse=True
        )[:5]  # 最多显示5个重要变更
        
        if important_files:
            summary_lines.append("\n重要变更:")
            for file_stat in important_files:
                path = file_stat["path"]
                change_type = change_type_desc.get(file_stat["change_type"], "修改")
                insertions = file_stat.get("insertions", 0)
                deletions = file_stat.get("deletions", 0)
                
                summary_lines.append(f"- {change_type}: {path} (+{insertions} -{deletions})")
                
                # 对于重要变更，显示关键代码块
                if not file_stat.get("is_binary") and file_stat.get("code_blocks"):
                    significant_blocks = self._get_significant_blocks(file_stat["code_blocks"])
                    if significant_blocks:
                        summary_lines.append("  主要变更:")
                        for block in significant_blocks:
                            summary_lines.append("  ```")
                            # 只显示每个代码块的前几行
                            block_preview = "\n  ".join(block.split("\n")[:5])
                            if len(block.split("\n")) > 5:
                                block_preview += "\n  ..."
                            summary_lines.append("  " + block_preview)
                            summary_lines.append("  ```")
                
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
        stats = {
            "insertions": 0,
            "deletions": 0,
            "modifications": 0
        }
        
        current_block = []
        code_blocks = []
        in_header = True
        
        for line in diff_content.split('\n'):
            # 跳过diff头部信息
            if in_header:
                if line.startswith('+++') or line.startswith('---'):
                    continue
                if line.startswith('@@'):
                    in_header = False
                continue
            
            # 统计变更
            if line.startswith('+') and not line.startswith('+++'):
                stats["insertions"] += 1
                current_block.append(line)
            elif line.startswith('-') and not line.startswith('---'):
                stats["deletions"] += 1
                current_block.append(line)
            elif line.startswith('@@'):
                # 新的代码块开始
                if current_block:
                    code_blocks.append('\n'.join(current_block))
                    current_block = []
            else:
                # 上下文行
                if current_block:
                    current_block.append(line)
        
        # 添加最后一个代码块
        if current_block:
            code_blocks.append('\n'.join(current_block))
        
        stats["modifications"] = min(stats["insertions"], stats["deletions"])
        
        return stats, code_blocks
        
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
        summary = []
        path = file_stat.get("path", "")
        extension = file_stat.get("extension", "").lower()
        
        # 根据文件路径和扩展名识别文件类型和用途
        if path.lower() == ".gitignore":
            summary.append("添加 Git 忽略规则文件")
            summary.append("配置了需要 Git 忽略的文件类型和目录")
        elif path.lower() in ["readme.md", "readme"]:
            summary.append("添加项目说明文档")
            summary.append("包含项目概述、安装和使用说明")
        elif path.lower() in ["license", "license.md", "license.txt"]:
            summary.append("添加开源许可证文件")
        elif extension == "py":
            summary.append("添加 Python 源代码文件")
            # 尝试识别文件内容特征
            if not file_stat.get("is_binary") and file_stat.get("diff_content"):
                content = file_stat.get("diff_content", "")
                if "class " in content:
                    summary.append("定义了新的类")
                if "def " in content:
                    summary.append("实现了新的函数/方法")
                if "import " in content or "from " in content:
                    summary.append("引入了依赖模块")
                if "test" in path.lower() or "test" in content.lower():
                    summary.append("增加了测试用例")
        elif extension in ["js", "ts", "jsx", "tsx"]:
            summary.append(f"添加 {'TypeScript' if extension in ['ts', 'tsx'] else 'JavaScript'} 源代码文件")
            if "react" in path.lower() or "component" in path.lower():
                summary.append("实现了新的界面组件")
        elif extension in ["html", "css", "scss", "sass"]:
            summary.append(f"添加 {extension.upper()} 文件")
            summary.append("更新了网页界面样式/结构")
        elif extension in ["json", "yaml", "yml", "toml", "xml"]:
            summary.append(f"添加 {extension.upper()} 配置文件")
        elif extension in ["md", "rst", "txt"]:
            summary.append("添加文档文件")
        elif extension in ["sh", "bash", "ps1", "bat", "cmd"]:
            summary.append("添加脚本文件")
        
        # 如果没有识别出特定类型
        if not summary:
            if file_stat.get("is_binary"):
                summary.append(f"添加二进制文件: {path}")
            else:
                summary.append(f"添加新文件: {path}")
        
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
        
        # 添加变更描述
        if file_stat.get("change_type") in ["renamed", "moved"]:
            summary.append("文件位置发生变化")
        
        if file_stat.get("insertions") or file_stat.get("deletions"):
            summary.append(
                f"修改了 {file_stat.get('insertions', 0) + file_stat.get('deletions', 0)} 行代码"
            )
        
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
        识别重要的变更
        
        Args:
            files_stats: 文件变更统计信息列表
            
        Returns:
            重要变更列表，每个元素包含变更路径、类型、影响分数和摘要
        """
        # 防御性编程：确保返回有效列表
        if not files_stats or not isinstance(files_stats, list):
            self.logger.warning(f"无效的文件变更统计信息: {type(files_stats)}")
            return []
            
        # 安全地排序文件变更
        try:
            # 过滤确保每个项都是有效的字典，并包含必要的路径信息
            valid_stats = []
            for stat in files_stats:
                if isinstance(stat, dict) and stat.get("path"):
                    valid_stats.append(stat)
                else:
                    self.logger.warning(f"跳过无效的文件统计信息: {stat}")
            
            # 排序有效的文件统计
            if valid_stats:
                sorted_stats = sorted(
                    valid_stats,
                    key=lambda x: self._calculate_impact_score(x),
                    reverse=True
                )
            else:
                self.logger.warning("没有找到有效的文件变更统计信息")
                return []
        except Exception as e:
            self.logger.warning(f"排序文件变更时出错: {str(e)}")
            # 如果排序失败，尝试使用原始列表中的有效项
            sorted_stats = [stat for stat in files_stats if isinstance(stat, dict) and stat.get("path")]
            if not sorted_stats:
                return []
        
        important_changes = []
        for stat in sorted_stats[:5]:  # 最多返回5个重要变更
            try:
                # 安全处理每个变更
                change = {
                    "path": stat.get("path", "unknown"),
                    "change_type": stat.get("change_type", "modified"),
                    "impact_score": self._calculate_impact_score(stat),
                }
                
                # 确保每个变更都有摘要信息
                try:
                    # 为不同类型的变更生成适当的摘要
                    if stat.get("change_type") == "added":
                        change["summary"] = self._extract_new_file_summary(stat)
                    else:
                        change["summary"] = self._extract_change_summary(stat)
                except Exception as e:
                    self.logger.warning(f"生成变更摘要时出错: {str(e)}")
                    # 确保即使摘要生成失败，也有一个空的摘要列表
                    change["summary"] = ["文件已变更"]
                
                # 安全添加代码块预览
                try:
                    if not stat.get("is_binary") and stat.get("code_blocks"):
                        code_blocks = stat.get("code_blocks", [])
                        if isinstance(code_blocks, list) and code_blocks:
                            significant_blocks = self._get_significant_blocks(code_blocks, max_blocks=2)
                            if significant_blocks:
                                change["code_preview"] = significant_blocks
                except Exception as e:
                    self.logger.warning(f"处理代码块时出错: {str(e)}")
                
                # 添加处理好的变更
                important_changes.append(change)
            except Exception as e:
                self.logger.warning(f"处理重要变更时出错: {str(e)}")
                # 添加基本信息而不失败
                important_changes.append({
                    "path": stat.get("path", "unknown"),
                    "change_type": stat.get("change_type", "unknown"),
                    "impact_score": 0.5,
                    "summary": []
                })
        
        return important_changes