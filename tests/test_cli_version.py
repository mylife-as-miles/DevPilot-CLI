from typer.testing import CliRunner

from devpilot.cli.app import app


def test_version_reports_the_installed_distribution_version() -> None:
    result = CliRunner().invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.startswith("devpilot ")
    assert "unknown" not in result.stdout.lower()
