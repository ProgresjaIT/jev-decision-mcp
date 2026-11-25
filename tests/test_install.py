import os
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize("existing", [None, "TYPESAFE_API_KEY=test-provider-key\n", "TYPESAFE_API_KEY=test-provider-key\nMCP_TOKEN=\n"])
def test_install_idempotent_and_secret_permissions(tmp_path, existing):
    root = Path(__file__).parents[1]
    for name in ("install.sh", ".env.example"):
        shutil.copy2(root / name, tmp_path / name)
    commands = tmp_path / "bin"
    commands.mkdir()
    docker = commands / "docker"
    docker.write_text("#!/bin/sh\nexit 0\n")
    docker.chmod(0o755)
    env = {**os.environ, "PATH": str(commands) + ":" + os.environ["PATH"]}
    if existing is not None:
        (tmp_path / ".env").write_text(existing)
    subprocess.run(
        ["bash", "install.sh"], cwd=tmp_path, env=env, check=True, capture_output=True
    )
    content = (tmp_path / ".env").read_bytes()
    values = dict(line.split("=", 1) for line in content.decode().splitlines() if "=" in line and not line.startswith("#"))
    assert len(values["MCP_TOKEN"]) >= 32
    assert values["HOST"] == "0.0.0.0"
    assert values["DB_PATH"] == "/data/history.sqlite3"
    if existing is not None:
        assert values["TYPESAFE_API_KEY"] == "test-provider-key"
    assert b"MCP_TOKEN=\n" not in content
    assert (tmp_path / ".env").stat().st_mode & 0o777 == 0o600
    subprocess.run(
        ["bash", "install.sh"], cwd=tmp_path, env=env, check=True, capture_output=True
    )
    assert (tmp_path / ".env").read_bytes() == content


def test_invalid_startup_does_not_print_secrets(tmp_path):
    import sys

    root = Path(__file__).parents[1]
    secret = "private-provider-value-do-not-log"
    env = {
        **os.environ,
        "PYTHONPATH": str(root / "src"),
        "TYPESAFE_API_KEY": secret,
        "MCP_TOKEN": "short",
    }
    result = subprocess.run(
        [sys.executable, "-m", "jev_decision.server", "--check-config"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert secret not in result.stdout + result.stderr
    assert "Traceback" not in result.stderr
