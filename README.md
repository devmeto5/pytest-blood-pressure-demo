# Blood Pressure Monitor - Pytest Demo

A beginner-friendly Python project that tests how a simulated blood pressure monitor sends readings to a simulated phone app. Explore data integrity, disconnected operation, retries, and duplicate prevention without buying or connecting equipment.

**Simulation only:** the link is an in-memory stand-in for a wireless connection. This project does not implement Bluetooth, a mobile app, or a manufacturer's device protocol. All sample readings are synthetic.

## Quick start

Requires Python 3.10 or newer.

```bash
git clone https://github.com/devmeto5/pytest-blood-pressure-demo.git
cd pytest-blood-pressure-demo
python -m venv .venv
```

Activate the environment on Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Or on macOS / Linux:

```bash
source .venv/bin/activate
```

Install and run:

```bash
python -m pip install -r requirements.txt
python -m pytest -v
python demo.py
```

Expected test result: **25 passed**.

The demo itself uses only the Python standard library. Expected demo output:

```text
Offline: delivered=0, queued=1
Reconnected: delivered=1, queued=0
Phone received: 120/80 mmHg, pulse 72 bpm
```

## How it works

```text
Monitor queue -> JSON message -> SimulatedLink -> PhoneApp history
              <- acknowledgement of stored measurement <-
```

Each reading carries systolic pressure, diastolic pressure, pulse, explicit units, a timezone-aware timestamp, a device ID, and a measurement ID. The monitor removes a reading from its queue only after receiving its matching acknowledgement.

If the connection fails, the reading remains queued. If the phone stores a reading but the acknowledgement is lost, retrying is safe: the phone identifies duplicates using `(device_id, measurement_id)`. A conflicting payload with the same identity is rejected rather than overwriting history.

## A simple test

```python
from monitor import Measurement, Monitor, PhoneApp, SimulatedLink

def test_reading_reaches_phone():
    phone = PhoneApp()
    monitor = Monitor("demo-device-01")
    link = SimulatedLink(phone)
    reading = Measurement(
        "demo-device-01", "reading-001", "2026-01-01T10:00:00+00:00",
        systolic=120, diastolic=80, pulse=72,
    )
    monitor.record(reading)
    assert monitor.sync(link) == 1
    assert phone.measurements[("demo-device-01", "reading-001")] == reading
    assert monitor.pending == []
```

## What the tests cover

| Scenario | Expected result |
| --- | --- |
| Successful transfer | Values, units, timestamp, and IDs remain unchanged |
| Disconnected link | Readings remain queued; phone history stays unchanged |
| Reconnection | Queued readings arrive in order |
| Lost acknowledgement | Retry stores no duplicate |
| Conflicting duplicate | Original phone record is preserved |
| Same reading ID on different devices | Both readings are stored |
| Malformed or incomplete JSON | Message is rejected without changing history |
| Invalid fields or unsupported units | Message is rejected |
| Unknown fields | Message is rejected |
| Reading from the wrong device | Reading is not queued |
| Incorrect acknowledgement | Pending reading is retained |
| Empty queue | Nothing is sent |

Fixtures provide a fresh setup for each test. Parameterized tests exercise multiple invalid messages and field values. There are no sleeps, network requests, or physical-device dependencies.

## Files

| File | Purpose |
| --- | --- |
| `monitor.py` | Measurement model, monitor queue, phone storage, and simulated link |
| `tests/test_monitor.py` | Automated tests |
| `demo.py` | Small offline/reconnect demonstration |
| `requirements.txt` | Pinned pytest dependency |
| `pytest.ini` | Test discovery settings |

Generate a JUnit XML report with:

```bash
python -m pytest --junitxml=test-results.xml
```

## Scope and limitations

Validation checks the demo message contract, not medical plausibility. Positive integer readings and the units `mmHg` / `bpm` are accepted; the project does not interpret readings, diagnose conditions, or verify sensor accuracy.

Queues and history exist only in memory and are lost when the process exits. Synchronization is synchronous and explicitly triggered; there is no background retry scheduler, persistent storage, pairing, encryption, authentication, or actual Bluetooth packet handling. A malformed queued message or conflicting ID stops synchronization with an error and leaves that reading pending for inspection.

To work with real equipment, replace the simulated link with an adapter for the manufacturer's documented interface and add protocol, timeout, persistence, security, and physical-device tests. Passing this suite validates the simulation only; it is not evidence of clinical accuracy, regulatory compliance, or suitability for patient use.
