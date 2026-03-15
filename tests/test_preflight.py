"""Tests for dds.preflight module."""

from dds.preflight import CheckResult, check_command, run_preflight


class TestCheckCommand:
    """Tests for check_command()."""

    def test_existing_command(self) -> None:
        """Python should always be available in the test env."""
        result = check_command("Python", "python3")
        assert result.passed is True
        assert result.name == "Python"

    def test_missing_command(self) -> None:
        result = check_command("Fake", "nonexistent_binary_xyz_123")
        assert result.passed is False
        assert "not found" in result.message


class TestRunPreflight:
    """Tests for run_preflight()."""

    def test_returns_list(self) -> None:
        results = run_preflight()
        assert isinstance(results, list)
        assert all(isinstance(r, CheckResult) for r in results)
        # Should at least check git
        names = [r.name for r in results]
        assert "Git" in names
