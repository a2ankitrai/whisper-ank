"""Shared pytest fixtures for the whisper_dictation test suite."""

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def no_real_os_permission_calls():
    """Never let tests touch the real macOS permission APIs.

    Without this, any real `TextTyper()` construction would call the live
    `AXIsProcessTrustedWithOptions` prompt API, which can pop a genuine
    system Accessibility dialog on the machine running the tests.
    """
    with patch(
        "whisper_dictation.text_typer.AXIsProcessTrustedWithOptions",
        return_value=True,
    ), patch(
        "whisper_dictation.text_typer.AXIsProcessTrusted", return_value=True
    ), patch(
        "whisper_dictation.text_typer._carbon"
    ) as mock_carbon:
        mock_carbon.IsSecureEventInputEnabled.return_value = False
        yield
