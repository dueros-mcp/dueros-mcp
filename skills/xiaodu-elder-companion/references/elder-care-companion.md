# 老人安心陪伴参考

## Trigger

Use this reference for requests such as:

```text
小度，我爸一个人在家，你帮我陪陪他。
小度，我妈一个人在家，你帮我安排点不费劲的事。
```

## Goal

Turn a vague family-care request into a safe Xiaodu MCP flow:

```text
确认在线设备 -> 逐台拍照定位 -> 选定老人所在设备 -> 轻声问候并说明安排 -> 设置提醒 -> 类型检索 App -> 打开陪伴内容 -> 反馈结果
```

The user does not need to name an app. The elder does not need to choose during the flow.

## Confirmation Reduction

Default to automatic decisions and summarize them afterward. Do not interrupt the requester for routine choices.

- Device choice: auto-select when there is one viable online device, a user-named device, a previous successful device, or a clear location photo.
- App choice: auto-select exact-name, not-disabled, low-burden candidates such as opera, old songs, storytelling, crosstalk, radio, and light music.
- Ask the requester only when photos are concerning, no usable device fallback exists, multiple devices show different plausible elders, candidates are equally plausible, or the action may involve payment, login, privacy impact, or high interaction burden.

## Tool Invocation Route

For execution, use `mcporter` first, not direct MCP calls:

1. Run `command -v mcporter`.
2. Run `mcporter list --schema` or `mcporter list --json` and locate the reachable Xiaodu server plus required tools.
3. Invoke each Xiaodu step with `mcporter call <server>.<tool> key=value ...`.
4. Use direct `mcp__xaiodu_demo.*` tools only when `mcporter` is unavailable, the Xiaodu server/tool is unreachable, auth fails, or that `mcporter call` fails.
5. If fallback is used, report the reason in the requester summary.

## Location Photo Notice

For elder-care device selection, take location photos before the full companion speech. Before each location photo, speak only:

```text
我先确认一下家人在不在这边。
```

After the photo identifies the elder as a live person physically present near a device, use the selected device for all later speech, reminders, and app opening. Adapt later companion wording from `叔叔` to `阿姨` when the user's wording indicates mother or another female elder.

## Photo Handling

Only make low-risk observations:

- If the elder appears as a live person physically present in the room on one device: select that device and continue.
- Do not treat a face shown on a device screen, phone/tablet display, album page, framed photo, poster, TV/video, app image, or other reproduced image as confirmation that the elder is physically present.
- If a reproduced elder image is visible but no live elder is visible: do not claim the elder is there; continue only with uncertainty wording or ask the requester to choose/check.
- If multiple devices show people: choose automatically only when the target elder is clearly visible as a live in-room person or one device is clearly more suitable; otherwise ask the requester to choose.
- If the elder is not visible as a live in-room person on any checked device: prefer the last successful or only viable device for a low-disturbance flow and report that physical presence was not clearly confirmed. If no usable fallback exists, ask the requester to choose.
- If image is unclear: check other plausible devices and report uncertainty.
- If something appears clearly concerning: stop app opening and ask requester to check directly.

Do not diagnose illness, falls, or medical status.

## App Recommendation From Agent Memory

Before choosing an App, inspect available agent memory and the current conversation for elder preferences:

- Content preference: 戏曲、豫剧、京剧、评书、相声、老歌、广播、新闻、广场舞、健康养生.
- App preference: previously opened or explicitly preferred Apps.
- Burden signals: avoid Apps likely to require login, payment, complex interaction, or heavy visual focus.

Recommendation rules:

1. If memory says the elder prefers a concrete App, query that exact App name first.
2. If memory says the elder prefers a content type but not an App, map it to a curated App candidate.
3. If no memory is available, use the curated fallback order below.
4. Do not reveal private memory details to the elder; only say the selected App/content in natural language.

Curated high-quality App pool:

| Preference | Preferred query | Notes |
| --- | --- | --- |
| 戏曲 / opera | `梨园行戏曲HD` | Preferred high-quality opera App for elder companion scenarios. |
| 评书 / 相声 / 广播 | `音乐` | Pick candidates mentioning 评书、相声、广播, such as FM/audio apps. |
| 老歌 / 轻音乐 | `音乐` | Pick low-interaction music Apps. |
| 戏曲视频 / 广场舞 | `视频` | Use only when audio-first choices are not suitable. |
| 健康养生 / 天气 / 日历 | `生活` | Use when entertainment content is not suitable. |

## Reminder

Before opening companion content, speak the arrangement and set the reminder first. Name the selected App when known:

```text
阿姨，我先给您设置一下：30 分钟后提醒您站立活动一下身体并放松眼睛。然后再帮您打开梨园行戏曲HD，您可以听您喜欢的戏曲。
```

Then call:

```text
control_xiaodu("半小时后提醒我站立活动一下身体并放松眼睛")
```

If Xiaodu asks for a specific time, answer with another relative-time phrasing such as `半小时后提醒我站立活动一下身体并放松眼睛`.

## Skill/App Search Strategy

Search by the remembered or recommended exact App first, then fall back by type:

1. `query_xiaodu_skills(query="<remembered_or_recommended_app>")`
   - For opera preference without a stronger memory, use `梨园行戏曲HD`.
2. If unavailable and the App was not already a type key: `query_xiaodu_skills(query="音乐")`
   - Prefer opera, old songs, storytelling, crosstalk, radio, light music.
3. If no suitable candidate: `query_xiaodu_skills(query="视频")`
   - Prefer opera video, square dance, variety, light short video.
4. If no suitable candidate: `query_xiaodu_skills(query="生活")`
   - Prefer health, wellness, weather, calendar, reminder apps.

Open only with the returned `app_key`:

```text
xiaodu_open_skill(app_key="...")
```

Never open with package name, display name, or guessed key.

## Fallbacks

- No online device: tell requester no online Xiaodu device was found.
- Photo failed or no device clearly shows the elder as a live in-room person: use the last successful or only viable device when available and report that physical presence was not clearly confirmed; otherwise ask the requester to choose a device or retry later.
- No suitable app: do not force opening; set a stand-up and eye-relax reminder and report no suitable app was found.
- Possible abnormal photo: do not open an app; tell requester to check directly using cautious wording.
