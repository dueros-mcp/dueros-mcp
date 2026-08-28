# Scheduling

Create schedules only after configuration, a dry run, and one successful live follow-up. When the user requested first-time automated setup, apply the defaults below and summarize them once instead of asking about each recurrence. Ask only when the user requests different timing or the host requires approval.

## Default Cadence

- Daily follow-up: Run 30 minutes after the final scheduled dose.
- Weekly report: Run every Monday at 09:00 for the previous Monday through Sunday.
- Monthly report: Run on the first day of each month at 09:15 for the previous calendar month.

Enable both weekly and monthly reports by default. Publish family reports containing medication names, doses, scheduled times, per-follow-up summaries, aggregate results, and a daily status trend chart, then push them to the Xiaodu App and device. Exclude raw transcripts and implementation fields. Do not open the report on the device unless the user explicitly asks.

Use the host's automation feature when available. The scheduled prompts should explicitly invoke `$xiaodu-medication-followup` and run these commands:

```bash
python3 "$FOLLOWUP_CLI" follow-up
python3 "$FOLLOWUP_CLI" report --period week --previous --publish --push
python3 "$FOLLOWUP_CLI" report --period month --previous --publish --push
```

The daily automation must remain active after `follow-up` returns
`classification_pending`: read the returned classification contract and input, create the model
analysis, and run `finalize` in the same task. Do not schedule `finalize` separately.

Direct cron, launchd, systemd timer, or Windows Task Scheduler execution has no calling agent and
therefore stops at `classification_pending`. Use it only for capture-only workflows with a separate
agent that resumes and finalizes pending events. For end-to-end follow-up, prefer the host's agent
automation. Use absolute paths and the same home directory and mcporter/Surge credentials, keep
logs private, and configure retention.

Do not overlap runs. The CLI rejects duplicate same-day calls unless `--force` is provided. Never put `--force` in a recurring schedule.

After creating a schedule, show the user the exact local time, timezone, command, first run, and how to disable it.
