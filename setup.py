"""
sf-ai-commit的安装配置文件
"""

import os
from setuptools import setup, find_packages

# 读取README文件
def read_readme():
    with open("README.md", "r", encoding="utf-8") as f:
        return f.read()

# 读取version文件
def get_version():
    with open(os.path.join("sf_ai_commit", "__init__.py"), "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("__version__"):
                return line.split("=")[1].strip().strip('"\'')
    return "0.1.0"  # 默认版本

setup(
    name="sf-ai-commit",
    version=get_version(),
    description="使用AI大模型自动生成git commit消息的命令行工具",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    author="AI Architect",
    author_email="user@example.com",
    url="https://github.com/yourusername/sf-ai-commit",
    packages=find_packages(),
    install_requires=[
        "gitpython>=3.1.0",
        "pyyaml>=6.0",
        "requests>=2.25.0",
        "rich>=10.0.0",
    ],
    entry_points={
        "console_scripts": [
            "sf-ai-commit=sf_ai_commit.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Topic :: Software Development :: Version Control :: Git",
    ],
    keywords="git, commit, ai, conventional-commits",
    python_requires=">=3.7",
    license="MIT",
)