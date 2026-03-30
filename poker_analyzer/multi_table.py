"""Multi-table manager — splits a captured frame into individual tables.

Supports tiled table layouts (e.g., 2x3 for 6 tables).
Each table gets its own OCR parser, solver state, and overlay labels.
"""

import numpy as np

from poker_analyzer.config import Config
from poker_analyzer.models.game_state import GameState, SolverResult, Street
from poker_analyzer.ocr.table_parser import TableParser
from poker_analyzer.solver.exploitative import ExploitativeSolver
from poker_analyzer.solver.player_tracker import PlayerTracker
from poker_analyzer.solver.range_manager import RangeManager
from poker_analyzer.solver.texas_solver import TexasSolver


class TableInstance:
    """State for a single table in a multi-table setup."""

    def __init__(self, table_id: int, config: Config):
        self.table_id = table_id
        self.parser = TableParser(config)
        self.solver = TexasSolver(config.solver)
        self.range_manager = RangeManager()
        self.tracker = PlayerTracker()
        self.exploit_solver = ExploitativeSolver(config.solver, self.tracker)

        # Per-table state
        self.game_state: GameState | None = None
        self.gto_result: SolverResult | None = None
        self.exploit_result: SolverResult | None = None
        self.last_board_str: str = ""
        self.last_pot: float = 0.0
        self.last_solve_time: float = 0.0


class MultiTableManager:
    """Manages multiple poker tables from a single captured frame.

    The captured frame (e.g., 1920x1080) is split into a grid of
    sub-frames, each containing one poker table. Each table is
    analyzed independently with its own OCR and solver state.

    Example layouts:
        1x1 = single table (full frame)
        2x1 = 2 tables side by side
        1x2 = 2 tables stacked vertically
        2x2 = 4 tables (2 cols x 2 rows)
        3x2 = 6 tables (3 cols x 2 rows)
        2x3 = 6 tables (2 cols x 3 rows)
    """

    def __init__(self, config: Config, cols: int = 1, rows: int = 1):
        self.config = config
        self.cols = cols
        self.rows = rows
        self.num_tables = cols * rows

        # Create one TableInstance per table slot
        self.tables: list[TableInstance] = []
        for i in range(self.num_tables):
            self.tables.append(TableInstance(i, config))

    def split_frame(self, frame: np.ndarray) -> list[tuple[np.ndarray, int, int, int, int]]:
        """Split the captured frame into sub-frames for each table.

        Returns:
            List of (sub_frame, offset_x, offset_y, width, height)
            for each table slot.
        """
        fh, fw = frame.shape[:2]
        table_w = fw // self.cols
        table_h = fh // self.rows

        results = []
        for row in range(self.rows):
            for col in range(self.cols):
                x = col * table_w
                y = row * table_h
                sub = frame[y:y + table_h, x:x + table_w]
                results.append((sub, x, y, table_w, table_h))

        return results

    def get_label_anchors_for_table(
        self,
        table_idx: int,
        offset_x: int,
        offset_y: int,
        table_w: int,
        table_h: int,
        frame_w: int,
        frame_h: int,
    ) -> list[tuple[float, float]]:
        """Convert per-table normalized anchors to full-frame normalized coords.

        Takes the player_label_anchors from config (normalized 0-1 within
        a single table) and converts them to full-frame coordinates.
        """
        anchors = self.config.site_roi.player_label_anchors
        if not anchors:
            return []

        full_anchors = []
        for ax, ay in anchors:
            # Convert from table-local to full-frame coordinates
            abs_x = offset_x + ax * table_w
            abs_y = offset_y + ay * table_h
            # Normalize to full frame
            full_anchors.append((abs_x / frame_w, abs_y / frame_h))

        return full_anchors

    def get_debug_rois_for_table(
        self,
        table: TableInstance,
        sub_frame: np.ndarray,
        offset_x: int,
        offset_y: int,
    ) -> list[tuple[tuple[int, int, int, int], str]]:
        """Get debug ROIs offset to full-frame coordinates."""
        local_rois = table.parser.get_debug_rois(sub_frame)

        offset_rois = []
        for (x, y, w, h), label in local_rois:
            offset_rois.append(((x + offset_x, y + offset_y, w, h), f"T{table.table_id + 1} {label}"))

        return offset_rois
