"""TODO: Add docstring."""

import pytest


def test_import_main() -> None:
    """TODO: Add docstring."""
    from dora_pyrealsense.main import main

    # Check that everything is working, and catch dora Runtime Exception as we're not running in a dora dataflow.
    with pytest.raises(ConnectionError):
        main()
