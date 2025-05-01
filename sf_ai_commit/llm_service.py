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
    ERROR_LLM_CONNECTION,
    ERROR_LLM_RESPONSE
)

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
            
        logging.debug(f"LLM 模型配置: {self.model}, 服务地址: {self.host_url}")
            
    def generate_commit_message(self, diff_summary: Dict[str, Any], detailed: bool = False) -> str:
        """
        生成提交消息
        
        Args:
            diff_summary: Git差异摘要
            detailed: 是否生成详细消息
            
        Returns:
            生成的提交消息
            
        Raises:
            RuntimeError: 如果生成失败
        """
        prompt = self._prepare_prompt(diff_summary, detailed)
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
        # 获取差异摘要文本
        diff_text = diff_summary.get("summary", "")
        
        # 获取重要变更信息，如果不存在则使用空字符串
        important_changes_list = diff_summary.get("important_changes", [])
        
        # 将重要变更列表转换为字符串格式
        if important_changes_list and isinstance(important_changes_list, list):
            important_changes_items = []
            for change in important_changes_list:
                if isinstance(change, dict):
                    path = change.get("path", "未知文件")
                    change_type = change.get("change_type", "修改")
                    summary = change.get("summary", [])
                    
                    # 确保summary是列表
                    if not isinstance(summary, list):
                        summary = [str(summary)]
                    
                    # 构建变更项描述
                    change_desc = f"- {path} ({change_type}):"
                    if summary:
                        change_desc += "\n  " + "\n  ".join(summary)
                    important_changes_items.append(change_desc)
                else:
                    important_changes_items.append(f"- {str(change)}")
            
            important_changes_text = "\n".join(important_changes_items)
        else:
            important_changes_text = "没有检测到重要变更"
        
        # 构建基础提示词
        prompt = DEFAULT_PROMPT_TEMPLATE.format(
            diff_summary=diff_text,
            important_changes=important_changes_text
        )
        
        # 如果需要详细消息，添加详细提示词扩展
        if detailed:
            prompt += "\n" + DETAILED_PROMPT_EXTENSION
            
        return prompt
    
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