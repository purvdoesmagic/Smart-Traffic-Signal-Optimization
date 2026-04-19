from flask import Flask, jsonify
import networkx as nx
import random
import threading
import time

app = Flask(__name__)

CAR_SPEED = 1.7
PASS_PROGRESS = 85
EXIT_PROGRESS = 170
SPAWN_INTERVAL_TICKS = 20

def is_waiting(car):
    return not car['passed'] and car['progress'] <= 0

class Sim:
    def __init__(self):
        self.lock = threading.Lock()
        self.reset()

    def reset(self):
        self.roads = ["North", "South", "East", "West"]
        G = nx.Graph()
        G.add_nodes_from(self.roads)
        G.add_edges_from([("North", "East"), ("North", "West"), ("South", "East"), ("South", "West")])
        coloring = nx.coloring.greedy_color(G)
        self.phases = {}
        for r, c in coloring.items():
            self.phases.setdefault(c, []).append(r)
        self.phase_keys = list(self.phases.keys())
        self.cars = []
        self.cars_passed = 0
        self.spawn_timer = 0
        self.density = {r: random.randint(1, 5) for r in self.roads}
        self.current_phase_index = 0
        self.last_switch = time.time()
        self.running = False
        self.car_id_counter = 0
        self.start_time = None
        self.paused_remaining = None

    def update(self):
        with self.lock:
            if not self.running:
                return
            if self.spawn_timer % SPAWN_INTERVAL_TICKS == 0:
                self.spawn_car()
            self.spawn_timer += 1

            current_phase = self.phase_keys[self.current_phase_index]
            active_roads = self.phases[current_phase]
            delay = 3 + max(self.density[r] for r in active_roads)

            if time.time() - self.last_switch > delay:
                self.current_phase_index = (self.current_phase_index + 1) % len(self.phase_keys)
                self.last_switch = time.time()
                self.density = {r: random.randint(1, 5) for r in self.roads}

            for car in self.cars:
                if car['road'] in active_roads or car['progress'] > 0:
                    car['progress'] += CAR_SPEED
                if not car['passed'] and car['progress'] >= PASS_PROGRESS:
                    self.cars_passed += 1
                    car['passed'] = True

            self.cars = [c for c in self.cars if c['progress'] < EXIT_PROGRESS]

    def spawn_car(self):
        self.cars.append({
            'id': self.car_id_counter,
            'road': random.choice(self.roads),
            'progress': 0,
            'passed': False,
            'color': random.choice(['#FF6B9D', '#00D96F', '#FFD700', '#64C8FF', '#FF6348'])
        })
        self.car_id_counter += 1

    def get_state(self):
        with self.lock:
            current_phase = self.phase_keys[self.current_phase_index]
            active_roads = list(self.phases[current_phase])
            inactive_roads = [road for road in self.roads if road not in active_roads]
            delay = 3 + max(self.density[r] for r in active_roads)
            if self.running:
                remaining = int(delay - (time.time() - self.last_switch))
            elif self.paused_remaining is not None:
                remaining = int(self.paused_remaining)
            else:
                remaining = int(delay)
            if self.cars_passed > 60:
                efficiency = "Excellent"
                efficiency_score = 95
            elif self.cars_passed > 40:
                efficiency = "Very Good"
                efficiency_score = 80
            elif self.cars_passed > 25:
                efficiency = "Good"
                efficiency_score = 65
            elif self.cars_passed > 10:
                efficiency = "Moderate"
                efficiency_score = 45
            else:
                efficiency = "Poor"
                efficiency_score = 20
            queue_length = sum(1 for car in self.cars if is_waiting(car))
            queue_by_road = {
                road: sum(1 for car in self.cars if car['road'] == road and is_waiting(car))
                for road in self.roads
            }
            elapsed_time = round(time.time() - self.start_time, 1) if self.start_time else 0
            throughput = round((self.cars_passed / elapsed_time) * 60, 1) if elapsed_time > 0 else 0
            return {
                'cars': [dict(car) for car in self.cars],
                'cars_passed': self.cars_passed,
                'queue_length': queue_length,
                'queue_by_road': queue_by_road,
                'current_phase': current_phase,
                'active_roads': active_roads,
                'inactive_roads': inactive_roads,
                'remaining_time': max(0, remaining),
                'phase_duration': delay,
                'density': dict(self.density),
                'running': self.running,
                'efficiency': efficiency,
                'efficiency_score': efficiency_score,
                'elapsed_time': elapsed_time,
                'throughput': throughput
            }

    def start(self):
        with self.lock:
            if not self.running:
                self.running = True
                now = time.time()
                if self.paused_remaining is not None:
                    current_phase = self.phase_keys[self.current_phase_index]
                    active_roads = self.phases[current_phase]
                    delay = 3 + max(self.density[r] for r in active_roads)
                    self.last_switch = now - max(0, delay - self.paused_remaining)
                    self.paused_remaining = None
                else:
                    self.last_switch = now
                if self.start_time is None:
                    self.start_time = self.last_switch

    def stop(self):
        with self.lock:
            if self.running:
                current_phase = self.phase_keys[self.current_phase_index]
                active_roads = self.phases[current_phase]
                delay = 3 + max(self.density[r] for r in active_roads)
                self.paused_remaining = max(0, delay - (time.time() - self.last_switch))
            self.running = False

sim = Sim()

def sim_loop():
    while True:
        sim.update()
        time.sleep(0.033)

threading.Thread(target=sim_loop, daemon=True).start()

HTML = '''<!DOCTYPE html>
<html>
<head>
    <title>Traffic Optimization</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { background: linear-gradient(135deg, #0a0e27 0%, #1a1f3a 100%); color: #fff; font-family: 'Segoe UI', Arial, sans-serif; display: flex; flex-direction: column; height: 100vh; overflow: hidden; }

        header {
            background: linear-gradient(90deg, #0ff, #00d9ff, #0ff);
            background-size: 200% 200%;
            animation: gradientShift 3s ease infinite;
            padding: 20px; text-align: center; box-shadow: 0 8px 32px rgba(0, 255, 255, 0.3);
        }

        @keyframes gradientShift {
            0%, 100% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
        }

        h1 { color: #000; font-size: 2.5em; margin: 0; font-weight: 900; text-shadow: 0 2px 4px rgba(0, 0, 0, 0.2); letter-spacing: 2px; }

        .main { display: grid; grid-template-columns: 1.2fr 0.8fr; gap: 15px; padding: 15px; flex: 1; overflow: hidden; }

        .canvas-container { display: flex; flex-direction: column; gap: 12px; }
        canvas { background: linear-gradient(45deg, #000a1a 0%, #001a33 100%); border: 4px solid #00ffff; border-radius: 8px; flex: 1; box-shadow: 0 0 30px rgba(0, 255, 255, 0.4), inset 0 0 20px rgba(0, 255, 255, 0.1); }

        .controls { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }
        button {
            padding: 16px; border: 3px solid #0ff; font-weight: bold; cursor: pointer; border-radius: 8px; font-size: 1.1em;
            transition: all 0.3s; text-transform: uppercase; letter-spacing: 1px; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
        }
        .start { background: linear-gradient(135deg, #0f0, #00ff00); color: #000; }
        .stop { background: linear-gradient(135deg, #f00, #ff3333); color: #fff; }
        .reset { background: linear-gradient(135deg, #ffa500, #ffb833); color: #000; }
        button:hover:not(:disabled) { transform: scale(1.05) translateY(-2px); box-shadow: 0 8px 25px rgba(0, 255, 255, 0.5); }
        button:active:not(:disabled) { transform: scale(0.98); }
        button:disabled { opacity: 0.4; cursor: not-allowed; }

        .sidebar { display: flex; flex-direction: column; gap: 12px; overflow-y: auto; padding-right: 8px; }
        .sidebar::-webkit-scrollbar { width: 8px; }
        .sidebar::-webkit-scrollbar-track { background: rgba(0, 255, 255, 0.1); border-radius: 10px; }
        .sidebar::-webkit-scrollbar-thumb { background: #0ff; border-radius: 10px; }

        .panel {
            background: linear-gradient(135deg, rgba(10, 30, 60, 0.8), rgba(20, 50, 100, 0.8));
            border: 3px solid #0ff; border-radius: 10px; padding: 16px;
            box-shadow: 0 8px 32px rgba(0, 255, 255, 0.2), inset 0 1px 1px rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
        }

        .panel h2 { color: #0ff; font-size: 1.2em; margin-bottom: 14px; display: flex; align-items: center; gap: 8px; text-transform: uppercase; letter-spacing: 1px; }

        .stat { margin-bottom: 10px; padding: 12px; background: rgba(0, 0, 0, 0.3); border-left: 4px solid #00ff88; border-radius: 5px; }
        .label { font-size: 0.75em; color: #88ccff; text-transform: uppercase; margin-bottom: 4px; font-weight: 600; letter-spacing: 0.5px; }
        .value { font-size: 2em; font-weight: 900; color: #00ff88; text-shadow: 0 0 10px rgba(0, 255, 136, 0.5); }
        .value.yellow { color: #ffff00; text-shadow: 0 0 10px rgba(255, 255, 0, 0.5); }

        .perf-rating {
            font-size: 1.4em; font-weight: 900; margin: 10px 0 12px 0; padding: 12px;
            border-radius: 8px; text-align: center; letter-spacing: 1px;
        }
        .rating-excellent { background: rgba(0, 255, 136, 0.2); color: #00ff88; border: 2px solid #00ff88; }
        .rating-good { background: rgba(255, 255, 0, 0.2); color: #ffff00; border: 2px solid #ffff00; }
        .rating-moderate { background: rgba(255, 165, 0, 0.2); color: #ffa500; border: 2px solid #ffa500; }
        .rating-poor { background: rgba(255, 51, 51, 0.2); color: #ff3333; border: 2px solid #ff3333; }

        .info-box { background: rgba(0, 0, 0, 0.4); padding: 10px; border-radius: 6px; font-size: 0.9em; color: #aaffff; line-height: 1.6; border-left: 3px solid #0ff; }

        .road-status { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 8px; }
        .road-item { padding: 10px; background: rgba(0, 0, 0, 0.3); border-radius: 5px; font-size: 0.9em; display: grid; gap: 4px; }
        .road-name { font-weight: 800; letter-spacing: 0.5px; }
        .road-meta { color: #b8d8ff; font-size: 0.85em; }
        .road-active { border-left: 3px solid #00ff88; }
        .road-inactive { border-left: 3px solid #ff3333; }
        .stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        .stat.compact { margin-bottom: 0; min-height: 88px; }
        .wide-stat { grid-column: 1 / -1; }
        .status-pill { color: #00ff88; font-weight: 900; font-size: 1.05em; line-height: 1.4; }
        .red-pill { color: #ff7777; }
        .countdown-track { height: 12px; background: rgba(0, 0, 0, 0.45); border: 1px solid rgba(0, 255, 255, 0.55); border-radius: 8px; overflow: hidden; margin-top: 8px; }
        .countdown-fill { height: 100%; width: 0%; background: linear-gradient(90deg, #00ff88, #ffff00); transition: width 0.2s ease; }
        .summary-line { color: #d8f8ff; font-size: 0.95em; line-height: 1.6; }
    </style>
</head>
<body>
    <header>
        <h1>SMART TRAFFIC SIGNAL OPTIMIZATION</h1>
    </header>
    <div class="main">
        <div class="canvas-container">
            <canvas id="c"></canvas>
            <div class="controls">
                <button class="start" id="s" onclick="start()">START</button>
                <button class="stop" id="t" onclick="stop()" disabled>STOP</button>
                <button class="reset" id="r" onclick="reset()">RESET</button>
            </div>
        </div>
        <div class="sidebar">
            <div class="panel">
                <h2>LIVE STATUS</h2>
                <div class="stat-grid">
                    <div class="stat compact"><div class="label">Current Phase</div><div class="value yellow" id="phase">-</div></div>
                    <div class="stat compact"><div class="label">Signal Countdown</div><div class="value yellow" id="sig">-s</div></div>
                    <div class="stat compact"><div class="label">Queue Length</div><div class="value" id="cars">0</div></div>
                    <div class="stat compact"><div class="label">Cars Passed</div><div class="value" id="pass">0</div></div>
                    <div class="stat compact wide-stat">
                        <div class="label">Green Roads</div>
                        <div class="status-pill" id="green-roads">-</div>
                        <div class="label" style="margin-top: 8px;">Red Roads</div>
                        <div class="status-pill red-pill" id="red-roads">-</div>
                        <div class="countdown-track"><div class="countdown-fill" id="phase-fill"></div></div>
                    </div>
                </div>
            </div>

            <div class="panel">
                <h2>PERFORMANCE RATING</h2>
                <div class="perf-rating" id="perf-rating">-</div>
                <div class="stat-grid">
                    <div class="stat compact"><div class="label">Efficiency Score</div><div class="value yellow" id="eff">0%</div></div>
                    <div class="stat compact"><div class="label">Throughput</div><div class="value" id="throughput">0</div></div>
                </div>
            </div>

            <div class="panel">
                <h2>ROAD-WISE TRAFFIC</h2>
                <div class="road-status" id="road-status">
                    <div class="road-item road-active"><span class="road-name">North</span><span class="road-meta">Queue 0 | Density 0 | GREEN</span></div>
                    <div class="road-item road-inactive"><span class="road-name">South</span><span class="road-meta">Queue 0 | Density 0 | RED</span></div>
                    <div class="road-item road-inactive"><span class="road-name">East</span><span class="road-meta">Queue 0 | Density 0 | RED</span></div>
                    <div class="road-item road-inactive"><span class="road-name">West</span><span class="road-meta">Queue 0 | Density 0 | RED</span></div>
                </div>
            </div>

            <div class="panel">
                <h2>HOW IT WORKS</h2>
                <div class="info-box">
                    <div class="summary-line">Graph coloring groups non-conflicting roads into the same phase.</div>
                    <div class="summary-line">Active roads receive green together; conflicting roads stay red.</div>
                    <div class="summary-line">Signal time adapts using the highest density on the active roads.</div>
                    <div class="summary-line">Live queue and throughput show how efficiently traffic is clearing.</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        const c = document.getElementById('c');
        const ctx = c.getContext('2d');
        c.width = c.offsetWidth;
        c.height = c.offsetHeight;
        const W = c.width, H = c.height, CX = W/2, CY = H/2;
        let st = {};

        function draw() {
            ctx.fillStyle = '#000';
            ctx.fillRect(0, 0, W, H);
            ctx.fillStyle = '#0a3a3a';
            ctx.fillRect(CX - 50, 0, 100, H);
            ctx.fillRect(0, CY - 40, W, 80);

            ctx.strokeStyle = '#0a6a6a';
            ctx.lineWidth = 1;
            ctx.setLineDash([10, 10]);
            ctx.beginPath();
            ctx.moveTo(CX - 20, 0);
            ctx.lineTo(CX - 20, H);
            ctx.stroke();
            ctx.beginPath();
            ctx.moveTo(CX + 20, 0);
            ctx.lineTo(CX + 20, H);
            ctx.stroke();
            ctx.beginPath();
            ctx.moveTo(0, CY - 12);
            ctx.lineTo(W, CY - 12);
            ctx.stroke();
            ctx.beginPath();
            ctx.moveTo(0, CY + 12);
            ctx.lineTo(W, CY + 12);
            ctx.stroke();
            ctx.setLineDash([]);

            // SIGNALS AT EDGES WITH GLOW
            const r = 14;

            // NORTH
            ctx.fillStyle = (st.active_roads || []).includes('North') ? '#0f0' : '#f00';
            if ((st.active_roads || []).includes('North')) {
                ctx.shadowColor = '#0f0';
                ctx.shadowBlur = 20;
            }
            ctx.beginPath(); ctx.arc(CX, 20, r, 0, Math.PI*2); ctx.fill();
            ctx.shadowColor = 'transparent';
            ctx.strokeStyle = '#fff'; ctx.lineWidth = 2; ctx.stroke();
            ctx.fillStyle = '#ff0'; ctx.font = 'bold 18px Arial'; ctx.textAlign = 'center'; ctx.textBaseline = 'top'; ctx.fillText('N', CX, 35);

            // SOUTH
            ctx.fillStyle = (st.active_roads || []).includes('South') ? '#0f0' : '#f00';
            if ((st.active_roads || []).includes('South')) {
                ctx.shadowColor = '#0f0';
                ctx.shadowBlur = 20;
            }
            ctx.beginPath(); ctx.arc(CX, H-20, r, 0, Math.PI*2); ctx.fill();
            ctx.shadowColor = 'transparent';
            ctx.strokeStyle = '#fff'; ctx.stroke();
            ctx.fillStyle = '#ff0'; ctx.font = 'bold 18px Arial'; ctx.textBaseline = 'bottom'; ctx.fillText('S', CX, H-35);

            // WEST
            ctx.fillStyle = (st.active_roads || []).includes('West') ? '#0f0' : '#f00';
            if ((st.active_roads || []).includes('West')) {
                ctx.shadowColor = '#0f0';
                ctx.shadowBlur = 20;
            }
            ctx.beginPath(); ctx.arc(20, CY, r, 0, Math.PI*2); ctx.fill();
            ctx.shadowColor = 'transparent';
            ctx.strokeStyle = '#fff'; ctx.stroke();
            ctx.fillStyle = '#ff0'; ctx.font = 'bold 18px Arial'; ctx.textAlign = 'left'; ctx.textBaseline = 'middle'; ctx.fillText('W', 35, CY);

            // EAST
            ctx.fillStyle = (st.active_roads || []).includes('East') ? '#0f0' : '#f00';
            if ((st.active_roads || []).includes('East')) {
                ctx.shadowColor = '#0f0';
                ctx.shadowBlur = 20;
            }
            ctx.beginPath(); ctx.arc(W-20, CY, r, 0, Math.PI*2); ctx.fill();
            ctx.shadowColor = 'transparent';
            ctx.strokeStyle = '#fff'; ctx.stroke();
            ctx.fillStyle = '#ff0'; ctx.font = 'bold 18px Arial'; ctx.textAlign = 'right'; ctx.fillText('E', W-35, CY);

            function drawCar(x, y, color, vertical) {
                const width = vertical ? 16 : 26;
                const height = vertical ? 26 : 16;
                const left = x - width / 2;
                const top = y - height / 2;

                ctx.fillStyle = color;
                ctx.fillRect(left, top, width, height);

                ctx.fillStyle = 'rgba(255, 255, 255, 0.75)';
                if (vertical) {
                    ctx.fillRect(left + 3, top + 5, width - 6, 6);
                    ctx.fillRect(left + 3, top + height - 11, width - 6, 5);
                } else {
                    ctx.fillRect(left + 5, top + 3, 6, height - 6);
                    ctx.fillRect(left + width - 11, top + 3, 6, height - 6);
                }

                ctx.fillStyle = '#101827';
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

            // Cars enter from road edges, cross the junction, and exit opposite.
            if (st.cars) {
                const waitingByRoad = { North: 0, South: 0, East: 0, West: 0 };
                const activeRoads = st.active_roads || [];

                st.cars.forEach((car) => {
                    let x, y;
                    const isWaiting = !car.passed && car.progress <= 0 && !activeRoads.includes(car.road);

                    if (isWaiting) {
                        const queueIndex = waitingByRoad[car.road]++;
                        const lane = ((queueIndex % 3) - 1) * 14;
                        const row = Math.floor(queueIndex / 3);
                        const gap = 32;

                        if (car.road === 'North') {
                            x = CX - 18 + lane;
                            y = 64 + row * gap;
                            drawCar(x, y, car.color, true);
                        } else if (car.road === 'South') {
                            x = CX + 18 - lane;
                            y = H - 64 - row * gap;
                            drawCar(x, y, car.color, true);
                        } else if (car.road === 'East') {
                            x = W - 64 - row * gap;
                            y = CY - 18 + lane;
                            drawCar(x, y, car.color, false);
                        } else {
                            x = 64 + row * gap;
                            y = CY + 18 - lane;
                            drawCar(x, y, car.color, false);
                        }
                        return;
                    }

                    const p = Math.max(0, Math.min(car.progress / 170, 1));
                    const lane = ((car.id % 3) - 1) * 14;
                    const margin = 20;

                    if (car.road === 'North') {
                        x = CX - 18 + lane;
                        y = -margin + (H + margin * 2) * p;
                        drawCar(x, y, car.color, true);
                    } else if (car.road === 'South') {
                        x = CX + 18 - lane;
                        y = H + margin - (H + margin * 2) * p;
                        drawCar(x, y, car.color, true);
                    } else if (car.road === 'East') {
                        x = W + margin - (W + margin * 2) * p;
                        y = CY - 18 + lane;
                        drawCar(x, y, car.color, false);
                    } else {
                        x = -margin + (W + margin * 2) * p;
                        y = CY + 18 - lane;
                        drawCar(x, y, car.color, false);
                    }
                });
            }
        }

        async function update() {
            const res = await fetch('/api/state');
            st = await res.json();
            document.getElementById('phase').textContent = st.current_phase || '-';
            document.getElementById('sig').textContent = (st.remaining_time ?? '-') + 's';
            document.getElementById('cars').textContent = st.queue_length ?? 0;
            document.getElementById('pass').textContent = st.cars_passed || 0;
            document.getElementById('eff').textContent = st.efficiency_score || 0;
            document.getElementById('throughput').textContent = `${st.throughput || 0}`;
            document.getElementById('green-roads').textContent = (st.active_roads || []).join(' + ') || '-';
            document.getElementById('red-roads').textContent = (st.inactive_roads || []).join(' + ') || '-';
            const phaseDuration = st.phase_duration || 1;
            const remaining = st.remaining_time ?? 0;
            const phasePercent = Math.max(0, Math.min(100, (remaining / phaseDuration) * 100));
            document.getElementById('phase-fill').style.width = `${phasePercent}%`;
            document.getElementById('s').disabled = st.running;
            document.getElementById('t').disabled = !st.running;

            // Road status
            const roads = ['North', 'South', 'East', 'West'];
            const activeRoads = st.active_roads || [];
            const queues = st.queue_by_road || {};
            const density = st.density || {};
            let roadHTML = '';
            roads.forEach(road => {
                const isActive = activeRoads.includes(road);
                const status = isActive ? 'GREEN' : 'RED';
                const className = isActive ? 'road-active' : 'road-inactive';
                roadHTML += `
                    <div class="road-item ${className}">
                        <span class="road-name">${road}</span>
                        <span class="road-meta">Queue ${queues[road] ?? 0} | Density ${density[road] ?? 0} | ${status}</span>
                    </div>`;
            });
            document.getElementById('road-status').innerHTML = roadHTML;

            // Performance rating
            let rating = '-';
            let ratingClass = '';
            if (st.cars_passed > 60) {
                rating = 'EFFICIENT FLOW';
                ratingClass = 'rating-excellent';
            } else if (st.cars_passed > 40) {
                rating = 'VERY GOOD';
                ratingClass = 'rating-good';
            } else if (st.cars_passed > 25) {
                rating = 'MODERATE';
                ratingClass = 'rating-good';
            } else if (st.cars_passed > 10) {
                rating = 'CONGESTION';
                ratingClass = 'rating-moderate';
            } else if (st.running) {
                rating = 'HEAVY TRAFFIC';
                ratingClass = 'rating-poor';
            }
            const perfEl = document.getElementById('perf-rating');
            perfEl.textContent = rating;
            perfEl.className = 'perf-rating ' + ratingClass;

            draw();
        }

        async function start() { await fetch('/api/start'); }
        async function stop() { await fetch('/api/stop'); }
        async function reset() { await fetch('/api/reset'); }

        setInterval(update, 100);
        update();
    </script>
</body>
</html>'''

@app.route('/')
def index():
    return HTML

@app.route('/api/state')
def get_state():
    return jsonify(sim.get_state())

@app.route('/api/start')
def start():
    sim.start()
    return jsonify({'ok': True})

@app.route('/api/stop')
def stop():
    sim.stop()
    return jsonify({'ok': True})

@app.route('/api/reset')
def reset():
    with sim.lock:
        sim.reset()
    return jsonify({'ok': True})

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, threaded=True)
