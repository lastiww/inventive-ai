"""Multi-table manager — fixed grid layout with scale/gap/offset controls.

The user selects a grid (1x1, 1x2, 2x2, etc.) in the launcher
and adjusts Scale, Gap, Offset, Top Offset sliders.
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

    # CoinPoker table width/height ratio (constant, adjustable later)
    TABLE_RATIO = 1.79

    def __init__(self, config: Config):
        self.config = config
        self.cols = max(config.grid_cols, 1)
        self.rows = max(config.grid_rows, 1)
        self.num_tables = self.cols * self.rows

        # Slider values (updated live from launcher)
        self.scale_pct = 100      # table scale %
        self.gap_x_pct = 0.0      # gap X as % of cell width
        self.gap_y_pct = 0.0      # gap Y as % of cell height
        self.top_offset = 0       # top offset in pixels (title bar)
        self.offset_x_pct = 0.0   # fine X offset as % of cell width
        self.offset_y_pct = 0.0   # fine Y offset as % of cell height

        self.tables: list[TableInstance] = []
        for i in range(self.num_tables):
            self.tables.append(TableInstance(i, config))

    def _compute_cells(self, fw: int, fh: int) -> list[tuple[int, int, int, int]]:
        """Divide the frame into grid cells with scale/gap/offset.

        Logic:
          1. Divide screen into raw cells (rows x cols)
          2. Apply gap_x / gap_y (% of cell size)
          3. Apply scale (with fixed ratio)
          4. Apply top_offset (skip title bar)
          5. Apply offset_x / offset_y (fine tuning)

        Returns list of (x, y, w, h) in full-frame pixel coords.
        """
        raw_w = fw // max(self.cols, 1)
        raw_h = fh // max(self.rows, 1)

        # Scaled table dimensions (width from scale, height from ratio)
        scale = self.scale_pct / 100.0
        rect_w = int(raw_w * scale)
        rect_h = int(rect_w / self.TABLE_RATIO)

        # Gap in pixels (% of raw cell)
        gx = raw_w * self.gap_x_pct / 100.0
        gy = raw_h * self.gap_y_pct / 100.0

        # Fine offset in pixels (% of raw cell)
        ox = raw_w * self.offset_x_pct / 100.0
        oy = raw_h * self.offset_y_pct / 100.0

        cells = []
        for r in range(self.rows):
            for c in range(self.cols):
                # Center of the raw slot
                slot_cx = c * raw_w + raw_w // 2
                slot_cy = r * raw_h + raw_h // 2

                # Apply gap (push outward from center of grid)
                slot_cx += int(gx * (c - (self.cols - 1) / 2))
                slot_cy += int(gy * (r - (self.rows - 1) / 2))

                # Top-left of the scaled rect, centered in slot
                x = int(slot_cx - rect_w // 2 + ox)
                y = int(slot_cy - rect_h // 2 + oy + self.top_offset)

                # Clamp to frame
                x = max(0, min(x, fw - 10))
                y = max(0, min(y, fh - 10))
                w = min(rect_w, fw - x)
                h = min(rect_h, fh - y)

                cells.append((x, y, max(w, 10), max(h, 10)))
        return cells

    def update_tables(self, frame: np.ndarray) -> list[tuple[np.ndarray, TableInstance]]:
        """Split frame into grid cells and return sub-frames."""
        fh, fw = frame.shape[:2]

        # Single table at defaults → full frame
        if (self.num_tables == 1 and self.scale_pct == 100
                and self.gap_x_pct == 0 and self.gap_y_pct == 0
                and self.top_offset == 0 and self.offset_x_pct == 0
                and self.offset_y_pct == 0):
            self.tables[0].region = (0, 0, fw, fh)
            return [(frame, self.tables[0])]

        cells = self._compute_cells(fw, fh)
        results = []
        for i, (x, y, w, h) in enumerate(cells):
            if i >= len(self.tables):
                break
            x2 = min(x + w, fw)
            y2 = min(y + h, fh)
            self.tables[i].region = (x, y, x2 - x, y2 - y)
            sub = frame[y:y2, x:x2]
            results.append((sub, self.tables[i]))
        return results

    def get_cell_borders(self, fw: int, fh: int) -> list[tuple[tuple[int, int, int, int], str]]:
        """Get cell border rectangles (for debug overlay). No frame needed."""
        cells = self._compute_cells(fw, fh)
        rois = []
        for i, (x, y, w, h) in enumerate(cells):
            rois.append(((x, y, w, h), f"TABLE {i + 1}"))
        return rois

    def get_label_anchors(self, table_index: int = 0) -> list[tuple[float, float]]:
        """Get overlay label anchors for a table (normalized to full frame)."""
        anchors = self.config.site_roi.player_label_anchors
        if not anchors:
            return []

        if self.num_tables == 1 and self.scale_pct == 100:
            return anchors

        table = self.tables[table_index]
        x, y, w, h = table.region
        last = self.tables[min(self.num_tables - 1, len(self.tables) - 1)]
        full_w = max(last.region[0] + last.region[2], 1)
        full_h = max(last.region[1] + last.region[3], 1)

        result = []
        for ax, ay in anchors:
            result.append(((x + ax * w) / full_w, (y + ay * h) / full_h))
        return result

    def get_debug_rois(self, frame: np.ndarray, table_index: int = 0) -> list[tuple[tuple[int, int, int, int], str]]:
        """Get per-table debug ROIs in full-frame pixel coords."""
        if table_index >= len(self.tables):
            return []
        table = self.tables[table_index]

        if self.num_tables == 1 and self.scale_pct == 100:
            return table.parser.get_debug_rois(frame)

        x, y, w, h = table.region
        sub = frame[y:y + h, x:x + w]
        local_rois = table.parser.get_debug_rois(sub)
        tid = table.table_id + 1
        return [((rx + x, ry + y, rw, rh), f"T{tid} {label}")
                for (rx, ry, rw, rh), label in local_rois]

    def get_all_debug_rois(self, frame: np.ndarray) -> list[tuple[tuple[int, int, int, int], str]]:
        """Get debug ROIs for ALL tables + cell borders."""
        fh, fw = frame.shape[:2]
        all_rois = self.get_cell_borders(fw, fh)
        for i in range(min(self.num_tables, len(self.tables))):
            all_rois.extend(self.get_debug_rois(frame, i))
        return all_rois
