# 接入指南

本文档介绍如何在各类支持 MCP 的客户端 / Agent 中接入小度 MCP Server。

接入前请先完成 [README 快速开始](../README.md#-快速开始)中的准备工作，拿到 `access_token`。所有客户端共用同一组接入信息：

| 项目 | 值 |
| --- | --- |
| Server 地址 | `https://xiaodu.baidu.com/dueros_mcp_server/mcp/` |
| 传输协议 | StreamableHTTP |
| 鉴权方式 | 请求头 `ACCESS_TOKEN: ${your_access_token}` |

## 📋 目录

- [接入模式说明](#接入模式说明)
- [Cursor](#cursor)
- [Cherry Studio](#cherry-studio)
- [Claude Code](#claude-code)
- [OpenClaw](#openclaw)
- [Hermes](#hermes)
- [Claude Desktop（Stdio + mcp-proxy）](#claude-desktopstdio--mcp-proxy)
- [Cline（Stdio + mcp-proxy）](#clinestdio--mcp-proxy)
- [开发者自定义 Agent](#开发者自定义-agent)

## 接入模式说明

我们提供两种接入方式以满足不同场景的需求：

- **StreamableHTTP 接入（推荐）**：客户端直连 MCP Server，要求客户端支持 StreamableHTTP 并支持透传请求头。当前主流 Agent（Cursor、Cherry Studio、Claude Code、OpenClaw、Hermes 等）均已支持。
- **Stdio 接入**：客户端仅支持 stdio 时，通过本地代理 [mcp-proxy](https://github.com/sparfenyuk/mcp-proxy) 桥接到 MCP Server，适用于 Claude Desktop、Cline 等。

---

## Cursor

1. 打开 Cursor → 设置 → MCP & Integrations
2. 在 MCP Tools 配置项中添加：

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

3. 在会话中选择 Agent 模式开始使用

---

## Cherry Studio

1. 打开 Cherry Studio → 设置 → MCP 服务器
2. 添加新的 MCP 服务器：
   - **名称**：`xiaodu_mcp`
   - **类型**：`可流式传输的HTTP（streamableHttp）`
   - **URL**：`https://xiaodu.baidu.com/dueros_mcp_server/mcp/`
   - **请求头**：`ACCESS_TOKEN=${your_access_token}`
3. 启用服务器并开始使用

---

## Claude Code

在终端中执行一条命令即可完成添加：

```bash
claude mcp add --transport http xiaodu-mcp \
  "https://xiaodu.baidu.com/dueros_mcp_server/mcp/" \
  --header "ACCESS_TOKEN: your_access_token_here"
```

说明：

- 默认添加到当前项目（local 作用域）；追加 `--scope user` 可在所有项目中使用
- 在 Claude Code 会话中运行 `/mcp` 可查看连接状态和工具列表

---

## OpenClaw

[OpenClaw](https://docs.openclaw.ai/) 通过 `openclaw mcp` 命令管理外部 MCP 服务器。

**第一步：添加服务器**

```bash
openclaw mcp add xiaodu-mcp \
  --url "https://xiaodu.baidu.com/dueros_mcp_server/mcp/" \
  --transport streamable-http \
  --header "ACCESS_TOKEN: your_access_token_here"
```

也可以用 `openclaw mcp set` 直接写入 JSON 定义：

```bash
openclaw mcp set xiaodu-mcp '{"url":"https://xiaodu.baidu.com/dueros_mcp_server/mcp/","transport":"streamable-http","headers":{"ACCESS_TOKEN":"your_access_token_here"}}'
```

**第二步：验证连接**

```bash
# 静态检查 + 真实连接探测，会列出可用工具
openclaw mcp doctor xiaodu-mcp --probe
```

说明：

- 服务器定义保存在 OpenClaw 配置的 `mcp.servers` 下，由 OpenClaw 统一下发给其管理的 Agent 运行时
- 修改配置后可运行 `openclaw mcp reload` 刷新缓存的 MCP 运行时
- 如需限制暴露给 Agent 的工具范围，可用 `openclaw mcp tools xiaodu-mcp --include '<工具名列表>'`

详见 OpenClaw 官方文档：[MCP CLI](https://docs.openclaw.ai/cli/mcp)

---

## Hermes

[Hermes Agent](https://hermes-agent.nousresearch.com/)（Nous Research）在 `~/.hermes/config.yaml` 中通过 `mcp_servers` 块配置远程 MCP 服务器。

**第一步：编辑 `~/.hermes/config.yaml`**

```yaml
mcp_servers:
  xiaodu_mcp:
    url: "https://xiaodu.baidu.com/dueros_mcp_server/mcp/"
    headers:
      ACCESS_TOKEN: "your_access_token_here"
```

如果不想在配置文件中保存明文 token，可以把它写入 `~/.hermes/.env`（如 `XIAODU_ACCESS_TOKEN=xxx`），然后在配置中引用：

```yaml
mcp_servers:
  xiaodu_mcp:
    url: "https://xiaodu.baidu.com/dueros_mcp_server/mcp/"
    headers:
      ACCESS_TOKEN: "${XIAODU_ACCESS_TOKEN}"
```

**第二步：生效并验证**

- 新启动的 Hermes 会话会自动发现该服务器；已在会话中时运行 `/reload-mcp` 即可重新加载，无需重启
- Hermes 会给 MCP 工具统一加前缀注册：`mcp_<服务器名>_<工具名>`，例如设备控制工具注册为 `mcp_xiaodu_mcp_control_xiaodu`

详见 Hermes 官方文档：[MCP (Model Context Protocol)](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp)

---

## Claude Desktop（Stdio + mcp-proxy）

Claude Desktop 需要通过本地代理服务连接，这里推荐使用 [mcp-proxy](https://github.com/sparfenyuk/mcp-proxy)。

**第一步：安装代理服务**

```bash
# 方式1：使用 uv 安装（推荐）
uv tool install mcp-proxy

# 方式2：使用 pipx 安装
pipx install mcp-proxy

# 查看安装路径
which mcp-proxy
```

**第二步：配置 Claude Desktop**

编辑 `claude_desktop_config.json`：

```json
{
  "mcpServers": {
    "xiaodu_mcp": {
      "command": "/path/to/mcp-proxy",
      "args": [
        "https://xiaodu.baidu.com/dueros_mcp_server/mcp/",
        "--headers",
        "ACCESS_TOKEN",
        "your_access_token_here",
        "--transport",
        "streamablehttp"
      ]
    }
  }
}
```

---

## Cline（Stdio + mcp-proxy）

Cline 同样可以通过 mcp-proxy 桥接接入，配置方式与 [Claude Desktop](#claude-desktopstdio--mcp-proxy) 相同：先安装 mcp-proxy，再在 Cline 的 MCP 设置（`cline_mcp_settings.json`）中添加相同的 `command` / `args` 配置。

---

## 开发者自定义 Agent

如果你在自研 Agent 中集成小度 MCP，可参考本仓库提供的 [示例代码](../clients)：

- 直接调用 MCP Server：[simple_chatbot](../clients/simple_chatbot)
- 在 LangGraph Agent 中调用 MCP Server：[art_gallery_agent](../clients/art_gallery_agent)
- 综合助手 Agent：[assistant_agent](../clients/assistant_agent)

核心要点：使用支持 StreamableHTTP 的 MCP 客户端 SDK，连接上表中的 Server 地址，并在每个请求中携带 `ACCESS_TOKEN` 请求头。
