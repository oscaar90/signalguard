from __future__ import annotations

from typing import Any

import httpx

from signalguard.models import MetricsSnapshot


class NetdataError(RuntimeError):
    """Raised when Netdata metrics cannot be collected."""


class NetdataClient:
    def __init__(self, base_url: str = "http://127.0.0.1:19999", timeout: float = 5.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def collect_snapshot(self) -> MetricsSnapshot:
        charts = self._get_json("/api/v1/charts")

        cpu_percent = self._read_first_matching_dimension(
            charts,
            [("system.cpu", ["user", "system", "softirq", "irq", "nice"])],
        )
        load1 = self._read_first_matching_dimension(
            charts,
            [("system.load", ["load1", "load", "load1m"])],
        )
        memory_used_percent = self._read_memory_used_percent(charts)
        swap_used_percent = self._read_optional_ratio_percent(
            charts,
            numerator_candidates=[("system.swap", ["used"])],
            denominator_candidates=[("system.swap", ["used", "free"])],
        )
        disk_read_kib_s = self._read_first_matching_dimension(
            charts,
            [("system.io", ["in"]), ("disk.io", ["reads"]), ("disk.sda", ["reads"])],
            default=0.0,
        )
        disk_write_kib_s = self._read_first_matching_dimension(
            charts,
            [("system.io", ["out"]), ("disk.io", ["writes"]), ("disk.sda", ["writes"])],
            default=0.0,
        )
        network_receive_kib_s = self._read_optional_first_matching_dimension(
            charts,
            [("system.net", ["received"]), ("net", ["received"])],
        )
        network_send_kib_s = self._read_optional_first_matching_dimension(
            charts,
            [("system.net", ["sent"]), ("net", ["sent"])],
        )

        return MetricsSnapshot(
            cpu_percent=round(cpu_percent, 2),
            load1=round(load1, 2),
            memory_used_percent=round(memory_used_percent, 2),
            swap_used_percent=round(swap_used_percent, 2) if swap_used_percent is not None else None,
            disk_read_kib_s=round(abs(disk_read_kib_s), 2),
            disk_write_kib_s=round(abs(disk_write_kib_s), 2),
            network_receive_kib_s=round(abs(network_receive_kib_s), 2) if network_receive_kib_s is not None else None,
            network_send_kib_s=round(abs(network_send_kib_s), 2) if network_send_kib_s is not None else None,
        )

    def _get_json(self, path: str) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            response = httpx.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise NetdataError(f"No se pudo consultar Netdata en {url}: {exc}") from exc

    def _get_latest_dimension_value(self, chart: str, dimension: str) -> float:
        data = self._get_json(
            f"/api/v1/data?chart={chart}&format=json&points=1&group=average&after=-60"
        )
        labels = data.get("labels", [])
        rows = data.get("data", [])
        if not labels or not rows:
            raise NetdataError(f"Netdata no devolvió datos para {chart}.")

        try:
            index = labels.index(dimension)
        except ValueError as exc:
            raise NetdataError(f"La dimensión {dimension} no existe en {chart}.") from exc

        value = rows[-1][index]
        if value is None:
            raise NetdataError(f"El valor de {dimension} en {chart} es nulo.")
        return float(value)

    def _chart_exists(self, charts: dict[str, Any], chart_name: str) -> bool:
        return chart_name in charts.get("charts", {})

    def _find_first_dimension(self, charts: dict[str, Any], candidates: list[tuple[str, list[str]]]) -> tuple[str, str]:
        for chart_name, dimensions in candidates:
            if not self._chart_exists(charts, chart_name):
                continue
            for dimension in dimensions:
                try:
                    self._get_latest_dimension_value(chart_name, dimension)
                    return chart_name, dimension
                except NetdataError:
                    continue
        raise NetdataError(f"No se encontró ninguna métrica compatible entre: {candidates}")

    def _read_first_matching_dimension(
        self,
        charts: dict[str, Any],
        candidates: list[tuple[str, list[str]]],
        default: float | None = None,
    ) -> float:
        try:
            chart_name, dimension = self._find_first_dimension(charts, candidates)
            return self._get_latest_dimension_value(chart_name, dimension)
        except NetdataError:
            if default is not None:
                return default
            raise

    def _read_optional_first_matching_dimension(
        self,
        charts: dict[str, Any],
        candidates: list[tuple[str, list[str]]],
    ) -> float | None:
        try:
            return self._read_first_matching_dimension(charts, candidates)
        except NetdataError:
            return None

    def _read_optional_ratio_percent(
        self,
        charts: dict[str, Any],
        numerator_candidates: list[tuple[str, list[str]]],
        denominator_candidates: list[tuple[str, list[str]]],
    ) -> float | None:
        try:
            numerator = self._read_first_matching_dimension(charts, numerator_candidates)
            chart_name, dimensions = denominator_candidates[0]
            if not self._chart_exists(charts, chart_name):
                return None
            total = 0.0
            for dimension in dimensions:
                try:
                    total += abs(self._get_latest_dimension_value(chart_name, dimension))
                except NetdataError:
                    continue
            if total <= 0:
                return None
            return numerator / total * 100.0
        except NetdataError:
            return None

    def _read_memory_used_percent(self, charts: dict[str, Any]) -> float:
        used = self._read_optional_first_matching_dimension(
            charts,
            [("system.ram", ["used"]), ("mem.available", ["MemUsed"])],
        )
        if used is not None:
            chart_name = "system.ram"
            if self._chart_exists(charts, chart_name):
                total = 0.0
                for dimension in ("used", "free", "cached", "buffers"):
                    try:
                        total += abs(self._get_latest_dimension_value(chart_name, dimension))
                    except NetdataError:
                        continue
                if total > 0:
                    return used / total * 100.0

        free_percent = self._read_optional_first_matching_dimension(
            charts,
            [("system.ram", ["free"])],
        )
        if free_percent is not None and free_percent <= 100:
            return max(0.0, 100.0 - free_percent)

        raise NetdataError("No se pudo calcular el uso de memoria desde Netdata.")
