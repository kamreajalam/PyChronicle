# PyChronicle

## AST-Powered Time-Travel Debugger for Python

PyChronicle is a Python debugging tool that records program execution history and allows developers to inspect previous execution states through an interactive terminal interface.

Instead of repeatedly restarting a program to understand what happened earlier, PyChronicle records execution events, variable states, source information, and execution history. The recorded information can then be explored through a timeline-based Textual dashboard.

---

## Features

- Python AST-based source analysis
- Runtime execution tracing using `sys.settrace`
- Execution event recording
- Variable/state tracking
- SQLite-based trace storage
- JSON trace loading and fallback support
- Interactive Textual terminal dashboard
- Execution timeline
- Source-code viewer
- Active-line highlighting
- Variable inspection panel
- Event log
- Keyboard navigation
- Dark/light theme toggle
- Command-line arguments for trace and database paths
- Automated test suite

---

## Architecture

```text
                    Python Program
                          |
                          v
                  +---------------+
                  |   AST Parser  |
                  +---------------+
                          |
                          v
                  +---------------+
                  | Execution     |
                  | Tracer        |
                  | sys.settrace  |
                  +---------------+
                          |
                          v
                  +---------------+
                  | SQLite        |
                  | Storage       |
                  +---------------+
                          |
                          v
                  +---------------+
                  | Trace Loader  |
                  +---------------+
                          |
                          v
                  +---------------+
                  | Textual TUI   |
                  +---------------+
                          |
          +---------------+---------------+
          |               |               |
          v               v               v
      Timeline       Code Viewer     Variable Panel
                                          |
                                          v
                                      Event Log
````

---

## Technology Stack

| Technology     | Purpose                                  |
| -------------- | ---------------------------------------- |
| Python         | Core implementation                      |
| `ast`          | Python source-code analysis              |
| `sys.settrace` | Runtime execution tracing                |
| SQLite         | Execution history storage                |
| Textual        | Terminal user interface                  |
| Rich           | Syntax highlighting and formatted output |
| JSON           | Trace data and fallback source           |
| argparse       | Command-line interface                   |
| pytest         | Automated testing                        |

---

## Project Structure

```text
PyChronicle/
│
├── app.py
├── cli.py
├── trace_loader.py
├── pychronicle.db
├── trace_output.json
│
├── src/
│   └── tracer.py
│
├── tests/
│   ├── test_app_integration.py
│   ├── test_trace_loader.py
│   └── test_tracer_validation.py
│
├── examples/
│
├── README.md
├── CHANGES.md
├── LICENSE
├── requirements.txt
└── pytest.ini
```

---

# How PyChronicle Works

PyChronicle follows the following execution pipeline:

```text
Python Source
     |
     v
AST Analysis
     |
     v
Runtime Execution
     |
     v
sys.settrace()
     |
     v
Execution Events
     |
     v
Variable / State Information
     |
     v
SQLite Database
     |
     v
Trace Loader
     |
     v
Textual Dashboard
```

The recorded execution history can then be explored through the timeline.

---

# Textual Dashboard

The PyChronicle dashboard provides an interactive terminal interface.

```text
+-----------------------------------------------------------+
|                     PYCHRONICLE                           |
+-------------------+---------------------------------------+
|                   |                                       |
|    TIMELINE       |             CODE VIEWER               |
|                   |                                       |
| Step 01: step1    |     Python source code                |
| Step 02: step2    |     with line highlighting             |
| Step 03: step3    |                                       |
|                   +-------------------+-------------------+
|                   | VARIABLE PANEL    | EVENT LOG         |
|                   |                   |                   |
|                   | x = 5             | Function called   |
|                   | y = 10            | Result = 15       |
+-------------------+-------------------+-------------------+
```

---

## Timeline

The timeline displays recorded execution steps.

Example:

```text
TIMELINE

Step 01: step1
Step 02: step2
Step 03: step3
```

Selecting an execution step updates the code viewer, variable panel, and event log.

---

## Code Viewer

The Code Viewer displays the source code associated with the selected execution state.

Example:

```python
def calculate_sum(a, b):
    result = a + b
    return result

print(calculate_sum(5, 10))
```

The relevant execution line can be highlighted to help identify where the selected state occurred.

---

## Variable Panel

The Variable Panel displays variables associated with the selected execution step.

Example:

```text
VARIABLE PANEL

a = 5
b = 10
result = 15
```

---

## Event Log

The Event Log provides information about the selected execution event.

Example:

```text
EVENT LOG

Function calculate_sum called
with parameters a=5, b=10.
```

Another example:

```text
Addition complete.
result evaluated to 15.
```

---

# Trace Storage

PyChronicle uses SQLite for persistent execution-history storage.

The project database is:

```text
pychronicle.db
```

Execution information can include:

* Execution events
* Source information
* Line information
* Variable information
* Variable changes
* Session information
* Timestamps

The tracer can therefore preserve execution information for later inspection by the dashboard.

---

# Trace Loader

The `trace_loader.py` module provides a common interface for loading execution data.

It supports:

```text
SQLite
   |
   v
JSON
   |
   v
Demo Data
```

The loader provides functions for:

```python
load_from_json()
load_from_sqlite()
load_tracer_data()
format_vars()
```

This allows the UI to work with real execution traces while also supporting JSON and demo fallback data.

---

# Running the Application

## 1. Clone the repository

```bash
git clone https://github.com/kamreajalam/PyChronicle.git
```

```bash
cd PyChronicle
```

## 2. Install dependencies

```bash
pip install -r requirements.txt
```

## 3. Run PyChronicle

```bash
python app.py
```

The application will load the available trace data and open the Textual dashboard.

---

# Command-Line Options

PyChronicle supports custom trace and database paths.

## JSON trace

```bash
python app.py --trace trace_output.json
```

## SQLite database

```bash
python app.py --db pychronicle.db
```

## Both

```bash
python app.py --trace trace_output.json --db pychronicle.db
```

---

# Keyboard Controls

| Key    | Action                     |
| ------ | -------------------------- |
| `D`    | Toggle dark/light theme    |
| `Home` | Go to first execution step |
| `End`  | Go to last execution step  |
| `Q`    | Quit application           |

---

# Running Tests

PyChronicle uses `pytest` for automated testing.

Run the complete test suite:

```bash
pytest -q
```

Current result:

```text
12 passed
```

### Test Coverage Areas

The tests validate:

* Variable formatting
* JSON trace loading
* Missing JSON files
* SQLite trace loading
* Trace-source selection
* Demo-data fallback
* Application integration
* Tracer validation

---

# Execution Tracing Validation

The execution tracer has been validated using real Python execution.

A completed tracing session produced:

```text
Session #12 complete
15 events traced
15 rows stored in pychronicle.db
```

Example event types include:

```text
call
line
return
```

This confirms that execution events can be captured and persisted in the SQLite database.

---

# Example

Consider the following Python program:

```python
def calculate_sum(a, b):
    result = a + b
    return result

print(calculate_sum(5, 10))
```

PyChronicle can represent the execution history as:

```text
Step 01: Function call
Step 02: Variable assignment
Step 03: Addition
Step 04: Return
```

When a step is selected, the dashboard displays the corresponding:

```text
Source Code
     +
Variables
     +
Execution Event
```

This provides a historical view of the program's execution.

---

# Data Sources

PyChronicle supports multiple trace sources.

### SQLite

```text
pychronicle.db
```

Used for persisted execution data.

### JSON

```text
trace_output.json
```

Used for trace data and fallback loading.

### Demo Data

If no usable trace is available, the application can fall back to built-in demo execution steps.

---

# Development Workflow

The project was developed incrementally through the following stages:

### Phase 1 — AST Foundation

* AST parsing
* Source analysis
* Variable assignment identification

### Phase 2 — Runtime Tracing

* `sys.settrace`
* Function events
* Line events
* Return events
* Variable/state information

### Phase 3 — Storage

* SQLite integration
* Execution-event persistence
* Session information
* Trace retrieval

### Phase 4 — Trace Loading

* SQLite loader
* JSON loader
* Variable formatting
* Fallback handling

### Phase 5 — Textual Dashboard

* Timeline
* Code viewer
* Variable panel
* Event log
* Keyboard navigation
* Syntax highlighting

### Phase 6 — Integration & Testing

* Component integration
* Application testing
* Trace validation
* SQLite validation
* Automated tests
* Final UI verification

---

# Project Status

## Completed

* [x] AST parser integration
* [x] Runtime execution tracer
* [x] `sys.settrace` integration
* [x] SQLite storage
* [x] JSON trace loading
* [x] Trace loader
* [x] Textual dashboard
* [x] Timeline
* [x] Code viewer
* [x] Variable panel
* [x] Event log
* [x] Active-line highlighting
* [x] Keyboard navigation
* [x] CLI argument support
* [x] Integration testing
* [x] Tracer validation
* [x] Documentation
* [x] Automated testing

### Test Status

```text
12 / 12 tests passed
```

---

# Limitations

PyChronicle is a project implementation/prototype intended to demonstrate historical Python execution inspection.

Some advanced debugging capabilities may require further development, including:

* Large-scale trace optimization
* More advanced state reconstruction
* Complex-object serialization
* Advanced variable watch functionality
* Performance benchmarking for very large programs
* Additional edge-case testing

---

# Future Improvements

Potential future improvements include:

* More efficient trace compression
* Watch-variable support
* Search through execution history
* Trace session export/import
* Improved handling of complex Python objects
* Advanced debugging conditions
* Performance optimization
* More comprehensive integration tests
* Improved visualization of variable changes

---

# Learning Outcomes

This project provided practical experience with:

* Python metaprogramming
* Abstract Syntax Trees
* Runtime introspection
* `sys.settrace`
* Debugging architecture
* SQLite database design
* State tracking
* Terminal UI development
* Textual framework
* Rich syntax rendering
* CLI development
* Automated testing
* Git and GitHub collaboration
* Software integration

---

# Conclusion

PyChronicle combines Python AST analysis, runtime execution tracing, SQLite storage, trace loading, and a Textual terminal interface into a historical execution-debugging system.

The project demonstrates how execution information can be captured, persisted, reconstructed, and interactively inspected through a timeline-based debugging interface.

The final implementation successfully integrates the major project components and currently passes the complete automated test suite:

```text
12 passed
```

---

## Author

**Md Kamreaj Alam**

B.Tech Computer Science (AI)

GitHub:

[https://github.com/kamreajalam/PyChronicle](https://github.com/kamreajalam/PyChronicle)

---

## License

This project is distributed under the license included in this repository.
