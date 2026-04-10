from __future__ import annotations

from signalguard.models import Diagnosis, MetricsSnapshot, Severity, SignalAssessment, TriggeredRule
from signalguard.rules import build_signal_assessments, evaluate_rules


def analyze_snapshot(metrics: MetricsSnapshot) -> Diagnosis:
    signals = build_signal_assessments(metrics)
    triggered_rules = evaluate_rules(metrics)
    signal_status = max((signal.level for signal in signals), default=Severity.OK)
    summary = _build_summary(signals=signals, triggered_rules=triggered_rules)
    non_ok_signals = [signal for signal in signals if signal.level != Severity.OK]

    if not triggered_rules:
        status = Severity.OK if not non_ok_signals else Severity.WARNING
        hypothesis = "No se detectaron combinaciones anómalas concluyentes."
        next_step = "Revisar las señales destacadas y confirmar si forman parte de la carga normal del sistema."
        if not non_ok_signals:
            hypothesis = "No se detectaron anomalías relevantes."
            next_step = "Seguir observando o ajustar umbrales según la carga normal del sistema."
        return Diagnosis(
            status=status,
            metrics=metrics,
            signals=signals,
            summary=summary,
            hypothesis=hypothesis,
            next_step=next_step,
        )

    top_rule = max(triggered_rules, key=lambda rule: int(rule.severity))
    status = max(signal_status, max((rule.severity for rule in triggered_rules), default=Severity.OK))

    return Diagnosis(
        status=status,
        metrics=metrics,
        signals=signals,
        summary=summary,
        triggered_rules=triggered_rules,
        hypothesis=top_rule.hypothesis,
        next_step=top_rule.next_step,
    )


def _build_summary(signals: list[SignalAssessment], triggered_rules: list[TriggeredRule]) -> list[str]:
    if triggered_rules:
        items = [f"Regla activa: {rule.name}." for rule in triggered_rules]
    else:
        items = []

    non_ok_signals = [signal for signal in signals if signal.level != Severity.OK]
    for signal in non_ok_signals:
        items.append(f"{signal.label}: {signal.summary}")

    if not items:
        return ["Sin señales anómalas relevantes en este chequeo."]

    return items[:4]
