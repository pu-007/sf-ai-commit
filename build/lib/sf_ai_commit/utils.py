"""
工具类模块 - 提供通用的辅助函数
"""

import os
import re
import sys
import logging
import tempfile
from typing import Dict, Any, List, Optional, Tuple

def setup_logging(level: int = logging.INFO) -> None:
    """
    设置日志记录
    
    Args:
        level: 日志级别
    """
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def truncate_text(text: str, max_length: int, append_ellipsis: bool = True) -> str:
    """
    截断文本到指定长度
    
    Args:
        text: 要截断的文本
        max_length: 最大长度
        append_ellipsis: 是否添加省略号
        
    Returns:
        截断后的文本
    """
    if len(text) <= max_length:
        return text
        
    truncated = text[:max_length]
    
    # 尝试在单词边界截断
    last_space = truncated.rfind(' ')
    if last_space > max_length * 0.8:  # 如果最后的空格位置在80%以后，在空格处截断
        truncated = truncated[:last_space]
        
    if append_ellipsis:
        truncated += "..."
        
    return truncated

def format_diff_stats(insertions: int, deletions: int) -> str:
    """
    格式化差异统计
    
    Args:
        insertions: 插入行数
        deletions: 删除行数
        
    Returns:
        格式化的统计字符串
    """
    stats = []
    
    if insertions:
        stats.append(f"+{insertions}")
        
    if deletions:
        stats.append(f"-{deletions}")
        
    return ", ".join(stats)

def validate_conventional_commit(message: str) -> Tuple[bool, Optional[str]]:
    """
    验证是否符合Conventional Commits格式
    
    Args:
        message: 提交消息
        
    Returns:
        元组(是否有效, 错误信息)
    """
    # Conventional Commits的基本格式
    pattern = r"^([\w]+)(\([\w\-\.]+\))?!?: (.+)$"
    
    # 有效的类型列表
    valid_types = [
        "feat", "fix", "docs", "style", "refactor", 
        "perf", "test", "build", "ci", "chore"
    ]
    
    # 检查格式
    match = re.match(pattern, message.split('\n')[0])
    if not match:
        return (False, "消息不符合Conventional Commits格式")
        
    # 检查类型
    commit_type = match.group(1)
    if commit_type not in valid_types:
        return (False, f"无效的提交类型: {commit_type}")
        
    # 检查描述
    description = match.group(3)
    if not description:
        return (False, "缺少提交描述")
        
    # 检查描述长度
    if len(description) > 100:
        return (False, "提交描述过长（超过100个字符）")
        
    return (True, None)

def ensure_dir_exists(path: str) -> None:
    """
    确保目录存在
    
    Args:
        path: 目录路径
    """
    os.makedirs(path, exist_ok=True)

def write_temp_file(content: str, suffix: str = ".txt") -> str:
    """
    写入临时文件
    
    Args:
        content: 文件内容
        suffix: 文件后缀
        
    Returns:
        临时文件路径
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False) as temp:
        temp.write(content)
        return temp.name

def read_file(file_path: str) -> str:
    """
    读取文件内容
    
    Args:
        file_path: 文件路径
        
    Returns:
        文件内容
        
    Raises:
        FileNotFoundError: 如果文件不存在
        IOError: 如果读取失败
    """
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

def write_file(file_path: str, content: str) -> None:
    """
    写入文件内容
    
    Args:
        file_path: 文件路径
        content: 文件内容
        
    Raises:
        IOError: 如果写入失败
    """
    # 确保目录存在
    dir_name = os.path.dirname(file_path)
    if dir_name:
        ensure_dir_exists(dir_name)
        
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

def is_binary_file(file_path: str) -> bool:
    """
    检查文件是否为二进制文件
    
    Args:
        file_path: 文件路径
        
    Returns:
        如果是二进制文件则为True，否则为False
    """
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(1024)
            return b'\0' in chunk
    except Exception:
        return False

def get_file_extension(file_path: str) -> str:
    """
    获取文件扩展名
    
    Args:
        file_path: 文件路径
        
    Returns:
        文件扩展名（不包含点号）
    """
    return os.path.splitext(file_path)[1].lstrip('.').lower()

def pluralize(count: int, singular: str, plural: Optional[str] = None) -> str:
    """
    根据数量选择单复数形式
    
    Args:
        count: 数量
        singular: 单数形式
        plural: 复数形式，如果为None则添加's'
        
    Returns:
        根据数量选择的单词形式
    """
    if count == 1:
        return f"{count} {singular}"
    else:
        if plural is None:
            plural = singular + 's'
        return f"{count} {plural}"