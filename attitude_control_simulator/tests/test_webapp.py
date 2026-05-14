from webapp import app


def test_presets_endpoint_returns_vehicles_and_scenarios() -> None:
    client = app.test_client()
    response = client.get("/api/presets")

    assert response.status_code == 200
    payload = response.get_json()
    assert "vehicles" in payload
    assert "spacecraft" in payload["vehicles"]
    assert "scenarios" in payload
    assert "track_moving_target" in payload["scenarios"]


def test_simulate_endpoint_returns_results_and_comparison() -> None:
    client = app.test_client()
    response = client.post(
        "/api/simulate",
        json={
            "vehicle": "spacecraft",
            "scenario": "disturbance_rejection",
            "controller": "both",
            "duration": 8.0,
            "dt": 0.02,
            "initial_deg": [20.0, -10.0, 30.0],
            "target_deg": [0.0, 0.0, 0.0],
            "initial_rates_deg_s": [0.0, 0.0, 0.0],
            "disturbance_torque": [0.6, -0.3, 0.2],
            "disturbance_window_s": [1.5, 3.0],
            "sensor_angle_noise_deg": 0.1,
            "sensor_rate_noise_deg_s": 0.25,
            "inertia_uncertainty_pct": 2.0,
            "damping_uncertainty_pct": 2.0,
            "actuator_time_constant_s": 0.2,
            "measurement_seed": 7,
            "auto_tune": True,
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert set(payload["results"]) == {"pid", "lqr"}
    assert payload["comparison"]["winner"] in {"pid", "lqr"}
    assert payload["results"]["pid"]["samples"]
