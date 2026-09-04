---
name: xiaodu-elder-companion
description: Execute Xiaodu elder-care companion workflows safely and consistently. Use this skill when a user asks Codex to accompany an elder through Xiaodu MCP, check an elder location/status with transparent photo notice, speak to a Xiaodu device, set stand-up and eye-relax reminders, recommend elder-friendly apps from agent memory, query/open Xiaodu skills or apps such as 梨园行戏曲HD, or validate elder-care MCP call plans. Use mcporter first and bundled scripts for routing, planning, and validation; avoid ad hoc command construction and never route Xiaodu requests to unrelated MCP servers.
---

# Xiaodu Elder Companion

Use this skill for Xiaodu elder-care companion work. Keep routing strict: Xiaodu requests must go to the Xiaodu MCP server/tools only. Use `mcporter` first for both MCP discovery and MCP invocation whenever it is installed and the Xiaodu server/tools are reachable through it. Use this skill's scripts for reusable call plans and validation instead of hand-writing fragile commands.

## Core Rules

- Discover devices before device-specific actions unless the user already provided a specific `cuid` and `client_id`.
- If multiple online devices match, auto-select when there is a clear signal such as one camera-capable device, a previously successful device, a device named by the user, or an elder-care location photo. Ask the user to choose only when available signals are insufficient or conflict.
- Do not call unrelated MCP servers for Xiaodu tasks.
- Do not invent `app_key`, `cuid`, `client_id`, `push_ack_token`, package names, or server names.
- For opening Xiaodu skills/apps, always call `query_xiaodu_skills` first and open only with the returned `app_key`.
- Do not use `package_name`, display name, or stale `app_key` as an opening key.
- Never expose `push_ack_token`; it is server-side only.
- For device-location photos in elder-care flows, use the shortest transparent notice before capture, then speak the full companion message only on the device where the elder is found. For other photo or video actions, speak a short notice before capture unless the user explicitly asked for silent device-side behavior and policy allows it.
- Do not make medical, safety, or diagnostic claims from photos. Use low-risk status wording only.

## Preferred Workflow

1. Identify intent: device control, speak, skill/app open, media push, photo, video, or companion flow.
2. Route to Xiaodu MCP only. Check `mcporter` availability and discover Xiaodu tools before any direct MCP tool call.
3. Use `scripts/plan_xiaodu_workflow.py` to produce a call plan for common workflows.
4. Execute MCP tools in the planned order through `mcporter call <server>.<tool>` when discovery shows a reachable Xiaodu server/tool. Do not skip required device selection or query-before-open steps.
5. Summarize what was sent, opened, pushed, captured, or scheduled. Mention any blocked step.

## mcporter First

- Before the first Xiaodu MCP action in a turn, check whether `mcporter` is available, for example with `command -v mcporter`.
- If `mcporter` is available, discover Xiaodu servers/tools with `mcporter list --schema` or `mcporter list --json` before invoking tools.
- Treat discovery as successful only when a Xiaodu server is reachable and exposes the needed tools, such as `list_user_devices`, `xiaodu_speak`, `xiaodu_take_photo`, `control_xiaodu`, `query_xiaodu_skills`, and `xiaodu_open_skill`.
- When discovery succeeds, invoke Xiaodu tools through `mcporter call <server>.<tool> key=value ...`; do not use direct `mcp__xaiodu_demo.*` calls for that step.
- When invoking through `mcporter`, still follow this skill's required order: device discovery, location photo before full companion speech for elder-care flows, query-before-open, and reminder-before-entertainment.
- Fall back to the already exposed `mcp__xaiodu_demo.*` tools only if `mcporter` is missing, the Xiaodu server is offline/unreachable, the needed tool is not exposed, auth fails, or `mcporter call` fails for that specific action.
- When falling back, state the reason briefly in the final summary, for example: `mcporter xaiodu-demo offline: connect EPERM`, then continue with direct MCP tools when available.
- Do not use `mcporter` to route Xiaodu requests to unrelated MCP servers.

## Tool Routing

Use these Xiaodu MCP tools when available:

- `list_user_devices`: get online Xiaodu devices. Auto-select when a single viable device, user-named device, previous-success device, or elder-care location photo gives a clear target; ask only when still ambiguous.
- `xiaodu_speak`: speak text on a selected device.
- `control_xiaodu`: send a natural-language command, such as setting reminders or timers.
- `query_xiaodu_skills`: search application-market Xiaodu skills/apps by exact app name or exact type key such as `音乐`, `视频`, `生活`, `教育`, `游戏`.
- `xiaodu_open_skill`: open a candidate using the `app_key` returned by `query_xiaodu_skills`.
- `push_resource_to_xiaodu`: push image, image with BGM, video, or audio resources.
- `xiaodu_take_photo`: take a photo after device notice when appropriate. If it returns inline Base64 image content that is too long to inspect in terminal output, save the raw output to `/private/tmp/<name>.txt`, run `scripts/decode_photo_result.py /private/tmp/<name>.txt -o /private/tmp/<name>.jpg`, then inspect the decoded image before making a location decision.
- `xiaodu_record_video`: record video after device notice when appropriate.
- `xiaodu_record_audio`: record audio after device notice when appropriate.
- `xiaodu_get_task`: poll async photo/video/audio task status when needed.

## Opening Skills or Apps

Use this sequence exactly:

1. `list_user_devices` if no concrete device is selected.
2. `query_xiaodu_skills(query=<app name or exact type key>, cuid=<cuid>, client_id=<client_id>)`.
3. If one strong candidate is suitable, call `xiaodu_open_skill(app_key=<returned app_key>, cuid=<cuid>, client_id=<client_id>)`.
4. If multiple candidates are plausible, auto-select the best candidate when one has an exact name match, is not disabled, and best fits the user's scenario; ask the user only when candidates are equally plausible or introduce extra risk such as payment, login, privacy impact, or high interaction burden.
5. If no candidate appears, report that no suitable openable skill was found.

Valid type-key examples: `音乐`, `视频`, `生活`, `教育`, `游戏`.

## Elder-Care Companion Flow

For requests like "小度，我爸一个人在家，你帮我陪陪他", use the elder-care workflow. Read `references/elder-care-companion.md` when executing or modifying this flow.

Default flow:

1. List online Xiaodu devices, preferring screen/camera devices.
2. For each plausible device, speak only the shortest transparent location notice:
   `我先确认一下家人在不在这边。`
3. Take a photo with `xiaodu_take_photo` to determine whether the elder is physically present near that device. If multiple devices are plausible, check them serially and choose the device whose photo clearly shows the target elder as a live person in the room. Do not treat a face shown on a device screen, album page, framed photo, poster, TV/video, or other reproduced image as confirmation that the elder is physically present.
4. If no device clearly shows the elder as a live person in the room, prefer the last successful or only viable device for a low-disturbance flow and report that physical presence was not clearly confirmed. Ask the requester to choose only when there is no usable fallback or multiple conflicting signals.
5. If the image is clearly abnormal or cannot be safely interpreted, stop app opening and report cautiously.
6. Choose the companion App from agent memory first. Use remembered elder preferences such as 戏曲、豫剧、京剧、评书、相声、老歌、广播、新闻、广场舞, recently opened elder-care apps, and requester-provided family preferences. If memory gives a clear preferred App, use that exact app name as the first query.
7. If memory is missing or ambiguous, use the curated high-quality App pool. For opera preference, prefer `梨园行戏曲HD` first.
8. Speak a low-disturbance companion message on the selected device that says the reminder will be set before entertainment starts and names the selected App, for example:
   `阿姨，我先给您设置一下：30 分钟后提醒您站立活动一下身体并放松眼睛。然后再帮您打开梨园行戏曲HD，您可以听您喜欢的戏曲。`
9. Set a reminder with `control_xiaodu`, e.g. `半小时后提醒我站立活动一下身体并放松眼睛`.
10. Search by exact app name first, such as `梨园行戏曲HD`; if unavailable, fall back by type: `音乐`, then `视频`, then `生活`.
11. Prefer remembered or curated Apps when returned and openable. Otherwise choose low-burden candidates for elder users: opera, old songs, storytelling, crosstalk, radio, light music; avoid complex or high-interaction apps.
12. Open with `xiaodu_open_skill` using the returned `app_key` on the selected device.
13. Tell the requester what was completed, including which device was selected, whether a live in-room elder was clearly confirmed, and whether the App came from memory or fallback.

## Bundled Scripts

- `scripts/plan_xiaodu_workflow.py`: generate a deterministic JSON call plan for common Xiaodu workflows. Run it before executing multi-step Xiaodu tasks.
- `scripts/validate_xiaodu_plan.py`: validate a call plan for query-before-open, server/tool naming, and unsafe opening keys.
- `scripts/decode_photo_result.py`: decode raw `xiaodu_take_photo` mcporter output containing inline Base64 image data into an inspectable image file.

Example:

```bash
python3 scripts/plan_xiaodu_workflow.py elder-care --device-name 小度智能屏3 --elder female --preference 戏曲 --preferred-app 梨园行戏曲HD
python3 scripts/validate_xiaodu_plan.py /tmp/xiaodu-plan.json
python3 scripts/decode_photo_result.py /private/tmp/xiaodu-photo.txt -o /private/tmp/xiaodu-photo.jpg
```

## References

- `references/elder-care-companion.md`: full elder-care companion flow, phrasing, app type strategy, and fallbacks.
