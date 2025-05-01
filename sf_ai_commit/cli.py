"""
CLI入口模块 - 提供命令行接口和主程序流程
"""

import os
import sys
import argparse
import logging
from typing import Dict, Any, List, Optional, Tuple, Sequence

from sf_ai_commit import __version__
from sf_ai_commit.config import ConfigManager
from sf_ai_commit.git_analyzer import GitAnalyzer
from sf_ai_commit.llm_service import LLMService
from sf_ai_commit.message_generator import MessageGenerator
from sf_ai_commit.interaction import InteractionManager
from sf_ai_commit.utils import setup_logging

class SFAICommit:
    """主程序入口类，协调各模块工作"""
    
    def __init__(self, args: Optional[List[str]] = None):
        """
        初始化程序
        
        Args:
            args: 命令行参数，如果为None则使用sys.argv
        """
        # 解析命令行参数
        self.args = self.parse_args(args)
        
        # 设置日志级别
        log_level = logging.DEBUG if self.args.verbose else logging.INFO
        setup_logging(log_level)
        
        # 初始化配置管理器
        self.config_manager = ConfigManager(self.args.config)
        
        # 如果指定了初始化配置选项，创建配置文件并退出
        if self.args.init:
            success = self.config_manager.create_default_config()
            if success:
                print(f"已创建默认配置文件: {self.config_manager.config_path}")
            else:
                print(f"创建配置文件失败")
            sys.exit(0 if success else 1)
            
        # 初始化交互管理器
        self.interaction = InteractionManager(no_color=self.args.no_color)
        
        # 其他组件将在需要时初始化，以避免在不必要的情况下创建对象
        self.git_analyzer = None
        self.llm_service = None
        self.message_generator = None
        
    def run(self) -> int:
        """
        主执行函数，协调整个工作流程
        
        Returns:
            退出码，0表示成功，非0表示失败
        """
        try:
            # 显示版本信息并退出
            if self.args.version:
                self.interaction.show_info(f"sf-ai-commit 版本 {__version__}")
                return 0
                
            # 初始化Git分析器
            try:
                self.git_analyzer = GitAnalyzer(self.args.repo_path)
            except ValueError as e:
                self.interaction.show_error(str(e))
                return 1
                
            # 处理指定的文件/文件夹
            if self.args.files:
                try:
                    with self.interaction.show_loading(f"正在添加指定的文件到暂存区..."):
                        self.git_analyzer.stage_files(self.args.files)
                except Exception as e:
                    self.interaction.show_error(f"添加文件到暂存区失败: {str(e)}")
                    return 1
            
            # 获取Git差异
            try:
                with self.interaction.show_loading("正在分析Git变更..."):
                    diff_summary = self.git_analyzer.analyze_diff()
                    
                if "error" in diff_summary:
                    self.interaction.show_error(diff_summary["error"])
                    return 1
                    
                if diff_summary["total_files"] == 0:
                    self.interaction.show_error("没有暂存的变更，请先使用 'git add' 添加变更或使用 sf-ai-commit [文件路径...] 指定文件")
                    return 1
            except Exception as e:
                self.interaction.show_error(f"分析Git变更失败: {str(e)}")
                logging.exception("Git分析错误详情")
                return 1
                
            # 初始化LLM服务
            self.llm_service = LLMService(self.config_manager.llm_config)
            
            # 初始化消息生成器
            self.message_generator = MessageGenerator()
            
            # 生成提交消息
            should_regenerate = True
            while should_regenerate:
                # 确定是否生成详细消息
                detailed = self.args.detailed
                
                try:
                    with self.interaction.show_loading("正在生成提交消息..."):
                        llm_response = self.llm_service.generate_commit_message(
                            diff_summary,
                            detailed=detailed,
                            verbose=self.args.verbose  # 添加verbose参数
                        )
                        
                    # 格式化提交消息
                    commit_message = self.message_generator.format_message(
                        llm_response,
                        diff_info=diff_summary,
                        detailed=detailed
                    )
                    
                    # 用户确认
                    confirmed, edited_message, regenerate = self.interaction.confirm_message(commit_message)
                    
                    if regenerate:
                        #TODO: 用户附加要求然后重新生成
                        should_regenerate = True
                        continue
                    elif not confirmed:
                        self.interaction.show_info("已取消提交")
                        return 0
                    else:
                        #TODO: 编辑后到选择界面，选择是否根据这个重新生成
                        # 使用编辑后的消息
                        commit_message = edited_message
                        should_regenerate = False
                        
                except Exception as e:
                    error_msg = str(e)
                    self.interaction.show_error(f"生成提交消息失败: {error_msg}")
                    # 添加更具体的错误提示
                    if "important_changes" in error_msg:
                        self.interaction.show_info("解析变更信息时出错，尝试重新分析...")
                        try:
                            # 再次尝试生成提交消息，使用兜底方案
                            with self.interaction.show_loading("重新尝试生成提交消息..."):
                                # 创建一个简单的差异摘要用于兜底
                                simple_diff = {
                                    "files": diff_summary.get("files", []),
                                    "total_files": diff_summary.get("total_files", 0),
                                    "important_changes": [],  # 使用空的重要变更列表
                                    "stats": diff_summary.get("stats", {}),
                                    "repo_info": diff_summary.get("repo_info", {})
                                }
                                
                                # 尝试使用简化的差异信息生成提交消息
                                llm_response = self.llm_service.generate_commit_message(
                                    simple_diff,
                                    detailed=False,
                                    verbose=self.args.verbose  # 添加verbose参数
                                )
                                
                                # 格式化提交消息
                                commit_message = self.message_generator.format_message(
                                    llm_response,
                                    diff_info=simple_diff,
                                    detailed=False
                                )
                                
                                # 用户确认
                                confirmed, edited_message, regenerate = self.interaction.confirm_message(commit_message)
                                
                                if regenerate:
                                    should_regenerate = True
                                    continue
                                elif not confirmed:
                                    self.interaction.show_info("已取消提交")
                                    return 0
                                else:
                                    # 使用编辑后的消息
                                    commit_message = edited_message
                                    should_regenerate = False
                            
                        except Exception as backup_error:
                            self.interaction.show_error(f"兜底方案也失败了: {str(backup_error)}")
                            logging.exception("兜底生成提交消息失败")
                            should_regenerate = False
                            return 1
                    else:
                        should_regenerate = False
                        return 1
            
            # 执行提交
            if not self.args.dry_run:
                try:
                    with self.interaction.show_loading("正在提交变更..."):
                        commit_hash = self.git_analyzer.commit(commit_message)
                    
                    self.interaction.show_success(f"成功提交: {commit_hash[:8]}")
                except Exception as e:
                    self.interaction.show_error(f"提交失败: {str(e)}")
                    return 1
            else:
                self.interaction.show_info("干运行模式，未执行实际提交")
                
            return 0
                
        except KeyboardInterrupt:
            self.interaction.show_info("\n已取消操作")
            return 130  # SIGINT的标准退出码
        except Exception as e:
            self.interaction.show_error(f"发生错误: {str(e)}")
            logging.exception("未处理的异常")
            return 1
            
    def parse_args(self, args: Optional[Sequence[str]] = None) -> argparse.Namespace:
        """
        解析命令行参数
        
        Args:
            args: 命令行参数，如果为None则使用sys.argv
            
        Returns:
            解析后的参数对象
        """
        parser = argparse.ArgumentParser(
            description="sf-ai-commit: 使用AI生成Git提交消息",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
        
        parser.add_argument("-v", "--version", action="store_true", help="显示版本信息并退出")
        parser.add_argument("-d", "--detailed", action="store_true", help="生成详细的提交消息")
        parser.add_argument("-c", "--config", help="指定配置文件路径")
        parser.add_argument("--init", action="store_true", help="创建默认配置文件")
        parser.add_argument("--no-color", action="store_true", help="禁用彩色输出")
        parser.add_argument("--dry-run", action="store_true", help="只生成消息但不实际提交")
        parser.add_argument("--verbose", action="store_true", help="显示详细日志和提示词信息")
        parser.add_argument("--repo-path", default=".", help="Git仓库路径")
        parser.add_argument("files", nargs="*", help="要添加到暂存区的文件或文件夹路径")
        
        return parser.parse_args(args)

def main() -> int:
    """
    命令行入口函数
    
    Returns:
        退出码
    """
    app = SFAICommit()
    return app.run()

if __name__ == "__main__":
    sys.exit(main())