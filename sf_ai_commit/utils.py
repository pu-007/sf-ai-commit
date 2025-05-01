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

def is_binary_stream(content: bytes) -> bool:
    """
    判断内容是否是二进制数据
    
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

def analyze_diff_content(diff_content: str) -> tuple:
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

def extract_meaningful_diff_content(diff_content: str, max_lines: int = 20) -> list:
    """
    从diff内容中提取有意义的部分
    
    Args:
        diff_content: 原始diff内容
        max_lines: 最大显示行数，0表示不限制
        
    Returns:
        有意义的diff行列表
    """
    lines = diff_content.split("\n")
    
    # 如果max_lines为0，返回所有内容
    if max_lines == 0:
        return lines
    
    # 跳过diff头部（@@ 行之前的内容）
    content_start = 0
    for i, line in enumerate(lines):
        if line.startswith("@@"):
            content_start = i
            break
    
    meaningful_lines = []
    in_change_block = False
    change_blocks = []
    current_block = []
    hunk_header = None
    
    # 解析diff内容
    for line in lines[content_start:]:
        # 保留hunk header（@@ -xx,xx +xx,xx @@）
        if line.startswith("@@"):
            if current_block and hunk_header:
                change_blocks.append((hunk_header, current_block))
            current_block = []
            hunk_header = line
            in_change_block = False
            continue
        
        # 检测是否包含实际变更
        if line.startswith("+") or line.startswith("-"):
            in_change_block = True
        
        # 在变更块中或者是上下文行
        if in_change_block or line.startswith(" "):
            current_block.append(line)
    
    # 添加最后一个块
    if current_block and hunk_header:
        change_blocks.append((hunk_header, current_block))
    
    # 选择最重要的变更块（基于变更行数）
    significant_blocks = sorted(
        change_blocks,
        key=lambda x: sum(1 for line in x[1] if line.startswith("+") or line.startswith("-")),
        reverse=True
    )
    
    # 最多返回3个最重要的变更块
    for header, block in significant_blocks[:3]:
        meaningful_lines.append(header)
        # 每个块最多显示max_lines/3行(平均分配给每个块)，优先保留变更行
        block_lines = []
        change_lines = [l for l in block if l.startswith("+") or l.startswith("-")]
        context_lines = [l for l in block if l.startswith(" ")]
        
        max_block_lines = max(10, max_lines // 3) if max_lines > 0 else len(block)
        
        # 确保变更行被保留
        if len(change_lines) <= max_block_lines:
            # 如果变更行少于限制，添加一些上下文
            block_lines = change_lines
            remaining = max_block_lines - len(block_lines)
            if remaining > 0 and context_lines:
                # 添加部分上下文
                context_to_add = min(len(context_lines), remaining)
                block_lines.extend(context_lines[:context_to_add])
        else:
            # 如果变更行超过限制，只保留最重要的部分
            block_lines = change_lines[:max_block_lines]
        
        meaningful_lines.extend(block_lines)
        
        # 如果原块更长，添加截断提示
        if len(block) > len(block_lines):
            meaningful_lines.append("...")
    
    # 如果没有找到有意义的变更，返回原始内容的前lines行
    if not meaningful_lines and lines:
        return lines[:min(max_lines, len(lines)) if max_lines > 0 else len(lines)]
    
    return meaningful_lines

def extract_meaningful_code_lines(code_lines: list, max_lines: int = 20) -> list:
    """
    从代码块中提取有意义的行
    
    Args:
        code_lines: 代码行列表
        max_lines: 最大显示行数，0表示不限制
        
    Returns:
        有意义的代码行列表
    """
    if not code_lines:
        return []
    
    # 如果max_lines为0，返回所有内容
    if max_lines == 0:
        return code_lines
    
    # 寻找包含 +/- 的行及其上下文
    meaningful_indices = []
    for i, line in enumerate(code_lines):
        if line.startswith("+") or line.startswith("-"):
            # 添加当前行及其前后两行的索引
            for j in range(max(0, i-2), min(len(code_lines), i+3)):
                meaningful_indices.append(j)
    
    # 去重并排序
    meaningful_indices = sorted(set(meaningful_indices))
    
    # 如果没有找到有意义的行，返回前几行
    if not meaningful_indices:
        return code_lines[:min(max_lines, len(code_lines))]
    
    # 提取有意义的行
    result = [code_lines[i] for i in meaningful_indices]
    
    # 如果结果太少，补充一些代码行
    if len(result) < 5 and len(code_lines) > len(result):
        additional_lines = min(max_lines - len(result), len(code_lines) - len(result))
        if additional_lines > 0:
            result.extend(code_lines[len(result):len(result) + additional_lines])
    
    # 如果结果超过max_lines，截断
    if max_lines > 0 and len(result) > max_lines:
        result = result[:max_lines]
    
    return result