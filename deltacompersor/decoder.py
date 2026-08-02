class Decoder:

    def decode(self, old_text, delta):
        result = ""
        for op in delta.get("operations", []):
            op_type = op.get("type") or op.get("operation")

            if op_type in ("COPY", "equal"):
                if "start" in op and "length" in op:
                    start = op["start"]
                    end = start + op["length"]
                    result += old_text[start:end]
                elif "text" in op:
                    result += op["text"]

            elif op_type in ("ADD", "insert"):
                result += op.get("text", op.get("new", ""))

            elif op_type in ("REPLACE", "replace"):
                result += op.get("text", op.get("new", ""))

            elif op_type == "delete":
                pass

        return result