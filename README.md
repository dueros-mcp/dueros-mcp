# 小度智能终端 MCP Server 

[![MCP](https://img.shields.io/badge/MCP-Compatible-blue)](https://modelcontextprotocol.io/)

一个基于 Model Context Protocol (MCP) 的小度智能终端服务，让AI应用能够无缝控制小度设备。支持Claude、Cursor、Cline等所有兼容MCP协议的平台。

## ✨ 特性

- 🎯 **开放式控制** - 通过自然语言指令控制小度设备
- 🔊 **语音播报** - 让小度设备朗读指定文本
- 📸 **实时拍照** - 获取支持摄像头的小度设备的实时图像
- 📱 **设备管理** - 获取用户绑定的在线设备列表

## 📋 目录

- [快速开始](#-快速开始)
- [接入方式](#-接入方式)
- [工具说明](#-工具说明)

## 🚀 快速开始

### 前提条件

- 百度开发者账号
- 小度智能设备
- 支持MCP的AI工具（Claude、Cursor、Cline等）

### 获取访问令牌

1. 访问[百度开发者平台](https://developer.dueros.baidu.com/)
2. 按照[接入授权文档](https://developer.dueros.baidu.com/doc/dueros-bot-platform//mcp-server/prepare/auth-intro_markdown)获取`access_token`
3. 保存好您的`access_token`，后续配置时需要使用

## 🔌 接入方式

我们提供两种接入方式以满足不同场景的需求：

### 方式一：SSE 接入（推荐开发者）

SSE（Server-Sent Events）模式直接连接到我们的服务器，配置简单，适合开发者使用。

#### 支持的工具
- **Cherry Studio** ✅（推荐，支持请求头配置）
- **自定义客户端** ✅

#### 配置步骤

**以 Cherry Studio 为例：**

1. 打开 Cherry Studio → 配置 → MCP服务器
2. 添加新的MCP服务器：
   - **名称**: `xiaodu_mcp`
   - **URL**: `https://xiaodu.baidu.com/dueros_mcp_server/sse`
   - **请求头**: `ACCESS_TOKEN=${your_access_token}`

3. 启用服务器并开始使用

### 方式二：Stdio 接入（推荐AI工具）

Stdio模式通过本地代理服务连接，兼容性更强，适合各种AI工具使用。

#### 支持的工具
- **Cursor** ✅
- **Claude Desktop** ✅
- **Cline** ✅
- **其他支持MCP的工具** ✅

#### 配置步骤

**第一步：安装代理服务**

使用开源项目 [mcp-proxy](https://github.com/sparfenyuk/mcp-proxy)：

```bash
# 方式1：使用uv安装（推荐）
uv tool install mcp-proxy

# 方式2：使用pipx安装
pipx install mcp-proxy

# 查看安装路径
which mcp-proxy
```

**第二步：配置AI工具**

**以 Cursor 为例：**

1. 打开 Cursor → 设置 → MCP
2. 编辑 `mcp.json` 配置文件：

```json
{
  "mcpServers": {
    "xiaodu_mcp": {
      "command": "/Users/.local/bin/mcp-proxy",
      "args": [
        "https://xiaodu.baidu.com/dueros_mcp_server/sse",
        "--headers",
        "ACCESS_TOKEN",
        "your_access_token_here"
      ]
    }
  }
}
```

3. 保存配置，重启Cursor
4. 在会话中选择 **Agent** 模式开始使用

**Claude Desktop 配置示例：**

编辑 `claude_desktop_config.json`：

```json
{
  "mcpServers": {
    "xiaodu_mcp": {
      "command": "/path/to/mcp-proxy",
      "args": [
        "https://xiaodu.baidu.com/dueros_mcp_server/sse",
        "--headers",
        "ACCESS_TOKEN",
        "your_access_token_here"
      ]
    }
  }
}
```

## 🛠️ 工具说明

本MCP服务器提供以下4个工具，让您能够完全控制小度智能设备：

### 1. 获取设备列表 (`list_user_devices`)

获取与已验证用户关联且当前在线的设备列表。

#### 参数
- 无需参数

#### 返回值
- `List[Dict[str, Any]]`: 设备信息列表

---

### 2. 设备控制 (`control_xiaodu`)

向小度设备发送语音指令，设备将像听到用户说话一样执行该指令。

#### 参数
- `command` (string, required): 要发送给设备的语音指令文本
- `userid` (string, required): 用户标识符
- `cuid` (string, required): 设备标识符
- `client_id` (string, required): 客户端标识符

#### 返回值
- `string`: 小度设备的响应或执行结果

---

### 3. 语音播报 (`xiaodu_speak`)

让小度设备朗读指定的文本内容。

#### 参数
- `text` (string, required): 要朗读的文本内容
- `userid` (string, required): 用户标识符
- `cuid` (string, required): 设备标识符
- `client_id` (string, required): 客户端标识符

#### 返回值
- `string`: 操作执行状态

---

### 4. 设备拍照 (`xiaodu_take_photo`)

触发支持摄像头的小度设备进行拍照并返回图像内容。

#### 参数
- `userid` (string, required): 用户标识符
- `cuid` (string, required): 设备标识符
- `client_id` (string, required): 客户端标识符

#### 返回值
- `ImageContent`: 图像内容对象
  - `content` (string): Base64编码的JPEG格式图像数据
  - `content_type` (string): 图像内容类型，固定为 "image/jpeg"

## 🙏 致谢

- [百度DuerOS](https://dueros.baidu.com/) - 提供小度智能设备平台支持
- [Model Context Protocol](https://modelcontextprotocol.io/) - MCP协议标准
- [mcp-proxy](https://github.com/sparfenyuk/mcp-proxy) - 优秀的MCP代理工具
- 所有为本项目做出贡献的开发者和用户

