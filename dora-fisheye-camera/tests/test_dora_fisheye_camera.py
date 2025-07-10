"""Test module for dora_fisheye_camera package."""

import pytest


def test_import_main() -> None:
    """Test importing and running the main function."""
    from dora_fisheye_camera.main import main

    # Check that everything is working, and catch Dora RuntimeError
    # as we're not running in a Dora dataflow.
    with pytest.raises(RuntimeError):
        main()
