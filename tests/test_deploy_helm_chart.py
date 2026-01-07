"""Unit tests for MAIA_scripts/MAIA_deploy_helm_chart.py."""
from __future__ import annotations

import pytest

from MAIA_scripts.MAIA_deploy_helm_chart import str2bool


@pytest.mark.unit
class TestStr2Bool:
    """Test string to boolean conversion function."""

    def test_str2bool_true_values(self):
        """Test that various true strings are converted correctly."""
        true_values = ["yes", "true", "t", "y", "1", "YES", "TRUE", "True"]
        for value in true_values:
            assert str2bool(value) is True

    def test_str2bool_false_values(self):
        """Test that various false strings are converted correctly."""
        false_values = ["no", "false", "f", "n", "0", "NO", "FALSE", "False"]
        for value in false_values:
            assert str2bool(value) is False

    def test_str2bool_invalid_value(self):
        """Test that invalid values raise an error."""
        with pytest.raises(Exception):
            str2bool("invalid")

    def test_str2bool_empty_string(self):
        """Test that empty string raises an error."""
        with pytest.raises(Exception):
            str2bool("")

    def test_str2bool_boolean_input(self):
        """Test that boolean input is handled correctly."""
        assert str2bool(True) is True
        assert str2bool(False) is False
