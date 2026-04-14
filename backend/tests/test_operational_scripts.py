from __future__ import annotations

import gzip
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKUP_SCRIPT = REPO_ROOT / "scripts" / "backup.sh"


def test_backup_export_is_not_polluted_by_trace_logs(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir(parents=True, exist_ok=True)
    fake_docker = fake_bin / "docker"
    fake_docker.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                "cat <<'SQL'",
                "-- PostgreSQL database dump",
                "CREATE TABLE projects (id int);",
                "SQL",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)
    fake_zfs = fake_bin / "zfs"
    fake_zfs.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    fake_zfs.chmod(0o755)

    backup_root = tmp_path / "backups"
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["DATUM_BACKUPS_ROOT"] = str(backup_root)

    result = subprocess.run(
        ["bash", str(BACKUP_SCRIPT)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    dumps = sorted((backup_root / "pgdump").glob("operational-*.sql.gz"))
    assert len(dumps) == 1
    dump_content = gzip.decompress(dumps[0].read_bytes()).decode("utf-8")
    assert dump_content.startswith("-- PostgreSQL database dump")
    assert "+ docker compose" not in dump_content
