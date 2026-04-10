from signalguard.analyzer import analyze_snapshot
from signalguard.models import MetricsSnapshot, Severity
from signalguard.rules import build_signal_assessments, evaluate_rules


def build_metrics(**overrides: float | None) -> MetricsSnapshot:
    base = {
        "cpu_percent": 20.0,
        "load1": 0.6,
        "memory_used_percent": 45.0,
        "swap_used_percent": 0.0,
        "disk_read_kib_s": 150.0,
        "disk_write_kib_s": 120.0,
        "network_receive_kib_s": 50.0,
        "network_send_kib_s": 40.0,
    }
    base.update(overrides)
    return MetricsSnapshot(**base)


def test_detects_cpu_and_load_saturation() -> None:
    rules = evaluate_rules(build_metrics(cpu_percent=91.0, load1=3.4))
    assert any(rule.rule_id == "cpu_load_high" for rule in rules)
    assert max(rule.severity for rule in rules) == Severity.CRITICAL


def test_detects_disk_bottleneck_and_io_wait_pattern() -> None:
    rules = evaluate_rules(build_metrics(cpu_percent=18.0, load1=4.1, disk_read_kib_s=20_000.0, disk_write_kib_s=8_000.0))
    rule_ids = {rule.rule_id for rule in rules}
    assert "disk_io_load_high" in rule_ids
    assert "io_wait_indirect" in rule_ids


def test_detects_memory_pressure() -> None:
    rules = evaluate_rules(build_metrics(memory_used_percent=94.0, swap_used_percent=36.0))
    assert any(rule.rule_id == "memory_pressure" for rule in rules)


def test_returns_empty_rules_when_system_is_healthy() -> None:
    assert evaluate_rules(build_metrics()) == []


def test_builds_signal_assessments() -> None:
    signals = build_signal_assessments(build_metrics(memory_used_percent=84.0))
    signal_map = {signal.signal_id: signal for signal in signals}
    assert signal_map["memory"].level == Severity.WARNING
    assert signal_map["cpu"].level == Severity.OK


def test_analysis_keeps_warning_state_without_triggered_rules() -> None:
    diagnosis = analyze_snapshot(build_metrics(memory_used_percent=82.0))
    assert diagnosis.status == Severity.WARNING
    assert diagnosis.triggered_rules == []
    assert diagnosis.summary


def test_analysis_summary_mentions_triggered_rule() -> None:
    diagnosis = analyze_snapshot(build_metrics(cpu_percent=91.0, load1=3.4))
    assert any("CPU alta con load alto" in item for item in diagnosis.summary)
