from __future__ import annotations

import json
import time

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from signalguard.analyzer import analyze_snapshot
from signalguard.config import load_config
from signalguard.llm import LLMError, build_local_explanation, generate_explanation
from signalguard.models import Diagnosis
from signalguard.netdata_client import NetdataClient, NetdataError

app = typer.Typer(help="Detecta señales anómalas simples desde Netdata y resume el estado del sistema.")
console = Console()


@app.command()
def check(
    json_output: bool = typer.Option(False, "--json", help="Devuelve la salida en JSON."),
    netdata_url: str = typer.Option(
        load_config().netdata_url,
        "--netdata-url",
        help="Base URL de la API de Netdata.",
    ),
) -> None:
    """Consulta métricas actuales y evalúa reglas locales."""
    diagnosis = _build_diagnosis(netdata_url=netdata_url)
    if json_output:
        console.print_json(data=diagnosis.to_dict())
        return
    _render_diagnosis(diagnosis)


@app.command()
def explain(
    json_output: bool = typer.Option(False, "--json", help="Devuelve la salida en JSON."),
    no_llm: bool = typer.Option(False, "--no-llm", help="Fuerza explicación local sin proveedor LLM."),
    netdata_url: str = typer.Option(
        load_config().netdata_url,
        "--netdata-url",
        help="Base URL de la API de Netdata.",
    ),
) -> None:
    """Añade una explicación breve a partir de las reglas disparadas."""
    diagnosis = _build_diagnosis(netdata_url=netdata_url)

    if no_llm:
        diagnosis.explanation = build_local_explanation(diagnosis)
    else:
        try:
            diagnosis.explanation = generate_explanation(diagnosis)
        except LLMError as exc:
            diagnosis.explanation = build_local_explanation(diagnosis)
            console.print(f"[yellow]Fallo al usar el LLM:[/yellow] {exc}")

    if json_output:
        console.print(json.dumps(diagnosis.to_dict(), indent=2, ensure_ascii=False))
        return
    _render_diagnosis(diagnosis)


@app.command()
def watch(
    interval: int = typer.Option(
        30,
        "--interval",
        min=5,
        help="Segundos entre chequeos consecutivos.",
    ),
    no_llm: bool = typer.Option(False, "--no-llm", help="Fuerza explicación local sin proveedor LLM."),
    json_output: bool = typer.Option(False, "--json", help="Devuelve cada iteración en JSON."),
    netdata_url: str = typer.Option(
        load_config().netdata_url,
        "--netdata-url",
        help="Base URL de la API de Netdata.",
    ),
) -> None:
    """Ejecuta chequeos periódicos para uso continuo en contenedor o terminal."""
    while True:
        diagnosis = _build_diagnosis(netdata_url=netdata_url)
        if no_llm:
            diagnosis.explanation = build_local_explanation(diagnosis)
        else:
            try:
                diagnosis.explanation = generate_explanation(diagnosis)
            except LLMError as exc:
                diagnosis.explanation = build_local_explanation(diagnosis)
                console.print(f"[yellow]Fallo al usar el LLM:[/yellow] {exc}")

        if json_output:
            console.print(json.dumps(diagnosis.to_dict(), ensure_ascii=False))
        else:
            console.rule(f"signalguard {time.strftime('%Y-%m-%d %H:%M:%S')}")
            _render_diagnosis(diagnosis)

        time.sleep(interval)


def _build_diagnosis(netdata_url: str) -> Diagnosis:
    client = NetdataClient(base_url=netdata_url)
    try:
        snapshot = client.collect_snapshot()
    except NetdataError as exc:
        console.print(f"[red]Error consultando Netdata:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    return analyze_snapshot(snapshot)


def _render_diagnosis(diagnosis: Diagnosis) -> None:
    status = diagnosis.status.label()
    title_style = {
        "ok": "green",
        "warning": "yellow",
        "critical": "red",
    }.get(status, "white")
    console.print(Panel.fit(f"estado general: {status}", border_style=title_style))

    summary_table = Table(title="Resumen rápido", show_header=False)
    summary_table.add_column("Mensaje")
    for item in diagnosis.summary:
        summary_table.add_row(item)
    console.print(summary_table)

    metrics_table = Table(title="Métricas relevantes", show_header=True, header_style="bold")
    metrics_table.add_column("Métrica")
    metrics_table.add_column("Valor", justify="right")

    metrics = diagnosis.metrics
    metrics_table.add_row("CPU %", f"{metrics.cpu_percent:.2f}")
    metrics_table.add_row("Load 1m", f"{metrics.load1:.2f}")
    metrics_table.add_row("Memoria usada %", f"{metrics.memory_used_percent:.2f}")
    metrics_table.add_row("Swap usada %", "-" if metrics.swap_used_percent is None else f"{metrics.swap_used_percent:.2f}")
    metrics_table.add_row("Disk I/O KiB/s", f"{metrics.disk_io_kib_s:.2f}")
    metrics_table.add_row("Net RX KiB/s", "-" if metrics.network_receive_kib_s is None else f"{metrics.network_receive_kib_s:.2f}")
    metrics_table.add_row("Net TX KiB/s", "-" if metrics.network_send_kib_s is None else f"{metrics.network_send_kib_s:.2f}")
    console.print(metrics_table)

    signals_table = Table(title="Señales evaluadas", show_header=True, header_style="bold")
    signals_table.add_column("Nivel")
    signals_table.add_column("Señal")
    signals_table.add_column("Valor")
    signals_table.add_column("Lectura")
    for signal in diagnosis.signals:
        signals_table.add_row(signal.level.label(), signal.label, signal.value, signal.summary)
    console.print(signals_table)

    if diagnosis.triggered_rules:
        rules_table = Table(title="Reglas disparadas", show_header=True, header_style="bold")
        rules_table.add_column("Severidad")
        rules_table.add_column("Regla")
        rules_table.add_column("Resumen")
        for rule in diagnosis.triggered_rules:
            rules_table.add_row(rule.severity.label(), rule.name, rule.summary)
        console.print(rules_table)
    else:
        console.print("[green]No se dispararon reglas.[/green]")

    console.print(f"[bold]Hipótesis:[/bold] {diagnosis.hypothesis}")
    console.print(f"[bold]Siguiente paso:[/bold] {diagnosis.next_step}")
    if diagnosis.explanation:
        console.print(f"[bold]Explicación:[/bold] {diagnosis.explanation}")


if __name__ == "__main__":
    app()
