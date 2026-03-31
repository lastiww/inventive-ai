"""Multi-table manager — auto-detects poker tables in the captured frame.

Detects tables by finding large green (poker felt) regions.
Each detected table gets its own OCR parser, solver state, and overlay labels.
"""

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

    def detect_tables(self, frame: np.ndarray) -> list[tuple[int, int, int, int]]:
        """Detect poker table regions in the frame.

        Looks for large green/teal areas (poker felt color).

        Returns:
            List of (x, y, w, h) bounding boxes for each detected table.
        """
        fh, fw = frame.shape[:2]
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # CoinPoker felt is green/teal
        # Winamax felt is darker green
        lower_green = np.array([35, 40, 40])
        upper_green = np.array([85, 255, 255])
        mask = cv2.inRange(hsv, lower_green, upper_green)

        # Clean up mask
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        # Find contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Filter by minimum area (at least 5% of frame = a real table)
        min_area = fh * fw * 0.03
        regions = []

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_area:
                continue

            x, y, w, h = cv2.boundingRect(contour)

            # Expand bounding box to include players around the table
            # Players sit around the felt, so extend by ~30% in each direction
            expand_x = int(w * 0.25)
            expand_y = int(h * 0.40)  # more vertical expansion for players above/below

            x = max(0, x - expand_x)
            y = max(0, y - expand_y)
            w = min(fw - x, w + expand_x * 2)
            h = min(fh - y, h + expand_y * 2)

            regions.append((x, y, w, h))

        # Sort by position (top-left to bottom-right)
        regions.sort(key=lambda r: (r[1] // (fh // 3), r[0]))

        # Limit to max tables
        regions = regions[:self.max_tables]

        return regions

    def update_tables(self, frame: np.ndarray) -> list[tuple[np.ndarray, TableInstance]]:
        """Detect tables and return sub-frames with their TableInstances.

        Returns:
            List of (sub_frame, table_instance) for each detected table.
        """
        regions = self.detect_tables(frame)

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
