"""
LLM服务模块 - 负责与LLM API通信和处理响应
"""

import os
import json
import logging
import requests
from typing import Dict, Any, Optional, List

from sf_ai_commit.constants import (
    DEFAULT_LLM_HOST_URL,
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_TEMPERATURE,
    DEFAULT_LLM_TIMEOUT,
    DEFAULT_PROMPT_TEMPLATE,
    DETAILED_PROMPT_EXTENSION,
    VERBOSE_PROMPT_TEMPLATE,
    GIT_DEFAULT_DIFF_MAX_LINES,
    ERROR_LLM_CONNECTION,
    ERROR_LLM_RESPONSE
)
from sf_ai_commit.utils import extract_meaningful_diff_content, extract_meaningful_code_lines

class LLMService:
    """封装LLM API调用"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化LLM服务
        
        Args:
            config: LLM配置字典
        """
        # API 配置
        self.host_url = config.get("host_url", DEFAULT_LLM_HOST_URL)
        self.model = config.get("model", DEFAULT_LLM_MODEL)
        self.timeout = config.get("timeout", DEFAULT_LLM_TIMEOUT)
        self.temperature = config.get("temperature", DEFAULT_LLM_TEMPERATURE)
        
        # 认证配置 - 支持直接 API 密钥或自定义请求头
        self.headers = config.get("headers", {}).copy()  # 使用副本避免修改原始配置
        
        # 确保头信息中包含正确的 Content-Type
        if "Content-Type" not in self.headers:
            self.headers["Content-Type"] = "application/json"
        
        # API 密钥处理（优先从环境变量获取，然后从配置，最后回退到空字符串）
        self.api_key = os.environ.get("OPENAI_API_KEY",
                                      config.get("api_key", ""))
        
        # 如果有 API 密钥但没有授权头，自动添加 Bearer 授权
        if self.api_key and "Authorization" not in self.headers:
            self.headers["Authorization"] = f"Bearer {self.api_key}"
            
        # 加载全局配置，用于diff内容显示等设置
        from sf_ai_commit.config import ConfigManager
        self.config = ConfigManager().config
            
        logging.debug(f"LLM 模型配置: {self.model}, 服务地址: {self.host_url}")
            
    def generate_commit_message(self, diff_summary: Dict[str, Any], detailed: bool = False, verbose: bool = False) -> str:
        """
        生成提交消息
        
        Args:
            diff_summary: Git差异摘要
            detailed: 是否生成详细消息
            verbose: 是否输出详细的提示词信息
            
        Returns:
            生成的提交消息
            
        Raises:
            RuntimeError: 如果生成失败
        """
        prompt = self._prepare_prompt(diff_summary, detailed)
        
        # 如果启用了verbose模式，先输出提示词
        if verbose:
            verbose_output = VERBOSE_PROMPT_TEMPLATE.format(full_prompt=prompt)
            print(verbose_output)
        
        response = self._call_llm(prompt)
        
        if not response:
            raise RuntimeError(ERROR_LLM_RESPONSE)
            
        return response.strip()
    
    def _prepare_prompt(self, diff_summary: Dict[str, Any], detailed: bool) -> str:
        """
        准备提示词
        
        Args:
            diff_summary: Git差异摘要
            detailed: 是否生成详细消息
            
        Returns:
            格式化的提示词
        """
        # 获取变更梗概 - 提取增删改的文件类型、数量，结构化输出
        structured_overview = self._generate_structured_overview(diff_summary)
        
        # 获取重要变更信息 - 选择更改比较大的文件，处理同一文件的增删记录
        important_changes_text = self._generate_important_changes(diff_summary)
        
        # 提取主要文件差异详情 - 显示重要的diff区块原文
        diff_details = self._extract_diff_details(diff_summary)
        
        # 构建基础提示词
        prompt = DEFAULT_PROMPT_TEMPLATE.format(
            diff_summary=structured_overview,
            important_changes=important_changes_text,
            diff_details=diff_details
        )
        
        # 如果需要详细消息，添加详细提示词扩展
        if detailed:
            prompt += "\n" + DETAILED_PROMPT_EXTENSION
            
        return prompt
    
    def _generate_structured_overview(self, diff_summary: Dict[str, Any]) -> str:
        """
        生成结构化的变更概览，不依赖AI总结
        
        Args:
            diff_summary: Git差异摘要
            
        Returns:
            结构化的变更概览文本
        """
        overview_lines = []
        
        # 获取基本统计信息
        total_files = diff_summary.get("total_files", 0)
        stats = diff_summary.get("stats", {})
        insertions = stats.get("insertions", 0)
        deletions = stats.get("deletions", 0)
        
        # 添加总体统计
        overview_lines.append(f"变更概览: 共 {total_files} 个文件")
        overview_lines.append(f"代码变更: +{insertions} -{deletions} 行")
        
        # 按文件变更类型分组统计
        file_changes = stats.get("files", {})
        change_type_counts = {
            "added": len(file_changes.get("added", [])),
            "modified": len(file_changes.get("modified", [])),
            "deleted": len(file_changes.get("deleted", [])),
            "renamed": len(file_changes.get("renamed", [])),
            "moved": len(file_changes.get("moved", []))
        }
        
        # 添加文件变更类型统计
        change_type_desc = {
            "added": "新增",
            "modified": "修改",
            "deleted": "删除",
            "renamed": "重命名",
            "moved": "移动"
        }
        
        change_summary = []
        for change_type, count in change_type_counts.items():
            if count > 0:
                change_summary.append(f"{change_type_desc.get(change_type, change_type)}: {count}个")
        
        if change_summary:
            overview_lines.append("文件变更: " + ", ".join(change_summary))
        
        # 按文件类型分组
        by_type = stats.get("by_type", {})
        if by_type:
            overview_lines.append("\n按文件类型统计:")
            for file_type, type_stats in by_type.items():
                count = len(type_stats.get("files", []))
                type_insertions = type_stats.get("insertions", 0)
                type_deletions = type_stats.get("deletions", 0)
                overview_lines.append(f"- {file_type}: {count}个文件 (+{type_insertions} -{type_deletions})")
        
        return "\n".join(overview_lines)
        
    def _generate_important_changes(self, diff_summary: Dict[str, Any]) -> str:
        """
        生成重要变更列表，选择更改比较大的文件，并处理同一文件的增删记录
        
        Args:
            diff_summary: Git差异摘要
            
        Returns:
            重要变更文本
        """
        important_changes_list = diff_summary.get("important_changes", [])
        
        # 如果没有重要变更
        if not important_changes_list or not isinstance(important_changes_list, list):
            return "没有检测到重要变更"
        
        # 用字典来合并相同文件的变更，只保留最终状态
        changes_by_file = {}
        for change in important_changes_list:
            if not isinstance(change, dict):
                continue
                
            path = change.get("path", "未知文件")
            change_type = change.get("change_type", "修改")
            summary = change.get("summary", [])
            impact_score = change.get("impact_score", 0)
            
            # 确保summary是列表
            if not isinstance(summary, list):
                summary = [str(summary)]
            
            # 如果文件已存在，保留最终状态
            if path in changes_by_file:
                # 根据变更类型确定最终状态
                existing_type = changes_by_file[path]["change_type"]
                # 如果当前是删除，但已有记录是新增，表示文件被新增后又删除，最终状态是不存在
                if change_type == "deleted" and existing_type == "added":
                    # 从跟踪中移除此文件
                    del changes_by_file[path]
                    continue
                # 如果当前是新增，但已有记录是删除，表示文件被删除后又新增，最终状态是修改
                elif change_type == "added" and existing_type == "deleted":
                    changes_by_file[path]["change_type"] = "modified"
                # 否则保留影响分数更高的变更
                elif impact_score > changes_by_file[path].get("impact_score", 0):
                    changes_by_file[path]["change_type"] = change_type
                    changes_by_file[path]["impact_score"] = impact_score
                
                # 合并摘要并去重
                existing_summary = changes_by_file[path]["summary"]
                new_summary = list(set(existing_summary + summary))
                changes_by_file[path]["summary"] = new_summary
            else:
                changes_by_file[path] = {
                    "change_type": change_type,
                    "summary": summary,
                    "impact_score": impact_score
                }
        
        # 按影响分数排序
        sorted_changes = sorted(
            [(path, info) for path, info in changes_by_file.items()],
            key=lambda x: x[1].get("impact_score", 0),
            reverse=True
        )
        
        # 格式化输出
        important_changes_items = []
        for i, (path, info) in enumerate(sorted_changes, 1):
            # 构建变更项描述
            change_type_desc = {
                "added": "新增",
                "modified": "修改",
                "deleted": "删除",
                "renamed": "重命名",
                "moved": "移动",
                "renamed_modified": "重命名并修改",
                "moved_modified": "移动并修改"
            }.get(info["change_type"], info["change_type"])
            
            change_desc = f"{i}. {path} ({change_type_desc})"
            if info["summary"]:
                # 使用短横线列表格式化summary
                summary_items = [f"- {item}" for item in info["summary"]]
                change_desc += "\n" + "\n".join(summary_items)
            important_changes_items.append(change_desc)
        
        return "\n".join(important_changes_items)
        
    def _analyze_changes_with_ai(self, diff_summary: Dict[str, Any]) -> Dict[str, str]:
        """
        使用AI生成提交消息（不再用于生成变更概述和重要变更）
        
        Args:
            diff_summary: Git差异摘要
            
        Returns:
            包含提交消息的字典
        """
        # 注意：由于我们不再使用AI来生成变更概述和重要变更，
        # 此函数只返回空字典，相关逻辑已移至 _generate_structured_overview
        # 和 _generate_important_changes 函数
        return {}
    
    def _extract_diff_details(self, diff_summary: Dict[str, Any]) -> str:
        """
        从差异摘要中提取主要文件的详细差异内容
        
        Args:
            diff_summary: Git差异摘要
            
        Returns:
            格式化的文件差异详情字符串
        """
        diff_details_lines = []
        
        # 获取文件列表
        files = diff_summary.get("files", [])
        
        # 如果没有文件，返回提示信息
        if not files:
            return "没有具体的文件差异信息可用"
        
        # 根据影响得分排序文件（如果可用）
        try:
            # 按影响程度排序，重要的文件在前面
            sorted_files = sorted(
                files,
                key=lambda x: x.get("impact_score", 0) if isinstance(x.get("impact_score"), (int, float)) else 0,
                reverse=True
            )
        except:
            # 如果排序失败，使用原始顺序
            sorted_files = files
        
        # 最多显示前3个文件的差异
        for file_index, file_stat in enumerate(sorted_files[:3]):
            # 获取文件路径和变更类型
            path = file_stat.get("path", "未知文件")
            change_type = file_stat.get("change_type", "修改")
            change_type_desc = {
                "added": "新增",
                "modified": "修改",
                "deleted": "删除",
                "renamed": "重命名",
                "moved": "移动",
                "renamed_modified": "重命名并修改",
                "moved_modified": "移动并修改"
            }.get(change_type, change_type)
            
            # 添加文件标题
            diff_details_lines.append(f"文件 {file_index+1}: {path} ({change_type_desc})")
            
            # 添加差异统计
            insertions = file_stat.get("insertions", 0)
            deletions = file_stat.get("deletions", 0)
            diff_details_lines.append(f"变更: +{insertions} -{deletions} 行")
            
            # 添加具体的差异内容
            if not file_stat.get("is_binary", False) and "diff_content" in file_stat:
                diff_content = file_stat.get("diff_content", "")
                
                # 提取重要的diff区块，适当截断但保证信息足够
                diff_lines = self._extract_meaningful_diff_content(diff_content)
                
                if diff_content and diff_lines:
                    diff_details_lines.append("```diff")
                    diff_details_lines.extend(diff_lines)
                    if len(diff_content.split("\n")) > len(diff_lines):
                        diff_details_lines.append("... (内容已截断)")
                    diff_details_lines.append("```")
            elif "code_blocks" in file_stat and file_stat["code_blocks"]:
                # 如果有代码块，选择最重要的代码块
                code_blocks = file_stat["code_blocks"]
                if code_blocks:
                    # 选择最大的代码块或第一个代码块
                    selected_block = max(code_blocks, key=len) if len(code_blocks) > 1 else code_blocks[0]
                    if selected_block:
                        diff_details_lines.append("```")
                        # 限制代码块行数，但保留完整的变更信息
                        code_lines = selected_block.split("\n")
                        # 只选择包含变更（+ 或 -）的行及其上下文
                        meaningful_lines = self._extract_meaningful_code_lines(code_lines)
                        diff_details_lines.extend(meaningful_lines[:20])
                        if len(code_lines) > 20:
                            diff_details_lines.append("... (内容已截断)")
                        diff_details_lines.append("```")
            else:
                # 如果没有可用的差异内容
                diff_details_lines.append("(无可显示的差异内容)")
            
            # 文件之间添加分隔线
            if file_index < min(len(sorted_files), 3) - 1:
                diff_details_lines.append("\n---\n")
        
        return "\n".join(diff_details_lines)
    
    def _extract_meaningful_diff_content(self, diff_content: str) -> List[str]:
        """
        从diff内容中提取有意义的部分，适当截断但保留关键信息
        
        Args:
            diff_content: 原始diff内容
            
        Returns:
            有意义的diff行列表
        """
        # 获取配置的显示行数
        max_diff_lines = 20  # 默认值
        
        # 从配置中获取显示行数设置(如果在__init__中有加载config，可以使用self.config)
        if hasattr(self, 'config') and self.config and 'preferences' in self.config:
            max_diff_lines = self.config.get('preferences', {}).get('diff_max_lines', 20)
        
        # 使用工具函数提取有意义的diff内容
        return extract_meaningful_diff_content(diff_content, max_diff_lines)
    
    def _extract_meaningful_code_lines(self, code_lines: List[str]) -> List[str]:
        """
        从代码块中提取有意义的行
        
        Args:
            code_lines: 代码行列表
            
        Returns:
            有意义的代码行列表
        """
        # 获取配置的显示行数
        max_code_lines = 20  # 默认值
        
        # 从配置中获取显示行数设置(如果在__init__中有加载config，可以使用self.config)
        if hasattr(self, 'config') and self.config and 'preferences' in self.config:
            max_code_lines = self.config.get('preferences', {}).get('diff_max_lines', 20)
        
        # 使用工具函数提取有意义的代码行
        return extract_meaningful_code_lines(code_lines, max_code_lines)
    
    def _call_llm(self, prompt: str) -> str:
        """
        调用LLM API
        
        Args:
            prompt: 提示词文本
            
        Returns:
            LLM生成的响应文本
            
        Raises:
            RuntimeError: 如果API调用失败
        """
        # 构建请求体 - 使用 OpenAI 兼容格式
        request_body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "你是一个Git提交消息生成助手。请生成符合Conventional Commits规范的提交消息。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": self.temperature
        }
        
        try:
            logging.debug(f"发送请求到 LLM API: {self.host_url}")
            
            # 发送API请求
            response = requests.post(
                self.host_url,
                headers=self.headers,
                json=request_body,
                timeout=self.timeout
            )
            
            # 检查响应状态
            response.raise_for_status()
            
            # 解析响应内容
            response_data = response.json()
            
            # 提取生成的文本（按优先级尝试不同的响应格式）
            
            # 1. OpenAI/PocketFlow 兼容格式
            if "choices" in response_data and len(response_data["choices"]) > 0:
                message = response_data["choices"][0].get("message", {})
                content = message.get("content", "")
                if content:
                    return content
            
            # 2. 其他常见 API 响应格式
            for key in ["output", "content", "text", "response", "message"]:
                if key in response_data and response_data[key]:
                    return response_data[key]
            
            # 3. 嵌套结构尝试
            if "data" in response_data and isinstance(response_data["data"], dict):
                data = response_data["data"]
                for key in ["content", "text", "message"]:
                    if key in data and data[key]:
                        return data[key]
            
            # 如果找不到有效输出，则返回整个响应作为字符串
            logging.warning(f"无法从LLM响应中提取标准格式内容，返回原始响应")
            return str(response_data)
            
        except requests.exceptions.RequestException as e:
            # 处理网络或API错误
            error_msg = ERROR_LLM_CONNECTION.format(str(e))
            logging.error(error_msg)
            raise RuntimeError(error_msg)
        except (ValueError, KeyError, json.JSONDecodeError) as e:
            # 处理响应解析错误
            error_msg = f"解析LLM响应失败: {str(e)}"
            logging.error(error_msg)
            raise RuntimeError(error_msg)
