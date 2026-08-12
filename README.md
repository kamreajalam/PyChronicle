# PyChronicle

## AST-Powered Time-Travel Debugger

PyChronicle is a Python-based execution history and debugging tool that records program execution and allows developers to inspect previous execution states through an interactive Textual-based terminal dashboard.

Instead of debugging only the current state of a program, PyChronicle records execution events, variable states, source information, and execution metadata so that developers can navigate through the execution history.

---

## 🚀 Features

- 🔍 **AST-based source analysis**
- 🐍 **Python execution tracing using `sys.settrace`**
- 🗃️ **SQLite-based execution history storage**
- 📄 **JSON trace loading and backup support**
- 📊 **Interactive Textual terminal dashboard**
- ⏱️ **Execution timeline navigation**
- 🔢 **Variable-state inspection**
- 📝 **Execution event log**
- 🎯 **Active source-line highlighting**
- ⌨️ **Keyboard navigation**
- 🧪 **Automated test suite**
- 🔄 **Multiple trace-data sources with fallback support**

---

## 🏗️ Architecture

PyChronicle consists of several major components:

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
````

---

## 📁 Project Structure

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

### Important

`pychronicle.db` is a runtime-generated SQLite database and is not required to be committed to the GitHub repository.

When PyChronicle executes a traced program, SQLite storage can generate/update the database locally.

---

## ⚙️ Technologies Used

| Technology     | Purpose                   |
| -------------- | ------------------------- |
| Python         | Core implementation       |
| `ast`          | Source-code parsing       |
| `sys.settrace` | Runtime execution tracing |
| SQLite         | Execution-history storage |
| JSON           | Trace-data backup/loading |
| Textual        | Terminal user interface   |
| Rich           | Syntax highlighting       |
| pytest         | Automated testing         |

---

## 🔄 Trace Data Flow

PyChronicle can obtain execution history from multiple sources.

The application uses the following practical priority:

```text
SQLite
   ↓
JSON
   ↓
Demo Data
```

If a usable SQLite trace is available, the application can display the real execution history.

If SQLite data is unavailable, JSON trace data can be loaded.

If neither source is available, PyChronicle falls back to built-in demo data.

---

## 🖥️ Dashboard

The interactive dashboard provides:

### Timeline

Displays recorded execution steps/events.

Example:

```text
TIMELINE

Step 01: step1
Step 02: step2
```

### Code Viewer

Displays the source code associated with the selected execution step and supports line numbering/highlighting.

### Variable Panel

Displays the variables associated with the selected execution state.

Example:

```text
a = 5
b = 10
result = 15
```

### Event Log

Displays execution information such as:

```text
Function: calculate_sum
File: tracer.py
Line: 3
```

---

## ⌨️ Keyboard Controls

| Key    | Action                     |
| ------ | -------------------------- |
| `d`    | Toggle dark/light theme    |
| `Home` | Go to first execution step |
| `End`  | Go to last execution step  |
| `q`    | Quit application           |

---

## 📦 Installation

Clone the repository:

```bash
git clone https://github.com/kamreajalam/PyChronicle.git
```

Move into the project directory:

```bash
cd PyChronicle
```

Create a virtual environment:

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

## ▶️ Running PyChronicle

Run the main dashboard:

```bash
python app.py
```

The application loads available trace data and opens the interactive Textual dashboard.

---

## 🧪 Running Tests

Run the complete test suite:

```bash
pytest -q
```

Current project validation:

```text
12 passed
```

The test suite covers:

* Variable formatting
* JSON trace loading
* Missing JSON files
* SQLite trace loading
* Trace-source priority/fallback
* Application integration
* Tracer validation

---

## 🧰 Command-Line Usage

PyChronicle supports configurable trace and database paths.

### JSON trace

```bash
python app.py --trace trace_output.json
```

### SQLite database

```bash
python app.py --db pychronicle.db
```

### Both

```bash
python app.py --trace trace_output.json --db pychronicle.db
```

---

## 📄 Trace Output

A JSON trace file can contain execution steps such as:

```json
{
    "step1": {
        "code": "x = 5",
        "vars": "x = 5",
        "event": "initialized"
    }
}
```

The trace loader converts available execution information into a common structure used by the dashboard.

---

## 🗃️ SQLite Storage

PyChronicle can store execution information in SQLite.

The database can contain execution information such as:

* Execution steps
* Events
* Variables
* Source file information
* Line numbers
* Function information
* Variable changes
* Timestamps
* Session information

The database is treated as a runtime artifact and does not need to be committed to GitHub.

---

## 🔬 Execution Tracing

The execution tracer uses Python's runtime tracing capabilities to observe program execution.

A tracing session can record events such as:

```text
call
line
return
```

The captured information can then be stored and loaded by the PyChronicle trace-loading system.

Example runtime result:

```text
Session complete
15 events traced
15 rows stored in pychronicle.db
```

---

## 🧩 Main Components

### `src/tracer.py`

Responsible for runtime execution tracing and collecting execution information.

### `src/parser.py`

Responsible for parsing Python source code and supporting AST-based analysis.

### `src/visiter.py`

Provides AST visitor functionality for analyzing the parsed Python syntax tree.

### `src/database.py`

Responsible for SQLite database operations and persistent execution-history storage.

### `src/models.py`

Contains the project's data models used to represent execution and trace information.

### `src/events.py`

Defines and manages execution events generated during program tracing.

### `src/config.py`

Provides project configuration, including database and application-related settings.

### `src/utils.py`

Contains supporting utility functions used by the PyChronicle components.

### `trace_loader.py`

Responsible for loading and normalizing trace data from:

* SQLite
* JSON
* Demo data

### `app.py`

Provides the interactive Textual dashboard for viewing execution history.

### `cli.py`

Provides command-line functionality for running and configuring PyChronicle.

### `tests/`

Contains automated tests for:

* Trace loading
* Tracer validation
* Application integration

### `examples/`

Contains example programs/resources used for demonstrating or testing PyChronicle functionality.

---

## 🧪 Testing and Validation

The project has been validated using automated tests.

Final test result:

```text
12 passed
```

The integration testing verifies that the major components work together, including:

```text
Tracer
   ↓
Trace Data
   ↓
SQLite / JSON
   ↓
Trace Loader
   ↓
Textual Dashboard
```

---

## 🛡️ Error Handling

PyChronicle handles several situations gracefully:

* Missing JSON trace files
* Missing SQLite databases
* Invalid JSON data
* Unsupported SQLite schemas
* Missing source files
* Invalid line numbers
* Missing variable information
* Empty execution data

When no usable trace data is available, the application falls back to demo data.

---

## 📚 Documentation

Additional project documentation is available in:

```text
docs/
```

The documentation contains project-level information about the implementation, architecture, testing, and usage.

---

## 🔮 Future Improvements

Potential future improvements include:

* More advanced variable-difference visualization
* Improved source-code navigation
* Search within execution history
* Breakpoint support
* Conditional execution inspection
* More detailed AST visualization
* Advanced filtering of execution events
* Exporting execution sessions
* Improved debugging controls
* Additional test coverage

---

## 👥 Project Development

PyChronicle was developed as a collaborative Python development project with separate components for:

* AST parsing
* Runtime execution tracing
* SQLite storage
* Terminal UI
* Integration
* Testing
* Documentation

The project was developed using Git and GitHub with feature-based development and integration.

---

## 📌 Project Status

**Status: Completed ✅**

Current implementation includes:

* [x] Project structure
* [x] AST parser integration
* [x] Runtime execution tracer
* [x] SQLite integration
* [x] JSON trace loading
* [x] Trace-loader fallback system
* [x] Textual dashboard
* [x] Timeline navigation
* [x] Code viewer
* [x] Variable panel
* [x] Event log
* [x] Source-line highlighting
* [x] CLI support
* [x] Application integration
* [x] Automated testing
* [x] Documentation
* [x] GitHub repository organization

### Final Test Result

```text
12 passed
```

---

## 📜 License

This project is distributed under the license included in the repository.

See:

```text
LICENSE
```

---

## 👨‍💻 Author

**Md Kamreaj Alam**

GitHub: https://github.com/kamreajalam

---

## ⭐ Project Summary

PyChronicle provides a visual execution-history experience for Python programs by combining AST-based analysis, runtime tracing, persistent execution storage, trace loading, and an interactive Textual dashboard.

The project demonstrates how Python's execution model, source-code analysis, databases, testing, and terminal UI technologies can be integrated into a practical developer tool.
