# sf-ai-commit

使用 AI 大模型自动生成 git commit 消息的命令行工具。

## 1. 项目概述和主要功能

sf-ai-commit 是一个智能命令行工具，利用 AI 大模型自动分析 Git 暂存区的变更，生成符合 [Conventional Commits](https://www.conventionalcommits.org/) 规范的提交消息。它让开发者摆脱编写 commit 消息的负担，同时保持提交历史的一致性和可读性。

### 主要功能

- **智能分析**：分析 Git 暂存区变更，理解代码修改意图
- **标准格式**：生成符合 Conventional Commits 规范的提交消息
- **交互式界面**：美观丰富的命令行输出，支持彩色显示
- **灵活确认**：支持确认/取消/重新生成/编辑生成的消息
- **编辑器集成**：可在系统编辑器（默认为 nvim）中编辑消息
- **自定义配置**：支持 YAML 格式配置文件，可自定义 AI API 和提示词
- **多模型兼容**：支持各种 LLM 模型（默认使用 qwen2.5-coder）和 API 格式
- **API 密钥支持**：支持通过环境变量或配置文件设置 API 密钥
- **灵活模式**：支持生成简洁消息或详细消息

## 2. 安装方法

### 通过 pip 安装

```bash
pip install sf-ai-commit
```

### 从源码安装

```bash
git clone https://github.com/yourusername/sf-ai-commit.git
cd sf-ai-commit
pip install .
```

## 3. 快速入门

### 初始化配置

首次运行时，创建默认配置文件：

```bash
sf-ai-commit --init
```

这将在 `~/.config/sf-ai-commit/config.yaml` 创建默认配置文件。

### 基本使用流程

1. 添加要提交的文件到暂存区：

```bash
git add file1.py file2.py
```

2. 使用 sf-ai-commit 生成并提交：

```bash
sf-ai-commit
```

3. 审核生成的提交消息，可以选择确认、取消、编辑或重新生成。

## 4. 配置选项

### 配置文件位置

默认配置文件位置为 `~/.config/sf-ai-commit/config.yaml`

### 配置文件格式

配置文件使用 YAML 格式，包含三个主要部分：

1. **LLM API 配置**（`llm` 部分）
2. **提示词配置**（`prompts` 部分）
3. **工具偏好设置**（`preferences` 部分）

### 完整配置示例

```yaml
# LLM API配置
llm:
  # API主机地址
  host_url: "http://127.0.0.1:11434/v1/chat/completions" # 默认使用本地 Ollama 服务
  # 使用的AI模型
  model: "qwen2.5-coder" # 默认使用通义千问 Qwen2.5 Coder 模型
  # API请求超时时间(秒)
  timeout: 30
  # API请求头
  headers: {}
  # API密钥（可选，也可通过环境变量设置）
  api_key: ""
  # 温度参数(0.0-1.0)，控制生成结果的随机性
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
  # 编辑器命令(留空使用系统默认)
  editor_command: "nvim" # 默认使用 nvim 编辑器
```

### 主要配置选项说明

#### LLM 设置

- **host_url**: API 服务地址，默认为本地 Ollama 服务
- **model**: 使用的 AI 模型，默认为 qwen2.5-coder
- **timeout**: API 请求超时时间（秒）
- **headers**: 自定义 HTTP 请求头
- **api_key**: API 密钥（可选，也可通过环境变量设置）
- **temperature**: 生成结果的随机性参数（0.0-1.0）

#### 提示词设置

- **default**: 基础提示词模板，用于生成简洁的 commit 消息
- **detailed**: 详细提示词扩展，用于生成带有详细说明的 commit 消息

#### 偏好设置

- **detailed_by_default**: 是否默认生成详细消息（默认为 false）
- **max_message_length**: 最大消息长度限制（默认为 100）
- **editor_command**: 自定义编辑器命令（默认为 nvim）

## 5. 命令行参数

sf-ai-commit 提供了多种命令行选项以满足不同使用场景：

| 参数               | 简写 | 描述                                |
| ------------------ | ---- | ----------------------------------- |
| `--version`        | `-v` | 显示版本信息并退出                  |
| `--detailed`       | `-d` | 生成详细的提交消息                  |
| `--config PATH`    | `-c` | 指定配置文件路径                    |
| `--init`           |      | 创建默认配置文件                    |
| `--no-color`       |      | 禁用彩色输出                        |
| `--dry-run`        |      | 只生成消息但不实际提交              |
| `--verbose`        |      | 显示详细日志                        |
| `--repo-path PATH` |      | 指定 Git 仓库路径（默认为当前目录） |
| `--help`           | `-h` | 显示帮助信息并退出                  |

## 6. 实际使用场景示例

### 场景一：快速提交简单修复

当你修复了一个 bug 并想快速提交时：

```bash
git add src/components/login.js
sf-ai-commit
```

生成的消息可能类似于：`fix(auth): 修复登录表单验证失败问题`

### 场景二：提交重要功能并提供详细说明

当你完成了一个重要功能并希望提供详细说明时：

```bash
git add src/features/payment/ tests/payment/
sf-ai-commit --detailed
```

生成的消息可能类似于：

```
feat(payment): 添加支付宝支付集成功能

1. 实现支付宝 API 客户端
2. 添加支付流程和回调处理
3. 集成订单系统与支付状态同步
4. 添加相关单元测试确保功能稳定
```

### 场景三：在提交前预览和编辑消息

当你想先查看并可能编辑生成的消息，但不立即提交：

```bash
sf-ai-commit --dry-run
```

这将生成消息但不执行实际提交，让你有机会查看并决定是否采用。

## 7. 如何贡献

我们欢迎并感谢任何形式的贡献！您可以通过以下方式参与项目：

1. **报告问题**：如果发现 bug 或有新功能建议，请提交 issue
2. **提交代码**：可以 fork 项目，修改代码后提交 pull request
3. **改进文档**：帮助我们完善文档，使其更加清晰易懂
4. **分享使用体验**：在社区中分享您使用本工具的经验和建议

贡献前请确保：

- 代码符合项目的编码风格
- 添加适当的测试
- 更新相关文档

## 8. 许可证

MIT
