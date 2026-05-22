# AI SALES MASTER - 销售实战训练大师

模拟真实客户与销售对练，支持多种销售风格学习，训练后给出专业维度评估与签单路径规划。

## 功能

- **双角色模拟**：AI扮演客户（销售练习）或AI扮演销售（风格学习）
- **4种婚礼场景**：酒店婚宴 / 户外草坪 / 小型精品 / 目的地婚礼
- **风格提取与学习**：上传销售聊天记录，AI自动提取风格特征，可对比互补
- **8维度评估**：沟通表达、需求发掘、价值主张、异议处理、流程完整、关系建立、风格运用、收尾技巧
- **实战总结**：对话结束后自动生成问题诊断、校正话术、签单路径规划
- **数据保密**：默认使用本地模型（Ollama），数据不出本机

## 快速开始

### 1. 安装 Python

下载 [Python 3.11+](https://www.python.org/downloads/)，安装时勾选 **Add Python to PATH**

### 2. 安装 Ollama（本地模型）

下载 [Ollama](https://ollama.com/download)，安装后运行：

```bash
ollama pull qwen2.5:14b
```

### 3. 安装依赖

```bash
cd AI_SALES_MASTER
pip install -r requirements.txt
```

### 4. 导入资料（首次使用）

将你的销售话术库、公司简介、面聊记录放到任意目录，然后编辑 `scripts/import_knowledge.py` 中的 `SOURCE_DIR` 路径，运行：

```bash
python scripts/import_knowledge.py
```

### 5. 启动

```bash
python app.py
```

浏览器自动打开 `http://localhost:7860`

## 使用流程

1. **风格管理**：上传销售对话文件，提取销售风格（最多4种）
2. **训练场**：选婚礼类型和难度，开始与AI客户对练
3. **结束训练**：自动生成实战总结（问题诊断 + 校正话术 + 签单路径）
4. **评估报告**：查看雷达图、8维度评分、具体对话点评

## 配置

复制 `.env.example` 为 `.env`，按需修改：

```bash
# 模型选择：ollama（本地，推荐）或 claude（云端，自动脱敏）
LLM_PROVIDER=ollama

# Ollama模型（推荐中文模型）
OLLAMA_MODEL=qwen2.5:14b

# Claude API（仅云端模式）
ANTHROPIC_API_KEY=your_key
```

## 数据安全

| 模式 | 数据流向 | 说明 |
|---|---|---|
| **Ollama（默认）** | 全部本机处理 | 零出网，数据不出电脑 |
| **Claude云端** | 自动脱敏后发送 | 手机号/姓名/金额等自动替换为标签 |

所有聊天记录、风格档案、评估报告存储在本地 `data/` 目录，不上传 GitHub。

## 项目结构

```
AI_SALES_MASTER/
├── app.py                 # 启动入口
├── config.py              # 配置
├── SOUL.md                # AI教练灵魂文档
├── core/                  # 核心引擎
│   ├── llm_client.py      # LLM客户端（Ollama/Claude）
│   ├── role_engine.py     # 角色模拟引擎
│   ├── training_manager.py# 训练管理
│   ├── style_extractor.py # 风格提取
│   └── evaluator.py       # 评估引擎
├── prompts/               # 提示词
├── models/                # 数据模型
├── storage/               # 本地存储
├── ui/                    # Gradio界面
├── utils/                 # 工具（文件解析/脱敏/文本处理）
├── scripts/               # 脚本
└── data/                  # 运行时数据（不上传）
```

## 技术栈

- Python 3.11+ / Gradio
- Ollama (qwen2.5) 本地模型
- Claude API (可选，云端模式)
- matplotlib 雷达图
