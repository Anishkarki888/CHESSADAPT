"""
Composition mixins for structured logging and state tracking.

LoggingMixin  — attaches a per-instance Python logger with rotating file
               output and structured context fields (FEN, rules, move).
StateTrackingMixin — records every push/validate event into an append-only
                     event log for post-experiment analysis and scoring.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

import chess

# ── Logging constants ────────────────────────────────────────────────────────
LOG_DIR = Path("data/logs")
LOG_FORMAT = (
    "%(asctime)s | %(levelname)-5s | %(name)s | %(message)s"
)
MAX_LOG_BYTES = 5 * 1024 * 1024  # 5 MB per file
LOG_BACKUP_COUNT = 3


# ── Event dataclass ──────────────────────────────────────────────────────────
@dataclass
class MoveEvent:
    """A single recorded event during board interaction."""

    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = field(default_factory=time.time)
    fen_before: str = ""
    fen_after: str = ""
    move_uci: str = ""
    rule_names: list[str] = field(default_factory=list)
    category: str = ""
    is_legal_perturbed: bool = False
    is_legal_standard: bool = False
    is_inhibition_failure: bool = False
    elapsed_ms: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# ── LoggingMixin ─────────────────────────────────────────────────────────────
class LoggingMixin:
    """
    Attaches a named Python logger with both console and rotating-file
    handlers.  Call ``_init_logging(name, rule_names)`` once during
    ``__init__`` of the host class.

    Log entries are plain-text but carry structured context so they can be
    grep'd or parsed programmatically.
    """

    _logger: logging.Logger

    def _init_logging(
        self,
        name: str = "composition",
        rule_names: list[str] | None = None,
    ) -> None:
        self._rule_names = rule_names or []
        self._logger = logging.getLogger(f"chessadapt.{name}")
        self._logger.setLevel(logging.DEBUG)

        # avoid duplicating handlers on re-init
        if not self._logger.handlers:
            # console handler — INFO and above
            ch = logging.StreamHandler()
            ch.setLevel(logging.INFO)
            ch.setFormatter(logging.Formatter(LOG_FORMAT))
            self._logger.addHandler(ch)

            # rotating file handler — DEBUG and above
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            fh = RotatingFileHandler(
                LOG_DIR / f"{name}.log",
                maxBytes=MAX_LOG_BYTES,
                backupCount=LOG_BACKUP_COUNT,
            )
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(logging.Formatter(LOG_FORMAT))
            self._logger.addHandler(fh)

    def _log_move(
        self,
        level: int,
        move_uci: str,
        fen: str,
        legal: bool,
        msg: str = "",
    ) -> None:
        rules_str = "+".join(self._rule_names) if self._rule_names else "none"
        self._logger.log(
            level,
            "move=%s | fen=%s | rules=%s | legal=%s | %s",
            move_uci,
            fen,
            rules_str,
            legal,
            msg,
        )

    def _log_info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._logger.info(msg, *args, **kwargs)

    def _log_debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._logger.debug(msg, *args, **kwargs)

    def _log_warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._logger.warning(msg, *args, **kwargs)


# ── StateTrackingMixin ───────────────────────────────────────────────────────
class StateTrackingMixin:
    """
    Maintains an append-only ``_event_log: list[MoveEvent]`` that records
    every board interaction.  The log is consumed by ``MetricsCalculator``
    for post-experiment scoring.

    Call ``_init_state_tracking(rule_names)`` once during ``__init__``.
    """

    _event_log: list[MoveEvent]
    _rule_names_tracking: list[str]
    _category_tracking: str

    def _init_state_tracking(
        self,
        rule_names: list[str] | None = None,
        category: str = "composed",
    ) -> None:
        self._event_log = []
        self._rule_names_tracking = rule_names or []
        self._category_tracking = category

    def _record_event(
        self,
        fen_before: str,
        fen_after: str,
        move_uci: str,
        is_legal_perturbed: bool,
        is_legal_standard: bool,
        elapsed_ms: float = 0.0,
        **extra: Any,
    ) -> MoveEvent:
        """Create and store a MoveEvent, return it for further use."""
        evt = MoveEvent(
            fen_before=fen_before,
            fen_after=fen_after,
            move_uci=move_uci,
            rule_names=list(self._rule_names_tracking),
            category=self._category_tracking,
            is_legal_perturbed=is_legal_perturbed,
            is_legal_standard=is_legal_standard,
            is_inhibition_failure=(is_legal_standard and not is_legal_perturbed),
            elapsed_ms=elapsed_ms,
            extra=dict(extra),
        )
        self._event_log.append(evt)
        return evt

    def get_event_log(self) -> list[MoveEvent]:
        """Return a copy of the full event log."""
        return list(self._event_log)

    def clear_event_log(self) -> None:
        self._event_log.clear()

    @property
    def event_count(self) -> int:
        return len(self._event_log)