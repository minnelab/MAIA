"""Unit tests for additional MAIA/maia_fn.py utility functions."""
from __future__ import annotations

import json
from unittest.mock import mock_open, patch

import pytest

from MAIA.maia_fn import edit_orthanc_configuration


@pytest.mark.unit
class TestOrthancConfiguration:
    """Test Orthanc configuration editing function."""

    def test_edit_orthanc_configuration_basic(self):
        """Test editing Orthanc configuration with basic values."""
        mock_config = {"Name": "Orthanc", "HttpPort": 8042, "DicomPort": 4242}

        with patch("builtins.open", mock_open(read_data=json.dumps(mock_config))):
            edit_dict = {"HttpPort": 9000, "DicomPort": 5000}
            result = edit_orthanc_configuration("/tmp/config.json", edit_dict)

        assert result["HttpPort"] == 9000
        assert result["DicomPort"] == 5000
        assert result["Name"] == "Orthanc"  # Unchanged value should remain

    def test_edit_orthanc_configuration_add_new_keys(self):
        """Test adding new keys to Orthanc configuration."""
        mock_config = {"Name": "Orthanc", "HttpPort": 8042}

        with patch("builtins.open", mock_open(read_data=json.dumps(mock_config))):
            edit_dict = {"NewKey": "NewValue", "AnotherKey": 123}
            result = edit_orthanc_configuration("/tmp/config.json", edit_dict)

        assert result["NewKey"] == "NewValue"
        assert result["AnotherKey"] == 123
        assert result["Name"] == "Orthanc"

    def test_edit_orthanc_configuration_complex_nested(self):
        """Test editing Orthanc configuration with nested values."""
        mock_config = {"Name": "Orthanc", "DicomModalities": {"PACS": ["PACS", "localhost", 104]}}

        with patch("builtins.open", mock_open(read_data=json.dumps(mock_config))):
            edit_dict = {"DicomModalities": {"NewPACS": ["NewPACS", "remote.host", 105]}}
            result = edit_orthanc_configuration("/tmp/config.json", edit_dict)

        assert result["DicomModalities"] == {"NewPACS": ["NewPACS", "remote.host", 105]}

    def test_edit_orthanc_configuration_empty_edit_dict(self):
        """Test editing Orthanc configuration with empty edit dictionary."""
        mock_config = {"Name": "Orthanc", "HttpPort": 8042}

        with patch("builtins.open", mock_open(read_data=json.dumps(mock_config))):
            result = edit_orthanc_configuration("/tmp/config.json", {})

        assert result == mock_config  # Should return unchanged

    def test_edit_orthanc_configuration_overwrite_all(self):
        """Test completely overwriting Orthanc configuration values."""
        mock_config = {"Key1": "Value1", "Key2": "Value2", "Key3": "Value3"}

        with patch("builtins.open", mock_open(read_data=json.dumps(mock_config))):
            edit_dict = {"Key1": "NewValue1", "Key2": "NewValue2", "Key3": "NewValue3"}
            result = edit_orthanc_configuration("/tmp/config.json", edit_dict)

        assert result["Key1"] == "NewValue1"
        assert result["Key2"] == "NewValue2"
        assert result["Key3"] == "NewValue3"
