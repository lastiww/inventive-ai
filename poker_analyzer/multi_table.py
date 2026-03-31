"""Multi-table manager — detects poker tables in the captured frame.

Uses the FULL frame for OCR (no sub-frame cropping).
Table detection only runs every N seconds to avoid lag.
"""

import time

import cv2
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


class MultiTableManager:
    """Manages poker table(s) — uses full frame, no cropping."""

    def __init__(self, config: Config, max_tables: int = 6):
        self.config = config
        self.max_tables = max_tables
        self.tables: list[TableInstance] = []
        self._table_count: int = 1
        self._last_detect_time: float = 0.0
        self._detect_interval: float = 3.0  # re-detect every 3 seconds

        # Always create at least 1 table
        self.tables.append(TableInstance(0, config))

    def update_tables(self, frame: np.ndarray) -> list[tuple[np.ndarray, TableInstance]]:
        """Return full frame paired with table instances.

        No sub-frame extraction — the full frame is used directly.
        Table count is re-evaluated periodically (every 3 seconds).
        """
        now = time.time()

        # Re-detect table count periodically (not every frame)
        if now - self._last_detect_time > self._detect_interval:
            self._last_detect_time = now
            count = self._count_tables(frame)
            if count != self._table_count:
                self._table_count = count
                # Ensure enough table instances
                while len(self.tables) < count:
                    self.tables.append(TableInstance(len(self.tables), self.config))

        # For now: single table = full frame
        # (multi-table tiling will be added later)
        results = []
        for i in range(min(self._table_count, len(self.tables))):
            results.append((frame, self.tables[i]))

        return results

    def _count_tables(self, frame: np.ndarray) -> int:
        """Count how many poker tables are visible via green felt detection."""
        fh, fw = frame.shape[:2]
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        lower = np.array([30, 50, 50])
        upper = np.array([85, 255, 255])
        mask = cv2.inRange(hsv, lower, upper)

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        min_area = fh * fw * 0.03
        count = 0
        for cnt in contours:
            if cv2.contourArea(cnt) >= min_area:
                x, y, w, h = cv2.boundingRect(cnt)
                ratio = w / max(h, 1)
                if 1.2 < ratio < 4.0:
                    count += 1

        return max(count, 1)

    def get_label_anchors(self) -> list[tuple[float, float]]:
        """Get overlay label anchors (normalized 0-1, full frame)."""
        return self.config.site_roi.player_label_anchors

    def get_debug_rois(self, frame: np.ndarray) -> list[tuple[tuple[int, int, int, int], str]]:
        """Get debug ROI rectangles in pixel coordinates for the full frame."""
        if not self.tables:
            return []
        return self.tables[0].parser.get_debug_rois(frame)
