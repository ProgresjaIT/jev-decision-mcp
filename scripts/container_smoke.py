"""Temporary container smoke test; no external calls, no production deployment."""

import os
import subprocess
import sys
import time

from jev_decision.probe import main

os.environ["MCP_TOKEN"] = "temporary-container-test-" + "x" * 32
os.environ["TYPESAFE_API_KEY"] = "synthetic-not-used"
os.environ["DB_PATH"] = "/tmp/smoke.sqlite3"
os.environ["HOST"] = "127.0.0.1"
assert os.getuid() != 0
process = subprocess.Popen([sys.executable, "-m", "jev_decision.server"])
try:
    # Startup readiness via the actual MCP protocol, bounded attempts.
    for _ in range(15):
        if process.poll() is not None:
            raise RuntimeError("server exited")
        time.sleep(0.2)
        if main() == 0:
            print("NONROOT_CONTAINER_MCP_SMOKE_PASS")
            break
    else:
        raise RuntimeError("server failed readiness")
finally:
    process.terminate()
    process.wait(timeout=10)
