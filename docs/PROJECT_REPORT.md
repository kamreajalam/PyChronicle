# PyChronicle — Project Documentation

## AST-Powered Time-Travel Debugger

**Project:** PyChronicle  
**Category:** Developer Tools & Metaprogramming  
**Language:** Python  
**Interface:** Textual Terminal User Interface  
**Storage:** SQLite  
**Testing:** pytest  

---

# 1. Introduction

PyChronicle is an AST-powered time-travel debugger for Python.

The objective of PyChronicle is to provide developers with a way to inspect historical execution states of a Python program instead of relying only on conventional forward debugging.

The system combines:

- Python Abstract Syntax Tree (AST) analysis
- Runtime execution tracing
- `sys.settrace`
- Variable/state tracking
- SQLite storage
- Trace loading
- Textual-based terminal interface

The project specification defines PyChronicle as a developer tool that records execution history and allows historical states to be inspected through a timeline-based interface.

---

# 2. Problem Statement

Traditional debugging generally follows a linear execution model.

A developer runs a program, encounters an incorrect state, investigates it, and may need to restart the program repeatedly to understand how that state was produced.

This becomes inefficient when the cause of an error occurred several execution steps earlier.

PyChronicle addresses this problem by recording execution information while a program runs.

The recorded history can then be inspected through a timeline.

Instead of:

    Run
      ↓
    Debug
      ↓
    Find previous state
      ↓
    Restart
      ↓
    Repeat

PyChronicle provides:

    Program Execution
          ↓
    Execution Recording
          ↓
    Persistent History
          ↓
    Timeline
          ↓
    Historical State Inspection

---

# 3. Objectives

The main objectives of the project are:

1. Parse Python source code using the AST.
2. Analyze relevant source-code structures.
3. Trace runtime execution.
4. Capture execution events.
5. Track variable/state information.
6. Store execution information in SQLite.
7. Load recorded trace information.
8. Provide an interactive terminal interface.
9. Display execution history through a timeline.
10. Display source code associated with an execution state.
11. Display variables associated with an execution state.
12. Display event information.
13. Provide basic navigation through execution history.
14. Provide command-line execution options.
15. Validate the implementation using automated tests.

The official project plan identifies AST parsing, runtime tracing, SQLite storage, Textual UI, timeline integration, and CLI packaging as the main development areas.

---

# 4. Technology Stack

| Technology | Purpose |
|---|---|
| Python | Core programming language |
| `ast` | Abstract Syntax Tree analysis |
| `sys.settrace` | Runtime execution tracing |
| SQLite | Persistent execution-history storage |
| Textual | Terminal user interface |
| Rich | Syntax highlighting |
| JSON | Trace data interchange/fallback |
| argparse | Command-line argument parsing |
| pytest | Automated testing |
| Git | Version control |
| GitHub | Repository and collaboration |

---

# 5. System Architecture

PyChronicle is divided into several logical components.

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

# 6. Component Architecture

## 6.1 AST Parser

The AST component uses Python's built-in `ast` module.

The parser analyzes the source code and creates an Abstract Syntax Tree representation.

The AST layer provides the foundation for identifying relevant code structures and variable assignments.

The project specification identifies AST parsing and assignment identification as an initial engineering objective.

---

## 6.2 Execution Tracer

The execution tracer uses:

```python
sys.settrace()
```

The tracing mechanism receives runtime execution events from the Python interpreter.

The tracer can observe events such as:

```text
call
line
return
```

The collected information can include:

* Function information
* Source file
* Source line
* Execution event
* Variable/state information
* Variable changes

The tracer then stores relevant execution information for later inspection.

---

# 7. SQLite Storage

PyChronicle uses SQLite as persistent storage for execution history.

The primary database file used by the project is:

```text
pychronicle.db
```

The storage layer is responsible for preserving execution information beyond the current runtime session.

The project specification identifies execution-related storage fields including:

* Timestamp
* Line number
* Variable name
* Serialized value

The implemented system additionally handles execution events, sessions, variable information, and related trace metadata.

---

# 8. Trace Loader

The `trace_loader.py` module acts as the data-loading layer between stored traces and the user interface.

It provides functionality for:

* Loading JSON trace data
* Loading SQLite execution data
* Formatting variable information
* Selecting available trace data
* Providing demo data when no trace is available

Important functions include:

```python
format_vars()
load_from_json()
load_from_sqlite()
load_tracer_data()
```

The loader allows the application to work with both persisted execution data and fallback data.

---

# 9. Trace Data Sources

PyChronicle supports three data states:

```text
SQLite
   ↓
JSON
   ↓
Demo Data
```

### SQLite

The SQLite database contains execution information produced by the tracer.

### JSON

The JSON trace file is:

```text
trace_output.json
```

It provides a portable representation of trace information.

### Demo Data

Demo data is used when no valid trace source is available.

This allows the Textual application to remain functional even when a real trace has not yet been generated.

---

# 10. Textual User Interface

The main application is implemented using Textual.

The interface consists of several panels.

```text
+------------------------------------------------------+
|                    PYCHRONICLE                       |
+----------------+-------------------------------------+
|                |                                     |
|   TIMELINE     |            CODE VIEWER               |
|                |                                     |
| Step 01        |       Python source code             |
| Step 02        |       Line highlighting             |
| Step 03        |                                     |
|                +------------------+------------------+
|                | VARIABLE PANEL   |   EVENT LOG      |
|                |                  |                  |
|                | x = 5            | Function called  |
|                | y = 10           | Result = 15      |
+----------------+------------------+------------------+
```

---

# 11. Timeline

The timeline represents the recorded execution history.

Example:

```text
TIMELINE

Step 01: step1
Step 02: step2
Step 03: step3
```

Selecting a step changes the information displayed in the other panels.

The timeline therefore acts as the main navigation mechanism for historical execution.

---

# 12. Code Viewer

The Code Viewer displays source code associated with the selected execution step.

Example:

```python
def calculate_sum(a, b):
    result = a + b
    return result

print(calculate_sum(5, 10))
```

The interface uses Rich syntax rendering to improve source-code readability.

The implementation also supports line highlighting when the corresponding source-line information is available.

---

# 13. Variable Panel

The Variable Panel displays the variables associated with the selected execution state.

Example:

```text
VARIABLE PANEL

a = 5
b = 10
result = 15
```

This allows the developer to inspect the program state at a particular point in execution.

---

# 14. Event Log

The Event Log displays information related to the selected execution event.

Example:

```text
EVENT LOG

Function calculate_sum called
with parameters a=5, b=10.
```

Another possible event:

```text
Addition complete.
result evaluated to 15.
```

This provides additional context about the execution state.

---

# 15. User Interaction

The application supports keyboard navigation.

| Key    | Function                |
| ------ | ----------------------- |
| `D`    | Toggle dark/light theme |
| `Home` | First execution step    |
| `End`  | Last execution step     |
| `Q`    | Quit application        |

The timeline can also be navigated interactively using the Textual list interface.

---

# 16. Command-Line Interface

PyChronicle supports command-line configuration through `argparse`.

The application accepts:

```text
--trace
-t
--db
```

### Run with default files

```bash
python app.py
```

### Specify JSON trace

```bash
python app.py --trace trace_output.json
```

### Specify SQLite database

```bash
python app.py --db pychronicle.db
```

### Specify both

```bash
python app.py --trace trace_output.json --db pychronicle.db
```

Default paths are:

```text
trace_output.json
pychronicle.db
```

---

# 17. Project Structure

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

# 18. Development Phases

## Phase 1 — AST and Project Foundation

The initial development focused on:

* Project structure
* AST parsing
* Source-code analysis
* Variable assignment identification
* Initial storage design

---

## Phase 2 — Runtime Execution Tracing

The next phase introduced:

* `sys.settrace`
* Runtime event capture
* Function events
* Line events
* Return events
* Variable/state information
* SQLite integration

---

## Phase 3 — Trace Storage and Loading

The project then implemented:

* SQLite trace storage
* JSON trace support
* Trace loading
* Variable formatting
* Fallback handling
* Session-related information

---

## Phase 4 — Textual Dashboard

The interface was developed with:

* Timeline
* Code Viewer
* Variable Panel
* Event Log
* Syntax highlighting
* Active-line highlighting
* Keyboard navigation
* Theme switching

---

## Phase 5 — Integration

The major components were connected:

```text
Tracer
   ↓
SQLite
   ↓
Trace Loader
   ↓
PyChronicleApp
   ↓
Textual Dashboard
```

The integration process included fixing SQLite loading compatibility, trace-source selection, application integration, and UI behavior.

---

## Phase 6 — Testing and Validation

The final stage focused on:

* Unit testing
* Integration testing
* Trace validation
* SQLite validation
* Application testing
* UI verification
* Documentation

The final automated test run currently reports:

```text
12 passed
```

---

# 19. Execution Validation

The tracer was validated using an actual execution session.

A completed session produced:

```text
Session #12 complete
15 events traced
15 rows stored in pychronicle.db
```

The execution output included event types such as:

```text
call
line
return
```

This demonstrates that runtime execution events were captured and persisted.

---

# 20. Testing

PyChronicle uses pytest.

Run:

```bash
pytest -q
```

Final test status:

```text
12 passed
```

The tests cover areas including:

* Variable formatting
* JSON loading
* Missing JSON files
* SQLite loading
* Trace-source selection
* Demo fallback
* Application integration
* Tracer validation

The final verified result is:

```text
12 / 12 tests passed
```

---

# 21. Integration Testing

The application was tested with the Textual interface.

The final interface provides:

```text
Timeline
     ↓
Select Step
     ↓
Code Viewer Updated
     ↓
Variables Updated
     ↓
Event Log Updated
```

The application was also tested using generated execution traces and the SQLite database.

---

# 22. Example Execution

Consider:

```python
def calculate_sum(a, b):
    result = a + b
    return result

print(calculate_sum(5, 10))
```

A trace can contain multiple execution states.

The dashboard allows the user to select a state and inspect:

```text
Source Code
Variables
Execution Event
```

For example:

```text
a = 5
b = 10
result = 15
```

The timeline provides access to different recorded states.

---

# 23. Error Handling

The trace-loading system includes handling for:

* Missing JSON files
* Invalid JSON
* Missing SQLite databases
* SQLite errors
* Unsupported database structures
* Missing source files
* Invalid line numbers
* Missing variable information

When no usable trace is available, the application can fall back to demo data.

---

# 24. Current Project Status

| Component           | Status   |
| ------------------- | -------- |
| AST Parser          | Complete |
| Execution Tracer    | Complete |
| `sys.settrace`      | Complete |
| SQLite Storage      | Complete |
| JSON Loader         | Complete |
| Trace Loader        | Complete |
| Textual Dashboard   | Complete |
| Timeline            | Complete |
| Code Viewer         | Complete |
| Variable Panel      | Complete |
| Event Log           | Complete |
| Syntax Highlighting | Complete |
| Line Highlighting   | Complete |
| Keyboard Navigation | Complete |
| CLI                 | Complete |
| Integration         | Complete |
| Automated Tests     | Complete |
| Documentation       | Complete |

### Final Test Result

```text
12 passed
```

### Tracing Validation

```text
15 events traced
15 rows stored in pychronicle.db
```

---

# 25. Limitations

The current project is a functional implementation/prototype of historical execution debugging.

Potential limitations include:

* Large execution traces may require optimization.
* Complex Python objects may require additional serialization handling.
* Advanced state reconstruction can be further improved.
* Large-scale performance benchmarking can be added.
* More advanced debugging conditions can be implemented.
* Additional test cases can improve coverage.

These limitations should not be interpreted as failed core requirements; they represent possible future enhancements.

---

# 26. Future Enhancements

Potential future development includes:

1. Improved trace compression.
2. More efficient state reconstruction.
3. Watch-variable functionality.
4. Search through execution history.
5. Trace session export/import.
6. Advanced conditional debugging.
7. Performance optimization.
8. More comprehensive test coverage.
9. Better handling of complex Python objects.
10. Extended CLI functionality.

---

# 27. Learning Outcomes

The project provided practical experience in:

* Python AST
* Runtime introspection
* `sys.settrace`
* Debugging systems
* SQLite
* State tracking
* Textual
* Rich
* CLI development
* Automated testing
* Git
* GitHub
* Team-based software development
* Integration of multiple software components

---

# 28. Conclusion

PyChronicle demonstrates a practical approach to historical Python execution debugging.

The system combines AST-based source analysis, runtime execution tracing, SQLite persistence, trace loading, and a Textual terminal interface.

The final application allows users to navigate recorded execution steps and inspect:

* Source code
* Variables
* Execution events
* Historical execution states

The final implementation has been integrated and validated through automated testing.

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

PyChronicle therefore provides a working foundation for historical execution inspection and demonstrates the use of Python metaprogramming and runtime tracing techniques in a practical developer tool.

---

# 29. References

The project was developed according to the PyChronicle project specification provided by Infotact Solutions.

Core technologies specified for the project include:

* Python AST
* `sys.settrace`
* SQLite
* Textual

The project specification also defines the four-week progression covering AST analysis, runtime tracing, SQLite storage, timeline integration, CLI packaging, testing, and UI refinement.
