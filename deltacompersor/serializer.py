import json
import os


class Serializer:

    def save(self, delta, filename):
        dir_name = os.path.dirname(filename)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with open(filename, "w", encoding="utf-8") as file:
            json.dump(delta, file, indent=4)

    def load(self, filename):
        with open(filename, "r", encoding="utf-8") as file:
            return json.load(file)