"""
配置管理模块 - 处理配置的加载、解析和访问
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from sf_ai_commit.constants import (
    DEFAULT_CONFIG_DIR,
    DEFAULT_CONFIG_PATH,
    DEFAULT_LLM_HOST_URL,
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_TIMEOUT,
    DEFAULT_LLM_TEMPERATURE,
    DEFAULT_EDITOR,
    DEFAULT_PROMPT_TEMPLATE,
    DETAILED_PROMPT_EXTENSION,
    DEFAULT_MAX_MESSAGE_LENGTH,
    ERROR_CONFIG_NOT_FOUND,
    ERROR_CONFIG_INVALID,
)

class ConfigManager:
    """管理配置文件和默认配置"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置管理器
        
        Args:
            config_path: 可选的配置文件路径，如果为None则使用默认路径
        """
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self.config = self._get_default_config()
        self.load_config()
        
    def _get_default_config(self) -> Dict[str, Any]:
        """
        获取默认配置
        
        Returns:
            包含默认配置的字典
        """
        return {
            "llm": {
                "host_url": DEFAULT_LLM_HOST_URL,
                "model": DEFAULT_LLM_MODEL,
                "timeout": DEFAULT_LLM_TIMEOUT,
                "headers": {},
                "api_key": "",
                "temperature": DEFAULT_LLM_TEMPERATURE,
            },
            "prompts": {
                "default": DEFAULT_PROMPT_TEMPLATE,
                "detailed": DETAILED_PROMPT_EXTENSION,
            },
            "preferences": {
                "detailed_by_default": False,
                "max_message_length": DEFAULT_MAX_MESSAGE_LENGTH,
                "editor_command": DEFAULT_EDITOR,
                "diff_max_lines": 20,  # 显示的差异内容行数，0 表示全部显示
            },
            "git": {
                "diff_encoding": "utf-8",  # Git差异内容的编码
            }
        }
    
    def load_config(self) -> None:
        """
        加载配置文件
        
        如果配置文件存在，则加载并更新默认配置
        如果配置文件不存在，则使用默认配置
        """
        if not os.path.exists(self.config_path):
            logging.info(f"配置文件不存在: {self.config_path}，使用默认配置")
            return
            
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                user_config = yaml.safe_load(f)
                
            if user_config and isinstance(user_config, dict):
                # 深度合并配置
                self._merge_configs(self.config, user_config)
            else:
                logging.warning(f"配置文件为空或格式不正确: {self.config_path}")
        except Exception as e:
            logging.error(f"{ERROR_CONFIG_INVALID.format(str(e))}")
    
    def _merge_configs(self, default_config: Dict[str, Any], user_config: Dict[str, Any]) -> None:
        """
        深度合并配置字典
        
        Args:
            default_config: 默认配置字典（将被修改）
            user_config: 用户配置字典
        """
        for key, value in user_config.items():
            if (
                key in default_config and 
                isinstance(default_config[key], dict) and 
                isinstance(value, dict)
            ):
                self._merge_configs(default_config[key], value)
            else:
                default_config[key] = value
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """
        获取指定配置项
        
        Args:
            key: 配置项键名（使用点号分隔嵌套键）
            default: 如果键不存在时返回的默认值
            
        Returns:
            配置项的值或默认值
        """
        keys = key.split('.')
        value = self.config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    @property
    def llm_config(self) -> Dict[str, Any]:
        """
        获取LLM相关配置
        
        Returns:
            LLM配置字典
        """
        return self.config.get("llm", {})
    
    @property
    def prompt_template(self) -> str:
        """
        获取默认提示词模板
        
        Returns:
            提示词模板字符串
        """
        return self.config.get("prompts", {}).get("default", DEFAULT_PROMPT_TEMPLATE)
    
    @property
    def detailed_prompt(self) -> str:
        """
        获取详细提示词扩展
        
        Returns:
            详细提示词扩展字符串
        """
        return self.config.get("prompts", {}).get("detailed", DETAILED_PROMPT_EXTENSION)
    
    def create_default_config(self) -> bool:
        """
        创建默认配置文件
        
        如果配置文件目录不存在，则创建
        如果配置文件已存在，则不覆盖
        
        Returns:
            如果创建成功或文件已存在则返回True，否则返回False
        """
        if os.path.exists(self.config_path):
            logging.info(f"配置文件已存在: {self.config_path}")
            return True
            
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
                
            logging.info(f"已创建默认配置文件: {self.config_path}")
            return True
        except Exception as e:
            logging.error(f"创建配置文件失败: {str(e)}")
            return False