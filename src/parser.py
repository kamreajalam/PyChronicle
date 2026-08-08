"""AST parsing front-end — turns Python source into a structural summary.

Ported from the integrated branch (PyChronicle-main). The summary produced
here is what gets stored in the ast_summary table, giving the UI static
structure (functions, classes, imports, loops) alongside the runtime events.
"""

import ast
import json
import os
import sys

# Same flat-import pattern used by tracer.py / database.py / app.py: put this
# file's own directory on sys.path so sibling modules (visiter.py) import by
# bare name regardless of the current working directory.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from visiter import ASTVisitor  # noqa: E402


def to_jsonable(value):
    """Recursively converts an ast.AST node (or nested lists/tuples of them)
    into plain JSON-serializable Python data."""
    if isinstance(value, ast.AST):
        return {
            "_type": type(value).__name__,
            **{field: to_jsonable(getattr(value, field)) for field in value._fields},
        }
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def parse_source(source_code, file_name="<string>"):
    """Parses Python source into an AST and runs the visitor over it.

    Returns (tree, summary) where `tree` is the raw ast.Module and `summary`
    is the visitor's collected dict (imports, variables, functions, classes,
    loops, conditions, returns, function_defs, class_defs).
    """
    tree = ast.parse(source_code, filename=file_name)
    visitor = ASTVisitor()
    visitor.visit(tree)
    return tree, visitor.data


def parse_file(file_path):
    """Parses a .py file on disk. Returns (tree, summary) — see parse_source."""
    with open(file_path, "r", encoding="utf-8") as f:
        source_code = f.read()
    return parse_source(source_code, file_name=file_path)


def export_ast_json(tree, output_path="ast.json"):
    """Writes the full AST as JSON (for inspection/debugging)."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(to_jsonable(tree), f, indent=4)
    return output_path


def export_summary_json(summary, output_path="output.json"):
    """Writes the visitor's summary dict as JSON (for inspection/debugging)."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=4)
    return output_path


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "examples", "sample_program.py"
    )

    tree, summary = parse_file(target)
    print(f"parsed {target}")
    print(f"  functions : {summary['functions']}")
    print(f"  classes   : {summary['classes']}")
    print(f"  imports   : {summary['imports']}")
    print(f"  loops     : {len(summary['loops'])}")
    print(f"  conditions: {len(summary['conditions'])}")
    print(f"  returns   : {len(summary['returns'])}")
