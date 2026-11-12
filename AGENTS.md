# Repository Guidelines

## Project Structure & Module Organization

`app.py` contains the Flask routes, embedded HTML/CSS/JavaScript, translation workflow, and NVIDIA NIM client. `assets/` holds the logo and favicon; `locales/` contains JSON locale files. Python tests live at the repository root as `test_*.py`, with browser-handler tests in `test_ui_flow.js`. `outputs/` stores generated ZIP archives and is ignored by Git. Docker files and GitHub workflows define container builds and deployment.

## Build, Test, and Development Commands

- `python3 -m venv venv && source venv/bin/activate`: create and activate a local environment.
- `python -m pip install Flask openai python-dotenv pypdf pytest`: install app and test dependencies. The `Dockerfile` pins production package versions.
- `cp .env.example .env` and `python app.py`: configure a local NVIDIA key and start the app at `http://localhost:5001`.
- `python -m pytest -q`: run the complete Python suite, including pytest-style asset and security tests.
- `python -m unittest discover -v` and `node --test test_ui_flow.js`: run standard-library Python regressions and the Node UI tests separately.
- `docker compose up --build`: build and run the container on port 5000.

## Coding Style & Naming Conventions

Follow the existing four-space Python indentation and `snake_case` names for functions, variables, and test files; use `UPPER_SNAKE_CASE` for constants. Keep JavaScript consistent with the existing inline code and Node test. No formatter or linter is configured; keep edits focused and readable. Preserve JSON keys, non-string values, and supported placeholders when changing translation logic.

## Testing Guidelines

Add regression tests beside the root-level suites using `test_*.py` and `test_*` methods or functions. Mock the provider and use Flask's test client for routine tests; offline translation tests block socket connections. Add UI behavior checks to `test_ui_flow.js`. No coverage threshold is configured. Run `python test.py --live` only when intentionally checking the real provider with `NVIDIA_API_KEY` set.

## Commit & Pull Request Guidelines

Recent commits commonly use prefixes such as `fix:`, `feat:`, and `fix(ui):`; write a short, specific subject in that style. In pull requests, describe the behavior changed, relevant issue, test commands and results, and any UI screenshots when the interface changes. Note provider or deployment effects where applicable.

## Security & Configuration

Never commit `.env`, API keys, or generated files under `outputs/`. Start from `.env.example`; use environment variables for deployed secrets.
