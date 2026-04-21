# Smart Traffic Signal Optimization

A Flask-based web simulation of a four-way traffic junction that applies Discrete Mathematics to generate safe, conflict-free signal phases and improve flow visibility through live metrics.

## Overview

This project models a junction with roads `North`, `South`, `East`, and `West`.  
Unsafe simultaneous movements are represented as graph conflicts, and graph coloring is used to schedule safe green phases.

## Live Demo

https://smart-traffic-signal-optimization.vercel.app/

The app includes:

- Real-time vehicle simulation on canvas
- Adaptive phase timing based on road density
- Scenario presets and simulation modes
- Live performance indicators (queue, throughput, waiting time)
- Graph model visualization and explanation

## Key Features

- Conflict-safe signal phase generation using graph coloring
- Simulation modes: `Normal`, `Balanced`, `Heavy`, `Random`
- Scenario presets: `Peak Hour`, `School Exit`, `Event Dispersal`
- Emergency priority controls per road
- Manual density controls (`+/-`) for each direction
- Road-wise queue and density cards
- Graph model panel with live node/edge highlights
- Live metrics: phase, countdown, queue length, cars passed, throughput, average wait
- Start, Stop, Reset control workflow

## Discrete Mathematics Used

- **Sets**: finite set of roads, active/inactive road sets
- **Relations**: conflict relation between incompatible movements
- **Graph Theory**: roads as vertices, conflicts as edges
- **Graph Coloring**: safe non-conflicting phase groups
- **Finite State Transitions**: deterministic phase switching
- **Logic and Constraints**: prevent unsafe simultaneous greens
- **Counting/Cardinality**: queue lengths and throughput metrics
- **Weighted Selection**: density-based probabilistic vehicle spawning

## Tech Stack

- Python
- Flask
- NetworkX
- HTML/CSS/JavaScript (Canvas)

## Project Structure

- `app.py` - Flask backend and simulation engine
- `IA2_DM.py` - local launcher
- `templates/index.html` - UI layout
- `static/styles.css` - UI styling
- `static/app.js` - rendering and client-side logic
- `requirements.txt` - Python dependencies

## Run Locally

1. Create and activate a virtual environment
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Start the app:

```bash
python IA2_DM.py
```

4. Open:

```text
http://127.0.0.1:5000
```

## Deployment

### Recommended: Render (for smoother runtime)

This app keeps live in-memory simulation state, so a persistent web service works better than serverless for performance.

1. Go to Render dashboard and create a new **Web Service** from this GitHub repo.
2. Render will detect `render.yaml` (or use these values manually):
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app --workers 1 --threads 8 --timeout 120`
3. Deploy and open the generated Render URL.
4. Keep **Auto Deploy** enabled so every push to `main` updates your live app.

### Vercel Note

Vercel can host the project, but because this is a stateful simulation with frequent updates, performance may feel laggy compared to Render/Railway.

## Author

Developed as a Discrete Mathematics mini project.
