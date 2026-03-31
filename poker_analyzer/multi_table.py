"""Multi-table manager — auto-detects poker tables in the captured frame.

Detects tables by finding large green (poker felt) regions.
Each detected table gets its own OCR parser, solver state, and overlay labels.
"""

import cv2
import numpy as np

from poker_analyzer.config import Config
from poker_analyzer.models.game_state import GameState, SolverResult, Street
from poker_analyzer.ocr.table_detector import detect_tables
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

        # Table region in the full frame (x, y, w, h)
        self.region: tuple[int, int, int, int] = (0, 0, 0, 0)


class MultiTableManager:
    """Auto-detects and manages multiple poker tables.

    Finds poker tables by detecting large green (felt) regions in the frame.
    """

    def __init__(self, config: Config, max_tables: int = 6):
        self.config = config
        self.max_tables = max_tables
        self.tables: list[TableInstance] = []
        self._last_regions: list[tuple[int, int, int, int]] = []

    def detect_tables_in_frame(self, frame: np.ndarray) -> list[tuple[int, int, int, int]]:
        """Detect poker table regions in the frame.

        Delegates to table_detector module.

        Returns:
            List of (x, y, w, h) bounding boxes for each detected table.
        """
        return detect_tables(frame, max_tables=self.max_tables)

    def update_tables(self, frame: np.ndarray) -> list[tuple[np.ndarray, TableInstance]]:
        """Detect tables and return sub-frames with their TableInstances.

        Returns:
            List of (sub_frame, table_instance) for each detected table.
        """
        regions = self.detect_tables_in_frame(frame)

        # If no tables detected, keep using last known regions
        if not regions and self._last_regions:
            regions = self._last_regions
        elif regions:
            self._last_regions = regions

        # Ensure we have enough TableInstance objects
        while len(self.tables) < len(regions):
            self.tables.append(TableInstance(len(self.tables), self.config))

        results = []
        for i, (x, y, w, h) in enumerate(regions):
            table = self.tables[i]
            table.region = (x, y, w, h)

            # Extract sub-frame for this table
            sub = frame[y:y + h, x:x + w]
            results.append((sub, table))

        return results

    def get_label_anchors_for_table(
        self,
        table: TableInstance,
        frame_w: int,
        frame_h: int,
    ) -> list[tuple[float, float]]:
        """Get overlay label anchors in full-frame normalized coords."""
        anchors = self.config.site_roi.player_label_anchors
        if not anchors:
            return []

        x, y, w, h = table.region
        full_anchors = []
        for ax, ay in anchors:
            abs_x = x + ax * w
            abs_y = y + ay * h
            full_anchors.append((abs_x / frame_w, abs_y / frame_h))

        return full_anchors

    def get_debug_rois_for_table(
        self,
        table: TableInstance,
        sub_frame: np.ndarray,
    ) -> list[tuple[tuple[int, int, int, int], str]]:
        """Get debug ROIs offset to full-frame coordinates."""
        local_rois = table.parser.get_debug_rois(sub_frame)
        ox, oy, _, _ = table.region
        tid = table.table_id + 1

        result = []
        for (rx, ry, rw, rh), label in local_rois:
            result.append(((rx + ox, ry + oy, rw, rh), f"T{tid} {label}"))

        return result

    def get_table_border_rois(self) -> list[tuple[tuple[int, int, int, int], str]]:
        """Get bounding box ROIs for detected tables (for debug display)."""
        rois = []
        for table in self.tables:
            x, y, w, h = table.region
            if w > 0 and h > 0:
                rois.append(((x, y, w, h), f"TABLE {table.table_id + 1}"))
        return rois
