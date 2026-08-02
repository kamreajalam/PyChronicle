from difflib import SequenceMatcher


class Matcher:

    def compare(self, old_text, new_text):
        matcher = SequenceMatcher(None, old_text, new_text)
        return matcher.get_opcodes()