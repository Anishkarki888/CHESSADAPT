"""
Extract UCI chess moves from raw LLM output.

Handles common model response patterns:
  • Plain UCI moves: "e2e4"
  • Numbered lists:  "1. e2e4\n2. g1f3"
  • Code blocks:     "```e2e4```"
  • Prose with moves: "My move is e2e4 because ..."
  • Promotion moves:  "e7e8q"
"""

from __future__ import annotations

import re
import logging

logger = logging.getLogger("chessadapt.response_parser")

# Matches standard UCI moves: source_square + target_square + optional promotion
_UCI_PATTERN = re.compile(r"\b([a-h][1-8][a-h][1-8][qrbnQRBN]?)\b", re.IGNORECASE)


class ResponseParser:
    """
    Extract UCI move strings from raw LLM output.

    Usage::

        parser = ResponseParser()
        moves = parser.extract("My best move is e2e4.")
        # moves = ["e2e4"]
    """

    @staticmethod
    def extract(raw_response: str, max_moves: int = 3) -> list[str]:
        """
        Extract up to ``max_moves`` UCI move strings from raw text.

        Parameters
        ----------
        raw_response : str
            Raw text output from the LLM.
        max_moves : int
            Maximum number of moves to extract.

        Returns
        -------
        list[str]
            Extracted UCI moves in order of appearance, lowercased.
            Empty list if no valid moves found.
        """
        if not raw_response or not raw_response.strip():
            logger.warning("Empty response received")
            return []

        # Normalize: strip markdown code fences
        cleaned = raw_response.replace("```", " ")

        # Find all UCI-pattern matches
        matches = _UCI_PATTERN.findall(cleaned)

        if not matches:
            logger.warning(
                "No UCI moves found in response: %s",
                raw_response[:200],
            )
            return []

        # Normalize to lowercase, deduplicate while preserving order
        seen: set[str] = set()
        moves: list[str] = []
        for m in matches:
            m_lower = m.lower()
            if m_lower not in seen:
                seen.add(m_lower)
                moves.append(m_lower)
            if len(moves) >= max_moves:
                break

        logger.debug("Extracted %d moves: %s", len(moves), moves)
        return moves

    @staticmethod
    def extract_single(raw_response: str) -> str | None:
        """
        Extract exactly one UCI move.  Returns ``None`` if no move found.
        """
        moves = ResponseParser.extract(raw_response, max_moves=1)
        return moves[0] if moves else None
