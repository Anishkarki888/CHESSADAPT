# hf_loader.py
# Anish's job — load chess games from Hugging Face Lichess dataset
# filter them by Elo and move number, extract 500 FEN positions
# and save as positions.jsonl

import json
import random
import chess
import chess.pgn
import io
import os
from datasets import load_dataset
from tqdm import tqdm

# ── CONFIG ──────────────────────────────────────────────────────────────────
# Change these if needed
TARGET_POSITIONS = 500       # how many unique FEN positions we want
MIN_ELO          = 1800      # minimum player rating
MAX_ELO          = 2400      # maximum player rating
MIN_MOVE         = 15        # earliest move to extract FEN from
MAX_MOVE         = 35        # latest move to extract FEN from
GAMES_TO_SCAN    = 100_000   # how many games to scan before giving up
OUTPUT_PATH      = "data/positions/positions.jsonl"
# ────────────────────────────────────────────────────────────────────────────


def load_hf_games(games_to_scan: int):
    """
    Streams Lichess dataset — no year filter for now,
    just takes first N games safely.
    """
    print(f"Loading first {games_to_scan:,} games...")

    ds = load_dataset(
        "Lichess/standard-chess-games",
        streaming=True,
        split="train",
    )

    # first print what fields exist so we know column names
    sample = next(iter(ds))
    print("Available columns:", list(sample.keys()))

    return ds.take(games_to_scan)


def is_valid_elo(game_row: dict) -> bool:
    """
    Checks if both players have Elo ratings between MIN_ELO and MAX_ELO.
    Skips games where Elo is missing or out of range.
    """
    try:
        white_elo = int(game_row.get("WhiteElo", 0))
        black_elo = int(game_row.get("BlackElo", 0))
    except (ValueError, TypeError):
        # Elo field is missing or not a number — skip this game
        return False

    return MIN_ELO <= white_elo <= MAX_ELO and MIN_ELO <= black_elo <= MAX_ELO


def extract_fen_from_game(game_row: dict) -> dict | None:
    """
    Parses a single game's PGN moves and extracts a FEN string
    at a random fullmove between MIN_MOVE and MAX_MOVE.
    """
    pgn_moves = game_row.get("movetext", "")
    if not pgn_moves:
        return None

    pgn_io = io.StringIO(pgn_moves)

    try:
        game = chess.pgn.read_game(pgn_io)
        if game is None:
            return None
    except Exception as e:
        # print(f"Error parsing PGN: {e}")
        return None

    board = game.board()
    valid_boards = []

    # Iterate through moves and track fullmove_number
    for move in game.mainline_moves():
        board.push(move)
        full_move = board.fullmove_number
        
        # Only collect if it's within move 15-35 range
        if MIN_MOVE <= full_move <= MAX_MOVE:
            valid_boards.append((full_move, board.fen()))
        
        # Optimization: stop if we passed the max move
        if full_move > MAX_MOVE:
            break

    if not valid_boards:
        return None

    # Pick a random move from the valid range
    move_number, fen = random.choice(valid_boards)

    # Extract Lichess ID from Site URL (e.g., https://lichess.org/ABCDEFGH)
    site_url = game_row.get("Site", "")
    game_id = site_url.split("/")[-1] if "/" in site_url else "unknown"

    return {
        "fen": fen,
        "source_game_id": game_id,
        "move_number": move_number,
        "white_elo": int(game_row.get("WhiteElo", 0)),
        "black_elo": int(game_row.get("BlackElo", 0))
    }


def save_jsonl(positions: list[dict], output_path: str):
    """
    Saves the final list of positions as a JSONL file.
    """
    abs_path = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)

    with open(abs_path, "w", encoding="utf-8") as f:
        for pos in positions:
            f.write(json.dumps(pos) + "\n")

    print(f"Successfully saved {len(positions)} positions to: {abs_path}")


def run():
    """
    Main function with enhanced debugging.
    """
    dataset = load_hf_games(GAMES_TO_SCAN)

    positions = []
    seen_fens = set()
    
    stats = {
        "scanned": 0,
        "invalid_elo": 0,
        "too_short": 0,
        "duplicate": 0,
        "valid": 0
    }

    print(f"Target: {TARGET_POSITIONS} positions from moves {MIN_MOVE}-{MAX_MOVE}")
    
    for game_row in tqdm(iter(dataset), total=GAMES_TO_SCAN, desc="Processing"):
        stats["scanned"] += 1
        
        if len(positions) >= TARGET_POSITIONS:
            break

        if not is_valid_elo(game_row):
            stats["invalid_elo"] += 1
            continue

        result = extract_fen_from_game(game_row)
        if result is None:
            stats["too_short"] += 1
            continue

        # Canonical FEN for dedup (stripping move counts)
        fen_parts = result["fen"].split(" ")
        canonical_fen = " ".join(fen_parts[:4])

        if canonical_fen in seen_fens:
            stats["duplicate"] += 1
            continue

        seen_fens.add(canonical_fen)
        positions.append(result)
        stats["valid"] += 1

    print("\n--- Pipeline Stats ---")
    for key, val in stats.items():
        print(f"{key.replace('_', ' ').title()}: {val}")
    
    if positions:
        save_jsonl(positions, OUTPUT_PATH)
        # Verify file immediately
        if os.path.exists(OUTPUT_PATH):
            size = os.path.getsize(OUTPUT_PATH)
            print(f"File verification: {OUTPUT_PATH} exists, size {size} bytes.")
    else:
        print("WARNING: No positions collected! Check Elo range and move range.")


# run this file directly with: python hf_loader.py
if __name__ == "__main__":
    run()