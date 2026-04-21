const canvas = document.getElementById("c");
const ctx = canvas.getContext("2d");
const trendCanvas = document.getElementById("trend-chart");
const trendCtx = trendCanvas.getContext("2d");
const graphCanvas = document.getElementById("graph-canvas");
const graphCtx = graphCanvas.getContext("2d");
let state = {};

const roads = ["North", "South", "East", "West"];
const history = { queue: [], throughput: [] };
const MAX_HISTORY = 120;
const IS_LOCAL_HOST =
    window.location.hostname === "127.0.0.1" ||
    window.location.hostname === "localhost";
const ACTIVE_POLL_MS = IS_LOCAL_HOST ? 120 : 700;
const IDLE_POLL_MS = IS_LOCAL_HOST ? 700 : 2500;
let chartTick = 0;
let sceneWidth = 0;
let sceneHeight = 0;
let sceneDpr = 1;
let trendDpr = 1;
let graphDpr = 1;
let modeControlsKey = "";
let densityControlsKey = "";
let scenarioControlsKey = "";
let stateRequestInFlight = false;
let pollingStarted = false;
let drewIdleScene = false;

function resizeCanvas() {
    const rect = canvas.getBoundingClientRect();
    const nextWidth = Math.max(320, Math.floor(rect.width));
    const nextHeight = Math.max(420, Math.floor(rect.height));
    const dpr = window.devicePixelRatio || 1;
    if (nextWidth !== sceneWidth || nextHeight !== sceneHeight || dpr !== sceneDpr) {
        sceneWidth = nextWidth;
        sceneHeight = nextHeight;
        sceneDpr = dpr;
        canvas.width = Math.floor(sceneWidth * sceneDpr);
        canvas.height = Math.floor(sceneHeight * sceneDpr);
        ctx.setTransform(sceneDpr, 0, 0, sceneDpr, 0, 0);
    }
}

function resizeTrendCanvas() {
    const wrap = trendCanvas.parentElement;
    if (!wrap) return;
    const nextWidth = Math.max(220, Math.floor(wrap.clientWidth - 16));
    const nextHeight = Math.max(80, Math.floor(wrap.clientHeight - 16));
    const dpr = window.devicePixelRatio || 1;
    if (trendCanvas.width !== Math.floor(nextWidth * dpr) || trendCanvas.height !== Math.floor(nextHeight * dpr) || dpr !== trendDpr) {
        trendDpr = dpr;
        trendCanvas.width = Math.floor(nextWidth * trendDpr);
        trendCanvas.height = Math.floor(nextHeight * trendDpr);
        trendCtx.setTransform(trendDpr, 0, 0, trendDpr, 0, 0);
    }
}

function resizeGraphCanvas() {
    const wrap = graphCanvas.parentElement;
    if (!wrap) return;
    const nextWidth = Math.max(220, Math.floor(wrap.clientWidth - 16));
    const nextHeight = Math.max(120, Math.floor(wrap.clientHeight - 16));
    const dpr = window.devicePixelRatio || 1;
    if (
        graphCanvas.width !== Math.floor(nextWidth * dpr) ||
        graphCanvas.height !== Math.floor(nextHeight * dpr) ||
        dpr !== graphDpr
    ) {
        graphDpr = dpr;
        graphCanvas.width = Math.floor(nextWidth * graphDpr);
        graphCanvas.height = Math.floor(nextHeight * graphDpr);
        graphCtx.setTransform(graphDpr, 0, 0, graphDpr, 0, 0);
    }
}

function drawGraphModel() {
    resizeGraphCanvas();
    const width = graphCanvas.width / graphDpr;
    const height = graphCanvas.height / graphDpr;
    graphCtx.clearRect(0, 0, width, height);

    const cx = width / 2;
    const cy = height / 2;
    const dx = Math.min(110, Math.max(72, width * 0.28));
    const dy = Math.min(76, Math.max(54, height * 0.28));
    const radius = 18;
    const nodes = {
        North: { x: cx, y: cy - dy, short: "N" },
        South: { x: cx, y: cy + dy, short: "S" },
        East: { x: cx + dx, y: cy, short: "E" },
        West: { x: cx - dx, y: cy, short: "W" },
    };

    const activeRoads = state.active_roads || [];
    const conflicts = state.conflicts || [];

    // Draw conflict edges.
    graphCtx.lineWidth = 2;
    conflicts.forEach((edge) => {
        const a = nodes[edge[0]];
        const b = nodes[edge[1]];
        if (!a || !b) return;
        const edgeActive = activeRoads.includes(edge[0]) || activeRoads.includes(edge[1]);
        graphCtx.strokeStyle = edgeActive ? "rgba(255, 139, 139, 0.92)" : "rgba(167, 196, 232, 0.62)";
        graphCtx.beginPath();
        graphCtx.moveTo(a.x, a.y);
        graphCtx.lineTo(b.x, b.y);
        graphCtx.stroke();
    });

    // Draw nodes.
    Object.entries(nodes).forEach(([road, node]) => {
        const active = activeRoads.includes(road);
        graphCtx.fillStyle = active ? "#16d487" : "#ef4f67";
        graphCtx.strokeStyle = "rgba(235, 244, 255, 0.95)";
        graphCtx.lineWidth = 3;
        graphCtx.beginPath();
        graphCtx.arc(node.x, node.y, radius, 0, Math.PI * 2);
        graphCtx.fill();
        graphCtx.stroke();

        graphCtx.fillStyle = "#ffffff";
        graphCtx.font = "bold 15px Arial";
        graphCtx.textAlign = "center";
        graphCtx.textBaseline = "middle";
        graphCtx.fillText(node.short, node.x, node.y + 0.5);
    });
}

function drawTrendChart() {
    resizeTrendCanvas();
    const width = trendCanvas.width / trendDpr;
    const height = trendCanvas.height / trendDpr;
    trendCtx.clearRect(0, 0, width, height);

    trendCtx.strokeStyle = "rgba(255,255,255,0.15)";
    trendCtx.lineWidth = 1;
    for (let i = 1; i <= 4; i += 1) {
        const y = (height / 5) * i;
        trendCtx.beginPath();
        trendCtx.moveTo(0, y);
        trendCtx.lineTo(width, y);
        trendCtx.stroke();
    }

    if (history.queue.length < 2) {
        return;
    }

    const maxQueue = Math.max(1, ...history.queue);
    const maxFlow = Math.max(1, ...history.throughput);

    const drawSeries = (series, maxValue, color) => {
        trendCtx.strokeStyle = color;
        trendCtx.lineWidth = 2;
        trendCtx.beginPath();
        series.forEach((value, index) => {
            const x = (index / (MAX_HISTORY - 1)) * width;
            const y = height - (value / maxValue) * (height - 8);
            if (index === 0) trendCtx.moveTo(x, y);
            else trendCtx.lineTo(x, y);
        });
        trendCtx.stroke();
    };

    drawSeries(history.queue, maxQueue, "#00ff88");
    drawSeries(history.throughput, maxFlow, "#ffd84d");
}

function drawCar(x, y, color, vertical) {
    const width = vertical ? 16 : 26;
    const height = vertical ? 26 : 16;
    const left = x - width / 2;
    const top = y - height / 2;

    ctx.fillStyle = color;
    ctx.fillRect(left, top, width, height);

    ctx.fillStyle = "rgba(255, 255, 255, 0.75)";
    if (vertical) {
        ctx.fillRect(left + 3, top + 5, width - 6, 6);
        ctx.fillRect(left + 3, top + height - 11, width - 6, 5);
    } else {
        ctx.fillRect(left + 5, top + 3, 6, height - 6);
        ctx.fillRect(left + width - 11, top + 3, 6, height - 6);
    }

    ctx.fillStyle = "#101827";
    if (vertical) {
        ctx.fillRect(left - 2, top + 5, 3, 6);
        ctx.fillRect(left + width - 1, top + 5, 3, 6);
        ctx.fillRect(left - 2, top + height - 11, 3, 6);
        ctx.fillRect(left + width - 1, top + height - 11, 3, 6);
    } else {
        ctx.fillRect(left + 5, top - 2, 6, 3);
        ctx.fillRect(left + 5, top + height - 1, 6, 3);
        ctx.fillRect(left + width - 11, top - 2, 6, 3);
        ctx.fillRect(left + width - 11, top + height - 1, 6, 3);
    }
}

function drawSignal(x, y, label, active, labelDx = 0, labelDy = 0) {
    ctx.fillStyle = active ? "#00ff00" : "#ff1717";
    if (active) {
        ctx.shadowColor = "#00ff00";
        ctx.shadowBlur = 20;
    }
    ctx.beginPath();
    ctx.arc(x, y, 14, 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowColor = "transparent";
    ctx.strokeStyle = "#fff";
    ctx.lineWidth = 2;
    ctx.stroke();

    ctx.fillStyle = "#ffff00";
    ctx.font = "bold 18px Arial";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(label, x + labelDx, y + labelDy);
}

function draw() {
    const width = sceneWidth || (canvas.width / sceneDpr);
    const height = sceneHeight || (canvas.height / sceneDpr);
    const cx = width / 2;
    const cy = height / 2;

    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, width, height);
    ctx.fillStyle = "#0a3a3a";
    ctx.fillRect(cx - 50, 0, 100, height);
    ctx.fillRect(0, cy - 40, width, 80);

    ctx.strokeStyle = "#0a6a6a";
    ctx.lineWidth = 1;
    ctx.setLineDash([10, 10]);
    ctx.beginPath(); ctx.moveTo(cx - 20, 0); ctx.lineTo(cx - 20, height); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(cx + 20, 0); ctx.lineTo(cx + 20, height); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0, cy - 12); ctx.lineTo(width, cy - 12); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0, cy + 12); ctx.lineTo(width, cy + 12); ctx.stroke();
    ctx.setLineDash([]);

    const activeRoads = state.active_roads || [];
    drawSignal(cx, 24, "N", activeRoads.includes("North"), 0, 28);
    drawSignal(cx, height - 24, "S", activeRoads.includes("South"), 0, -28);
    drawSignal(24, cy, "W", activeRoads.includes("West"), 28, 0);
    drawSignal(width - 24, cy, "E", activeRoads.includes("East"), -28, 0);

    const waitingByRoad = { North: 0, South: 0, East: 0, West: 0 };
    (state.cars || []).forEach((car) => {
        const isWaiting = !car.passed && car.progress <= 0 && !activeRoads.includes(car.road);
        let x;
        let y;

        if (isWaiting) {
            const queueIndex = waitingByRoad[car.road]++;
            const lane = ((queueIndex % 3) - 1) * 14;
            const row = Math.floor(queueIndex / 3);
            const gap = 32;
            if (car.road === "North") {
                x = cx - 18 + lane;
                y = 64 + row * gap;
                drawCar(x, y, car.color, true);
            } else if (car.road === "South") {
                x = cx + 18 - lane;
                y = height - 64 - row * gap;
                drawCar(x, y, car.color, true);
            } else if (car.road === "East") {
                x = width - 64 - row * gap;
                y = cy - 18 + lane;
                drawCar(x, y, car.color, false);
            } else {
                x = 64 + row * gap;
                y = cy + 18 - lane;
                drawCar(x, y, car.color, false);
            }
            return;
        }

        const p = Math.max(0, Math.min(car.progress / 170, 1));
        const lane = ((car.id % 3) - 1) * 14;
        const margin = 20;
        if (car.road === "North") {
            x = cx - 18 + lane;
            y = -margin + (height + margin * 2) * p;
            drawCar(x, y, car.color, true);
        } else if (car.road === "South") {
            x = cx + 18 - lane;
            y = height + margin - (height + margin * 2) * p;
            drawCar(x, y, car.color, true);
        } else if (car.road === "East") {
            x = width + margin - (width + margin * 2) * p;
            y = cy - 18 + lane;
            drawCar(x, y, car.color, false);
        } else {
            x = -margin + (width + margin * 2) * p;
            y = cy + 18 - lane;
            drawCar(x, y, car.color, false);
        }
    });
}

function setText(id, value) {
    document.getElementById(id).textContent = value;
}

function renderModeButtons() {
    const container = document.getElementById("mode-controls");
    const key = JSON.stringify({
        mode: state.mode || "",
        modes: state.modes || {},
    });
    if (key === modeControlsKey) {
        return;
    }
    modeControlsKey = key;
    container.innerHTML = Object.entries(state.modes || {})
        .map(([mode, label]) => {
            const active = mode === state.mode ? " active" : "";
            return `<button class="mode-btn${active}" data-mode="${mode}">${label}</button>`;
        })
        .join("");
}

function renderRoadCards() {
    const queues = state.queue_by_road || {};
    const density = state.density || {};
    const activeRoads = state.active_roads || [];
    document.getElementById("road-status").innerHTML = roads.map((road) => {
        const isActive = activeRoads.includes(road);
        const status = isActive ? "GREEN" : "RED";
        const className = isActive ? "road-active" : "road-inactive";
        return `
            <div class="road-item ${className}">
                <span class="road-name">${road}</span>
                <span class="road-meta">Queue ${queues[road] ?? 0} | Density ${density[road] ?? 0} | ${status}</span>
            </div>`;
    }).join("");
}

function renderDensityControls() {
    const density = state.density || {};
    const key = JSON.stringify(density);
    if (key === densityControlsKey) {
        return;
    }
    densityControlsKey = key;
    document.getElementById("density-controls").innerHTML = roads.map((road) => `
        <div class="density-row">
            <span>${road}</span>
            <button class="density-btn" data-density-road="${road}" data-density-delta="-1">-</button>
            <span class="density-value">${density[road] ?? 0}</span>
            <button class="density-btn" data-density-road="${road}" data-density-delta="1">+</button>
        </div>
    `).join("");
}

function renderScenarioButtons() {
    const container = document.getElementById("scenario-controls");
    const key = JSON.stringify({
        active: state.active_scenario || "",
        scenarios: state.scenarios || {},
    });
    if (key === scenarioControlsKey) {
        return;
    }
    scenarioControlsKey = key;
    container.innerHTML = Object.entries(state.scenarios || {})
        .map(([scenarioKey, label]) => {
            const active = scenarioKey === state.active_scenario ? " active" : "";
            return `<button class="mode-btn scenario-btn${active}" data-scenario="${scenarioKey}">${label}</button>`;
        })
        .join("");
}

function renderGraphDetails() {
    const groups = state.phase_groups || {};
    const phaseText = Object.keys(groups).map((phase) => `Phase ${phase}: ${groups[phase].join(" + ")}`).join(" | ") || "-";
    const conflicts = (state.conflicts || []).map((edge) => edge.join(" - ")).join(", ") || "-";
    setText("phase-groups", `Phases: ${phaseText}`);
    setText("conflict-edges", `Conflict edges: ${conflicts}`);
    setText("phase-explanation", `Current phase explanation: ${state.phase_explanation || "-"}`);
}

function renderPerformance() {
    const perfEl = document.getElementById("perf-rating");
    perfEl.textContent = state.efficiency || "-";
    perfEl.className = "perf-rating";
    if (state.efficiency === "Excellent") perfEl.classList.add("rating-excellent");
    else if (state.efficiency === "Very Good" || state.efficiency === "Good") perfEl.classList.add("rating-good");
    else if (state.efficiency === "Moderate") perfEl.classList.add("rating-moderate");
    else perfEl.classList.add("rating-poor");
}

function renderModeIntensity() {
    const badge = document.getElementById("mode-intensity");
    const intensity = (state.mode_intensity || "Medium").toLowerCase();
    badge.textContent = state.mode_intensity || "Medium";
    badge.className = "mode-intensity-badge";
    badge.classList.add(`intensity-${intensity}`);
}

async function update() {
    if (stateRequestInFlight) {
        return;
    }
    stateRequestInFlight = true;
    try {
        const res = await fetch("/api/state", { cache: "no-store" });
        state = await res.json();
    } catch {
        stateRequestInFlight = false;
        return;
    }
    stateRequestInFlight = false;

    setText("phase", state.current_phase || "-");
    setText("sig", `${state.remaining_time ?? "-"}s`);
    setText("cars", state.queue_length ?? 0);
    setText("pass", state.cars_passed || 0);
    setText("eff", state.efficiency_score || 0);
    setText("throughput", state.throughput || 0);
    setText("avg-wait", `${state.average_wait || 0}s`);
    setText("green-roads", (state.active_roads || []).join(" + ") || "-");
    setText("red-roads", (state.inactive_roads || []).join(" + ") || "-");
    setText("priority-status", state.priority_message || "No priority active");
    setText("mode-status", `Mode: ${state.mode_label || "Normal Traffic"}`);
    setText("scenario-status", state.scenario_description || "Pick a preset to simulate a real-world traffic pattern.");

    const phaseDuration = state.phase_duration || 1;
    const remaining = state.remaining_time ?? 0;
    const phasePercent = Math.max(0, Math.min(100, (remaining / phaseDuration) * 100));
    document.getElementById("phase-fill").style.width = `${phasePercent}%`;

    document.getElementById("s").disabled = state.running;
    document.getElementById("t").disabled = !state.running;

    renderModeButtons();
    renderRoadCards();
    renderDensityControls();
    renderScenarioButtons();
    renderGraphDetails();
    renderPerformance();
    renderModeIntensity();

    const hasCars = (state.cars || []).length > 0;
    const activeAnimation = state.running || hasCars;

    if (activeAnimation) {
        drewIdleScene = false;
        drawGraphModel();
        chartTick += 1;
        if (chartTick % 3 === 0) {
            history.queue.push(state.queue_length ?? 0);
            history.throughput.push(state.throughput ?? 0);
            if (history.queue.length > MAX_HISTORY) history.queue.shift();
            if (history.throughput.length > MAX_HISTORY) history.throughput.shift();
            drawTrendChart();
        }
        draw();
    } else if (!drewIdleScene) {
        // Draw once in idle state to avoid unnecessary heavy canvas redraw loops.
        drawGraphModel();
        drawTrendChart();
        draw();
        drewIdleScene = true;
    }
}

async function callApi(path) {
    await fetch(path);
    await update();
}

async function start() { await callApi("/api/start"); }
async function stop() { await callApi("/api/stop"); }
async function reset() { await callApi("/api/reset"); }

document.addEventListener("click", (event) => {
    const aboutToggle = event.target.dataset.aboutToggle;
    if (aboutToggle) {
        const section = document.getElementById(aboutToggle);
        if (section) {
            section.classList.toggle("open");
            const isOpen = section.classList.contains("open");
            const openLabel = event.target.dataset.openLabel || "View Less";
            const closedLabel = event.target.dataset.closedLabel || "View More";
            event.target.textContent = isOpen ? openLabel : closedLabel;
        }
        return;
    }
    const mode = event.target.dataset.mode;
    if (mode) {
        callApi(`/api/mode/${mode}`);
        return;
    }
    const priorityRoad = event.target.dataset.priority;
    if (priorityRoad) {
        callApi(`/api/priority/${priorityRoad}`);
        return;
    }
    const densityRoad = event.target.dataset.densityRoad;
    if (densityRoad) {
        const current = (state.density || {})[densityRoad] || 1;
        const delta = Number(event.target.dataset.densityDelta || 0);
        const next = Math.max(1, Math.min(9, current + delta));
        callApi(`/api/density/${densityRoad}/${next}`);
        return;
    }
    const scenario = event.target.dataset.scenario;
    if (scenario) {
        callApi(`/api/scenario/${scenario}`);
    }
});

window.addEventListener("resize", () => {
    resizeCanvas();
    draw();
    drawTrendChart();
    drawGraphModel();
});

function pollDelay() {
    if (document.hidden || !state.running) {
        return IDLE_POLL_MS;
    }
    return ACTIVE_POLL_MS;
}

async function pollLoop() {
    await update();
    setTimeout(pollLoop, pollDelay());
}

function startPolling() {
    if (pollingStarted) return;
    pollingStarted = true;
    pollLoop();
}

resizeCanvas();
startPolling();
