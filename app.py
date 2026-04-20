"""
Smart Traffic Signal Optimization using Graph Coloring

This application simulates a four-way traffic intersection where signal phases
are determined by graph coloring algorithms. Each road is a vertex, and conflicting
roads (those that cannot have green lights simultaneously) are connected by edges.

The greedy coloring algorithm assigns colors (phases) such that no two adjacent
vertices share the same color. Each color becomes a traffic signal phase.
"""

from flask import Flask, jsonify, render_template
import networkx as nx
import random
import threading
import time

app = Flask(__name__)

CAR_SPEED = 1.7
PASS_PROGRESS = 85
EXIT_PROGRESS = 170
SPAWN_INTERVAL_TICKS = 20
MIN_DENSITY = 1
MAX_DENSITY = 9
ROADS = ("North", "South", "East", "West")
CONFLICTS = (("North", "East"), ("North", "West"), ("South", "East"), ("South", "West"))
MODES = {
    "normal": "Normal Traffic",
    "heavy": "Heavy Traffic",
    "random": "Random Traffic",
    "balanced": "Balanced Traffic",
}


def is_waiting(car):
    return not car["passed"] and car["progress"] <= 0


class Sim:
    def __init__(self):
        self.lock = threading.Lock()
        self.mode = "normal"
        self.reset()

    def reset(self, mode=None):
        if mode in MODES:
            self.mode = mode

        graph = nx.Graph()
        graph.add_nodes_from(ROADS)
        graph.add_edges_from(CONFLICTS)
        coloring = nx.coloring.greedy_color(graph)

        self.roads = list(ROADS)
        self.conflicts = list(CONFLICTS)
        self.phases = {}
        for road, color in coloring.items():
            self.phases.setdefault(color, []).append(road)
        self.phase_keys = list(self.phases.keys())

        self.cars = []
        self.cars_passed = 0
        self.spawn_timer = 0
        self.density = self.make_density(self.mode)
        self.current_phase_index = 0
        self.last_switch = time.time()
        self.running = False
        self.car_id_counter = 0
        self.start_time = None
        self.paused_remaining = None
        self.priority_road = None
        self.priority_message = "No priority active"
        self.total_wait_time = 0.0
        self.wait_samples = 0
        self.emergency_active = False
        self.emergency_road = None
        self.emergency_until = 0

    def make_density(self, mode):
        if mode == "heavy":
            return {road: random.randint(6, MAX_DENSITY) for road in self.roads}
        if mode == "random":
            return {road: random.randint(MIN_DENSITY, MAX_DENSITY) for road in self.roads}
        if mode == "balanced":
            return {road: 5 for road in self.roads}
        return {road: random.randint(2, 5) for road in self.roads}

    def drift_density(self):
        if self.mode == "balanced":
            return dict(self.density)
        if self.mode == "random":
            return dict(self.density)  # Keep random density fixed

        low, high = (6, MAX_DENSITY) if self.mode == "heavy" else (MIN_DENSITY, 5)
        return {
            road: max(low, min(high, self.density[road] + random.choice([-1, 0, 1])))
            for road in self.roads
        }

    def current_active_roads(self):
        current_phase = self.phase_keys[self.current_phase_index]
        return current_phase, self.phases[current_phase]

    def current_delay(self, active_roads):
        return 3 + max(self.density[road] for road in active_roads)

    def update(self):
        with self.lock:
            if not self.running:
                return

            if self.spawn_timer % SPAWN_INTERVAL_TICKS == 0:
                self.spawn_car()
            self.spawn_timer += 1

            _, active_roads = self.current_active_roads()
            delay = self.current_delay(active_roads)

            if time.time() - self.last_switch > delay:
                if not (self.emergency_active and time.time() < self.emergency_until):
                    self.current_phase_index = (self.current_phase_index + 1) % len(self.phase_keys)
                    self.last_switch = time.time()
                    self.priority_road = None
                    self.priority_message = "No priority active"
                    self.density = self.drift_density()
                    _, active_roads = self.current_active_roads()

            now = time.time()
            for car in self.cars:
                can_move = car["road"] in active_roads or car["progress"] > 0
                if can_move:
                    if car["progress"] <= 0 and not car["wait_recorded"]:
                        self.total_wait_time += now - car["waiting_since"]
                        self.wait_samples += 1
                        car["wait_recorded"] = True
                    car["progress"] += CAR_SPEED

                if not car["passed"] and car["progress"] >= PASS_PROGRESS:
                    self.cars_passed += 1
                    car["passed"] = True

            self.cars = [car for car in self.cars if car["progress"] < EXIT_PROGRESS]

    def spawn_car(self):
        weights = [self.density[road] for road in self.roads]
        road = random.choices(self.roads, weights=weights, k=1)[0]
        self.cars.append({
            "id": self.car_id_counter,
            "road": road,
            "progress": 0,
            "passed": False,
            "color": random.choice(["#ec4899", "#10b981", "#f59e0b", "#0ea5e9", "#f43f5e"]),
            "waiting_since": time.time(),
            "wait_recorded": False,
        })
        self.car_id_counter += 1

    def get_state(self):
        with self.lock:
            current_phase, active_roads = self.current_active_roads()
            active_roads = list(active_roads)
            inactive_roads = [road for road in self.roads if road not in active_roads]
            delay = self.current_delay(active_roads)

            if self.running:
                remaining = int(delay - (time.time() - self.last_switch))
            elif self.paused_remaining is not None:
                remaining = int(self.paused_remaining)
            else:
                remaining = int(delay)

            queue_length = sum(1 for car in self.cars if is_waiting(car))
            queue_by_road = {
                road: sum(1 for car in self.cars if car["road"] == road and is_waiting(car))
                for road in self.roads
            }
            elapsed_time = round(time.time() - self.start_time, 1) if self.start_time else 0
            throughput = round((self.cars_passed / elapsed_time) * 60, 1) if elapsed_time > 0 else 0
            average_wait = round(self.total_wait_time / self.wait_samples, 1) if self.wait_samples else 0
            efficiency, efficiency_score = self.performance(queue_length, throughput)

            return {
                "cars": [self.car_snapshot(car) for car in self.cars],
                "cars_passed": self.cars_passed,
                "queue_length": queue_length,
                "queue_by_road": queue_by_road,
                "current_phase": current_phase,
                "active_roads": active_roads,
                "inactive_roads": inactive_roads,
                "remaining_time": max(0, remaining),
                "phase_duration": delay,
                "density": dict(self.density),
                "conflicts": [list(edge) for edge in self.conflicts],
                "phase_groups": {str(phase): list(roads) for phase, roads in self.phases.items()},
                "phase_explanation": self.phase_explanation(active_roads, inactive_roads),
                "priority_road": self.priority_road,
                "priority_message": self.priority_message,
                "chromatic_number": len(self.phase_keys),
                "mode": self.mode,
                "mode_label": MODES[self.mode],
                "modes": MODES,
                "running": self.running,
                "efficiency": efficiency,
                "efficiency_score": efficiency_score,
                "elapsed_time": elapsed_time,
                "throughput": throughput,
                "average_wait": average_wait,
            }

    def car_snapshot(self, car):
        return {
            "id": car["id"],
            "road": car["road"],
            "progress": car["progress"],
            "passed": car["passed"],
            "color": car["color"],
        }

    def performance(self, queue_length, throughput):
        if throughput >= 45 and queue_length <= 5:
            return "Excellent", 95
        if throughput >= 30 and queue_length <= 8:
            return "Very Good", 80
        if throughput >= 18 or self.cars_passed > 20:
            return "Good", 65
        if self.running:
            return "Moderate", 45
        return "Ready", 20

    def phase_explanation(self, active_roads, inactive_roads):
        green = " + ".join(active_roads)
        red = " + ".join(inactive_roads)
        return (
            f"{green} are green because they share a graph-coloring phase and do not conflict. "
            f"{red} stay red because each has a conflict edge with at least one active road."
        )

    def start(self):
        with self.lock:
            if not self.running:
                self.running = True
                now = time.time()
                if self.paused_remaining is not None:
                    _, active_roads = self.current_active_roads()
                    delay = self.current_delay(active_roads)
                    self.last_switch = now - max(0, delay - self.paused_remaining)
                    self.paused_remaining = None
                else:
                    self.last_switch = now
                if self.start_time is None:
                    self.start_time = self.last_switch

    def stop(self):
        with self.lock:
            if self.running:
                _, active_roads = self.current_active_roads()
                delay = self.current_delay(active_roads)
                self.paused_remaining = max(0, delay - (time.time() - self.last_switch))
            self.running = False

    def set_density(self, road, value):
        with self.lock:
            if road not in self.roads:
                return False
            self.density[road] = max(MIN_DENSITY, min(MAX_DENSITY, value))
            return True

    def set_mode(self, mode):
        with self.lock:
            if mode not in MODES:
                return False
            self.mode = mode
            self.density = self.make_density(mode)
            self.priority_road = None
            self.priority_message = f"{MODES[mode]} mode active"
            self.last_switch = time.time()
            self.paused_remaining = None
            return True

    def prioritize(self, road):
        with self.lock:
            if road not in self.roads:
                return False
            for index, phase in enumerate(self.phase_keys):
                if road in self.phases[phase]:
                    self.current_phase_index = index
                    self.last_switch = time.time()
                    self.paused_remaining = None
                    self.priority_road = road
                    self.priority_message = f"{road} priority active"
                    return True
            return False

    def trigger_emergency(self):
        with self.lock:
            if self.emergency_active:
                return
            road = random.choice(self.roads)
            self.emergency_active = True
            self.emergency_road = road
            self.emergency_until = time.time() + 10  # 10 seconds
            self.prioritize(road)
            self.priority_message = f"Emergency: {road} priority for 10s"


sim = Sim()


def sim_loop():
    while True:
        sim.update()
        time.sleep(0.033)


threading.Thread(target=sim_loop, daemon=True).start()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/state")
def get_state():
    return jsonify(sim.get_state())


@app.route("/api/start")
def start():
    sim.start()
    return jsonify({"ok": True})


@app.route("/api/stop")
def stop():
    sim.stop()
    return jsonify({"ok": True})


@app.route("/api/reset")
def reset():
    with sim.lock:
        sim.reset()
    return jsonify({"ok": True})


@app.route("/api/density/<road>/<int:value>")
def set_density(road, value):
    return jsonify({"ok": sim.set_density(road, value)})


@app.route("/api/priority/<road>")
def set_priority(road):
    return jsonify({"ok": sim.prioritize(road)})


@app.route("/api/mode/<mode>")
def set_mode(mode):
    return jsonify({"ok": sim.set_mode(mode)})


@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500
