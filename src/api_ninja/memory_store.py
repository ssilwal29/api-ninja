import json


class MemoryStore:
    def __init__(self):
        self.context_str = ""

    def store(self, obj, label: str = None):
        if isinstance(obj, (dict, list)):
            text = json.dumps(obj, indent=2)
        else:
            text = str(obj)

        if label:
            entry = f"\n[{label}]\n{text}"
        else:
            entry = f"\n{text}"

        self.context_str += entry

    def get_context(self) -> str:
        return self.context_str.strip()
