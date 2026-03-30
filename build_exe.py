"""Build script to create a standalone .exe with PyInstaller.

Usage:
    python build_exe.py

This creates: dist/PokerGTOAnalyzer/PokerGTOAnalyzer.exe
"""

import subprocess
import sys


def build():
    sep = ";" if sys.platform == "win32" else ":"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "PokerGTOAnalyzer",
        "--noconfirm",            # overwrite without asking
        "--clean",                # clean cache
        "--add-data", f"poker_analyzer/ocr/templates{sep}poker_analyzer/ocr/templates",
        "--add-data", f"poker_analyzer/solver/precomputed{sep}poker_analyzer/solver/precomputed",
        "--hidden-import", "poker_analyzer",
        "--hidden-import", "poker_analyzer.capture",
        "--hidden-import", "poker_analyzer.capture.video_capture",
        "--hidden-import", "poker_analyzer.ocr",
        "--hidden-import", "poker_analyzer.ocr.card_detector",
        "--hidden-import", "poker_analyzer.ocr.text_reader",
        "--hidden-import", "poker_analyzer.ocr.table_parser",
        "--hidden-import", "poker_analyzer.solver",
        "--hidden-import", "poker_analyzer.solver.texas_solver",
        "--hidden-import", "poker_analyzer.solver.range_manager",
        "--hidden-import", "poker_analyzer.solver.exploitative",
        "--hidden-import", "poker_analyzer.solver.player_tracker",
        "--hidden-import", "poker_analyzer.display",
        "--hidden-import", "poker_analyzer.display.overlay",
        "--hidden-import", "poker_analyzer.models",
        "--hidden-import", "poker_analyzer.models.game_state",
        "--hidden-import", "poker_analyzer.multi_table",
        "--hidden-import", "poker_analyzer.launcher",
        "--hidden-import", "poker_analyzer.main",
        "poker_analyzer/launcher.py",
    ]

    print("Building PokerGTOAnalyzer.exe ...")
    print("This may take a few minutes.\n")
    result = subprocess.run(cmd)

    if result.returncode == 0:
        print("\n" + "=" * 50)
        print("  BUILD SUCCESSFUL!")
        print("  Executable: dist/PokerGTOAnalyzer/PokerGTOAnalyzer.exe")
        print("=" * 50)
    else:
        print("\nBuild failed!")
        sys.exit(1)


if __name__ == "__main__":
    build()
