"""In-memory device-to-phone simulation; no Bluetooth or clinical logic."""

import json
from dataclasses import asdict, dataclass
from datetime import datetime


@dataclass(frozen=True)
class Measurement:
    device_id: str
    measurement_id: str
    measured_at: str
    systolic: int
    diastolic: int
    pulse: int
    pressure_unit: str = "mmHg"
    pulse_unit: str = "bpm"

    def __post_init__(self):
        for name in ("device_id", "measurement_id", "measured_at"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        timestamp = datetime.fromisoformat(self.measured_at)
        if timestamp.utcoffset() is None:
            raise ValueError("measured_at must include a timezone")
        for name in ("systolic", "diastolic", "pulse"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if self.pressure_unit != "mmHg" or self.pulse_unit != "bpm":
            raise ValueError("unsupported units")

    def encode(self):
        return json.dumps(asdict(self))

    @classmethod
    def decode(cls, payload):
        try:
            data = json.loads(payload)
            if not isinstance(data, dict):
                raise ValueError("expected a JSON object")
            if set(data) != set(cls.__dataclass_fields__):
                raise ValueError("unexpected or missing fields")
            return cls(**data)
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid measurement message") from exc


class PhoneApp:
    def __init__(self):
        self.measurements = {}

    def receive(self, payload):
        measurement = Measurement.decode(payload)
        key = (measurement.device_id, measurement.measurement_id)
        existing = self.measurements.get(key)
        if existing is not None and existing != measurement:
            raise ValueError("conflicting measurement ID")
        self.measurements[key] = measurement
        return key  # Acknowledgement: the phone has stored this measurement.


class SimulatedLink:
    def __init__(self, phone):
        self.phone = phone
        self.connected = True
        self.lose_next_ack = False

    def send(self, payload):
        if not self.connected:
            raise ConnectionError("link disconnected")
        acknowledgement = self.phone.receive(payload)
        if self.lose_next_ack:
            self.lose_next_ack = False
            raise ConnectionError("acknowledgement lost")
        return acknowledgement


class Monitor:
    def __init__(self, device_id):
        if not isinstance(device_id, str) or not device_id.strip():
            raise ValueError("device_id must be a non-empty string")
        self.device_id = device_id
        self.pending = []

    def record(self, measurement):
        if measurement.device_id != self.device_id:
            raise ValueError("measurement belongs to another device")
        self.pending.append(measurement)

    def sync(self, link):
        """Remove each queued reading only after a matching acknowledgement."""
        sent = 0
        while self.pending:
            measurement = self.pending[0]
            try:
                ack = link.send(measurement.encode())
            except ConnectionError:
                break
            if ack != (self.device_id, measurement.measurement_id):
                raise ValueError("unexpected acknowledgement")
            self.pending.pop(0)
            sent += 1
        return sent
