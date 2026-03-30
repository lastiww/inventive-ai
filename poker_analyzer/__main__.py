"""Allow running as: python -m poker_analyzer

Launches the GUI launcher by default.
Use --no-gui to run in CLI mode with command-line arguments.
"""
import sys

if "--no-gui" in sys.argv:
    sys.argv.remove("--no-gui")
    from poker_analyzer.main import main
else:
    from poker_analyzer.launcher import main

main()
