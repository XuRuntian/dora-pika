"""Test module for dora_pyaudio package."""

import pytest


def test_import_main() -> None:
    """Test importing and running the main function."""
    from dora_pyaudio.main import main

    # Check that everything is working, and catch Dora RuntimeError
    # as we're not running in a Dora dataflow.
    with pytest.raises(RuntimeError):
        main()
