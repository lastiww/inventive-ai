"""Python wrapper for TexasSolver (C++ GTO solver)."""

import hashlib
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from threading import Thread

from poker_analyzer.config import SolverConfig
from poker_analyzer.models.game_state import GameState, SolverResult, Street
from poker_analyzer.solver.range_manager import RangeManager


CACHE_DIR = Path(__file__).parent / "precomputed"


class TexasSolver:
    """Wrapper for the TexasSolver CLI binary.

    TexasSolver is an open-source C++ postflop GTO solver.
    This wrapper:
    1. Constructs solver input files from game state
    2. Runs the solver via subprocess
    3. Parses the output into SolverResult
    4. Caches results to avoid re-solving identical spots
    """

    def __init__(self, config: SolverConfig):
        self.config = config
        self.range_manager = RangeManager()
        self._cache: dict[str, SolverResult] = {}
        self._solving = False
        self._current_result: SolverResult | None = None

        # Load cached solutions from disk
        self._load_cache()

    def is_solving(self) -> bool:
        return self._solving

    def solve_async(self, game_state: GameState, oop_range: str, ip_range: str):
        """Start solving in a background thread."""
        thread = Thread(
            target=self._solve_thread,
            args=(game_state, oop_range, ip_range),
            daemon=True,
        )
        thread.start()

    def _solve_thread(self, game_state: GameState, oop_range: str, ip_range: str):
        """Background solving thread."""
        self._solving = True
        self._current_result = None
        try:
            result = self.solve(game_state, oop_range, ip_range)
            self._current_result = result
        except Exception as e:
            print(f"[SOLVER ERROR] {e}")
            self._current_result = SolverResult()
        finally:
            self._solving = False

    def get_result(self) -> SolverResult | None:
        """Get the latest solver result (None if still solving)."""
        return self._current_result

    def solve(self, game_state: GameState, oop_range: str, ip_range: str) -> SolverResult:
        """Solve a postflop spot and return GTO strategy.

        Args:
            game_state: Current game state with board, pot, stacks.
            oop_range: OOP player's range string.
            ip_range: IP player's range string.

        Returns:
            SolverResult with action frequencies.
        """
        if game_state.street == Street.PREFLOP:
            return self._preflop_lookup(game_state)

        # Check cache
        cache_key = self._cache_key(game_state, oop_range, ip_range)
        if cache_key in self._cache:
            print("[SOLVER] Cache hit!")
            return self._cache[cache_key]

        # Build solver input
        input_text = self._build_input(game_state, oop_range, ip_range)

        # Run solver
        start = time.time()
        result = self._run_solver(input_text)
        elapsed = time.time() - start
        print(f"[SOLVER] Solved in {elapsed:.1f}s")

        # Cache result
        self._cache[cache_key] = result
        self._save_to_cache(cache_key, result)

        return result

    def _build_input(self, state: GameState, oop_range: str, ip_range: str) -> str:
        """Build TexasSolver input file content.

        TexasSolver input format:
        ```
        set_pot <pot_size>
        set_effective_stack <stack_size>
        set_board <board_cards>
        set_range_oop <range>
        set_range_ip <range>
        set_bet_sizes <flop_bet>,<flop_raise>,<turn_bet>,<turn_raise>,<river_bet>,<river_raise>
        set_allin_threshold <threshold>
        set_accuracy <accuracy>
        set_max_iteration <iterations>
        set_thread_num <threads>
        build_tree
        start_solve
        dump_result
        ```
        """
        eff_stack = state.get_effective_stack()
        board = state.board_str

        lines = [
            f"set_pot {state.pot_bb}",
            f"set_effective_stack {eff_stack}",
            f"set_board {board}",
            f"set_range_oop {self.range_manager.range_to_solver_format(oop_range)}",
            f"set_range_ip {self.range_manager.range_to_solver_format(ip_range)}",
            f"set_bet_sizes {self.config.flop_bet_sizes},{self.config.flop_raise_sizes},"
            f"{self.config.turn_bet_sizes},{self.config.turn_raise_sizes},"
            f"{self.config.river_bet_sizes},{self.config.river_raise_sizes}",
            f"set_allin_threshold {self.config.allin_threshold}",
            f"set_accuracy {self.config.accuracy}",
            f"set_max_iteration {self.config.max_iterations}",
            f"set_thread_num {self.config.thread_count}",
            "build_tree",
            "start_solve",
            "dump_result",
        ]

        return "\n".join(lines)

    def _run_solver(self, input_text: str) -> SolverResult:
        """Run TexasSolver binary and parse output."""
        binary = self.config.binary_path

        if not os.path.isfile(binary):
            print(f"[SOLVER ERROR] Binary not found: {binary}")
            print("[SOLVER] Please compile TexasSolver and set the binary_path in config.")
            return SolverResult()

        # Write input to temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(input_text)
            input_file = f.name

        try:
            proc = subprocess.run(
                [binary, "-i", input_file],
                capture_output=True,
                text=True,
                timeout=10,  # Hard 10s timeout (target <5s)
            )

            if proc.returncode != 0:
                print(f"[SOLVER ERROR] Exit code {proc.returncode}")
                print(f"[SOLVER STDERR] {proc.stderr[:500]}")
                return SolverResult()

            return self._parse_output(proc.stdout)

        except subprocess.TimeoutExpired:
            print("[SOLVER] Timeout (>10s) — try reducing tree complexity")
            return SolverResult()
        except FileNotFoundError:
            print(f"[SOLVER ERROR] Cannot execute: {binary}")
            return SolverResult()
        finally:
            os.unlink(input_file)

    def _parse_output(self, output: str) -> SolverResult:
        """Parse TexasSolver output into a SolverResult.

        Output format (simplified):
        ```
        Root:
        OOP strategy:
        CHECK: 45.2%
        BET 75%: 54.8%
        EV: 2.35
        ```
        """
        result = SolverResult()
        lines = output.strip().split("\n")

        in_strategy = False
        for line in lines:
            line = line.strip()

            if "strategy:" in line.lower():
                in_strategy = True
                continue

            if in_strategy and ":" in line and "%" in line:
                parts = line.split(":")
                if len(parts) == 2:
                    action = parts[0].strip().lower()
                    freq_str = parts[1].strip().replace("%", "")
                    try:
                        freq = float(freq_str) / 100.0
                        result.actions[action] = freq
                    except ValueError:
                        pass

            if line.lower().startswith("ev:"):
                try:
                    result.ev = float(line.split(":")[1].strip())
                except (ValueError, IndexError):
                    pass

            # Stop parsing after first strategy block
            if in_strategy and line == "":
                break

        return result

    def _preflop_lookup(self, state: GameState) -> SolverResult:
        """Simple preflop strategy lookup (not solver-based).

        Returns basic preflop GTO frequencies.
        """
        result = SolverResult()

        hero = state.hero
        if hero is None or hero.position is None:
            return result

        # Check if hero has an opening range for this position
        rfi = self.range_manager.get_rfi_range(hero.position)
        if hero.hole_cards:
            hand_str = self._hand_to_category(
                str(hero.hole_cards[0]), str(hero.hole_cards[1])
            )
            if hand_str in rfi:
                result.actions["raise"] = 1.0
                result.actions["fold"] = 0.0
            else:
                result.actions["raise"] = 0.0
                result.actions["fold"] = 1.0

        return result

    def _hand_to_category(self, card1_str: str, card2_str: str) -> str:
        """Convert two card strings to hand category.

        E.g., 'Ah', 'Kh' → 'AKs'
              'Ah', 'Kd' → 'AKo'
              'Ah', 'Ad' → 'AA'
        """
        r1, s1 = card1_str[0], card1_str[1]
        r2, s2 = card2_str[0], card2_str[1]

        # Order ranks (higher first)
        rank_order = "23456789TJQKA"
        if rank_order.index(r1) < rank_order.index(r2):
            r1, r2 = r2, r1
            s1, s2 = s2, s1

        if r1 == r2:
            return f"{r1}{r2}"
        elif s1 == s2:
            return f"{r1}{r2}s"
        else:
            return f"{r1}{r2}o"

    def _cache_key(self, state: GameState, oop_range: str, ip_range: str) -> str:
        """Generate a unique cache key for a solver spot."""
        key_data = f"{state.board_str}|{state.pot_bb:.1f}|{state.get_effective_stack():.1f}|{oop_range}|{ip_range}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def _load_cache(self):
        """Load cached solutions from disk."""
        cache_file = CACHE_DIR / "cache.json"
        if cache_file.exists():
            try:
                with open(cache_file) as f:
                    data = json.load(f)
                for key, val in data.items():
                    self._cache[key] = SolverResult(
                        actions=val.get("actions", {}),
                        ev=val.get("ev", 0.0),
                    )
                print(f"[SOLVER] Loaded {len(self._cache)} cached solutions")
            except Exception as e:
                print(f"[SOLVER] Cache load error: {e}")

    def _save_to_cache(self, key: str, result: SolverResult):
        """Save a solution to the disk cache."""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file = CACHE_DIR / "cache.json"

        data = {}
        if cache_file.exists():
            try:
                with open(cache_file) as f:
                    data = json.load(f)
            except Exception:
                pass

        data[key] = {"actions": result.actions, "ev": result.ev}

        with open(cache_file, "w") as f:
            json.dump(data, f, indent=2)
