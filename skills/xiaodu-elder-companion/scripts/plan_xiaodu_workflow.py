#!/usr/bin/env python3
"""Generate deterministic Xiaodu MCP workflow call plans."""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List


LOCATION_NOTICE = "我先确认一下家人在不在这边。"
DEFAULT_ELDER_APP = "梨园行戏曲HD"
PREFERENCE_APP_MAP = {
    "戏曲": "梨园行戏曲HD",
    "豫剧": "梨园行戏曲HD",
    "京剧": "梨园行戏曲HD",
    "评书": "音乐",
    "相声": "音乐",
    "广播": "音乐",
    "老歌": "音乐",
    "音乐": "音乐",
    "广场舞": "视频",
    "健康": "生活",
    "养生": "生活",
}


def resolve_elder_app(preferred_app: str, preference: str) -> str:
    preferred_app = preferred_app.strip()
    if preferred_app:
        return preferred_app
    preference = preference.strip()
    if preference:
        return PREFERENCE_APP_MAP.get(preference, DEFAULT_ELDER_APP)
    return DEFAULT_ELDER_APP


def companion_text(elder: str, app_name: str) -> str:
    title = "阿姨" if elder == "female" else "叔叔"
    if app_name == "梨园行戏曲HD":
        content = "您可以听您喜欢的戏曲"
    elif app_name == "音乐":
        content = "我会给您找一段轻松好听的内容"
    elif app_name == "视频":
        content = "我会给您找一段轻松的视频内容"
    elif app_name == "生活":
        content = "我会给您找一个轻松的生活服务"
    else:
        content = "您可以听一会儿喜欢的内容"
    return f"{title}，我先给您设置一下：30 分钟后提醒您站立活动一下身体并放松眼睛。然后再帮您打开{app_name}，{content}。"


def step(tool: str, args: Dict[str, Any], note: str) -> Dict[str, Any]:
    return {"server": "xiaodu", "tool": tool, "arguments": args, "note": note}


def elder_care(args: argparse.Namespace) -> Dict[str, Any]:
    selected_app = resolve_elder_app(args.preferred_app, args.preference)
    companion = companion_text(args.elder, selected_app)
    device_hint = {"device_name": args.device_name} if args.device_name else {}
    plan: List[Dict[str, Any]] = [
        step("list_user_devices", {}, "Find online Xiaodu screen/camera devices for location checking."),
        step("xiaodu_speak", {**device_hint, "text": LOCATION_NOTICE}, "Give the shortest transparent notice before the location photo."),
        step("xiaodu_take_photo", device_hint, "Take a location photo before full companion speech; if multiple devices are plausible, repeat this notice/photo pair serially and choose only the device where the elder is visible as a live in-room person, not a screen/photo/album image."),
        step("xiaodu_speak", {**device_hint, "text": companion}, f"After selecting the elder's device, explain that the reminder will be set before opening {selected_app}."),
        step("control_xiaodu", {**device_hint, "command": "设置 30 分钟后提醒站立活动一下身体并放松眼睛"}, "Set stand-up and eye-relax reminder before entertainment."),
        step("query_xiaodu_skills", {**device_hint, "query": selected_app}, f"Search {selected_app} first based on agent memory or curated fallback."),
        step("xiaodu_open_skill", {**device_hint, "app_key": "<app_key from query_xiaodu_skills>"}, "Open only with returned app_key on the selected device."),
    ]
    return {
        "workflow": "elder-care",
        "selected_app": selected_app,
        "selection_source": "preferred_app" if args.preferred_app.strip() else ("preference" if args.preference.strip() else "curated_default"),
        "fallback_skill_queries": ["音乐", "视频", "生活"],
        "steps": plan,
    }


def open_skill(args: argparse.Namespace) -> Dict[str, Any]:
    device_hint = {"device_name": args.device_name} if args.device_name else {}
    return {
        "workflow": "open-skill",
        "steps": [
            step("list_user_devices", {}, "Select target Xiaodu device if not already selected."),
            step("query_xiaodu_skills", {**device_hint, "query": args.query}, "Search by exact app name or exact type key."),
            step("xiaodu_open_skill", {**device_hint, "app_key": "<app_key from query_xiaodu_skills>"}, "Open only with returned app_key."),
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="workflow", required=True)

    elder = sub.add_parser("elder-care")
    elder.add_argument("--device-name", default="")
    elder.add_argument("--elder", choices=["male", "female"], default="male")
    elder.add_argument("--preferred-app", default="", help="Exact App remembered by the agent for this elder")
    elder.add_argument("--preference", default="", help="Remembered elder content preference, e.g. 戏曲/评书/老歌/广播")
    elder.set_defaults(func=elder_care)

    open_skill_parser = sub.add_parser("open-skill")
    open_skill_parser.add_argument("query")
    open_skill_parser.add_argument("--device-name", default="")
    open_skill_parser.set_defaults(func=open_skill)

    args = parser.parse_args()
    json.dump(args.func(args), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
