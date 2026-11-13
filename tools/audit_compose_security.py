"""Read-only Docker Compose security inventory; no Docker daemon required.

Development Compose findings are reported but do not fail CI. A future
secure profile can be gated with --mode secure. Never echo secret values.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml


SECRET_KEY = re.compile(r"(?:PASSWORD|SECRET|TOKEN|API_KEY|AUTH_PASS)", re.I)
INLINE_DB_CREDENTIAL = re.compile(r"://[^:/\s]+:[^@/\s]+@")
LOOPBACK = {"127.0.0.1", "::1", "localhost"}
DOCKER_DAEMON_SOCKETS = {"/var/run/docker.sock", "/run/docker.sock"}


def _mounts_docker_socket(volume: Any) -> bool:
    """Inspect the source only; never include mount strings in findings."""
    if isinstance(volume, dict):
        return (
            str(volume.get("type", "bind")) == "bind"
            and str(volume.get("source", "")) in DOCKER_DAEMON_SOCKETS
        )
    if isinstance(volume, str):
        return volume.split(":", 1)[0] in DOCKER_DAEMON_SOCKETS
    return False



def _environment(service: dict[str, Any]) -> dict[str, str]:
    env = service.get("environment") or {}
    if isinstance(env, dict):
        return {str(key): str(value) for key, value in env.items() if value is not None}
    if isinstance(env, list):
        result = {}
        for entry in env:
            key, separator, value = str(entry).partition("=")
            if separator:
                result[key] = value
        return result
    return {}


def _published_to_nonloopback(port: Any) -> bool:
    if isinstance(port, dict):
        return str(port.get("host_ip", "")).strip("[]") not in LOOPBACK
    # Compose short syntax: [HOST_IP:]HOST_PORT:CONTAINER_PORT[/protocol]
    segments = str(port).split("/")[0].rsplit(":", 2)
    if len(segments) < 3:
        return True
    return segments[0].strip("[]") not in LOOPBACK


def audit_compose(document: dict[str, Any]) -> list[dict[str, str]]:
    if not isinstance(document, dict) or not isinstance(document.get("services"), dict):
        raise ValueError("Compose document must contain a services mapping")

    findings: list[dict[str, str]] = []

    def add(service: str, rule: str, severity: str, detail: str) -> None:
        findings.append({
            "service": service, "rule": rule,
            "severity": severity, "detail": detail,
        })

    # This scanner does not resolve Compose includes or inherited service files.
    # Fail closed rather than certifying only the visible fragment as secure.
    if document.get("include"):
        add("<compose>", "UNRESOLVED_INCLUDE", "high",
            "External Compose includes are not resolved by this static audit")

    for name, service in sorted(document["services"].items()):
        if not isinstance(service, dict):
            continue
        if service.get("extends"):
            add(name, "UNRESOLVED_EXTENDS", "high",
                "Inherited Compose service configuration is not resolved")
        if str(service.get("network_mode", "")).strip().lower() == "host":
            add(name, "HOST_NETWORK", "high",
                "Service shares the host network namespace even without ports")
        if service.get("privileged") is True:
            add(name, "PRIVILEGED_CONTAINER", "high",
                "Container requests unrestricted privileged mode")
        pid_mode = str(service.get("pid", "")).strip().lower()
        if pid_mode == "host":
            add(name, "HOST_PID", "high",
                "Service shares the host PID namespace")
        if pid_mode.startswith(("service:", "container:")):
            add(name, "INDIRECT_PID_NAMESPACE", "high",
                "Inherited PID namespace requires a resolved trust-boundary review")
        network_mode = str(service.get("network_mode", "")).strip().lower()
        if network_mode.startswith(("service:", "container:")):
            add(name, "INDIRECT_NETWORK_NAMESPACE", "high",
                "Shared network namespace requires a resolved trust-boundary review")
        if str(service.get("userns_mode", "")).strip().lower() == "host":
            add(name, "HOST_USER_NAMESPACE", "high",
                "Service disables user-namespace isolation from the host")
        if str(service.get("ipc", "")).strip().lower() == "host":
            add(name, "HOST_IPC", "high",
                "Service shares the host IPC namespace")
        capabilities = service.get("cap_add") or []
        if isinstance(capabilities, str):
            capabilities = [capabilities]
        if capabilities:
            add(name, "ADDED_LINUX_CAPABILITIES", "high",
                "Service requests additional Linux capabilities; review required")
        security_options = service.get("security_opt") or []
        if isinstance(security_options, str):
            security_options = [security_options]
        if any(re.fullmatch(r"(?:seccomp|apparmor)[:=]unconfined|label[:=]disable",
                            str(option).strip().lower()) for option in security_options):
            add(name, "DISABLED_SECURITY_PROFILE", "high",
                "Service disables a container confinement policy")
        if service.get("devices") or service.get("device_cgroup_rules"):
            add(name, "HOST_DEVICE_ACCESS", "high",
                "Service requests host device access; manual review required")
        if any(_mounts_docker_socket(v) for v in (service.get("volumes") or [])):
            add(name, "DOCKER_SOCKET_MOUNT", "high",
                "Service mounts the Docker daemon control socket")
        image = str(service.get("image") or "")
        if image and "@sha256:" not in image and (
            image.endswith(":latest") or (":" not in image.rsplit("/", 1)[-1])
        ):
            add(name, "IMAGE_UNPINNED", "medium", "Image uses latest or an implicit tag")

        for port in service.get("ports") or []:
            if _published_to_nonloopback(port):
                add(name, "NON_LOOPBACK_PORT", "high",
                    "Port is published without an explicit loopback host binding")

        env = _environment(service)
        for key, value in sorted(env.items()):
            if key.endswith("_FILE"):
                continue
            if SECRET_KEY.search(key) and value and "${" not in value and not value.startswith("$"):
                add(name, "INLINE_SECRET", "high",
                    f"Credential-like variable {key} has a literal value")
            if INLINE_DB_CREDENTIAL.search(value) and "${" not in value:
                add(name, "INLINE_URL_CREDENTIAL", "high",
                    f"Variable {key} contains an inline URL credential")

        command = service.get("command") or ""
        command_text = " ".join(map(str, command)) if isinstance(command, list) else str(command)
        if name.startswith("redis") or image.startswith("redis:"):
            if "--aclfile" not in command_text and "--requirepass" not in command_text:
                add(name, "REDIS_AUTH_UNVERIFIED", "high",
                    "No Redis ACL file or requirepass is visible in service command")

        entrypoint = service.get("entrypoint") or ""
        entrypoint_text = " ".join(map(str, entrypoint)) if isinstance(entrypoint, list) else str(entrypoint)
        if re.search(r"\bmc\s+anonymous\s+set\s+public\b", entrypoint_text, re.I):
            add(name, "PUBLIC_OBJECT_BUCKET", "high",
                "MinIO setup grants anonymous public bucket access")

        if env.get("AUTH_TYPE", "").lower() == "plain":
            add(name, "PGBOUNCER_PLAIN_AUTH", "medium",
                "PgBouncer uses plain authentication; review transport and policy")

    return sorted(findings, key=lambda f: (f["service"], f["rule"], f["detail"]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compose", default="docker-compose.yml")
    parser.add_argument("--mode", choices=("dev", "secure"), default="dev")
    parser.add_argument("--output", help="Optional JSON report path")
    args = parser.parse_args()

    document = yaml.safe_load(Path(args.compose).read_text(encoding="utf-8"))
    findings = audit_compose(document)
    report = {
        "mode": args.mode,
        "compose": args.compose,
        "finding_count": len(findings),
        "findings": findings,
        "note": "Static source review only; no claim of deployed exposure.",
    }
    serialized = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 1 if args.mode == "secure" and any(f["severity"] == "high" for f in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
