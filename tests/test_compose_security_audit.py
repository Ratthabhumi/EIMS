"""Hermetic static Compose audit tests; no Docker daemon or service access."""
import json
import subprocess
import sys
from pathlib import Path

import yaml

from tools.audit_compose_security import audit_compose

ROOT = Path(__file__).resolve().parents[1]
DEV_COMPOSE = ROOT / "docker-compose.yml"
SCANNER = ROOT / "tools" / "audit_compose_security.py"


def test_current_dev_compose_has_explicit_security_findings():
    document = yaml.safe_load(DEV_COMPOSE.read_text(encoding="utf-8"))
    findings = audit_compose(document)
    rules = {item["rule"] for item in findings}
    assert {
        "NON_LOOPBACK_PORT",
        "INLINE_SECRET",
        "IMAGE_UNPINNED",
        "PUBLIC_OBJECT_BUCKET",
        "REDIS_AUTH_UNVERIFIED",
    }.issubset(rules)
    assert any(f["service"] == "minio_setup" and f["rule"] == "PUBLIC_OBJECT_BUCKET" for f in findings)
    assert any(f["service"] == "redis_cache" and f["rule"] == "REDIS_AUTH_UNVERIFIED" for f in findings)


def test_secure_pattern_with_loopback_and_external_secrets_is_not_flagged():
    safe = yaml.safe_load("""
services:
  postgres_db:
    image: pgvector/pgvector:pg16
    ports: ["127.0.0.1:5432:5432"]
    environment:
      POSTGRES_PASSWORD: "${POSTGRES_PASSWORD}"
  redis_cache:
    image: redis:7-alpine
    command: ["redis-server", "--aclfile", "/run/secrets/redis.acl"]
  minio_setup:
    image: minio/mc:RELEASE.2026-01-01T00-00-00Z
    entrypoint: "mc mb eims_local/private-bucket --ignore-existing"
""")
    assert audit_compose(safe) == []


def test_secure_mode_fails_closed_without_leaking_values(tmp_path):
    compose = tmp_path / "unsafe.yml"
    compose.write_text("""
services:
  redis_cache:
    image: redis:latest
    ports: ["6379:6379"]
    environment:
      REDIS_PASSWORD: "do-not-print-this-value"
""", encoding="utf-8")
    cmd = [sys.executable, str(SCANNER), "--compose", str(compose)]
    dev = subprocess.run(cmd + ["--mode", "dev"], capture_output=True, text=True, check=False)
    secure = subprocess.run(cmd + ["--mode", "secure"], capture_output=True, text=True, check=False)
    assert dev.returncode == 0
    assert secure.returncode == 1
    report = json.loads(secure.stdout)
    assert report["finding_count"] >= 3
    assert "do-not-print-this-value" not in secure.stdout
    assert "do-not-print-this-value" not in secure.stderr


def test_host_network_privileged_and_docker_socket_are_high_risk():
    """No published ports are required for host networking or daemon access."""
    compose = yaml.safe_load("""
services:
  unsafe:
    image: busybox:1.36
    network_mode: host
    privileged: true
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
""")
    findings = audit_compose(compose)
    rules = {f["rule"] for f in findings}
    assert {"HOST_NETWORK", "PRIVILEGED_CONTAINER", "DOCKER_SOCKET_MOUNT"}.issubset(rules)
    assert all(f["severity"] == "high" for f in findings)


def test_long_syntax_docker_socket_and_host_pid_are_detected():
    compose = yaml.safe_load("""
services:
  unsafe:
    image: busybox:1.36
    pid: host
    volumes:
      - type: bind
        source: /run/docker.sock
        target: /tmp/engine.sock
        read_only: true
""")
    assert {"HOST_PID", "DOCKER_SOCKET_MOUNT"}.issubset(
        {f["rule"] for f in audit_compose(compose)}
    )


def test_unresolved_include_and_extends_fail_closed_without_echoing_paths(tmp_path):
    marker = "synthetic-secret-filename-not-to-print"
    compose = tmp_path / "indirect.yml"
    compose.write_text(f"""
include:
  - {marker}.yml
services:
  inherited:
    image: busybox:1.36
    extends:
      file: {marker}-base.yml
      service: parent
""", encoding="utf-8")
    findings = audit_compose(yaml.safe_load(compose.read_text(encoding="utf-8")))
    assert {"UNRESOLVED_INCLUDE", "UNRESOLVED_EXTENDS"}.issubset(
        {f["rule"] for f in findings}
    )
    cmd = [sys.executable, str(SCANNER), "--compose", str(compose), "--mode", "secure"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert result.returncode == 1
    assert marker not in result.stdout
    assert marker not in result.stderr


def test_ordinary_named_volume_and_bridge_network_are_not_false_positives():
    safe = yaml.safe_load("""
services:
  ordinary:
    image: busybox:1.36
    network_mode: bridge
    privileged: false
    volumes:
      - app_data:/var/lib/app
      - ./config:/etc/app:ro
      - type: volume
        source: app_cache
        target: /cache
volumes:
  app_data: {}
  app_cache: {}
""")
    assert audit_compose(safe) == []


def test_host_userns_ipc_and_device_access_are_high_risk():
    """Host IPC/user namespaces and device pass-through bypass ordinary isolation."""
    compose = yaml.safe_load("""
services:
  unsafe:
    image: busybox:1.36
    userns_mode: host
    ipc: host
    devices:
      - /dev/null:/dev/example
    device_cgroup_rules:
      - "c 1:3 rwm"
""")
    findings = audit_compose(compose)
    assert {"HOST_USER_NAMESPACE", "HOST_IPC", "HOST_DEVICE_ACCESS"}.issubset(
        {f["rule"] for f in findings}
    )
    assert all(f["severity"] == "high" for f in findings)
    assert "/dev/example" not in json.dumps(findings)


def test_capability_and_unconfined_security_options_fail_secure_mode(tmp_path):
    """No Docker daemon; synthetic profile must not pass the secure static gate."""
    compose = tmp_path / "synthetic.yml"
    compose.write_text("""
services:
  unsafe:
    image: busybox:1.36
    cap_add: [SYS_ADMIN]
    security_opt:
      - "seccomp:unconfined"
      - "apparmor:unconfined"
""", encoding="utf-8")
    findings = audit_compose(yaml.safe_load(compose.read_text(encoding="utf-8")))
    assert {"ADDED_LINUX_CAPABILITIES", "DISABLED_SECURITY_PROFILE"}.issubset(
        {f["rule"] for f in findings}
    )
    result = subprocess.run(
        [sys.executable, str(SCANNER), "--compose", str(compose), "--mode", "secure"],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 1
    assert "SYS_ADMIN" not in result.stdout
    assert "seccomp:unconfined" not in result.stdout


def test_indirect_namespace_references_are_not_silently_certified():
    """A service/container namespace reference is not equivalent to bridge isolation."""
    compose = yaml.safe_load("""
services:
  parent:
    image: busybox:1.36
  child:
    image: busybox:1.36
    network_mode: "service:parent"
    pid: "container:synthetic-other"
""")
    findings = audit_compose(compose)
    assert {"INDIRECT_NETWORK_NAMESPACE", "INDIRECT_PID_NAMESPACE"}.issubset(
        {f["rule"] for f in findings}
    )
    assert not any(f["service"] == "parent" for f in findings)


def test_normal_namespace_and_confinement_settings_remain_unflagged():
    compose = yaml.safe_load("""
services:
  ordinary:
    image: busybox:1.36
    network_mode: bridge
    ipc: private
    userns_mode: private
    cap_drop: [ALL]
    security_opt:
      - "no-new-privileges:true"
""")
    assert audit_compose(compose) == []
