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

        # Test encryption and decryption
        original_text = "Test secret message"
        encrypted = encrypt_string(str(tmp_path / "public_key.pem"), original_text)
        decrypted = decrypt_string(str(tmp_path / "private_key.pem"), encrypted)

        assert decrypted == original_text

    def test_encrypt_string_returns_hex(self, tmp_path):
        """Test that encryption returns hex."""
        generate_encryption_keys(str(tmp_path))

        encrypted = encrypt_string(str(tmp_path / "public_key.pem"), "test message")
        assert isinstance(encrypted, str)


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
        assert len(overlapping_times) == 2
        assert overlapping_times[0] == datetime(2024, 1, 1, 10, 0, 0)
        assert overlapping_times[1] == datetime(2024, 1, 1, 12, 0, 0)
        assert availability[0] == 2

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
        assert len(overlapping_times) == 3
        assert overlapping_times[0] == datetime(2024, 1, 1, 10, 0, 0)
        assert overlapping_times[1] == datetime(2024, 1, 1, 11, 0, 0)
        assert overlapping_times[2] == datetime(2024, 1, 1, 12, 0, 0)
        assert availability[0] == 1
        assert availability[1] == 2

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
            {"name": "NVIDIA-GeForce-RTX-3090", "replicas": 1, "count": 1},
            {"name": "NVIDIA-Tesla-V100", "replicas": 1, "count": 1},
        ]

        overlapping_times, availability, total = verify_gpu_availability(
            existing_bookings, new_booking, gpu_specs
        )

        # Different GPU type, so no overlap
        assert len(overlapping_times) == 2
        assert total == 1
        assert overlapping_times[0] == datetime(2024, 1, 1, 10, 0, 0)
        assert overlapping_times[1] == datetime(2024, 1, 1, 12, 0, 0)
        assert availability[0] == 1

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
        assert len(overlapping_times) == 3
        assert overlapping_times[0] == datetime(2024, 1, 1, 10, 0, 0)
        assert overlapping_times[1] == datetime(2024, 1, 1, 11, 0, 0)
        assert overlapping_times[2] == datetime(2024, 1, 1, 12, 0, 0)
        assert availability[0] == 1
        assert availability[1] == 2


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
            "ending_time": "2024-01-02 12:00:00",
        }
        global_existing_bookings = []
        gpu_specs = [{"name": "NVIDIA-GeForce-RTX-3090", "replicas": 2, "count": 1}]

        is_bookable, error_msg = verify_gpu_booking_policy(
            existing_bookings, new_booking, global_existing_bookings, gpu_specs
        )

        # The function returns results based on policy checks
        assert is_bookable is True
        assert error_msg is None

    def test_verify_gpu_booking_policy_user_with_existing_booking(self):
        """Test booking policy when user is within booking limits."""
        class Booking:
            def __init__(self, user, gpu, namespace, start_date, end_date):
                self.user = user
                self.gpu = gpu
                self.namespace = namespace
                self.start_date = start_date
                self.end_date = end_date

        existing_bookings = [
            Booking(
                user="user1@example.com",
                gpu="NVIDIA-GeForce-RTX-3090",
                namespace="namespace1",
                start_date=datetime(2024, 1, 1, 9, 0, 0),
                end_date=datetime(2024, 1, 2, 11, 0, 0),
            )
        ]

        new_booking = {
            "user": "user1@example.com",
            "gpu": "NVIDIA-GeForce-RTX-3090",
            "starting_time": "2024-01-01 10:00:00",
            "ending_time": "2024-01-02 12:00:00",
        }
        global_existing_bookings = []
        gpu_specs = [{"name": "NVIDIA-GeForce-RTX-3090", "replicas": 2, "count": 1}]

        is_bookable, error_msg = verify_gpu_booking_policy(
            existing_bookings, new_booking, global_existing_bookings, gpu_specs
        )

        # The function returns results based on policy checks
        assert is_bookable is False
        assert error_msg == "The time between your old booking and the new booking must be at least 14 days. You can start a new booking on 2024-01-16 11:00:00."

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
