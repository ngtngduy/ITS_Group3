"""Main Integration Pipeline for ITS_Group3 Highway AID Project.

Author: Thanh vien 5 (Integration & Visualization Lead)
Role:
    - Coordinates and integrates modules from Member 1, Member 2, Member 3, and Member 4.
    - Manages real-time simulation step execution via TraCI.
    - Synchronizes incident injection, detector occupancy reading, California #7 algorithm,
      visual alerts (Visualizer in GUI and Console), and quantitative metrics logging.

Usage:
    python main.py --scenario k1
    python main.py --scenario k2 --gui
    python main.py --scenario k3
    python main.py --scenario all
"""
from __future__ import annotations

import argparse
import csv
import os
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

# Ensure project directory is in python search path
PROJECT_DIR = Path(__file__).resolve().parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

# Import Member 2 modules
from incident_injector import IncidentConfig, IncidentInjector
from sumo_connector import SCENARIOS, ScenarioSpec, load_traci, resolve_sumo_binary

# Import Member 5 module
from visualizer import Visualizer, Style


# ==============================================================================
# FALLBACK ALGORITHM INTERFACE (Member 3 - California #7 Detector)
# If california_algo.py exists in repo, use it. Otherwise use built-in reference.
# ==============================================================================
try:
    from california_algo import CaliforniaDetector  # type: ignore
except ImportError:
    class CaliforniaDetector:
        """Reference implementation of California Algorithm #7 with Persistence Test.

        Matches exact specifications assigned to Member 3:
            Thresholds: T1 = 8.0%, T2 = 0.39, T3 = 9.0%
            Persistence Test: P = 2 consecutive intervals
        """
        def __init__(self, t1: float = 8.0, t2: float = 0.39, t3: float = 9.0, persistence_p: int = 2) -> None:
            self.t1 = t1
            self.t2 = t2
            self.t3 = t3
            self.persistence_p = persistence_p
            # State tracking: {pair_index: consecutive_positive_count}
            self.consecutive_counts: dict[int, int] = {}
            self.confirmed_incidents: set[int] = set()

        def evaluate_pair(self, pair_idx: int, occ_upstream: float, occ_downstream: float) -> tuple[bool, bool, float, float]:
            """Check California #7 conditions for a detector pair (i, i+1).

            Returns:
                (is_suspected, is_confirmed, docc, occrdf)
            """
            # 1. Absolute occupancy difference
            docc = occ_upstream - occ_downstream
            # 2. Relative occupancy difference
            occrdf = (docc / occ_upstream) if occ_upstream > 1e-4 else 0.0

            # California #7 criteria:
            # Cond 1: DOCC > T1
            # Cond 2: OCCRDF > T2
            # Cond 3: occ_downstream < T3
            is_suspected = (docc > self.t1) and (occrdf > self.t2) and (occ_downstream < self.t3)

            if is_suspected:
                self.consecutive_counts[pair_idx] = self.consecutive_counts.get(pair_idx, 0) + 1
            else:
                self.consecutive_counts[pair_idx] = max(0, self.consecutive_counts.get(pair_idx, 0) - 1)
                if self.consecutive_counts[pair_idx] == 0:
                    self.confirmed_incidents.discard(pair_idx)

            is_confirmed = self.consecutive_counts.get(pair_idx, 0) >= self.persistence_p
            if is_confirmed:
                self.confirmed_incidents.add(pair_idx)

            return is_suspected, is_confirmed, docc, occrdf


# ==============================================================================
# PIPELINE RUNNER
# ==============================================================================
STATION_POSITIONS = {
    "S1": 500.0,
    "S2": 1000.0,
    "S3": 1500.0,
    "S4": 2000.0,
    "S5": 2500.0,
    "S6": 3000.0,
    "S7": 3500.0,
}
STATION_KEYS = ["S1", "S2", "S3", "S4", "S5", "S6", "S7"]


def read_station_occupancies(traci: Any) -> dict[str, float]:
    """Read average occupancy (%) across 3 lanes for all 7 stations."""
    station_occ: dict[str, float] = {}
    for st in STATION_KEYS:
        total_occ = 0.0
        count = 0
        for lane_idx in range(3):
            det_id = f"{st}_L{lane_idx}"
            try:
                # getLastIntervalOccupancy returns 0.0 - 100.0
                val = float(traci.inductionloop.getLastIntervalOccupancy(det_id))
                total_occ += max(0.0, val)
                count += 1
            except Exception:
                continue
        station_occ[st] = (total_occ / count) if count > 0 else 0.0
    return station_occ


def run_pipeline(
    scenario_key: str,
    gui: bool = False,
    max_steps: int = 1500,
    output_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """Execute complete AID simulation pipeline for one scenario."""
    traci = load_traci()
    spec = SCENARIOS[scenario_key]
    out_dir = output_dir or (PROJECT_DIR / "output" / "integrated_run" / spec.scenario_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{Style.BOLD}{Style.CYAN}======================================================================{Style.RESET}")
    print(f"{Style.BOLD}KHOI DONG PIPELINE: {spec.title} (ID: {spec.scenario_id}){Style.RESET}")
    print(f"{Style.DIM}Config file: {spec.sumocfg_file} | GUI mode: {gui}{Style.RESET}")
    print(f"{Style.BOLD}{Style.CYAN}======================================================================{Style.RESET}\n")

    # Initialize submodules
    injector = IncidentInjector(spec.injector_config, scenario_id=spec.scenario_id) if spec.injector_config else None
    detector = CaliforniaDetector(t1=8.0, t2=0.39, t3=9.0, persistence_p=2)
    visualizer = Visualizer(output_dir=out_dir, enable_gui_effects=gui)

    binary = resolve_sumo_binary(gui=gui)
    sumo_cmd = [
        binary,
        "-c", str(PROJECT_DIR / spec.sumocfg_file),
        "--no-step-log", "true",
        "--duration-log.disable", "true",
        "--seed", str(spec.seed_offset),
    ]

    traci.start(sumo_cmd)
    sim_results_file = out_dir / "simulation_results.csv"
    results_records: list[dict[str, Any]] = []

    first_alert_sim_time: Optional[float] = None
    incident_start_sim_time: Optional[float] = None
    incident_veh_id: Optional[str] = None

    try:
        step = 0
        sampling_interval = 30  # evaluate algorithm every 30s as configured by Member 1
        active_alert_reported = False

        while step < max_steps and traci.simulation.getMinExpectedNumber() > 0:
            traci.simulationStep()
            sim_time = float(traci.simulation.getTime())

            # 1. Step Member 2's Incident Injector
            if injector:
                injector.step(traci, sim_time)
                if injector.is_active and incident_start_sim_time is None:
                    incident_start_sim_time = sim_time
                    incident_veh_id = injector._vehicle_id

            # 2. Periodic AID Evaluation (every 30s)
            if int(sim_time) % sampling_interval == 0 and sim_time > 0:
                station_occ = read_station_occupancies(traci)

                # Evaluate all 6 adjacent station pairs (S1-S2, S2-S3, ..., S6-S7)
                for pair_idx in range(len(STATION_KEYS) - 1):
                    up_st = STATION_KEYS[pair_idx]
                    down_st = STATION_KEYS[pair_idx + 1]
                    occ_up = station_occ.get(up_st, 0.0)
                    occ_down = station_occ.get(down_st, 0.0)

                    is_susp, is_conf, docc, occrdf = detector.evaluate_pair(pair_idx, occ_up, occ_down)

                    # If confirmed incident detected
                    if is_conf and not active_alert_reported:
                        first_alert_sim_time = sim_time
                        active_alert_reported = True

                        pos_range = (STATION_POSITIONS[up_st], STATION_POSITIONS[down_st])

                        # A. Highlight vehicle in RED in SUMO-GUI
                        if incident_veh_id:
                            visualizer.highlight_incident_vehicle(traci, incident_veh_id)

                        # B. Print prominent formatted alert to Console
                        visualizer.log_incident_console(
                            sim_time=sim_time,
                            station_upstream=up_st,
                            station_downstream=down_st,
                            position_range=pos_range,
                            vehicle_id=incident_veh_id,
                            docc=docc,
                            occrdf=occrdf,
                            severity="CRITICAL",
                            is_confirmed=True,
                        )

                    # Record step log for Member 4
                    results_records.append({
                        "sim_time": sim_time,
                        "pair": f"{up_st}-{down_st}",
                        "occ_upstream": f"{occ_up:.2f}",
                        "occ_downstream": f"{occ_down:.2f}",
                        "docc": f"{docc:.2f}",
                        "occrdf": f"{occrdf:.2f}",
                        "suspected": is_susp,
                        "confirmed": is_conf,
                        "incident_active": injector.is_active if injector else False,
                    })

            step += 1

        if injector:
            injector.finalize(traci, float(traci.simulation.getTime()))

    finally:
        traci.close()

    # Export records
    visualizer.write_csv("visualizer_alerts.csv")

    with sim_results_file.open("w", newline="", encoding="utf-8-sig") as f:
        if results_records:
            writer = csv.DictWriter(f, fieldnames=list(results_records[0].keys()))
            writer.writeheader()
            writer.writerows(results_records)

    # Compute key metrics summary
    mttd = (first_alert_sim_time - incident_start_sim_time) if (first_alert_sim_time and incident_start_sim_time) else None
    print(f"\n{Style.BOLD}{Style.GREEN}=== HOAN THANH MO PHONG: {spec.scenario_id} ==={Style.RESET}")
    print(f"- File ket qua : {sim_results_file}")
    print(f"- Su co bat dau: {incident_start_sim_time}s" if incident_start_sim_time else "- Su co: Khong tiem (Baseline)")
    print(f"- Phat hien luc: {first_alert_sim_time}s" if first_alert_sim_time else "- Phat hien: Khong co bao dong")
    if mttd is not None:
        print(f"- {Style.BOLD}Thoi gian phat hien (MTTD): {mttd:.1f} giay (Xuat sac!){Style.RESET}")
    print("======================================================================\n")

    return {
        "scenario_id": spec.scenario_id,
        "incident_start": incident_start_sim_time,
        "first_alert": first_alert_sim_time,
        "mttd_seconds": mttd,
        "results_file": str(sim_results_file),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="ITS_Group3 Main Integration Pipeline (Thanh vien 5)")
    parser.add_argument(
        "--scenario",
        choices=["all", "k1", "k2", "k3"],
        default="k1",
        help="Kich ban can chay (k1: Thua + Su co, k2: Dong + Su co, k3: Dong binh thuong, all: Chay ca 3)",
    )
    parser.add_argument("--gui", action="store_true", help="Chay voi giao dien SUMO-GUI")
    parser.add_argument("--duration", type=int, default=1200, help="So buoc mo phong (default: 1200s)")

    args = parser.parse_args()

    # Ensure SUMO environment
    load_traci()

    scenarios_to_run = ["k1", "k2", "k3"] if args.scenario == "all" else [args.scenario]
    for sc in scenarios_to_run:
        run_pipeline(sc, gui=args.gui, max_steps=args.duration)


if __name__ == "__main__":
    main()
