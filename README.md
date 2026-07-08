# 小度智能终端 MCP Server

[![MCP](https://img.shields.io/badge/MCP-Compatible-blue)](https://modelcontextprotocol.io/)

一个基于 Model Context Protocol (MCP) 的小度智能终端服务，让 AI 应用能够控制小度设备。支持 Cursor、Claude、OpenClaw、Hermes、Cherry Studio、Cline 等兼容 MCP 协议的平台。

## 📋 目录

- [快速开始](#-快速开始)
- [接入方式](#-接入方式)
- [工具一览](#%EF%B8%8F-工具一览)
- [客户端示例](#-客户端示例)
- [文档索引](#-文档索引)

## 🚀 快速开始

### 前提条件

- 百度开发者账号
- 小度智能设备
- 支持 MCP 的 AI 工具（Cursor、Claude、OpenClaw、Hermes 等）

### 第一步：获取访问令牌

1. 访问[百度开发者平台](https://developer.dueros.baidu.com/)
2. 按照[接入授权文档](https://developer.dueros.baidu.com/doc/dueros-bot-platform//mcp-server/prepare/auth-intro_markdown)获取 `access_token`

### 第二步：在客户端中配置

小度 MCP Server 是一个远程 StreamableHTTP 服务，只需要两项信息即可接入：

| 项目 | 值 |
| --- | --- |
| Server 地址 | `https://xiaodu.baidu.com/dueros_mcp_server/mcp/` |
| 鉴权请求头 | `ACCESS_TOKEN: ${your_access_token}` |

以 Cursor 为例（设置 → MCP & Integrations → MCP Tools）：

```json
{
  "mcpServers": {
    "xiaodu-mcp": {
      "url": "https://xiaodu.baidu.com/dueros_mcp_server/mcp/",
      "headers": {
        "ACCESS_TOKEN": "${your_access_token}"
      }
    }
  }
}
```

配置完成后，在对话中说「列出我的小度设备」即可验证接通。其他客户端的详细步骤见下方[接入方式](#-接入方式)。

## 🔌 接入方式

支持 StreamableHTTP 的客户端可直连；仅支持 stdio 的客户端通过 [mcp-proxy](https://github.com/sparfenyuk/mcp-proxy) 桥接。各客户端的详细配置步骤见[接入指南](docs/integrations.md)：

| 客户端 | 接入模式 | 配置指南 |
| --- | --- | --- |
| Cursor | StreamableHTTP 直连 | [配置步骤](docs/integrations.md#cursor) |
| Cherry Studio | StreamableHTTP 直连 | [配置步骤](docs/integrations.md#cherry-studio) |
| Claude Code | StreamableHTTP 直连 | [配置步骤](docs/integrations.md#claude-code) |
| OpenClaw | StreamableHTTP 直连 | [配置步骤](docs/integrations.md#openclaw) |
| Hermes | StreamableHTTP 直连 | [配置步骤](docs/integrations.md#hermes) |
| Claude Desktop | Stdio + mcp-proxy | [配置步骤](docs/integrations.md#claude-desktopstdio--mcp-proxy) |
| Cline | Stdio + mcp-proxy | [配置步骤](docs/integrations.md#clinestdio--mcp-proxy) |
| 自定义 Agent | StreamableHTTP 直连 | [配置步骤](docs/integrations.md#开发者自定义-agent) |

## 🛠️ 工具一览

完整的参数与返回值定义见[工具接口参考](docs/tools.md)。

| 工具 | 功能 |
| --- | --- |
| [`list_user_devices`](docs/tools.md#1-获取设备列表-list_user_devices) | 获取用户绑定的在线设备列表 |
| [`control_xiaodu`](docs/tools.md#2-设备控制-control_xiaodu) | 通过自然语言指令控制小度设备 |
| [`xiaodu_speak`](docs/tools.md#3-语音播报-xiaodu_speak) | 让小度设备朗读指定文本 |
| [`xiaodu_send_notification`](docs/tools.md#4-发送通知-xiaodu_send_notification) | 向小度 App 或设备发送系统通知 |
| [`xiaodu_take_photo`](docs/tools.md#5-设备拍照-xiaodu_take_photo) | 触发支持摄像头的设备拍照并返回图像 |
| [`xiaodu_record_video`](docs/tools.md#6-设备录像-xiaodu_record_video) | 异步创建录像任务并返回可查询结果 |
| [`xiaodu_get_task`](docs/tools.md#7-查询任务状态-xiaodu_get_task) | 统一查询长任务执行状态与结果 |
| [`push_resource_to_xiaodu`](docs/tools.md#8-资源推送-push_resource_to_xiaodu) | 推送图片、视频、音频到小度设备 |
| [`xiaodu_open_web_page`](docs/tools.md#9-打开网页-xiaodu_open_web_page) | 在屏幕设备上打开 HTTP/HTTPS 页面 |
| [`query_xiaodu_skills`](docs/tools.md#10-查询小度技能-query_xiaodu_skills) | 查询当前设备可打开的小度技能 |
| [`xiaodu_open_skill`](docs/tools.md#11-打开小度技能-xiaodu_open_skill) | 按 `app_key` 打开小度技能 |

> 拍照/录像的并发限制、长任务的轮询方式、技能打开的两步流程等实践建议，见[使用建议](docs/tools.md#-使用建议)。

## 🧩 客户端示例

本仓库提供三个可直接运行的集成示例：

- [simple_chatbot](clients/simple_chatbot/README.md) — 直接调用 MCP Server 的最小示例
- [art_gallery_agent](clients/art_gallery_agent/README.md) — 在 LangGraph Agent 中调用 MCP Server
- [assistant_agent](clients/assistant_agent/README.md) — 综合助手 Agent 示例

## 📚 文档索引

- [接入指南](docs/integrations.md) — 各客户端 / Agent 的详细配置步骤
- [工具接口参考](docs/tools.md) — 全部工具的参数、返回值与使用建议

## 🙏 致谢

- [Model Context Protocol](https://modelcontextprotocol.io/) - MCP 协议标准
- [mcp-proxy](https://github.com/sparfenyuk/mcp-proxy) - MCP 代理工具
