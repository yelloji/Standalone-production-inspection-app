# Standalone Production Inspection App

Independent Windows production application for brake-disc reconstruction and
ONNX-based inspection.

The application is designed to run without Gevis AI Studio. Production models
will be imported manually as validated ONNX model packages.

## Architecture

- Electron desktop shell
- React and TypeScript frontend
- FastAPI backend
- Isolated Python processing workers
- SQLite metadata database
- Application-owned production storage

See the [documentation index](docs/README.md) and
[implementation tasks](docs/tasks/IMPLEMENTATION_TASKS.md).

## Development foundation

Requirements:

- Python 3.10
- Node.js 22.12 or newer within the supported Node 22/24 range
- npm 10 or newer

Create the Python environment:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Install JavaScript dependencies:

```powershell
npm install
```

Run quality checks:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check backend tests
.\.venv\Scripts\python.exe -m mypy backend
npm run check
```

Start development services:

```powershell
npm run dev
```

Development terminals remain visible for debugging. The future packaged
production application will start its backend and workers without console
windows and will show errors inside the application.
