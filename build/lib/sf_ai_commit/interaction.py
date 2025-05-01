"""
交互管理器模块 - 负责用户交互界面
"""

import logging
import os
import tempfile
import subprocess
from typing import Dict, Any, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt, Confirm
from rich import box

from sf_ai_commit.constants import (
    CONFIRM_OPTIONS,
    ERROR_EDITOR_NOT_FOUND
)

class InteractionManager:
    """管理用户交互界面"""
    
    def __init__(self, no_color: bool = False):
        """
        初始化交互管理器
        
        Args:
            no_color: 是否禁用彩色输出
        """
        self.console = Console(highlight=not no_color, color_system=None if no_color else "auto")
        
    def display_message(self, message: str) -> None:
        """
        美化显示生成的消息
        
        Args:
            message: 要显示的提交消息
        """
        # 分割消息标题和正文
        parts = message.split('\n\n', 1)
        title = parts[0]
        body = parts[1] if len(parts) > 1 else ""
        
        # 显示标题
        self.console.print()
        self.console.print(Panel(
            title,
            title="[bold blue]提交消息标题",
            border_style="blue",
            box=box.ROUNDED
        ))
        
        # 如果有正文，显示正文
        if body:
            self.console.print(Panel(
                Markdown(body),
                title="[bold green]提交消息正文",
                border_style="green",
                box=box.ROUNDED
            ))
            
        self.console.print()
    
    def confirm_message(self, message: str) -> Tuple[bool, str, bool]:
        """
        用户确认界面
        
        展示提交消息并提供选项：确认/取消/编辑/重新生成
        
        Args:
            message: 要确认的提交消息
            
        Returns:
            元组(操作结果, 可能修改过的消息, 是否请求重新生成)
            - 操作结果: 如果确认则为True，否则为False
            - 消息: 可能是编辑后的消息
            - 是否重新生成: 如果用户请求重新生成则为True
        """
        # 显示生成的消息
        self.display_message(message)
        
        # 提示用户选择操作
        choice = Prompt.ask(
            "请选择操作",
            choices=[str(i+1) for i in range(len(CONFIRM_OPTIONS))],
            default="1"
        )
        
        option = CONFIRM_OPTIONS[int(choice) - 1]
        
        if option == "确认":
            return (True, message, False)
        elif option == "取消":
            return (False, message, False)
        elif option == "编辑":
            edited_message = self.edit_message(message)
            if edited_message:
                return (True, edited_message, False)
            else:
                # 编辑取消，返回原消息并请求用户重新选择
                self.console.print("[yellow]编辑已取消，使用原消息。[/yellow]")
                return self.confirm_message(message)
        elif option == "重新生成":
            return (False, message, True)
            
        # 默认返回取消
        return (False, message, False)
    
    def edit_message(self, message: str) -> Optional[str]:
        """
        在系统编辑器中编辑消息
        
        Args:
            message: 要编辑的提交消息
            
        Returns:
            编辑后的消息，如果编辑被取消则返回None
        """
        editor_command = self._get_editor_command()
        if not editor_command:
            self.console.print("[bold red]错误: 找不到可用的编辑器。[/bold red]")
            return None
            
        # 创建临时文件
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w+", delete=False) as temp_file:
            temp_path = temp_file.name
            # 写入原始消息
            temp_file.write(message)
            
        try:
            # 打开编辑器
            self.console.print(f"[blue]正在打开编辑器: {editor_command}[/blue]")
            result = subprocess.run([editor_command, temp_path], check=True)
            
            # 如果编辑器正常退出，读取编辑后的内容
            if result.returncode == 0:
                with open(temp_path, "r") as f:
                    edited_message = f.read().strip()
                    
                if edited_message != message:
                    self.console.print("[green]消息已更新。[/green]")
                else:
                    self.console.print("[yellow]消息未变更。[/yellow]")
                    
                return edited_message
            else:
                self.console.print("[yellow]编辑器异常退出，使用原消息。[/yellow]")
                return message
                
        except Exception as e:
            self.console.print(f"[bold red]编辑器错误: {str(e)}[/bold red]")
            return None
        finally:
            # 删除临时文件
            try:
                os.unlink(temp_path)
            except Exception:
                pass
    
    def _get_editor_command(self) -> Optional[str]:
        """
        获取系统默认编辑器命令
        
        优先使用VISUAL或EDITOR环境变量，然后尝试常见编辑器
        
        Returns:
            编辑器命令，如果找不到则返回None
        """
        # 尝试从环境变量获取
        editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
        
        if editor:
            return editor
            
        # 尝试常见编辑器
        common_editors = ["code", "notepad", "vim", "nano", "gedit"]
        
        for editor in common_editors:
            try:
                result = subprocess.run(
                    ["which", editor], 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    return editor
            except Exception:
                pass
                
        return None
        
    def show_error(self, message: str) -> None:
        """
        显示错误消息
        
        Args:
            message: 错误消息
        """
        self.console.print(f"[bold red]错误: {message}[/bold red]")
        
    def show_success(self, message: str) -> None:
        """
        显示成功消息
        
        Args:
            message: 成功消息
        """
        self.console.print(f"[bold green]{message}[/bold green]")
        
    def show_warning(self, message: str) -> None:
        """
        显示警告消息
        
        Args:
            message: 警告消息
        """
        self.console.print(f"[bold yellow]警告: {message}[/bold yellow]")
        
    def show_info(self, message: str) -> None:
        """
        显示信息消息
        
        Args:
            message: 信息消息
        """
        self.console.print(f"[bold blue]{message}[/bold blue]")
        
    def show_loading(self, message: str) -> Any:
        """
        显示加载状态
        
        Args:
            message: 加载状态消息
            
        Returns:
            Rich加载状态对象
        """
        return self.console.status(message, spinner="dots")