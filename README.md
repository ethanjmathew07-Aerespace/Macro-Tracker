# Islander Macro Tracker

Local Flask app for tracking daily macros and syncing the Islander Dining menu into a reusable macro log.

## What changed

- `macros.json` is now a legacy import source instead of the primary database.
- The app stores meals, settings, menu snapshots, and sync history in `macro_tracker.db`.
- Dining sync now uses Playwright so a real browser session can load the Dine on Campus site before requesting menu JSON.
- If a live sync fails, the app falls back to the last cached menu snapshot instead of leaving the Dining page blank.

## Local setup

1. Create a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
python3 -m pip install -r requirements.txt
python3 -m playwright install chromium
```

3. Start the app:

```bash
python3 app.py
```

The app runs on `http://127.0.0.1:5001`.

## First run behavior

- If `macros.json` exists, the app imports its settings and meals one time into SQLite.
- New data is written to `macro_tracker.db`.
- The Dining page tries a live refresh when it opens, then keeps the result locally for fallback use.

## Tests

Run the test suite with:

```bash
pytest
```

## Docker

Build the image:

```bash
docker build -t macro-tracker .
```

Run it with a mounted data directory so the SQLite database persists:

```bash
docker run --rm -p 5001:5001 -v "$(pwd)/data:/data" macro-tracker
```

Then open `http://127.0.0.1:5001`.

## Fly.io

This repo now includes a starter [fly.toml](/Users/ethanjmathew/macro-tracker/fly.toml) and [Dockerfile](/Users/ethanjmathew/macro-tracker/Dockerfile).

Before your first deploy:

1. Install the Fly CLI and log in.
2. Replace `app = "replace-with-your-fly-app-name"` in [fly.toml](/Users/ethanjmathew/macro-tracker/fly.toml) with your real Fly app name.
3. Create the Fly app without deploying yet:

```bash
fly launch --copy-config --no-deploy
```

4. Create a persistent volume:

```bash
fly volumes create macro_tracker_data --region dfw --size 1
```

5. Deploy:

```bash
fly deploy
```

Notes:

- The database is configured to live at `/data/macro_tracker.db` on the Fly volume.
- The image uses Playwright's official Python base image so Chromium is available in the container.
- The dining hall sync may still need real-world testing after deployment because the target site can behave differently from a hosted server than it does from your laptop.
