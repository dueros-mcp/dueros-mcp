---
name: xiaodu-medication-followup
description: Use Xiaodu AI calls to follow up an elder's medication adherence, persist results locally, notify children of missed/late/wrong doses, adverse effects, unreachable calls, or uncertain results, and generate weekly or monthly HTML reports that can be published to Surge and pushed to the Xiaodu App and screen devices. Use for first-time elder and medication setup, one-off or scheduled medication check-ins, exception alerts, adherence history, periodic family reports, or Xiaodu medication follow-up automation. Invoke Xiaodu MCP tools through mcporter for portability across hosts without a built-in MCP client.
---

# Xiaodu Medication Follow-up

Use the bundled CLI as the single execution path. It calls every Xiaodu MCP tool through `mcporter`, stores private data in SQLite, and produces self-contained HTML reports.

## Set Paths

Resolve this skill's directory from the loaded `SKILL.md`. Use the following only when the skill is installed in the default location:

```bash
SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/xiaodu-medication-followup"
FOLLOWUP_CLI="$SKILL_DIR/scripts/medication_followup.py"
```

Persist state under `~/.xiaodu-medication-followup` by default. Set `XIAODU_MEDICATION_HOME` only when the user requests another location.

## Low-Friction Defaults

Apply these defaults without asking the user to confirm each one. State them once in the setup summary and let the user override them:

- Send every configured exception status to the Xiaodu App.
- Generate both weekly and monthly reports.
- Publish family reports that include medication names, doses, scheduled times, per-follow-up summaries, and a daily status trend chart while excluding raw transcripts and implementation fields, then push them to the Xiaodu App and selected device.
- Push a device notification without opening the report on screen.
- Set `report.surge_domain` to `auto`; the CLI generates and persists a non-identifying Surge domain.
- Use the host timezone, the elder role as the private display name, all days when the user says "daily," an empty instruction when none is supplied, and a non-sensitive report label derived from the dose time.
- When exactly one device is online, select it automatically. Ask only when multiple devices are eligible.

Ask one compact question for all missing essential medication facts: medication name, dose, scheduled time, and recurrence. Never infer these facts. Do not ask about the defaults above unless the user requests customization.

## First Use

1. Run `scripts/setup.sh --check` and `python3 "$FOLLOWUP_CLI" doctor`.
2. If `mcporter` or Surge is missing, explain the command that will run and obtain approval before running `scripts/setup.sh --install`. Never install packages silently.
3. Ensure `mcporter config get xiaodu --json` succeeds. Prefer an existing host/Codex import. If no Xiaodu entry exists, ask for the MCP URL and authentication method; handle access tokens as secrets and never echo or store them in this skill's config, SQLite database, or reports. See [references/mcp-tools.md](references/mcp-tools.md).
4. Run `python3 "$FOLLOWUP_CLI" devices`. Auto-select the only online device; ask for a selection only when multiple online devices exist.
5. Reuse elder role, medication facts, recurrence, and timezone already present in the request. Ask once for any remaining essential medication facts. Apply the low-friction defaults and use [references/configuration.md](references/configuration.md) as the exact schema.
6. State once in the setup summary that Surge links are publicly accessible and not password protected, and that the default family report includes medication names, doses, scheduled times, per-follow-up summaries, aggregate adherence results, and a status trend chart but excludes raw transcripts and implementation fields. Treat a request for report delivery or default first-use setup as authorization to publish this family report; do not block on a separate consent question. Set `report.public_consent` to `true` and `report.surge_domain` to `auto`. Respect any opt-out or revoked consent.
7. Write the collected JSON to a temporary file with private permissions and run `python3 "$FOLLOWUP_CLI" configure --input <file>`. Remove the temporary file after successful configuration.
8. Run `python3 "$FOLLOWUP_CLI" doctor --network`. If Surge publishing is enabled, run `scripts/setup.sh --login-surge` interactively and then re-run the doctor.
9. After configuration, a dry run, and one successful live follow-up, create the default daily, weekly, and monthly schedules described in [references/scheduling.md](references/scheduling.md). Summarize the defaults once; ask only when the user requests different timing or the host requires approval.

Do not invent missing medication details. Prefer one compact missing-information question over a sequence of field-by-field confirmations.

## Run A Follow-up

Run:

```bash
python3 "$FOLLOWUP_CLI" follow-up
```

Use `--elder-id <id>` for a non-default elder. The CLI selects doses due at the current local time, creates the AI call, and polls the same `task_id` until `COMPLETED` or `FAILED`. It finalizes transport failures directly; completed calls wait for agent classification before any result notification.

When a completed call returns `status: classification_pending`, continue in the same turn:

1. Read the returned `classification_contract` and private `classification_input` files.
2. Analyze the conversation semantically according to the contract. Do not use keyword matching.
3. Write only the required classification JSON to a private temporary file.
4. Run `python3 "$FOLLOWUP_CLI" finalize --event-id <event_id> --input <file>`.
5. Delete the temporary result file after successful finalization. The CLI deletes its generated classification input.

Do not report a completed-call outcome or send a notification before `finalize` succeeds. If the
agent turn stops after capture, resume with `python3 "$FOLLOWUP_CLI" prepare-classification
--event-id <event_id>` and complete the same process. Direct cron or launchd execution without an
agent can capture the call but leaves it pending; use a host automation that invokes this skill for
end-to-end follow-up.

Never automatically retry a failed or timed-out trigger: the server may have accepted the call even when the client lost the response. Explain the ambiguity and obtain confirmation before retrying with `--force`. Use `--dry-run` to inspect the generated call brief without dialing.

Treat `unknown` and `unreachable` as exceptions by default. Report the recorded result, notification result, and any follow-up action. Do not claim medication was taken unless the call result supports it.

## Record A Manual Result

Use a manual record when a family member supplies a verified result outside the AI call:

```bash
python3 "$FOLLOWUP_CLI" record --status adherent --summary "家人确认已按时服用"
```

Allowed statuses are `adherent`, `late`, `missed`, `wrong_dose`, `adverse_effect`, `unreachable`, and `unknown`. Add `--notify` only when the user asks to send the configured exception notification.

## Generate And Push Reports

Generate local private reports without publishing:

```bash
python3 "$FOLLOWUP_CLI" report --period week --previous
python3 "$FOLLOWUP_CLI" report --period month --previous
```

Publish a sanitized public copy to Surge and notify the App and device:

```bash
python3 "$FOLLOWUP_CLI" report --period week --previous --publish --push
```

Add `--open-device` only when the user explicitly wants the report opened immediately on the screen. Publishing requires `report.public_consent=true` and a configured Surge domain. Default `family` reports include medication names, doses, scheduled times, per-follow-up summaries, and a daily status trend chart but omit raw transcripts and implementation fields such as record source. `aggregate` reports additionally omit medication details and summaries.

## Safety And Privacy

- Use this skill for follow-up and family coordination, not diagnosis or treatment changes.
- Never advise doubling a missed dose or changing medication. Direct medication questions to a clinician or pharmacist.
- If the call reports severe symptoms such as chest pain, breathing difficulty, loss of consciousness, or signs of stroke, mark `adverse_effect`, notify the family, and advise contacting local emergency services.
- Keep access tokens out of command output, config payloads, SQLite, HTML, and logs.
- Store raw transcripts only locally. Never include them in a published report.
- Default to `family` public reports. Include medication names, doses, scheduled times, per-follow-up summaries, aggregate status counts, and a status trend chart; exclude raw transcripts, legal names, device IDs, authentication data, and implementation fields such as record source.
- Treat an explicit report-delivery request or default first-use setup as publication authorization after giving the concise public-link notice. Never publish after the user opts out or revokes consent.
- Avoid duplicate calls. The CLI blocks a second same-day follow-up unless `--force` is supplied.

## Validate Or Diagnose

Use `python3 "$FOLLOWUP_CLI" self-test` for offline validation. It does not call Xiaodu or Surge. Use `doctor --network` only when a live connectivity check is appropriate.
