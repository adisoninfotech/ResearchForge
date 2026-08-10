"""In-process metrics for Prometheus-style scraping. Never store manuscript text."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _Counter:
    value: float = 0.0
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class _Gauge:
    value: float = 0.0
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class _Histogram:
    count: int = 0
    total: float = 0.0
    labels: dict[str, str] = field(default_factory=dict)

    def observe(self, amount: float) -> None:
        self.count += 1
        self.total += amount


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, _Counter] = {}
        self._gauges: dict[str, _Gauge] = {}
        self._histograms: dict[str, _Histogram] = {}

    def _key(self, name: str, labels: dict[str, str] | None) -> str:
        if not labels:
            return name
        parts = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{parts}}}"

    def incr(self, name: str, amount: float = 1.0, labels: dict[str, str] | None = None) -> None:
        key = self._key(name, labels)
        with self._lock:
            counter = self._counters.get(key)
            if counter is None:
                counter = _Counter(labels=dict(labels or {}))
                self._counters[key] = counter
            counter.value += amount

    def set_gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        key = self._key(name, labels)
        with self._lock:
            self._gauges[key] = _Gauge(value=value, labels=dict(labels or {}))

    def observe(self, name: str, amount: float, labels: dict[str, str] | None = None) -> None:
        key = self._key(name, labels)
        with self._lock:
            hist = self._histograms.get(key)
            if hist is None:
                hist = _Histogram(labels=dict(labels or {}))
                self._histograms[key] = hist
            hist.observe(amount)

    def render_prometheus(self) -> str:
        lines: list[str] = []
        with self._lock:
            for key, counter in sorted(self._counters.items()):
                lines.append(f"{key} {counter.value}")
            for key, gauge in sorted(self._gauges.items()):
                lines.append(f"{key} {gauge.value}")
            for key, hist in sorted(self._histograms.items()):
                base = key.split("{", 1)[0]
                label_suffix = ""
                if "{" in key:
                    label_suffix = "{" + key.split("{", 1)[1]
                lines.append(f"{base}_count{label_suffix} {hist.count}")
                lines.append(f"{base}_sum{label_suffix} {hist.total}")
        return "\n".join(lines) + ("\n" if lines else "")

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "counters": {k: v.value for k, v in self._counters.items()},
                "gauges": {k: v.value for k, v in self._gauges.items()},
                "histograms": {
                    k: {"count": v.count, "sum": v.total} for k, v in self._histograms.items()
                },
            }


metrics = MetricsRegistry()

# Convenience names used across the app
AI_LATENCY = "researchforge_ai_latency_seconds"
AI_REQUESTS = "researchforge_ai_requests_total"
JOB_QUEUE = "researchforge_job_queue_depth"
EXPORT_JOBS = "researchforge_export_jobs_total"
UPLOAD_JOBS = "researchforge_upload_jobs_total"
DB_POOL = "researchforge_db_pool"


class Timer:
    def __init__(self, name: str, labels: dict[str, str] | None = None) -> None:
        self.name = name
        self.labels = labels
        self._start = 0.0

    def __enter__(self) -> Timer:
        self._start = time.perf_counter()
        return self

    def __exit__(self, *_exc: object) -> None:
        metrics.observe(self.name, time.perf_counter() - self._start, self.labels)
