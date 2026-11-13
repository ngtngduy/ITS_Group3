"""Visualizer and Real-time Incident Alerting Module for ITS_Group3.

Author: Thanh vien 5 (Integration & Visualization Lead)
Role:
    - TraCI-based visual alerts in SUMO-GUI (highlighting stopped/incident vehicles in RED,
      marking affected detector pairs/warning zones).
    - Formatted, ANSI-colored console alerts for Traffic Management Center (TMC) operators.
    - Persistent CSV logging of all detection and visualization events.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


# ANSI escape sequences for vibrant, high-contrast terminal styling
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_RED = "\033[41m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"


@dataclass
class AlertRecord:
    """Represents a single confirmed incident alert event."""
    sim_time: float
    wall_time: str
    station_upstream: str
    station_downstream: str
    position_start_m: float
    position_end_m: float
    vehicle_id: Optional[str]
    docc: float
    occrdf: float
    severity: str
    status: str
    description: str


class Visualizer:
    """Manages real-time visual warnings in SUMO-GUI and formatted console logging.

    Adheres strictly to the Member 5 specification:
    - Changes vehicle color to BRIGHT RED (255, 0, 0, 255) upon incident detection.
    - Highlights upstream/downstream detectors and affected highway zones.
    - Outputs high-visibility colored alerts to the Terminal Console.
    - Saves structured event logs to visualizer_alerts.csv for quantitative analysis.
    """

    CSV_FIELDS = [
        "sim_time_s",
        "wall_time",
        "station_upstream",
        "station_downstream",
        "position_start_m",
        "position_end_m",
        "vehicle_id",
        "docc_diff",
        "occrdf_ratio",
        "severity",
        "status",
        "description",
    ]

    # RGBA color presets for SUMO-GUI
    COLOR_INCIDENT_RED = (255, 0, 0, 255)       # Bright Red for incident vehicle
    COLOR_WARNING_ORANGE = (255, 140, 0, 255)   # Orange for congested upstream
    COLOR_NORMAL = (255, 255, 255, 255)         # Default fallback color

    def __init__(self, output_dir: Optional[str | Path] = None, enable_gui_effects: bool = True) -> None:
        self.enable_gui_effects = enable_gui_effects
        self.output_dir = Path(output_dir) if output_dir else Path("output") / "member5"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.alerts_history: list[AlertRecord] = []
        self._highlighted_vehicles: set[str] = set()
        self._highlighted_polygons: set[str] = set()

    def highlight_incident_vehicle(self, traci: Any, vehicle_id: str, color: tuple[int, int, int, int] = COLOR_INCIDENT_RED) -> bool:
        """Change the visual color of the incident vehicle in SUMO-GUI to RED.

        Uses TraCI's vehicle.setColor() and vehicle.highlight() APIs.
        """
        if not self.enable_gui_effects:
            return False

        try:
            active_vehicles = set(traci.vehicle.getIDList())
            if vehicle_id in active_vehicles:
                # 1. Change vehicle color to RED
                traci.vehicle.setColor(vehicle_id, color)
                # 2. Highlight vehicle with visual ring (if supported in GUI mode)
                try:
                    traci.vehicle.highlight(vehicle_id, color=color, size=5.0, alphaMax=255, duration=300)
                except Exception:
                    pass  # TraCI highlight is optional depending on SUMO build

                self._highlighted_vehicles.add(vehicle_id)
                return True
        except Exception as exc:
            print(f"{Style.YELLOW}[Visualizer Warning] Khong the doi mau xe {vehicle_id}: {exc}{Style.RESET}")
        return False

    def reset_vehicle_color(self, traci: Any, vehicle_id: str) -> None:
        """Restore normal color of vehicle when incident is cleared."""
        if not self.enable_gui_effects or vehicle_id not in self._highlighted_vehicles:
            return

        try:
            active_vehicles = set(traci.vehicle.getIDList())
            if vehicle_id in active_vehicles:
                traci.vehicle.setColor(vehicle_id, self.COLOR_NORMAL)
                self._highlighted_vehicles.discard(vehicle_id)
        except Exception:
            pass

    def log_incident_console(
        self,
        sim_time: float,
        station_upstream: str,
        station_downstream: str,
        position_range: tuple[float, float],
        vehicle_id: Optional[str] = None,
        docc: float = 0.0,
        occrdf: float = 0.0,
        severity: str = "CRITICAL",
        is_confirmed: bool = True,
    ) -> None:
        """Print a prominently styled alert block to the terminal console."""
        now_str = datetime.now().strftime("%H:%M:%S")
        pos_start, pos_end = position_range

        header_bg = Style.BG_RED if severity == "CRITICAL" else Style.BG_YELLOW
        status_text = "CONFIRMED (Persistence Test: PASS)" if is_confirmed else "SUSPECTED (Verifying...)"
        veh_info = f"{Style.BOLD}{vehicle_id}{Style.RESET}" if vehicle_id else "Dang xac dinh qua cam bien"

        print("\n" + f"{header_bg}{Style.WHITE}{Style.BOLD} [CANH BAO AID] PHAT HIEN SU CO GIAO THONG / UN TAC {Style.RESET}")
        print(f"{Style.RED}┌─────────────────────────────────────────────────────────────────────────────┐{Style.RESET}")
        print(f"{Style.RED}│{Style.RESET} {Style.BOLD}Thoi gian mo phong:{Style.RESET} {Style.CYAN}{sim_time:8.1f}s{Style.RESET}  |  {Style.BOLD}Gio he thong:{Style.RESET} {now_str}            {Style.RED}│{Style.RESET}")
        print(f"{Style.RED}│{Style.RESET} {Style.BOLD}Vi tri anh huong  :{Style.RESET} Giua tram {Style.YELLOW}{station_upstream}{Style.RESET} va {Style.YELLOW}{station_downstream}{Style.RESET} (km {pos_start/1000:.2f} -> {pos_end/1000:.2f})      {Style.RED}│{Style.RESET}")
        print(f"{Style.RED}│{Style.RESET} {Style.BOLD}Phuong tien su co :{Style.RESET} {veh_info:<40} {Style.RED}│{Style.RESET}")
        print(f"{Style.RED}│{Style.RESET} {Style.BOLD}Chi so thuat toan :{Style.RESET} DOCC = {Style.RED}{docc:5.2f}%{Style.RESET}  |  OCCRDF = {Style.RED}{occrdf:5.2f}{Style.RESET}               {Style.RED}│{Style.RESET}")
        print(f"{Style.RED}│{Style.RESET} {Style.BOLD}Trang thai xac nhan:{Style.RESET} {Style.GREEN if is_confirmed else Style.YELLOW}{status_text:<42}{Style.RESET} {Style.RED}│{Style.RESET}")
        print(f"{Style.RED}└─────────────────────────────────────────────────────────────────────────────┘{Style.RESET}\n")

        # Record in history
        record = AlertRecord(
            sim_time=sim_time,
            wall_time=now_str,
            station_upstream=station_upstream,
            station_downstream=station_downstream,
            position_start_m=pos_start,
            position_end_m=pos_end,
            vehicle_id=vehicle_id,
            docc=docc,
            occrdf=occrdf,
            severity=severity,
            status="CONFIRMED" if is_confirmed else "SUSPECTED",
            description=f"Su co chenh lech OCC giua {station_upstream} va {station_downstream}",
        )
        self.alerts_history.append(record)

    def write_csv(self, filename: str = "visualizer_alerts.csv") -> Path:
        """Export all recorded alerts to CSV for Member 4 & 5 report analysis."""
        dest = self.output_dir / filename
        with dest.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.CSV_FIELDS)
            writer.writeheader()
            for rec in self.alerts_history:
                writer.writerow({
                    "sim_time_s": rec.sim_time,
                    "wall_time": rec.wall_time,
                    "station_upstream": rec.station_upstream,
                    "station_downstream": rec.station_downstream,
                    "position_start_m": rec.position_start_m,
                    "position_end_m": rec.position_end_m,
                    "vehicle_id": rec.vehicle_id,
                    "docc_diff": rec.docc,
                    "occrdf_ratio": rec.occrdf,
                    "severity": rec.severity,
                    "status": rec.status,
                    "description": rec.description,
                })
        return dest
