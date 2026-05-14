from pathlib import Path

from simulator import (
    SimulationConfig,
    compare_results,
    run_simulation,
    save_report_bundle,
)


def test_pid_spacecraft_stabilizes_default_case() -> None:
    config = SimulationConfig(vehicle="spacecraft", duration=15.0)
    result = run_simulation(config, "pid")["pid"]

    assert max(abs(value) for value in result.summary.final_error_deg) < 1.2
    assert result.summary.settling_time_s is not None
    assert result.summary.settling_time_s < 15.0
    assert result.summary.score > 45.0


def test_lqr_uav_tracking_remains_bounded() -> None:
    config = SimulationConfig(vehicle="uav", scenario="track_moving_target", duration=18.0)
    result = run_simulation(config, "lqr")["lqr"]

    assert max(abs(value) for value in result.summary.final_error_deg) < 5.0
    assert result.summary.score > 55.0


def test_both_mode_returns_comparison_summary() -> None:
    config = SimulationConfig(vehicle="spacecraft", scenario="disturbance_rejection", duration=18.0)
    results = run_simulation(config, "both")
    comparison = compare_results(results)

    assert set(results) == {"pid", "lqr"}
    assert comparison is not None
    assert comparison["winner"] in {"pid", "lqr"}
    assert comparison["score_gap"] >= 0.0


def test_report_bundle_writes_expected_files(tmp_path: Path) -> None:
    config = SimulationConfig(vehicle="spacecraft", scenario="disturbance_rejection", duration=10.0)
    results = run_simulation(config, "both")
    report_folder = save_report_bundle(results, config, root=tmp_path)

    assert (report_folder / "results.csv").exists()
    assert (report_folder / "response.png").exists()
    assert (report_folder / "summary.json").exists()
    assert (report_folder / "summary.txt").exists()
