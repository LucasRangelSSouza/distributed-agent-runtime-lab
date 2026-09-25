"""Static host-boundary policy for the public-demo Compose profile.

Reads the fully resolved Compose model (``docker compose config --format json``)
and fails on any of:

- privileged mode, host network/PID/IPC/user namespaces, devices, added capabilities;
- a Docker socket mount, or any host-path bind mount outside the read-only
  config allowlist below (named volumes and tmpfs are fine);
- a missing or root ``user``;
- a missing ``cap_drop: [ALL]``, ``no-new-privileges``, ``read_only`` root
  filesystem, memory limit, restart policy, or (for long-running services)
  health check;
- a published port other than nginx 80->8080 and 443->8443;
- an image with a ``latest`` tag, no explicit tag, or no ``@sha256`` digest.
  A service labelled ``public-demo.image-source=local-build`` may omit the
  digest in local mode only; ``--strict-release`` rejects it;
- attachment to a non-internal network by any service other than nginx
  (edge) and egress-proxy (outbound).

Usage:
    python scripts/check_public_demo_policy.py                 # local mode
    python scripts/check_public_demo_policy.py --strict-release
    python scripts/check_public_demo_policy.py --config-json resolved.json

Without --config-json the script runs ``docker compose config`` itself with
versions.env and .env.example, so it needs no secrets.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
DEMO_DIR = REPO / "deploy" / "public-demo"
PROFILES = ("seed", "checks")

# Host paths that may be bind-mounted, always read-only, relative to DEMO_DIR.
BIND_ALLOWLIST = {
    "nginx/nginx.conf",
    "nginx/templates",
    "nginx/snippets",
    "nginx/html",
    "certs",
    "egress/squid.conf",
    "analytics/init",
    "analytics/fixture",
    "analytics/release",
    "metabase/seed_metabase.py",
}
ALLOWED_PORTS = {"nginx": {("80", 8080), ("443", 8443)}}
OUTBOUND_ALLOWED = {"nginx": {"edge"}, "egress-proxy": {"outbound"}}
ONE_SHOT_PROFILES = set(PROFILES)
LOCAL_BUILD_LABEL = "public-demo.image-source"
DIGEST = re.compile(r"@sha256:[0-9a-f]{64}$")


def _rel(source: str, project_dir: Path) -> str | None:
    try:
        rel = os.path.relpath(os.path.normcase(os.path.abspath(source)), os.path.normcase(os.path.abspath(project_dir)))
    except ValueError:  # different drive on Windows
        return None
    rel = rel.replace("\\", "/")
    return None if rel.startswith("..") else rel


def check_image(name: str, service: dict[str, Any], strict_release: bool) -> list[str]:
    image = service.get("image")
    if not image:
        return [f"{name}: no image; every service must reference a pinned image (no build-only services)"]
    errors = []
    reference, _, digest = image.partition("@")
    last = reference.rsplit("/", 1)[-1]
    tag = last.partition(":")[2]
    if not tag:
        errors.append(f"{name}: image '{image}' has no explicit tag")
    elif tag == "latest":
        errors.append(f"{name}: image '{image}' uses the latest tag")
    if not DIGEST.search(image):
        local = (service.get("labels") or {}).get(LOCAL_BUILD_LABEL) == "local-build"
        if strict_release:
            errors.append(f"{name}: image '{image}' is not pinned by digest (strict release mode)")
        elif not local:
            errors.append(f"{name}: image '{image}' is not pinned by digest and is not labelled {LOCAL_BUILD_LABEL}=local-build")
    return errors


def check_user(name: str, service: dict[str, Any]) -> list[str]:
    user = str(service.get("user") or "").strip()
    if not user:
        return [f"{name}: no user; set a non-root uid:gid"]
    uid = user.split(":", 1)[0]
    if uid in {"0", "root"}:
        return [f"{name}: runs as root ({user})"]
    return []


def check_mounts(name: str, service: dict[str, Any], project_dir: Path) -> list[str]:
    errors = []
    for volume in service.get("volumes") or []:
        kind = volume.get("type")
        source = str(volume.get("source") or "")
        target = str(volume.get("target") or "")
        if "docker.sock" in source or "docker.sock" in target or "docker_engine" in source:
            errors.append(f"{name}: mounts the Docker socket ({source})")
            continue
        if kind in {"volume", "tmpfs"}:
            continue
        if kind == "bind":
            rel = _rel(source, project_dir)
            if rel not in BIND_ALLOWLIST:
                errors.append(f"{name}: host-path mount '{source}' is not in the read-only config allowlist")
            elif not volume.get("read_only"):
                errors.append(f"{name}: config mount '{rel}' must be read_only")
            continue
        errors.append(f"{name}: unsupported mount type '{kind}' for '{source}'")
    return errors


def check_hardening(name: str, service: dict[str, Any], one_shot: bool) -> list[str]:
    errors = []
    if service.get("privileged"):
        errors.append(f"{name}: privileged mode")
    for key in ("network_mode", "pid", "ipc", "userns_mode", "uts", "cgroup"):
        if str(service.get(key) or "") == "host":
            errors.append(f"{name}: {key}=host")
    if service.get("devices"):
        errors.append(f"{name}: maps host devices")
    if service.get("cap_add"):
        errors.append(f"{name}: adds capabilities {service['cap_add']}")
    if "ALL" not in (service.get("cap_drop") or []):
        errors.append(f"{name}: cap_drop must include ALL")
    if not any(str(opt).replace("=", ":") in {"no-new-privileges:true", "no-new-privileges"} for opt in service.get("security_opt") or []):
        errors.append(f"{name}: security_opt must include no-new-privileges:true")
    if any("unconfined" in str(opt) for opt in service.get("security_opt") or []):
        errors.append(f"{name}: disables seccomp or AppArmor")
    if not service.get("read_only"):
        errors.append(f"{name}: root filesystem must be read_only")
    limits = ((service.get("deploy") or {}).get("resources") or {}).get("limits") or {}
    if not limits.get("memory"):
        errors.append(f"{name}: no memory limit")
    if not service.get("restart"):
        errors.append(f"{name}: no restart policy")
    if not one_shot:
        health = service.get("healthcheck") or {}
        if not health.get("test") or health.get("disable"):
            errors.append(f"{name}: no health check")
    return errors


def check_ports(name: str, service: dict[str, Any]) -> list[str]:
    allowed = ALLOWED_PORTS.get(name, set())
    errors = []
    for port in service.get("ports") or []:
        pair = (str(port.get("published", "")), int(port.get("target", 0)))
        if pair not in allowed:
            errors.append(f"{name}: unexpected published port {pair[0]}->{pair[1]}")
    return errors


def check_networks(name: str, service: dict[str, Any], networks: dict[str, Any]) -> list[str]:
    errors = []
    attached = service.get("networks") or {}
    if not attached and not service.get("network_mode"):
        errors.append(f"{name}: no explicit network (would join the default, non-internal network)")
    for network in attached:
        if not (networks.get(network) or {}).get("internal"):
            if network not in OUTBOUND_ALLOWED.get(name, set()):
                errors.append(f"{name}: attached to non-internal network '{network}'")
    return errors


def evaluate(config: dict[str, Any], project_dir: Path = DEMO_DIR, strict_release: bool = False) -> list[str]:
    networks = config.get("networks") or {}
    errors: list[str] = []
    for name, service in sorted((config.get("services") or {}).items()):
        one_shot = bool(set(service.get("profiles") or []) & ONE_SHOT_PROFILES)
        errors += check_hardening(name, service, one_shot)
        errors += check_user(name, service)
        errors += check_mounts(name, service, project_dir)
        errors += check_ports(name, service)
        errors += check_image(name, service, strict_release)
        errors += check_networks(name, service, networks)
    return errors


def resolved_config() -> dict[str, Any]:
    command = ["docker", "compose", "--project-directory", str(DEMO_DIR), "-f", str(DEMO_DIR / "compose.yaml"),
               "--env-file", str(DEMO_DIR / "versions.env"), "--env-file", str(DEMO_DIR / ".env.example")]
    for profile in PROFILES:
        command += ["--profile", profile]
    command += ["config", "--format", "json"]
    return json.loads(subprocess.run(command, check=True, capture_output=True, text=True).stdout)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config-json", type=Path, help="resolved Compose model; default runs docker compose config")
    parser.add_argument("--project-dir", type=Path, default=DEMO_DIR)
    parser.add_argument("--strict-release", action="store_true", help="require registry digests for every image")
    args = parser.parse_args(argv)
    config = json.loads(args.config_json.read_text(encoding="utf-8")) if args.config_json else resolved_config()
    errors = evaluate(config, args.project_dir, args.strict_release)
    services = len(config.get("services") or {})
    if errors:
        print(f"public-demo policy: FAIL ({len(errors)} findings across {services} services)")
        for error in errors:
            print(f"  - {error}")
        return 1
    mode = "strict release" if args.strict_release else "local"
    print(f"public-demo policy: PASS ({services} services, {mode} mode)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
