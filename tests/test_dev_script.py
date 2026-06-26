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
    assert "workflow-check" in result.stdout
    assert "prompt-check" in result.stdout
    assert "benchmark-report" in result.stdout


def test_workflow_spec_check_passes():
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_workflow_spec.py")],
        check=True,
        capture_output=True,
        text=True,
    )


def test_prompt_contract_check_passes():
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_prompt_contract.py")],
        check=True,
        capture_output=True,
        text=True,
    )


def test_benchmark_report_generator_help_runs():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "generate_benchmark_report.py"), "--help"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Generate benchmark report" in result.stdout
