from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import IntEnum
from typing import Any


class Severity(IntEnum):
    OK = 0
    WARNING = 1
    CRITICAL = 2

    def label(self) -> str:
        return self.name.lower()


@dataclass(slots=True)
class MetricsSnapshot:
    cpu_percent: float
    load1: float
    memory_used_percent: float
    swap_used_percent: float | None
    disk_read_kib_s: float
    disk_write_kib_s: float
    network_receive_kib_s: float | None
    network_send_kib_s: float | None

    @property
    def disk_io_kib_s(self) -> float:
        return self.disk_read_kib_s + self.disk_write_kib_s

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["disk_io_kib_s"] = round(self.disk_io_kib_s, 2)
        return data


@dataclass(slots=True)
class SignalAssessment:
    signal_id: str
    label: str
    level: Severity
    value: str
    summary: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["level"] = self.level.label()
        return data


@dataclass(slots=True)
class TriggeredRule:
    rule_id: str
    name: str
    severity: Severity
    summary: str
    hypothesis: str
    next_step: str
    evidence: list[str]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["severity"] = self.severity.label()
        return data


@dataclass(slots=True)
class Diagnosis:
    status: Severity
    metrics: MetricsSnapshot
    signals: list[SignalAssessment] = field(default_factory=list)
    summary: list[str] = field(default_factory=list)
    triggered_rules: list[TriggeredRule] = field(default_factory=list)
    hypothesis: str = "No se detectaron anomalías relevantes."
    next_step: str = "Seguir observando o ajustar umbrales según la carga normal del sistema."
    explanation: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.label(),
            "metrics": self.metrics.to_dict(),
            "signals": [signal.to_dict() for signal in self.signals],
            "summary": self.summary,
            "triggered_rules": [rule.to_dict() for rule in self.triggered_rules],
            "hypothesis": self.hypothesis,
            "next_step": self.next_step,
            "explanation": self.explanation,
        }
