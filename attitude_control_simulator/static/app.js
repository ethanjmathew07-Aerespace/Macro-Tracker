const state = {
  presets: null,
  latest: null,
  focusController: null,
  animationStart: null,
  animationRequestId: null,
};

const refs = {};

document.addEventListener("DOMContentLoaded", async () => {
  captureRefs();
  bindEvents();
  await loadPresets();
  applySelectionDefaults();
  await runSimulation();
});

function captureRefs() {
  refs.form = document.getElementById("sim-form");
  refs.vehicle = document.getElementById("vehicle");
  refs.scenario = document.getElementById("scenario");
  refs.controller = document.getElementById("controller");
  refs.duration = document.getElementById("duration");
  refs.dt = document.getElementById("dt");
  refs.autoTune = document.getElementById("auto-tune");
  refs.initial = [
    document.getElementById("initial-roll"),
    document.getElementById("initial-pitch"),
    document.getElementById("initial-yaw"),
  ];
  refs.target = [
    document.getElementById("target-roll"),
    document.getElementById("target-pitch"),
    document.getElementById("target-yaw"),
  ];
  refs.rates = [
    document.getElementById("rate-roll"),
    document.getElementById("rate-pitch"),
    document.getElementById("rate-yaw"),
  ];
  refs.disturbance = [
    document.getElementById("dist-roll"),
    document.getElementById("dist-pitch"),
    document.getElementById("dist-yaw"),
  ];
  refs.distStart = document.getElementById("dist-start");
  refs.distEnd = document.getElementById("dist-end");
  refs.sensorAngleNoise = document.getElementById("sensor-angle-noise");
  refs.sensorRateNoise = document.getElementById("sensor-rate-noise");
  refs.inertiaUncertainty = document.getElementById("inertia-uncertainty");
  refs.dampingUncertainty = document.getElementById("damping-uncertainty");
  refs.actuatorLag = document.getElementById("actuator-lag");
  refs.measurementSeed = document.getElementById("measurement-seed");
  refs.runBtn = document.getElementById("run-btn");
  refs.reportBtn = document.getElementById("report-btn");
  refs.statusChip = document.getElementById("status-chip");
  refs.statusCopy = document.getElementById("status-copy");
  refs.heroCopy = document.getElementById("hero-copy");
  refs.focusTabs = document.getElementById("focus-tabs");
  refs.scorecards = document.getElementById("scorecards");
  refs.comparisonSummary = document.getElementById("comparison-summary");
  refs.animationGrid = document.getElementById("animation-grid");
  refs.controllerNotes = document.getElementById("controller-notes");
  refs.reportOutput = document.getElementById("report-output");
  refs.charts = {
    attitude: document.getElementById("attitude-chart"),
    error: document.getElementById("error-chart"),
    rate: document.getElementById("rate-chart"),
    torque: document.getElementById("torque-chart"),
  };
}

function bindEvents() {
  refs.form.addEventListener("submit", async (event) => {
    event.preventDefault();
    await runSimulation();
  });

  refs.reportBtn.addEventListener("click", async () => {
    await exportReport();
  });

  refs.vehicle.addEventListener("change", () => applySelectionDefaults());
  refs.scenario.addEventListener("change", () => applySelectionDefaults());
  window.addEventListener("resize", () => {
    if (state.latest) {
      renderCharts();
      startAnimationLoop();
    }
  });
}

async function loadPresets() {
  setStatus("Loading", "Fetching vehicle and scenario presets.");
  const response = await fetch("/api/presets");
  state.presets = await response.json();
  populateSelect(refs.vehicle, state.presets.vehicles);
  populateSelect(refs.scenario, state.presets.scenarios);
}

function populateSelect(select, entries) {
  select.innerHTML = "";
  Object.entries(entries).forEach(([value, item]) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = item.label;
    select.appendChild(option);
  });
}

function applySelectionDefaults() {
  const vehicle = state.presets.vehicles[refs.vehicle.value];
  const scenario = state.presets.scenarios[refs.scenario.value];

  refs.duration.value = formatNumber(scenario.duration_s, 2);
  setVectorInputs(refs.initial, refs.scenario.value === "custom" ? vehicle.default_initial_deg : scenario.initial_deg);
  setVectorInputs(refs.target, refs.scenario.value === "custom" ? vehicle.default_target_deg : scenario.target_deg);
  setVectorInputs(
    refs.rates,
    refs.scenario.value === "custom" ? vehicle.default_initial_rates_deg_s : scenario.initial_rates_deg_s
  );
  setVectorInputs(refs.disturbance, scenario.disturbance_torque);
  refs.distStart.value = scenario.disturbance_window_s ? scenario.disturbance_window_s[0] : "";
  refs.distEnd.value = scenario.disturbance_window_s ? scenario.disturbance_window_s[1] : "";
  refs.sensorAngleNoise.value = formatNumber(vehicle.sensor_angle_noise_deg, 2);
  refs.sensorRateNoise.value = formatNumber(vehicle.sensor_rate_noise_deg_s, 2);
  refs.actuatorLag.value = formatNumber(vehicle.actuator_time_constant_s, 2);
  refs.heroCopy.textContent = `${vehicle.description} ${scenario.description}`;
}

function setVectorInputs(inputs, values) {
  inputs.forEach((input, index) => {
    input.value = formatNumber(values[index], 2);
  });
}

function getVectorInputs(inputs) {
  return inputs.map((input) => Number(input.value || 0));
}

function formatNumber(value, digits = 2) {
  return Number(value).toFixed(digits).replace(/\.00$/, "");
}

function buildPayload() {
  const start = Number(refs.distStart.value);
  const end = Number(refs.distEnd.value);
  const hasWindow = Number.isFinite(start) && Number.isFinite(end) && end > start;

  return {
    vehicle: refs.vehicle.value,
    scenario: refs.scenario.value,
    controller: refs.controller.value,
    duration: Number(refs.duration.value),
    dt: Number(refs.dt.value),
    initial_deg: getVectorInputs(refs.initial),
    target_deg: getVectorInputs(refs.target),
    initial_rates_deg_s: getVectorInputs(refs.rates),
    disturbance_torque: getVectorInputs(refs.disturbance),
    disturbance_window_s: hasWindow ? [start, end] : null,
    sensor_angle_noise_deg: Number(refs.sensorAngleNoise.value),
    sensor_rate_noise_deg_s: Number(refs.sensorRateNoise.value),
    inertia_uncertainty_pct: Number(refs.inertiaUncertainty.value),
    damping_uncertainty_pct: Number(refs.dampingUncertainty.value),
    actuator_time_constant_s: Number(refs.actuatorLag.value),
    measurement_seed: Number(refs.measurementSeed.value),
    auto_tune: refs.autoTune.checked,
  };
}

async function runSimulation() {
  setStatus("Running", "Simulating quaternion dynamics, actuator realism, and controller response.");
  toggleBusy(true);
  try {
    const response = await fetch("/api/simulate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildPayload()),
    });
    state.latest = await response.json();
    const controllerNames = Object.keys(state.latest.results);
    state.focusController = state.latest.comparison?.winner || controllerNames[0];
    renderAll();
    setStatus("Ready", "Simulation complete. Explore scorecards, charts, and live animation below.");
  } catch (error) {
    console.error(error);
    setStatus("Error", "The simulation request failed. Check the browser console for details.");
  } finally {
    toggleBusy(false);
  }
}

async function exportReport() {
  setStatus("Exporting", "Saving CSV, plot, JSON, and text summary into the reports folder.");
  toggleBusy(true);
  try {
    const response = await fetch("/api/report", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildPayload()),
    });
    const report = await response.json();
    refs.reportOutput.innerHTML = `
      <div class="note-list">
        <div class="note-item"><strong>Saved Report Folder</strong><br>${report.report_folder}</div>
        <div class="note-item">
          <strong>Assets</strong><br>
          <a href="${report.assets.plot_url}" target="_blank" rel="noreferrer">Open plot</a><br>
          <a href="${report.assets.csv_url}" target="_blank" rel="noreferrer">Open CSV</a><br>
          <a href="${report.assets.summary_json_url}" target="_blank" rel="noreferrer">Open summary JSON</a><br>
          <a href="${report.assets.summary_txt_url}" target="_blank" rel="noreferrer">Open summary text</a>
        </div>
      </div>
    `;
    setStatus("Ready", "Report saved. The links below open files served from the local reports folder.");
  } catch (error) {
    console.error(error);
    setStatus("Error", "Report export failed. Check the browser console for details.");
  } finally {
    toggleBusy(false);
  }
}

function renderAll() {
  renderFocusTabs();
  renderScorecards();
  renderComparison();
  renderNotes();
  renderCharts();
  renderAnimations();
}

function renderFocusTabs() {
  refs.focusTabs.innerHTML = "";
  Object.keys(state.latest.results).forEach((controllerName) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `focus-tab ${state.focusController === controllerName ? "active" : ""}`;
    button.textContent = controllerName.toUpperCase();
    button.addEventListener("click", () => {
      state.focusController = controllerName;
      renderFocusTabs();
      renderNotes();
      renderCharts();
    });
    refs.focusTabs.appendChild(button);
  });
}

function renderScorecards() {
  const comparison = state.latest.comparison;
  refs.scorecards.classList.remove("empty-state");
  refs.scorecards.innerHTML = Object.values(state.latest.results)
    .map((result) => {
      const summary = result.summary;
      const isWinner = comparison && comparison.winner === result.controller;
      const rmsAverage = average(summary.rms_error_deg);
      const finalAverage = average(summary.final_error_deg);
      return `
        <article class="scorecard ${isWinner ? "winner" : ""}">
          <div class="scorecard-head">
            <strong>${result.controller.toUpperCase()}</strong>
            <span class="score-pill">${summary.score.toFixed(1)} / 100</span>
          </div>
          <div class="metrics">
            <div class="metric"><span>Settling</span><strong>${formatSettling(summary.settling_time_s)}</strong></div>
            <div class="metric"><span>Avg RMS Error</span><strong>${rmsAverage.toFixed(2)} deg</strong></div>
            <div class="metric"><span>Final Error</span><strong>${finalAverage.toFixed(2)} deg</strong></div>
            <div class="metric"><span>Control Effort</span><strong>${summary.control_effort.toFixed(2)}</strong></div>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderComparison() {
  const comparison = state.latest.comparison;
  if (!comparison) {
    const result = Object.values(state.latest.results)[0];
    refs.comparisonSummary.innerHTML = `
      <strong>${result.controller.toUpperCase()} run complete.</strong><br>
      Scenario: ${result.scenario.replaceAll("_", " ")}.<br>
      Vehicle: ${result.vehicle}.<br>
      Composite score: ${result.summary.score.toFixed(1)} / 100.
    `;
    return;
  }

  refs.comparisonSummary.innerHTML = `
    <strong>${comparison.winner.toUpperCase()}</strong> wins the comparison by
    <strong>${comparison.score_gap.toFixed(2)}</strong> points over
    ${comparison.runner_up.toUpperCase()}.
    <div class="comparison-reasons">
      ${comparison.reasons.map((reason) => `<span class="reason-chip">${reason}</span>`).join("")}
    </div>
  `;
}

function renderNotes() {
  const result = state.latest.results[state.focusController];
  const details = result.controller_details;
  const tuningKey = details.type === "PID" ? "natural_frequency_scale" : "weight_scale";
  refs.controllerNotes.classList.remove("empty-state");
  refs.controllerNotes.innerHTML = `
    <div class="note-list">
      <div class="note-item"><strong>Focus Controller</strong><br>${result.controller.toUpperCase()} on ${result.vehicle.toUpperCase()}</div>
      <div class="note-item"><strong>Auto-Tune</strong><br>${details.auto_tuned ? "Enabled" : "Disabled"} with severity ${details.severity}</div>
      <div class="note-item"><strong>Tuning Scale</strong><br>${details[tuningKey]}</div>
      ${result.notes.map((note) => `<div class="note-item">${note}</div>`).join("")}
    </div>
  `;
}

function renderCharts() {
  const result = state.latest.results[state.focusController];
  const samples = result.samples;
  const times = samples.map((sample) => sample.time_s);

  drawLineChart(refs.charts.attitude, {
    title: "Altitude Tracking",
    times,
    datasets: [
      makeDataset("Roll", "#4fd1c5", samples.map((sample) => sample.attitude_deg[0])),
      makeDataset("Pitch", "#ffba63", samples.map((sample) => sample.attitude_deg[1])),
      makeDataset("Yaw", "#7db6ff", samples.map((sample) => sample.attitude_deg[2])),
      makeDataset("Target Roll", "rgba(79, 209, 197, 0.45)", samples.map((sample) => sample.target_deg[0]), true),
      makeDataset("Target Pitch", "rgba(255, 186, 99, 0.45)", samples.map((sample) => sample.target_deg[1]), true),
      makeDataset("Target Yaw", "rgba(125, 182, 255, 0.45)", samples.map((sample) => sample.target_deg[2]), true),
    ],
  });

  drawLineChart(refs.charts.error, {
    title: "Error Response",
    times,
    datasets: [
      makeDataset("Roll Error", "#4fd1c5", samples.map((sample) => sample.error_deg[0])),
      makeDataset("Pitch Error", "#ffba63", samples.map((sample) => sample.error_deg[1])),
      makeDataset("Yaw Error", "#7db6ff", samples.map((sample) => sample.error_deg[2])),
    ],
  });

  drawLineChart(refs.charts.rate, {
    title: "Body Rates",
    times,
    datasets: [
      makeDataset("Roll Rate", "#4fd1c5", samples.map((sample) => sample.body_rates_deg_s[0])),
      makeDataset("Pitch Rate", "#ffba63", samples.map((sample) => sample.body_rates_deg_s[1])),
      makeDataset("Yaw Rate", "#7db6ff", samples.map((sample) => sample.body_rates_deg_s[2])),
    ],
  });

  drawLineChart(refs.charts.torque, {
    title: "Actuator Torque",
    times,
    datasets: [
      makeDataset("Roll Torque", "#4fd1c5", samples.map((sample) => sample.actuator_torque[0])),
      makeDataset("Pitch Torque", "#ffba63", samples.map((sample) => sample.actuator_torque[1])),
      makeDataset("Yaw Torque", "#7db6ff", samples.map((sample) => sample.actuator_torque[2])),
    ],
  });
}

function makeDataset(label, color, values, dashed = false) {
  return { label, color, values, dashed };
}

function drawLineChart(canvas, config) {
  const ctx = prepareCanvas(canvas);
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  const padding = { top: 26, right: 20, bottom: 28, left: 48 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;
  const times = config.times;
  const allValues = config.datasets.flatMap((dataset) => dataset.values);
  const minY = Math.min(...allValues, 0);
  const maxY = Math.max(...allValues, 0);
  const yRange = maxY - minY || 1;
  const xMax = times[times.length - 1] || 1;

  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#08131d";
  ctx.fillRect(0, 0, width, height);

  ctx.strokeStyle = "rgba(255, 255, 255, 0.08)";
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i += 1) {
    const y = padding.top + (chartHeight * i) / 4;
    ctx.beginPath();
    ctx.moveTo(padding.left, y);
    ctx.lineTo(width - padding.right, y);
    ctx.stroke();
  }

  ctx.fillStyle = "rgba(244, 247, 251, 0.78)";
  ctx.font = "12px Avenir Next";
  for (let i = 0; i <= 4; i += 1) {
    const value = maxY - (yRange * i) / 4;
    const y = padding.top + (chartHeight * i) / 4 + 4;
    ctx.fillText(value.toFixed(1), 10, y);
  }

  config.datasets.forEach((dataset, index) => {
    ctx.save();
    ctx.strokeStyle = dataset.color;
    ctx.lineWidth = dataset.dashed ? 1.4 : 2.1;
    ctx.setLineDash(dataset.dashed ? [6, 6] : []);
    ctx.beginPath();
    dataset.values.forEach((value, sampleIndex) => {
      const x = padding.left + (times[sampleIndex] / xMax) * chartWidth;
      const y = padding.top + ((maxY - value) / yRange) * chartHeight;
      if (sampleIndex === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });
    ctx.stroke();
    ctx.restore();

    const legendX = padding.left + (index % 3) * 120;
    const legendY = 16 + Math.floor(index / 3) * 14;
    ctx.fillStyle = dataset.color;
    ctx.fillRect(legendX, legendY - 7, 18, 3);
    ctx.fillStyle = "rgba(244, 247, 251, 0.76)";
    ctx.fillText(dataset.label, legendX + 24, legendY);
  });

  ctx.fillStyle = "rgba(244, 247, 251, 0.6)";
  ctx.fillText(`0`, padding.left - 4, height - 8);
  ctx.fillText(`${xMax.toFixed(1)}s`, width - padding.right - 24, height - 8);
}

function prepareCanvas(canvas) {
  const dpr = window.devicePixelRatio || 1;
  const width = canvas.clientWidth || canvas.width;
  const height = canvas.clientHeight || canvas.height;
  canvas.width = width * dpr;
  canvas.height = height * dpr;
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return ctx;
}

function renderAnimations() {
  const controllers = Object.keys(state.latest.results);
  refs.animationGrid.innerHTML = controllers
    .map((controller) => {
      return `
        <article class="animation-card" data-controller="${controller}">
          <div class="panel-head">
            <h3>${controller.toUpperCase()} Altitude</h3>
            <span class="panel-tag">${state.latest.results[controller].vehicle.toUpperCase()}</span>
          </div>
          <canvas width="340" height="260"></canvas>
          <div class="animation-meta">
            <span class="time-readout">t = 0.00s</span>
            <span class="angle-readout">0.0, 0.0, 0.0</span>
          </div>
        </article>
      `;
    })
    .join("");

  startAnimationLoop();
}

function startAnimationLoop() {
  if (state.animationRequestId) {
    cancelAnimationFrame(state.animationRequestId);
  }
  state.animationStart = null;

  const animate = (timestamp) => {
    if (!state.latest) {
      return;
    }
    if (state.animationStart === null) {
      state.animationStart = timestamp;
    }
    const cards = refs.animationGrid.querySelectorAll(".animation-card");
    cards.forEach((card) => {
      const controller = card.dataset.controller;
      const result = state.latest.results[controller];
      const samples = result.samples;
      const duration = samples[samples.length - 1].time_s || 1;
      const elapsed = ((timestamp - state.animationStart) / 1000) * 1.25;
      const simTime = elapsed % duration;
      const sampleIndex = Math.min(samples.length - 1, Math.floor((simTime / duration) * (samples.length - 1)));
      const sample = samples[sampleIndex];
      drawAttitudeScene(card.querySelector("canvas"), sample, controller);
      card.querySelector(".time-readout").textContent = `t = ${sample.time_s.toFixed(2)}s`;
      card.querySelector(".angle-readout").textContent =
        `roll ${sample.attitude_deg[0].toFixed(1)} deg, pitch ${sample.attitude_deg[1].toFixed(1)} deg, yaw ${sample.attitude_deg[2].toFixed(1)} deg`;
    });

    state.animationRequestId = requestAnimationFrame(animate);
  };

  state.animationRequestId = requestAnimationFrame(animate);
}

function drawAttitudeScene(canvas, sample, controller) {
  const ctx = prepareCanvas(canvas);
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#07111c";
  ctx.fillRect(0, 0, width, height);

  drawStarfield(ctx, width, height);

  const cubeVertices = [
    [-1, -1, -1],
    [1, -1, -1],
    [1, 1, -1],
    [-1, 1, -1],
    [-1, -1, 1],
    [1, -1, 1],
    [1, 1, 1],
    [-1, 1, 1],
  ];
  const edges = [
    [0, 1], [1, 2], [2, 3], [3, 0],
    [4, 5], [5, 6], [6, 7], [7, 4],
    [0, 4], [1, 5], [2, 6], [3, 7],
  ];
  const rotation = sample.rotation_matrix;
  const transformed = cubeVertices.map((vertex) => rotateVertex(rotation, vertex));
  const projected = transformed.map((vertex) => projectVertex(vertex, width, height));

  ctx.strokeStyle = controller === state.focusController ? "#4fd1c5" : "#7db6ff";
  ctx.lineWidth = 2;
  edges.forEach(([start, end]) => {
    ctx.beginPath();
    ctx.moveTo(projected[start].x, projected[start].y);
    ctx.lineTo(projected[end].x, projected[end].y);
    ctx.stroke();
  });

  drawAxis(ctx, rotation, width, height, [1.7, 0, 0], "#ff7a7a");
  drawAxis(ctx, rotation, width, height, [0, 1.7, 0], "#91f2a3");
  drawAxis(ctx, rotation, width, height, [0, 0, 1.7], "#7db6ff");
}

function rotateVertex(rotation, vertex) {
  return [
    rotation[0][0] * vertex[0] + rotation[0][1] * vertex[1] + rotation[0][2] * vertex[2],
    rotation[1][0] * vertex[0] + rotation[1][1] * vertex[1] + rotation[1][2] * vertex[2],
    rotation[2][0] * vertex[0] + rotation[2][1] * vertex[1] + rotation[2][2] * vertex[2],
  ];
}

function projectVertex(vertex, width, height) {
  const distance = 4.8;
  const scale = 86 / (distance - vertex[2]);
  return {
    x: width / 2 + vertex[0] * scale,
    y: height / 2 - vertex[1] * scale,
  };
}

function drawAxis(ctx, rotation, width, height, endpoint, color) {
  const point = projectVertex(rotateVertex(rotation, endpoint), width, height);
  ctx.strokeStyle = color;
  ctx.lineWidth = 2.4;
  ctx.beginPath();
  ctx.moveTo(width / 2, height / 2);
  ctx.lineTo(point.x, point.y);
  ctx.stroke();
}

function drawStarfield(ctx, width, height) {
  const stars = [
    [0.12, 0.18, 1.7],
    [0.82, 0.22, 1.2],
    [0.22, 0.74, 1.4],
    [0.68, 0.82, 1.8],
    [0.48, 0.34, 1.1],
    [0.88, 0.58, 1.5],
  ];
  ctx.fillStyle = "rgba(255, 255, 255, 0.45)";
  stars.forEach(([x, y, r]) => {
    ctx.beginPath();
    ctx.arc(width * x, height * y, r, 0, Math.PI * 2);
    ctx.fill();
  });
}

function setStatus(label, message) {
  refs.statusChip.textContent = label;
  refs.statusCopy.textContent = message;
}

function toggleBusy(isBusy) {
  refs.runBtn.disabled = isBusy;
  refs.reportBtn.disabled = isBusy;
  refs.runBtn.style.opacity = isBusy ? "0.7" : "1";
  refs.reportBtn.style.opacity = isBusy ? "0.7" : "1";
}

function average(values) {
  return values.reduce((sum, value) => sum + Math.abs(value), 0) / values.length;
}

function formatSettling(value) {
  return value === null ? "not reached" : `${value.toFixed(2)} s`;
}
