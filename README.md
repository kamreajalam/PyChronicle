# PyChronicle

## AST-Powered Time-Travel Debugger for Python

PyChronicle is an interactive Python execution-history debugger designed to help developers understand how a program reached a particular state.

Instead of debugging only the final state of a program, PyChronicle records execution events, source-code locations, variable information, and execution metadata. The recorded history can then be explored through an interactive terminal-based dashboard.

---

## Overview

Debugging a program can be difficult when the final state does not clearly explain how the program reached that state.

PyChronicle addresses this problem by creating a timeline of program execution.

The system combines:

- Python AST analysis
- Runtime execution tracing
- Variable tracking
- SQLite persistence
- JSON trace support
- Interactive terminal visualization

The recorded execution history can be navigated step-by-step through the PyChronicle dashboard.

---

## Key Features

### 🔍 AST-Based Analysis

Uses Python's built-in `ast` module to analyze Python source code and identify important program structures.

### 🕵️ Runtime Execution Tracing

Uses Python's `sys.settrace()` mechanism to capture runtime execution events.

### 💾 SQLite Storage

Execution sessions and events can be stored persistently in SQLite.

### 📄 JSON Trace Support

Trace information can also be loaded from JSON files.

### 🧭 Interactive Timeline

The Textual dashboard provides a step-by-step execution timeline.

### 💻 Code Viewer

Displays the source code associated with the selected execution event.

### 🎯 Active-Line Highlighting

Highlights the relevant execution line when source information is available.

### 📊 Variable Panel

Displays variables associated with the selected execution step.

### 📝 Event Log

Displays execution information including:

- Event
- Function
- File
- Line number
- Variable changes

### ⌨️ Keyboard Navigation

Supports:

- First step
- Last step
- Dark/light theme
- Application exit

### 🧪 Automated Testing

The project includes tests for:

- Trace loading
- JSON handling
- SQLite handling
- Tracer validation
- Application integration

---

# Architecture

```text
                 Python Program
                       │
                       ▼
                ┌──────────────┐
                │  AST Parser  │
                └──────────────┘
                       │
                       ▼
                ┌──────────────┐
                │   Execution  │
                │    Tracer    │
                │ sys.settrace │
                └──────────────┘
                       │
                       ▼
                ┌──────────────┐
                │    SQLite    │
                │   Storage    │
                └──────────────┘
                       │
                       ▼
                ┌──────────────┐
                │ Trace Loader │
                └──────────────┘
                       │
                       ▼
                ┌──────────────┐
                │  Textual TUI │
                └──────────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
      Timeline     Code Viewer   Variables
                                     │
                                     ▼
                                 Event Log
````

---

# Execution Flow

The complete execution flow is:

```text
Python Source Code
        ↓
AST Analysis
        ↓
Runtime Execution
        ↓
sys.settrace()
        ↓
Execution Events
        ↓
SQLite Database
        ↓
Trace Loader
        ↓
PyChronicle Dashboard
        ↓
Timeline + Code + Variables + Events
```

---

# Technology Stack

| Technology       | Purpose                      |
| ---------------- | ---------------------------- |
| Python           | Core programming language    |
| `ast`            | Source-code analysis         |
| `sys.settrace()` | Runtime execution tracing    |
| SQLite           | Persistent execution storage |
| JSON             | Trace data support           |
| Textual          | Terminal user interface      |
| Rich             | Syntax highlighting          |
| pytest           | Automated testing            |
| Git/GitHub       | Version control              |

---

# Project Structure

```text
PyChronicle/
│
├── app.py
├── trace_loader.py
├── requirements.txt
├── README.md
│
├── src/
│   ├── __init__.py
│   ├── tracer.py
│   ├── parser.py
│   ├── storage.py
│   └── config.py
│
├── tests/
│   ├── test_trace_loader.py
│   ├── test_tracer_validation.py
│   └── test_app_integration.py
│
├── pychronicle.db
└── trace_output.json
```

---

# Installation

## 1. Clone the Repository

```bash
git clone https://github.com/kamreajalam/PyChronicle.git
```

Move into the project directory:

```bash
cd PyChronicle
```

---

## 2. Create a Virtual Environment

### Windows

```bash
python -m venv .venv
```

Activate it:

```bash
.venv\Scripts\activate
```

### Linux/macOS

```bash
python3 -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

---

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

# Running PyChronicle

## Step 1 — Generate Execution Trace

Run the execution tracer:

```bash
python src/tracer.py
```

The tracer records execution information and stores the resulting execution history in the SQLite database.

Example validation result:

```text
Session #12 complete
15 events traced
15 rows stored in pychronicle.db
```

---

## Step 2 — Launch the Dashboard

Run:

```bash
python app.py
```

The PyChronicle dashboard will open in the terminal.

---

# Dashboard Controls

| Key    | Action                     |
| ------ | -------------------------- |
| `Home` | Go to first execution step |
| `End`  | Go to last execution step  |
| `d`    | Toggle dark/light theme    |
| `q`    | Quit PyChronicle           |

---

# Command-Line Options

PyChronicle supports custom trace and database paths.

### Specify a JSON trace

```bash
python app.py --trace trace_output.json
```

### Specify a SQLite database

```bash
python app.py --db pychronicle.db
```

### Specify both

```bash
python app.py --trace trace_output.json --db pychronicle.db
```

---

# Dashboard Components

## Timeline

The timeline displays recorded execution steps.

Selecting an execution step updates the remaining panels.

---

## Code Viewer

The Code Viewer displays the source code associated with the selected execution event.

When source-line information is available, the relevant line is highlighted.

---

## Variable Panel

The Variable Panel displays the variables associated with the selected execution event.

Example:

```text
a = 5
b = 10
result = 15
```

---

## Event Log

The Event Log displays information about the selected event.

Example:

```text
Event: line
Function: multiply
File: example.py
Line: 12
Variable changes: result: 10 → 15
```

---

# Data Sources

PyChronicle supports multiple trace-data sources.

The application can work with:

1. SQLite execution data
2. JSON trace data
3. Demo data when no trace is available

SQLite is used for real execution-history storage, while JSON provides an additional trace-data format.

---

# SQLite Execution Storage

PyChronicle stores execution information in:

```text
pychronicle.db
```

Recorded information can include:

* Execution sessions
* Events
* Functions
* Source files
* Line numbers
* Variables
* Variable differences
* Timestamps

This allows execution history to be inspected after a program has completed.

---

# Testing

PyChronicle uses `pytest`.

Run the complete test suite:

```bash
pytest -q
```

Run trace-loader tests:

```bash
pytest tests/test_trace_loader.py -q
```

Run tracer validation tests:

```bash
pytest tests/test_tracer_validation.py -q
```

Run application integration tests:

```bash
pytest tests/test_app_integration.py -q
```

> Always use the latest `pytest -q` output as the authoritative test result.

---

# Validation

During development, the real execution tracer was successfully validated with:

```text
Session #12 complete
15 events traced
15 rows stored in pychronicle.db
```

This confirms that the tracer successfully captured execution events and persisted them in SQLite.

The project also includes automated tests covering the trace loader, tracer validation, and application integration.

---

# Error Handling

PyChronicle includes handling for common trace-data problems, including:

* Missing JSON files
* Invalid JSON
* Missing SQLite databases
* Empty trace data
* Unsupported database schemas
* Missing source files
* Invalid source-line numbers

The application can fall back to another available data source when trace information is unavailable.

---

# Development Workflow

The project follows this general workflow:

```text
Source Code
    ↓
AST Analysis
    ↓
Runtime Tracing
    ↓
SQLite Storage
    ↓
Trace Loading
    ↓
Textual Dashboard
    ↓
Testing
    ↓
GitHub
```

---

# Project Development Highlights

During development, the project focused on:

* Integrating AST analysis with runtime execution tracing
* Recording execution history
* Persisting events in SQLite
* Loading trace information into a common structure
* Connecting backend trace data with the Textual dashboard
* Implementing interactive execution navigation
* Displaying variables and execution events
* Handling integration and testing issues
* Validating real execution sessions

---

# Future Improvements

Possible future improvements include:

* Full variable-state time travel
* Breakpoint support
* Execution search
* Event filtering
* Function filtering
* Session comparison
* Execution-speed controls
* Advanced variable-difference visualization
* Trace export/import
* Performance optimization
* Web-based interface
* Advanced AST visualization
* Expanded automated test coverage

---

# Project Status

## PyChronicle — Final Review Ready

The core PyChronicle components have been implemented and integrated:

* AST analysis
* Runtime execution tracing
* SQLite storage
* Trace loading
* Interactive Textual dashboard
* Code visualization
* Variable visualization
* Event logging
* Execution navigation
* Automated testing

The project is currently being finalized with documentation, testing, cleanup, and review preparation.

---

# Team Contributions

The project was developed collaboratively with responsibilities distributed across:

* AST parsing
* Execution tracing
* SQLite storage
* Textual UI
* Integration
* Testing
* Documentation

---

# Conclusion

PyChronicle demonstrates how Python AST analysis, runtime tracing, persistent storage, and terminal-based visualization can be combined to create an execution-history debugging system.

The project provides a foundation for time-travel debugging by allowing developers to inspect recorded execution events rather than relying only on the final program state.

````
