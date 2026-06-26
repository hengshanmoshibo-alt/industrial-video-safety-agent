import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dev_script_help_lists_core_commands():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "dev.py"), "--help"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "doctor" in result.stdout
    assert "verify" in result.stdout
    assert "seed" in result.stdout
    assert "docs-check" in result.stdout
