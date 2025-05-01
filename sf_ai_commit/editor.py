"""
编辑器集成模块 - 负责与系统编辑器的交互
"""

import os
import tempfile
import subprocess
import logging
from typing import Optional, List, Tuple

from sf_ai_commit.constants import ERROR_EDITOR_NOT_FOUND, ERROR_EDITOR_FALLBACK

class EditorIntegration:
    """集成系统编辑器"""
    
    def __init__(self, editor_command: Optional[str] = None):
        """
        初始化编辑器集成
        
        Args:
            editor_command: 可选的指定编辑器命令，如果为None则使用系统默认
        """
        self.editor_command, self.is_fallback = self._resolve_editor_command(editor_command)
        
    def open_editor(self, message: str) -> Optional[str]:
        """
        在系统编辑器中打开消息
        
        Args:
            message: 要编辑的消息
            
        Returns:
            编辑后的消息，如果编辑被取消则返回None
            
        Raises:
            RuntimeError: 如果找不到可用的编辑器或编辑过程中出错
        """
        if not self.editor_command:
            raise RuntimeError(ERROR_EDITOR_NOT_FOUND.format("未找到系统编辑器"))
            
        # 创建临时文件
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w+", delete=False) as temp_file:
            temp_path = temp_file.name
            temp_file.write(message)
            
        try:
            # 构建编辑器命令
            cmd_parts = self.editor_command.split()
            cmd_parts.append(temp_path)
            
            # 打开编辑器
            process = subprocess.Popen(cmd_parts)
            process.wait()
            
            # 读取编辑后的文件
            if os.path.exists(temp_path):
                with open(temp_path, "r", encoding="utf-8") as f:
                    edited_message = f.read().strip()
                return edited_message
            else:
                raise RuntimeError(f"临时文件不存在: {temp_path}")
                
        except Exception as e:
            logging.error(f"编辑器错误: {str(e)}")
            raise RuntimeError(f"使用编辑器时出错: {str(e)}")
        finally:
            # 删除临时文件
            try:
                os.unlink(temp_path)
            except Exception as e:
                logging.warning(f"删除临时文件失败: {str(e)}")
    
    def _resolve_editor_command(self, specified_editor: Optional[str] = None) -> Tuple[Optional[str], bool]:
        """
        解析编辑器命令，如果指定的编辑器不存在则回退到系统默认编辑器
        
        Args:
            specified_editor: 用户指定的编辑器命令
            
        Returns:
            Tuple[Optional[str], bool]: 编辑器命令和是否进行了回退的标志
        """
        is_fallback = False
        
        # 如果指定了编辑器，尝试使用它
        if specified_editor:
            # 检查平台
            is_windows = os.name == "nt"
            
            # 检查指定的编辑器是否存在
            try:
                cmd = "where" if is_windows else "which"
                result = subprocess.run(
                    [cmd, specified_editor.split()[0]],  # 只检查命令的第一个部分
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    return specified_editor, is_fallback
                
                # 如果指定的编辑器不存在，记录警告并回退
                logging.warning(ERROR_EDITOR_FALLBACK.format(specified_editor))
                is_fallback = True
            except Exception as e:
                logging.warning(f"检查编辑器时出错: {str(e)}")
                is_fallback = True
        
        # 回退到系统默认编辑器
        editor_command = self.get_editor_command()
        return editor_command, is_fallback
        
    def get_editor_command(self) -> Optional[str]:
        """
        获取系统默认编辑器命令
        
        按以下顺序尝试:
        1. VISUAL环境变量
        2. EDITOR环境变量
        3. 常见编辑器
        
        Returns:
            编辑器命令，如果找不到则返回None
        """
        # 尝试从环境变量获取
        editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
        
        if editor:
            return editor
            
        # 检查平台
        is_windows = os.name == "nt"
        
        # 平台特定的编辑器列表
        if is_windows:
            common_editors = ["notepad.exe", "code.exe", "notepad++.exe", "gvim.exe"]
        else:
            common_editors = ["vim", "nano", "emacs", "gedit", "code", "nvim", "kwrite", "kate"]
            
        # 尝试常见编辑器
        for editor in common_editors:
            try:
                if is_windows:
                    # Windows上使用where命令
                    result = subprocess.run(
                        ["where", editor], 
                        stdout=subprocess.PIPE, 
                        stderr=subprocess.PIPE,
                        text=True,
                        check=False
                    )
                else:
                    # Unix/Linux上使用which命令
                    result = subprocess.run(
                        ["which", editor], 
                        stdout=subprocess.PIPE, 
                        stderr=subprocess.PIPE,
                        text=True,
                        check=False
                    )
                    
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip().split("\n")[0]
            except Exception:
                continue
                
        return None
        
    def get_available_editors(self) -> List[str]:
        """
        获取系统上可用的编辑器列表
        
        Returns:
            可用编辑器命令列表
        """
        available_editors = []
        
        # 检查环境变量
        for env_var in ["VISUAL", "EDITOR"]:
            if env_var in os.environ and os.environ[env_var]:
                available_editors.append(os.environ[env_var])
                
        # 检查常见编辑器
        is_windows = os.name == "nt"
        
        if is_windows:
            common_editors = ["notepad.exe", "code.exe", "notepad++.exe", "gvim.exe"]
        else:
            common_editors = ["vim", "nano", "emacs", "gedit", "code", "nvim", "kwrite", "kate"]
            
        for editor in common_editors:
            try:
                if is_windows:
                    result = subprocess.run(
                        ["where", editor], 
                        stdout=subprocess.PIPE, 
                        stderr=subprocess.PIPE,
                        text=True,
                        check=False
                    )
                else:
                    result = subprocess.run(
                        ["which", editor], 
                        stdout=subprocess.PIPE, 
                        stderr=subprocess.PIPE,
                        text=True,
                        check=False
                    )
                    
                if result.returncode == 0 and result.stdout.strip():
                    editor_path = result.stdout.strip().split("\n")[0]
                    if editor_path not in available_editors:
                        available_editors.append(editor_path)
            except Exception:
                continue
                
        return available_editors