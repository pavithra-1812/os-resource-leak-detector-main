# Automated OS Resource Leak Detection and Recovery System

A browser-friendly Python project scaffold for developing and demonstrating resource-leak detection using simulated process data first.

## Important scope note
The starter version intentionally uses **simulated data**. It does not inspect or repair processes on your personal computer. If run in a hosted cloud environment, any real process monitoring would describe the cloud container, not your laptop.

## Project roadmap
1. Build and test simulated process data.
2. Implement a configurable detection rule.
3. Demonstrate simulated recovery and validate before/after values.
4. Add a Streamlit dashboard and charts.
5. Add optional real-process observation of the environment where the app is running, with clear labels and no automatic termination.

## Folder structure
```text
os_resource_leak_detector/
├── app.py                 # Streamlit dashboard entry point (starter)
├── simulator.py           # Simulated process data (starter)
├── detector.py            # Detection rules (starter)
├── recovery.py            # Simulated recovery (starter)
├── requirements.txt       # Python dependencies
├── .gitignore
├── README.md
├── data/
│   └── .gitkeep
├── logs/
│   └── .gitkeep
└── tests/
    ├── __init__.py
    └── test_detector.py
```

## Run in a Python-enabled browser workspace
Open a terminal in your cloud VS Code workspace and run:

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

If the workspace supports forwarded ports, open the forwarded port for Streamlit (usually 8501).

## What is implemented now?
- A small, clearly labelled simulation.
- A starter detection rule that looks for sustained growth across recent samples.
- A simulated reset action.
- A basic Streamlit UI to experiment with threshold settings.

This is a scaffold for learning, not a finished or validated detector. Detection thresholds are illustrative and must be tuned through tests.

## Suggested first experiment
1. Run the app.
2. Select `Process_B` in the dashboard.
3. Observe the increasing memory series.
4. Change the threshold and minimum consecutive increases.
5. Trigger simulated recovery and compare the value before and after.
6. Run the tests with `python -m pytest`.

