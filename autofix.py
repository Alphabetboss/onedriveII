import os
import re

PROJECT_DIR = r"C:\Users\alpha\Desktop\IngeniousIrrigation"


def clean_file(path):
    with open(path, "rb") as f:
        raw = f.read()

    # Remove BOM if present
    if raw.startswith(b'\xef\xbb\xbf'):
        raw = raw[3:]

    text = raw.decode("utf-8", errors="replace")

    # Fix Windows paths
    text = re.sub(r'(?<!r)"([A-Z]:\\[^"]+)"', r'r"\1"', text)

    # Normalize indentation
    lines = text.splitlines()
    fixed_lines = []
    for line in lines:
        # Convert tabs to 4 spaces
        fixed_lines.append(line.replace("\t", "    "))

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(fixed_lines))


def scan_and_fix():
    for root, _, files in os.walk(PROJECT_DIR):
        for file in files:
            if file.endswith(".py"):
                full_path = os.path.join(root, file)
                try:
                    compile(open(full_path, encoding="utf-8").read(),
                            full_path, "exec")
                except SyntaxError as e:
                    print(f"[FIXING] {file}: {e}")
                    clean_file(full_path)
                except Exception as e:
                    print(f"[SKIP] {file}: {e}")


if __name__ == "__main__":
    scan_and_fix()