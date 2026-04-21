from flask import Flask, jsonify, render_template
import networkx as nx
import random
import threading
import time

app = Flask(__name__)

CAR_SPEED = 1.7
PASS_PROGRESS = 85
EXIT_PROGRESS = 170
MIN_DENSITY = 1
MAX_DENSITY = 9
MODES = {
    "normal": "Normal Traffic",
    "heavy": "Heavy Traffic",
    "random": "Random Traffic",
    "balanced": "Balanced Traffic",
}
MODE_INTENSITY = {
    "normal": "Medium",
    "heavy": "High",
    "random": "Variable",
    "balanced": "Medium",
}
SCENARIOS = {
    "peak_hour": {
        "label": "Peak Hour",
        "mode": "heavy",
        "density": {"North": 9, "South": 8, "East": 7, "West": 8},
        "description": "Office commute surge with heavy directional inflow.",
    },
    "school_exit": {
        "label": "School Exit",
        "mode": "balanced",
        "density": {"North": 6, "South": 7, "East": 5, "West": 5},
        "description": "Short burst around campus roads with moderate balance.",
    },
    "event_dispersal": {
        "label": "Event Dispersal",
        "mode": "heavy",
        "density": {"North": 3, "South": 3, "East": 3, "West": 3},
        "focus_boost": 5,
        "description": "Post-event outflow spikes on one randomly selected road.",
    },
}


def is_waiting(car):
    return not car["passed"] and car["progress"] <= 0


MODE_SPAWN_CONFIG = {
    "normal": {"interval": 17, "min_burst": 1, "max_burst": 2, "prefill": 2, "queue_cap": 4},
    "balanced": {"interval": 14, "min_burst": 1, "max_burst": 2, "prefill": 3, "queue_cap": 5},
    "random": {"interval": 12, "min_burst": 1, "max_burst": 3, "prefill": 3, "queue_cap": 5},
    "heavy": {"interval": 11, "min_burst": 2, "max_burst": 3, "prefill": 4, "queue_cap": 9},
}


class Sim:
    def __init__(self):
        self.lock = threading.Lock()
        self.mode = "normal"
        self.reset()

    def reset(self, mode=None):
        if mode in MODES:
            self.mode = mode
        # Discrete Maths (Set): finite set of traffic directions.
        self.roads = ["North", "South", "East", "West"]
        # Discrete Maths (Binary Relation): conflict relation between road pairs.
        self.conflicts = [("North", "East"), ("North", "West"), ("South", "East"), ("South", "West")]
        # Discrete Maths (Graph Theory): roads -> vertices, conflicts -> edges.
        graph = nx.Graph()
        graph.add_nodes_from(self.roads)
        graph.add_edges_from(self.conflicts)
        # Discrete Maths (Graph Coloring): group non-conflicting roads into safe phases.
        coloring = nx.coloring.greedy_color(graph)
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
        self.active_scenario = None
        self.scenario_focus_road = None
        self.total_wait_time = 0.0
        self.wait_samples = 0

    def make_density(self, mode):
        if mode == "heavy":
            return {road: random.randint(6, MAX_DENSITY) for road in self.roads}
        if mode == "random":
            return {road: random.randint(MIN_DENSITY, MAX_DENSITY) for road in self.roads}
        if mode == "balanced":
            return {road: 5 for road in self.roads}
        return {road: random.randint(2, 5) for road in self.roads}

    def drift_density(self):
        if self.active_scenario == "event_dispersal" and self.scenario_focus_road in self.roads:
            updated = {
                road: max(2, min(4, self.density[road] + random.choice([-1, 0, 1])))
                for road in self.roads
            }
            focus = self.scenario_focus_road
            updated[focus] = max(7, min(MAX_DENSITY, self.density[focus] + random.choice([0, 1])))
            return updated
        if self.mode == "balanced":
            return dict(self.density)
        if self.mode == "random":
            return self.make_density("random")
        low, high = (6, MAX_DENSITY) if self.mode == "heavy" else (MIN_DENSITY, 5)
        return {
            road: max(low, min(high, self.density[road] + random.choice([-1, 0, 1])))
            for road in self.roads
        }

    def update(self):
        with self.lock:
            if not self.running:
                return
            config = MODE_SPAWN_CONFIG[self.mode]
            if self.spawn_timer % config["interval"] == 0:
                for _ in range(random.randint(config["min_burst"], config["max_burst"])):
                    self.spawn_car()
            self.spawn_timer += 1

            current_phase = self.phase_keys[self.current_phase_index]
            active_roads = self.phases[current_phase]
            delay = 3 + max(self.density[road] for road in active_roads)

            # Discrete Maths (Finite State Transition): move to next phase state after delay.
            if time.time() - self.last_switch > delay:
                self.current_phase_index = (self.current_phase_index + 1) % len(self.phase_keys)
                self.last_switch = time.time()
                self.priority_road = None
                self.priority_message = "No priority active"
                self.density = self.drift_density()
                current_phase = self.phase_keys[self.current_phase_index]
                active_roads = self.phases[current_phase]

            now = time.time()
            for car in self.cars:
                if car["road"] in active_roads or car["progress"] > 0:
                    if car["progress"] <= 0 and not car["wait_recorded"]:
                        self.total_wait_time += now - car["waiting_since"]
                        self.wait_samples += 1
                        car["wait_recorded"] = True
                    car["progress"] += CAR_SPEED
                if not car["passed"] and car["progress"] >= PASS_PROGRESS:
                    self.cars_passed += 1
                    car["passed"] = True

            self.cars = [car for car in self.cars if car["progress"] < EXIT_PROGRESS]

    def choose_spawn_road(self):
        candidates = [road for road in self.roads if self.waiting_count(road) < self.queue_cap_for_road(road)]
        if not candidates:
            return None
        weights = []
        for road in candidates:
            weight = max(1, self.density[road])
            if self.active_scenario == "event_dispersal" and self.scenario_focus_road == road:
                weight *= 3.0
            elif self.active_scenario == "event_dispersal":
                weight *= 0.45
            weights.append(weight)
        # Discrete Maths (Weighted Probability): density-weighted random choice of incoming road.
        return random.choices(candidates, weights=weights, k=1)[0]

    def waiting_count(self, road):
        # Discrete Maths (Counting/Cardinality): number of waiting cars on a road.
        return sum(1 for car in self.cars if car["road"] == road and is_waiting(car))

    def queue_cap_for_road(self, road):
        base_cap = MODE_SPAWN_CONFIG[self.mode]["queue_cap"]
        if self.active_scenario == "event_dispersal" and self.scenario_focus_road in self.roads:
            if road == self.scenario_focus_road:
                return base_cap
            return max(3, base_cap - 4)
        return base_cap

    def spawn_car(self, road=None):
        if road in self.roads and self.waiting_count(road) < self.queue_cap_for_road(road):
            spawn_road = road
        else:
            spawn_road = self.choose_spawn_road()
        if spawn_road is None:
            return
        self.cars.append({
            "id": self.car_id_counter,
            "road": spawn_road,
            "progress": 0,
            "passed": False,
            "color": random.choice(["#FF6B9D", "#00D96F", "#FFD700", "#64C8FF", "#FF6348"]),
            "waiting_since": time.time(),
            "wait_recorded": False,
        })
        self.car_id_counter += 1

    def prefill_mode_traffic(self):
        config = MODE_SPAWN_CONFIG[self.mode]
        for _ in range(config["prefill"]):
            self.spawn_car()

    def get_state(self):
        with self.lock:
            current_phase = self.phase_keys[self.current_phase_index]
            active_roads = list(self.phases[current_phase])
            # Discrete Maths (Set Partition): roads split into active and inactive sets.
            inactive_roads = [road for road in self.roads if road not in active_roads]
            delay = 3 + max(self.density[road] for road in active_roads)
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

            # Discrete Maths (Counting): total queued cars across all roads.
            queue_length = sum(1 for car in self.cars if is_waiting(car))
            queue_by_road = {
                # Discrete Maths (Counting by subset): queued cars per road.
                road: sum(1 for car in self.cars if car["road"] == road and is_waiting(car))
                for road in self.roads
            }
            elapsed_time = round(time.time() - self.start_time, 1) if self.start_time else 0
            throughput = round((self.cars_passed / elapsed_time) * 60, 1) if elapsed_time > 0 else 0
            average_wait = round(self.total_wait_time / self.wait_samples, 1) if self.wait_samples else 0
            phase_text = " + ".join(active_roads)
            blocked_text = " + ".join(inactive_roads)
            phase_explanation = (
                f"{phase_text} are green because they share one graph-coloring phase. "
                f"{blocked_text} stay red because they conflict with at least one active road."
            )

            return {
                "cars": [
                    {
                        "id": car["id"],
                        "road": car["road"],
                        "progress": car["progress"],
                        "passed": car["passed"],
                        "color": car["color"],
                    }
                    for car in self.cars
                ],
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
                "phase_explanation": phase_explanation,
                "priority_road": self.priority_road,
                "priority_message": self.priority_message,
                "mode": self.mode,
                "mode_label": MODES[self.mode],
                "mode_intensity": MODE_INTENSITY[self.mode],
                "modes": MODES,
                "scenarios": {key: item["label"] for key, item in SCENARIOS.items()},
                "active_scenario": self.active_scenario,
                "scenario_description": (
                    (
                        f"{SCENARIOS[self.active_scenario]['description']} "
                        f"Current focus: {self.scenario_focus_road}."
                        if self.active_scenario == "event_dispersal" and self.scenario_focus_road
                        else SCENARIOS[self.active_scenario]["description"]
                    )
                    if self.active_scenario in SCENARIOS
                    else "Pick a preset to simulate a real-world traffic pattern."
                ),
                "running": self.running,
                "efficiency": efficiency,
                "efficiency_score": efficiency_score,
                "elapsed_time": elapsed_time,
                "throughput": throughput,
                "average_wait": average_wait,
            }

    def start(self):
        with self.lock:
            if not self.running:
                self.running = True
                now = time.time()
                if self.paused_remaining is not None:
                    current_phase = self.phase_keys[self.current_phase_index]
                    active_roads = self.phases[current_phase]
                    delay = 3 + max(self.density[road] for road in active_roads)
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
                delay = 3 + max(self.density[road] for road in active_roads)
                self.paused_remaining = max(0, delay - (time.time() - self.last_switch))
            self.running = False

    def set_density(self, road, value):
        with self.lock:
            if road not in self.roads:
                return False
            self.density[road] = max(MIN_DENSITY, min(MAX_DENSITY, value))
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

    def set_mode(self, mode):
        with self.lock:
            if mode not in MODES:
                return False
            self.mode = mode
            self.density = self.make_density(mode)
            self.prefill_mode_traffic()
            self.priority_road = None
            self.priority_message = f"{MODES[mode]} mode active"
            self.active_scenario = None
            self.scenario_focus_road = None
            self.last_switch = time.time()
            self.paused_remaining = None
            return True

    def apply_scenario(self, scenario_key):
        with self.lock:
            if scenario_key not in SCENARIOS:
                return False
            scenario = SCENARIOS[scenario_key]
            self.mode = scenario["mode"]
            density = {
                road: max(MIN_DENSITY, min(MAX_DENSITY, scenario["density"][road]))
                for road in self.roads
            }
            self.scenario_focus_road = None
            if scenario_key == "event_dispersal":
                self.scenario_focus_road = random.choice(self.roads)
                boost = int(scenario.get("focus_boost", 0))
                density[self.scenario_focus_road] = min(MAX_DENSITY, density[self.scenario_focus_road] + boost)
            self.density = density
            self.prefill_mode_traffic()
            self.priority_road = None
            self.priority_message = f"Scenario active: {scenario['label']}"
            self.active_scenario = scenario_key
            self.last_switch = time.time()
            self.paused_remaining = None
            return True


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


@app.route("/healthz")
def healthz():
    return jsonify({"ok": True})


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


@app.route("/api/scenario/<scenario_key>")
def set_scenario(scenario_key):
    return jsonify({"ok": sim.apply_scenario(scenario_key)})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, threaded=True)
