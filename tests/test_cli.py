"""
Tests for CLI module.

This module contains tests for the command-line interface,
ensuring proper command handling and output formatting.
"""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vprism.cli import app
from vprism.core.exceptions import VPrismException
from vprism.core.models import AssetType, MarketType, TimeFrame


class TestCLI:
    """Test CLI commands."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_version_command(self):
        """Test version command."""
        result = self.runner.invoke(app, ["version"])

        assert result.exit_code == 0
        assert "vprism version:" in result.stdout

    def test_get_command_basic(self):
        """Test basic get command."""
        with patch("vprism.cli.VPrismClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.get_sync.side_effect = VPrismException(
                "Not implemented", "NOT_IMPLEMENTED"
            )

            result = self.runner.invoke(app, ["get", "stock"])

            assert result.exit_code == 1
            assert "Error: Not implemented" in result.stdout
            mock_client.get_sync.assert_called_once()

    def test_get_command_with_options(self):
        """Test get command with various options."""
        with patch("vprism.cli.VPrismClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.get_sync.side_effect = VPrismException(
                "Not implemented", "NOT_IMPLEMENTED"
            )

            result = self.runner.invoke(
                app,
                [
                    "get",
                    "stock",
                    "--market",
                    "us",
                    "--symbols",
                    "AAPL,GOOGL",
                    "--provider",
                    "test_provider",
                    "--timeframe",
                    "1d",
                    "--start",
                    "2024-01-01",
                    "--end",
                    "2024-01-31",
                    "--limit",
                    "100",
                    "--format",
                    "json",
                ],
            )

            assert result.exit_code == 1
            mock_client.get_sync.assert_called_once_with(
                asset=AssetType.STOCK,
                market=MarketType.US,
                symbols=["AAPL", "GOOGL"],
                provider="test_provider",
                timeframe=TimeFrame.DAY_1,
                start="2024-01-01",
                end="2024-01-31",
                limit=100,
            )

    def test_get_command_invalid_format(self):
        """Test get command with invalid output format."""
        with patch("vprism.cli.VPrismClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_response = MagicMock()
            mock_client.get_sync.return_value = mock_response

            result = self.runner.invoke(app, ["get", "stock", "--format", "invalid"])

            assert result.exit_code == 1
            assert "Unsupported format: invalid" in result.stdout

    def test_get_command_json_format(self):
        """Test get command with JSON output format."""
        with patch("vprism.cli.VPrismClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_response = MagicMock()
            mock_response.model_dump_json.return_value = '{"test": "data"}'
            mock_client.get_sync.return_value = mock_response

            self.runner.invoke(app, ["get", "stock", "--format", "json"])

            # Should not raise an error for JSON format
            mock_client.get_sync.assert_called_once()

    def test_get_command_csv_format(self):
        """Test get command with CSV output format."""
        with patch("vprism.cli.VPrismClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_response = MagicMock()
            mock_client.get_sync.return_value = mock_response

            result = self.runner.invoke(app, ["get", "stock", "--format", "csv"])

            # Should not raise an error for CSV format
            assert result.exit_code == 0
            mock_client.get_sync.assert_called_once()
            # Check that CSV output is in the result
            assert "symbol,timestamp,open,high,low,close,volume" in result.stdout

    def test_get_command_unsupported_format(self):
        """Test get command with unsupported output format."""
        with patch("vprism.cli.VPrismClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_response = MagicMock()
            mock_client.get_sync.return_value = mock_response

            result = self.runner.invoke(app, ["get", "stock", "--format", "xml"])

            # Should exit with error code 1 for unsupported format
            assert result.exit_code == 1
            assert "Unsupported format: xml" in result.stdout

    def test_get_command_with_exception_details(self):
        """Test get command with exception that has details."""
        with patch("vprism.cli.VPrismClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            exception = VPrismException(
                "Test error", "TEST_ERROR", details={"key": "value"}
            )
            mock_client.get_sync.side_effect = exception

            result = self.runner.invoke(app, ["get", "stock"])

            assert result.exit_code == 1
            assert "Error: Test error" in result.stdout
            assert "Details:" in result.stdout

    def test_stream_command_basic(self):
        """Test basic stream command."""
        with patch("vprism.cli.VPrismClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.stream.side_effect = VPrismException(
                "Not implemented", "NOT_IMPLEMENTED"
            )

            result = self.runner.invoke(app, ["stream", "stock"])

            assert result.exit_code == 1
            assert "Error: Not implemented" in result.stdout

    def test_stream_command_with_options(self):
        """Test stream command with options."""
        with patch("vprism.cli.VPrismClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.stream.side_effect = VPrismException(
                "Not implemented", "NOT_IMPLEMENTED"
            )

            result = self.runner.invoke(
                app,
                [
                    "stream",
                    "stock",
                    "--market",
                    "us",
                    "--symbols",
                    "AAPL,GOOGL",
                    "--provider",
                    "test_provider",
                ],
            )

            assert result.exit_code == 1

    def test_stream_command_keyboard_interrupt(self):
        """Test stream command handles keyboard interrupt."""
        with patch("vprism.cli.VPrismClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.stream.side_effect = KeyboardInterrupt()

            result = self.runner.invoke(app, ["stream", "stock"])

            assert result.exit_code == 0
            assert "Stream stopped by user" in result.stdout

    def test_config_command_show(self):
        """Test config command with show option."""
        result = self.runner.invoke(app, ["config", "--show"])

        assert result.exit_code == 0
        assert "Current configuration:" in result.stdout
        assert "Configuration management not yet implemented" in result.stdout

    def test_config_command_set(self):
        """Test config command with set option."""
        result = self.runner.invoke(app, ["config", "--set", "key=value"])

        assert result.exit_code == 0
        assert "Setting configuration: key=value" in result.stdout
        assert "Configuration management not yet implemented" in result.stdout

    def test_config_command_no_options(self):
        """Test config command without options."""
        result = self.runner.invoke(app, ["config"])

        assert result.exit_code == 0
        assert "Use --show to view or --set key=value to configure" in result.stdout

    def test_health_command(self):
        """Test health command."""
        result = self.runner.invoke(app, ["health"])

        assert result.exit_code == 0
        assert "Checking system health..." in result.stdout
        assert "Health check not yet implemented" in result.stdout

    def test_get_command_unexpected_error(self):
        """Test get command handles unexpected errors."""
        with patch("vprism.cli.VPrismClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.get_sync.side_effect = RuntimeError("Unexpected error")

            result = self.runner.invoke(app, ["get", "stock"])

            assert result.exit_code == 1
            assert "Unexpected error: Unexpected error" in result.stdout

    def test_stream_command_unexpected_error(self):
        """Test stream command handles unexpected errors."""
        with patch("vprism.cli.VPrismClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.stream.side_effect = RuntimeError("Unexpected error")

            result = self.runner.invoke(app, ["stream", "stock"])

            assert result.exit_code == 1
            assert "Unexpected error: Unexpected error" in result.stdout

    def test_stream_command_keyboard_interrupt_coverage(self):
        """Test stream command keyboard interrupt to ensure coverage."""
        with (
            patch("vprism.cli.VPrismClient") as mock_client_class,
            patch("asyncio.run") as mock_run,
        ):
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_run.side_effect = KeyboardInterrupt()

            result = self.runner.invoke(app, ["stream", "stock"])

            assert result.exit_code == 0
            assert "Stream stopped by user" in result.stdout

    def test_stream_command_vprism_exception_with_details(self):
        """Test stream command with VPrismException that has details."""
        with (
            patch("vprism.cli.VPrismClient") as mock_client_class,
            patch("asyncio.run") as mock_run,
        ):
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            # Create exception with details
            exception = VPrismException(
                message="Provider error",
                error_code="PROVIDER_ERROR",
                details={"provider": "test_provider", "status": "failed"},
            )
            mock_run.side_effect = exception

            result = self.runner.invoke(app, ["stream", "stock"])

            assert result.exit_code == 1
            assert "Error: Provider error" in result.stdout
            assert "Details:" in result.stdout

    def test_stream_command_with_data_display(self):
        """Test that _display_stream_data function gets called for coverage."""
        # This test ensures the _display_stream_data function is covered
        from vprism.cli import _display_stream_data

        # Call the function directly to ensure coverage
        test_data = {"symbol": "AAPL", "price": 150.0}
        _display_stream_data(test_data)

        # The function should execute without error
        # (it just prints to console, so we can't easily assert the output)


class TestCLIHelpers:
    """Test CLI helper functions."""

    def test_display_table(self):
        """Test _display_table function."""
        from vprism.cli import _display_table

        # Should not raise any exceptions
        _display_table(None)

    def test_display_csv(self):
        """Test _display_csv function."""
        from vprism.cli import _display_csv

        # Should not raise any exceptions
        _display_csv(None)

    def test_display_stream_data(self):
        """Test _display_stream_data function."""
        from vprism.cli import _display_stream_data

        # Should not raise any exceptions
        _display_stream_data("test_data")


class TestCLIIntegration:
    """Integration tests for CLI."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_cli_app_exists(self):
        """Test that CLI app is properly configured."""
        assert app is not None
        assert app.info.name == "vprism"

    def test_help_command(self):
        """Test help command."""
        result = self.runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "vprism - Modern Financial Data Infrastructure Platform" in result.stdout
        assert "get" in result.stdout
        assert "stream" in result.stdout
        assert "config" in result.stdout
        assert "health" in result.stdout
        assert "version" in result.stdout

    def test_command_help(self):
        """Test individual command help."""
        commands = ["get", "stream", "config", "health", "version"]

        for command in commands:
            result = self.runner.invoke(app, [command, "--help"])
            assert result.exit_code == 0
            assert command in result.stdout.lower()

    def test_invalid_command(self):
        """Test invalid command handling."""
        result = self.runner.invoke(app, ["invalid_command"])

        assert result.exit_code != 0

    def test_asset_type_validation(self):
        """Test asset type validation in commands."""
        result = self.runner.invoke(app, ["get", "invalid_asset"])

        assert result.exit_code != 0

    def test_market_type_validation(self):
        """Test market type validation in commands."""
        with patch("vprism.cli.VPrismClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.get_sync.side_effect = VPrismException(
                "Not implemented", "NOT_IMPLEMENTED"
            )

            result = self.runner.invoke(
                app, ["get", "stock", "--market", "invalid_market"]
            )

            assert result.exit_code != 0

    def test_timeframe_validation(self):
        """Test timeframe validation in commands."""
        with patch("vprism.cli.VPrismClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.get_sync.side_effect = VPrismException(
                "Not implemented", "NOT_IMPLEMENTED"
            )

            result = self.runner.invoke(
                app, ["get", "stock", "--timeframe", "invalid_timeframe"]
            )

            assert result.exit_code != 0
