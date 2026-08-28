#!/usr/bin/env python3
"""Portable Xiaodu medication follow-up workflow backed by mcporter and SQLite."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import html
import json
import os
import re
import secrets
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


APP_NAME = "xiaodu-medication-followup"
SCHEMA_VERSION = 1
STATUSES = (
    "adherent",
    "late",
    "missed",
    "wrong_dose",
    "adverse_effect",
    "unreachable",
    "unknown",
)
DEFAULT_ABNORMAL = [
    "late",
    "missed",
    "wrong_dose",
    "adverse_effect",
    "unreachable",
    "unknown",
]
STATUS_LABELS = {
    "adherent": "按时确认",
    "late": "延迟服用",
    "missed": "漏服/未服",
    "wrong_dose": "剂量异常",
    "adverse_effect": "身体不适",
    "unreachable": "未能联系",
    "unknown": "结果待确认",
}
INTERMEDIATE_CALL_STATUSES = {"PENDING", "ACTIVE", "PROCESSING"}
TERMINAL_CALL_STATUSES = {"COMPLETED", "FAILED"}
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
HOST_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?$")
TOKEN_PATTERNS = (
    re.compile(r"(?i)(access[_-]?token\s*[=:]\s*)[^\s,;]+"),
    re.compile(r"(?i)(authorization\s*[=:]\s*)(?:bearer\s+)?[^\s,;]+"),
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/-]+=*"),
)


class AppError(RuntimeError):
    """Expected user-facing failure."""


class McporterError(AppError):
    """mcporter invocation or response failure."""


@dataclass(frozen=True)
class StatePaths:
    root: Path
    config: Path
    database: Path
    classification: Path
    reports: Path
    publish: Path


def resolve_paths(explicit_home: str | None = None) -> StatePaths:
    configured = explicit_home or os.environ.get("XIAODU_MEDICATION_HOME")
    root = Path(configured).expanduser() if configured else Path.home() / f".{APP_NAME}"
    root = root.resolve()
    return StatePaths(
        root=root,
        config=root / "config.json",
        database=root / "followups.sqlite3",
        classification=root / "classification-pending",
        reports=root / "reports",
        publish=root / "surge-public",
    )


def ensure_private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        path.chmod(0o700)
    except OSError:
        pass


def atomic_write_text(path: Path, value: str, mode: int = 0o600) -> None:
    ensure_private_dir(path.parent)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(mode)
        os.replace(temporary, path)
        try:
            path.chmod(mode)
        except OSError:
            pass
    finally:
        if temporary.exists():
            temporary.unlink()


def redact_text(value: str, limit: int = 1200) -> str:
    redacted = value
    for pattern in TOKEN_PATTERNS:
        redacted = pattern.sub(r"\1[REDACTED]", redacted)
    redacted = " ".join(redacted.split())
    return redacted[:limit]


def require_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AppError(f"{field} must be a non-empty string")
    return value.strip()


def generate_surge_domain() -> str:
    date_stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d")
    return f"family-care-{date_stamp}-{secrets.token_hex(6)}.surge.sh"


def validate_config(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise AppError("configuration must be a JSON object")
    config = copy.deepcopy(raw)
    if config.get("schema_version") != SCHEMA_VERSION:
        raise AppError(f"schema_version must be {SCHEMA_VERSION}")

    timezone_name = require_string(config.get("timezone"), "timezone")
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise AppError(f"unknown timezone: {timezone_name}") from exc

    mcporter = config.setdefault("mcporter", {})
    if not isinstance(mcporter, dict):
        raise AppError("mcporter must be an object")
    mcporter.setdefault("server", "xiaodu")
    mcporter.setdefault("timeout_ms", 30000)
    require_string(mcporter.get("server"), "mcporter.server")
    if not isinstance(mcporter.get("timeout_ms"), int) or mcporter["timeout_ms"] < 1000:
        raise AppError("mcporter.timeout_ms must be an integer of at least 1000")

    abnormal = config.setdefault("abnormal_statuses", list(DEFAULT_ABNORMAL))
    if not isinstance(abnormal, list) or any(item not in STATUSES for item in abnormal):
        raise AppError(f"abnormal_statuses must contain only: {', '.join(STATUSES)}")
    config["abnormal_statuses"] = list(dict.fromkeys(abnormal))

    elders = config.get("elders")
    if not isinstance(elders, list) or not elders:
        raise AppError("elders must contain at least one elder")
    elder_ids: set[str] = set()
    for elder_index, elder in enumerate(elders):
        prefix = f"elders[{elder_index}]"
        if not isinstance(elder, dict):
            raise AppError(f"{prefix} must be an object")
        elder_id = require_string(elder.get("id"), f"{prefix}.id")
        if not ID_RE.fullmatch(elder_id):
            raise AppError(f"{prefix}.id must use lowercase letters, digits, and hyphens")
        if elder_id in elder_ids:
            raise AppError(f"duplicate elder id: {elder_id}")
        elder_ids.add(elder_id)
        role = require_string(elder.get("role"), f"{prefix}.role")
        elder.setdefault("display_name", role)
        require_string(elder.get("display_name"), f"{prefix}.display_name")

        device = elder.get("device")
        if not isinstance(device, dict):
            raise AppError(f"{prefix}.device must be an object")
        require_string(device.get("name"), f"{prefix}.device.name")
        require_string(device.get("client_id"), f"{prefix}.device.client_id")
        require_string(device.get("cuid"), f"{prefix}.device.cuid")

        notifications = elder.setdefault("notifications", {})
        if not isinstance(notifications, dict):
            raise AppError(f"{prefix}.notifications must be an object")
        notifications.setdefault("alert_app", True)
        if not isinstance(notifications["alert_app"], bool):
            raise AppError(f"{prefix}.notifications.alert_app must be boolean")

        medications = elder.get("medications")
        if not isinstance(medications, list) or not medications:
            raise AppError(f"{prefix}.medications must contain at least one medication")
        medication_ids: set[str] = set()
        for med_index, medication in enumerate(medications):
            med_prefix = f"{prefix}.medications[{med_index}]"
            if not isinstance(medication, dict):
                raise AppError(f"{med_prefix} must be an object")
            medication_id = require_string(medication.get("id"), f"{med_prefix}.id")
            if not ID_RE.fullmatch(medication_id):
                raise AppError(f"{med_prefix}.id must use lowercase letters, digits, and hyphens")
            if medication_id in medication_ids:
                raise AppError(f"duplicate medication id for {elder_id}: {medication_id}")
            medication_ids.add(medication_id)
            require_string(medication.get("name"), f"{med_prefix}.name")
            require_string(medication.get("dose"), f"{med_prefix}.dose")
            medication.setdefault("report_label", f"用药项目{med_index + 1}")
            require_string(medication.get("report_label"), f"{med_prefix}.report_label")
            medication.setdefault("instructions", "")
            if not isinstance(medication["instructions"], str):
                raise AppError(f"{med_prefix}.instructions must be a string")
            times = medication.get("times")
            if not isinstance(times, list) or not times or any(
                not isinstance(item, str) or not TIME_RE.fullmatch(item) for item in times
            ):
                raise AppError(f"{med_prefix}.times must contain HH:MM values")
            medication["times"] = sorted(set(times))
            days = medication.setdefault("days_of_week", list(range(7)))
            if not isinstance(days, list) or not days or any(
                not isinstance(day, int) or isinstance(day, bool) or day < 0 or day > 6 for day in days
            ):
                raise AppError(f"{med_prefix}.days_of_week must contain integers from 0 to 6")
            medication["days_of_week"] = sorted(set(days))

    default_elder = config.setdefault("default_elder_id", elders[0]["id"])
    if default_elder not in elder_ids:
        raise AppError("default_elder_id must match an elders[].id")

    report = config.setdefault("report", {})
    if not isinstance(report, dict):
        raise AppError("report must be an object")
    report.setdefault("surge_domain", "")
    report.setdefault("public_consent", True)
    report.setdefault("public_mode", "family")
    report.setdefault("push_app", True)
    report.setdefault("push_device", True)
    report.setdefault("open_device", False)
    if not isinstance(report["surge_domain"], str):
        raise AppError("report.surge_domain must be a string")
    if report["surge_domain"].strip().lower() == "auto":
        report["surge_domain"] = generate_surge_domain()
    if report["public_mode"] not in {"aggregate", "family", "detailed"}:
        raise AppError("report.public_mode must be aggregate, family, or detailed")
    for field in ("public_consent", "push_app", "push_device", "open_device"):
        if not isinstance(report[field], bool):
            raise AppError(f"report.{field} must be boolean")

    return config


def load_config(paths: StatePaths) -> dict[str, Any]:
    if not paths.config.exists():
        raise AppError(f"configuration not found: {paths.config}; complete first-use setup")
    try:
        raw = json.loads(paths.config.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AppError(f"cannot read configuration: {redact_text(str(exc))}") from exc
    return validate_config(raw)


def save_config(paths: StatePaths, config: dict[str, Any]) -> None:
    normalized = validate_config(config)
    atomic_write_text(paths.config, json.dumps(normalized, ensure_ascii=False, indent=2) + "\n")


def connect_database(paths: StatePaths) -> sqlite3.Connection:
    ensure_private_dir(paths.root)
    connection = sqlite3.connect(paths.database)
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        PRAGMA journal_mode=WAL;
        PRAGMA foreign_keys=ON;
        CREATE TABLE IF NOT EXISTS followups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            elder_id TEXT NOT NULL,
            local_date TEXT NOT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT NOT NULL,
            status TEXT NOT NULL,
            source TEXT NOT NULL,
            task_id TEXT,
            expected_doses INTEGER NOT NULL DEFAULT 0,
            summary TEXT NOT NULL,
            transcript_json TEXT,
            raw_json TEXT,
            notified_app INTEGER NOT NULL DEFAULT 0,
            notification_error TEXT,
            execution_error TEXT,
            classification_state TEXT NOT NULL DEFAULT 'final',
            scheduled_json TEXT,
            classification_json TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_followups_elder_date
            ON followups(elder_id, local_date);
        CREATE TABLE IF NOT EXISTS publications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            elder_id TEXT NOT NULL,
            period TEXT NOT NULL,
            period_start TEXT NOT NULL,
            period_end TEXT NOT NULL,
            created_at TEXT NOT NULL,
            local_report_path TEXT NOT NULL,
            public_url TEXT NOT NULL,
            app_pushed INTEGER NOT NULL DEFAULT 0,
            device_pushed INTEGER NOT NULL DEFAULT 0,
            device_opened INTEGER NOT NULL DEFAULT 0,
            push_error TEXT
        );
        """
    )
    existing_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(followups)").fetchall()
    }
    migrations = {
        "classification_state": "TEXT NOT NULL DEFAULT 'final'",
        "scheduled_json": "TEXT",
        "classification_json": "TEXT",
    }
    for column, declaration in migrations.items():
        if column not in existing_columns:
            connection.execute(f"ALTER TABLE followups ADD COLUMN {column} {declaration}")
    connection.commit()
    try:
        paths.database.chmod(0o600)
    except OSError:
        pass
    return connection


def extract_json(value: str) -> Any:
    text = value.strip()
    if not text:
        raise AppError("empty JSON output")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    best: tuple[int, Any] | None = None
    for index, character in enumerate(text):
        if character not in "[{":
            continue
        try:
            parsed, end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        span = end
        if best is None or span > best[0]:
            best = (span, parsed)
    if best is None:
        raise AppError("output does not contain valid JSON")
    return best[1]


def parse_text_json(value: Any) -> Any | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped or stripped[0] not in "[{":
        return None
    try:
        return extract_json(stripped)
    except AppError:
        return None


def unwrap_tool_payload(value: Any) -> Any:
    if isinstance(value, dict):
        for key in ("structuredContent", "structured_content"):
            if key in value and value[key] is not None:
                return unwrap_tool_payload(value[key])
        if "content" in value and isinstance(value["content"], list):
            parsed_blocks: list[Any] = []
            for block in value["content"]:
                if isinstance(block, dict) and block.get("type") == "text":
                    parsed = parse_text_json(block.get("text"))
                    if parsed is not None:
                        parsed_blocks.append(unwrap_tool_payload(parsed))
            if len(parsed_blocks) == 1:
                return parsed_blocks[0]
            if parsed_blocks:
                return parsed_blocks
        if "result" in value and len(value) <= 5:
            return unwrap_tool_payload(value["result"])
    return value


def recursive_find(value: Any, key: str) -> Any | None:
    if isinstance(value, dict):
        if key in value:
            return value[key]
        for child in value.values():
            found = recursive_find(child, key)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = recursive_find(child, key)
            if found is not None:
                return found
    return None


def envelope_error(value: Any) -> str | None:
    if isinstance(value, dict):
        if value.get("isError") is True:
            return redact_text(json.dumps(value.get("content", value), ensure_ascii=False))
        if "error" in value and "jsonrpc" in value:
            return redact_text(json.dumps(value["error"], ensure_ascii=False))
    return None


def mcporter_binary(config: dict[str, Any] | None = None) -> str:
    configured = None
    if config:
        configured = config.get("mcporter", {}).get("binary")
    binary = configured or os.environ.get("MCPORTER_BIN") or shutil.which("mcporter")
    if not binary:
        raise McporterError("mcporter is not installed or not on PATH")
    return str(binary)


def call_xiaodu(
    config: dict[str, Any],
    tool: str,
    arguments: dict[str, Any],
    timeout_ms: int | None = None,
) -> tuple[Any, Any]:
    settings = config["mcporter"]
    effective_timeout = timeout_ms or settings["timeout_ms"]
    selector = f"{settings['server']}.{tool}"
    command = [
        mcporter_binary(config),
        "call",
        selector,
        "--args",
        json.dumps(arguments, ensure_ascii=False, separators=(",", ":")),
        "--timeout",
        str(effective_timeout),
        "--output",
        "json",
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=max(15, effective_timeout / 1000 + 15),
        )
    except subprocess.TimeoutExpired as exc:
        raise McporterError(f"mcporter timed out while calling {selector}") from exc
    except OSError as exc:
        raise McporterError(f"cannot start mcporter: {redact_text(str(exc))}") from exc

    raw_output = completed.stdout.strip() or completed.stderr.strip()
    if completed.returncode != 0:
        raise McporterError(
            f"{selector} failed with exit code {completed.returncode}: {redact_text(raw_output)}"
        )
    try:
        envelope = extract_json(raw_output)
    except AppError as exc:
        raise McporterError(f"{selector} returned invalid JSON: {redact_text(raw_output)}") from exc
    error = envelope_error(envelope)
    if error:
        raise McporterError(f"{selector} returned an MCP error: {error}")
    return unwrap_tool_payload(envelope), envelope


def find_device_list(value: Any) -> list[dict[str, Any]] | None:
    if isinstance(value, dict) and "cuid" in value and "client_id" in value:
        return [value]
    if isinstance(value, list) and all(isinstance(item, dict) for item in value):
        if not value or any("cuid" in item and "client_id" in item for item in value):
            return value
    if isinstance(value, dict):
        for child in value.values():
            found = find_device_list(child)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = find_device_list(child)
            if found is not None:
                return found
    return None


def get_elder(config: dict[str, Any], elder_id: str | None) -> dict[str, Any]:
    selected = elder_id or config["default_elder_id"]
    for elder in config["elders"]:
        if elder["id"] == selected:
            return elder
    raise AppError(f"elder not found: {selected}")


def parse_local_datetime(value: str | None, timezone: ZoneInfo) -> dt.datetime:
    if not value:
        return dt.datetime.now(timezone)
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = dt.datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise AppError("datetime must be ISO 8601, for example 2026-08-04T20:30:00+08:00") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone)
    return parsed.astimezone(timezone)


def medication_schedule_for_date(elder: dict[str, Any], date_value: dt.date) -> list[dict[str, Any]]:
    scheduled: list[dict[str, Any]] = []
    for medication in elder["medications"]:
        if date_value.weekday() not in medication["days_of_week"]:
            continue
        for scheduled_time in medication["times"]:
            scheduled.append({"medication": medication, "time": scheduled_time})
    return sorted(scheduled, key=lambda item: (item["time"], item["medication"]["id"]))


def due_schedule(
    elder: dict[str, Any],
    now: dt.datetime,
    include_all_today: bool,
) -> list[dict[str, Any]]:
    schedule = medication_schedule_for_date(elder, now.date())
    if include_all_today:
        return schedule
    current_hhmm = now.strftime("%H:%M")
    return [item for item in schedule if item["time"] <= current_hhmm]


def build_task_description(elder: dict[str, Any], due: list[dict[str, Any]], now: dt.datetime) -> str:
    items = []
    for entry in due:
        medication = entry["medication"]
        instruction = medication.get("instructions", "").strip()
        detail = f"{entry['time']} {medication['name']}，剂量 {medication['dose']}"
        if instruction:
            detail += f"，{instruction}"
        items.append(detail)
    medication_text = "；".join(items)
    return (
        f"今天是 {now.strftime('%Y年%m月%d日')}。请主动问询{elder['role']}以下用药是否已经按计划完成："
        f"{medication_text}。逐项确认是否已服、实际服用时间、实际剂量，以及服药后有无明显不适；"
        "如果由家人代答，请说明由家人确认。结束前复述确认结果。不要建议自行加倍、停药或改变剂量；"
        "如对方报告胸痛、呼吸困难、意识不清或疑似卒中等紧急症状，提醒其立即联系当地急救服务。"
    )


def transcript_to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        preferred = []
        for key in ("summary", "text", "content", "utterance", "message"):
            if key in value:
                preferred.append(transcript_to_text(value[key]))
        if preferred:
            return " ".join(item for item in preferred if item)
        return " ".join(transcript_to_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(transcript_to_text(item) for item in value)
    return str(value)


def participant_transcript_text(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(filter(None, (participant_transcript_text(item) for item in value)))
    if isinstance(value, dict):
        speaker = str(value.get("speaker") or value.get("role") or "").strip().lower()
        if speaker in {"ai", "assistant", "agent", "bot", "xiaodu"}:
            return ""
        if speaker in {"target", "user", "callee", "human", "elder", "patient"}:
            for key in ("text", "content", "utterance", "message"):
                if key in value:
                    return transcript_to_text(value[key])
        return transcript_to_text(value)
    return transcript_to_text(value)


CLASSIFICATION_BINARY = {"yes", "no", "unknown"}
CLASSIFICATION_TIMING = {"on_time", "late", "unknown"}
CLASSIFICATION_DOSE = {"correct", "wrong", "unknown"}
CLASSIFICATION_RESPONDERS = {"self", "family", "unknown"}
CLASSIFICATION_CONFIDENCE_THRESHOLD = 0.8


def classification_turns(transcript: Any) -> list[dict[str, str]]:
    if not isinstance(transcript, list):
        return []
    turns: list[dict[str, str]] = []
    for item in transcript:
        if not isinstance(item, dict):
            continue
        raw_speaker = str(item.get("speaker") or item.get("role") or "").strip().lower()
        if raw_speaker in {"ai", "assistant", "agent", "bot", "xiaodu"}:
            speaker = "ai"
        elif raw_speaker in {"target", "user", "callee", "human", "elder", "patient"}:
            speaker = "target"
        else:
            speaker = "unknown"
        text = ""
        for key in ("text", "content", "utterance", "message"):
            if key in item:
                text = transcript_to_text(item[key]).strip()
                break
        if text:
            turns.append({"speaker": speaker, "text": text})
    return turns


def scheduled_doses_for_classification(due: list[dict[str, Any]]) -> list[dict[str, str]]:
    scheduled = []
    for entry in due:
        medication = entry["medication"]
        scheduled.append(
            {
                "medication_id": medication["id"],
                "name": medication["name"],
                "scheduled_time": entry["time"],
                "expected_dose": medication["dose"],
                "instructions": medication.get("instructions", ""),
            }
        )
    return scheduled


def classification_input_path(paths: StatePaths, event_id: int) -> Path:
    return paths.classification / f"event-{event_id}.json"


def write_classification_input(
    paths: StatePaths,
    *,
    event_id: int,
    task_id: str,
    elder: dict[str, Any],
    scheduled: list[dict[str, str]],
    summary: str,
    transcript: Any,
) -> Path:
    turns = classification_turns(transcript)
    payload = {
        "schema_version": 1,
        "event_id": event_id,
        "task_id": task_id,
        "elder_role": elder["role"],
        "scheduled_doses": scheduled,
        "upstream_summary": summary,
        "conversation": turns,
        "participant_utterances": [
            turn["text"] for turn in turns if turn["speaker"] == "target"
        ],
    }
    path = classification_input_path(paths, event_id)
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return path


def validate_model_classification(
    value: Any,
    *,
    scheduled: list[dict[str, Any]],
    participant_utterances: list[str],
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AppError("classification must be a JSON object")
    if value.get("schema_version") != 1:
        raise AppError("classification.schema_version must be 1")
    summary = require_string(value.get("summary"), "classification.summary")
    adverse_effect = value.get("adverse_effect")
    if adverse_effect not in CLASSIFICATION_BINARY:
        raise AppError("classification.adverse_effect must be yes, no, or unknown")
    responder = value.get("responder")
    if responder not in CLASSIFICATION_RESPONDERS:
        raise AppError("classification.responder must be self, family, or unknown")
    confidence = value.get("confidence")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        raise AppError("classification.confidence must be a number from 0 to 1")
    confidence = float(confidence)
    if not 0 <= confidence <= 1:
        raise AppError("classification.confidence must be a number from 0 to 1")
    symptoms = value.get("symptoms")
    conflicts = value.get("conflicts")
    evidence = value.get("evidence")
    if not isinstance(symptoms, list) or not all(isinstance(item, str) for item in symptoms):
        raise AppError("classification.symptoms must be an array of strings")
    if not isinstance(conflicts, list) or not all(isinstance(item, str) for item in conflicts):
        raise AppError("classification.conflicts must be an array of strings")
    if not isinstance(evidence, list) or not evidence or not all(isinstance(item, str) for item in evidence):
        raise AppError("classification.evidence must be a non-empty array of exact quotes")

    searchable = [re.sub(r"\s+", "", item) for item in participant_utterances]
    for index, quote_text in enumerate(evidence):
        normalized_quote = re.sub(r"\s+", "", quote_text.strip())
        if not normalized_quote or not any(normalized_quote in utterance for utterance in searchable):
            raise AppError(
                f"classification.evidence[{index}] is not an exact participant quote"
            )

    medication_results = value.get("medications")
    if not isinstance(medication_results, list):
        raise AppError("classification.medications must be an array")
    expected_keys = {
        (str(item["medication_id"]), str(item["scheduled_time"])) for item in scheduled
    }
    seen_keys: set[tuple[str, str]] = set()
    normalized_results = []
    for index, result in enumerate(medication_results):
        if not isinstance(result, dict):
            raise AppError(f"classification.medications[{index}] must be an object")
        medication_id = require_string(
            result.get("medication_id"), f"classification.medications[{index}].medication_id"
        )
        scheduled_time = require_string(
            result.get("scheduled_time"), f"classification.medications[{index}].scheduled_time"
        )
        key = (medication_id, scheduled_time)
        if key not in expected_keys or key in seen_keys:
            raise AppError(
                f"classification.medications[{index}] does not match one unique scheduled dose"
            )
        seen_keys.add(key)
        taken = result.get("taken")
        timing = result.get("timing")
        dose = result.get("dose")
        if taken not in CLASSIFICATION_BINARY:
            raise AppError(f"classification.medications[{index}].taken is invalid")
        if timing not in CLASSIFICATION_TIMING:
            raise AppError(f"classification.medications[{index}].timing is invalid")
        if dose not in CLASSIFICATION_DOSE:
            raise AppError(f"classification.medications[{index}].dose is invalid")
        actual_time = result.get("actual_time")
        actual_dose = result.get("actual_dose")
        if actual_time is not None and not isinstance(actual_time, str):
            raise AppError(f"classification.medications[{index}].actual_time must be a string or null")
        if actual_dose is not None and not isinstance(actual_dose, str):
            raise AppError(f"classification.medications[{index}].actual_dose must be a string or null")
        normalized_results.append(
            {
                "medication_id": medication_id,
                "scheduled_time": scheduled_time,
                "taken": taken,
                "timing": timing,
                "dose": dose,
                "actual_time": actual_time,
                "actual_dose": actual_dose,
            }
        )
    if seen_keys != expected_keys:
        raise AppError("classification.medications must cover every scheduled dose exactly once")

    return {
        "schema_version": 1,
        "summary": concise_summary(summary, 2000),
        "medications": normalized_results,
        "adverse_effect": adverse_effect,
        "symptoms": [concise_summary(item, 200) for item in symptoms],
        "responder": responder,
        "evidence": [concise_summary(item, 500) for item in evidence],
        "confidence": confidence,
        "conflicts": [concise_summary(item, 500) for item in conflicts],
    }


def derive_classification_status(classification: dict[str, Any]) -> str:
    medications = classification["medications"]
    if classification["adverse_effect"] == "yes":
        return "adverse_effect"
    if classification["confidence"] < CLASSIFICATION_CONFIDENCE_THRESHOLD or classification["conflicts"]:
        return "unknown"
    if any(item["dose"] == "wrong" for item in medications):
        return "wrong_dose"
    if any(item["taken"] == "no" for item in medications):
        return "missed"
    if any(item["timing"] == "late" for item in medications):
        return "late"
    if (
        classification["adverse_effect"] == "no"
        and all(item["taken"] == "yes" for item in medications)
        and all(item["timing"] == "on_time" for item in medications)
        and all(item["dose"] == "correct" for item in medications)
    ):
        return "adherent"
    return "unknown"


def interaction_fields(payload: Any) -> tuple[str, Any]:
    report = recursive_find(payload, "interaction_report")
    source = report if isinstance(report, dict) else payload
    summary_value = recursive_find(source, "summary")
    transcript = recursive_find(source, "full_transcript")
    if transcript is None:
        transcript = recursive_find(source, "transcript")
    summary = transcript_to_text(summary_value).strip()
    if not summary:
        summary = "通话已完成，但未返回明确摘要"
    return summary, transcript


def concise_summary(value: str, limit: int = 180) -> str:
    return redact_text(value, limit=limit)


def insert_followup(
    connection: sqlite3.Connection,
    *,
    elder_id: str,
    local_date: str,
    started_at: str,
    completed_at: str,
    status: str,
    source: str,
    task_id: str | None,
    expected_doses: int,
    summary: str,
    transcript: Any = None,
    raw: Any = None,
    notified_app: bool = False,
    notification_error: str | None = None,
    execution_error: str | None = None,
    classification_state: str = "final",
    scheduled: Any = None,
    classification: Any = None,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO followups (
            elder_id, local_date, started_at, completed_at, status, source,
            task_id, expected_doses, summary, transcript_json, raw_json,
            notified_app, notification_error, execution_error,
            classification_state, scheduled_json, classification_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            elder_id,
            local_date,
            started_at,
            completed_at,
            status,
            source,
            task_id,
            expected_doses,
            concise_summary(summary, 2000),
            json.dumps(transcript, ensure_ascii=False) if transcript is not None else None,
            json.dumps(raw, ensure_ascii=False) if raw is not None else None,
            int(notified_app),
            concise_summary(notification_error, 1000) if notification_error else None,
            concise_summary(execution_error, 1000) if execution_error else None,
            classification_state,
            json.dumps(scheduled, ensure_ascii=False) if scheduled is not None else None,
            json.dumps(classification, ensure_ascii=False) if classification is not None else None,
        ),
    )
    connection.commit()
    return int(cursor.lastrowid)


def existing_followup(connection: sqlite3.Connection, elder_id: str, local_date: str) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT * FROM followups
        WHERE elder_id = ? AND local_date = ?
        ORDER BY id DESC LIMIT 1
        """,
        (elder_id, local_date),
    ).fetchone()


def get_followup(connection: sqlite3.Connection, event_id: int) -> sqlite3.Row:
    row = connection.execute("SELECT * FROM followups WHERE id = ?", (event_id,)).fetchone()
    if row is None:
        raise AppError(f"follow-up event not found: {event_id}")
    return row


def send_exception_notification(
    config: dict[str, Any], elder: dict[str, Any], status: str, summary: str
) -> None:
    title = f"用药随访异常：{elder['role']}"
    description = f"{STATUS_LABELS[status]}。{concise_summary(summary, 140)}"
    if status == "adverse_effect":
        description += " 请尽快联系确认；如有紧急症状，请联系当地急救服务。"
    call_xiaodu(
        config,
        "xiaodu_send_notification",
        {
            "target": "app",
            "title": title,
            "description": description,
        },
    )


def finalize_failed_followup(
    *,
    config: dict[str, Any],
    elder: dict[str, Any],
    connection: sqlite3.Connection,
    now: dt.datetime,
    started_at: str,
    due_count: int,
    status: str,
    summary: str,
    task_id: str | None,
    raw: Any,
    notify: bool,
) -> tuple[int, bool, str | None]:
    notified = False
    notification_error = None
    if notify and elder["notifications"]["alert_app"] and status in config["abnormal_statuses"]:
        try:
            send_exception_notification(config, elder, status, summary)
            notified = True
        except AppError as exc:
            notification_error = str(exc)
    event_id = insert_followup(
        connection,
        elder_id=elder["id"],
        local_date=now.date().isoformat(),
        started_at=started_at,
        completed_at=dt.datetime.now(now.tzinfo).isoformat(),
        status=status,
        source="ai_call",
        task_id=task_id,
        expected_doses=due_count,
        summary=summary,
        raw=raw,
        notified_app=notified,
        notification_error=notification_error,
        execution_error=summary,
    )
    return event_id, notified, notification_error


def normalize_call_status(payload: Any) -> str:
    value = recursive_find(payload, "status")
    return str(value).upper() if value is not None else ""


def period_bounds(period: str, anchor: dt.date, previous: bool) -> tuple[dt.date, dt.date]:
    if period == "week":
        start = anchor - dt.timedelta(days=anchor.weekday())
        if previous:
            start -= dt.timedelta(days=7)
        return start, start + dt.timedelta(days=6)

    start = anchor.replace(day=1)
    if previous:
        previous_end = start - dt.timedelta(days=1)
        start = previous_end.replace(day=1)
    if start.month == 12:
        next_month = start.replace(year=start.year + 1, month=1)
    else:
        next_month = start.replace(month=start.month + 1)
    return start, next_month - dt.timedelta(days=1)


def planned_counts(elder: dict[str, Any], start: dt.date, end: dt.date) -> tuple[int, int]:
    days = 0
    doses = 0
    cursor = start
    while cursor <= end:
        schedule = medication_schedule_for_date(elder, cursor)
        if schedule:
            days += 1
            doses += len(schedule)
        cursor += dt.timedelta(days=1)
    return days, doses


def percent(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "--"
    return f"{round(numerator * 100 / denominator)}%"


def badge_class(status: str) -> str:
    if status == "adherent":
        return "badge-good"
    if status in {"late", "unknown"}:
        return "badge-warn"
    if status in {"missed", "wrong_dose", "adverse_effect", "unreachable"}:
        return "badge-alert"
    return "badge-neutral"


def render_status_trend(rows: list[sqlite3.Row], start: dt.date, end: dt.date) -> str:
    if not rows:
        return '<p class="empty">本周期暂无可视化的随访记录。</p>'

    risk_rank = {
        "adherent": 0,
        "late": 1,
        "unknown": 2,
        "unreachable": 3,
        "missed": 3,
        "wrong_dose": 3,
        "adverse_effect": 4,
    }
    trend_level = {
        "adherent": 2,
        "late": 1,
        "unknown": 1,
        "unreachable": 0,
        "missed": 0,
        "wrong_dose": 0,
        "adverse_effect": 0,
    }
    status_color = {
        "adherent": "#18794e",
        "late": "#c87500",
        "unknown": "#7c3aed",
        "unreachable": "#b42318",
        "missed": "#b42318",
        "wrong_dose": "#b42318",
        "adverse_effect": "#b42318",
    }

    daily: dict[str, sqlite3.Row] = {}
    for row in rows:
        date_key = row["local_date"]
        previous = daily.get(date_key)
        if previous is None or risk_rank[row["status"]] > risk_rank[previous["status"]]:
            daily[date_key] = row

    dates: list[dt.date] = []
    cursor = start
    while cursor <= end:
        dates.append(cursor)
        cursor += dt.timedelta(days=1)

    width = 960
    height = 260
    left = 82
    right = 28
    plot_width = width - left - right
    y_for_level = {2: 48, 1: 118, 0: 188}
    axis_rows = (("按时", 48), ("延迟 / 待确认", 118), ("异常", 188))
    grid = "".join(
        f'<line x1="{left}" y1="{y}" x2="{width - right}" y2="{y}" stroke="#d9e0e5" stroke-width="1" />'
        f'<text x="{left - 12}" y="{y + 5}" text-anchor="end" fill="#5d6874" font-size="13">{label}</text>'
        for label, y in axis_rows
    )

    points: list[str] = []
    marks: list[str] = []
    date_labels: list[str] = []
    total = len(dates)
    for index, date_value in enumerate(dates):
        x = left + (plot_width / 2 if total == 1 else plot_width * index / (total - 1))
        date_key = date_value.isoformat()
        row = daily.get(date_key)
        if row is None:
            marks.append(
                f'<g><title>{date_key}：无随访记录</title>'
                f'<circle cx="{x:.1f}" cy="222" r="4" fill="#aab4bd" /></g>'
            )
            show_label = total <= 14 or index in {0, total - 1}
        else:
            status = row["status"]
            y = y_for_level[trend_level[status]]
            points.append(f"{x:.1f},{y}")
            label = STATUS_LABELS[status]
            marks.append(
                f'<g data-status="{html.escape(status)}"><title>{date_key}：{html.escape(label)}</title>'
                f'<circle cx="{x:.1f}" cy="{y}" r="7" fill="{status_color[status]}" '
                'stroke="#ffffff" stroke-width="3" /></g>'
            )
            show_label = total <= 14 or status != "adherent" or index in {0, total - 1}
        if show_label:
            date_labels.append(
                f'<text x="{x:.1f}" y="246" text-anchor="middle" fill="#5d6874" font-size="12">'
                f'{date_value.strftime("%m-%d")}</text>'
            )

    line = ""
    if len(points) >= 2:
        line = (
            f'<polyline points="{" ".join(points)}" fill="none" stroke="#496a68" '
            'stroke-width="3" stroke-linecap="round" stroke-linejoin="round" opacity="0.75" />'
        )

    return (
        '<div class="trend-chart">'
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="每日随访状态趋势">'
        '<desc>纵向分为按时、延迟或待确认、异常三档；折线和节点显示每日状态变化。</desc>'
        f'{grid}{line}{"".join(marks)}{"".join(date_labels)}</svg>'
        '<div class="chart-legend" aria-label="图例">'
        '<span class="chart-key"><span class="chart-dot" style="background:#18794e"></span>按时</span>'
        '<span class="chart-key"><span class="chart-dot" style="background:#c87500"></span>延迟</span>'
        '<span class="chart-key"><span class="chart-dot" style="background:#7c3aed"></span>待确认</span>'
        '<span class="chart-key"><span class="chart-dot" style="background:#b42318"></span>异常</span>'
        '<span class="chart-key"><span class="chart-dot" style="background:#aab4bd"></span>无记录</span>'
        '</div></div>'
    )


def render_report(
    *,
    config: dict[str, Any],
    elder: dict[str, Any],
    rows: list[sqlite3.Row],
    period: str,
    start: dt.date,
    end: dt.date,
    generated_at: dt.datetime,
    public: bool,
) -> str:
    css_path = Path(__file__).resolve().parent.parent / "assets" / "report-style.css"
    css = css_path.read_text(encoding="utf-8")
    public_mode = config["report"]["public_mode"] if public else "private"
    public_aggregate = public_mode == "aggregate"
    public_family = public_mode == "family"
    public_sanitized = public_aggregate or public_family
    elder_label = elder["role"] if public_sanitized else elder["display_name"]
    period_label = "周度" if period == "week" else "月度"
    observed_days = {row["local_date"] for row in rows}
    definitive = [row for row in rows if row["status"] not in {"unknown", "unreachable"}]
    adherent_count = sum(row["status"] == "adherent" for row in definitive)
    exception_count = sum(row["status"] in config["abnormal_statuses"] for row in rows)
    planned_days, planned_doses = planned_counts(elder, start, end)
    status_counts = {status: sum(row["status"] == status for row in rows) for status in STATUSES}

    metric_values = (
        ("计划随访天数", str(planned_days)),
        ("实际随访天数", str(len(observed_days))),
        ("按时确认率", percent(adherent_count, len(definitive))),
        ("异常记录", str(exception_count)),
    )
    metric_html = "".join(
        f'<article class="metric"><p class="metric-label">{html.escape(label)}</p>'
        f'<p class="metric-value">{html.escape(value)}</p></article>'
        for label, value in metric_values
    )
    status_html = "".join(
        f'<div class="status-row"><span class="badge {badge_class(status)}">'
        f'{html.escape(STATUS_LABELS[status])}</span><strong>{count}</strong></div>'
        for status, count in status_counts.items()
    )
    trend_html = render_status_trend(rows, start, end)

    if public_aggregate:
        medication_html = (
            '<p class="empty">公开汇总已隐藏药品名称、剂量和具体服用时间。'
            f'本周期计划用药记录共 {planned_doses} 次。</p>'
        )
    else:
        medication_rows = []
        for medication in elder["medications"]:
            days = "每天" if medication["days_of_week"] == list(range(7)) else ", ".join(
                str(day + 1) for day in medication["days_of_week"]
            )
            instructions = "--" if public_family else medication.get("instructions", "") or "--"
            medication_rows.append(
                "<tr>"
                f"<td data-label=\"药品\">{html.escape(medication['name'])}</td>"
                f"<td data-label=\"剂量\">{html.escape(medication['dose'])}</td>"
                f"<td data-label=\"时间\">{html.escape(' / '.join(medication['times']))}</td>"
                f"<td data-label=\"星期\">{html.escape(days)}</td>"
                f"<td data-label=\"备注\">{html.escape(instructions)}</td>"
                "</tr>"
            )
        medication_html = (
            '<div class="table-wrap"><table><thead><tr>'
            '<th style="width:20%">药品</th><th style="width:14%">剂量</th>'
            '<th style="width:16%">时间</th><th style="width:16%">星期</th>'
            '<th>备注</th></tr></thead><tbody>'
            + "".join(medication_rows)
            + "</tbody></table></div>"
        )

    if rows:
        history_rows = []
        for row in rows:
            summary = "已隐藏" if public_aggregate else row["summary"]
            history_rows.append(
                "<tr>"
                f"<td data-label=\"日期\">{html.escape(row['local_date'])}</td>"
                f'<td data-label="结果"><span class="badge {badge_class(row["status"])}">'
                f"{html.escape(STATUS_LABELS[row['status']])}</span></td>"
                f"<td data-label=\"应确认\">{row['expected_doses']}</td>"
                f"<td data-label=\"摘要\">{html.escape(summary)}</td>"
                "</tr>"
            )
        history_html = (
            '<div class="table-wrap"><table><thead><tr>'
            '<th style="width:16%">日期</th><th style="width:18%">结果</th>'
            '<th style="width:12%">应确认</th><th>摘要</th>'
            '</tr></thead><tbody>' + "".join(history_rows) + "</tbody></table></div>"
        )
    else:
        history_html = '<p class="empty">本周期暂无随访记录。</p>'

    if public_aggregate:
        privacy_note = "这是公开聚合版本，已隐藏原始对话、自由文本摘要、药名、剂量和具体服用时间。"
    elif public_family:
        privacy_note = "这是公开家庭版本，包含药名、剂量、计划时间和随访摘要；已隐藏原始对话和底层实现信息。"
    else:
        privacy_note = "这是本地私密版本，包含用药安排和随访摘要，请妥善保管。"
    privacy_note += " 按时确认率按有明确结论的随访记录计算，不等同于逐次剂量核验。"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex,nofollow">
  <link rel="icon" href="data:,">
  <title>{html.escape(elder_label)} {period_label}用药随访报告</title>
  <style>{css}</style>
</head>
<body>
  <header class="report-header">
    <div class="header-inner">
      <p class="eyebrow">家庭用药随访</p>
      <h1>{html.escape(elder_label)} · {period_label}报告</h1>
      <p class="header-meta">{start.isoformat()} 至 {end.isoformat()} · 生成于 {generated_at.strftime('%Y-%m-%d %H:%M %Z')}</p>
    </div>
  </header>
  <main>
    <section class="metrics" aria-label="核心指标">{metric_html}</section>
    <section class="section">
      <h2>结果分布</h2>
      <div class="status-grid">{status_html}</div>
    </section>
    <section class="section">
      <h2>状态趋势</h2>
      {trend_html}
    </section>
    <section class="section">
      <h2>用药安排</h2>
      {medication_html}
    </section>
    <section class="section">
      <h2>随访记录</h2>
      {history_html}
      <p class="privacy-note">{html.escape(privacy_note)}</p>
    </section>
  </main>
  <footer class="report-footer">本报告用于家庭随访记录，不替代医生或药师建议。原始通话内容不会进入公开报告。</footer>
</body>
</html>
"""


def query_period_rows(
    connection: sqlite3.Connection, elder_id: str, start: dt.date, end: dt.date
) -> list[sqlite3.Row]:
    return list(
        connection.execute(
            """
            SELECT * FROM followups
            WHERE elder_id = ? AND local_date BETWEEN ? AND ?
              AND classification_state = 'final'
            ORDER BY local_date ASC, id ASC
            """,
            (elder_id, start.isoformat(), end.isoformat()),
        ).fetchall()
    )


def normalize_surge_domain(value: str) -> str:
    domain = value.strip()
    domain = re.sub(r"^https?://", "", domain, flags=re.IGNORECASE).strip("/")
    if not domain or "/" in domain or not HOST_RE.fullmatch(domain):
        raise AppError("report.surge_domain must be a hostname such as family-report.surge.sh")
    return domain.lower()


def publish_to_surge(paths: StatePaths, report_file: Path, config: dict[str, Any]) -> str:
    surge_binary = shutil.which("surge")
    if not surge_binary:
        raise AppError("Surge CLI is not installed; run scripts/setup.sh --install with approval")
    domain = normalize_surge_domain(config["report"]["surge_domain"])
    ensure_private_dir(paths.publish)
    public_name = report_file.name.replace(".public", "")
    destination = paths.publish / public_name
    shutil.copy2(report_file, destination)
    shutil.copy2(report_file, paths.publish / "index.html")
    try:
        completed = subprocess.run(
            [surge_binary, str(paths.publish), domain],
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except subprocess.TimeoutExpired as exc:
        raise AppError("Surge publish timed out; check login and network") from exc
    except OSError as exc:
        raise AppError(f"cannot start Surge: {redact_text(str(exc))}") from exc
    if completed.returncode != 0:
        output = completed.stderr.strip() or completed.stdout.strip()
        raise AppError(f"Surge publish failed: {redact_text(output)}")
    return f"https://{domain}/{quote(public_name)}"


def push_report(
    config: dict[str, Any],
    elder: dict[str, Any],
    *,
    period: str,
    url: str,
    open_device: bool,
) -> tuple[bool, bool, bool, str | None]:
    period_label = "周报" if period == "week" else "月报"
    title = f"{elder['role']}用药{period_label}"
    description = f"{period_label}已生成，点击查看汇总。"
    app_pushed = False
    device_pushed = False
    device_opened = False
    errors: list[str] = []

    if config["report"]["push_app"]:
        try:
            call_xiaodu(
                config,
                "xiaodu_send_notification",
                {"target": "app", "title": title, "description": description, "url": url},
            )
            app_pushed = True
        except AppError as exc:
            errors.append(f"App: {exc}")

    device = elder["device"]
    if config["report"]["push_device"]:
        try:
            call_xiaodu(
                config,
                "xiaodu_send_notification",
                {
                    "target": "device",
                    "title": title,
                    "description": description,
                    "url": url,
                    "client_id": device["client_id"],
                    "cuid": device["cuid"],
                },
            )
            device_pushed = True
        except AppError as exc:
            errors.append(f"设备: {exc}")

    if open_device:
        try:
            call_xiaodu(
                config,
                "xiaodu_open_web_page",
                {"url": url, "client_id": device["client_id"], "cuid": device["cuid"]},
            )
            device_opened = True
        except AppError as exc:
            errors.append(f"打开页面: {exc}")

    return app_pushed, device_pushed, device_opened, "; ".join(errors) or None


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def cmd_configure(args: argparse.Namespace, paths: StatePaths) -> int:
    if paths.config.exists() and not args.replace:
        raise AppError(f"configuration already exists at {paths.config}; use --replace after confirmation")
    if args.input == "-":
        raw_text = sys.stdin.read()
    else:
        raw_text = Path(args.input).expanduser().read_text(encoding="utf-8")
    try:
        config = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise AppError(f"invalid configuration JSON: {exc}") from exc
    save_config(paths, config)
    connection = connect_database(paths)
    connection.close()
    print_json({"configured": True, "config": str(paths.config), "database": str(paths.database)})
    return 0


def cmd_doctor(args: argparse.Namespace, paths: StatePaths) -> int:
    checks: list[dict[str, Any]] = []
    checks.append(
        {
            "name": "python",
            "ok": sys.version_info >= (3, 9),
            "detail": sys.version.split()[0],
            "required": True,
        }
    )
    binary = shutil.which("mcporter")
    checks.append({"name": "mcporter", "ok": bool(binary), "detail": binary or "missing", "required": True})

    server = "xiaodu"
    config: dict[str, Any] | None = None
    if paths.config.exists():
        try:
            config = load_config(paths)
            server = config["mcporter"]["server"]
            checks.append({"name": "medication_config", "ok": True, "detail": str(paths.config), "required": True})
        except AppError as exc:
            checks.append({"name": "medication_config", "ok": False, "detail": str(exc), "required": True})
    else:
        checks.append(
            {
                "name": "medication_config",
                "ok": False,
                "detail": f"missing: {paths.config}",
                "required": True,
            }
        )

    xiaodu_config_ok = False
    if binary:
        completed = subprocess.run(
            [binary, "config", "get", server, "--json"],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        xiaodu_config_ok = completed.returncode == 0
    checks.append(
        {
            "name": "xiaodu_mcporter_config",
            "ok": xiaodu_config_ok,
            "detail": f"server={server}" if xiaodu_config_ok else "not configured",
            "required": True,
        }
    )

    surge_binary = shutil.which("surge")
    publishing_enabled = bool(config and config["report"].get("surge_domain"))
    checks.append(
        {
            "name": "surge",
            "ok": bool(surge_binary) or not publishing_enabled,
            "detail": surge_binary or ("optional" if not publishing_enabled else "missing"),
            "required": publishing_enabled,
        }
    )

    if args.network and binary and xiaodu_config_ok:
        completed = subprocess.run(
            [binary, "list", server, "--brief", "--timeout", "30000"],
            check=False,
            capture_output=True,
            text=True,
            timeout=45,
        )
        checks.append(
            {
                "name": "xiaodu_tool_discovery",
                "ok": completed.returncode == 0,
                "detail": "reachable" if completed.returncode == 0 else redact_text(completed.stderr or completed.stdout),
                "required": True,
            }
        )
    if args.network and surge_binary and publishing_enabled:
        completed = subprocess.run(
            [surge_binary, "whoami"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        checks.append(
            {
                "name": "surge_login",
                "ok": completed.returncode == 0,
                "detail": "authenticated" if completed.returncode == 0 else "not authenticated",
                "required": True,
            }
        )

    ok = all(item["ok"] for item in checks if item["required"])
    print_json({"ok": ok, "state_home": str(paths.root), "checks": checks})
    return 0 if ok else 1


def cmd_devices(args: argparse.Namespace, paths: StatePaths) -> int:
    if paths.config.exists():
        config = load_config(paths)
    else:
        config = {
            "mcporter": {"server": args.server, "timeout_ms": args.timeout_ms},
        }
    payload, _ = call_xiaodu(config, "list_user_devices", {}, timeout_ms=args.timeout_ms)
    devices = find_device_list(payload)
    if devices is None:
        raise AppError("device list response did not contain client_id/cuid entries")
    normalized = []
    for device in devices:
        normalized.append(
            {
                "device_name": device.get("device_name") or device.get("name") or "未命名设备",
                "online_status": device.get("online_status"),
                "client_id": device.get("client_id"),
                "cuid": device.get("cuid"),
                "location": device.get("location"),
            }
        )
    print_json(normalized)
    return 0


def cmd_follow_up(args: argparse.Namespace, paths: StatePaths) -> int:
    config = load_config(paths)
    elder = get_elder(config, args.elder_id)
    timezone = ZoneInfo(config["timezone"])
    now = parse_local_datetime(args.at, timezone)
    due = due_schedule(elder, now, args.all_today)
    if not due:
        raise AppError("no medication dose is due yet for this elder today")
    task_description = build_task_description(elder, due, now)

    if args.dry_run:
        print_json(
            {
                "dry_run": True,
                "elder_id": elder["id"],
                "target": elder["role"],
                "due_doses": len(due),
                "task_description": task_description,
            }
        )
        return 0

    connection = connect_database(paths)
    previous = existing_followup(connection, elder["id"], now.date().isoformat())
    if previous is not None and not args.force:
        previous_status = (
            "classification_pending"
            if previous["classification_state"] == "pending"
            else previous["status"]
        )
        connection.close()
        raise AppError(
            f"a follow-up already exists today (event {previous['id']}, {previous_status}); "
            "confirm before retrying with --force"
        )

    started_at = dt.datetime.now(timezone).isoformat()
    device = elder["device"]
    task_id: str | None = None
    try:
        payload, envelope = call_xiaodu(
            config,
            "xiaodu_trigger_ai_call",
            {
                "client_id": device["client_id"],
                "cuid": device["cuid"],
                "target": elder["role"],
                "task_description": task_description,
            },
        )
        task_id_value = recursive_find(payload, "task_id")
        task_id = str(task_id_value) if task_id_value else None
        status = normalize_call_status(payload)
        if status == "FAILED":
            message = transcript_to_text(recursive_find(payload, "message")) or "AI 电话任务创建失败"
            event_id, notified, notification_error = finalize_failed_followup(
                config=config,
                elder=elder,
                connection=connection,
                now=now,
                started_at=started_at,
                due_count=len(due),
                status="unreachable",
                summary=message,
                task_id=task_id,
                raw=envelope,
                notify=not args.no_notify,
            )
            print_json(
                {
                    "event_id": event_id,
                    "status": "unreachable",
                    "task_id": task_id,
                    "summary": message,
                    "app_notified": notified,
                    "notification_error": notification_error,
                }
            )
            connection.close()
            return 2
        if not task_id:
            raise McporterError("AI call trigger response did not contain task_id")
    except AppError as exc:
        summary = f"AI 电话触发失败：{redact_text(str(exc))}"
        event_id, notified, notification_error = finalize_failed_followup(
            config=config,
            elder=elder,
            connection=connection,
            now=now,
            started_at=started_at,
            due_count=len(due),
            status="unreachable",
            summary=summary,
            task_id=task_id,
            raw=None,
            notify=not args.no_notify,
        )
        connection.close()
        print_json(
            {
                "event_id": event_id,
                "status": "unreachable",
                "task_id": task_id,
                "summary": summary,
                "app_notified": notified,
                "notification_error": notification_error,
                "retry_requires_confirmation": True,
            }
        )
        return 2

    deadline = time.monotonic() + args.poll_timeout
    last_payload = payload
    last_envelope = envelope
    poll_error: str | None = None
    while True:
        status = normalize_call_status(last_payload)
        if status in TERMINAL_CALL_STATUSES:
            break
        if time.monotonic() >= deadline:
            status = "POLL_TIMEOUT"
            break
        if status and status not in INTERMEDIATE_CALL_STATUSES:
            poll_error = f"unexpected task status: {status}"
        time.sleep(args.poll_interval)
        try:
            last_payload, last_envelope = call_xiaodu(
                config,
                "xiaodu_get_ai_call_task_status",
                {"task_id": task_id},
            )
            poll_error = None
        except AppError as exc:
            poll_error = redact_text(str(exc))

    if status != "COMPLETED":
        message_value = recursive_find(last_payload, "message")
        message = transcript_to_text(message_value).strip()
        if status == "FAILED":
            summary = message or "AI 电话任务失败"
            recorded_status = "unreachable"
        else:
            summary = f"AI 电话状态查询超时：{poll_error or status}"
            recorded_status = "unknown"
        event_id, notified, notification_error = finalize_failed_followup(
            config=config,
            elder=elder,
            connection=connection,
            now=now,
            started_at=started_at,
            due_count=len(due),
            status=recorded_status,
            summary=summary,
            task_id=task_id,
            raw=last_envelope,
            notify=not args.no_notify,
        )
        connection.close()
        print_json(
            {
                "event_id": event_id,
                "status": recorded_status,
                "task_id": task_id,
                "summary": summary,
                "app_notified": notified,
                "notification_error": notification_error,
            }
        )
        return 2

    summary, transcript = interaction_fields(last_payload)
    scheduled = scheduled_doses_for_classification(due)
    event_id = insert_followup(
        connection,
        elder_id=elder["id"],
        local_date=now.date().isoformat(),
        started_at=started_at,
        completed_at=dt.datetime.now(timezone).isoformat(),
        status="unknown",
        source="ai_call",
        task_id=task_id,
        expected_doses=len(due),
        summary="等待智能体完成语义分析",
        transcript=transcript,
        raw=last_envelope,
        classification_state="pending",
        scheduled=scheduled,
    )
    input_path = write_classification_input(
        paths,
        event_id=event_id,
        task_id=task_id,
        elder=elder,
        scheduled=scheduled,
        summary=summary,
        transcript=transcript,
    )
    connection.close()
    print_json(
        {
            "event_id": event_id,
            "status": "classification_pending",
            "task_id": task_id,
            "classification_input": str(input_path),
            "classification_contract": str(
                Path(__file__).resolve().parent.parent / "references" / "classification-contract.md"
            ),
            "app_notified": False,
        }
    )
    return 0


def cmd_prepare_classification(args: argparse.Namespace, paths: StatePaths) -> int:
    config = load_config(paths)
    connection = connect_database(paths)
    row = get_followup(connection, args.event_id)
    if row["classification_state"] != "pending":
        connection.close()
        raise AppError(f"follow-up event {args.event_id} is not awaiting classification")
    elder = get_elder(config, row["elder_id"])
    scheduled = json.loads(row["scheduled_json"] or "[]")
    transcript = json.loads(row["transcript_json"] or "[]")
    path = write_classification_input(
        paths,
        event_id=int(row["id"]),
        task_id=str(row["task_id"] or ""),
        elder=elder,
        scheduled=scheduled,
        summary=transcript_to_text(recursive_find(json.loads(row["raw_json"] or "{}"), "summary"))
        or "通话已完成，但未返回明确摘要",
        transcript=transcript,
    )
    connection.close()
    print_json(
        {
            "event_id": int(row["id"]),
            "status": "classification_pending",
            "classification_input": str(path),
            "classification_contract": str(
                Path(__file__).resolve().parent.parent / "references" / "classification-contract.md"
            ),
        }
    )
    return 0


def read_json_argument(path_value: str) -> Any:
    if path_value == "-":
        raw_text = sys.stdin.read()
    else:
        raw_text = Path(path_value).expanduser().read_text(encoding="utf-8")
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise AppError(f"invalid classification JSON: {redact_text(str(exc))}") from exc


def cmd_finalize(args: argparse.Namespace, paths: StatePaths) -> int:
    config = load_config(paths)
    connection = connect_database(paths)
    row = get_followup(connection, args.event_id)
    if row["classification_state"] != "pending":
        connection.close()
        raise AppError(f"follow-up event {args.event_id} is not awaiting classification")
    scheduled = json.loads(row["scheduled_json"] or "[]")
    transcript = json.loads(row["transcript_json"] or "[]")
    participant_utterances = [
        turn["text"]
        for turn in classification_turns(transcript)
        if turn["speaker"] == "target"
    ]
    classification = validate_model_classification(
        read_json_argument(args.input),
        scheduled=scheduled,
        participant_utterances=participant_utterances,
    )
    result_status = derive_classification_status(classification)
    elder = get_elder(config, row["elder_id"])
    notified = False
    notification_error = None
    if (
        not args.no_notify
        and elder["notifications"]["alert_app"]
        and result_status in config["abnormal_statuses"]
    ):
        try:
            send_exception_notification(config, elder, result_status, classification["summary"])
            notified = True
        except AppError as exc:
            notification_error = str(exc)

    connection.execute(
        """
        UPDATE followups
        SET status = ?, summary = ?, classification_state = 'final',
            classification_json = ?, notified_app = ?, notification_error = ?
        WHERE id = ? AND classification_state = 'pending'
        """,
        (
            result_status,
            classification["summary"],
            json.dumps(classification, ensure_ascii=False),
            int(notified),
            concise_summary(notification_error, 1000) if notification_error else None,
            args.event_id,
        ),
    )
    connection.commit()
    connection.close()
    pending_path = classification_input_path(paths, args.event_id)
    if pending_path.exists():
        pending_path.unlink()
    print_json(
        {
            "event_id": args.event_id,
            "status": result_status,
            "status_label": STATUS_LABELS[result_status],
            "task_id": row["task_id"],
            "summary": classification["summary"],
            "confidence": classification["confidence"],
            "app_notified": notified,
            "notification_error": notification_error,
        }
    )
    return 0 if result_status == "adherent" else 2


def cmd_record(args: argparse.Namespace, paths: StatePaths) -> int:
    config = load_config(paths)
    elder = get_elder(config, args.elder_id)
    timezone = ZoneInfo(config["timezone"])
    observed = parse_local_datetime(args.observed_at, timezone)
    expected_doses = args.expected_doses
    if expected_doses is None:
        expected_doses = len(medication_schedule_for_date(elder, observed.date()))
    notified = False
    notification_error = None
    if (
        args.notify
        and elder["notifications"]["alert_app"]
        and args.status in config["abnormal_statuses"]
    ):
        try:
            send_exception_notification(config, elder, args.status, args.summary)
            notified = True
        except AppError as exc:
            notification_error = str(exc)
    connection = connect_database(paths)
    event_id = insert_followup(
        connection,
        elder_id=elder["id"],
        local_date=observed.date().isoformat(),
        started_at=observed.isoformat(),
        completed_at=observed.isoformat(),
        status=args.status,
        source="manual",
        task_id=None,
        expected_doses=expected_doses,
        summary=args.summary,
        notified_app=notified,
        notification_error=notification_error,
    )
    connection.close()
    print_json(
        {
            "event_id": event_id,
            "status": args.status,
            "app_notified": notified,
            "notification_error": notification_error,
        }
    )
    return 0


def cmd_report(args: argparse.Namespace, paths: StatePaths) -> int:
    config = load_config(paths)
    elder = get_elder(config, args.elder_id)
    timezone = ZoneInfo(config["timezone"])
    now = dt.datetime.now(timezone)
    if args.anchor:
        try:
            anchor = dt.date.fromisoformat(args.anchor)
        except ValueError as exc:
            raise AppError("anchor must use YYYY-MM-DD") from exc
    else:
        anchor = now.date()
    start, end = period_bounds(args.period, anchor, args.previous)
    if start > now.date():
        raise AppError("the requested report period is in the future")
    end = min(end, now.date())
    connection = connect_database(paths)
    rows = query_period_rows(connection, elder["id"], start, end)
    ensure_private_dir(paths.reports)
    stem = f"{elder['id']}-{args.period}-{start.isoformat()}-{end.isoformat()}"
    private_path = paths.reports / f"{stem}.html"
    private_html = render_report(
        config=config,
        elder=elder,
        rows=rows,
        period=args.period,
        start=start,
        end=end,
        generated_at=now,
        public=False,
    )
    atomic_write_text(private_path, private_html)

    result: dict[str, Any] = {
        "period": args.period,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "records": len(rows),
        "private_report": str(private_path),
        "published": False,
    }
    exit_code = 0
    if args.push and not args.publish:
        connection.close()
        raise AppError("--push requires --publish because notifications need a public URL")

    if args.publish:
        if not config["report"]["public_consent"] and not args.force_public:
            connection.close()
            raise AppError(
                "Surge publishing is public and public_consent is false; obtain explicit consent before publishing"
            )
        public_path = paths.reports / f"{stem}.public.html"
        public_html = render_report(
            config=config,
            elder=elder,
            rows=rows,
            period=args.period,
            start=start,
            end=end,
            generated_at=now,
            public=True,
        )
        atomic_write_text(public_path, public_html)
        url = publish_to_surge(paths, public_path, config)
        result.update({"published": True, "public_report": str(public_path), "url": url})
        app_pushed = False
        device_pushed = False
        device_opened = False
        push_error = None
        if args.push:
            open_device = args.open_device or config["report"]["open_device"]
            app_pushed, device_pushed, device_opened, push_error = push_report(
                config,
                elder,
                period=args.period,
                url=url,
                open_device=open_device,
            )
            result.update(
                {
                    "app_pushed": app_pushed,
                    "device_pushed": device_pushed,
                    "device_opened": device_opened,
                    "push_error": push_error,
                }
            )
            if push_error:
                exit_code = 2
        connection.execute(
            """
            INSERT INTO publications (
                elder_id, period, period_start, period_end, created_at,
                local_report_path, public_url, app_pushed, device_pushed,
                device_opened, push_error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                elder["id"],
                args.period,
                start.isoformat(),
                end.isoformat(),
                now.isoformat(),
                str(private_path),
                url,
                int(app_pushed),
                int(device_pushed),
                int(device_opened),
                concise_summary(push_error, 1000) if push_error else None,
            ),
        )
        connection.commit()

    connection.close()
    print_json(result)
    return exit_code


def sample_config() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "timezone": "Asia/Shanghai",
        "default_elder_id": "mom",
        "mcporter": {"server": "xiaodu", "timeout_ms": 30000},
        "abnormal_statuses": list(DEFAULT_ABNORMAL),
        "elders": [
            {
                "id": "mom",
                "role": "妈妈",
                "display_name": "妈妈",
                "device": {"name": "测试屏", "client_id": "client-test", "cuid": "cuid-test"},
                "notifications": {"alert_app": True},
                "medications": [
                    {
                        "id": "morning",
                        "name": "测试药品",
                        "report_label": "晨间用药",
                        "dose": "1片",
                        "times": ["08:00"],
                        "days_of_week": list(range(7)),
                        "instructions": "早餐后",
                    }
                ],
            }
        ],
        "report": {
            "surge_domain": "example.surge.sh",
            "public_consent": True,
            "public_mode": "family",
            "push_app": True,
            "push_device": True,
            "open_device": False,
        },
    }


def cmd_self_test(args: argparse.Namespace, paths: StatePaths) -> int:
    del args, paths
    assertions = 0
    wrapped = {
        "content": [
            {"type": "text", "text": '{"task_id":"task-test","status":"PENDING"}'}
        ]
    }
    parsed = unwrap_tool_payload(extract_json(json.dumps(wrapped)))
    assert recursive_find(parsed, "task_id") == "task-test"
    assertions += 1
    single_device = {"client_id": "client-test", "cuid": "cuid-test", "device_name": "测试屏"}
    assert find_device_list(single_device) == [single_device]
    assertions += 1
    scheduled = [
        {
            "medication_id": "morning-medicine",
            "name": "测试药品",
            "scheduled_time": "08:00",
            "expected_dose": "1片",
            "instructions": "早餐后",
        }
    ]
    participant_utterances = ["早上8点吃了1片。", "没有出现不舒服。", "家人代答。"]
    adherent_analysis = {
        "schema_version": 1,
        "summary": "家人确认已于08:00服用1片，服药后无不适。",
        "medications": [
            {
                "medication_id": "morning-medicine",
                "scheduled_time": "08:00",
                "taken": "yes",
                "timing": "on_time",
                "dose": "correct",
                "actual_time": "08:00",
                "actual_dose": "1片",
            }
        ],
        "adverse_effect": "no",
        "symptoms": [],
        "responder": "family",
        "evidence": participant_utterances,
        "confidence": 0.98,
        "conflicts": [],
    }
    normalized_analysis = validate_model_classification(
        adherent_analysis,
        scheduled=scheduled,
        participant_utterances=participant_utterances,
    )
    assert derive_classification_status(normalized_analysis) == "adherent"
    assertions += 1
    auto_domain_config = sample_config()
    auto_domain_config["report"]["surge_domain"] = "auto"
    generated_domain = validate_config(auto_domain_config)["report"]["surge_domain"]
    assert re.fullmatch(r"family-care-\d{8}-[0-9a-f]{12}\.surge\.sh", generated_domain)
    assertions += 1
    low_confidence = copy.deepcopy(normalized_analysis)
    low_confidence["confidence"] = 0.6
    assert derive_classification_status(low_confidence) == "unknown"
    assertions += 1
    adverse = copy.deepcopy(normalized_analysis)
    adverse["adverse_effect"] = "yes"
    adverse["symptoms"] = ["头晕"]
    adverse["confidence"] = 0.7
    assert derive_classification_status(adverse) == "adverse_effect"
    assertions += 1
    bad_evidence = copy.deepcopy(adherent_analysis)
    bad_evidence["evidence"] = ["原始对话中不存在的句子"]
    try:
        validate_model_classification(
            bad_evidence,
            scheduled=scheduled,
            participant_utterances=participant_utterances,
        )
    except AppError:
        assertions += 1
    else:
        raise AssertionError("invented evidence must be rejected")

    with tempfile.TemporaryDirectory(prefix=f"{APP_NAME}-test-") as temporary:
        test_paths = resolve_paths(temporary)
        config = validate_config(sample_config())
        save_config(test_paths, config)
        connection = connect_database(test_paths)
        timezone = ZoneInfo(config["timezone"])
        now = dt.datetime.now(timezone)
        insert_followup(
            connection,
            elder_id="mom",
            local_date=now.date().isoformat(),
            started_at=now.isoformat(),
            completed_at=now.isoformat(),
            status="adherent",
            source="manual",
            task_id=None,
            expected_doses=1,
            summary="测试记录",
        )
        rows = query_period_rows(connection, "mom", now.date(), now.date())
        report = render_report(
            config=config,
            elder=config["elders"][0],
            rows=rows,
            period="week",
            start=now.date(),
            end=now.date(),
            generated_at=now,
            public=True,
        )
        assert "测试记录" in report
        assert "测试药品" in report
        assert "1片" in report
        assert "早餐后" not in report
        assert "按时确认" in report
        assert "data-label=\"来源\"" not in report
        assert ">manual<" not in report
        assert "状态趋势" in report
        assert "data-status=\"adherent\"" in report
        assertions += 9
        aggregate_config = copy.deepcopy(config)
        aggregate_config["report"]["public_mode"] = "aggregate"
        aggregate_report = render_report(
            config=aggregate_config,
            elder=aggregate_config["elders"][0],
            rows=rows,
            period="week",
            start=now.date(),
            end=now.date(),
            generated_at=now,
            public=True,
        )
        assert "测试药品" not in aggregate_report
        assert "测试记录" not in aggregate_report
        assertions += 2
        connection.close()

        if os.name != "nt":
            mock_path = Path(temporary) / "fake-mcporter.py"
            mock_source = r'''#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

selector = sys.argv[2] if len(sys.argv) > 2 else ""

def emit(payload):
    wrapped = {
        "content": [
            {"type": "text", "text": json.dumps(payload, ensure_ascii=False)}
        ]
    }
    print(json.dumps(wrapped, ensure_ascii=False))

if selector.endswith(".xiaodu_trigger_ai_call"):
    emit({"task_id": "task-offline-test", "status": "PENDING"})
elif selector.endswith(".xiaodu_get_ai_call_task_status"):
    state_path = Path(os.environ["FAKE_MCPORTER_STATE"])
    count = int(state_path.read_text() or "0") if state_path.exists() else 0
    count += 1
    state_path.write_text(str(count))
    if count == 1:
        emit({"task_id": "task-offline-test", "status": "PROCESSING"})
    else:
        emit({
            "task_id": "task-offline-test",
            "status": "COMPLETED",
            "interaction_report": {
                "summary": "今天忘记服药",
                "full_transcript": [{"speaker": "target", "text": "家人确认今天忘记服药"}]
            }
        })
elif selector.endswith(".xiaodu_send_notification"):
    Path(os.environ["FAKE_MCPORTER_NOTIFICATIONS"]).write_text("sent")
    emit({"status": "success"})
else:
    emit({"status": "success"})
'''
            atomic_write_text(mock_path, mock_source, mode=0o700)
            integration_root = Path(temporary) / "integration"
            integration_paths = resolve_paths(str(integration_root))
            integration_config = sample_config()
            integration_config["mcporter"]["binary"] = str(mock_path)
            save_config(integration_paths, integration_config)
            state_path = Path(temporary) / "poll-count"
            notification_path = Path(temporary) / "notification-sent"
            environment = os.environ.copy()
            environment["FAKE_MCPORTER_STATE"] = str(state_path)
            environment["FAKE_MCPORTER_NOTIFICATIONS"] = str(notification_path)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--home",
                    str(integration_root),
                    "follow-up",
                    "--all-today",
                    "--poll-interval",
                    "0.01",
                    "--poll-timeout",
                    "2",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
                env=environment,
            )
            assert completed.returncode == 0, completed.stderr
            result = extract_json(completed.stdout)
            assert result["status"] == "classification_pending"
            assert result["app_notified"] is False
            assert int(state_path.read_text()) >= 2
            assert not notification_path.exists()
            analysis_path = Path(temporary) / "analysis.json"
            missed_analysis = {
                "schema_version": 1,
                "summary": "家人确认今天忘记服药。",
                "medications": [
                    {
                        "medication_id": "morning",
                        "scheduled_time": "08:00",
                        "taken": "no",
                        "timing": "unknown",
                        "dose": "unknown",
                        "actual_time": None,
                        "actual_dose": None,
                    }
                ],
                "adverse_effect": "unknown",
                "symptoms": [],
                "responder": "family",
                "evidence": ["家人确认今天忘记服药"],
                "confidence": 0.99,
                "conflicts": [],
            }
            atomic_write_text(
                analysis_path,
                json.dumps(missed_analysis, ensure_ascii=False, indent=2) + "\n",
            )
            finalized = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--home",
                    str(integration_root),
                    "finalize",
                    "--event-id",
                    str(result["event_id"]),
                    "--input",
                    str(analysis_path),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
                env=environment,
            )
            assert finalized.returncode == 2, finalized.stderr
            final_result = extract_json(finalized.stdout)
            assert final_result["status"] == "missed"
            assert final_result["app_notified"] is True
            assert notification_path.read_text() == "sent"
            integration_connection = connect_database(integration_paths)
            stored = integration_connection.execute(
                "SELECT status, classification_state, notified_app FROM followups ORDER BY id DESC LIMIT 1"
            ).fetchone()
            assert stored is not None and stored["status"] == "missed"
            assert stored["classification_state"] == "final"
            assert stored["notified_app"] == 1
            integration_connection.close()
            assertions += 12

    print_json({"ok": True, "assertions": assertions, "live_external_calls": 0})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Follow up elder medication through Xiaodu AI calls using mcporter."
    )
    parser.add_argument(
        "--home",
        help="State directory; defaults to XIAODU_MEDICATION_HOME or ~/.xiaodu-medication-followup",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    configure = subparsers.add_parser("configure", help="Validate and store first-use configuration")
    configure.add_argument("--input", required=True, help="JSON file path or - for stdin")
    configure.add_argument("--replace", action="store_true", help="Replace existing config; history remains")
    configure.set_defaults(handler=cmd_configure)

    doctor = subparsers.add_parser("doctor", help="Check dependencies and configuration")
    doctor.add_argument("--network", action="store_true", help="Also verify live tool discovery and Surge login")
    doctor.set_defaults(handler=cmd_doctor)

    devices = subparsers.add_parser("devices", help="List Xiaodu devices through mcporter")
    devices.add_argument("--server", default="xiaodu")
    devices.add_argument("--timeout-ms", type=int, default=30000)
    devices.set_defaults(handler=cmd_devices)

    follow_up = subparsers.add_parser("follow-up", help="Run and persist an AI medication call")
    follow_up.add_argument("--elder-id")
    follow_up.add_argument("--at", help="ISO 8601 time; defaults to now")
    follow_up.add_argument("--all-today", action="store_true", help="Include future doses scheduled today")
    follow_up.add_argument("--dry-run", action="store_true", help="Print task without making a call")
    follow_up.add_argument("--no-notify", action="store_true", help="Do not send automatic exception notification")
    follow_up.add_argument("--force", action="store_true", help="Allow another call after a same-day record")
    follow_up.add_argument("--poll-interval", type=float, default=5.0)
    follow_up.add_argument("--poll-timeout", type=float, default=900.0)
    follow_up.set_defaults(handler=cmd_follow_up)

    prepare = subparsers.add_parser(
        "prepare-classification",
        help="Regenerate the private model input for a pending follow-up",
    )
    prepare.add_argument("--event-id", required=True, type=int)
    prepare.set_defaults(handler=cmd_prepare_classification)

    finalize = subparsers.add_parser(
        "finalize",
        help="Validate model analysis, finalize the record, and notify exceptions",
    )
    finalize.add_argument("--event-id", required=True, type=int)
    finalize.add_argument("--input", required=True, help="Classification JSON file path or - for stdin")
    finalize.add_argument("--no-notify", action="store_true")
    finalize.set_defaults(handler=cmd_finalize)

    record = subparsers.add_parser("record", help="Store a manually verified result")
    record.add_argument("--elder-id")
    record.add_argument("--status", required=True, choices=STATUSES)
    record.add_argument("--summary", required=True)
    record.add_argument("--observed-at", help="ISO 8601 time; defaults to now")
    record.add_argument("--expected-doses", type=int)
    record.add_argument("--notify", action="store_true")
    record.set_defaults(handler=cmd_record)

    report = subparsers.add_parser("report", help="Generate, publish, and push a period report")
    report.add_argument("--elder-id")
    report.add_argument("--period", required=True, choices=("week", "month"))
    report.add_argument("--anchor", help="Date inside the period, YYYY-MM-DD")
    report.add_argument("--previous", action="store_true", help="Use the previous complete week/month")
    report.add_argument("--publish", action="store_true", help="Publish a public copy to Surge")
    report.add_argument("--push", action="store_true", help="Push published URL to App/device")
    report.add_argument("--open-device", action="store_true", help="Open URL immediately on screen")
    report.add_argument(
        "--force-public",
        action="store_true",
        help="Explicit one-time public consent override",
    )
    report.set_defaults(handler=cmd_report)

    self_test = subparsers.add_parser("self-test", help="Run offline parser, classifier, DB, and report tests")
    self_test.set_defaults(handler=cmd_self_test)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    paths = resolve_paths(args.home)
    try:
        return int(args.handler(args, paths))
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        return 130
    except (AppError, OSError, sqlite3.Error) as exc:
        print(f"ERROR: {redact_text(str(exc), 2000)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
