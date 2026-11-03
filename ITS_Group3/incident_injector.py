"""Artificial traffic-incident injection for the ITS_Group3 SUMO project.

The module deliberately uses TraCI's setSpeed(vehicle_id, 0) as required by
Member 2's assignment. The vehicle is selected reproducibly from vehicles on
the configured edge and near the target position between two E1 stations.
"""
from __future__ import annotations

import csv
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass(frozen=True)
class IncidentConfig:
    """Parameters for one artificial stopped-vehicle incident."""

    enabled: bool = True
    scheduled_time: float = 900.0
    edge_id: str = "E_main"
    target_position: float = 1750.0
    search_radius: float = 125.0
    duration: float = 300.0
    max_wait: float = 120.0
    min_initial_speed: float = 0.5
    seed: int = 42
    disable_speed_checks: bool = True


class IncidentInjector:
    """Schedule, start, hold, and release one stopped-vehicle incident.

    Call :meth:`step` once per SUMO simulation step, after ``simulationStep``.
    At the scheduled time, a vehicle is chosen randomly among vehicles on the
    configured edge whose lane position is within ``search_radius`` of the
    target. If none is present, the injector retries until ``max_wait``.

    ``setSpeedMode(..., 0)`` is optional and enabled by default to make the
    artificial stop immediate for this controlled stress test. The original
    speed mode is restored on release. This is a deliberate simulation
    override, not a claim that a real vehicle can stop instantaneously.
    """

    CSV_FIELDS = [
        "scenario_id", "status", "scheduled_time", "actual_start_time",
        "release_time", "vehicle_id", "edge_id", "lane_id",
        "target_position_m", "actual_position_m", "position_error_m",
        "initial_speed_mps", "incident_duration_s", "message",
    ]

    def __init__(self, config: IncidentConfig, scenario_id: str = "") -> None:
        self.config = config
        self.scenario_id = scenario_id
        self._rng = random.Random(config.seed)
        self._attempt_started_at: Optional[float] = None
        self._vehicle_id: Optional[str] = None
        self._original_speed_mode: Optional[int] = None
        self._actual_start_time: Optional[float] = None
        self._actual_position: Optional[float] = None
        self._lane_id: Optional[str] = None
        self._initial_speed: Optional[float] = None
        self._release_time: Optional[float] = None
        self._status = "pending" if config.enabled else "disabled"
        self._message = ""
        self._rows: list[dict[str, Any]] = []

    @property
    def status(self) -> str:
        return self._status

    @property
    def is_active(self) -> bool:
        return self._status == "active"

    @property
    def event_rows(self) -> list[dict[str, Any]]:
        return list(self._rows)

    def step(self, traci: Any, sim_time: float) -> None:
        """Advance injector state by one simulation step."""
        if not self.config.enabled or self._status in {
            "completed", "disabled", "not_injected", "simulation_ended"
        }:
            return

        if self._status == "pending" and sim_time >= self.config.scheduled_time:
            self._attempt_started_at = sim_time
            self._try_inject(traci, sim_time)
            return

        if self._status == "waiting_for_vehicle":
            self._try_inject(traci, sim_time)
            return

        if self._status == "active" and self._actual_start_time is not None:
            if sim_time >= self._actual_start_time + self.config.duration:
                self._release(traci, sim_time)

    def _try_inject(self, traci: Any, sim_time: float) -> None:
        if self._attempt_started_at is None:
            self._attempt_started_at = sim_time

        candidates: list[tuple[str, str, float, float]] = []
        for vehicle_id in traci.vehicle.getIDList():
            try:
                if traci.vehicle.getRoadID(vehicle_id) != self.config.edge_id:
                    continue
                lane_position = float(traci.vehicle.getLanePosition(vehicle_id))
                speed = float(traci.vehicle.getSpeed(vehicle_id))
                offset = abs(lane_position - self.config.target_position)
                if offset <= self.config.search_radius and speed >= self.config.min_initial_speed:
                    lane_id = traci.vehicle.getLaneID(vehicle_id)
                    candidates.append((vehicle_id, lane_id, lane_position, speed))
            except Exception:
                # Vehicle may have departed/arrived between TraCI queries.
                continue

        if candidates:
            vehicle_id, lane_id, actual_position, initial_speed = self._rng.choice(candidates)
            try:
                if self.config.disable_speed_checks:
                    self._original_speed_mode = int(traci.vehicle.getSpeedMode(vehicle_id))
                    traci.vehicle.setSpeedMode(vehicle_id, 0)
                traci.vehicle.setSpeed(vehicle_id, 0)
            except Exception:
                # Avoid leaving a partially modified vehicle if TraCI rejects
                # one of the state changes.
                try:
                    traci.vehicle.setSpeed(vehicle_id, -1)
                    if self._original_speed_mode is not None:
                        traci.vehicle.setSpeedMode(vehicle_id, self._original_speed_mode)
                except Exception:
                    pass
                self._original_speed_mode = None
                self._status = "waiting_for_vehicle"
                self._message = "TraCI khong ap dung duoc lenh dung xe; se thu lai."
                return

            self._vehicle_id = vehicle_id
            self._lane_id = lane_id
            self._actual_position = actual_position
            self._initial_speed = initial_speed
            self._actual_start_time = sim_time
            self._status = "active"
            self._message = "Da chon ngau nhien mot xe trong vung tiem su co."
            return

        waited = sim_time - self._attempt_started_at
        if waited >= self.config.max_wait:
            self._status = "not_injected"
            self._message = (
                "Khong co xe phu hop trong vung tiem su co trong thoi gian cho toi da."
            )
            self._append_event_row(status="not_injected", release_time=None)
        else:
            self._status = "waiting_for_vehicle"

    def _release(self, traci: Any, sim_time: float) -> None:
        if self._vehicle_id is not None:
            try:
                active_ids = set(traci.vehicle.getIDList())
                if self._vehicle_id in active_ids:
                    # -1 restores SUMO's normal speed control. Restore the
                    # vehicle's original speedMode as well.
                    traci.vehicle.setSpeed(self._vehicle_id, -1)
                    if self._original_speed_mode is not None:
                        traci.vehicle.setSpeedMode(
                            self._vehicle_id, self._original_speed_mode
                        )
            except Exception as exc:
                self._message = f"Da het thoi luong su co nhung loi khi giai phong xe: {exc}"
        self._release_time = sim_time
        self._status = "completed"
        if not self._message:
            self._message = "Da giai phong xe va tra quyen dieu khien toc do ve SUMO."
        self._append_event_row(status="completed", release_time=sim_time)

    def finalize(self, traci: Any, sim_time: float) -> None:
        """Release an active vehicle if SUMO ends before the planned duration."""
        if self._status == "active":
            self._release(traci, sim_time)
            if self._rows:
                self._rows[-1]["status"] = "simulation_ended_before_release"
                self._rows[-1]["message"] = (
                    "Mo phong ket thuc truoc khi het thoi luong su co; xe da duoc tra quyen toc do."
                )
            self._status = "simulation_ended"
        elif self._status in {"pending", "waiting_for_vehicle"}:
            self._status = "not_injected"
            self._message = "Mo phong ket thuc truoc khi tim duoc xe phu hop."
            self._append_event_row(status="not_injected", release_time=None)

    def _append_event_row(self, status: str, release_time: Optional[float]) -> None:
        if self._rows:
            return
        self._rows.append({
            "scenario_id": self.scenario_id,
            "status": status,
            "scheduled_time": self.config.scheduled_time,
            "actual_start_time": self._actual_start_time,
            "release_time": release_time,
            "vehicle_id": self._vehicle_id,
            "edge_id": self.config.edge_id,
            "lane_id": self._lane_id,
            "target_position_m": self.config.target_position,
            "actual_position_m": self._actual_position,
            "position_error_m": (
                abs(self._actual_position - self.config.target_position)
                if self._actual_position is not None else None
            ),
            "initial_speed_mps": self._initial_speed,
            "incident_duration_s": (
                (release_time - self._actual_start_time)
                if release_time is not None and self._actual_start_time is not None
                else self.config.duration
            ),
            "message": self._message,
        })

    def write_csv(self, path: str | Path) -> Path:
        """Write incident event details; no rows means no configured incident."""
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.CSV_FIELDS)
            writer.writeheader()
            writer.writerows(self._rows)
        return destination

    def summary(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "status": self._status,
            "config": asdict(self.config),
            "vehicle_id": self._vehicle_id,
            "actual_start_time": self._actual_start_time,
            "release_time": self._release_time,
            "actual_position_m": self._actual_position,
            "lane_id": self._lane_id,
            "message": self._message,
        }
