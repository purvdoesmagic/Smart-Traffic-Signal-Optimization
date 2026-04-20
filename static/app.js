const canvas = document.getElementById("traffic-canvas");
const ctx = canvas.getContext("2d");
const graphCanvas = document.getElementById("graph-canvas");
const graphCtx = graphCanvas.getContext("2d");
const chartCanvas = document.getElementById("throughput-chart");
const chartCtx = chartCanvas.getContext("2d");

function resizeCanvasElement(targetCanvas, targetCtx) {
    const rect = targetCanvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    targetCanvas.width = rect.width * dpr;
    targetCanvas.height = rect.height * dpr;
    targetCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
}

function resizeMainCanvas() {
    resizeCanvasElement(canvas, ctx);
}

function resizeGraphCanvas() {
    resizeCanvasElement(graphCanvas, graphCtx);
}

function resizeChartCanvas() {
    resizeCanvasElement(chartCanvas, chartCtx);
}

// Throughput history for the performance chart
let throughputHistory = [];
let state = {};

const roads = ["North", "South", "East", "West"];

function resizeCanvas() {
    resizeMainCanvas();
    const rect = canvas.getBoundingClientRect();
    canvas.style.width = rect.width + 'px';
    canvas.style.height = rect.height + 'px';
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

    ctx.fillStyle = "#0f172a";
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

function drawSignal(x, y, label, active, canvasHeight, align = "center") {
    ctx.fillStyle = active ? "#10b981" : "#ef4444";
    if (active) {
        ctx.shadowColor = "rgba(16, 185, 129, 0.6)";
        ctx.shadowBlur = 20;
    }
    ctx.beginPath();
    ctx.arc(x, y, 14, 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowColor = "transparent";
    ctx.strokeStyle = "rgba(255,255,255,0.9)";
    ctx.lineWidth = 2;
    ctx.stroke();

    const xOffset = align === "left" ? 18 : align === "right" ? -18 : 0;
    const yOffset = align === "center" ? (y > canvasHeight / 2 ? -24 : 24) : 0;
    ctx.fillStyle = "#fbbf24";
    ctx.font = "bold 18px Inter, Arial";
    ctx.textAlign = align;
    ctx.textBaseline = "middle";
    ctx.fillText(label, x + xOffset, y + yOffset);
}

function drawGraph() {
    const rect = graphCanvas.getBoundingClientRect();
    const width = rect.width;
    const height = rect.height;
    graphCtx.clearRect(0, 0, width, height);
    graphCtx.fillStyle = "#0f172a";
    graphCtx.fillRect(0, 0, width, height);

    const centerX = width / 2;
    const centerY = height / 2;
    const radius = Math.min(width, height) * 0.25;
    const nodeRadius = 15;

    const positions = {
        "North": { x: centerX, y: centerY - radius },
        "South": { x: centerX, y: centerY + radius },
        "East": { x: centerX + radius, y: centerY },
        "West": { x: centerX - radius, y: centerY }
    };

    // Draw edges
    graphCtx.strokeStyle = "#94a3b8";
    graphCtx.lineWidth = 2;
    const edges = state.conflicts || [];
    edges.forEach(([a, b]) => {
        const posA = positions[a];
        const posB = positions[b];
        graphCtx.beginPath();
        graphCtx.moveTo(posA.x, posA.y);
        graphCtx.lineTo(posB.x, posB.y);
        graphCtx.stroke();
    });

    // Draw nodes
    const activeRoads = state.active_roads || [];
    Object.entries(positions).forEach(([road, pos]) => {
        const isActive = activeRoads.includes(road);
        graphCtx.fillStyle = isActive ? "#10b981" : "#ef4444";
        graphCtx.beginPath();
        graphCtx.arc(pos.x, pos.y, nodeRadius, 0, Math.PI * 2);
        graphCtx.fill();
        graphCtx.strokeStyle = "#fff";
        graphCtx.lineWidth = 2;
        graphCtx.stroke();

        graphCtx.fillStyle = "#fff";
        graphCtx.font = "bold 12px Inter, Arial";
        graphCtx.textAlign = "center";
        graphCtx.textBaseline = "middle";
        graphCtx.fillText(road[0], pos.x, pos.y);
    });
}

function drawChart() {
    const rect = chartCanvas.getBoundingClientRect();
    const width = rect.width;
    const height = rect.height;
    chartCtx.clearRect(0, 0, width, height);
    chartCtx.fillStyle = "#0f172a";
    chartCtx.fillRect(0, 0, width, height);

    if (throughputHistory.length < 2) return;

    const maxThroughput = Math.max(...throughputHistory);
    const minThroughput = Math.min(...throughputHistory);
    const range = maxThroughput - minThroughput || 1;

    chartCtx.strokeStyle = "#10b981";
    chartCtx.lineWidth = 2;
    chartCtx.beginPath();
    throughputHistory.forEach((value, index) => {
        const x = (index / (throughputHistory.length - 1)) * width;
        const y = height - ((value - minThroughput) / range) * (height - 20) - 10;
        if (index === 0) {
            chartCtx.moveTo(x, y);
        } else {
            chartCtx.lineTo(x, y);
        }
    });
    chartCtx.stroke();

    // Labels
    chartCtx.fillStyle = "#94a3b8";
    chartCtx.font = "10px Inter, Arial";
    chartCtx.textAlign = "center";
    chartCtx.fillText("Time", width / 2, height - 5);
    chartCtx.save();
    chartCtx.translate(10, height / 2);
    chartCtx.rotate(-Math.PI / 2);
    chartCtx.fillText("Throughput", 0, 0);
    chartCtx.restore();
}

function draw() {
    const rect = canvas.getBoundingClientRect();
    const width = rect.width;
    const height = rect.height;
    const cx = width / 2;
    const cy = height / 2;

    ctx.fillStyle = "#0f172a";
    ctx.fillRect(0, 0, width, height);

    ctx.fillStyle = "#1e293b";
    ctx.fillRect(cx - 50, 0, 100, height);
    ctx.fillRect(0, cy - 40, width, 80);

    ctx.strokeStyle = "#334155";
    ctx.lineWidth = 2;
    ctx.setLineDash([10, 10]);
    ctx.beginPath();
    ctx.moveTo(cx - 20, 0);
    ctx.lineTo(cx - 20, height);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(cx + 20, 0);
    ctx.lineTo(cx + 20, height);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(0, cy - 12);
    ctx.lineTo(width, cy - 12);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(0, cy + 12);
    ctx.lineTo(width, cy + 12);
    ctx.stroke();
    ctx.setLineDash([]);

    const activeRoads = state.active_roads || [];
    drawSignal(cx, 20, "N", activeRoads.includes("North"), height);
    drawSignal(cx, height - 20, "S", activeRoads.includes("South"), height);
    drawSignal(20, cy, "W", activeRoads.includes("West"), height, "left");
    drawSignal(width - 20, cy, "E", activeRoads.includes("East"), height, "right");

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

        const progress = Math.max(0, Math.min(car.progress / 170, 1));
        const lane = ((car.id % 3) - 1) * 14;
        const margin = 20;

        if (car.road === "North") {
            x = cx - 18 + lane;
            y = -margin + (height + margin * 2) * progress;
            drawCar(x, y, car.color, true);
        } else if (car.road === "South") {
            x = cx + 18 - lane;
            y = height + margin - (height + margin * 2) * progress;
            drawCar(x, y, car.color, true);
        } else if (car.road === "East") {
            x = width + margin - (width + margin * 2) * progress;
            y = cy - 18 + lane;
            drawCar(x, y, car.color, false);
        } else {
            x = -margin + (width + margin * 2) * progress;
            y = cy + 18 - lane;
            drawCar(x, y, car.color, false);
        }
    });
}

function setText(id, value) {
    document.getElementById(id).textContent = value;
}

function renderModes() {
    const modeControls = document.getElementById("mode-controls");
    const modeEntries = Object.entries(state.modes || {});
    const existingButtons = modeControls.querySelectorAll("button[data-mode]");

    if (existingButtons.length !== modeEntries.length) {
        modeControls.innerHTML = modeEntries
            .map(([mode, label]) => {
                const activeClass = mode === state.mode ? " active" : "";
                return `<button type="button" class="mode-btn${activeClass}" data-mode="${mode}">${label}</button>`;
            })
            .join("");

        modeControls.querySelectorAll("button[data-mode]").forEach((button) => {
            button.addEventListener("click", (event) => {
                event.preventDefault();
                event.stopPropagation();
                const mode = button.dataset.mode;
                if (mode) {
                    callApi(`/api/mode/${mode}`);
                }
            });
        });
    }

    updateModeButtons();
}

function updateModeButtons() {
    const modeControls = document.getElementById("mode-controls");
    const activeMode = state.mode;
    modeControls.querySelectorAll("button[data-mode]").forEach((button) => {
        button.classList.toggle("active", button.dataset.mode === activeMode);
    });
}

function renderRoads() {
    const roadStatus = document.getElementById("road-status");
    const densityControls = document.getElementById("density-controls");

    if (!roadStatus.hasChildNodes()) {
        roadStatus.innerHTML = roads.map((road) => {
            return `
            <div class="road-item" data-road="${road}">
                <span class="road-name">${road}</span>
                <span class="road-meta" data-road-meta="${road}"></span>
            </div>`;
        }).join("");
    }

    if (!densityControls.hasChildNodes()) {
        densityControls.innerHTML = roads.map((road) => `
        <div class="density-row" data-density-row="${road}">
            <span>${road}</span>
            <button class="density-btn" data-density-road="${road}" data-density-delta="-1">-</button>
            <span class="density-value" data-density-value="${road}">${state.density?.[road] ?? 0}</span>
            <button class="density-btn" data-density-road="${road}" data-density-delta="1">+</button>
        </div>`).join("");

        densityControls.querySelectorAll("button[data-density-road]").forEach((button) => {
            button.addEventListener("click", (event) => {
                event.preventDefault();
                event.stopPropagation();
                const road = button.dataset.densityRoad;
                const delta = Number(button.dataset.densityDelta || 0);
                const current = (state.density || {})[road] || 1;
                const next = Math.max(1, Math.min(9, current + delta));
                callApi(`/api/density/${road}/${next}`);
            });
        });
    }

    updateRoadValues();
}

function updateRoadValues() {
    const queues = state.queue_by_road || {};
    const density = state.density || {};
    const activeRoads = state.active_roads || [];

    roads.forEach((road) => {
        const meta = document.querySelector(`[data-road-meta="${road}"]`);
        if (meta) {
            const isActive = activeRoads.includes(road);
            const status = isActive ? "GREEN" : "RED";
            meta.textContent = `Queue ${queues[road] ?? 0} | Density ${density[road] ?? 0} | ${status}`;
        }

        const densityValue = document.querySelector(`[data-density-value="${road}"]`);
        if (densityValue) {
            densityValue.textContent = density[road] ?? 0;
        }

        const item = document.querySelector(`[data-road="${road}"]`);
        if (item) {
            item.classList.toggle("road-active", activeRoads.includes(road));
            item.classList.toggle("road-inactive", !activeRoads.includes(road));
        }
    });
}

function renderGraphModel() {
    const phaseGroups = state.phase_groups || {};
    const phaseText = Object.keys(phaseGroups)
        .map((phase) => `Phase ${phase}: ${phaseGroups[phase].join(" + ")}`)
        .join(" | ") || "-";
    const conflictText = (state.conflicts || [])
        .map((edge) => edge.join(" - "))
        .join(", ") || "-";

    setText("chromatic-number", `Chromatic Number (χ): ${state.chromatic_number || "-"}`);
    setText("phase-groups", `Phases: ${phaseText}`);
    setText("conflict-edges", `Conflict edges: ${conflictText}`);
    setText("phase-explanation", `Current phase explanation: ${state.phase_explanation || "-"}`);
}

function renderPerformance() {
    let ratingClass = "";
    if (state.efficiency === "Excellent") {
        ratingClass = "rating-excellent";
    } else if (state.efficiency === "Very Good" || state.efficiency === "Good") {
        ratingClass = "rating-good";
    } else if (state.efficiency === "Moderate") {
        ratingClass = "rating-moderate";
    } else {
        ratingClass = "rating-poor";
    }

    const perfEl = document.getElementById("performance-rating");
    perfEl.textContent = state.efficiency || "-";
    perfEl.className = `perf-rating ${ratingClass}`;
}

async function update() {
    try {
        const response = await fetch("/api/state");
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        state = await response.json();

        setText("phase", state.current_phase ?? "-");
        setText("signal", `${state.remaining_time ?? "-"}s`);
        setText("queue", state.queue_length ?? 0);
        setText("passed", state.cars_passed || 0);
        setText("efficiency", state.efficiency_score || 0);
        setText("throughput", state.throughput || 0);
        setText("average-wait", `${state.average_wait || 0}s`);
        setText("green-roads", (state.active_roads || []).join(" + ") || "-");
        setText("red-roads", (state.inactive_roads || []).join(" + ") || "-");
        setText("priority-status", state.priority_message || "No priority active");
        setText("mode-status", `Mode: ${state.mode_label || "Normal Traffic"}`);

        const phaseDuration = state.phase_duration || 1;
        const remaining = state.remaining_time ?? 0;
        const phasePercent = Math.max(0, Math.min(100, (remaining / phaseDuration) * 100));
        document.getElementById("phase-fill").style.width = `${phasePercent}%`;

        document.getElementById("start-btn").disabled = state.running;
        document.getElementById("stop-btn").disabled = !state.running;

        // Update throughput history
        if (state.throughput !== undefined) {
            throughputHistory.push(state.throughput);
            if (throughputHistory.length > 50) {
                throughputHistory.shift();
            }
        }

        renderPerformance();
        renderModes();
        renderRoads();
        renderGraphModel();
        drawGraph();
        drawChart();
        draw();
    } catch (error) {
        console.error("Error updating state:", error);
        // Continue trying to update
    }
}

async function callApi(path) {
    try {
        const response = await fetch(path);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const result = await response.json();
        if (result.ok === false) {
            throw new Error("API call failed");
        }
        if (path.startsWith("/api/mode/")) {
            const selectedMode = path.split("/api/mode/")[1];
            if (selectedMode) {
                state.mode = selectedMode;
                state.mode_label = (state.modes || {})[selectedMode] || state.mode_label;
                renderModes();
                setText("mode-status", `Mode: ${state.mode_label || "Normal Traffic"}`);
            }
        }
        await update();
    } catch (error) {
        console.error("Error calling API:", error);
    }
}

document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("start-btn").addEventListener("click", () => callApi("/api/start"));
    document.getElementById("stop-btn").addEventListener("click", () => callApi("/api/stop"));
    document.getElementById("reset-btn").addEventListener("click", () => {
        throughputHistory = [];
        callApi("/api/reset");
    });

    document.addEventListener("click", (event) => {
        const button = event.target.closest("button");
        if (!button) {
            return;
        }

        const priorityRoad = button.dataset.priority;
        if (priorityRoad) {
            callApi(`/api/priority/${priorityRoad}`);
            return;
        }

        const densityRoad = button.dataset.densityRoad;
        if (densityRoad) {
            const current = (state.density || {})[densityRoad] || 1;
            const delta = Number(button.dataset.densityDelta || 0);
            const next = Math.max(1, Math.min(9, current + delta));
            callApi(`/api/density/${densityRoad}/${next}`);
        }
    });

    window.addEventListener("resize", () => {
        resizeCanvas();
        resizeGraphCanvas();
        resizeChartCanvas();
        drawGraph();
        drawChart();
        draw();
    });

    resizeCanvas();
    resizeGraphCanvas();
    resizeChartCanvas();
    setInterval(update, 100);
    update();
});
