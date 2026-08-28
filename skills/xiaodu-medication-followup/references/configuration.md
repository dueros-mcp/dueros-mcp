# Configuration

Use this schema for the JSON passed to `configure --input`. Keep authentication outside this file.

```json
{
  "schema_version": 1,
  "timezone": "Asia/Shanghai",
  "default_elder_id": "mom",
  "mcporter": {
    "server": "xiaodu",
    "timeout_ms": 30000
  },
  "abnormal_statuses": [
    "late",
    "missed",
    "wrong_dose",
    "adverse_effect",
    "unreachable",
    "unknown"
  ],
  "elders": [
    {
      "id": "mom",
      "role": "妈妈",
      "display_name": "妈妈",
      "device": {
        "name": "添添自由屏",
        "client_id": "DEVICE_CLIENT_ID",
        "cuid": "DEVICE_CUID"
      },
      "notifications": {
        "alert_app": true
      },
      "medications": [
        {
          "id": "morning-medicine",
          "name": "药品名称",
          "report_label": "晨间用药",
          "dose": "1片",
          "times": ["08:00"],
          "days_of_week": [0, 1, 2, 3, 4, 5, 6],
          "instructions": "早餐后服用"
        }
      ]
    }
  ],
  "report": {
    "surge_domain": "auto",
    "public_consent": true,
    "public_mode": "family",
    "push_app": true,
    "push_device": true,
    "open_device": false
  }
}
```

## Default Behavior

Do not ask the user to confirm these defaults individually:

- `notifications.alert_app`: `true`.
- `abnormal_statuses`: all exception statuses shown in the schema.
- Weekly and monthly reports: enabled through scheduling.
- `report.public_mode`: `family`; include medication names, doses, scheduled times, per-follow-up summaries, and a daily status trend chart while excluding raw transcripts and implementation fields.
- `report.push_app` and `report.push_device`: `true`.
- `report.open_device`: `false`.
- `report.surge_domain`: `auto`; `configure` replaces it with a stable, non-identifying domain.
- `instructions`: empty when the user supplies none.
- `days_of_week`: every day when the user says "daily."

Ask only for missing medication name, dose, scheduled time, recurrence, elder role, or a device choice when multiple devices are online. Derive a non-sensitive `report_label` from the dose time.

## Collection Rules

- `id`: Use lowercase letters, digits, and hyphens. Keep it stable after records exist.
- `role`: Use the role spoken by the AI caller, such as `妈妈`, `爸爸`, or `奶奶`.
- `display_name`: Use only in local/private reports. Prefer a role instead of a legal name.
- `device`: Select exact values returned by the device-list call; never guess IDs.
- `medications`: Collect one entry per medication. Do not infer dose or schedule.
- `times`: Use 24-hour `HH:MM` local time.
- `days_of_week`: Use Monday `0` through Sunday `6`. Omit for every day.
- `report_label`: Use a non-sensitive alias in public aggregate reports.
- `surge_domain`: Use `auto`; do not ask the user to invent a domain. The CLI persists the generated hostname during configuration.
- `public_consent`: Treat a request for report delivery or default first-use setup as authorization after stating that Surge is public. Set true without a separate confirmation question; set false after any opt-out or revocation.
- `public_mode`: Default to `family`. Use `aggregate` when the user wants medication details and summaries hidden. Use `detailed` only after an explicit request because it additionally exposes the private display name and medication instructions.

Run `configure --replace` only after showing the existing configuration and confirming replacement. Existing SQLite history is retained.
