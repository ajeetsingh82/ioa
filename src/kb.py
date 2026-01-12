import os

class KnowledgeBase:
    def __init__(self, file_path):
        self.file_path = file_path
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        if not os.path.exists(self.file_path):
            with open(self.file_path, 'w') as f: f.write("")

    def read(self, tail_chars=3000):
        with open(self.file_path, 'r') as f:
            content = f.read()
            return content[-tail_chars:]

    def append(self, text):
        with open(self.file_path, 'a') as f:
            f.write(f"\n{text}")

    def clear(self):
        with open(self.file_path, 'w') as f:
            f.write(f"--- RESET ---")