# hf_loader.py
# Loads real chess games from Lichess via Hugging Face,
# filters by Elo and move number, picks middlegame positions,
# removes duplicates, and saves exactly 500 unique positions to JSONL.

import json
import random
import chess
import chess.pgn
import io
import os
from datasets import load_dataset
from tqdm import tqdm

# ── CONFIG ─────────────────────────────────────────────────────────────
TARGET_POSITIONS = 500
MIN_ELO = 1800
MAX_ELO = 2400
MIN_MOVE = 15
MAX_MOVE = 35
GAMES_TO_SCAN = 100_000
OUTPUT_PATH = "data/positions/positions.jsonl"
# ────────────────────────────────────────────────────────────────────────


def load_hf_games(limit: int):
    """Load games from Hugging Face dataset, streaming to avoid downloading 30GB."""
    print(f"Loading first {limit:,} games...")
    ds = load_dataset("Lichess/standard-chess-games", streaming=True, split="train")
    sample = next(iter(ds))
    print("Available columns:", list(sample.keys()))
    return ds.take(limit)


def valid_elo(game: dict) -> bool:
    """Check if both players are within target Elo range."""
    try:
        w, b = int(game.get("WhiteElo", 0)), int(game.get("BlackElo", 0))
    except (ValueError, TypeError):
        return False
    return MIN_ELO <= w <= MAX_ELO and MIN_ELO <= b <= MAX_ELO


def pick_fen(game: dict) -> dict | None:
    """Replay a game and randomly pick one FEN from moves 15-35."""
    pgn_text = game.get("movetext", "")
    if not pgn_text:
        return None

    try:
        g = chess.pgn.read_game(io.StringIO(pgn_text))
        if g is None:
            return None
    except:
        return None

    board = g.board()
    middlegame = []

    for move in g.mainline_moves():
        board.push(move)
        if MIN_MOVE <= board.fullmove_number <= MAX_MOVE:
            middlegame.append((board.fullmove_number, board.fen()))
        if board.fullmove_number > MAX_MOVE:
            break

    if not middlegame:
        return None

    move_no, fen = random.choice(middlegame)
    site_url = game.get("Site", "")
    game_id = site_url.split("/")[-1] if "/" in site_url else "unknown"

    return {
        "fen": fen,
        "source_game_id": game_id,
        "move_number": move_no,
        "white_elo": int(game.get("WhiteElo", 0)),
        "black_elo": int(game.get("BlackElo", 0)),
    }


def save_positions(positions: list[dict], path: str):
    """Save all positions to a JSONL file, one FEN per line."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for pos in positions:
            f.write(json.dumps(pos) + "\n")
    print(f"Saved {len(positions)} positions to {os.path.abspath(path)}")


def run():
    dataset = load_hf_games(GAMES_TO_SCAN)
    positions = []
    seen = set()
    stats = {"scanned": 0, "invalid_elo": 0, "too_short": 0, "duplicate": 0, "valid": 0}

    print(f"Target: {TARGET_POSITIONS} positions from moves {MIN_MOVE}-{MAX_MOVE}")

    for game in tqdm(dataset, total=GAMES_TO_SCAN):
        stats["scanned"] += 1
        if len(positions) >= TARGET_POSITIONS:
            break
        if not valid_elo(game):
            stats["invalid_elo"] += 1
            continue

        fen_data = pick_fen(game)
        if fen_data is None:
            stats["too_short"] += 1
            continue

        canonical = " ".join(fen_data["fen"].split()[:4])
        if canonical in seen:
            stats["duplicate"] += 1
            continue

        seen.add(canonical)
        positions.append(fen_data)
        stats["valid"] += 1

    print("\n--- Pipeline Stats ---")
    for k, v in stats.items():
        print(f"{k.replace('_', ' ').title()}: {v}")

    if positions:
        save_positions(positions, OUTPUT_PATH)
    else:
        print("No positions collected — check your filters.")


if __name__ == "__main__":
    run()