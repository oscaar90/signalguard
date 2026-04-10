from __future__ import annotations

from signalguard.models import MetricsSnapshot, Severity, SignalAssessment, TriggeredRule

CPU_HIGH = 85.0
CPU_MODERATE = 25.0
LOAD_HIGH = 2.0
LOAD_WARNING = 1.0
MEMORY_HIGH = 90.0
MEMORY_WARNING = 80.0
SWAP_HIGH = 20.0
DISK_IO_HIGH = 25_000.0
DISK_IO_WARNING = 8_000.0
NETWORK_TRAFFIC_WARNING = 15_000.0


def build_signal_assessments(metrics: MetricsSnapshot) -> list[SignalAssessment]:
    return [
        _assess_cpu(metrics),
        _assess_load(metrics),
        _assess_memory(metrics),
        _assess_disk(metrics),
        _assess_network(metrics),
    ]


def evaluate_rules(metrics: MetricsSnapshot) -> list[TriggeredRule]:
    rules: list[TriggeredRule] = []

    if metrics.cpu_percent >= CPU_HIGH and metrics.load1 >= LOAD_HIGH:
        rules.append(
            TriggeredRule(
                rule_id="cpu_load_high",
                name="CPU alta con load alto",
                severity=Severity.CRITICAL,
                summary="La CPU y el load medio están altos al mismo tiempo.",
                hypothesis="Posible saturación general de CPU o procesos intensivos en ejecución.",
                next_step="Revisar procesos con mayor consumo de CPU y confirmar si la carga es esperada.",
                evidence=[
                    f"cpu_percent={metrics.cpu_percent:.2f}",
                    f"load1={metrics.load1:.2f}",
                ],
            )
        )

    if metrics.disk_io_kib_s >= DISK_IO_HIGH and metrics.load1 >= LOAD_HIGH:
        rules.append(
            TriggeredRule(
                rule_id="disk_io_load_high",
                name="Disk I/O alto con load alto",
                severity=Severity.CRITICAL,
                summary="El volumen de I/O en disco y el load apuntan a espera relevante del subsistema de disco.",
                hypothesis="Posible cuello de botella de disco o ráfaga de escrituras/lecturas.",
                next_step="Inspeccionar procesos con más I/O y latencia de disco antes de escalar.",
                evidence=[
                    f"disk_io_kib_s={metrics.disk_io_kib_s:.2f}",
                    f"load1={metrics.load1:.2f}",
                ],
            )
        )

    if metrics.memory_used_percent >= MEMORY_HIGH and (metrics.swap_used_percent or 0.0) >= SWAP_HIGH:
        rules.append(
            TriggeredRule(
                rule_id="memory_pressure",
                name="Memoria alta con uso de swap",
                severity=Severity.CRITICAL,
                summary="La memoria usada es alta y ya hay uso apreciable de swap.",
                hypothesis="Posible presión de memoria y degradación por swapping.",
                next_step="Localizar procesos con mayor RSS y valorar reducción de carga o ampliación de memoria.",
                evidence=[
                    f"memory_used_percent={metrics.memory_used_percent:.2f}",
                    f"swap_used_percent={metrics.swap_used_percent:.2f}",
                ],
            )
        )

    if (
        metrics.cpu_percent <= CPU_MODERATE
        and metrics.load1 >= LOAD_HIGH
        and metrics.disk_io_kib_s >= DISK_IO_HIGH
    ):
        rules.append(
            TriggeredRule(
                rule_id="io_wait_indirect",
                name="CPU baja con load alto e I/O alto",
                severity=Severity.WARNING,
                summary="El load es alto sin saturación real de CPU y con disco ocupado.",
                hypothesis="Posible espera por disco o threads bloqueados en I/O.",
                next_step="Comprobar latencia de disco y procesos en estado D o con colas de I/O elevadas.",
                evidence=[
                    f"cpu_percent={metrics.cpu_percent:.2f}",
                    f"load1={metrics.load1:.2f}",
                    f"disk_io_kib_s={metrics.disk_io_kib_s:.2f}",
                ],
            )
        )

    return rules


def _assess_cpu(metrics: MetricsSnapshot) -> SignalAssessment:
    if metrics.cpu_percent >= CPU_HIGH:
        level = Severity.CRITICAL
        summary = "CPU claramente saturada."
    elif metrics.cpu_percent >= 70.0:
        level = Severity.WARNING
        summary = "CPU elevada para un chequeo puntual."
    else:
        level = Severity.OK
        summary = "Uso de CPU dentro de un rango razonable."
    return SignalAssessment(
        signal_id="cpu",
        label="CPU",
        level=level,
        value=f"{metrics.cpu_percent:.2f}%",
        summary=summary,
    )


def _assess_load(metrics: MetricsSnapshot) -> SignalAssessment:
    if metrics.load1 >= LOAD_HIGH:
        level = Severity.CRITICAL
        summary = "Load alto y sostenido a 1 minuto."
    elif metrics.load1 >= LOAD_WARNING:
        level = Severity.WARNING
        summary = "Load por encima del ruido habitual."
    else:
        level = Severity.OK
        summary = "Load bajo o moderado."
    return SignalAssessment(
        signal_id="load",
        label="Load 1m",
        level=level,
        value=f"{metrics.load1:.2f}",
        summary=summary,
    )


def _assess_memory(metrics: MetricsSnapshot) -> SignalAssessment:
    swap = metrics.swap_used_percent or 0.0
    if metrics.memory_used_percent >= MEMORY_HIGH and swap >= SWAP_HIGH:
        level = Severity.CRITICAL
        summary = "Memoria alta con evidencia de swapping."
    elif metrics.memory_used_percent >= MEMORY_WARNING:
        level = Severity.WARNING
        summary = "Memoria alta; conviene vigilar presión y crecimiento."
    else:
        level = Severity.OK
        summary = "Uso de memoria sin presión aparente."
    swap_label = "-" if metrics.swap_used_percent is None else f"{metrics.swap_used_percent:.2f}% swap"
    return SignalAssessment(
        signal_id="memory",
        label="Memoria",
        level=level,
        value=f"{metrics.memory_used_percent:.2f}% RAM / {swap_label}",
        summary=summary,
    )


def _assess_disk(metrics: MetricsSnapshot) -> SignalAssessment:
    if metrics.disk_io_kib_s >= DISK_IO_HIGH:
        level = Severity.CRITICAL
        summary = "I/O de disco suficientemente alto como para ser cuello de botella."
    elif metrics.disk_io_kib_s >= DISK_IO_WARNING:
        level = Severity.WARNING
        summary = "I/O de disco elevado; conviene correlacionarlo con load y latencia."
    else:
        level = Severity.OK
        summary = "Actividad de disco baja o moderada."
    return SignalAssessment(
        signal_id="disk_io",
        label="Disk I/O",
        level=level,
        value=f"{metrics.disk_io_kib_s:.2f} KiB/s",
        summary=summary,
    )


def _assess_network(metrics: MetricsSnapshot) -> SignalAssessment:
    receive = metrics.network_receive_kib_s or 0.0
    send = metrics.network_send_kib_s or 0.0
    total = receive + send
    if metrics.network_receive_kib_s is None and metrics.network_send_kib_s is None:
        return SignalAssessment(
            signal_id="network",
            label="Red",
            level=Severity.OK,
            value="-",
            summary="Netdata no expuso métricas de red útiles para este host.",
        )
    if total >= NETWORK_TRAFFIC_WARNING:
        level = Severity.WARNING
        summary = "Tráfico de red apreciable; útil para correlación, no para alertar por sí solo."
    else:
        level = Severity.OK
        summary = "Tráfico de red bajo o moderado."
    return SignalAssessment(
        signal_id="network",
        label="Red",
        level=level,
        value=f"rx {receive:.2f} / tx {send:.2f} KiB/s",
        summary=summary,
    )
