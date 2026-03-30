"""Build script to create a standalone .exe with PyInstaller.

Usage:
    python build_exe.py

This creates: dist/PokerGTOAnalyzer.exe
"""

import subprocess
import sys


def build():
    # Use ; on Windows for --add-data separator, : on Linux/Mac
    sep = ";" if sys.platform == "win32" else ":"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", "PokerGTOAnalyzer",
        "--windowed",  # no console window
        "--add-data", f"poker_analyzer/ocr/templates{sep}poker_analyzer/ocr/templates",
        "--add-data", f"poker_analyzer/solver/precomputed{sep}poker_analyzer/solver/precomputed",
        "--hidden-import", "poker_analyzer",
        "--hidden-import", "poker_analyzer.capture",
        "--hidden-import", "poker_analyzer.ocr",
        "--hidden-import", "poker_analyzer.solver",
        "--hidden-import", "poker_analyzer.display",
        "--hidden-import", "poker_analyzer.models",
        "--hidden-import", "poker_analyzer.multi_table",
        "--hidden-import", "poker_analyzer.launcher",
        "poker_analyzer/__main__.py",
    ]

    print("Building .exe with PyInstaller...")
    print(f"Command: {' '.join(cmd)}")
    result = subprocess.run(cmd)

    if result.returncode == 0:
        print("\nBuild successful!")
        print("Executable: dist/PokerGTOAnalyzer.exe")
        print("\nDouble-click PokerGTOAnalyzer.exe to launch!")
    else:
        print("\nBuild failed!")
        sys.exit(1)


if __name__ == "__main__":
    build()
