# hf_loader.py
# Loads chess games from Hugging Face, filters by Elo/move range,
# selects middlegame positions, deduplicates, and saves exactly 500 FENs.
#
# Fixes applied vs original:
#   - pick_fen() now wraps raw movetext in a dummy PGN header so
#     chess.pgn.read_game() can parse it (was silently returning None)
#   - Move number uses board.ply() arithmetic, not fullmove_number
#     (fullmove_number only increments after Black's move — was off by ~0.5)
#   - Game-over positions (checkmate, stalemate) are filtered out
#   - Schema probe fails fast if expected columns are missing
#   - GAMES_TO_SCAN raised to 200k as a buffer against low yield
#   - FEN sampling stratified across early/mid/late move buckets
#   - Early-exit warning added if dataset exhausted before target

import io
import json
import os
import random
import warnings
from typing import Optional

import chess
import chess.pgn
from datasets import load_dataset
from tqdm import tqdm

# ── CONFIG ──────────────────────────────────────────────────────────────
TARGET_POSITIONS = 500
MIN_ELO          = 1800
MAX_ELO          = 2400
MIN_MOVE         = 15
MAX_MOVE         = 35
GAMES_TO_SCAN    = 200_000          # raised: ~5-10% yield expected after filters
OUTPUT_PATH      = "/home/anish/chess_benchmark/data/positions/positions_2.jsonl"

# Stratified sampling buckets (move ranges within MIN_MOVE..MAX_MOVE).
# Positions are drawn equally from each bucket to avoid late-move bias.
MOVE_BUCKETS = [
    (15, 20),
    (21, 27),
    (28, 35),
]
# ────────────────────────────────────────────────────────────────────────


def load_hf_games(limit: int):
    """Stream games from the Lichess HF dataset, take only `limit` rows."""
    print(f"Connecting to HuggingFace dataset (streaming, limit={limit:,})...")
    ds = load_dataset(
        "Lichess/standard-chess-games",
        split="train",
        streaming=True,
    )
    return ds.take(limit)


def probe_schema(sample: dict) -> tuple[str, str]:
    """
    Inspect one record and return (move_col, elo_col) column name prefixes.
    Raises RuntimeError immediately if required columns are absent — fail fast
    rather than running 200k games and producing nothing.
    """
    move_candidates = ["movetext", "Moves", "moves", "pgn"]
    elo_candidates  = ["WhiteElo", "white_elo", "white_rating"]

    move_col = next((c for c in move_candidates if c in sample), None)
    elo_col  = next((c for c in elo_candidates  if c in sample), None)

    if move_col is None:
        raise RuntimeError(
            f"No move column found. Available columns: {list(sample.keys())}\n"
            f"Expected one of: {move_candidates}"
        )
    if elo_col is None:
        raise RuntimeError(
            f"No Elo column found. Available columns: {list(sample.keys())}\n"
            f"Expected one of: {elo_candidates}"
        )

    print(f"Schema OK — move column: '{move_col}', Elo column: '{elo_col}'")
    return move_col, elo_col


def get_elos(game: dict) -> tuple[int, int]:
    """Return (white_elo, black_elo), raising ValueError on bad data."""
    for w_key in ("WhiteElo", "white_elo", "white_rating"):
        if w_key in game:
            w = game[w_key]
            break
    else:
        raise ValueError("no white elo")

    for b_key in ("BlackElo", "black_elo", "black_rating"):
        if b_key in game:
            b = game[b_key]
            break
    else:
        raise ValueError("no black elo")

    return int(w), int(b)


def valid_elo(game: dict) -> bool:
    """Return True only if both players are strictly within [MIN_ELO, MAX_ELO]."""
    try:
        w, b = get_elos(game)
    except (ValueError, TypeError, KeyError):
        return False
    return MIN_ELO <= w <= MAX_ELO and MIN_ELO <= b <= MAX_ELO


def parse_positions(movetext: str) -> dict[tuple[int, int], list[str]]:
    """
    Replay a game from raw SAN movetext and collect FENs bucketed by move range.

    Returns a dict keyed by (bucket_min, bucket_max) → list of FEN strings.
    Skips any position where the game is already over (checkmate / stalemate).

    The raw movetext from HF has no PGN headers, so we prepend a minimal
    header to make chess.pgn.read_game() happy.  We then use board.ply()
    to compute the full-move number:

        full_move = (ply + 1) // 2      [1-indexed, same as OTB notation]

    This is correct for both sides:
        ply 1  → White's move 1  → full_move 1
        ply 2  → Black's move 1  → full_move 1
        ply 29 → White's move 15 → full_move 15   ✓
        ply 30 → Black's move 15 → full_move 15   ✓
    """
    # Wrap raw SAN in a minimal PGN so the parser accepts it.
    pgn_text = (
        '[Event "?"]\n[Site "?"]\n[Date "????.??.??"]\n'
        '[Round "?"]\n[White "?"]\n[Black "?"]\n[Result "*"]\n\n'
        + movetext.strip()
    )

    try:
        game_node = chess.pgn.read_game(io.StringIO(pgn_text))
    except Exception:
        return {}

    if game_node is None:
        return {}

    board = game_node.board()
    buckets: dict[tuple[int, int], list[str]] = {b: [] for b in MOVE_BUCKETS}

    try:
        for move in game_node.mainline_moves():
            board.push(move)

            # ply() is the number of half-moves played so far (1-indexed after push).
            full_move = (board.ply() + 1) // 2

            if full_move > MAX_MOVE:
                break
            if full_move < MIN_MOVE:
                continue
            if board.is_game_over():
                # Checkmate / stalemate positions have no legal moves — skip.
                continue

            for lo, hi in MOVE_BUCKETS:
                if lo <= full_move <= hi:
                    buckets[(lo, hi)].append(board.fen())
                    break
    except Exception:
        # Illegal move in movetext — discard the whole game.
        return {}

    return buckets


def pick_fen_stratified(
    game: dict,
    move_col: str,
    seen: set,
) -> Optional[dict]:
    """
    Pick one FEN from the game, drawn from a randomly chosen non-empty bucket.
    Enforces deduplication against `seen` (first 4 FEN fields, ignoring clocks).
    Returns a TaskItem-ready dict or None.
    """
    movetext = game.get(move_col, "")
    if not movetext:
        return None

    buckets = parse_positions(movetext)

    # Shuffle bucket order so we don't always prefer early moves.
    bucket_keys = list(MOVE_BUCKETS)
    random.shuffle(bucket_keys)

    for key in bucket_keys:
        fens = buckets.get(key, [])
        if not fens:
            continue

        random.shuffle(fens)
        for fen in fens:
            # Canonical key: position + side + castling + en-passant (ignore clocks).
            canonical = " ".join(fen.split()[:4])
            if canonical in seen:
                continue

            # Parse out the full-move number from the FEN string itself.
            fen_parts  = fen.split()
            move_no    = int(fen_parts[5]) if len(fen_parts) >= 6 else -1

            try:
                w, b = get_elos(game)
            except (ValueError, TypeError):
                w = b = 0

            site_url = game.get("Site") or game.get("site") or ""
            game_id  = site_url.split("/")[-1] if "/" in site_url else "unknown"

            return {
                "fen":           fen,
                "source_game_id": game_id,
                "move_number":   move_no,
                "white_elo":     w,
                "black_elo":     b,
            }

    return None


def save_positions(positions: list[dict], path: str) -> None:
    """Write positions to JSONL, one JSON object per line."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for pos in positions:
            f.write(json.dumps(pos) + "\n")
    print(f"\nSaved {len(positions)} positions → {os.path.abspath(path)}")


def run() -> None:
    dataset = load_hf_games(GAMES_TO_SCAN)

    # Schema probe on the very first record — fail fast before processing anything.
    first_sample = next(iter(dataset))
    move_col, _ = probe_schema(first_sample)

    # Re-stream from the start (take() returns an iterable, not rewindable).
    dataset = load_hf_games(GAMES_TO_SCAN)

    positions: list[dict] = []
    seen: set[str]        = set()
    stats = {
        "scanned":     0,
        "invalid_elo": 0,
        "parse_fail":  0,
        "no_bucket":   0,
        "duplicate":   0,
        "valid":       0,
    }

    print(
        f"\nTarget: {TARGET_POSITIONS} positions | "
        f"Elo {MIN_ELO}–{MAX_ELO} | "
        f"Moves {MIN_MOVE}–{MAX_MOVE}\n"
    )

    for game in tqdm(dataset, total=GAMES_TO_SCAN, desc="Scanning games"):
        if len(positions) >= TARGET_POSITIONS:
            break

        stats["scanned"] += 1

        if not valid_elo(game):
            stats["invalid_elo"] += 1
            continue

        result = pick_fen_stratified(game, move_col, seen)

        if result is None:
            # Distinguish parse failure from no middlegame positions found.
            movetext = game.get(move_col, "")
            if not movetext:
                stats["parse_fail"] += 1
            else:
                buckets = parse_positions(movetext)
                if not any(buckets.values()):
                    stats["no_bucket"] += 1
                else:
                    stats["duplicate"] += 1
            continue

        canonical = " ".join(result["fen"].split()[:4])
        seen.add(canonical)
        positions.append(result)
        stats["valid"] += 1

    # ── Summary ────────────────────────────────────────────────────────
    print("\n── Pipeline stats ──────────────────────────────────────────")
    col_w = max(len(k) for k in stats) + 2
    for k, v in stats.items():
        label = k.replace("_", " ").title()
        print(f"  {label:<{col_w}} {v:>6,}")

    if len(positions) < TARGET_POSITIONS:
        warnings.warn(
            f"\nWARNING: Only collected {len(positions)}/{TARGET_POSITIONS} positions. "
            f"Consider increasing GAMES_TO_SCAN (currently {GAMES_TO_SCAN:,}) "
            f"or relaxing Elo/move filters.",
            stacklevel=2,
        )

    if positions:
        save_positions(positions, OUTPUT_PATH)
    else:
        print("\nNo positions collected — check column names and filters above.")


if __name__ == "__main__":
    run()