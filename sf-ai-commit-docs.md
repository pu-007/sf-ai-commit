# sf-ai-commit 用户指南

## 目录

- [项目概述](#项目概述)
  - [主要功能](#主要功能)
  - [技术特点](#技术特点)
  - [Conventional Commits 格式](#conventional-commits-格式)
- [安装说明](#安装说明)
  - [通过 pip 安装](#通过-pip-安装)
  - [从源码安装](#从源码安装)
  - [首次配置](#首次配置)
- [使用指南](#使用指南)
  - [基本用法](#基本用法)
  - [命令行选项](#命令行选项)
  - [配置文件设置](#配置文件设置)
- [高级功能](#高级功能)
  - [自定义提示词](#自定义提示词)
  - [连接不同的 AI 服务](#连接不同的-ai-服务)
  - [自定义提交消息格式](#自定义提交消息格式)
- [故障排除](#故障排除)
  - [常见问题与解决方案](#常见问题与解决方案)
  - [错误消息解释](#错误消息解释)

## 项目概述

sf-ai-commit 是一个强大的命令行工具，使用 AI 大模型自动生成高质量的 git commit 消息。通过分析 git 暂存区的变更，工具会生成符合 Conventional Commits 规范的提交消息，帮助开发者保持一致的提交风格并提高代码库的可维护性。

### 主要功能

- **自动生成提交消息**：根据 git 暂存区的变更自动生成有意义的提交消息
- **符合规范**：生成的消息遵循 Conventional Commits 规范
- **交互式确认**：允许用户确认、编辑、重新生成或取消提交
- **详细模式**：可以生成包含更多上下文信息的详细提交消息
- **易于集成**：与现有 git 工作流程无缝集成

### 技术特点

- **灵活的 LLM 集成**：默认使用 Ollama 本地模型，也支持 OpenAI 和其他兼容 OpenAI API 格式的服务
- **美观的命令行界面**：使用 Rich 库提供丰富的色彩和格式化输出
- **高度可配置**：通过 YAML 配置文件自定义行为和选项
- **编辑器集成**：支持在系统默认编辑器中编辑生成的提交消息
- **差异智能分析**：使用 GitPython 精确分析代码变更

### Conventional Commits 格式

sf-ai-commit 生成的提交消息遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范，格式如下：

```
<type>[optional scope]: <description>

[optional body]

[optional footer]
```

支持的类型（type）包括：

- `feat`: 新功能
- `fix`: 修复 bug
- `docs`: 文档变更
- `style`: 代码风格变更（不影响代码功能）
- `refactor`: 代码重构
- `perf`: 性能优化
- `test`: 测试相关
- `build`: 构建系统或外部依赖变更
- `ci`: CI 配置文件和脚本变更
- `chore`: 其他变更

## 安装说明

### 通过 pip 安装

最简单的安装方式是通过 pip：

```bash
pip install sf-ai-commit
```

这将安装 sf-ai-commit 及其所有依赖项。

### 从源码安装

如果您想从源码安装或进行开发，可以按照以下步骤操作：

```bash
# 克隆仓库
git clone https://github.com/yourusername/sf-ai-commit.git

# 进入项目目录
cd sf-ai-commit

# 安装项目及其依赖
pip install .

# 或者，如果您正在开发该项目，可以使用可编辑模式安装
pip install -e .
```

### 首次配置

安装完成后，您需要创建一个配置文件：

```bash
sf-ai-commit --init
```

这个命令会在 `~/.config/sf-ai-commit/config.yaml` 创建默认配置文件。如果您计划使用默认的 Ollama 后端，请确保已安装并运行了 Ollama 服务：

```bash
# 安装 Ollama（如果尚未安装）
# 请参考 https://ollama.ai/download 获取特定平台的安装指南

# 启动 Ollama 服务
ollama serve

# 拉取模型（如果尚未下载）
ollama pull llama3
```

如果您打算使用 OpenAI API，您需要设置您的 API 密钥（稍后会详细说明）。

## 使用指南

### 基本用法

sf-ai-commit 的基本工作流程如下：

1. 使用 `git add` 将要提交的文件添加到暂存区：

```bash
git add path/to/your/changed/files
```

2. 运行 sf-ai-commit 生成并提交：

```bash
sf-ai-commit
```

3. 查看生成的提交消息，然后选择：
   - 确认并执行提交
   - 取消操作
   - 在编辑器中修改消息
   - 要求重新生成消息

下面是一个典型的工作流程示例：

```bash
# 修改一些文件
echo "新功能代码" >> feature.js

# 将更改添加到暂存区
git add feature.js

# 使用 sf-ai-commit 生成并提交
sf-ai-commit

# 程序会分析变更并生成消息，例如：
# feat: 添加新功能代码到 feature.js
#
# 您可以选择：
# 1. 确认
# 2. 取消
# 3. 编辑
# 4. 重新生成
```

### 命令行选项

sf-ai-commit 提供了以下命令行选项：

| 选项               | 短格式 | 描述                                |
| ------------------ | ------ | ----------------------------------- |
| `--version`        | `-v`   | 显示版本信息并退出                  |
| `--detailed`       | `-d`   | 生成详细的提交消息（包含消息体）    |
| `--config PATH`    | `-c`   | 指定配置文件路径                    |
| `--init`           |        | 创建默认配置文件                    |
| `--no-color`       |        | 禁用彩色输出                        |
| `--dry-run`        |        | 只生成消息但不实际提交              |
| `--verbose`        |        | 显示详细日志                        |
| `--repo-path PATH` |        | 指定 Git 仓库路径（默认为当前目录） |
| `--help`           | `-h`   | 显示帮助信息并退出                  |

示例用法：

```bash
# 生成详细提交消息
sf-ai-commit --detailed

# 使用自定义配置文件
sf-ai-commit --config /path/to/my-config.yaml

# 只生成消息但不提交（预览模式）
sf-ai-commit --dry-run

# 在不同目录的 Git 仓库中工作
sf-ai-commit --repo-path /path/to/repo
```

### 配置文件设置

配置文件使用 YAML 格式，默认位于 `~/.config/sf-ai-commit/config.yaml`。以下是完整的配置选项：

```yaml
# LLM API配置
llm:
  # API主机地址
  host_url: "http://127.0.0.1:11434/v1/chat/completions" # 默认使用ollama
  # 使用的AI模型
  model: "qwen2.5-coder" # 默认使用 qwen2.5-coder 模型
  # API请求超时时间(秒)
  timeout: 30
  # API请求头 - 用于自定义HTTP头信息
  headers: {}
  # API密钥 - 直接设置API密钥，会自动添加到Authorization头
  api_key: ""
  # 温度参数(0.0-1.0)，控制生成内容的随机性，越高越随机
  temperature: 0.7

# 提示词配置
prompts:
  # 默认提示词
  default: |
    你是一个Git提交消息生成助手。
    请根据以下Git差异生成符合Conventional Commits规范的提交消息。
    格式应为: <type>[optional scope]: <description>

    类型(type)应该是以下之一:
    - feat: 新功能
    - fix: 修复bug
    - docs: 文档变更
    - style: 代码风格变更(不影响代码功能)
    - refactor: 代码重构
    - perf: 性能优化
    - test: 测试相关
    - build: 构建系统或外部依赖变更
    - ci: CI配置文件和脚本变更
    - chore: 其他变更

    保持描述简洁、清晰，使用现在时态和祈使句。
    不要以句号结尾。

  # 详细提示词
  detailed: |
    在上面基础上增加详细的消息体，包含以下内容:
    1. 变更的原因或目的
    2. 变更的主要内容
    3. 可能的影响或注意事项

    消息体应与主题行之间空一行，且每行不超过72个字符。

# 工具偏好设置
preferences:
  # 是否默认生成详细消息
  detailed_by_default: false
  # 最大消息长度
  max_message_length: 100
  # 编辑器命令(默认使用nvim，如果系统上没有指定的编辑器，将回退到系统默认编辑器)
  editor_command: "nvim"
```

## 高级功能

### 自定义提示词

您可以通过编辑配置文件中的 `prompts` 部分来自定义生成提交消息的提示词。这允许您调整生成的消息风格、格式和内容。

例如，如果您想要更简洁的提交消息，可以修改默认提示词：

```yaml
prompts:
  default: |
    你是一个Git提交消息生成专家。
    请根据以下Git差异生成简洁的提交消息，符合Conventional Commits格式。
    格式: <type>: <description>
    使用英文，保持在50个字符以内，使用命令式语气。
```

如果您的团队使用特定的提交消息格式或约定，您可以相应地调整提示词：

```yaml
prompts:
  default: |
    根据以下Git差异生成符合公司规范的提交消息。
    格式: [JIRA-ID] <type>: <description>
    每个提交应该引用相关的JIRA工单ID。
    从差异内容中推断可能的JIRA ID。
```

### 连接不同的 AI 服务

sf-ai-commit 支持多种 LLM 服务，包括 OpenAI、Ollama 和其他兼容 OpenAI API 格式的服务。

#### 使用 OpenAI API

```yaml
llm:
  host_url: "https://api.openai.com/v1/chat/completions"
  model: "gpt-4o"
  # 可以通过两种方式设置API密钥:
  # 方式1: 使用headers
  headers:
    Authorization: "Bearer YOUR_API_KEY"
  # 方式2: 直接设置api_key（推荐）
  api_key: "YOUR_API_KEY"
  temperature: 0.7
```

您也可以通过环境变量设置 API 密钥：

```bash
export OPENAI_API_KEY="your-api-key-here"
```

#### 使用 Ollama（默认）

确保 Ollama 服务已启动：

```bash
ollama serve
```

然后在配置文件中设置：

```yaml
llm:
  host_url: "http://127.0.0.1:11434/v1/chat/completions"
  model: "llama3"
  temperature: 0.7
```

#### 使用其他 AI 服务

例如，使用 Azure OpenAI 服务：

```yaml
llm:
  host_url: "https://your-resource-name.openai.azure.com/openai/deployments/your-deployment-name/chat/completions?api-version=2023-05-15"
  model: "gpt-4"
  headers:
    api-key: "YOUR_AZURE_API_KEY"
  temperature: 0.7
```

或者使用本地托管的开源模型 API：

```yaml
llm:
  host_url: "http://localhost:8080/v1/chat/completions"
  model: "your-local-model"
  temperature: 0.7
```

### 自定义提交消息格式

如果您希望更改默认的提交消息格式和处理方式，可以通过以下方式实现：

1. **修改提示词**：如前所述，通过调整提示词可以控制生成的消息格式和风格。

2. **使用详细模式**：使用 `--detailed` 选项或设置 `preferences.detailed_by_default: true` 来生成包含消息体的更详细提交消息。

3. **调整温度参数**：温度参数控制生成内容的随机性，较低的值（如 0.3）会产生更确定性的结果，较高的值（如 0.8）会增加创造性和多样性。

```yaml
llm:
  temperature: 0.4 # 更确定性的结果
```

4. **通过交互式编辑**：生成消息后，选择"编辑"选项在系统编辑器中修改消息，以满足您的确切需求。

## 故障排除

### 常见问题与解决方案

#### 问题：提示"没有暂存的变更"

**解决方案**：
确保您已经使用 `git add` 将更改添加到暂存区：

```bash
git add path/to/changed/files
```

#### 问题：无法连接到 LLM API

**解决方案**：
检查网络连接和 API 配置：

1. 确认 API URL 是否正确
2. 验证 API 密钥是否有效
3. 如果使用 Ollama，确保服务已启动：

```bash
ollama serve
```

4. 检查防火墙或代理设置

#### 问题：生成的提交消息质量不佳

**解决方案**：

1. 调整提示词以提供更明确的指导
2. 使用更高级的模型（如从 llama3 切换到 gpt-4o）
3. 降低温度参数以获得更确定性的结果：

```yaml
llm:
  temperature: 0.4
```

#### 问题：找不到编辑器

**解决方案**：
在配置文件中明确指定编辑器命令：

```yaml
preferences:
  editor_command: "code"  # 使用VS Code
  # 或
  editor_command: "vim"   # 使用Vim
  # 或
  editor_command: "notepad"  # 在Windows上使用记事本
```

如果系统上没有找到指定的编辑器，sf-ai-commit 将显示警告并自动回退到系统默认编辑器，确保程序仍然能够正常运行。

#### 问题：配置文件不生效

**解决方案**：

1. 确认配置文件路径正确
2. 检查 YAML 格式是否有效
3. 尝试使用 `--config` 明确指定配置文件路径：

```bash
sf-ai-commit --config ~/.config/sf-ai-commit/config.yaml
```

### 错误消息解释

| 错误消息                                               | 说明                          | 解决方案                                                      |
| ------------------------------------------------------ | ----------------------------- | ------------------------------------------------------------- |
| `配置文件不存在: {path}`                               | 找不到指定的配置文件          | 使用 `sf-ai-commit --init` 创建默认配置文件                   |
| `Git仓库未找到: {path}`                                | 指定的路径不是有效的 Git 仓库 | 确保您在 Git 仓库中或使用 `--repo-path` 指定正确的仓库路径    |
| `没有暂存的变更，请先使用 'git add' 添加变更`          | 没有要提交的变更              | 使用 `git add` 添加变更到暂存区                               |
| `连接LLM API失败: {error}`                             | 无法连接到 LLM 服务           | 检查网络连接、API URL 和凭据                                  |
| `LLM响应无效: {error}`                                 | LLM 返回了无法解析的响应      | 检查 API 配置，尝试使用不同的模型或调整参数                   |
| `找不到编辑器: {editor}`                               | 找不到指定的编辑器命令        | 在配置文件中指定正确的编辑器命令或设置 VISUAL/EDITOR 环境变量 |
| `找不到指定的编辑器: {editor}，已回退到系统默认编辑器` | 指定的编辑器不存在，自动回退  | 这是一个警告，不需要操作，系统已自动回退到默认编辑器          |

## 结语

sf-ai-commit 是一个强大的工具，能够显著简化 Git 提交消息的创建过程，并确保整个项目保持一致的提交风格。通过灵活的配置选项和多种 AI 服务支持，您可以根据自己的需求定制工具的行为。

我们欢迎您的贡献和反馈，请通过 GitHub 仓库提交问题或功能请求。
