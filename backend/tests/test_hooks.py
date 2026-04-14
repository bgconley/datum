import json
import os
import stat
import subprocess

HOOKS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "hooks", "claude"
)


def test_hook_scripts_exist():
    expected = [
        "session-start.sh",
        "pre-tool-use.sh",
        "post-tool-use.sh",
        "pre-compact.sh",
        "stop.sh",
        "session-end.sh",
        "install-hooks.sh",
        "README.md",
    ]
    for script in expected:
        path = os.path.join(HOOKS_DIR, script)
        assert os.path.exists(path), f"Missing hook asset: {script}"


def test_hook_scripts_executable():
    for script in os.listdir(HOOKS_DIR):
        if not script.endswith(".sh"):
            continue
        path = os.path.join(HOOKS_DIR, script)
        mode = os.stat(path).st_mode
        assert mode & stat.S_IXUSR, f"{script} is not executable"


def test_install_script_outputs_json():
    result = subprocess.run(
        ["bash", os.path.join(HOOKS_DIR, "install-hooks.sh")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    config = json.loads(result.stdout)
    assert "hooks" in config
    assert "SessionStart" in config["hooks"]
    assert "PreToolUse" in config["hooks"]
    assert "Stop" in config["hooks"]
