# Simple Chatbot（MCP 测试客户端）

一个用于测试小度 MCP 服务器功能的简易聊天客户端，支持 StreamableHTTP 和 Stdio 两种接入方式。

## 功能概述
- 连接一个或多个 MCP 服务器
- 从服务器动态获取工具清单
- 通过 OpenAI Chat Completions 驱动对话与工具调用
- 自动保存工具返回的图片（如拍照）到本地文件

## 前置条件
- Python 3.10+
- 一个可用的 LLM API Key（环境变量 `LLM_API_KEY`）
- 至少一个可用的 MCP 服务器（推荐使用本仓库的小度 MCP 服务器）

## 配置

本客户端通过 `servers_config.json` 配置要连接的 MCP 服务器，支持环境变量占位符（`${VAR}`）。示例：

```json
{
    "mcpServers": {
        "xiaodu_mcp_server": {
            "url": "https://xiaodu.baidu.com/dueros_mcp_server/mcp/",
            "transport_type": "streamablehttp",
            "headers": {
                "Access_Token": "${ACCESS_TOKEN}"
            },
            "timeout": 30,
            "sse_read_timeout": 300
        }
    }
}
```

- 将 `ACCESS_TOKEN` 导出到环境变量：
```bash
export ACCESS_TOKEN=your_access_token_here
```

- 也可以添加更多服务器或切换到 Stdio 模式（例如结合 mcp-proxy）：
```json
{
  "mcpServers": {
    "xiaodu_mcp_via_stdio": {
      "command": "/path/to/mcp-proxy",
      "args": [
        "https://xiaodu.baidu.com/dueros_mcp_server/mcp/",
        "--headers", "ACCESS_TOKEN", "${ACCESS_TOKEN}",
        "--transport", "streamablehttp"
      ]
    }
  }
}
```

## 运行

1) 设置 LLM API Key（用于 OpenAI Chat Completions）：
```bash
export LLM_API_KEY=your_openai_api_key_here
```

2) 启动客户端：
```bash
cd clients/simple_chatbot
python simple_chatbot.py
```

启动后，程序会：
- 连接并初始化配置中的 MCP 服务器
- 列出可用工具并转换为 OpenAI 工具格式
- 进入交互式对话；当工具返回图片（如 `xiaodu_take_photo`）时，会自动保存到当前目录，文件名形如 `xiaodu_photo_<timestamp>.jpg`

## 常见问题
- 没有找到 `LLM_API_KEY`：请先 `export LLM_API_KEY=...`
- 401/鉴权错误：检查 `ACCESS_TOKEN` 是否正确导出并在 `servers_config.json` 中被引用
- 无法连接服务器：确认 `url` 可达，或 Stdio 模式下的 `command/args` 正确

## 参考
- 服务器配置文件：`clients/simple_chatbot/servers_config.json`
- 客户端入口：`clients/simple_chatbot/simple_chatbot.py`
