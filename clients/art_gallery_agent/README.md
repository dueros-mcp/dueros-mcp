# 艺术画廊多智能体系统 (Art Gallery Multi-Agent System)

一个基于 LangGraph 的多智能体系统，专门用于艺术画廊管理、展览信息查询和智能聊天服务。

## 系统概述

本系统采用分层多智能体架构，通过智能分类路由将用户请求分发到相应的专业智能体处理：

- 🎨 **艺术画廊智能体**: 处理艺术作品查询、推荐和展示
- 💬 **聊天智能体**: 处理通用对话和用户引导
- 🧠 **分类路由智能体**: 智能分析用户意图并进行路由

## 核心功能

### 1. 艺术画廊管理
- 基于 Elasticsearch 的艺术作品搜索
- 画家、风格、时期多维度查询
- 小度设备艺术作品展示推送（MCP）
- 居家装饰画作推荐

### 2. 智能对话助手
- 自然语言交互
- 需求意图识别
- 服务功能引导
- 多轮对话支持

## 技术架构

```
用户输入 → 分类路由器 → 专业智能体 → 工具调用 → 设备推送/响应
           ↓
    ┌────────────────────────┐
    ↓                        ↓
艺术画廊智能体             聊天智能体
    ↓                        ↓
专业工具集                  通用对话
    ↓                        ↓
小度设备推送                直接响应
```

## 快速开始

### 环境要求
- Python 3.10+
- LangGraph
- LangChain

### 安装依赖
```bash
# 推荐使用虚拟环境
conda create -n art_gallery_agent python=3.11
conda activate art_gallery_agent

# 在仓库根目录安装依赖
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 创建配置文件
```bash
# 进入目录并创建配置文件（或拷贝示例后按需修改）
cd clients/art_gallery_agent
# 使用 JSON 配置（必选）
cp servers_config.json.example servers_config.json
```

- JSON 配置（文件 `servers_config.json`）
  - `models.main_model` / `models.classification_model`
  - `elasticsearch.host/username/password/artwork_index`
  - `mcpServers`: 使用 `transport: "streamable_http"`，支持 `${ENV}` 占位符

OpenRouter 环境变量（若使用 `openrouter/*` 模型）：
```bash
export OPENROUTER_API_KEY=your_key_here
export OPENROUTER_SITE_URL=https://your.site
export OPENROUTER_SITE_NAME="Your App Name"
```

> 配置加载规则：程序会在同目录或当前工作目录下查找 `servers_config.json`（支持环境变量替换）。不再支持 INI 配置。

### 基本使用
```python
import asyncio
from art_gallery_system.graph import graph
from art_gallery_system.state import MultiAgentState
from langchain_core.messages import HumanMessage

async def main():
    state = MultiAgentState(messages=[HumanMessage(content="我想了解梵高的星夜")])
    result = await graph.ainvoke(state)
    print(result)

if __name__ == "__main__":
    asyncio.run(main())
```

> 包名说明：源码中的导入使用 `art_gallery_system.*`。若直接以源码运行，可在仓库根目录创建软链接以匹配包名：
```bash
ln -s clients/art_gallery_agent/art_gallery_system art_gallery_system
```

## 项目结构

```
clients/art_gallery_agent/
├── art_gallery_system/
│   ├── __init__.py
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── art_gallery_agent.py
│   │   ├── base_agent.py
│   │   ├── chat_agent.py
│   │   └── classification_router.py
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── art_gallery_tools.py
│   │   ├── handoff_tools.py
│   │   └── mcp_client.py
│   ├── configuration.py
│   ├── graph.py
│   ├── prompts.py
│   ├── state.py
│   └── utils.py
├── langgraph.json
├── servers_config.json.example
└── README.md
```

## 工具与MCP集成

- 本地工具：
  - `search_artworks`：对 ES 索引进行检索，返回结构化艺术品列表。
  - `transfer_to_chat` / `transfer_to_art_gallery`：在 "聊天" 与 "艺术画廊" 子图之间交接。
- MCP 工具：
  - 通过 `tools/mcp_client.py` 自动拉取并注入（`get_tools()`）。
  - 在运行时由 `tools/art_gallery_tools.py` 的 `get_art_gallery_tools_with_mcp()` 合并到工具集中。
- 可选开关：
  - 在 `graph.py` 中可将 `ENABLE_HITL_TOOL_REVIEW=True` 以启用“工具执行前的人参与审阅”。

## 开发指南

### 添加新智能体
1. 继承 `BaseAgent` 类
2. 实现 `process` 方法
3. 在路由器中添加分类规则
4. 注册到主图中

### 添加新工具
1. 使用 `@tool` 装饰器定义工具（参见 `tools/art_gallery_tools.py`）
2. 在相应智能体或工具装载函数中注册

### 自定义提示词
在 `prompts.py` 中修改或添加提示词模板。

## 常见问题（FAQ）
- 导入失败（找不到 `art_gallery_system`）：在仓库根执行 `ln -s clients/art_gallery_agent/art_gallery_system art_gallery_system`，或将其打包为同名模块后安装。
- 无法找到 `servers_config.json`：在 `clients/art_gallery_agent/` 放置 `servers_config.json` 或在当前工作目录放置该文件，参考 `servers_config.json.example`。
- OpenRouter 报鉴权错误：检查 `OPENROUTER_API_KEY/OPENROUTER_SITE_URL/OPENROUTER_SITE_NAME`。
- ES 搜索失败：确认 `elasticsearch.host` 可访问、账户密码正确，索引名与集群一致。
- MCP 工具未注入：确认 `mcp.*.enabled=true` 且凭据（token/api_key）正确。
