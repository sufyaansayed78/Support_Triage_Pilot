"""CloudWatch Embedded Metric Format (EMF).

The app writes one JSON line per event to stdout; the ECS awslogs driver ships it to
CloudWatch Logs, and CloudWatch extracts the metrics automatically. No PutMetricData
call on the request path, no extra IAM, no added latency.
"""
import json
import sys
import time
from threading import Lock
from typing import Protocol, TextIO


class Metrics(Protocol):
    def emit(self, category: str, values: dict[str, float], units: dict[str, str] | None = None) -> None: ...


class EmfMetrics:
    def __init__(self, namespace: str, stream: TextIO | None = None):
        self._ns, self._stream, self._lock = namespace, stream or sys.stdout, Lock()

    def emit(self, category: str, values: dict[str, float], units: dict[str, str] | None = None) -> None:
        units = units or {}
        record = {
            "_aws": {
                "Timestamp": int(time.time() * 1000),
                "CloudWatchMetrics": [
                    {
                        "Namespace": self._ns,
                        # Two dimension sets: per-category AND an all-categories rollup.
                        "Dimensions": [["Category"], []],
                        "Metrics": [{"Name": n, "Unit": units.get(n, "Count")} for n in values],
                    }
                ],
            },
            "Category": category,
            **values,
        }
        with self._lock:
            self._stream.write(json.dumps(record) + "\n")
            self._stream.flush()


class NullMetrics:
    def emit(self, category: str, values: dict[str, float], units: dict[str, str] | None = None) -> None:
        pass
