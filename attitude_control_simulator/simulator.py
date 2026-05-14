from __future__ import annotations

import argparse
import csv
import json
import math
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Literal, Sequence, Tuple

import numpy as np


Vector3 = Tuple[float, float, float]
Quaternion = Tuple[float, float, float, float]
ControllerName = Literal["pid", "lqr"]
VehicleName = Literal["spacecraft", "uav"]
ScenarioName = Literal["custom", "recover_from_tumble", "track_moving_target", "disturbance_rejection"]
ActuatorName = Literal["reaction_wheels", "quad_motors"]


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def clamp_tuple(values: Sequence[float], limits: Sequence[float]) -> Vector3:
    return tuple(clamp(values[index], -limits[index], limits[index]) for index in range(3))  # type: ignore[return-value]


def add(a: Sequence[float], b: Sequence[float]) -> Vector3:
    return tuple(a[index] + b[index] for index in range(3))  # type: ignore[return-value]


def sub(a: Sequence[float], b: Sequence[float]) -> Vector3:
    return tuple(a[index] - b[index] for index in range(3))  # type: ignore[return-value]


def mul(a: Sequence[float], scalar: float) -> Vector3:
    return tuple(a[index] * scalar for index in range(3))  # type: ignore[return-value]


def hadamard(a: Sequence[float], b: Sequence[float]) -> Vector3:
    return tuple(a[index] * b[index] for index in range(3))  # type: ignore[return-value]


def cross(a: Sequence[float], b: Sequence[float]) -> Vector3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def vector_norm(values: Iterable[float]) -> float:
    return math.sqrt(sum(value * value for value in values))


def max_abs(values: Iterable[float]) -> float:
    return max(abs(value) for value in values)


def wrap_angle_radians(angle: float) -> float:
    return (angle + math.pi) % (2.0 * math.pi) - math.pi


def wrapped_error_deg(target_deg: Sequence[float], actual_deg: Sequence[float]) -> Vector3:
    return tuple(
        math.degrees(wrap_angle_radians(math.radians(target_deg[index] - actual_deg[index])))
        for index in range(3)
    )  # type: ignore[return-value]


def degrees_tuple(values: Sequence[float]) -> Vector3:
    return tuple(math.degrees(value) for value in values)  # type: ignore[return-value]


def radians_tuple(values: Sequence[float]) -> Vector3:
    return tuple(math.radians(value) for value in values)  # type: ignore[return-value]


def parse_vector(argument: str) -> Vector3:
    parts = [part.strip() for part in argument.split(",")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("Expected three comma-separated values, like 20,-10,35")
    try:
        return tuple(float(part) for part in parts)  # type: ignore[return-value]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("All vector values must be numbers") from exc


def parse_window(argument: str) -> Tuple[float, float]:
    parts = [part.strip() for part in argument.split(",")]
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("Expected start,end window values in seconds, like 2.0,4.5")
    try:
        start_s, end_s = (float(part) for part in parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Window values must be numbers") from exc
    if end_s <= start_s:
        raise argparse.ArgumentTypeError("Window end must be greater than start")
    return (start_s, end_s)


def quat_normalize(quaternion: Sequence[float]) -> Quaternion:
    magnitude = math.sqrt(sum(component * component for component in quaternion))
    if magnitude <= 1e-12:
        return (1.0, 0.0, 0.0, 0.0)
    return tuple(component / magnitude for component in quaternion)  # type: ignore[return-value]


def quat_conjugate(quaternion: Sequence[float]) -> Quaternion:
    return (quaternion[0], -quaternion[1], -quaternion[2], -quaternion[3])


def quat_multiply(a: Sequence[float], b: Sequence[float]) -> Quaternion:
    return (
        a[0] * b[0] - a[1] * b[1] - a[2] * b[2] - a[3] * b[3],
        a[0] * b[1] + a[1] * b[0] + a[2] * b[3] - a[3] * b[2],
        a[0] * b[2] - a[1] * b[3] + a[2] * b[0] + a[3] * b[1],
        a[0] * b[3] + a[1] * b[2] - a[2] * b[1] + a[3] * b[0],
    )


def quat_from_euler_deg(euler_deg: Sequence[float]) -> Quaternion:
    roll, pitch, yaw = (math.radians(value) for value in euler_deg)
    cr = math.cos(roll * 0.5)
    sr = math.sin(roll * 0.5)
    cp = math.cos(pitch * 0.5)
    sp = math.sin(pitch * 0.5)
    cy = math.cos(yaw * 0.5)
    sy = math.sin(yaw * 0.5)
    return quat_normalize(
        (
            cr * cp * cy + sr * sp * sy,
            sr * cp * cy - cr * sp * sy,
            cr * sp * cy + sr * cp * sy,
            cr * cp * sy - sr * sp * cy,
        )
    )


def quat_to_euler_deg(quaternion: Sequence[float]) -> Vector3:
    w, x, y, z = quat_normalize(quaternion)

    sinr_cosp = 2.0 * (w * x + y * z)
    cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
    roll = math.atan2(sinr_cosp, cosr_cosp)

    sinp = 2.0 * (w * y - z * x)
    sinp = clamp(sinp, -1.0, 1.0)
    pitch = math.asin(sinp)

    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    yaw = math.atan2(siny_cosp, cosy_cosp)

    return degrees_tuple((roll, pitch, yaw))


def quat_to_rotation_matrix(quaternion: Sequence[float]) -> Tuple[Tuple[float, float, float], ...]:
    w, x, y, z = quat_normalize(quaternion)
    return (
        (1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - z * w), 2.0 * (x * z + y * w)),
        (2.0 * (x * y + z * w), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - x * w)),
        (2.0 * (x * z - y * w), 2.0 * (y * z + x * w), 1.0 - 2.0 * (x * x + y * y)),
    )


def quat_error_vector(target: Sequence[float], actual: Sequence[float]) -> Vector3:
    error_quaternion = quat_normalize(quat_multiply(target, quat_conjugate(actual)))
    if error_quaternion[0] < 0.0:
        error_quaternion = tuple(-component for component in error_quaternion)  # type: ignore[assignment]

    vector_part = error_quaternion[1:]
    sin_half_angle = vector_norm(vector_part)
    if sin_half_angle <= 1e-8:
        return tuple(2.0 * component for component in vector_part)  # type: ignore[return-value]

    angle = 2.0 * math.atan2(sin_half_angle, clamp(error_quaternion[0], -1.0, 1.0))
    axis = tuple(component / sin_half_angle for component in vector_part)
    return tuple(axis[index] * angle for index in range(3))  # type: ignore[return-value]


def integrate_quaternion(quaternion: Sequence[float], body_rates: Sequence[float], dt: float) -> Quaternion:
    rate_quaternion = (0.0, body_rates[0], body_rates[1], body_rates[2])
    quaternion_dot = quat_multiply(quaternion, rate_quaternion)
    next_quaternion = tuple(
        quaternion[index] + 0.5 * quaternion_dot[index] * dt for index in range(4)
    )
    return quat_normalize(next_quaternion)


@dataclass(frozen=True)
class VehiclePreset:
    name: VehicleName
    label: str
    description: str
    actuator_name: ActuatorName
    inertia: Vector3
    rotational_damping: Vector3
    torque_limit: Vector3
    rate_limit_deg_s: float
    default_initial_deg: Vector3
    default_target_deg: Vector3
    default_initial_rates_deg_s: Vector3
    sensor_angle_noise_deg: float
    sensor_rate_noise_deg_s: float
    actuator_time_constant_s: float
    actuator_capacity: Tuple[float, ...]


@dataclass(frozen=True)
class ScenarioPreset:
    name: ScenarioName
    label: str
    description: str
    duration_s: float
    initial_deg: Vector3
    initial_rates_deg_s: Vector3
    target_deg: Vector3
    disturbance_torque: Vector3
    disturbance_window_s: Tuple[float, float] | None
    target_mode: Literal["hold", "track"]


VEHICLE_PRESETS: Dict[VehicleName, VehiclePreset] = {
    "spacecraft": VehiclePreset(
        name="spacecraft",
        label="Spacecraft",
        description="Reaction-wheel stabilized spacecraft with slower rotational response and stored momentum limits.",
        actuator_name="reaction_wheels",
        inertia=(10.0, 8.0, 12.0),
        rotational_damping=(0.12, 0.10, 0.16),
        torque_limit=(18.0, 18.0, 14.0),
        rate_limit_deg_s=140.0,
        default_initial_deg=(35.0, -20.0, 55.0),
        default_target_deg=(0.0, 0.0, 0.0),
        default_initial_rates_deg_s=(0.0, 0.0, 0.0),
        sensor_angle_noise_deg=0.12,
        sensor_rate_noise_deg_s=0.25,
        actuator_time_constant_s=0.20,
        actuator_capacity=(20.0, 20.0, 16.0),
    ),
    "uav": VehiclePreset(
        name="uav",
        label="UAV",
        description="Quad-motor aerial vehicle with faster response, motor lag, and rate-heavy stabilization.",
        actuator_name="quad_motors",
        inertia=(0.9, 1.1, 1.4),
        rotational_damping=(0.55, 0.60, 0.70),
        torque_limit=(6.0, 6.5, 5.0),
        rate_limit_deg_s=260.0,
        default_initial_deg=(18.0, -12.0, 24.0),
        default_target_deg=(0.0, 0.0, 0.0),
        default_initial_rates_deg_s=(0.0, 0.0, 0.0),
        sensor_angle_noise_deg=0.18,
        sensor_rate_noise_deg_s=0.45,
        actuator_time_constant_s=0.08,
        actuator_capacity=(1.0, 1.0, 1.0, 1.0),
    ),
}


SCENARIO_PRESETS: Dict[ScenarioName, ScenarioPreset] = {
    "custom": ScenarioPreset(
        name="custom",
        label="Custom",
        description="Manual scenario where the dashboard values drive the simulation.",
        duration_s=15.0,
        initial_deg=(0.0, 0.0, 0.0),
        initial_rates_deg_s=(0.0, 0.0, 0.0),
        target_deg=(0.0, 0.0, 0.0),
        disturbance_torque=(0.0, 0.0, 0.0),
        disturbance_window_s=None,
        target_mode="hold",
    ),
    "recover_from_tumble": ScenarioPreset(
        name="recover_from_tumble",
        label="Recover From Tumble",
        description="High-angle recovery with large initial body rates and a hold altitude target.",
        duration_s=20.0,
        initial_deg=(120.0, -70.0, 150.0),
        initial_rates_deg_s=(35.0, -25.0, 45.0),
        target_deg=(0.0, 0.0, 0.0),
        disturbance_torque=(0.0, 0.0, 0.0),
        disturbance_window_s=None,
        target_mode="hold",
    ),
    "track_moving_target": ScenarioPreset(
        name="track_moving_target",
        label="Track Moving Target",
        description="Continuously track a moving altitude reference instead of settling to one fixed pose.",
        duration_s=18.0,
        initial_deg=(0.0, 0.0, 0.0),
        initial_rates_deg_s=(0.0, 0.0, 0.0),
        target_deg=(0.0, 0.0, 0.0),
        disturbance_torque=(0.0, 0.0, 0.0),
        disturbance_window_s=None,
        target_mode="track",
    ),
    "disturbance_rejection": ScenarioPreset(
        name="disturbance_rejection",
        label="Disturbance Rejection",
        description="Hold altitude while rejecting an external disturbance pulse.",
        duration_s=18.0,
        initial_deg=(20.0, -10.0, 25.0),
        initial_rates_deg_s=(0.0, 0.0, 0.0),
        target_deg=(0.0, 0.0, 0.0),
        disturbance_torque=(0.8, -0.5, 0.3),
        disturbance_window_s=(2.0, 5.0),
        target_mode="hold",
    ),
}


@dataclass
class PIDAxis:
    kp: float
    ki: float
    kd: float
    integral_limit: float
    output_limit: float
    integral: float = 0.0

    def update(self, error: float, measured_rate: float, dt: float) -> float:
        self.integral = clamp(self.integral + error * dt, -self.integral_limit, self.integral_limit)
        output = self.kp * error + self.ki * self.integral - self.kd * measured_rate
        return clamp(output, -self.output_limit, self.output_limit)


@dataclass
class PIDController3Axis:
    roll: PIDAxis
    pitch: PIDAxis
    yaw: PIDAxis

    def update(self, attitude_error: Vector3, body_rates: Vector3, dt: float) -> Vector3:
        return (
            self.roll.update(attitude_error[0], body_rates[0], dt),
            self.pitch.update(attitude_error[1], body_rates[1], dt),
            self.yaw.update(attitude_error[2], body_rates[2], dt),
        )


@dataclass
class LQRAxis:
    gain_angle: float
    gain_rate: float
    output_limit: float

    def update(self, error: float, measured_rate: float) -> float:
        output = -(self.gain_angle * error + self.gain_rate * measured_rate)
        return clamp(output, -self.output_limit, self.output_limit)


@dataclass
class LQRController3Axis:
    roll: LQRAxis
    pitch: LQRAxis
    yaw: LQRAxis

    def update(self, attitude_error: Vector3, body_rates: Vector3, dt: float) -> Vector3:
        del dt
        return (
            self.roll.update(attitude_error[0], body_rates[0]),
            self.pitch.update(attitude_error[1], body_rates[1]),
            self.yaw.update(attitude_error[2], body_rates[2]),
        )


@dataclass
class RigidBodyState:
    quaternion: Quaternion
    body_rates: Vector3


@dataclass
class ReactionWheelState:
    wheel_torque: Vector3 = (0.0, 0.0, 0.0)
    wheel_momentum: Vector3 = (0.0, 0.0, 0.0)


@dataclass
class QuadMotorState:
    motor_levels: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)


@dataclass
class SimulationConfig:
    vehicle: VehicleName = "spacecraft"
    scenario: ScenarioName = "custom"
    dt: float = 0.02
    duration: float | None = None
    inertia: Vector3 | None = None
    rotational_damping: Vector3 | None = None
    torque_limit: Vector3 | None = None
    initial_deg: Vector3 | None = None
    target_deg: Vector3 | None = None
    initial_rates_deg_s: Vector3 | None = None
    rate_limit: float | None = None
    disturbance_torque: Vector3 | None = None
    disturbance_window_s: Tuple[float, float] | None = None
    sensor_angle_noise_deg: float | None = None
    sensor_rate_noise_deg_s: float | None = None
    inertia_uncertainty_pct: float = 0.0
    damping_uncertainty_pct: float = 0.0
    actuator_time_constant_s: float | None = None
    measurement_seed: int = 7
    auto_tune: bool = True
    print_interval: float = 0.5

    def __post_init__(self) -> None:
        vehicle_preset = VEHICLE_PRESETS[self.vehicle]
        scenario_preset = SCENARIO_PRESETS[self.scenario]

        if self.inertia is None:
            self.inertia = vehicle_preset.inertia
        if self.rotational_damping is None:
            self.rotational_damping = vehicle_preset.rotational_damping
        if self.torque_limit is None:
            self.torque_limit = vehicle_preset.torque_limit
        if self.initial_deg is None:
            self.initial_deg = (
                scenario_preset.initial_deg if self.scenario != "custom" else vehicle_preset.default_initial_deg
            )
        if self.target_deg is None:
            self.target_deg = scenario_preset.target_deg if self.scenario != "custom" else vehicle_preset.default_target_deg
        if self.initial_rates_deg_s is None:
            self.initial_rates_deg_s = (
                scenario_preset.initial_rates_deg_s
                if self.scenario != "custom"
                else vehicle_preset.default_initial_rates_deg_s
            )
        if self.rate_limit is None:
            self.rate_limit = math.radians(vehicle_preset.rate_limit_deg_s)
        if self.duration is None:
            self.duration = scenario_preset.duration_s
        if self.disturbance_torque is None:
            self.disturbance_torque = scenario_preset.disturbance_torque
        if self.disturbance_window_s is None:
            self.disturbance_window_s = scenario_preset.disturbance_window_s
        if self.sensor_angle_noise_deg is None:
            self.sensor_angle_noise_deg = vehicle_preset.sensor_angle_noise_deg
        if self.sensor_rate_noise_deg_s is None:
            self.sensor_rate_noise_deg_s = vehicle_preset.sensor_rate_noise_deg_s
        if self.actuator_time_constant_s is None:
            self.actuator_time_constant_s = vehicle_preset.actuator_time_constant_s

    @property
    def vehicle_preset(self) -> VehiclePreset:
        return VEHICLE_PRESETS[self.vehicle]

    @property
    def scenario_preset(self) -> ScenarioPreset:
        return SCENARIO_PRESETS[self.scenario]


@dataclass
class Sample:
    time_s: float
    target_deg: Vector3
    attitude_deg: Vector3
    measured_attitude_deg: Vector3
    body_rates_deg_s: Vector3
    measured_rates_deg_s: Vector3
    torque_cmd: Vector3
    actuator_torque: Vector3
    disturbance_torque: Vector3
    error_deg: Vector3
    attitude_quat: Quaternion


@dataclass
class SimulationSummary:
    final_attitude_deg: Vector3
    final_error_deg: Vector3
    peak_error_deg: Vector3
    rms_error_deg: Vector3
    peak_body_rate_deg_s: Vector3
    max_torque_cmd: Vector3
    max_actuator_torque: Vector3
    control_effort: float
    settling_time_s: float | None
    score: float


@dataclass
class ControllerResult:
    controller: ControllerName
    vehicle: VehicleName
    scenario: ScenarioName
    samples: List[Sample]
    summary: SimulationSummary
    controller_details: Dict[str, object]
    notes: List[str] = field(default_factory=list)


def compute_scenario_severity(config: SimulationConfig) -> float:
    initial_error = vector_norm(sub(config.initial_deg, config.target_deg))
    initial_rate = vector_norm(config.initial_rates_deg_s)
    disturbance = vector_norm(config.disturbance_torque)
    uncertainty = config.inertia_uncertainty_pct + config.damping_uncertainty_pct
    tracking_bonus = 0.9 if config.scenario == "track_moving_target" else 0.0
    severity = (
        initial_error / 55.0
        + initial_rate / 40.0
        + disturbance / max(1.0, sum(config.torque_limit) / 3.0)
        + uncertainty / 40.0
        + config.sensor_angle_noise_deg / 1.2
        + tracking_bonus
    )
    return clamp(severity, 0.3, 3.5)


def axis_pid_from_dynamics(
    axis_inertia: float,
    axis_damping: float,
    output_limit: float,
    natural_frequency: float,
    damping_ratio: float,
    integral_ratio: float,
) -> PIDAxis:
    kp = axis_inertia * natural_frequency**2
    kd = max(0.05, 2.0 * damping_ratio * axis_inertia * natural_frequency - axis_damping)
    ki = max(0.0, integral_ratio * kp)
    integral_limit = min(1.1, output_limit / max(ki, 1e-6))
    return PIDAxis(kp=kp, ki=ki, kd=kd, integral_limit=integral_limit, output_limit=output_limit)


def make_pid_controller(config: SimulationConfig) -> Tuple[PIDController3Axis, Dict[str, object]]:
    severity = compute_scenario_severity(config)
    if config.vehicle == "spacecraft":
        base_natural_frequencies = (1.25, 1.30, 1.45)
        damping_ratios = (0.98, 0.98, 1.00)
        integral_ratios = (0.18, 0.18, 0.18)
    else:
        base_natural_frequencies = (3.20, 3.10, 2.60)
        damping_ratios = (0.95, 0.95, 1.00)
        integral_ratios = (0.12, 0.12, 0.08)

    tuning_scale = 1.0
    if config.auto_tune:
        tuning_scale = clamp(1.0 + 0.18 * (severity - 1.0), 0.85, 1.55)

    natural_frequencies = tuple(value * tuning_scale for value in base_natural_frequencies)
    pid = PIDController3Axis(
        roll=axis_pid_from_dynamics(
            config.inertia[0],
            config.rotational_damping[0],
            config.torque_limit[0],
            natural_frequencies[0],
            damping_ratios[0],
            integral_ratios[0],
        ),
        pitch=axis_pid_from_dynamics(
            config.inertia[1],
            config.rotational_damping[1],
            config.torque_limit[1],
            natural_frequencies[1],
            damping_ratios[1],
            integral_ratios[1],
        ),
        yaw=axis_pid_from_dynamics(
            config.inertia[2],
            config.rotational_damping[2],
            config.torque_limit[2],
            natural_frequencies[2],
            damping_ratios[2],
            integral_ratios[2],
        ),
    )
    details = {
        "type": "PID",
        "auto_tuned": config.auto_tune,
        "severity": round(severity, 3),
        "natural_frequency_scale": round(tuning_scale, 3),
        "axes": {
            "roll": asdict(pid.roll),
            "pitch": asdict(pid.pitch),
            "yaw": asdict(pid.yaw),
        },
    }
    return pid, details


def solve_discrete_lqr(
    axis_inertia: float,
    axis_damping: float,
    dt: float,
    q_angle: float,
    q_rate: float,
    r_value: float,
) -> Tuple[float, float]:
    a_matrix = np.array(
        [
            [1.0, -dt],
            [0.0, 1.0 - (axis_damping / axis_inertia) * dt],
        ],
        dtype=float,
    )
    b_matrix = np.array([[0.0], [dt / axis_inertia]], dtype=float)
    q_matrix = np.diag([q_angle, q_rate]).astype(float)
    r_matrix = np.array([[r_value]], dtype=float)

    p_matrix = q_matrix.copy()
    for _ in range(1000):
        bt_p = b_matrix.T @ p_matrix
        gain_term = np.linalg.inv(r_matrix + bt_p @ b_matrix)
        next_p = a_matrix.T @ p_matrix @ a_matrix - a_matrix.T @ p_matrix @ b_matrix @ gain_term @ bt_p @ a_matrix + q_matrix
        if np.max(np.abs(next_p - p_matrix)) < 1e-10:
            p_matrix = next_p
            break
        p_matrix = next_p

    gain = np.linalg.inv(r_matrix + b_matrix.T @ p_matrix @ b_matrix) @ (b_matrix.T @ p_matrix @ a_matrix)
    return (float(gain[0, 0]), float(gain[0, 1]))


def make_lqr_controller(config: SimulationConfig) -> Tuple[LQRController3Axis, Dict[str, object]]:
    severity = compute_scenario_severity(config)
    if config.vehicle == "spacecraft":
        q_angle = (60.0, 65.0, 52.0)
        q_rate = (16.0, 18.0, 20.0)
        r_value = (1.1, 1.0, 1.3)
    else:
        q_angle = (45.0, 45.0, 36.0)
        q_rate = (10.0, 10.0, 12.0)
        r_value = (0.9, 0.9, 1.1)

    weight_scale = 1.0
    if config.auto_tune:
        weight_scale = clamp(1.0 + 0.24 * (severity - 1.0), 0.85, 1.7)

    roll_gains = solve_discrete_lqr(
        config.inertia[0],
        config.rotational_damping[0],
        config.dt,
        q_angle=q_angle[0] * weight_scale,
        q_rate=q_rate[0] * weight_scale,
        r_value=r_value[0] / weight_scale,
    )
    pitch_gains = solve_discrete_lqr(
        config.inertia[1],
        config.rotational_damping[1],
        config.dt,
        q_angle=q_angle[1] * weight_scale,
        q_rate=q_rate[1] * weight_scale,
        r_value=r_value[1] / weight_scale,
    )
    yaw_gains = solve_discrete_lqr(
        config.inertia[2],
        config.rotational_damping[2],
        config.dt,
        q_angle=q_angle[2] * weight_scale,
        q_rate=q_rate[2] * weight_scale,
        r_value=r_value[2] / weight_scale,
    )

    controller = LQRController3Axis(
        roll=LQRAxis(gain_angle=roll_gains[0], gain_rate=roll_gains[1], output_limit=config.torque_limit[0]),
        pitch=LQRAxis(gain_angle=pitch_gains[0], gain_rate=pitch_gains[1], output_limit=config.torque_limit[1]),
        yaw=LQRAxis(gain_angle=yaw_gains[0], gain_rate=yaw_gains[1], output_limit=config.torque_limit[2]),
    )
    details = {
        "type": "LQR",
        "auto_tuned": config.auto_tune,
        "severity": round(severity, 3),
        "weight_scale": round(weight_scale, 3),
        "axes": {
            "roll": asdict(controller.roll),
            "pitch": asdict(controller.pitch),
            "yaw": asdict(controller.yaw),
        },
    }
    return controller, details


def scenario_target_deg_at(time_s: float, config: SimulationConfig) -> Vector3:
    base_target = config.target_deg
    if config.scenario == "track_moving_target":
        return (
            base_target[0] + 12.0 * math.sin(0.45 * time_s),
            base_target[1] + 8.0 * math.sin(0.32 * time_s + 0.45),
            base_target[2] + 25.0 * math.sin(0.18 * time_s),
        )
    return base_target


def active_disturbance(time_s: float, config: SimulationConfig) -> Vector3:
    if config.disturbance_window_s is None:
        return (0.0, 0.0, 0.0)
    start_s, end_s = config.disturbance_window_s
    if start_s <= time_s <= end_s:
        return config.disturbance_torque
    return (0.0, 0.0, 0.0)


def make_plant_variation(values: Sequence[float], uncertainty_pct: float, rng: np.random.Generator) -> Vector3:
    if uncertainty_pct <= 0.0:
        return tuple(values)  # type: ignore[return-value]
    spread = uncertainty_pct / 100.0
    scale = rng.uniform(1.0 - spread, 1.0 + spread, size=3)
    return tuple(values[index] * float(scale[index]) for index in range(3))  # type: ignore[return-value]


def initial_actuator_state(config: SimulationConfig) -> ReactionWheelState | QuadMotorState:
    if config.vehicle_preset.actuator_name == "reaction_wheels":
        return ReactionWheelState()
    return QuadMotorState()


def apply_spacecraft_actuator(
    command_torque: Vector3,
    state: ReactionWheelState,
    config: SimulationConfig,
    dt: float,
) -> Tuple[Vector3, ReactionWheelState]:
    alpha = clamp(dt / max(config.actuator_time_constant_s, 1e-4), 0.0, 1.0)
    filtered_torque = tuple(
        state.wheel_torque[index] + alpha * (command_torque[index] - state.wheel_torque[index]) for index in range(3)
    )
    momentum_limit = config.vehicle_preset.actuator_capacity
    momentum_usage = tuple(abs(state.wheel_momentum[index]) / momentum_limit[index] for index in range(3))
    availability = tuple(clamp(1.0 - usage * 0.65, 0.2, 1.0) for usage in momentum_usage)
    actual_torque = tuple(filtered_torque[index] * availability[index] for index in range(3))
    next_momentum = tuple(
        clamp(
            state.wheel_momentum[index] + actual_torque[index] * dt,
            -momentum_limit[index],
            momentum_limit[index],
        )
        for index in range(3)
    )
    return actual_torque, ReactionWheelState(wheel_torque=filtered_torque, wheel_momentum=next_momentum)


def apply_uav_actuator(
    command_torque: Vector3,
    state: QuadMotorState,
    config: SimulationConfig,
    dt: float,
) -> Tuple[Vector3, QuadMotorState]:
    alpha = clamp(dt / max(config.actuator_time_constant_s, 1e-4), 0.0, 1.0)
    normalized = tuple(
        command_torque[index] / max(config.torque_limit[index], 1e-6) for index in range(3)
    )
    desired_motor_levels = (
        clamp(normalized[0] + normalized[1] + normalized[2], -1.0, 1.0),
        clamp(-normalized[0] + normalized[1] - normalized[2], -1.0, 1.0),
        clamp(-normalized[0] - normalized[1] + normalized[2], -1.0, 1.0),
        clamp(normalized[0] - normalized[1] - normalized[2], -1.0, 1.0),
    )
    motor_levels = tuple(
        state.motor_levels[index] + alpha * (desired_motor_levels[index] - state.motor_levels[index])
        for index in range(4)
    )
    roll = 0.25 * (motor_levels[0] - motor_levels[1] - motor_levels[2] + motor_levels[3]) * config.torque_limit[0]
    pitch = 0.25 * (motor_levels[0] + motor_levels[1] - motor_levels[2] - motor_levels[3]) * config.torque_limit[1]
    yaw = 0.25 * (motor_levels[0] - motor_levels[1] + motor_levels[2] - motor_levels[3]) * config.torque_limit[2]
    return (roll, pitch, yaw), QuadMotorState(motor_levels=motor_levels)


def apply_actuator(
    command_torque: Vector3,
    state: ReactionWheelState | QuadMotorState,
    config: SimulationConfig,
    dt: float,
) -> Tuple[Vector3, ReactionWheelState | QuadMotorState]:
    limited_command = clamp_tuple(command_torque, config.torque_limit)
    if isinstance(state, ReactionWheelState):
        return apply_spacecraft_actuator(limited_command, state, config, dt)
    return apply_uav_actuator(limited_command, state, config, dt)


def measure_state(
    state: RigidBodyState,
    config: SimulationConfig,
    rng: np.random.Generator,
    angle_bias_deg: Vector3,
    rate_bias_deg_s: Vector3,
) -> Tuple[Quaternion, Vector3, Vector3, Vector3]:
    attitude_deg = quat_to_euler_deg(state.quaternion)
    noisy_attitude_deg = tuple(
        attitude_deg[index] + angle_bias_deg[index] + float(rng.normal(0.0, config.sensor_angle_noise_deg))
        for index in range(3)
    )
    measured_quaternion = quat_from_euler_deg(noisy_attitude_deg)
    body_rates_deg_s = degrees_tuple(state.body_rates)
    noisy_rates_deg_s = tuple(
        body_rates_deg_s[index] + rate_bias_deg_s[index] + float(rng.normal(0.0, config.sensor_rate_noise_deg_s))
        for index in range(3)
    )
    return measured_quaternion, radians_tuple(noisy_rates_deg_s), noisy_attitude_deg, noisy_rates_deg_s


def step_dynamics(
    state: RigidBodyState,
    actual_inertia: Vector3,
    actual_damping: Vector3,
    config: SimulationConfig,
    actuator_torque: Vector3,
    disturbance_torque: Vector3,
    dt: float,
) -> RigidBodyState:
    inertial_momentum = hadamard(actual_inertia, state.body_rates)
    gyro = cross(state.body_rates, inertial_momentum)
    damping = hadamard(actual_damping, state.body_rates)
    net_torque = sub(sub(add(actuator_torque, disturbance_torque), gyro), damping)

    body_rate_dot = (
        net_torque[0] / actual_inertia[0],
        net_torque[1] / actual_inertia[1],
        net_torque[2] / actual_inertia[2],
    )
    next_body_rates = add(state.body_rates, mul(body_rate_dot, dt))
    next_body_rates = tuple(clamp(rate, -config.rate_limit, config.rate_limit) for rate in next_body_rates)  # type: ignore[return-value]
    next_quaternion = integrate_quaternion(state.quaternion, next_body_rates, dt)
    return RigidBodyState(quaternion=next_quaternion, body_rates=next_body_rates)


def rms_triplet(values: Sequence[Vector3]) -> Vector3:
    sample_count = len(values)
    return tuple(
        math.sqrt(sum(sample[index] * sample[index] for sample in values) / sample_count)
        for index in range(3)
    )  # type: ignore[return-value]


def find_settling_time(samples: Sequence[Sample]) -> float | None:
    for start_index, sample in enumerate(samples):
        if max_abs(sample.error_deg) > 1.0 or max_abs(sample.body_rates_deg_s) > 1.0:
            continue
        if all(max_abs(item.error_deg) <= 1.0 and max_abs(item.body_rates_deg_s) <= 1.0 for item in samples[start_index:]):
            return sample.time_s
    return None


def compute_score(summary: SimulationSummary, duration: float) -> float:
    rms_error = sum(abs(value) for value in summary.rms_error_deg) / 3.0
    final_error = sum(abs(value) for value in summary.final_error_deg) / 3.0
    peak_rate = sum(abs(value) for value in summary.peak_body_rate_deg_s) / 3.0
    max_possible_effort = duration * 6.0
    effort_ratio = summary.control_effort / max(max_possible_effort, 1e-6)
    settling_penalty = 1.0 if summary.settling_time_s is None else summary.settling_time_s / max(duration, 1e-6)
    raw_score = (
        100.0
        - 1.8 * rms_error
        - 3.0 * final_error
        - 0.08 * peak_rate
        - 18.0 * effort_ratio
        - 18.0 * settling_penalty
    )
    return clamp(raw_score, 0.0, 100.0)


def summarize_samples(samples: Sequence[Sample], dt: float, duration: float) -> SimulationSummary:
    final = samples[-1]
    peak_error = (
        max(abs(sample.error_deg[0]) for sample in samples),
        max(abs(sample.error_deg[1]) for sample in samples),
        max(abs(sample.error_deg[2]) for sample in samples),
    )
    peak_rate = (
        max(abs(sample.body_rates_deg_s[0]) for sample in samples),
        max(abs(sample.body_rates_deg_s[1]) for sample in samples),
        max(abs(sample.body_rates_deg_s[2]) for sample in samples),
    )
    max_command = (
        max(abs(sample.torque_cmd[0]) for sample in samples),
        max(abs(sample.torque_cmd[1]) for sample in samples),
        max(abs(sample.torque_cmd[2]) for sample in samples),
    )
    max_actuator = (
        max(abs(sample.actuator_torque[0]) for sample in samples),
        max(abs(sample.actuator_torque[1]) for sample in samples),
        max(abs(sample.actuator_torque[2]) for sample in samples),
    )
    control_effort = sum(sum(abs(value) for value in sample.actuator_torque) for sample in samples) * dt
    settling_time = find_settling_time(samples)

    summary = SimulationSummary(
        final_attitude_deg=final.attitude_deg,
        final_error_deg=final.error_deg,
        peak_error_deg=peak_error,
        rms_error_deg=rms_triplet([sample.error_deg for sample in samples]),
        peak_body_rate_deg_s=peak_rate,
        max_torque_cmd=max_command,
        max_actuator_torque=max_actuator,
        control_effort=control_effort,
        settling_time_s=settling_time,
        score=0.0,
    )
    summary.score = compute_score(summary, duration)
    return summary


def simulate_controller(config: SimulationConfig, controller_name: ControllerName) -> ControllerResult:
    rng = np.random.default_rng(config.measurement_seed)
    actual_inertia = make_plant_variation(config.inertia, config.inertia_uncertainty_pct, rng)
    actual_damping = make_plant_variation(config.rotational_damping, config.damping_uncertainty_pct, rng)
    angle_bias_deg = tuple(
        float(rng.normal(0.0, config.sensor_angle_noise_deg * 0.35)) for _ in range(3)
    )  # type: ignore[assignment]
    rate_bias_deg_s = tuple(
        float(rng.normal(0.0, config.sensor_rate_noise_deg_s * 0.35)) for _ in range(3)
    )  # type: ignore[assignment]

    if controller_name == "pid":
        controller, controller_details = make_pid_controller(config)
    else:
        controller, controller_details = make_lqr_controller(config)

    notes = [
        f"Quaternion propagation active for {config.vehicle_preset.label.lower()} dynamics.",
        f"Actuator model: {config.vehicle_preset.actuator_name.replace('_', ' ')}.",
    ]
    if config.auto_tune:
        notes.append("Controller gains were auto-tuned from scenario severity and vehicle dynamics.")
    if config.inertia_uncertainty_pct or config.damping_uncertainty_pct:
        notes.append("Plant uncertainty was injected into inertia and damping for realism.")

    state = RigidBodyState(
        quaternion=quat_from_euler_deg(config.initial_deg),
        body_rates=radians_tuple(config.initial_rates_deg_s),
    )
    actuator_state = initial_actuator_state(config)
    samples: List[Sample] = []
    steps = int(config.duration / config.dt) + 1

    for step_index in range(steps):
        time_s = step_index * config.dt
        target_deg = scenario_target_deg_at(time_s, config)
        target_quaternion = quat_from_euler_deg(target_deg)
        measured_quaternion, measured_rates, measured_attitude_deg, measured_rates_deg_s = measure_state(
            state, config, rng, angle_bias_deg, rate_bias_deg_s
        )
        attitude_error = quat_error_vector(target_quaternion, measured_quaternion)
        torque_cmd = controller.update(attitude_error, measured_rates, config.dt)
        actuator_torque, actuator_state = apply_actuator(torque_cmd, actuator_state, config, config.dt)
        disturbance_torque = active_disturbance(time_s, config)
        actual_attitude_deg = quat_to_euler_deg(state.quaternion)
        actual_error = wrapped_error_deg(target_deg, actual_attitude_deg)

        samples.append(
            Sample(
                time_s=time_s,
                target_deg=target_deg,
                attitude_deg=actual_attitude_deg,
                measured_attitude_deg=measured_attitude_deg,
                body_rates_deg_s=degrees_tuple(state.body_rates),
                measured_rates_deg_s=measured_rates_deg_s,
                torque_cmd=torque_cmd,
                actuator_torque=actuator_torque,
                disturbance_torque=disturbance_torque,
                error_deg=actual_error,
                attitude_quat=state.quaternion,
            )
        )
        state = step_dynamics(state, actual_inertia, actual_damping, config, actuator_torque, disturbance_torque, config.dt)

    controller_details["actual_inertia"] = actual_inertia
    controller_details["actual_damping"] = actual_damping
    controller_details["sensor_bias_deg"] = angle_bias_deg
    controller_details["sensor_rate_bias_deg_s"] = rate_bias_deg_s

    return ControllerResult(
        controller=controller_name,
        vehicle=config.vehicle,
        scenario=config.scenario,
        samples=samples,
        summary=summarize_samples(samples, config.dt, config.duration),
        controller_details=controller_details,
        notes=notes,
    )


def run_simulation(config: SimulationConfig, controller_mode: Literal["pid", "lqr", "both"]) -> Dict[str, ControllerResult]:
    if controller_mode == "both":
        return {
            "pid": simulate_controller(config, "pid"),
            "lqr": simulate_controller(
                SimulationConfig(
                    **{
                        **asdict(config),
                        "measurement_seed": config.measurement_seed,
                    }
                ),
                "lqr",
            ),
        }
    return {controller_mode: simulate_controller(config, controller_mode)}


def compare_results(results: Dict[str, ControllerResult]) -> Dict[str, object] | None:
    if len(results) < 2:
        return None

    ordered = sorted(results.values(), key=lambda item: item.summary.score, reverse=True)
    winner = ordered[0]
    runner_up = ordered[1]
    reasons: List[str] = []

    if winner.summary.settling_time_s is not None and (
        runner_up.summary.settling_time_s is None
        or winner.summary.settling_time_s < runner_up.summary.settling_time_s
    ):
        reasons.append("faster settling")
    if vector_norm(winner.summary.rms_error_deg) < vector_norm(runner_up.summary.rms_error_deg):
        reasons.append("lower RMS error")
    if winner.summary.control_effort < runner_up.summary.control_effort:
        reasons.append("lower control effort")

    return {
        "winner": winner.controller,
        "winner_score": round(winner.summary.score, 2),
        "runner_up": runner_up.controller,
        "runner_up_score": round(runner_up.summary.score, 2),
        "score_gap": round(winner.summary.score - runner_up.summary.score, 2),
        "reasons": reasons or ["higher overall composite score"],
    }


def format_summary(result: ControllerResult) -> str:
    settling = f"{result.summary.settling_time_s:.2f} s" if result.summary.settling_time_s is not None else "not reached"
    return "\n".join(
        [
            f"{result.vehicle.upper()} | {result.controller.upper()} | scenario={result.scenario}",
            (
                f"Final altitude (deg): roll={result.summary.final_attitude_deg[0]:7.2f} "
                f"pitch={result.summary.final_attitude_deg[1]:7.2f} yaw={result.summary.final_attitude_deg[2]:7.2f}"
            ),
            (
                f"Final error    (deg): roll={result.summary.final_error_deg[0]:7.2f} "
                f"pitch={result.summary.final_error_deg[1]:7.2f} yaw={result.summary.final_error_deg[2]:7.2f}"
            ),
            (
                f"RMS error      (deg): roll={result.summary.rms_error_deg[0]:7.2f} "
                f"pitch={result.summary.rms_error_deg[1]:7.2f} yaw={result.summary.rms_error_deg[2]:7.2f}"
            ),
            (
                f"Peak body rate (deg/s): roll={result.summary.peak_body_rate_deg_s[0]:6.2f} "
                f"pitch={result.summary.peak_body_rate_deg_s[1]:6.2f} yaw={result.summary.peak_body_rate_deg_s[2]:6.2f}"
            ),
            (
                f"Max actuator torque (N*m): roll={result.summary.max_actuator_torque[0]:6.2f} "
                f"pitch={result.summary.max_actuator_torque[1]:6.2f} yaw={result.summary.max_actuator_torque[2]:6.2f}"
            ),
            f"Control effort: {result.summary.control_effort:.2f}",
            f"Settling time: {settling}",
            f"Composite score: {result.summary.score:.2f}/100",
        ]
    )


def emit_timeline(result: ControllerResult, print_interval: float) -> str:
    lines = ["", f"{result.controller.upper()} time history:"]
    last_time = -print_interval
    for sample in result.samples:
        if sample.time_s - last_time + 1e-9 < print_interval and sample is not result.samples[-1]:
            continue
        last_time = sample.time_s
        lines.append(
            (
                f"t={sample.time_s:5.2f}s | "
                f"target=({sample.target_deg[0]:6.2f}, {sample.target_deg[1]:6.2f}, {sample.target_deg[2]:6.2f}) | "
                f"att=({sample.attitude_deg[0]:6.2f}, {sample.attitude_deg[1]:6.2f}, {sample.attitude_deg[2]:6.2f}) | "
                f"err=({sample.error_deg[0]:6.2f}, {sample.error_deg[1]:6.2f}, {sample.error_deg[2]:6.2f})"
            )
        )
    return "\n".join(lines)


def write_csv(results: Dict[str, ControllerResult], path: str | Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "controller",
                "time_s",
                "target_roll_deg",
                "target_pitch_deg",
                "target_yaw_deg",
                "roll_deg",
                "pitch_deg",
                "yaw_deg",
                "measured_roll_deg",
                "measured_pitch_deg",
                "measured_yaw_deg",
                "roll_rate_deg_s",
                "pitch_rate_deg_s",
                "yaw_rate_deg_s",
                "roll_torque_cmd",
                "pitch_torque_cmd",
                "yaw_torque_cmd",
                "roll_actuator_torque",
                "pitch_actuator_torque",
                "yaw_actuator_torque",
                "roll_error_deg",
                "pitch_error_deg",
                "yaw_error_deg",
                "quat_w",
                "quat_x",
                "quat_y",
                "quat_z",
            ]
        )
        for controller_name, result in results.items():
            for sample in result.samples:
                writer.writerow(
                    [
                        controller_name,
                        sample.time_s,
                        *sample.target_deg,
                        *sample.attitude_deg,
                        *sample.measured_attitude_deg,
                        *sample.body_rates_deg_s,
                        *sample.torque_cmd,
                        *sample.actuator_torque,
                        *sample.error_deg,
                        *sample.attitude_quat,
                    ]
                )


def export_plot(results: Dict[str, ControllerResult], path: str | Path) -> Path:
    try:
        cache_dir = Path(__file__).resolve().parent / ".mpl-cache"
        cache_dir.mkdir(exist_ok=True)
        os.environ.setdefault("MPLCONFIGDIR", str(cache_dir))
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "matplotlib is not installed. Install dependencies with `pip install -r requirements.txt`."
        ) from exc

    output_path = Path(path)
    figure, axes = plt.subplots(4, 1, figsize=(12, 12), sharex=True)
    figure.suptitle("Altitude Control Dashboard Report")
    for controller_name, result in results.items():
        times = [sample.time_s for sample in result.samples]
        axes[0].plot(times, [sample.attitude_deg[0] for sample in result.samples], label=f"{controller_name.upper()} roll")
        axes[0].plot(times, [sample.attitude_deg[1] for sample in result.samples], label=f"{controller_name.upper()} pitch")
        axes[0].plot(times, [sample.attitude_deg[2] for sample in result.samples], label=f"{controller_name.upper()} yaw")
        axes[1].plot(times, [sample.error_deg[0] for sample in result.samples], label=f"{controller_name.upper()} roll err")
        axes[1].plot(times, [sample.error_deg[1] for sample in result.samples], label=f"{controller_name.upper()} pitch err")
        axes[1].plot(times, [sample.error_deg[2] for sample in result.samples], label=f"{controller_name.upper()} yaw err")
        axes[2].plot(times, [sample.body_rates_deg_s[0] for sample in result.samples], label=f"{controller_name.upper()} roll rate")
        axes[2].plot(times, [sample.body_rates_deg_s[1] for sample in result.samples], label=f"{controller_name.upper()} pitch rate")
        axes[2].plot(times, [sample.body_rates_deg_s[2] for sample in result.samples], label=f"{controller_name.upper()} yaw rate")
        axes[3].plot(times, [sample.actuator_torque[0] for sample in result.samples], label=f"{controller_name.upper()} roll torque")
        axes[3].plot(times, [sample.actuator_torque[1] for sample in result.samples], label=f"{controller_name.upper()} pitch torque")
        axes[3].plot(times, [sample.actuator_torque[2] for sample in result.samples], label=f"{controller_name.upper()} yaw torque")

    target_times = [sample.time_s for sample in next(iter(results.values())).samples]
    for axis_index, label in enumerate(("Roll", "Pitch", "Yaw")):
        axes[0].plot(
            target_times,
            [sample.target_deg[axis_index] for sample in next(iter(results.values())).samples],
            linestyle="--",
            linewidth=1.2,
            alpha=0.45,
            color=("tab:blue", "tab:orange", "tab:green")[axis_index],
        )

    axes[0].set_ylabel("Altitude (deg)")
    axes[1].set_ylabel("Error (deg)")
    axes[2].set_ylabel("Rate (deg/s)")
    axes[3].set_ylabel("Torque (N*m)")
    axes[3].set_xlabel("Time (s)")

    for axis in axes:
        axis.grid(True, alpha=0.3)
        axis.legend(loc="upper right", ncol=3, fontsize=8)

    figure.tight_layout()
    figure.savefig(output_path, dpi=160, bbox_inches="tight")
    plt.close(figure)
    return output_path


def serialize_sample(sample: Sample) -> Dict[str, object]:
    return {
        "time_s": sample.time_s,
        "target_deg": list(sample.target_deg),
        "attitude_deg": list(sample.attitude_deg),
        "measured_attitude_deg": list(sample.measured_attitude_deg),
        "body_rates_deg_s": list(sample.body_rates_deg_s),
        "measured_rates_deg_s": list(sample.measured_rates_deg_s),
        "torque_cmd": list(sample.torque_cmd),
        "actuator_torque": list(sample.actuator_torque),
        "disturbance_torque": list(sample.disturbance_torque),
        "error_deg": list(sample.error_deg),
        "attitude_quat": list(sample.attitude_quat),
        "rotation_matrix": [list(row) for row in quat_to_rotation_matrix(sample.attitude_quat)],
    }


def downsample_samples(samples: Sequence[Sample], max_points: int = 700) -> List[Sample]:
    if len(samples) <= max_points:
        return list(samples)
    step = max(1, len(samples) // max_points)
    trimmed = list(samples[::step])
    if trimmed[-1] is not samples[-1]:
        trimmed.append(samples[-1])
    return trimmed


def serialize_result(result: ControllerResult, max_points: int = 700) -> Dict[str, object]:
    return {
        "controller": result.controller,
        "vehicle": result.vehicle,
        "scenario": result.scenario,
        "summary": asdict(result.summary),
        "controller_details": result.controller_details,
        "notes": result.notes,
        "samples": [serialize_sample(sample) for sample in downsample_samples(result.samples, max_points=max_points)],
    }


def serialize_config(config: SimulationConfig) -> Dict[str, object]:
    return {
        "vehicle": config.vehicle,
        "scenario": config.scenario,
        "dt": config.dt,
        "duration": config.duration,
        "inertia": list(config.inertia),
        "rotational_damping": list(config.rotational_damping),
        "torque_limit": list(config.torque_limit),
        "initial_deg": list(config.initial_deg),
        "target_deg": list(config.target_deg),
        "initial_rates_deg_s": list(config.initial_rates_deg_s),
        "rate_limit_deg_s": math.degrees(config.rate_limit),
        "disturbance_torque": list(config.disturbance_torque),
        "disturbance_window_s": list(config.disturbance_window_s) if config.disturbance_window_s else None,
        "sensor_angle_noise_deg": config.sensor_angle_noise_deg,
        "sensor_rate_noise_deg_s": config.sensor_rate_noise_deg_s,
        "inertia_uncertainty_pct": config.inertia_uncertainty_pct,
        "damping_uncertainty_pct": config.damping_uncertainty_pct,
        "actuator_time_constant_s": config.actuator_time_constant_s,
        "measurement_seed": config.measurement_seed,
        "auto_tune": config.auto_tune,
    }


def save_report_bundle(
    results: Dict[str, ControllerResult],
    config: SimulationConfig,
    report_name: str | None = None,
    root: str | Path | None = None,
) -> Path:
    report_root = Path(root) if root is not None else Path(__file__).resolve().parent / "reports"
    report_root.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_name = (report_name or f"{config.vehicle}-{config.scenario}").replace(" ", "-").replace("/", "-").lower()
    folder = report_root / f"{timestamp}-{safe_name}"
    folder.mkdir(parents=True, exist_ok=True)

    csv_path = folder / "results.csv"
    plot_path = folder / "response.png"
    summary_json_path = folder / "summary.json"
    summary_txt_path = folder / "summary.txt"

    write_csv(results, csv_path)
    export_plot(results, plot_path)

    comparison = compare_results(results)
    payload = {
        "config": serialize_config(config),
        "comparison": comparison,
        "results": {name: serialize_result(result) for name, result in results.items()},
    }
    summary_json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "Altitude Control Report",
        f"Vehicle: {config.vehicle}",
        f"Scenario: {config.scenario}",
        "",
    ]
    for result in results.values():
        lines.append(format_summary(result))
        lines.append("")
    if comparison:
        lines.append(f"Winner: {comparison['winner']} ({comparison['winner_score']:.2f})")
        lines.append(f"Reasons: {', '.join(comparison['reasons'])}")

    summary_txt_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return folder


def available_presets_payload() -> Dict[str, object]:
    return {
        "vehicles": {
            name: {
                "label": preset.label,
                "description": preset.description,
                "actuator_name": preset.actuator_name,
                "inertia": list(preset.inertia),
                "rotational_damping": list(preset.rotational_damping),
                "torque_limit": list(preset.torque_limit),
                "rate_limit_deg_s": preset.rate_limit_deg_s,
                "default_initial_deg": list(preset.default_initial_deg),
                "default_target_deg": list(preset.default_target_deg),
                "default_initial_rates_deg_s": list(preset.default_initial_rates_deg_s),
                "sensor_angle_noise_deg": preset.sensor_angle_noise_deg,
                "sensor_rate_noise_deg_s": preset.sensor_rate_noise_deg_s,
                "actuator_time_constant_s": preset.actuator_time_constant_s,
            }
            for name, preset in VEHICLE_PRESETS.items()
        },
        "scenarios": {
            name: {
                "label": preset.label,
                "description": preset.description,
                "duration_s": preset.duration_s,
                "initial_deg": list(preset.initial_deg),
                "initial_rates_deg_s": list(preset.initial_rates_deg_s),
                "target_deg": list(preset.target_deg),
                "disturbance_torque": list(preset.disturbance_torque),
                "disturbance_window_s": list(preset.disturbance_window_s) if preset.disturbance_window_s else None,
                "target_mode": preset.target_mode,
            }
            for name, preset in SCENARIO_PRESETS.items()
        },
    }


def build_config_from_mapping(values: Dict[str, object]) -> SimulationConfig:
    def pick_vector(name: str) -> Vector3 | None:
        raw = values.get(name)
        if raw is None:
            return None
        return tuple(float(item) for item in raw)  # type: ignore[return-value]

    window = values.get("disturbance_window_s")
    parsed_window = tuple(float(item) for item in window) if window else None

    return SimulationConfig(
        vehicle=str(values.get("vehicle", "spacecraft")),  # type: ignore[arg-type]
        scenario=str(values.get("scenario", "custom")),  # type: ignore[arg-type]
        dt=float(values.get("dt", 0.02)),
        duration=float(values["duration"]) if values.get("duration") is not None else None,
        initial_deg=pick_vector("initial_deg"),
        target_deg=pick_vector("target_deg"),
        initial_rates_deg_s=pick_vector("initial_rates_deg_s"),
        disturbance_torque=pick_vector("disturbance_torque"),
        disturbance_window_s=parsed_window,  # type: ignore[arg-type]
        sensor_angle_noise_deg=float(values["sensor_angle_noise_deg"]) if values.get("sensor_angle_noise_deg") is not None else None,
        sensor_rate_noise_deg_s=float(values["sensor_rate_noise_deg_s"]) if values.get("sensor_rate_noise_deg_s") is not None else None,
        inertia_uncertainty_pct=float(values.get("inertia_uncertainty_pct", 0.0)),
        damping_uncertainty_pct=float(values.get("damping_uncertainty_pct", 0.0)),
        actuator_time_constant_s=float(values["actuator_time_constant_s"]) if values.get("actuator_time_constant_s") is not None else None,
        measurement_seed=int(values.get("measurement_seed", 7)),
        auto_tune=bool(values.get("auto_tune", True)),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Quaternion-based 3-axis altitude control simulator")
    parser.add_argument("--vehicle", choices=tuple(VEHICLE_PRESETS), default="spacecraft")
    parser.add_argument("--scenario", choices=tuple(SCENARIO_PRESETS), default="custom")
    parser.add_argument("--controller", choices=("pid", "lqr", "both"), default="both")
    parser.add_argument("--initial-deg", type=parse_vector)
    parser.add_argument("--target-deg", type=parse_vector)
    parser.add_argument("--initial-rates-deg-s", type=parse_vector)
    parser.add_argument("--duration", type=float)
    parser.add_argument("--dt", type=float, default=0.02)
    parser.add_argument("--disturbance", type=parse_vector)
    parser.add_argument("--disturbance-window", type=parse_window)
    parser.add_argument("--sensor-noise-deg", type=float)
    parser.add_argument("--sensor-rate-noise-deg-s", type=float)
    parser.add_argument("--inertia-uncertainty-pct", type=float, default=0.0)
    parser.add_argument("--damping-uncertainty-pct", type=float, default=0.0)
    parser.add_argument("--measurement-seed", type=int, default=7)
    parser.add_argument("--no-auto-tune", action="store_true")
    parser.add_argument("--csv", type=str)
    parser.add_argument("--plot", nargs="?", const="altitude_response.png")
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    return parser


def describe_run(config: SimulationConfig) -> str:
    disturbance = "none"
    if config.disturbance_window_s and max_abs(config.disturbance_torque) > 0.0:
        disturbance = (
            f"{config.disturbance_torque} N*m from "
            f"{config.disturbance_window_s[0]:.2f}s to {config.disturbance_window_s[1]:.2f}s"
        )
    return "\n".join(
        [
            "Altitude Control Simulator",
            f"Vehicle: {config.vehicle_preset.label}",
            f"Scenario: {config.scenario_preset.label}",
            f"Dynamics: quaternion-based rigid body with {config.vehicle_preset.actuator_name.replace('_', ' ')} actuators",
            f"Initial altitude (deg): {config.initial_deg}",
            f"Initial body rates (deg/s): {config.initial_rates_deg_s}",
            f"Disturbance: {disturbance}",
        ]
    )


def main() -> None:
    args = build_parser().parse_args()
    config = SimulationConfig(
        vehicle=args.vehicle,
        scenario=args.scenario,
        dt=args.dt,
        duration=args.duration,
        initial_deg=args.initial_deg,
        target_deg=args.target_deg,
        initial_rates_deg_s=args.initial_rates_deg_s,
        disturbance_torque=args.disturbance,
        disturbance_window_s=args.disturbance_window,
        sensor_angle_noise_deg=args.sensor_noise_deg,
        sensor_rate_noise_deg_s=args.sensor_rate_noise_deg_s,
        inertia_uncertainty_pct=args.inertia_uncertainty_pct,
        damping_uncertainty_pct=args.damping_uncertainty_pct,
        measurement_seed=args.measurement_seed,
        auto_tune=not args.no_auto_tune,
    )
    results = run_simulation(config, args.controller)

    print(describe_run(config))
    for index, result in enumerate(results.values()):
        if index:
            print()
        print()
        print(format_summary(result))
        if not args.quiet:
            print(emit_timeline(result, config.print_interval))

    comparison = compare_results(results)
    if comparison:
        print()
        print(
            f"Winner: {comparison['winner'].upper()} by {comparison['score_gap']:.2f} points "
            f"({', '.join(comparison['reasons'])})"
        )

    if args.csv:
        write_csv(results, args.csv)
        print(f"\nSaved CSV log to {args.csv}")

    if args.plot:
        output_path = export_plot(results, args.plot)
        print(f"Saved plot to {output_path}")

    if args.report:
        report_folder = save_report_bundle(results, config)
        print(f"Saved report bundle to {report_folder}")


if __name__ == "__main__":
    main()
