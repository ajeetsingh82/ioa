import os

class KnowledgeBase:
    def __init__(self, agent_name):
        # Resolve path relative to the project root (assuming this file is in src/)
        base_dir = "."
        
        # Construct the full path: project_root/kb/{agent_name}.txt
        self.file_path = os.path.join(base_dir, 'kb', f"{agent_name}.txt")
        
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        if not os.path.exists(self.file_path):
            with open(self.file_path, 'w') as f: f.write("")

    def read(self, tail_chars=3000):
        if not os.path.exists(self.file_path):
            return ""
            
        with open(self.file_path, 'r') as f:
            content = f.read()
            
            if len(content) <= tail_chars:
                return content
            
            chunk = content[-tail_chars:]
            first_newline = chunk.find('\n')
            if first_newline != -1:
                return chunk[first_newline+1:]
            return chunk

    def append(self, text):
        with open(self.file_path, 'a') as f:
            f.write(f"\n{text}")

    def clear(self):
        with open(self.file_path, 'w') as f:
            f.write(f"--- RESET ---")