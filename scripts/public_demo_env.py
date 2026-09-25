"""Generate deploy/public-demo/.env from .env.example with fresh secrets.

Usage:
    py -3.12 scripts/public_demo_env.py                 # create .env if absent
    py -3.12 scripts/public_demo_env.py --rotate REDIS_PASSWORD [--rotate ...]
    py -3.12 scripts/public_demo_env.py --set PUBLIC_DASHBOARD_UUID=<uuid>

Values are hex (safe inside connection URLs) except the Airflow Fernet key,
which is 32 random bytes in URL-safe base64. Secrets are never printed.
"""

from __future__ import annotations

import argparse
import base64
import os
import secrets
import sys
from pathlib import Path

DEMO_DIR = Path(__file__).resolve().parent.parent / "deploy" / "public-demo"
EXAMPLE = DEMO_DIR / ".env.example"
TARGET = DEMO_DIR / ".env"


def generate(placeholder: str) -> str:
    if placeholder == "__GENERATE_FERNET__":
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii")
    return secrets.token_hex(24)


def render(example_text: str) -> str:
    lines = []
    for line in example_text.splitlines():
        key, sep, value = line.partition("=")
        if sep and not line.lstrip().startswith("#") and value.startswith("__GENERATE"):
            line = f"{key}={generate(value.strip())}"
        lines.append(line)
    return "\n".join(lines) + "\n"


def update(text: str, key: str, value: str) -> str:
    lines, found = [], False
    for line in text.splitlines():
        if line.partition("=")[0] == key and not line.startswith("#"):
            line, found = f"{key}={value}", True
        lines.append(line)
    if not found:
        raise SystemExit(f"{key} is not defined in {TARGET.name}")
    return "\n".join(lines) + "\n"


def write(text: str) -> None:
    TARGET.write_text(text, encoding="utf-8", newline="\n")
    if os.name == "posix":
        TARGET.chmod(0o600)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rotate", action="append", default=[], metavar="KEY", help="replace one generated secret with a new value")
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE", help="set a non-secret value such as PUBLIC_DASHBOARD_UUID")
    args = parser.parse_args(argv)

    if not TARGET.exists():
        write(render(EXAMPLE.read_text(encoding="utf-8")))
        print(f"created {TARGET.relative_to(DEMO_DIR.parent.parent)}")
    elif not args.rotate and not args.set:
        print(f"{TARGET.name} already exists; use --rotate KEY or --set KEY=VALUE", file=sys.stderr)
        return 1

    text = TARGET.read_text(encoding="utf-8")
    example = {line.partition("=")[0]: line.partition("=")[2] for line in EXAMPLE.read_text(encoding="utf-8").splitlines() if "=" in line and not line.startswith("#")}
    for key in args.rotate:
        placeholder = example.get(key, "")
        if not placeholder.startswith("__GENERATE"):
            raise SystemExit(f"{key} is not a generated secret")
        text = update(text, key, generate(placeholder))
        print(f"rotated {key}")
    for item in args.set:
        key, _, value = item.partition("=")
        if example.get(key, "").startswith("__GENERATE"):
            raise SystemExit(f"{key} is a secret; use --rotate")
        text = update(text, key, value)
        print(f"set {key}")
    write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
