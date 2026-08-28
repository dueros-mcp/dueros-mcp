#!/usr/bin/env python3
"""Package a static travel itinerary page and publish it to Surge."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request


EXCLUDE_DIRS = {
    ".git",
    ".playwright-cli",
    "__pycache__",
    "node_modules",
    "output",
    "surge-dist",
}

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


@dataclass
class DeployResult:
    deploy_dir: Path
    domain: str
    url: str


class SurgeAuthError(RuntimeError):
    pass


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "travel-plan"


def normalize_domain(domain: str | None, source: Path) -> str:
    if domain:
        cleaned = domain.strip().removeprefix("https://").removeprefix("http://").strip("/")
        if "." not in cleaned:
            cleaned = f"{cleaned}.surge.sh"
        return cleaned
    suffix = time.strftime("%m%d%H%M")
    return f"{slugify(source.stem)}-{suffix}.surge.sh"


def strip_ansi(value: str) -> str:
    return ANSI_RE.sub("", value)


def copy_directory(source: Path, target: Path) -> None:
    def is_relative_to(path: Path, base: Path) -> bool:
        try:
            path.relative_to(base)
            return True
        except ValueError:
            return False

    def ignore(dir_path: str, names: list[str]) -> set[str]:
        ignored = {name for name in names if name in EXCLUDE_DIRS}
        current = Path(dir_path).resolve()
        if is_relative_to(target.resolve(), current):
            ignored.add(target.name)
        return ignored

    shutil.copytree(source, target, ignore=ignore)


def package_source(source: Path, out_root: Path, domain: str) -> Path:
    source = source.resolve()
    if not source.exists():
        raise FileNotFoundError(f"Source not found: {source}")

    deploy_dir = out_root.resolve() / slugify(domain.split(".")[0])
    if deploy_dir.exists():
        shutil.rmtree(deploy_dir)
    deploy_dir.parent.mkdir(parents=True, exist_ok=True)

    if source.is_file():
        if source.suffix.lower() not in {".html", ".htm"}:
            raise ValueError("Single-file source must be an HTML file.")
        deploy_dir.mkdir(parents=True)
        shutil.copy2(source, deploy_dir / "index.html")
        sibling_assets = source.parent / "assets"
        if sibling_assets.is_dir():
            shutil.copytree(sibling_assets, deploy_dir / "assets")
    elif source.is_dir():
        copy_directory(source, deploy_dir)
        if not (deploy_dir / "index.html").exists():
            html_files = sorted(deploy_dir.glob("*.html"))
            if len(html_files) == 1:
                html_files[0].rename(deploy_dir / "index.html")
            else:
                raise ValueError(
                    "Site directory must contain index.html, or exactly one root HTML file."
                )
    else:
        raise ValueError("Source must be an HTML file or directory.")

    (deploy_dir / "CNAME").write_text(domain + "\n", encoding="utf-8")
    return deploy_dir


def surge_command() -> list[str]:
    surge = shutil.which("surge")
    if surge:
        return [surge]
    npx = shutil.which("npx")
    if npx:
        return [npx, "--yes", "surge"]
    raise RuntimeError("Neither surge nor npx is available in PATH.")


def login_command() -> str:
    if shutil.which("surge"):
        return "surge login"
    if shutil.which("npx"):
        return "npx --yes surge login"
    return "npm install --global surge"


def check_auth() -> str:
    cmd = [*surge_command(), "whoami"]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    output = strip_ansi(result.stdout or result.stderr).strip()
    if result.returncode != 0:
        raise SurgeAuthError(
            "Surge login could not be confirmed. "
            f"Run `{login_command()}` first, then rerun this deploy command."
        )
    if not output or "not logged" in output.lower():
        raise SurgeAuthError(
            "Surge is not logged in. "
            f"Run `{login_command()}` first, then rerun this deploy command."
        )
    return output


def publish(deploy_dir: Path, domain: str) -> None:
    cmd = [*surge_command(), str(deploy_dir), domain]
    subprocess.run(cmd, check=True)


def verify(url: str) -> None:
    request = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            if response.status < 200 or response.status >= 400:
                raise RuntimeError(f"Unexpected HTTP status: {response.status}")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Verification failed: HTTP {exc.code}") from exc


def deploy(
    source: Path,
    out_root: Path,
    domain: str | None,
    dry_run: bool,
    no_verify: bool,
    skip_auth_check: bool,
) -> DeployResult:
    final_domain = normalize_domain(domain, source)
    deploy_dir = package_source(source, out_root, final_domain)
    url = f"https://{final_domain}"

    if dry_run:
        print(f"Dry run: packaged {deploy_dir}")
        print(f"Domain: {final_domain}")
        return DeployResult(deploy_dir=deploy_dir, domain=final_domain, url=url)

    if not skip_auth_check:
        account = check_auth()
        print(f"Surge account: {account}")
    publish(deploy_dir, final_domain)
    if not no_verify:
        verify(url)
    return DeployResult(deploy_dir=deploy_dir, domain=final_domain, url=url)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Package and publish a static travel itinerary page to Surge.")
    parser.add_argument("source", nargs="?", help="HTML file or static site directory to publish")
    parser.add_argument("--domain", help="Surge domain, e.g. my-plan.surge.sh")
    parser.add_argument("--out-dir", default="surge-dist", help="Deployment output root")
    parser.add_argument("--dry-run", action="store_true", help="Package files but do not publish")
    parser.add_argument("--no-verify", action="store_true", help="Skip HTTP verification after publish")
    parser.add_argument("--skip-auth-check", action="store_true", help="Skip surge whoami login check")
    parser.add_argument("--check-auth-only", action="store_true", help="Only confirm Surge login, then exit")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        if args.check_auth_only:
            account = check_auth()
            print(f"Surge account: {account}")
            return 0
        if not args.source:
            raise ValueError("Missing source. Provide an HTML file or static site directory.")
        result = deploy(
            source=Path(args.source),
            out_root=Path(args.out_dir),
            domain=args.domain,
            dry_run=args.dry_run,
            no_verify=args.no_verify,
            skip_auth_check=args.skip_auth_check,
        )
    except SurgeAuthError as exc:
        print(f"Login required: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Deploy directory: {result.deploy_dir}")
    print(f"Production URL: {result.url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
