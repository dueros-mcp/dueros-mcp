#!/usr/bin/env bash
set -euo pipefail

INSTALL_MISSING=0
LOGIN_SURGE=0
CONFIGURE_XIAODU=0

usage() {
  printf '%s\n' \
    'Usage: setup.sh --check [--install] [--login-surge] [--configure-xiaodu]' \
    '' \
    '  --check              Check dependencies and configuration (default).' \
    '  --install            Install missing mcporter/surge packages with npm.' \
    '  --login-surge        Run the interactive Surge login.' \
    '  --configure-xiaodu   Add a home-scoped xiaodu entry using' \
    '                       XIAODU_MCP_URL and XIAODU_ACCESS_TOKEN.'
}

while (($#)); do
  case "$1" in
    --check) ;;
    --install) INSTALL_MISSING=1 ;;
    --login-surge) LOGIN_SURGE=1 ;;
    --configure-xiaodu) CONFIGURE_XIAODU=1 ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'Unknown argument: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

if ! command -v python3 >/dev/null 2>&1; then
  printf 'ERROR: Python 3.9 or newer is required.\n' >&2
  exit 1
fi

PYTHON_OK="$(python3 -c 'import sys; print(int(sys.version_info >= (3, 9)))')"
if [[ "$PYTHON_OK" != "1" ]]; then
  printf 'ERROR: Python 3.9 or newer is required.\n' >&2
  exit 1
fi

if [[ "$INSTALL_MISSING" == "1" ]]; then
  if ! command -v npm >/dev/null 2>&1; then
    printf 'ERROR: npm is required to install mcporter and Surge. Install Node.js LTS first.\n' >&2
    exit 1
  fi

  PACKAGES=()
  command -v mcporter >/dev/null 2>&1 || PACKAGES+=(mcporter)
  command -v surge >/dev/null 2>&1 || PACKAGES+=(surge)
  if ((${#PACKAGES[@]})); then
    NPM_CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/xiaodu-medication-followup/npm"
    mkdir -p "$NPM_CACHE_DIR"
    npm --cache "$NPM_CACHE_DIR" install --global "${PACKAGES[@]}"
  fi
fi

if [[ "$CONFIGURE_XIAODU" == "1" ]]; then
  if ! command -v mcporter >/dev/null 2>&1; then
    printf 'ERROR: mcporter is not installed.\n' >&2
    exit 1
  fi
  if mcporter config get xiaodu --json >/dev/null 2>&1; then
    printf 'Xiaodu server already exists; existing configuration was preserved.\n'
  else
    : "${XIAODU_MCP_URL:?Set XIAODU_MCP_URL before configuring Xiaodu.}"
    : "${XIAODU_ACCESS_TOKEN:?Set XIAODU_ACCESS_TOKEN before configuring Xiaodu.}"
    mcporter config add xiaodu \
      --scope home \
      --url "$XIAODU_MCP_URL" \
      --header "ACCESS_TOKEN=$XIAODU_ACCESS_TOKEN" \
      --header 'accept=application/json, text/event-stream'
  fi
fi

if [[ "$LOGIN_SURGE" == "1" ]]; then
  if ! command -v surge >/dev/null 2>&1; then
    printf 'ERROR: Surge is not installed.\n' >&2
    exit 1
  fi
  surge login
fi

printf 'python3: %s\n' "$(python3 --version 2>&1)"
SETUP_OK=1
if command -v mcporter >/dev/null 2>&1; then
  printf 'mcporter: %s\n' "$(mcporter --version 2>&1 | head -n 1)"
else
  printf 'mcporter: MISSING\n'
  SETUP_OK=0
fi
if command -v surge >/dev/null 2>&1; then
  printf 'surge: installed\n'
else
  printf 'surge: MISSING (required only for public reports)\n'
fi
if command -v mcporter >/dev/null 2>&1 && mcporter config get xiaodu --json >/dev/null 2>&1; then
  printf 'xiaodu mcporter config: present\n'
else
  printf 'xiaodu mcporter config: MISSING\n'
  SETUP_OK=0
fi

if [[ "$SETUP_OK" != "1" ]]; then
  exit 1
fi
