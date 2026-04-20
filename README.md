# Smart Traffic Signal Optimization

A Flask-based traffic signal simulation that applies graph coloring from Discrete Mathematics to create safe, conflict-free traffic phases for a four-way intersection.

## Features

- Graph coloring based signal phase generation
- Four-way intersection simulation for North, South, East, and West roads
- Adaptive green signal timing based on traffic density
- Visible vehicle queues at red signals
- Cars already moving continue clearing the road after a signal change
- Road-wise queue and density display
- Manual road density controls
- Emergency road priority controls
- **NEW:** Visual conflict graph representation with real-time coloring
- **NEW:** Emergency vehicle simulation with temporary signal override
- **NEW:** Throughput history chart for performance analysis
- Conflict graph and graph-coloring phase display
- Simulation modes for normal, heavy, random, and balanced traffic
- Average waiting time metric
- Current phase explanation connected to graph coloring
- Live metrics for cars passed, throughput, and efficiency
- Start, stop, and reset controls

## Discrete Mathematics Concept

Each road is represented as a vertex in a graph. Conflicting roads are connected by edges. The project uses greedy graph coloring through `networkx` so adjacent/conflicting roads do not receive the same color.

Each graph color becomes a traffic signal phase. Roads in the same phase can safely receive green signals together.

## How To Run

1. Ensure you have Python 3.8 or higher installed.
2. Create and activate a virtual environment.
3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Start the app:

```bash
python IA2_DM.py
```

5. Open the app in your browser:

```text
http://127.0.0.1:5000
```
