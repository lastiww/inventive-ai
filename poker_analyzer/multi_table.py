"""Multi-table manager — fixed grid layout with gap/padding controls.

The user selects a grid (1x1, 1x2, 2x2, etc.) in the launcher
and adjusts Gap X, Gap Y, and Padding sliders.
The captured frame is divided into cells accordingly.
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
    """State for a single table."""

    def __init__(self, table_id: int, config: Config):
        self.table_id = table_id
        self.parser = TableParser(config)
        self.solver = TexasSolver(config.solver)
        self.range_manager = RangeManager()
        self.tracker = PlayerTracker()
        self.exploit_solver = ExploitativeSolver(config.solver, self.tracker)

        self.game_state: GameState | None = None
        self.gto_result: SolverResult | None = None
        self.exploit_result: SolverResult | None = None
        self.last_board_str: str = ""
        self.last_pot: float = 0.0
        self.last_solve_time: float = 0.0

        # Cell region in the full frame (x, y, w, h)
        self.region: tuple[int, int, int, int] = (0, 0, 0, 0)


class MultiTableManager:
    """Manages tables using a fixed grid layout with gap/padding."""

    def __init__(self, config: Config):
        self.config = config
        self.cols = max(config.grid_cols, 1)
        self.rows = max(config.grid_rows, 1)
        self.gap_x = config.grid_gap_x    # pixels between tables horizontally
        self.gap_y = config.grid_gap_y    # pixels between tables vertically
        self.padding = config.grid_padding  # shrink each cell inward (pixels)
        self.num_tables = self.cols * self.rows

        self.tables: list[TableInstance] = []
        for i in range(self.num_tables):
            self.tables.append(TableInstance(i, config))

    def _compute_cells(self, fw: int, fh: int) -> list[tuple[int, int, int, int]]:
        """Divide the frame into grid cells with gaps and padding.

        Layout:
          gap_x is the total horizontal space between columns.
          gap_y is the total vertical space between rows.
          padding shrinks each cell inward on all 4 sides.

        Returns list of (x, y, w, h) for each cell.
        """
        # Total gap space
        total_gap_x = self.gap_x * (self.cols - 1) if self.cols > 1 else 0
        total_gap_y = self.gap_y * (self.rows - 1) if self.rows > 1 else 0

        # Cell size before padding
        cell_w = (fw - total_gap_x) // self.cols
        cell_h = (fh - total_gap_y) // self.rows

        cells = []
        for r in range(self.rows):
            for c in range(self.cols):
                x = c * (cell_w + self.gap_x) + self.padding
                y = r * (cell_h + self.gap_y) + self.padding
                w = cell_w - self.padding * 2
                h = cell_h - self.padding * 2
                # Clamp
                w = max(w, 10)
                h = max(h, 10)
                cells.append((x, y, w, h))
        return cells

    def update_tables(self, frame: np.ndarray) -> list[tuple[np.ndarray, TableInstance]]:
        """Split frame into grid cells and return sub-frames.

        For 1x1 with no padding: full frame, no cropping.
        Otherwise: one sub-frame per cell.
        """
        fh, fw = frame.shape[:2]

        # Single table, no padding → use full frame directly
        if self.num_tables == 1 and self.padding == 0:
            self.tables[0].region = (0, 0, fw, fh)
            return [(frame, self.tables[0])]

        cells = self._compute_cells(fw, fh)
        results = []
        for i, (x, y, w, h) in enumerate(cells):
            if i >= len(self.tables):
                break
            self.tables[i].region = (x, y, w, h)
            sub = frame[y:y + h, x:x + w]
            results.append((sub, self.tables[i]))
        return results

    def get_label_anchors(self, table_index: int = 0) -> list[tuple[float, float]]:
        """Get overlay label anchors for a table (normalized to full frame)."""
        anchors = self.config.site_roi.player_label_anchors
        if not anchors:
            return []

        # Single table no padding → raw anchors
        if self.num_tables == 1 and self.padding == 0:
            return anchors

        table = self.tables[table_index]
        x, y, w, h = table.region

        # We need the full frame dimensions to normalize
        # Estimate from grid: total width = cols * (cell_w + gap) - gap
        cell_w_padded = w + self.padding * 2
        cell_h_padded = h + self.padding * 2
        full_w = self.cols * cell_w_padded + self.gap_x * (self.cols - 1)
        full_h = self.rows * cell_h_padded + self.gap_y * (self.rows - 1)

        result = []
        for ax, ay in anchors:
            abs_x = x + ax * w
            abs_y = y + ay * h
            result.append((abs_x / full_w, abs_y / full_h))
        return result

    def get_debug_rois(self, frame: np.ndarray, table_index: int = 0) -> list[tuple[tuple[int, int, int, int], str]]:
        """Get debug ROI rectangles in pixel coordinates."""
        if table_index >= len(self.tables):
            return []
        table = self.tables[table_index]

        # Single table no padding → full frame coords
        if self.num_tables == 1 and self.padding == 0:
            return table.parser.get_debug_rois(frame)

        # Multi-table → local ROIs offset to full frame
        x, y, w, h = table.region
        sub = frame[y:y + h, x:x + w]
        local_rois = table.parser.get_debug_rois(sub)
        tid = table.table_id + 1

        result = []
        for (rx, ry, rw, rh), label in local_rois:
            result.append(((rx + x, ry + y, rw, rh), f"T{tid} {label}"))
        return result

    def get_all_debug_rois(self, frame: np.ndarray) -> list[tuple[tuple[int, int, int, int], str]]:
        """Get debug ROIs for ALL tables."""
        all_rois = []
        for i in range(min(self.num_tables, len(self.tables))):
            all_rois.extend(self.get_debug_rois(frame, i))
        return all_rois
