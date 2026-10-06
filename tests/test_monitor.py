import json
from dataclasses import asdict, replace

import pytest

from monitor import Measurement, Monitor, PhoneApp, SimulatedLink


@pytest.fixture
def reading():
    return Measurement("demo-device-01", "reading-001", "2026-01-01T10:00:00+00:00", 120, 80, 72)


@pytest.fixture
def setup_devices():
    phone = PhoneApp()
    return Monitor("demo-device-01"), phone, SimulatedLink(phone)


def test_transfers_values_units_timestamp_and_device_id(reading, setup_devices):
    monitor, phone, link = setup_devices
    monitor.record(reading)
    assert monitor.sync(link) == 1
    assert asdict(phone.measurements[("demo-device-01", "reading-001")]) == {
        "device_id": "demo-device-01", "measurement_id": "reading-001",
        "measured_at": "2026-01-01T10:00:00+00:00",
        "systolic": 120, "diastolic": 80, "pulse": 72,
        "pressure_unit": "mmHg", "pulse_unit": "bpm",
    }
    assert monitor.pending == []


def test_offline_readings_are_delivered_in_order_after_reconnection(reading, setup_devices):
    monitor, phone, link = setup_devices
    second = replace(reading, measurement_id="reading-002", pulse=75)
    monitor.record(reading)
    monitor.record(second)
    link.connected = False
    assert monitor.sync(link) == 0
    assert monitor.pending == [reading, second]
    assert phone.measurements == {}
    link.connected = True
    assert monitor.sync(link) == 2
    assert list(phone.measurements.values()) == [reading, second]
    assert monitor.pending == []


def test_lost_ack_retry_does_not_duplicate_reading(reading, setup_devices):
    monitor, phone, link = setup_devices
    monitor.record(reading)
    link.lose_next_ack = True
    assert monitor.sync(link) == 0
    assert monitor.pending == [reading]
    assert len(phone.measurements) == 1
    assert monitor.sync(link) == 1
    assert list(phone.measurements.values()) == [reading]
    assert monitor.pending == []


def test_conflicting_duplicate_does_not_overwrite_original(reading):
    phone = PhoneApp()
    phone.receive(reading.encode())
    with pytest.raises(ValueError, match="conflicting measurement ID"):
        phone.receive(replace(reading, pulse=90).encode())
    assert list(phone.measurements.values()) == [reading]


def test_same_reading_id_from_different_devices_is_not_a_duplicate(reading):
    phone = PhoneApp()
    phone.receive(reading.encode())
    other = replace(reading, device_id="demo-device-02")
    phone.receive(other.encode())
    assert list(phone.measurements.values()) == [reading, other]


@pytest.mark.parametrize("payload", ["broken JSON", "[]", "null", "{}", '{"systolic":120}'])
def test_malformed_message_does_not_change_phone_history(payload, reading):
    phone = PhoneApp()
    phone.receive(reading.encode())
    with pytest.raises(ValueError, match="invalid measurement message"):
        phone.receive(payload)
    assert list(phone.measurements.values()) == [reading]


@pytest.mark.parametrize("field,value", [
    ("systolic", 0), ("diastolic", -1), ("pulse", True), ("pulse", "72"),
    ("systolic", 120.5), ("device_id", ""), ("measurement_id", " "),
    ("measured_at", "not-a-date"), ("measured_at", "2026-01-01T10:00:00"),
    ("pressure_unit", "kPa"), ("pulse_unit", "Hz"),
])
def test_invalid_fields_are_rejected(field, value, reading):
    data = asdict(reading)
    data[field] = value
    phone = PhoneApp()
    with pytest.raises(ValueError, match="invalid measurement message"):
        phone.receive(json.dumps(data))
    assert phone.measurements == {}


def test_unknown_fields_are_rejected(reading):
    data = asdict(reading)
    data["unexpected"] = 1
    with pytest.raises(ValueError, match="invalid measurement message"):
        Measurement.decode(json.dumps(data))


def test_wrong_device_reading_is_not_queued(reading, setup_devices):
    monitor, _, _ = setup_devices
    with pytest.raises(ValueError, match="another device"):
        monitor.record(replace(reading, device_id="other-device"))
    assert monitor.pending == []


def test_wrong_ack_does_not_remove_pending_reading(reading, setup_devices):
    class WrongAckLink:
        def send(self, payload):
            return ("other-device", "other-reading")

    monitor, _, _ = setup_devices
    monitor.record(reading)
    with pytest.raises(ValueError, match="unexpected acknowledgement"):
        monitor.sync(WrongAckLink())
    assert monitor.pending == [reading]


def test_empty_queue_sends_nothing(setup_devices):
    monitor, phone, link = setup_devices
    assert monitor.sync(link) == 0
    assert phone.measurements == {}
