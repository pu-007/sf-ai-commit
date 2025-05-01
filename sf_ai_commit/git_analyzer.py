"""
Git差异分析模块 - 负责分析Git仓库的变更
"""

import os
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
    
    def get_staged_diff(self) -> List[Diff]:
        """
        获取暂存区的差异对象列表
        
        Returns:
            包含暂存区变更的差异对象列表
            
        Raises:
            ValueError: 如果没有暂存的变更
        """
        # 获取索引(暂存区)和HEAD之间的差异
        diffs = self.repo.index.diff(self.repo.head.commit, staged=True)
        
        if not diffs:
            # 检查是否有未跟踪但已暂存的文件
            staged_untracked = [item for item in self.repo.index.diff("HEAD")]
            if not staged_untracked:
                raise ValueError(ERROR_GIT_NO_STAGED_CHANGES)
            return staged_untracked
            
        return list(diffs)
    
    def analyze_diff(self) -> Dict[str, Any]:
        """
        分析差异内容，提取有用信息
        
        Returns:
            包含差异分析结果的字典
        """
        try:
            diffs = self.get_staged_diff()
        except ValueError as e:
            logging.error(str(e))
            return {"error": str(e), "files": [], "summary": ""}
        
        files_stats = []
        total_insertions = 0
        total_deletions = 0
        
        # 分析每个变更的文件
        for diff in diffs:
            diff_stats = self._analyze_file_diff(diff)
            files_stats.append(diff_stats)
            
            total_insertions += diff_stats.get("insertions", 0)
            total_deletions += diff_stats.get("deletions", 0)
        
        # 整理汇总信息
        diff_summary = {
            "files": files_stats,
            "total_files": len(files_stats),
            "total_insertions": total_insertions,
            "total_deletions": total_deletions,
            "summary": self._generate_text_summary(files_stats, total_insertions, total_deletions)
        }
        
        self._diff_summary = diff_summary
        return diff_summary
    
    def _analyze_file_diff(self, diff: Diff) -> Dict[str, Any]:
        """
        分析单个文件的差异
        
        Args:
            diff: GitPython的Diff对象
            
        Returns:
            包含文件差异分析结果的字典
        """
        # 获取文件路径（a_path是变更前的路径，b_path是变更后的路径）
        file_path = diff.b_path or diff.a_path
        
        # 确定变更类型
        if diff.new_file:
            change_type = "added"
        elif diff.deleted_file:
            change_type = "deleted"
        elif diff.renamed:
            change_type = "renamed"
        else:
            change_type = "modified"
        
        # 获取差异统计信息
        insertions = 0
        deletions = 0
        
        try:
            # 对于文本文件，我们可以获取详细的差异内容
            diff_content = diff.diff.decode(GIT_DIFF_ENCODING)
            
            # 计算插入和删除的行数
            for line in diff_content.split('\n'):
                if line.startswith('+') and not line.startswith('+++'):
                    insertions += 1
                elif line.startswith('-') and not line.startswith('---'):
                    deletions += 1
        except (UnicodeDecodeError, AttributeError):
            # 对于二进制文件或其他无法解码的文件，我们只记录变更类型
            diff_content = "(binary file)"
        
        # 获取文件扩展名以识别文件类型
        _, file_ext = os.path.splitext(file_path)
        file_ext = file_ext.lstrip('.').lower() if file_ext else ""
        
        return {
            "path": file_path,
            "change_type": change_type,
            "insertions": insertions,
            "deletions": deletions,
            "extension": file_ext,
            "is_binary": diff.b_blob.binary if diff.b_blob else diff.a_blob.binary if diff.a_blob else False,
            "diff_content": diff_content
        }
    
    def _generate_text_summary(self, files_stats: List[Dict[str, Any]], 
                              total_insertions: int, total_deletions: int) -> str:
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
        summary_lines.append(f"变更统计: {len(files_stats)}个文件，+{total_insertions} -{total_deletions}")
        summary_lines.append("")
        
        # 按文件添加详细信息
        for file_stat in files_stats:
            path = file_stat["path"]
            change_type = file_stat["change_type"]
            insertions = file_stat.get("insertions", 0)
            deletions = file_stat.get("deletions", 0)
            
            # 构建文件变更描述
            if change_type == "added":
                change_desc = "新增"
            elif change_type == "deleted":
                change_desc = "删除"
            elif change_type == "renamed":
                change_desc = "重命名"
            else:
                change_desc = "修改"
                
            summary_lines.append(f"{change_desc}: {path} (+{insertions}, -{deletions})")
            
            # 如果是文本文件且有内容变更，添加简化的差异内容
            if not file_stat.get("is_binary") and "diff_content" in file_stat:
                diff_content = file_stat["diff_content"]
                # 仅保留少量行，避免摘要过长
                content_lines = diff_content.split('\n')[:20]  # 最多显示20行
                content_snippet = '\n'.join(content_lines)
                if len(content_lines) < len(diff_content.split('\n')):
                    content_snippet += "\n... (更多变更省略)"
                    
                summary_lines.append("```")
                summary_lines.append(content_snippet)
                summary_lines.append("```")
                
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
            # 执行提交
            commit = self.repo.index.commit(message)
            return commit.hexsha
        except GitCommandError as e:
            raise RuntimeError(f"提交失败: {str(e)}")
        
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
        }