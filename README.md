# 小度智能终端 MCP Server

[![MCP](https://img.shields.io/badge/MCP-Compatible-blue)](https://modelcontextprotocol.io/)

一个基于 Model Context Protocol (MCP) 的小度智能终端服务，让 AI 应用能够控制小度设备。支持 Claude、Cursor、Cherry Studio、Cline 等兼容 MCP 协议的平台。

## ✨ 特性

- **开放式控制**：通过自然语言指令控制小度设备
- **语音播报**：让小度设备朗读指定文本
- **设备拍照**：触发支持摄像头的小度设备拍照并返回图像内容
- **设备录像**：异步创建录像任务并返回可查询结果
- **统一任务查询**：查询长任务执行状态与结果
- **设备管理**：获取用户绑定的在线设备列表
- **资源推送**：推送图片、视频、音频到小度设备
- **技能查询与打开**：查询当前设备可打开的小度技能，并按 `app_key` 下发打开指令

## 📋 目录

- [快速开始](#-快速开始)
- [接入方式](#-接入方式)
- [工具说明](#-工具说明)
- [使用建议](#-使用建议)
- [客户端示例](#-客户端示例)

## 🚀 快速开始

### 前提条件

- 百度开发者账号
- 小度智能设备
- 支持 MCP 的 AI 工具（Claude、Cursor、Cherry Studio、Cline 等）

### 获取访问令牌

1. 访问[百度开发者平台](https://developer.dueros.baidu.com/)
2. 按照[接入授权文档](https://developer.dueros.baidu.com/doc/dueros-bot-platform//mcp-server/prepare/auth-intro_markdown)获取 `access_token`
3. 保存好 `access_token`，后续配置时需要使用

## 🔌 接入方式

我们提供两种接入方式以满足不同场景的需求。

### 方式一：StreamableHTTP 接入

StreamableHTTP 模式直接连接到 MCP Server，要求客户端支持 StreamableHTTP 并支持透传请求头。

#### 支持的工具

- **Cursor** ✅（推荐）
- **Cherry Studio** ✅
- **自定义客户端** ✅

#### 配置步骤

**以 Cursor 为例：**

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

**以 Cherry Studio 为例：**

1. 打开 Cherry Studio → 设置 → MCP 服务器
2. 添加新的 MCP 服务器：
   - **名称**：`xiaodu_mcp`
   - **类型**：`可流式传输的HTTP（streamableHttp）`
   - **URL**：`https://xiaodu.baidu.com/dueros_mcp_server/mcp/`
   - **请求头**：`ACCESS_TOKEN=${your_access_token}`
3. 启用服务器并开始使用

**开发者自定义 Agent：**

1. 参考本代码库提供的 [Demo](clients)
2. 当前提供两类示例：
   - 直接调用 MCP Server：[simple_chatbot](clients/simple_chatbot)
   - 在 Agent 中调用 MCP Server：[art_gallery_agent](clients/art_gallery_agent)

### 方式二：Stdio 接入

Stdio 模式需要通过本地代理服务连接，这里推荐使用 [mcp-proxy](https://github.com/sparfenyuk/mcp-proxy)。

#### 支持的工具

- **Claude Desktop** ✅
- **Cline** ✅
- **其他支持 MCP 的工具** ✅

#### 配置步骤

**第一步：安装代理服务**

```bash
# 方式1：使用 uv 安装（推荐）
uv tool install mcp-proxy

# 方式2：使用 pipx 安装
pipx install mcp-proxy

# 查看安装路径
which mcp-proxy
```

**第二步：配置 AI 工具**

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

## 🛠️ 工具说明

当前 MCP Server 主要提供以下工具。

### 1. 获取设备列表 (`list_user_devices`)

获取与已验证用户关联且当前在线的设备列表。

#### 参数

- 无需参数

#### 返回值

- `List[Dict[str, Any]]`：设备信息列表

---

### 2. 设备控制 (`control_xiaodu`)

向小度设备发送语音指令，设备将像听到用户说话一样执行该指令。

#### 参数

- `command` (string, required)：要发送给设备的语音指令文本
- `cuid` (string, required)：设备标识符
- `client_id` (string, required)：客户端标识符

#### 返回值

- `string`：小度设备的响应或执行结果

---

### 3. 语音播报 (`xiaodu_speak`)

让小度设备朗读指定的文本内容。

#### 参数

- `text` (string, required)：要朗读的文本内容
- `cuid` (string, required)：设备标识符
- `client_id` (string, required)：客户端标识符

#### 返回值

- `string`：操作执行状态

---

### 4. 设备拍照 (`xiaodu_take_photo`)

触发支持摄像头的小度设备拍照并返回图像内容。

#### 参数

- `cuid` (string, required)：设备标识符
- `client_id` (string, required)：客户端标识符

#### 返回值

- `ImageContent`：图像内容对象
  - `data` (string)：Base64 编码的 JPEG 图像数据
  - `mimeType` (string)：固定为 `image/jpeg`

---

### 5. 设备录像 (`xiaodu_record_video`)

异步录制视频，并返回统一 task_id。该接口不会直接阻塞到录像完成，而是立即返回任务信息。

#### 参数

- `cuid` (string, required)：设备标识符
- `client_id` (string, required)：客户端标识符
- `record_time_ms` (int, optional)：录制时长，单位毫秒，默认 `5000`，最大 `120000`

#### 返回值

- `Dict[str, Any]`
  - `status`：任务创建结果
  - `task_id`：录像任务 ID
  - `task_type`：当前为 `record_video`
  - `message`：结果说明

---

### 6. 查询任务状态 (`xiaodu_get_task`)

统一查询长任务状态。当前录像任务已接入该接口，后续新增长任务也会复用同一查询方式。

#### 参数

- `task_id` (string, required)：任务 ID

#### 返回值

- `Dict[str, Any]`
  - `task_id`：任务 ID
  - `task_type`：任务类型
  - `status`：`queued` / `running` / `succeeded` / `failed`
  - `progress`：任务进度
  - `result`：任务结果。录像成功时包含 `video_url`、`file_size`、`record_time_ms`
  - `error`：任务失败时的错误信息

---

### 7. 资源推送 (`push_resource_to_xiaodu`)

推送图片、图片+背景音、视频、音频到小度设备。

#### 参数

- `resource_type` (string, required)：资源类型，支持 `image`、`image_with_bgm`、`video`、`audio`
- `cuid` (string, required)：设备 CUID
- `client_id` (string, required)：设备 client_id
- `image_url` (string, required)：图片地址（`image` / `image_with_bgm` 必填）
- `bgm_url` (string, required)：背景音地址（`image_with_bgm` 必填）
- `video_url` (string, required)：视频地址（`video` 必填）
- `audio_url` (string, required)：音频地址（`audio` 必填）
- `timeout` (int, optional)：超时时间（秒）

---

### 8. 查询小度技能 (`query_xiaodu_skills`)

查询当前 MCP 支持打开的小度技能列表。该工具用于把用户的自然语言描述转换为可打开技能候选，模型应根据返回的名称和简介选择合适的 `app_key`，再调用 `xiaodu_open_skill` 打开。

#### 参数

- `query` (string, required)：查询词，不允许为空。可以是用户提到的应用名、技能名；如果按类型查找，必须使用精确类型 key，例如 `生活`、`游戏`、`教育`、`音乐`、`视频`
- `cuid` (string, required)：设备 CUID
- `client_id` (string, required)：设备 client_id
- `page` (int, optional)：页码，默认 `1`
- `page_size` (int, optional)：每页数量，默认 `10`，最大 `20`

#### 返回值

- `List[Dict[str, Any]]`：技能候选列表。每个候选至少包含：
  - `app_key`：打开技能时使用的唯一标识
  - `name`：技能名称
  - `description`：技能简介
  - `disabled`：技能是否处于禁用状态
  - 可能还包含 `icon`、`skill_type`、`package_name`、`external` 等展示辅助字段

#### 示例

```python
skills = await client.call_tool("query_xiaodu_skills", {
    "query": "音乐",
    "cuid": "your_device_cuid",
    "client_id": "your_device_client_id",
    "page": 1,
    "page_size": 10
})
```

---

### 9. 打开小度技能 (`xiaodu_open_skill`)

按 `app_key` 打开一个小度技能。`app_key` 必须来自 `query_xiaodu_skills` 的查询结果，服务端会根据该 `app_key` 找回打开凭证，并向指定小度设备发送技能打开指令。

#### 参数

- `app_key` (string, required)：`query_xiaodu_skills` 返回的技能 key
- `cuid` (string, required)：设备 CUID
- `client_id` (string, required)：设备 client_id

#### 返回值

- `Dict[str, Any]`
  - `success`：是否成功下发打开指令
  - `message`：结果说明
  - `app_key`：本次打开使用的技能 key
  - `name`：技能名称
  - `push_result`：PushService 下发结果

#### 示例

```python
result = await client.call_tool("xiaodu_open_skill", {
    "app_key": "market:query_session_id:item_key",
    "cuid": "your_device_cuid",
    "client_id": "your_device_client_id"
})
```

## 📌 使用建议

### 1. 拍照与录像的并发建议

同一个用户如果对多款设备有拍照或录像需求，请求方需要在多次请求之间串行执行，不建议并发触发多个媒体请求。

### 2. 录像任务的使用方式

推荐按两步使用：

1. 调用 `xiaodu_record_video` 创建任务并获取 `task_id`
2. 轮询调用 `xiaodu_get_task(task_id)` 获取状态和最终结果

### 3. 录像时长建议

- 默认录制时长为 `5000ms`
- 最大录制时长为 `120000ms`
- 建议优先使用短视频场景，避免不必要的长任务占用

### 4. 技能打开的使用方式

推荐按两步使用：

1. 调用 `query_xiaodu_skills` 查询候选技能
2. 从返回结果中选择合适的 `app_key`，再调用 `xiaodu_open_skill`

注意事项：

- 不要手写或复用过期的 `app_key`，它是查询结果中的打开凭证。
- 如果打开时返回“应用选择已过期，请重新查询”，需要重新调用 `query_xiaodu_skills` 获取新的 `app_key`。
- 如果返回多个候选，应根据 `name` 和 `description` 让用户确认要打开哪一个。

## 客户端示例

- [clients/simple_chatbot/README.md](clients/simple_chatbot/README.md)
- [clients/art_gallery_agent/README.md](clients/art_gallery_agent/README.md)
- [clients/assistant_agent/README.md](clients/assistant_agent/README.md)

## 🙏 致谢

- [Model Context Protocol](https://modelcontextprotocol.io/) - MCP 协议标准
- [mcp-proxy](https://github.com/sparfenyuk/mcp-proxy) - MCP 代理工具
