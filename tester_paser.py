import unittest
import ast

from visiter import ASTVisitor


class TestASTParser(unittest.TestCase):

    def parse_code(self, code):
        tree = ast.parse(code)

        visitor = ASTVisitor()
        visitor.visit(tree)

        return visitor.data

    def test_import(self):
        result = self.parse_code("import math")
        self.assertIn("math", result["imports"])

    def test_variable(self):
        result = self.parse_code("x = 10")
        self.assertIn("x", result["variables"])

    def test_function(self):
        result = self.parse_code("def hello(): pass")
        self.assertIn("hello", result["functions"])

    def test_class(self):
        result = self.parse_code("class Student: pass")
        self.assertIn("Student", result["classes"])

    def test_for(self):
        result = self.parse_code("for i in range(5): pass")
        self.assertIn("for", result["loops"])

    def test_while(self):
        result = self.parse_code("while True: break")
        self.assertIn("while", result["loops"])

    def test_if(self):
        result = self.parse_code("if True: pass")
        self.assertIn("if", result["conditions"])


if __name__ == "__main__":
    unittest.main()
