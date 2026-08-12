# 1. Project Overview

PyChronicle is a Python-based execution-history and debugging tool that records program execution and allows developers to inspect previous execution states through an interactive Textual-based terminal dashboard.

The project combines:

* Python Abstract Syntax Tree (AST) analysis
* Runtime execution tracing using `sys.settrace`
* Execution-event recording
* Variable/state tracking
* SQLite-based storage
* JSON trace loading
* Trace-data normalization
* Textual terminal visualization
* Automated testing

The purpose of the system is to provide a historical view of program execution rather than relying only on conventional forward debugging.

---

# 2. Problem Statement

Traditional debugging generally follows a linear execution process.

When an incorrect state occurred several execution steps earlier, developers may need to restart the program and reproduce the same execution to investigate the problem.

PyChronicle addresses this problem by recording execution information and making it available through a timeline-based interface.

### Traditional Approach

```text
Run Program
     ↓
Find Problem
     ↓
Restart Program
     ↓
Reproduce State
     ↓
Debug Again
```

### PyChronicle Approach

```text
Run Program
     ↓
Trace Execution
     ↓
Store Execution History
     ↓
Load Trace
     ↓
Navigate Timeline
     ↓
Inspect Historical State
```

---

# 3. Objectives

The main objectives of PyChronicle are:

1. Analyze Python source code using AST.
2. Parse relevant source-code structures.
3. Trace runtime Python execution.
4. Capture execution events.
5. Record variable/state information.
6. Store execution information in SQLite.
7. Load execution history from SQLite and JSON.
8. Normalize trace data for the application.
9. Provide an interactive Textual dashboard.
10. Provide execution timeline navigation.
11. Display source code for selected execution steps.
12. Display variables associated with execution states.
13. Display execution events.
14. Highlight relevant source lines.
15. Provide command-line configuration.
16. Validate the implementation using automated tests.

---

# 4. Technology Stack

| Technology     | Purpose                       |
| -------------- | ----------------------------- |
| Python         | Core implementation           |
| `ast`          | Source-code and AST analysis  |
| `sys.settrace` | Runtime execution tracing     |
| SQLite         | Execution-history storage     |
| JSON           | Trace-data loading and backup |
| Textual        | Terminal user interface       |
| Rich           | Syntax highlighting           |
| argparse       | Command-line arguments        |
| pytest         | Automated testing             |
| Git            | Version control               |
| GitHub         | Repository management         |

---

# 5. System Architecture

```text
                    Python Program
                          │
                          ▼
                  ┌───────────────┐
                  │   AST Parser  │
                  └───────┬───────┘
                          │
                          ▼
                  ┌───────────────┐
                  │ Execution     │
                  │ Tracer        │
                  │ sys.settrace  │
                  └───────┬───────┘
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
       ┌─────────────┐         ┌─────────────┐
       │   SQLite    │         │    JSON     │
       │   Storage   │         │    Trace    │
       └──────┬──────┘         └──────┬──────┘
              │                       │
              └───────────┬───────────┘
                          ▼
                  ┌───────────────┐
                  │ Trace Loader  │
                  └───────┬───────┘
                          │
                          ▼
                  ┌───────────────┐
                  │   Textual     │
                  │   Dashboard   │
                  └───────────────┘
```

---

# 6. Project Structure

```text
PyChronicle/
│
├── app.py
├── cli.py
├── trace_loader.py
├── trace_output.json
│
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── database.py
│   ├── events.py
│   ├── models.py
│   ├── parser.py
│   ├── tracer.py
│   ├── utils.py
│   └── visiter.py
│
├── tests/
│   ├── test_app_integration.py
│   ├── test_trace_loader.py
│   └── test_tracer_validation.py
│
├── examples/
│
├── docs/
│
├── README.md
├── CHANGES.md
├── LICENSE
├── requirements.txt
└── pytest.ini
```

### Runtime Database

`pychronicle.db` is a runtime-generated SQLite database. It is used locally during execution and is not required to be committed to the GitHub repository.

---

# 7. Main Components

## 7.1 `src/tracer.py`

Responsible for runtime execution tracing using Python's `sys.settrace()` mechanism.

It captures execution information during program runtime.

Events can include:

```text
call
line
return
```

---

## 7.2 `src/parser.py`

Responsible for parsing Python source code and supporting AST-based analysis.

The parser works with Python's built-in `ast` module.

---

## 7.3 `src/visiter.py`

Provides AST visitor functionality for traversing and analyzing the parsed Python syntax tree.

---

## 7.4 `src/database.py`

Responsible for SQLite database operations and persistent execution-history storage.

It provides the database layer used by the tracing system.

---

## 7.5 `src/models.py`

Contains project data models used to represent execution and trace-related information.

---

## 7.6 `src/events.py`

Defines and manages execution events generated during program tracing.

---

## 7.7 `src/config.py`

Provides project configuration, including database and application-related settings.

---

## 7.8 `src/utils.py`

Contains reusable utility functions used by PyChronicle components.

---

## 7.9 `trace_loader.py`

Acts as the bridge between stored trace information and the dashboard.

It supports:

* SQLite trace loading
* JSON trace loading
* Variable formatting
* Demo-data fallback
* Trace-data normalization

Important functions include:

```python
format_vars()
load_from_json()
load_from_sqlite()
load_tracer_data()
```

---

## 7.10 `app.py`

Provides the interactive Textual terminal dashboard.

It connects loaded execution data with:

* Timeline
* Code Viewer
* Variable Panel
* Event Log

---

## 7.11 `cli.py`

Provides command-line functionality for running and configuring PyChronicle.

---

## 7.12 `tests/`

Contains automated tests for:

* Trace loading
* Tracer validation
* Application integration
* JSON handling
* SQLite handling

---

# 8. Execution Workflow

The complete execution workflow is:

```text
Python Source
      ↓
AST Analysis
      ↓
Program Execution
      ↓
sys.settrace()
      ↓
Execution Events
      ↓
Variable / State Information
      ↓
SQLite Storage
      ↓
Trace Loader
      ↓
Textual Dashboard
      ↓
Historical Execution Inspection
```

---

# 9. AST Analysis

The project uses Python's `ast` module to represent and analyze Python source code structurally.

The AST layer provides information about the program's source-code structure and supports identification of relevant source constructs.

The AST analysis works together with the runtime tracing layer rather than replacing it.

---

# 10. Runtime Execution Tracing

PyChronicle uses:

```python
sys.settrace()
```

to observe Python program execution.

The tracing mechanism can receive runtime events such as:

```text
call
line
return
```

These events provide information about how the program progresses during execution.

The captured information can then be passed to the storage layer.

---

# 11. SQLite Storage

SQLite is used to persist execution-history information.

The runtime database is:

```text
pychronicle.db
```

Execution data can contain information such as:

* Events
* Sessions
* Functions
* Source files
* Line numbers
* Variables
* Variable changes
* Timestamps

The database allows execution information to remain available after the tracing operation.

---

# 12. JSON Trace Support

PyChronicle also supports JSON trace information.

The default JSON trace file is:

```text
trace_output.json
```

Example structure:

```json
{
    "step1": {
        "code": "x = 5",
        "vars": "x = 5",
        "event": "initialized"
    }
}
```

The trace loader converts JSON trace information into the common structure required by the application.

---

# 13. Trace Loading

The trace loader supports multiple sources:

```text
SQLite
   ↓
JSON
   ↓
Demo Data
```

If usable SQLite data is available, the application can load the recorded execution history.

If SQLite data is unavailable, JSON trace information can be loaded.

If neither source is available, demo data can be used as a fallback.

This allows the dashboard to remain functional even when a real execution trace is unavailable.

---

# 14. Textual Dashboard

The user interface is implemented using Textual.

The dashboard provides four major areas:

```text
┌──────────────────────────────────────────────────────┐
│                    PYCHRONICLE                       │
├────────────────┬─────────────────────────────────────┤
│                │                                     │
│   TIMELINE     │           CODE VIEWER               │
│                │                                     │
│ Step 01        │      Python source code             │
│ Step 02        │      with line highlighting         │
│ Step 03        │                                     │
│                ├──────────────────┬──────────────────┤
│                │ VARIABLE PANEL   │ EVENT LOG        │
│                │                  │                  │
│                │ x = 5            │ Function called │
│                │ y = 10           │ Result = 15     │
└────────────────┴──────────────────┴──────────────────┘
```

---

# 15. Timeline

The timeline displays recorded execution steps.

Example:

```text
TIMELINE

Step 01: step1
Step 02: step2
Step 03: step3
```

When a user selects an execution step, the dashboard updates the corresponding code, variables, and event information.

---

# 16. Code Viewer

The Code Viewer displays source code associated with the selected execution step.

It provides:

* Python syntax highlighting
* Line numbers
* Source-line highlighting

This allows the developer to identify the part of the source code associated with the selected execution state.

---

# 17. Variable Panel

The Variable Panel displays variables associated with the selected execution state.

Example:

```text
VARIABLE PANEL

x = 5
y = 10
total = 15
```

This allows the user to inspect program state at a particular point in execution.

---

# 18. Event Log

The Event Log displays information about the selected execution event.

Example:

```text
EVENT LOG

Event: line
Function: calculate_sum
File: example.py
Line: 3
```

Variable changes can also be displayed when available.

---

# 19. Keyboard Controls

| Key    | Action                  |
| ------ | ----------------------- |
| `d`    | Toggle dark/light theme |
| `Home` | First execution step    |
| `End`  | Last execution step     |
| `q`    | Quit application        |

---

# 20. Command-Line Interface

Run the application:

```bash
python app.py
```

Specify a JSON trace:

```bash
python app.py --trace trace_output.json
```

Specify a SQLite database:

```bash
python app.py --db pychronicle.db
```

Specify both:

```bash
python app.py --trace trace_output.json --db pychronicle.db
```

---

# 21. Installation

Clone the repository:

```bash
git clone https://github.com/kamreajalam/PyChronicle.git
```

Move into the repository:

```bash
cd PyChronicle
```

Create a virtual environment.

### Windows

```powershell
python -m venv .venv
.venv\Scripts\activate
```

### Linux/macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

# 22. Running the Application

Start the dashboard:

```bash
python app.py
```

The application loads the available trace data and opens the Textual interface.

The user can select execution steps from the timeline and inspect the corresponding:

* Source code
* Variables
* Execution event

---

# 23. Testing

PyChronicle uses `pytest` for automated testing.

Run:

```bash
pytest -q
```

### Final Verified Result

```text
12 passed
```

Therefore:

```text
12 / 12 tests passed successfully
```

The test suite covers areas including:

* Variable formatting
* JSON trace loading
* Missing JSON files
* SQLite trace loading
* Trace-source handling
* Demo fallback
* Application integration
* Tracer validation

---

# 24. Execution Validation

The execution tracer was validated using a real tracing session.

The validated result was:

```text
Session #12 complete
15 events traced
15 rows stored in pychronicle.db
```

The recorded execution included runtime events such as:

```text
call
line
return
```

This validated the connection between runtime tracing and SQLite storage.

---

# 25. Integration

The major project components were integrated through:

```text
AST Parser
     ↓
Execution Tracer
     ↓
SQLite Storage
     ↓
Trace Loader
     ↓
Textual Application
```

The trace loader provides normalized execution data to the application.

The Textual dashboard then displays the information through the timeline and corresponding detail panels.

---

# 26. Error Handling

PyChronicle handles conditions including:

* Missing JSON files
* Invalid JSON
* Missing SQLite databases
* SQLite errors
* Unsupported SQLite structures
* Missing source files
* Invalid line numbers
* Missing variable information
* Empty trace data

When no usable trace is available, demo data can be used as a fallback.

---

# 27. Development Phases

## Phase 1 — AST and Foundation

* Project structure
* AST parsing
* Source analysis
* Variable assignment analysis
* Database foundation

## Phase 2 — Runtime Tracing

* `sys.settrace`
* Runtime events
* Function events
* Line events
* Return events
* State information
* SQLite persistence

## Phase 3 — Storage and Trace Loading

* SQLite integration
* JSON support
* Trace loader
* Variable formatting
* Session handling
* Fallback handling

## Phase 4 — Textual Dashboard

* Timeline
* Code Viewer
* Variable Panel
* Event Log
* Syntax highlighting
* Line highlighting
* Keyboard navigation
* Theme switching

## Phase 5 — Integration

```text
Tracer
   ↓
Storage
   ↓
Trace Loader
   ↓
Application
   ↓
Textual Dashboard
```

## Phase 6 — Testing and Documentation

* Integration testing
* Tracer validation
* SQLite validation
* Application testing
* Automated testing
* README preparation
* Technical documentation
* GitHub organization

---

# 28. Final Project Status

The following components are implemented:

* [x] AST parser
* [x] AST visitor
* [x] Runtime execution tracer
* [x] `sys.settrace`
* [x] SQLite integration
* [x] Execution events
* [x] Data models
* [x] Configuration
* [x] Utility functions
* [x] JSON trace loading
* [x] SQLite trace loading
* [x] Demo fallback
* [x] Textual dashboard
* [x] Timeline
* [x] Code viewer
* [x] Variable panel
* [x] Event log
* [x] Source-line highlighting
* [x] Keyboard navigation
* [x] CLI support
* [x] Application integration
* [x] Automated testing
* [x] README
* [x] Technical documentation

---

# 29. Final Validation

## Test Validation

```text
12 passed
```

**Final test status: 12 / 12 tests passed.**

## Tracer Validation

```text
Session #12 complete
15 events traced
15 rows stored in pychronicle.db
```

These are the final verified project results.

---

# 30. Limitations

The current implementation provides the core historical execution-debugging functionality.

Potential limitations include:

* Large traces may require further optimization.
* Complex Python objects may require additional serialization support.
* Large-scale performance benchmarking can be expanded.
* Advanced historical state reconstruction can be improved.
* Additional debugging controls can be added.
* More edge-case tests can be introduced.

---

# 31. Future Enhancements

Possible future improvements include:

1. More efficient trace compression.
2. Improved historical state reconstruction.
3. Watch-variable functionality.
4. Execution-history search.
5. Trace session export/import.
6. Advanced event filtering.
7. Conditional debugging.
8. Performance optimization.
9. Improved complex-object handling.
10. Extended CLI functionality.
11. Additional integration tests.
12. Enhanced visualization of variable changes.

---

# 32. Learning Outcomes

This project provided practical experience with:

* Python AST
* AST visitors
* Runtime introspection
* `sys.settrace`
* Debugging architecture
* SQLite
* Data modeling
* Execution-state tracking
* Textual
* Rich
* CLI development
* Automated testing
* Git
* GitHub
* Collaborative development
* Software integration

---

# 33. Conclusion

PyChronicle demonstrates a practical approach to historical execution debugging in Python.

The system combines AST-based source analysis, runtime execution tracing, SQLite persistence, trace loading, and an interactive Textual terminal interface.

The completed application allows developers to navigate recorded execution steps and inspect:

* Source code
* Variables
* Execution events
* Line information
* Historical execution states

The implementation has been integrated and validated through automated testing.

Final test result:

```text
12 passed
```

The tracing system was also validated with:

```text
Session #12 complete
15 events traced
15 rows stored in pychronicle.db
```

PyChronicle therefore provides a functional foundation for time-oriented Python execution inspection while demonstrating practical use of Python metaprogramming, runtime tracing, persistent storage, automated testing, and terminal UI development.

---

# 34. Repository

**GitHub Repository:**

[https://github.com/kamreajalam/PyChronicle](https://github.com/kamreajalam/PyChronicle)

**Main Documentation:**

```text
README.md
docs/PROJECT_REPORT.md
```

**Runtime Database:**

```text
pychronicle.db
```

The SQLite database is generated locally during execution and is not required to be committed to the GitHub repository.
