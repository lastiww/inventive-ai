"""Multi-table manager — fixed grid layout with gap + size controls.

The user selects a grid (1x1, 1x2, 2x2, etc.) in the launcher
and adjusts Gap X, Gap Y, Largeur %, Hauteur % sliders.
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
    """Manages tables using a fixed grid layout."""

    def __init__(self, config: Config):
        self.config = config
        self.cols = max(config.grid_cols, 1)
        self.rows = max(config.grid_rows, 1)
        self.gap_x = config.grid_gap_x       # pixels between columns
        self.gap_y = config.grid_gap_y       # pixels between rows
        self.width_pct = config.grid_width_pct   # 80-120, table width %
        self.height_pct = config.grid_height_pct  # 80-120, table height %
        self.shift_x = config.grid_shift_x       # shift all cells left/right
        self.shift_y = config.grid_shift_y       # shift all cells up/down
        self.num_tables = self.cols * self.rows

        self.tables: list[TableInstance] = []
        for i in range(self.num_tables):
            self.tables.append(TableInstance(i, config))

    def _compute_cells(self, fw: int, fh: int) -> list[tuple[int, int, int, int]]:
        """Divide the frame into grid cells.

        Each cell's raw size = (total_width - gaps) / cols.
        Then width_pct / height_pct scale the cell, centered in its slot.

        Returns list of (x, y, w, h) in full-frame pixel coords.
        """
        total_gap_x = self.gap_x * (self.cols - 1) if self.cols > 1 else 0
        total_gap_y = self.gap_y * (self.rows - 1) if self.rows > 1 else 0

        # Raw cell size (100%)
        raw_w = (fw - total_gap_x) // max(self.cols, 1)
        raw_h = (fh - total_gap_y) // max(self.rows, 1)

        # Scaled cell size
        cell_w = int(raw_w * self.width_pct / 100)
        cell_h = int(raw_h * self.height_pct / 100)

        # Offset to center the scaled cell within its raw slot
        dx = (raw_w - cell_w) // 2
        dy = (raw_h - cell_h) // 2

        cells = []
        for r in range(self.rows):
            for c in range(self.cols):
                slot_x = c * (raw_w + self.gap_x)
                slot_y = r * (raw_h + self.gap_y)
                x = slot_x + dx + self.shift_x
                y = slot_y + dy + self.shift_y
                # Clamp to frame
                x = max(0, min(x, fw - 10))
                y = max(0, min(y, fh - 10))
                w = min(cell_w, fw - x)
                h = min(cell_h, fh - y)
                cells.append((x, y, max(w, 10), max(h, 10)))
        return cells

    def update_tables(self, frame: np.ndarray) -> list[tuple[np.ndarray, TableInstance]]:
        """Split frame into grid cells and return sub-frames.

        For 1x1 at 100%: full frame, no cropping.
        Otherwise: one sub-frame per cell.
        """
        fh, fw = frame.shape[:2]

        # Single table at default size → full frame
        if (self.num_tables == 1 and self.width_pct == 100
                and self.height_pct == 100 and self.gap_x == 0 and self.gap_y == 0):
            self.tables[0].region = (0, 0, fw, fh)
            return [(frame, self.tables[0])]

        cells = self._compute_cells(fw, fh)
        results = []
        for i, (x, y, w, h) in enumerate(cells):
            if i >= len(self.tables):
                break
            # Clamp to frame bounds
            x2 = min(x + w, fw)
            y2 = min(y + h, fh)
            self.tables[i].region = (x, y, x2 - x, y2 - y)
            sub = frame[y:y2, x:x2]
            results.append((sub, self.tables[i]))
        return results

    def get_label_anchors(self, table_index: int = 0) -> list[tuple[float, float]]:
        """Get overlay label anchors for a table (normalized to full frame)."""
        anchors = self.config.site_roi.player_label_anchors
        if not anchors:
            return []

        # Single table at default → raw anchors
        if self.num_tables == 1 and self.width_pct == 100 and self.height_pct == 100:
            return anchors

        table = self.tables[table_index]
        x, y, w, h = table.region

        # Estimate full frame size from first + last cell
        last = self.tables[-1]
        full_w = last.region[0] + last.region[2]
        full_h = last.region[1] + last.region[3]
        full_w = max(full_w, 1)
        full_h = max(full_h, 1)

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

        # Single table at default → full frame coords
        if self.num_tables == 1 and self.width_pct == 100 and self.height_pct == 100:
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
        """Get debug ROIs for ALL tables + cell borders."""
        all_rois = []

        # Draw cell borders first
        for i, table in enumerate(self.tables):
            if i >= self.num_tables:
                break
            x, y, w, h = table.region
            if w > 0 and h > 0:
                all_rois.append(((x, y, w, h), f"TABLE {i + 1}"))

        # Then per-table ROIs
        for i in range(min(self.num_tables, len(self.tables))):
            all_rois.extend(self.get_debug_rois(frame, i))
        return all_rois
