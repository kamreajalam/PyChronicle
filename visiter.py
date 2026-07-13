import ast


class MyVisitor(ast.NodeVisitor):
    def __init__(self):
        self.data = {
            "imports": [],
            "variables": [],
            "functions": [],
            "classes": [],
            "loops": [],
            "conditions": []
        }

    def _serialize_node(self, node):
        return ast.dump(node, include_attributes=False)

    def visit_FunctionDef(self, node):
        print(f"Function name: {node.name}")
        self.data["functions"].append(node.name)
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        print(f"Class name: {node.name}")
        self.data["classes"].append(node.name)
        self.generic_visit(node)

    def visit_Assign(self, node):
        targets = [target.id for target in node.targets if isinstance(target, ast.Name)]
        print(f"Assignment to: {', '.join(targets)}")
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
        print("If statement found")
        self.data["conditions"].append("if")
        self.generic_visit(node)

    def visit_For(self, node):
        print("For loop found")
        self.data["loops"].append("for")
        self.generic_visit(node)

    def visit_While(self, node):
        print("While loop found")
        self.data["loops"].append(self._serialize_node(node))
        self.generic_visit(node)

    def visit_Return(self, node):
        print("Return statement found")
        self.data["functions"].append(self._serialize_node(node))
        self.generic_visit(node)


ASTVisitor = MyVisitor