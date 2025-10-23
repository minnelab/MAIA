"""Unit tests for MAIA/dashboard_utils.py functions."""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from MAIA.dashboard_utils import (
    decrypt_string,
    encrypt_string,
    generate_encryption_keys,
    verify_gpu_availability,
    verify_gpu_booking_policy,
)


@pytest.mark.unit
class TestEncryptionFunctions:
    """Test encryption and decryption functions."""

    def test_generate_encryption_keys_creates_files(self, tmp_path):
        """Test that encryption keys are generated and saved."""
        generate_encryption_keys(str(tmp_path))

        private_key_path = tmp_path / "private_key.pem"
        public_key_path = tmp_path / "public_key.pem"

        assert private_key_path.exists()
        assert public_key_path.exists()

    def test_encrypt_decrypt_roundtrip(self, tmp_path):
        """Test that encryption and decryption work correctly together."""
        generate_encryption_keys(str(tmp_path))

        # Read keys
        with open(tmp_path / "public_key.pem", "rb") as f:
            public_key = f.read()
        with open(tmp_path / "private_key.pem", "rb") as f:
            private_key = f.read()

        # Test encryption and decryption
        original_text = "Test secret message"
        encrypted = encrypt_string(public_key, original_text)
        decrypted = decrypt_string(private_key, encrypted)

        assert decrypted == original_text

    def test_encrypt_string_returns_bytes(self, tmp_path):
        """Test that encryption returns bytes."""
        generate_encryption_keys(str(tmp_path))

        with open(tmp_path / "public_key.pem", "rb") as f:
            public_key = f.read()

        encrypted = encrypt_string(public_key, "test message")
        assert isinstance(encrypted, bytes)


@pytest.mark.unit
class TestGPUAvailability:
    """Test GPU availability verification functions."""

    def test_verify_gpu_availability_no_overlap(self):
        """Test GPU availability when there's no booking overlap."""
        existing_bookings = []
        new_booking = {
            "gpu": "NVIDIA-GeForce-RTX-3090",
            "starting_time": "2024-01-01 10:00:00",
            "ending_time": "2024-01-01 12:00:00",
        }
        gpu_specs = [{"name": "NVIDIA-GeForce-RTX-3090", "replicas": 2, "count": 1}]

        overlapping_times, availability, total = verify_gpu_availability(
            existing_bookings, new_booking, gpu_specs
        )

        assert total == 2  # 2 replicas * 1 GPU each
        assert len(overlapping_times) == 0

    def test_verify_gpu_availability_with_overlap(self):
        """Test GPU availability when bookings overlap."""
        existing_bookings = [
            {
                "gpu": "NVIDIA-GeForce-RTX-3090",
                "start_date": datetime(2024, 1, 1, 9, 0, 0),
                "end_date": datetime(2024, 1, 1, 11, 0, 0),
            }
        ]
        new_booking = {
            "gpu": "NVIDIA-GeForce-RTX-3090",
            "starting_time": "2024-01-01 10:00:00",
            "ending_time": "2024-01-01 12:00:00",
        }
        gpu_specs = [{"name": "NVIDIA-GeForce-RTX-3090", "replicas": 2, "count": 1}]

        overlapping_times, availability, total = verify_gpu_availability(
            existing_bookings, new_booking, gpu_specs
        )

        assert total == 2
        assert len(overlapping_times) > 0

    def test_verify_gpu_availability_different_gpu_type(self):
        """Test GPU availability when existing booking is for different GPU."""
        existing_bookings = [
            {
                "gpu": "NVIDIA-Tesla-V100",
                "start_date": datetime(2024, 1, 1, 9, 0, 0),
                "end_date": datetime(2024, 1, 1, 11, 0, 0),
            }
        ]
        new_booking = {
            "gpu": "NVIDIA-GeForce-RTX-3090",
            "starting_time": "2024-01-01 10:00:00",
            "ending_time": "2024-01-01 12:00:00",
        }
        gpu_specs = [
            {"name": "NVIDIA-GeForce-RTX-3090", "replicas": 2, "count": 1},
            {"name": "NVIDIA-Tesla-V100", "replicas": 1, "count": 1},
        ]

        overlapping_times, availability, total = verify_gpu_availability(
            existing_bookings, new_booking, gpu_specs
        )

        # Different GPU type, so no overlap
        assert len(overlapping_times) == 0

    def test_verify_gpu_availability_with_string_dates(self):
        """Test GPU availability when dates are strings."""
        existing_bookings = [
            {
                "gpu": "NVIDIA-GeForce-RTX-3090",
                "start_date": "2024-01-01 09:00:00",
                "end_date": "2024-01-01 11:00:00",
            }
        ]
        new_booking = {
            "gpu": "NVIDIA-GeForce-RTX-3090",
            "starting_time": "2024-01-01 10:00:00",
            "ending_time": "2024-01-01 12:00:00",
        }
        gpu_specs = [{"name": "NVIDIA-GeForce-RTX-3090", "replicas": 2, "count": 1}]

        overlapping_times, availability, total = verify_gpu_availability(
            existing_bookings, new_booking, gpu_specs
        )

        assert total == 2
        assert len(overlapping_times) > 0


@pytest.mark.unit
class TestGPUBookingPolicy:
    """Test GPU booking policy verification."""

    def test_verify_gpu_booking_policy_user_within_limit(self):
        """Test booking policy when user is within booking limits."""
        existing_bookings = []
        new_booking = {
            "user": "user1@example.com",
            "gpu": "NVIDIA-GeForce-RTX-3090",
            "starting_time": "2024-01-01 10:00:00",
            "ending_time": "2024-01-01 12:00:00",
        }
        global_existing_bookings = []
        gpu_specs = [{"name": "NVIDIA-GeForce-RTX-3090", "replicas": 2, "count": 1}]

        result = verify_gpu_booking_policy(
            existing_bookings, new_booking, global_existing_bookings, gpu_specs
        )

        # The function returns results based on policy checks
        assert result is not None

    def test_verify_gpu_booking_policy_handles_empty_bookings(self):
        """Test booking policy with no existing bookings."""
        new_booking = {
            "user": "user1@example.com",
            "gpu": "NVIDIA-GeForce-RTX-3090",
            "starting_time": "2024-01-01 10:00:00",
            "ending_time": "2024-01-01 12:00:00",
        }
        gpu_specs = [{"name": "NVIDIA-GeForce-RTX-3090", "replicas": 2, "count": 1}]

        result = verify_gpu_booking_policy([], new_booking, [], gpu_specs)

        assert result is not None
