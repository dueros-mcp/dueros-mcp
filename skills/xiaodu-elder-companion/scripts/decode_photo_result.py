#!/usr/bin/env python3
"""Decode xiaodu_take_photo mcporter output into an inspectable image file."""
from __future__ import annotations

import argparse
import ast
import base64
import json
import re
import sys
from pathlib import Path
from typing import Any


DATA_RE = re.compile(r"data:\s*(['\"])(.*?)\1", re.DOTALL)
MIME_RE = re.compile(r"mimeType:\s*(['\"])(.*?)\1", re.DOTALL)


def fail(message: str) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    return 1


def walk_images(value: Any) -> tuple[str, str] | None:
    if isinstance(value, dict):
        if value.get("type") == "image" and isinstance(value.get("data"), str):
            mime = value.get("mimeType")
            return value["data"], mime if isinstance(mime, str) else ""
        for item in value.values():
            found = walk_images(item)
            if found:
                return found
    elif isinstance(value, list):
        for item in value:
            found = walk_images(item)
            if found:
                return found
    return None


def parse_json_like(raw: str) -> tuple[str, str] | None:
    for decoder in (json.loads, ast.literal_eval):
        try:
            parsed = decoder(raw)
        except Exception:
            continue
        found = walk_images(parsed)
        if found:
            return found
    return None


def extract_payload(raw: str) -> tuple[str, str]:
    found = parse_json_like(raw)
    if found:
        return found

    data_match = DATA_RE.search(raw)
    if not data_match:
        raise ValueError("no image data field found")
    mime_match = MIME_RE.search(raw)
    return data_match.group(2), mime_match.group(2) if mime_match else ""


def output_path(input_path: Path, requested: str | None, mime_type: str) -> Path:
    if requested:
        return Path(requested)
    if mime_type == "image/png":
        return input_path.with_suffix(".png")
    if mime_type == "image/webp":
        return input_path.with_suffix(".webp")
    return input_path.with_suffix(".jpg")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Raw mcporter xiaodu_take_photo output file")
    parser.add_argument("-o", "--output", help="Decoded image output path")
    args = parser.parse_args()

    input_path = Path(args.input)
    try:
        raw = input_path.read_text(encoding="utf-8")
        payload, mime_type = extract_payload(raw)
        image_bytes = base64.b64decode(payload, validate=True)
    except Exception as exc:
        return fail(str(exc))

    target = output_path(input_path, args.output, mime_type)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(image_bytes)
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
