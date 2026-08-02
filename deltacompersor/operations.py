class OperationGenerator:
    def generate(self, opcodes, old_text, new_text):
        operations = []
        for tag, i1, i2, j1, j2 in opcodes:
            if tag == 'equal':
                operations.append({
                    'type': 'COPY',
                    'start': i1,
                    'length': i2 - i1
                })
            elif tag == 'insert':
                operations.append({
                    'type': 'ADD',
                    'text': new_text[j1:j2]
                })
            elif tag == 'copy':
                operations.append({
                    'type': 'COPY',
                    'start': i1,
                    'length': i2 - i1
                })
            elif tag == 'add':
                operations.append({
                    'type': 'ADD',
                    'text': new_text[j1:j2]
                })
            elif tag == 'replace':
                operations.append({
                    'type': 'REPLACE',
                    'text': new_text[j1:j2]
                })
            elif tag == 'delete':
                pass
        return operations