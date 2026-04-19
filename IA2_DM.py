"""Run the Smart Traffic Signal Optimization web app."""

from app import app


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, threaded=True, use_reloader=False)
