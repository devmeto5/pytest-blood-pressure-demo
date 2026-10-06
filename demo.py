"""Run with python demo.py to watch an offline reading reach the phone."""

from monitor import Measurement, Monitor, PhoneApp, SimulatedLink


def main():
    phone = PhoneApp()
    monitor = Monitor("demo-device-01")
    link = SimulatedLink(phone)
    monitor.record(Measurement("demo-device-01", "reading-001", "2026-01-01T10:00:00+00:00", 120, 80, 72))
    link.connected = False
    print(f"Offline: delivered={monitor.sync(link)}, queued={len(monitor.pending)}")
    link.connected = True
    print(f"Reconnected: delivered={monitor.sync(link)}, queued={len(monitor.pending)}")
    for reading in phone.measurements.values():
        print(f"Phone received: {reading.systolic}/{reading.diastolic} {reading.pressure_unit}, pulse {reading.pulse} {reading.pulse_unit}")


if __name__ == "__main__":
    main()
