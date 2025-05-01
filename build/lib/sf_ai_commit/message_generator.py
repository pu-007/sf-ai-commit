"""
消息生成器模块 - 负责生成和格式化符合Conventional Commits的消息
"""

import re
import logging
from typing import Dict, Any, Tuple, Optional

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
        pass
        
    def format_message(self, llm_response: str, detailed: bool = False) -> str:
        """
        格式化LLM响应为标准格式
        
        Args:
            llm_response: LLM生成的原始响应
            detailed: 是否需要详细消息
            
        Returns:
            格式化后的提交消息
        """
        # 移除前后空白
        message = llm_response.strip()
        
        # 如果消息为空，返回默认消息
        if not message:
            return "chore: update files"
            
        # 分割消息行
        lines = message.split('\n')
        first_line = lines[0].strip()
        
        # 确保第一行符合Conventional Commits格式
        if not self._is_conventional_format(first_line):
            first_line = self.ensure_conventional_format(first_line)
            
        # 如果不需要详细消息或只有一行，直接返回格式化的第一行
        if not detailed or len(lines) <= 1:
            return first_line
            
        # 处理详细消息体
        message_body = []
        
        # 跳过第一行，处理剩余内容作为消息体
        body_started = False
        for line in lines[1:]:
            line = line.strip()
            
            # 跳过空行，直到找到第一个非空行
            if not body_started and not line:
                continue
                
            body_started = True
            message_body.append(line)
        
        # 确保主题行和消息体之间有空行
        formatted_message = first_line
        if message_body:
            formatted_message += "\n\n" + "\n".join(message_body)
            
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
    
    def _infer_type_from_content(self, message: str) -> str:
        """
        从消息内容推断类型
        
        Args:
            message: 提交消息
            
        Returns:
            推断的类型
        """
        lower_message = message.lower()
        
        # 关键词映射到类型
        keyword_mapping = {
            "fix": ["fix", "bug", "issue", "error", "problem", "修复", "错误", "问题"],
            "feat": ["feat", "feature", "add", "new", "implement", "功能", "新增", "实现"],
            "docs": ["doc", "docs", "document", "documentation", "comment", "文档", "注释"],
            "style": ["style", "format", "lint", "样式", "格式"],
            "refactor": ["refactor", "restructure", "clean", "重构", "优化", "调整"],
            "perf": ["perf", "performance", "optimize", "fast", "性能", "优化", "加速"],
            "test": ["test", "spec", "测试"],
            "build": ["build", "package", "构建", "打包"],
            "ci": ["ci", "continuous", "integration", "pipeline", "workflow", "持续集成"],
            "chore": ["chore", "misc", "杂项", "其他"]
        }
        
        # 检查每种类型的关键词
        for type_key, keywords in keyword_mapping.items():
            for keyword in keywords:
                if keyword in lower_message:
                    return type_key
        
        # 默认类型
        return "chore"