# 工具接口参考

本文档是小度 MCP Server 全部工具的详细接口说明。工具能力概览见 [README](../README.md#%EF%B8%8F-工具一览)，接入配置见[接入指南](integrations.md)。

## 📋 工具目录

| 工具 | 功能 |
| --- | --- |
| [`list_user_devices`](#1-获取设备列表-list_user_devices) | 获取用户绑定的在线设备列表 |
| [`control_xiaodu`](#2-设备控制-control_xiaodu) | 通过自然语言指令控制小度设备 |
| [`xiaodu_speak`](#3-语音播报-xiaodu_speak) | 让小度设备朗读指定文本 |
| [`xiaodu_send_notification`](#4-发送通知-xiaodu_send_notification) | 向小度 App 或设备发送系统通知 |
| [`xiaodu_take_photo`](#5-设备拍照-xiaodu_take_photo) | 触发设备拍照并返回图像 |
| [`xiaodu_record_video`](#6-设备录像-xiaodu_record_video) | 异步创建录像任务 |
| [`xiaodu_record_audio`](#7-设备录音-xiaodu_record_audio) | 异步创建录音任务 |
| [`xiaodu_get_task`](#8-查询任务状态-xiaodu_get_task) | 统一查询长任务状态与结果 |
| [`xiaodu_trigger_ai_call`](#9-触发-ai-通话-xiaodu_trigger_ai_call) | 创建异步 AI 通话任务 |
| [`xiaodu_get_ai_call_task_status`](#10-查询-ai-通话任务状态-xiaodu_get_ai_call_task_status) | 查询 AI 通话任务状态 |
| [`push_resource_to_xiaodu`](#11-资源推送-push_resource_to_xiaodu) | 推送图片、视频、音频到设备 |
| [`xiaodu_open_web_page`](#12-打开网页-xiaodu_open_web_page) | 在屏幕设备上打开 HTTP/HTTPS 页面 |
| [`query_xiaodu_skills`](#13-查询小度技能-query_xiaodu_skills) | 查询当前设备可打开的小度技能 |
| [`xiaodu_open_skill`](#14-打开小度技能-xiaodu_open_skill) | 按 `app_key` 打开小度技能 |

---

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

### 4. 发送通知 (`xiaodu_send_notification`)

向小度 App 或指定小度设备发送系统通知。

#### 参数

- `target` (string, required)：通知目标，取值为 `app` 或 `device`
- `title` (string, required)：通知标题，最长 `100` 个字符
- `description` (string, required)：通知正文，最长 `1000` 个字符
- `url` (string, optional)：通知详情页链接，仅支持 `http` / `https`，最长 `2048` 个字符
- `cuid` (string, optional)：设备 CUID，`target=device` 时必填
- `client_id` (string, optional)：设备 client_id，`target=device` 时必填

#### 返回值

- `Dict[str, Any]`
  - `notification_id`：通知 ID
  - `status`：通知发送状态，可能为 `sent`、`failed` 或 `unknown`
  - `target`：通知目标，发送到设备时返回 `device`
  - `has_url`：本次通知是否携带详情链接
  - `message`：结果说明
  - `error_code`：失败时的错误码
  - `retryable`：失败时是否建议重试

---

### 5. 设备拍照 (`xiaodu_take_photo`)

触发支持摄像头的小度设备拍照并返回图像内容。

#### 参数

- `cuid` (string, required)：设备标识符
- `client_id` (string, required)：客户端标识符

#### 返回值

- `ImageContent`：图像内容对象
  - `data` (string)：Base64 编码的 JPEG 图像数据
  - `mimeType` (string)：固定为 `image/jpeg`

---

### 6. 设备录像 (`xiaodu_record_video`)

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

### 7. 设备录音 (`xiaodu_record_audio`)

创建 RTC 异步录音任务，并通过 `xiaodu_get_task` 查询最终音频地址。录音达到 `record_time_ms` 后自然结束，不支持主动停止。状态为 `succeeded` 时，从 `result.audio_url` 获取 MP3 格式的临时访问地址。

#### 参数

- `cuid` (string, required)：设备 CUID
- `client_id` (string, required)：设备 client_id
- `record_time_ms` (int, optional)：录制时长，单位毫秒，默认 `5000`，最大 `120000`

#### 返回值

- `Dict[str, Any]`
  - `status`：任务创建结果，成功时为 `queued`
  - `task_id`：录音任务 ID
  - `task_type`：当前为 `record_audio`
  - `progress`：初始进度，为 `0`
  - `record_time_ms`：录制时长，单位毫秒
  - `message`：结果说明

---

### 8. 查询任务状态 (`xiaodu_get_task`)

统一查询长任务状态。当前录像与录音任务均已接入该接口，后续新增长任务也会复用同一查询方式。

#### 参数

- `task_id` (string, required)：任务 ID（`xiaodu_record_video` 或 `xiaodu_record_audio` 返回的任务 ID）

#### 返回值

- `Dict[str, Any]`
  - `task_id`：任务 ID
  - `task_type`：任务类型（`record_video` 或 `record_audio`）
  - `status`：`queued` / `running` / `succeeded` / `failed` 等
  - `progress`：任务进度
  - `result`：任务结果。录像成功时包含 `video_url`、`file_size`、`record_time_ms`；录音成功时包含 `audio_url`、`file_size`、`record_time_ms`
  - `error`：任务失败时的错误信息

---

### 9. 触发 AI 通话 (`xiaodu_trigger_ai_call`)

创建异步 AI 通话任务。该接口只负责创建任务，不会等待通话完成；创建成功后需要保存返回的 `task_id`，并调用 `xiaodu_get_ai_call_task_status` 轮询任务状态。

#### 参数

- `client_id` (string, required)：目标小度设备的客户端标识符
- `cuid` (string, required)：目标小度设备的 CUID
- `target` (string, required)：通话对象的角色描述，最长 `64` 个字符
- `task_description` (string, required)：AI 通话需要完成的任务描述，最长 `500` 个字符

#### 返回值

- `Dict[str, Any]`
  - `task_id`：任务唯一标识，后续查询必须使用该值
  - `status`：任务状态，创建成功时通常为 `PENDING`；创建失败时可能直接为 `FAILED`
  - `err_code`：下游错误码，`0` 表示创建成功
  - `message`：结果说明

---

### 10. 查询 AI 通话任务状态 (`xiaodu_get_ai_call_task_status`)

查询 AI 通话任务状态。调用方应使用 `xiaodu_trigger_ai_call` 返回的同一个 `task_id` 持续轮询，直到任务进入 `COMPLETED` 或 `FAILED` 终态。

#### 参数

- `task_id` (string, required)：`xiaodu_trigger_ai_call` 返回的任务 ID，最长 `128` 个字符

#### 返回值

- `Dict[str, Any]`
  - `task_id`：任务 ID
  - `status`：任务状态，可能为 `PENDING`、`ACTIVE`、`PROCESSING`、`COMPLETED`、`FAILED`
  - `interaction_report`：通话完成后的交互报告，`status=COMPLETED` 时可能包含 `full_transcript`
  - `err_code`：失败或下游异常时的错误码
  - `message`：结果说明

---

### 11. 资源推送 (`push_resource_to_xiaodu`)

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

### 12. 打开网页 (`xiaodu_open_web_page`)

在指定小度屏幕设备上打开一个 HTML 页面。

#### 参数

- `url` (string, required)：要在设备上打开的页面地址，仅支持 `http` / `https`
- `cuid` (string, required)：设备 CUID
- `client_id` (string, required)：设备 client_id

#### 返回值

- `Dict[str, Any]`
  - `success`：是否成功下发打开指令
  - `message`：结果说明
  - `url`：本次打开的页面地址
  - `push_result`：PushService 下发结果，成功时返回

---

### 13. 查询小度技能 (`query_xiaodu_skills`)

查询当前 MCP 支持打开的小度技能列表。

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

---

### 14. 打开小度技能 (`xiaodu_open_skill`)

按 `app_key` 打开一个小度技能。

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

## 📌 使用建议

### 1. 拍照、录像与录音的并发建议

同一个用户如果对多款设备有拍照、录像或录音需求，请求方需要在多次请求之间串行执行，不建议并发触发多个媒体请求。

### 2. 录像与录音任务的使用方式

推荐按两步使用：

1. 调用 `xiaodu_record_video` 或 `xiaodu_record_audio` 创建任务并获取 `task_id`
2. 轮询调用 `xiaodu_get_task(task_id)` 获取状态和最终结果

### 3. 录制时长建议

- 默认录制时长为 `5000ms`
- 最大录制时长为 `120000ms`
- 录音达到 `record_time_ms` 后自然结束，不支持主动停止
- 建议优先使用短时长场景，避免不必要的长任务占用

### 4. AI 通话任务的使用方式

推荐按两步使用：

1. 调用 `xiaodu_trigger_ai_call` 创建任务并获取 `task_id`
2. 轮询调用 `xiaodu_get_ai_call_task_status(task_id)` 获取状态和最终结果

注意事项：

- `PENDING`、`ACTIVE`、`PROCESSING` 都不是终态，需要继续轮询。
- `COMPLETED` 和 `FAILED` 是终态，分别表示任务完成或失败。
- `COMPLETED` 时可读取 `interaction_report`，其中可能包含 `full_transcript`。

### 5. 技能打开的使用方式

推荐按两步使用：

1. 调用 `query_xiaodu_skills` 查询候选技能
2. 从返回结果中选择合适的 `app_key`，再调用 `xiaodu_open_skill`

注意事项：

- 不要手写或复用过期的 `app_key`，它是查询结果中的打开凭证。
- 如果打开时返回“应用选择已过期，请重新查询”，需要重新调用 `query_xiaodu_skills` 获取新的 `app_key`。
- 如果返回多个候选，应根据 `name` 和 `description` 让用户确认要打开哪一个。
