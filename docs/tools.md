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
| [`xiaodu_play_music`](#13-播放音乐-xiaodu_play_music) | 按条件或指定歌单播放音乐 |
| [`query_xiaodu_skills`](#14-查询小度技能-query_xiaodu_skills) | 查询当前设备可打开的小度技能 |
| [`xiaodu_open_skill`](#15-打开小度技能-xiaodu_open_skill) | 按 `app_key` 打开小度技能 |
| [`xiaodu_get_device_status`](#16-查询设备状态-xiaodu_get_device_status) | 查询设备当前的屏幕、媒体播放、音量、模式设置和摄像头状态 |
| [`xiaodu_list_device_history`](#17-查询设备历史-xiaodu_list_device_history) | 查询设备最近的交互记录，支持按时间范围筛选 |

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

### 13. 播放音乐 (`xiaodu_play_music`)

在指定小度设备上播放音乐。支持按歌手、歌名、风格进行条件播放，也支持按指定顺序播放歌单；两种模式不能同时使用。本次播放会替换设备当前的播放列表，条件播放无匹配曲目时设备将保持静默。

#### 参数

- `cuid` (string, required)：设备 CUID
- `client_id` (string, required)：设备 client_id
- `singer` (array[string], optional)：歌手列表，支持多个歌手
- `song` (string, optional)：歌名
- `tag` (string, optional)：音乐风格或主题
- `playlist` (array[object], optional)：按顺序播放的歌曲列表，最多 `20` 项；每项支持 `song`、`singer`，且至少填写一个字段

使用条件播放时，`singer`、`song`、`tag` 至少填写一项；使用列表播放时，仅填写 `playlist`。

#### 返回值

- `Dict[str, Any]`
  - `success`：是否成功下发播放指令
  - `message`：结果说明
  - `mode`：播放模式，条件播放为 `play`，列表播放为 `batch`
  - `conditions`：条件播放时返回归一化后的播放条件
  - `playlist`：列表播放时返回归一化后的歌曲列表
  - `push_result`：PushService 下发结果，成功时返回

---

### 14. 查询小度技能 (`query_xiaodu_skills`)

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

### 15. 打开小度技能 (`xiaodu_open_skill`)

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

---

### 16. 查询设备状态 (`xiaodu_get_device_status`)

查询指定小度设备此刻的状态，用于了解设备当前在做什么，以及判断后续操作是否可能打断用户。接口等待设备上报后直接返回状态快照，无需轮询任务接口。

#### 参数

- `cuid` (string, required)：设备 CUID
- `client_id` (string, required)：设备 client_id

#### 返回值

- `Dict[str, Any]`
  - `success`：是否成功获取设备状态
  - `observed_at`：设备上报状态的 Unix 时间戳，单位秒；未上报时为 `null`
  - `summary`：状态的文字概括
  - `screen`：屏幕状态，包含 `on`（是否亮屏）、`display_mode`（显示模式）、`foreground_package`（前台应用包名）、`foreground_activity`（前台页面）
  - `audio`：音频播放状态，包含 `activity`（播放状态）、`offset_ms`（播放进度，毫秒）、`source`（来源技能 ID）、`content`（音频内容）
  - `video`：视频播放状态，包含 `activity`、`offset_ms`、`source`、`content`
  - `long_video`：已接入的长视频 App 播放状态，包含 `activity`、`player_status`（播放器状态）、`offset_ms`、`source`、`content`
  - `local_audio`：蓝牙等本地播放状态，包含 `activity`、`player`（播放器名称）、`status`（播放器状态）
  - `speech`：语音播报状态，当前固定为 `null`
  - `volume`：音量状态，包含 `level`（设备音量值）、`muted`（是否静音）
  - `settings`：模式设置，包含 `do_not_disturb`（勿扰）、`sleep_protect`（睡眠保护）、`child_mode`（儿童模式）、`elder_mode`（长辈模式）、`desktop_mode`（桌面模式）
  - `camera`：摄像头状态，包含 `on`（是否开启）、`occluded`（是否遮挡；关闭或未上报时为 `null`）
  - `message`：查询失败时的结果说明；设备超时未返回状态时会提示稍后重试

除 `success` 和失败时的 `message` 外，上述字段在查询成功时返回。设备未上报的模块为 `null`，不表示该功能已关闭；媒体内容无法解析时 `content` 为 `null`，不影响状态查询成功。

#### 媒体状态与内容

- `activity` 的常见值为 `PLAYING`（正在播放）、`PAUSED`（已暂停）、`STOPPED`（已停止）、`FINISHED`（已播完）、`BUFFER_UNDERRUN`（缓冲中）、`SCHEDULED_STOP`（即将停止）、`IDLE`（空闲）。
- `audio.content`：音乐来源 `audio_music` 返回 `title`（歌名）、`artists`（歌手列表）、`song_id`（歌曲 ID）；有声来源 `audio_unicast` 返回 `title`（节目名）、`artists`（主播列表）、`album`（专辑）。
- `video.content`：目前仅支持小度短视频来源 `ai.dueros.bot.short_video`，包含 `title`（标题）、`uploader`（作者）、`category`（分类）、`tags`（标签列表）、`duration_ms`（时长，毫秒）。
- `long_video.content`：包含 `title`（当前播放名称，电视剧可带集数）、`series`（剧名）、`episode`（集数）、`category`（类型）、`genres`（题材列表）、`directors`（导演列表）、`actors`（演员列表，最多 `5` 位）、`duration_ms`（时长，毫秒）、`provider`（内容提供方）。

---

### 17. 查询设备历史 (`xiaodu_list_device_history`)

查询指定小度设备最近的交互记录，了解用户问过什么、小度的回复，以及点播内容、打开应用等交互。记录按写入时间从新到旧返回，支持按时间范围筛选；接口直接返回查询结果，无需轮询。

#### 参数

- `cuid` (string, required)：设备 CUID
- `client_id` (string, required)：设备 client_id
- `limit` (int, optional)：最多返回的条数，默认 `20`，取值限制在 `1` 至 `50`；超出范围时按边界值处理
- `start_time` (string, optional)：开始时间，包含该时间；支持 `YYYY-MM-DD HH:MM:SS`、`YYYY-MM-DD HH:MM`、`YYYY-MM-DD`，无时区时按北京时间处理，也接受带时区的 ISO 8601；不传则不限制开始时间
- `end_time` (string, optional)：结束时间，不包含该时间，格式与 `start_time` 相同；不传则不限制结束时间

时间范围按记录写入时间筛选。同时传入 `start_time` 和 `end_time` 时，开始时间必须早于结束时间；时间格式错误或范围无效时返回 `success=false` 和说明信息。

#### 返回值

- `Dict[str, Any]`
  - `success`：查询是否成功
  - `count`：实际返回的记录条数，成功时返回
  - `items`：交互记录列表，成功时返回；没有可展示的记录时为空列表
  - `message`：查询失败、没有可展示的记录，或指定时间范围可能存在已清理记录时的说明信息，按需返回

#### 记录字段

- `time`：交互时间，格式为 `YYYY-MM-DD HH:MM:SS`，北京时间
- `timestamp`：交互时间的 Unix 时间戳，单位秒；缺失时回退为记录写入时间
- `initiator`：发起方，`user` 表示可确定由用户发起，`unknown` 表示无法判断
- `trigger`：触发方式，取值为 `voice`（语音）、`text`（文本指令）、`click`（触屏点击）、`app_open`（打开应用）、`event`（其他事件）
- `query`：用户请求或指令文本
- `skill`：处理请求的技能 ID，与 `xiaodu_get_device_status` 中的 `source` 含义一致
- `reply`：小度的回复文本，超过 `200` 个字符时截断并追加省略号
- `card`：屏幕卡片信息，可包含 `title`（标题）、`text`（正文，超过 `100` 个字符时截断并追加省略号）；与回复相同的正文不重复返回
- `media`：涉及的音视频信息，包含 `type`（媒体类型）、`title`（标题），以及按内容类型返回的 `artists`（歌手或主播列表）、`album`（专辑）、`duration_ms`（时长，毫秒）、`category`（分类）、`provider`（内容提供方）；长视频还可能包含 `episode`、`genres`、`actors`（最多 `5` 位）、`directors`
- `app`：打开的应用，可包含 `name`（应用名称）、`package`（应用包名）
- `click_target`：触屏点击的目标名称
- `summary`：该条交互的一句话概括

记录中没有值的字段会被省略。`media.type` 支持 `music`（音乐）、`unicast`（有声）、`short_video`（短视频）、`news`（新闻）、`long_video`（长视频）、`radio`（电台），以及 `audio` / `video`（未细分的音频 / 视频）。

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

### 5. 音乐播放模式的选择

- 用户按歌手、歌名、风格或主题描述播放需求时，使用条件播放，只填写 `singer`、`song`、`tag` 中能够确定的字段。
- 用户明确指定多首歌曲且在意播放顺序时，使用列表播放，只填写 `playlist`。
- 条件参数与 `playlist` 不能同时填写，不要补充用户未提及的歌手、歌名或风格。

### 6. 技能打开的使用方式

推荐按两步使用：

1. 调用 `query_xiaodu_skills` 查询候选技能
2. 从返回结果中选择合适的 `app_key`，再调用 `xiaodu_open_skill`

注意事项：

- 不要手写或复用过期的 `app_key`，它是查询结果中的打开凭证。
- 如果打开时返回“应用选择已过期，请重新查询”，需要重新调用 `query_xiaodu_skills` 获取新的 `app_key`。
- 如果返回多个候选，应根据 `name` 和 `description` 让用户确认要打开哪一个。

### 7. 设备状态的解读

- 通过 `list_user_devices` 获取目标设备的 `cuid` 和 `client_id`，再调用 `xiaodu_get_device_status` 查询当前状态。
- 结果仅代表 `observed_at` 对应时刻的快照，状态随时可能变化，不能将其作为之前某次操作的执行结果。
- 媒体状态仅覆盖小度自带播放器、已接入的长视频 App 和蓝牙等本地播放。快手等第三方 App 的播放可能不会上报，即使该 App 是通过小度技能打开的；播放器均为空闲或 `summary` 未提及媒体时，仍需结合 `screen.foreground_package` 判断，不能断定设备没有播放内容。
- 小度短视频暂停后的 `activity` 为 `STOPPED`，无法区分暂停与停止；长视频 App 暂停时 `activity` 仍可能为 `PLAYING`，无法据此判断是否暂停。
- `long_video` 仅在已接入的长视频 App 处于前台时上报，退到后台或退出后为 `null`。

### 8. 设备历史的查询与解读

- 了解设备最近发生过什么时使用 `xiaodu_list_device_history`；了解设备此刻在做什么时使用 `xiaodu_get_device_status`。
- 查询最近的交互时只需指定 `limit`，用户关注具体时间段时再传入 `start_time`、`end_time`。设备仅保留最近 `50` 条原始记录，接口会过滤空记录等不可展示内容，返回条数可能少于 `limit`；扩大时间范围或提高 `limit` 无法恢复已清理记录。
- `initiator=unknown` 不表示一定由用户发起。文本指令可能来自 `control_xiaodu`，打开应用可能来自 `xiaodu_open_skill`；设备控制类请求通常没有 `reply`，不能仅凭 `query` 认定操作已执行成功。
- 点播或切换时，`media` 表示新内容；停止播放时，`media` 可能是被停止的内容，不能据此认定设备仍在播放。
- `xiaodu_play_music`、`xiaodu_speak`、资源推送、发送通知、打开网页等 MCP 指令，以及按键、触屏暂停等设备本地操作、歌单自动切歌和播放进度，不在记录覆盖范围内。没有记录不代表操作没有发生。
