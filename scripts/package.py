"""Build a deployment archive from an explicit allowlist; never include runtime data."""

import hashlib
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
out = root / "dist"
out.mkdir(exist_ok=True)
files = [
    root / name
    for name in (
        "pyproject.toml",
        "requirements.lock",
        "Dockerfile",
        "docker-compose.yml",
        ".env.example",
        ".gitignore",
        ".dockerignore",
        "README.md",
        "INSTALL.md",
        "install.sh",
        "start.sh",
        "stop.sh",
        "update.sh",
        "healthcheck.sh",
    )
]
for directory in ("src", "tests", "examples", "docs", "scripts"):
    files.extend(
        p
        for p in (root / directory).rglob("*")
        if p.is_file() and p.suffix in (".py", ".md", ".json")
    )
archive = out / "jev-decision-mcp.zip"
with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as z:
    for path in sorted(files):
        if path.is_symlink():
            raise RuntimeError("Symlink in package inputs")
        z.write(path, root.name + "/" + str(path.relative_to(root)))
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert all("/.env" not in n or n.endswith("/.env.example") for n in z.namelist())
    assert all(
        not any(x in n for x in (".venv/", "__pycache__/", ".sqlite", ".git/"))
        for n in z.namelist()
    )
digest = hashlib.sha256(archive.read_bytes()).hexdigest()
(archive.with_suffix(".zip.sha256")).write_text(f"{digest}  {archive.name}\n")
print(f"{archive}: {len(files)} files, {archive.stat().st_size} bytes, SHA256 {digest}")
