"""SUMO/TraCI runner for the three Member-2 experimental scenarios.

Run from the repository root or execute this file directly:
    python sumo_connector.py --scenario all
    python sumo_connector.py --scenario all --gui

The original Member-1 network, route, detector and sumocfg files are read-only
inputs. A scenario-specific additional file is generated so detector XML output
is written into the matching output/<scenario_id>/ directory.
"""
from __future__ import annotations

import argparse
import csv
import importlib
import json
import os
import shutil
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Optional

from incident_injector import IncidentConfig, IncidentInjector

PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "output" / "member2"


@dataclass(frozen=True)
class ScenarioSpec:
    scenario_id: str
    title: str
    sumocfg_file: str
    route_file: str
    injector_config: Optional[IncidentConfig]
    seed_offset: int


@dataclass
class RunResult:
    scenario_id: str
    title: str
    seed: int
    output_dir: str
    simulated_seconds: float
    simulation_steps: int
    wall_time_seconds: float
    incident_status: str
    detector_output_files: list[str]


SCENARIOS: dict[str, ScenarioSpec] = {
    "k1": ScenarioSpec(
        scenario_id="K1_sparse_with_incident",
        title="Mat do thap + tiem su co dung xe",
        sumocfg_file="highway_sparse.sumocfg",
        route_file="highway_sparse.rou.xml",
        injector_config=IncidentConfig(seed=42),
        seed_offset=0,
    ),
    "k2": ScenarioSpec(
        scenario_id="K2_dense_with_incident",
        title="Mat do cao + tiem su co dung xe",
        sumocfg_file="highway_dense.sumocfg",
        route_file="highway_dense.rou.xml",
        injector_config=IncidentConfig(seed=43),
        seed_offset=1,
    ),
    "k3": ScenarioSpec(
        scenario_id="K3_dense_without_incident",
        title="Mat do cao tu nhien + khong tiem su co",
        sumocfg_file="highway_dense.sumocfg",
        route_file="highway_dense.rou.xml",
        injector_config=None,
        seed_offset=1,
    ),
}


def load_traci() -> Any:
    """Import TraCI from pip or from the SUMO_HOME/tools directory."""
    sumo_home = os.environ.get("SUMO_HOME")
    if sumo_home:
        tools_dir = str(Path(sumo_home) / "tools")
        if tools_dir not in sys.path:
            sys.path.append(tools_dir)
    try:
        return importlib.import_module("traci")
    except ImportError as exc:
        raise RuntimeError(
            "Khong tim thay thu vien TraCI. Hay cai SUMO, dat bien SUMO_HOME "
            "va dam bao <SUMO_HOME>/tools nam trong Python path; hoac chay "
            "'pip install traci'."
        ) from exc


def resolve_sumo_binary(gui: bool, explicit_binary: Optional[str] = None) -> str:
    """Find SUMO or SUMO-GUI executable without hard-coding an OS path."""
    if explicit_binary:
        candidate = Path(explicit_binary)
        if candidate.exists():
            return str(candidate.resolve())
        found = shutil.which(explicit_binary)
        if found:
            return found
        raise FileNotFoundError(f"Khong tim thay SUMO binary: {explicit_binary}")

    binary_name = "sumo-gui" if gui else "sumo"
    found = shutil.which(binary_name)
    if found:
        return found

    sumo_home = os.environ.get("SUMO_HOME")
    if sumo_home:
        suffix = ".exe" if os.name == "nt" else ""
        candidate = Path(sumo_home) / "bin" / f"{binary_name}{suffix}"
        if candidate.exists():
            return str(candidate)
    raise FileNotFoundError(
        f"Khong tim thay {binary_name}. Hay cai SUMO va them thu muc bin vao PATH."
    )


def _read_sumocfg(source: Path) -> tuple[float, float, str]:
    """Read begin/end/step-length from Member-1's existing SUMO config."""
    if not source.exists():
        raise FileNotFoundError(f"Khong tim thay file SUMO config: {source}")
    root = ET.parse(source).getroot()
    time_node = root.find("time")
    begin = float(time_node.find("begin").get("value", "0")) if time_node is not None and time_node.find("begin") is not None else 0.0
    end = float(time_node.find("end").get("value", "3600")) if time_node is not None and time_node.find("end") is not None else 3600.0
    step = time_node.find("step-length").get("value", "1") if time_node is not None and time_node.find("step-length") is not None else "1"
    return begin, end, step


def prepare_scenario_files(
    spec: ScenarioSpec,
    scenario_output_dir: Path,
) -> Path:
    """Create an isolated .add.xml and .sumocfg for this run.

    This prevents E1 outputs from K1/K2/K3 overwriting each other and leaves
    all Member-1 source files unchanged.
    """
    scenario_output_dir.mkdir(parents=True, exist_ok=True)
    source_cfg = PROJECT_DIR / spec.sumocfg_file
    begin, end, step_length = _read_sumocfg(source_cfg)
    network = PROJECT_DIR / "highway.net.xml"
    route_file = PROJECT_DIR / spec.route_file
    additional_file = PROJECT_DIR / "highway.add.xml"
    for required in (network, route_file, additional_file):
        if not required.exists():
            raise FileNotFoundError(f"Thieu file mo hinh cua Thanh vien 1: {required.name}")

    add_root = ET.parse(additional_file).getroot()
    for detector in add_root.findall("inductionLoop"):
        original_name = Path(detector.get("file", "detector.xml")).name
        detector.set("file", os.path.relpath(scenario_output_dir / original_name, scenario_output_dir).replace("\\", "/"))
    scenario_add = scenario_output_dir / "member2_highway.add.xml"
    ET.ElementTree(add_root).write(scenario_add, encoding="utf-8", xml_declaration=True)

    config_root = ET.Element("configuration")
    input_node = ET.SubElement(config_root, "input")
    ET.SubElement(input_node, "net-file", {"value": os.path.relpath(network, scenario_output_dir).replace("\\", "/")})
    ET.SubElement(input_node, "route-files", {"value": os.path.relpath(route_file, scenario_output_dir).replace("\\", "/")})
    ET.SubElement(input_node, "additional-files", {"value": os.path.relpath(scenario_add, scenario_output_dir).replace("\\", "/")})
    
    time_node = ET.SubElement(config_root, "time")
    ET.SubElement(time_node, "begin", {"value": str(begin)})
    ET.SubElement(time_node, "end", {"value": str(end)})
    ET.SubElement(time_node, "step-length", {"value": str(step_length)})
    
    report_node = ET.SubElement(config_root, "report")
    ET.SubElement(report_node, "no-step-log", {"value": "true"})

    run_cfg = scenario_output_dir / "member2_run.sumocfg"
    ET.ElementTree(config_root).write(run_cfg, encoding="utf-8", xml_declaration=True)
    return run_cfg


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_scenario(
    spec: ScenarioSpec,
    *,
    gui: bool = False,
    seed: int = 42,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    sumo_binary: Optional[str] = None,
    step_callback: Optional[Callable[[float, Any], None]] = None,
) -> RunResult:
    """Run one scenario, advancing SUMO one step at a time via TraCI.

    ``step_callback(sim_time, traci_connection)`` is an integration hook for
    Member 3's California #7 detector/algorithm module and Member 4's logger.
    The callback is deliberately optional so this module can be tested alone.
    """
    traci = load_traci()
    binary = resolve_sumo_binary(gui, sumo_binary)
    scenario_output = output_dir / spec.scenario_id
    run_cfg = prepare_scenario_files(spec, scenario_output)
    scenario_seed = seed + spec.seed_offset
    # Sửa lại đoạn khởi tạo incident_config:
    incident_config = (
    replace(spec.injector_config, seed=scenario_seed)
    if spec.injector_config is not None and getattr(spec.injector_config, "enabled", True) else None
)

    # Và ở phần tạo incident, bọc thêm điều kiện kiểm tra:
    incident = (
    IncidentInjector(incident_config, scenario_id=spec.scenario_id)
    if incident_config is not None and getattr(incident_config, "enabled", True) else None
)

    command = [binary, "-c", str(run_cfg), "--seed", str(scenario_seed)]
    if gui:
        command.extend(["--start", "--quit-on-end"])

    started_at = time.perf_counter()
    simulation_steps = 0
    simulated_seconds = 0.0
    connection = None
    try:
        traci.start(command)
        connection = traci
        while connection.simulation.getMinExpectedNumber() > 0:
            connection.simulationStep()
            simulated_seconds = float(connection.simulation.getTime())
            simulation_steps += 1
            if incident is not None:
                incident.step(connection, simulated_seconds)
            if step_callback is not None:
                step_callback(simulated_seconds, connection)

        if incident is not None:
            incident.finalize(connection, simulated_seconds)
    finally:
        # Write available incident state even when the simulation or a
        # downstream callback raises an exception.
        if incident is not None:
            # Finalize on success and on exceptions so an active vehicle is
            # released and the incident attempt is recorded before closing TraCI.
            incident.finalize(connection if connection is not None else traci, simulated_seconds)
            incident.write_csv(scenario_output / "incident_events.csv")
            incident_summary = incident.summary()
            incident_status = incident.status
        else:
            incident_status = "not_configured"
            incident_summary = {
                "scenario_id": spec.scenario_id,
                "status": "not_configured",
                "message": "Kich ban doi chung: khong tiem su co.",
            }
            # Keep the same CSV schema in the control scenario so downstream
            # modules can read all three scenarios with one parser.
            empty_event_file = scenario_output / "incident_events.csv"
            with empty_event_file.open("w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.DictWriter(handle, fieldnames=IncidentInjector.CSV_FIELDS)
                writer.writeheader()
        _write_json(scenario_output / "incident_summary.json", incident_summary)
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass

    wall_time = time.perf_counter() - started_at
    detector_files = sorted(str(p) for p in scenario_output.glob("e1_*.xml"))
    result = RunResult(
        scenario_id=spec.scenario_id,
        title=spec.title,
        seed=scenario_seed,
        output_dir=str(scenario_output),
        simulated_seconds=simulated_seconds,
        simulation_steps=simulation_steps,
        wall_time_seconds=wall_time,
        incident_status=incident_status,
        detector_output_files=detector_files,
    )
    _write_json(scenario_output / "run_summary.json", result.__dict__)
    return result


def run_experiments(
    scenario_keys: list[str],
    *,
    gui: bool = False,
    seed: int = 42,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    sumo_binary: Optional[str] = None,
) -> list[RunResult]:
    results: list[RunResult] = []
    for key in scenario_keys:
        if key not in SCENARIOS:
            raise ValueError(f"Ma kich ban khong hop le: {key}")
        spec = SCENARIOS[key]
        print(f"\n=== {spec.scenario_id}: {spec.title} ===")
        result = run_scenario(
            spec,
            gui=gui,
            seed=seed,
            output_dir=output_dir,
            sumo_binary=sumo_binary,
        )
        results.append(result)
        print(
            f"Hoan tat {result.scenario_id}: {result.simulation_steps} buoc, "
            f"{result.simulated_seconds:.0f} giay mo phong, "
            f"incident={result.incident_status}"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "member2_experiment_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8-sig") as handle:
        fieldnames = [
            "scenario_id", "title", "seed", "simulated_seconds", "simulation_steps",
            "wall_time_seconds", "incident_status", "output_dir",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in results:
            writer.writerow({key: getattr(item, key) for key in fieldnames})
    print(f"\nDa ghi tong hop kich ban: {summary_path}")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Chay 3 kich ban SUMO/TraCI cua Thanh vien 2")
    parser.add_argument("--scenario", choices=["all", *SCENARIOS.keys()], default="all")
    parser.add_argument("--gui", action="store_true", help="Mo SUMO-GUI de quan sat truc quan")
    parser.add_argument("--seed", type=int, default=42, help="Random seed co the lap lai")
    parser.add_argument("--sumo-binary", default=None, help="Duong dan tuy chon den sumo/sumo-gui")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    keys = list(SCENARIOS) if args.scenario == "all" else [args.scenario]
    try:
        run_experiments(
            keys,
            gui=args.gui,
            seed=args.seed,
            output_dir=args.output_dir,
            sumo_binary=args.sumo_binary,
        )
    except Exception as exc:
        print(f"LOI: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
