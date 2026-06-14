"""Check all Python files compile."""
import os
import sys

base = os.path.dirname(os.path.abspath(__file__))
errors = []
count = 0

for root, dirs, files in os.walk(base):
    if "__pycache__" in root or ".git" in root or ".pytest_cache" in root:
        continue
    for f in files:
        if f.endswith(".py"):
            path = os.path.join(root, f)
            count += 1
            try:
                with open(path, encoding="utf-8") as fh:
                    compile(fh.read(), path, "exec")
            except SyntaxError as e:
                errors.append((os.path.relpath(path, base), str(e)))

for p, e in errors:
    print(f"FAIL: {p}: {e}")
if not errors:
    print(f"All {count} Python files compile OK")
else:
    print(f"\n{len(errors)} file(s) failed")
    sys.exit(1)
