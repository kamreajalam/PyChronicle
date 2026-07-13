import ast
import json
from visiter import MyVisitor


def to_jsonable(value):
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


# Read the source code from a file
with open("sample.py", "r") as file:
    source_code = file.read()

# Parse the source code into an AST
tree = ast.parse(source_code)
print(tree)

# Visitor for the AST
visitor = MyVisitor()
visitor.visit(tree)

# Display the collected data
print("visitor data:", visitor.data)

# Write the full AST as JSON
with open("ast.json", "w") as file:
    json.dump(to_jsonable(tree), file, indent=4)

# Write the visitor summary as JSON
with open("output.json", "w") as file:
    json.dump(visitor.data, file, indent=4)

print("JSON files created successfully!")
print(ast.dump(tree, indent=4))