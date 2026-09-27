# Autonomous Job Seeker

A Python desktop application for browser-assisted LinkedIn job searches, application form workflows, CV text extraction, and local activity tracking. It uses Playwright, asyncio, a CLI, and a Tk GUI.

This repository is an MVP. Browser selectors and provider availability depend on external services. The audit and remaining implementation limits are documented in [AUDIT_REPORT.md](AUDIT_REPORT.md). Architecture diagrams are in [ARCHITECTURE.md](ARCHITECTURE.md).

## Setup

Python **3.12+** is required. Tk/Tcl must be included in your Python installation for GUI mode (for example, `python3-tk` on Debian/Ubuntu).

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Linux/macOS:
# source .venv/bin/activate
python -m pip install -r requirements.lock
python -m playwright install chromium
```

For the GUI and development checks, install the complete pinned environment:

```bash
python -m pip install -r requirements-dev.lock
```

`requirements.txt` lists direct runtime dependencies; `requirements.lock` pins their transitive dependencies. GUI-only additions are listed in `requirements-gui.txt`. The optional Streamlit dashboard has a separate `requirements-dashboard.txt`; it is not required to launch the application.

Copy `.env.example` to `.env` and configure the settings you use:

```dotenv
BROWSER_TYPE=chromium
BROWSER_HEADLESS=false
DATA_DIR=./data
TELEMETRY_ENABLED=false
LINKEDIN_AUTO_APPLY=false
LINKEDIN_JOB_SEARCH_LIMIT=50
```

Leave `BROWSER_TYPE` empty to select an installed Edge/Chrome/Firefox browser interactively. Edge/Chrome use their installed browser channels; Chromium/Firefox browser binaries can be installed with Playwright. Sign in using the browser. Automated credential entry is incomplete.

Run from the repository root:

```bash
python main.py
```

## Operation

- **Automatic mode** asks for a job title and location, then runs the search workflow. It no longer uses hard-coded job criteria.
- **Interactive CLI** supports `start`, `search "Engineer" "Dubai"`, `pause`, `resume`, `stop`, `status`, `config`, `help`, and `quit`. A search runs in the background so pause/stop remain usable. `config` describes how to change `.env`; it does not claim to save arbitrary options.
- **GUI** provides search criteria, start/pause/resume/stop, delay and auto-pause controls, activity views, and CV selection/preview. Browser operations and Tk updates share one event loop on the main thread.

Bulk application actions require `LINKEDIN_AUTO_APPLY=true`. Required form answers and consent must be supplied explicitly; the application does not invent answers or automatically tick consent fields. A click alone is never recorded as a successful application: a fresh confirmation is required. Ambiguous submission failures are not automatically retried.

Programmatic form workflows accept `settings['form_data']` and explicit field mappings. CV parsing extracts text from PDF, DOCX, and TXT files (up to 5 MB); it does not infer a complete contact profile from arbitrary CV text. Job records distinguish applied, redirected, skipped, and failed outcomes.

## Data and privacy

`DATA_DIR` controls local storage. Profiles, CV text, logs, browser sessions, and activity history remain local files. Treat that directory as personal data: profile storage is plaintext, and concurrent application processes should use different directories. File updates are atomic and serialized within one process.

Telemetry is local and can be disabled with `TELEMETRY_ENABLED=false`. New diagnostic events redact recognized credentials and form payloads. Existing logs are preserved; the audit does not retroactively scrub them. Never commit `.env`, browser profiles, or personal data.

## Model integration

Optional OpenAI-compatible providers use isolated asynchronous SDK clients. Configure the provider credentials you actually use in `.env`; API calls are not needed for ordinary browser setup or the offline test suite. `MODEL_BOX_ENDPOINT` is a base URL such as `https://api.model.box/v1`, not a `/chat/completions` URL.

Model identifiers in the repository are examples from the original MVP and are not a guarantee of current provider availability. Provider errors are reported as errors. The vision wrapper invokes the configured provider instead of fabricating a successful response. See [the official SDK documentation](https://developers.openai.com/api/docs/libraries).

## Validation

```bash
python -m pip install -r requirements-dev.lock
python -m pytest -q
python -m ruff check --select F821,F822,F823,E9 .
node --test tests/test_extension_audit.cjs
python -m pip_audit -r requirements-dev.lock --no-deps --disable-pip
npm audit --package-lock-only
```

GUI tests are opt-in and require an available display:

```bash
python -m pytest --run-gui -q
# Linux CI:
# xvfb-run -a python -m pytest --run-gui -q
```

The `--run-live` option explicitly enables the live LinkedIn/vision diagnostic; it requires a browser, provider credentials, and may incur API charges. It is excluded from ordinary tests and CI. Regression tests use mocks and synthetic data; they do not log in, send applications, or call paid models.

GitHub CI checks Python behavior, GUI components, extension message handling, syntax/name errors, and both dependency trees. Release automation runs only on release branch pushes after these checks pass. Release tooling requires Node **22.14+ or 24.10+**; CI uses Node 24.19.

## Implementation limits

- Live LinkedIn layouts and real application submissions need account-specific validation.
- LLM CV enrichment, advanced job matching, and several CAPTCHA provider/token-injection paths remain incomplete; these are not production features.
- The browser extension is a prototype: its manifest and native messaging host are absent. Message-handling tests do not make it installable.
- The dashboard is optional; its analytical core is tested, but a full hosted dashboard deployment is outside the desktop workflow.

## Project

Author: Zouhair Mudakka ([GitHub](https://github.com/ZouhairMudakka)).

Licensed under Apache License 2.0; see [LICENSE](LICENSE). The audited upstream baseline was release **2.2.0**, commit `47ed00b746cd59f4881eee3268ef3e4c6e6ac71c`.
