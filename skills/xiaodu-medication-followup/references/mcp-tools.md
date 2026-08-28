# Xiaodu MCP Through mcporter

Use `mcporter call <server>.<tool> --args '<json>' --output json`. The bundled CLI performs these calls; do not reconstruct them unless diagnosing the wrapper.

| Purpose | Default tool | Required arguments |
| --- | --- | --- |
| List devices | `xiaodu.list_user_devices` | none |
| Start AI call | `xiaodu.xiaodu_trigger_ai_call` | `client_id`, `cuid`, `target`, `task_description` |
| Poll AI call | `xiaodu.xiaodu_get_ai_call_task_status` | `task_id` |
| Notify App/device | `xiaodu.xiaodu_send_notification` | `target`, `title`, `description`; device also needs `client_id`, `cuid`; `url` is optional |
| Open report on screen | `xiaodu.xiaodu_open_web_page` | `client_id`, `cuid`, `url` |

The trigger call is asynchronous. Save its `task_id` and poll the same ID through every `PENDING`, `ACTIVE`, or `PROCESSING` response. Stop only on `COMPLETED` or `FAILED`.

`mcporter --output json` may wrap tool data in MCP `content`, `structuredContent`, or `result`. Text content may itself contain serialized JSON. The bundled parser unwraps these forms. Do not parse the default human-readable output as JSON.

## Setup

Prefer an existing imported `xiaodu` server:

```bash
mcporter config get xiaodu --json
```

When no entry exists, obtain the MCP URL and authentication method from the user or deployment owner. For a header-token deployment, set `XIAODU_MCP_URL` and `XIAODU_ACCESS_TOKEN` only in the current process, then run `scripts/setup.sh --configure-xiaodu`. The setup command stores the token in mcporter's own configuration; it must never copy it into medication state or reports.

Run `python3 scripts/medication_followup.py doctor --network` after configuration. A server entry can exist while authentication or tool discovery still fails.

## Failure Rules

- Do not automatically retry the trigger call after a timeout or transport error; a call may already be in progress.
- Retry status polling with the same `task_id` only while the overall polling deadline remains.
- Treat terminal `FAILED`, polling deadline expiry, and an unclassifiable completed call as exception records.
- Keep error messages concise and redact any access-token-like value before storing or displaying them.
