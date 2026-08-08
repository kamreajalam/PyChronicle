"""AST visitor — collects a structural summary of a Python source file.

Ported from the integrated branch (PyChronicle-main) so this checkout can
populate the ast_summary table that the integrated UI reads for its
"N file(s) AST-parsed" counter.
"""

import ast


class MyVisitor(ast.NodeVisitor):
    """Walks a Python AST and collects a structural summary of the source:
    imports, variable assignments, function/class definitions (with line
    numbers), loops, conditions, and return statements.

    Return statements are recorded under their own "returns" key rather than
    being appended into data["functions"], which used to corrupt the
    function-name list with serialized AST dumps.
    """

    def __init__(self):
        self.data = {
            "imports": [],
            "variables": [],
            "functions": [],
            "classes": [],
            "loops": [],
            "conditions": [],
            "returns": [],
            "function_defs": [],
            "class_defs": [],
        }

    def _serialize_node(self, node):
        return ast.dump(node, include_attributes=False)

    def visit_FunctionDef(self, node):
        self.data["functions"].append(node.name)
        self.data["function_defs"].append({"name": node.name, "line": node.lineno})
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        self.data["functions"].append(node.name)
        self.data["function_defs"].append({"name": node.name, "line": node.lineno})
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self.data["classes"].append(node.name)
        self.data["class_defs"].append({"name": node.name, "line": node.lineno})
        self.generic_visit(node)

    def visit_Assign(self, node):
        targets = [target.id for target in node.targets if isinstance(target, ast.Name)]
        self.data["variables"].extend(targets)
        self.generic_visit(node)

    def visit_Import(self, node):
        for alias in node.names:
            self.data["imports"].append(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        module = node.module or ""
        for alias in node.names:
            name = f"{module}.{alias.name}" if module else alias.name
            self.data["imports"].append(name)
        self.generic_visit(node)

    def visit_If(self, node):
        self.data["conditions"].append("if")
        self.generic_visit(node)

    def visit_For(self, node):
        self.data["loops"].append("for")
        self.generic_visit(node)

    def visit_While(self, node):
        self.data["loops"].append("while")
        self.generic_visit(node)

    def visit_Return(self, node):
        self.data["returns"].append(
            {"line": node.lineno, "code": self._serialize_node(node)}
        )
        self.generic_visit(node)


ASTVisitor = MyVisitor
