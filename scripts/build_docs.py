"""Build English API HTML documentation using Python's built-in pydoc.

Run from the repository root: python scripts/build_docs.py
No internet access or additional documentation package is required.
"""
from pathlib import Path
import os
import subprocess
import sys


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    target = root / "docs" / "api"
    target.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "src") + os.pathsep + env.get("PYTHONPATH", "")
    modules = ("apple_tree_project", "apple_tree_project.manifest",
               "apple_tree_project.metrics", "apple_tree_project.audit")
    for module in modules:
        subprocess.run([sys.executable, "-m", "pydoc", "-w", module],
                       cwd=target, env=env, check=True)
    print(f"Generated HTML API pages in {target}")


if __name__ == "__main__":
    main()
