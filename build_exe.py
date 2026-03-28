"""Build script to create a standalone .exe with PyInstaller.

Usage:
    python build_exe.py

This creates: dist/PokerGTOAnalyzer.exe
"""

import subprocess
import sys


def build():
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", "PokerGTOAnalyzer",
        "--windowed",  # no console window
        "--add-data", "poker_analyzer/ocr/templates:poker_analyzer/ocr/templates",
        "--add-data", "poker_analyzer/solver/precomputed:poker_analyzer/solver/precomputed",
        "--hidden-import", "poker_analyzer",
        "--hidden-import", "poker_analyzer.capture",
        "--hidden-import", "poker_analyzer.ocr",
        "--hidden-import", "poker_analyzer.solver",
        "--hidden-import", "poker_analyzer.display",
        "--hidden-import", "poker_analyzer.models",
        "poker_analyzer/main.py",
    ]

    print("Building .exe with PyInstaller...")
    print(f"Command: {' '.join(cmd)}")
    result = subprocess.run(cmd)

    if result.returncode == 0:
        print("\nBuild successful!")
        print("Executable: dist/PokerGTOAnalyzer.exe")
    else:
        print("\nBuild failed!")
        sys.exit(1)


if __name__ == "__main__":
    build()
