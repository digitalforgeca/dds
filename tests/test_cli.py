"""Tests for dds.cli module."""

from click.testing import CliRunner

from dds.cli import main


class TestCLI:
    """Tests for the CLI commands."""

    def test_version(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "Daedalus Deployment System" in result.output

    def test_deploy_no_config(self, tmp_path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["-c", str(tmp_path / "nope.yaml"), "deploy", "dev"])
        assert result.exit_code != 0
        assert "No dds.yaml found" in result.output

    def test_deploy_unknown_env(self, tmp_path) -> None:
        import yaml

        cfg_file = tmp_path / "dds.yaml"
        cfg_file.write_text(yaml.dump({
            "project": "test",
            "environments": {"dev": {"services": {}}},
        }))
        runner = CliRunner()
        result = runner.invoke(main, ["-c", str(cfg_file), "deploy", "staging"])
        assert result.exit_code != 0
        assert "Unknown environment" in result.output

    def test_init_creates_file(self, tmp_path) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(main, ["init"])
            assert result.exit_code == 0
            assert "Created dds.yaml" in result.output

    def test_init_existing_file(self, tmp_path) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            # Create existing file
            with open("dds.yaml", "w") as f:
                f.write("exists")
            result = runner.invoke(main, ["init"])
            assert result.exit_code != 0
            assert "already exists" in result.output

    def test_all_commands_registered(self) -> None:
        """Ensure all expected commands are registered."""
        expected = {"deploy", "status", "preflight", "rollback", "revisions", "logs", "health", "init"}
        actual = set(main.commands.keys())
        assert expected == actual, f"Missing: {expected - actual}, Extra: {actual - expected}"

    def test_dry_run(self, tmp_path) -> None:
        import yaml

        cfg_file = tmp_path / "dds.yaml"
        cfg_file.write_text(yaml.dump({
            "project": "test",
            "registry": "test.azurecr.io",
            "environments": {
                "dev": {
                    "resource_group": "test-rg",
                    "services": {
                        "api": {"type": "container-app", "name": "dev-api"},
                    },
                }
            },
        }))
        runner = CliRunner()
        result = runner.invoke(main, ["-c", str(cfg_file), "deploy", "dev", "--dry-run"])
        assert result.exit_code == 0
        assert "DRY RUN" in result.output
        assert "api" in result.output
