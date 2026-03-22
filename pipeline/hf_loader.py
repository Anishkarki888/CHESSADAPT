# hf_loader.py
# Part of the ChessAdapt benchmark pipeline
# This script loads real chess games from the Lichess dataset on Hugging Face,
# filters them by player rating and move number, extracts board positions as FEN strings,
# removes duplicates, and saves exactly 500 unique positions to a JSONL file.
# That JSONL file is the foundation of the entire ChessAdapt benchmark.

import json
import random
import chess
import chess.pgn
import io
import os
from datasets import load_dataset
from tqdm import tqdm

# ── CONFIGURATION ────────────────────────────────────────────────────────────
# These values control what kind of positions we collect.
# Adjust them here if needed — no need to touch the functions below.
TARGET_POSITIONS = 500       # how many unique board positions we want in total
MIN_ELO          = 1800      # only include games where both players are rated 1800+
MAX_ELO          = 2400      # and no higher than 2400 — keeps play competent but human
MIN_MOVE         = 15        # only extract positions from move 15 onwards (past the opening)
MAX_MOVE         = 35        # and no later than move 35 (before the endgame)
GAMES_TO_SCAN    = 100_000   # maximum number of games to read before stopping
OUTPUT_PATH      = "data/positions/positions.jsonl"  # where the final file is saved
# ─────────────────────────────────────────────────────────────────────────────


def load_hf_games(games_to_scan: int):
    """
    Connects to the official Lichess dataset on Hugging Face and streams games
    one by one without downloading the full file (which is over 30GB).
    Streaming means we only read what we need and stop early.
    We also print the available column names on first run so we know the data structure.
    """
    print(f"Loading first {games_to_scan:,} games...")

    ds = load_dataset(
        "Lichess/standard-chess-games",
        streaming=True,   # stream row by row — never downloads the full file
        split="train",
    )

    # print column names once so we can verify the data looks right
    sample = next(iter(ds))
    print("Available columns:", list(sample.keys()))

    return ds.take(games_to_scan)


def is_valid_elo(game_row: dict) -> bool:
    """
    Checks whether both players in a game are within our target rating range.
    Games outside 1800-2400 Elo are skipped — too weak means poor play,
    too strong means positions are too unusual for a general benchmark.
    Returns True if the game passes the Elo check, False otherwise.
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
    Takes a single game record, replays its moves on a chess board,
    and picks a random position from anywhere between move 15 and move 35.
    This middlegame range is the most strategically complex part of a chess game —
    exactly the kind of position we want models to reason about under new rules.
    Returns a dict with the FEN string and metadata, or None if the game is too short.
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
        # some games have malformed PGN — skip them silently
        return None

    # replay the game move by move and collect board states in our target range
    board = game.board()
    valid_boards = []

    for move in game.mainline_moves():
        board.push(move)
        full_move = board.fullmove_number

        # only keep positions that fall in the middlegame window
        if MIN_MOVE <= full_move <= MAX_MOVE:
            valid_boards.append((full_move, board.fen()))

        # stop replaying once we are past move 35 — no point going further
        if full_move > MAX_MOVE:
            break

    # if the game ended before move 15, there are no valid positions — skip it
    if not valid_boards:
        return None

    # randomly pick one position from the valid range so we get variety
    move_number, fen = random.choice(valid_boards)

    # extract the Lichess game ID from the Site URL for traceability
    site_url = game_row.get("Site", "")
    game_id = site_url.split("/")[-1] if "/" in site_url else "unknown"

    return {
        "fen": fen,                                      # the board position in FEN format
        "source_game_id": game_id,                       # original Lichess game ID
        "move_number": move_number,                      # which move this position came from
        "white_elo": int(game_row.get("WhiteElo", 0)),   # white player rating
        "black_elo": int(game_row.get("BlackElo", 0))    # black player rating
    }


def save_jsonl(positions: list[dict], output_path: str):
    """
    Saves the collected positions to a JSONL file — one JSON object per line.
    JSONL format is used because it is easy to read line by line in other scripts
    without loading the entire file into memory at once.
    """
    abs_path = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)

    with open(abs_path, "w", encoding="utf-8") as f:
        for pos in positions:
            f.write(json.dumps(pos) + "\n")

    print(f"Successfully saved {len(positions)} positions to: {abs_path}")


def run():
    """
    Main entry point — runs the full pipeline from loading to saving.
    Tracks stats at each stage so we can see exactly why games were skipped.
    Stops as soon as we have 500 unique positions.
    """
    # Step 1 — load games from Hugging Face via streaming
    dataset = load_hf_games(GAMES_TO_SCAN)

    positions = []
    seen_fens = set()

    # track why games are being skipped — useful for debugging
    stats = {
        "scanned": 0,
        "invalid_elo": 0,
        "too_short": 0,
        "duplicate": 0,
        "valid": 0
    }

    print(f"Target: {TARGET_POSITIONS} positions from moves {MIN_MOVE}-{MAX_MOVE}")

    # Step 2 — loop through games, apply filters, extract FEN positions
    for game_row in tqdm(iter(dataset), total=GAMES_TO_SCAN, desc="Processing"):
        stats["scanned"] += 1

        # stop early once we have enough positions
        if len(positions) >= TARGET_POSITIONS:
            break

        # skip games where player ratings are out of range
        if not is_valid_elo(game_row):
            stats["invalid_elo"] += 1
            continue

        # skip games that ended too early to have a middlegame position
        result = extract_fen_from_game(game_row)
        if result is None:
            stats["too_short"] += 1
            continue

        # use only the first 4 parts of FEN for deduplication
        # (ignores move counters which change every move but represent same position)
        fen_parts = result["fen"].split(" ")
        canonical_fen = " ".join(fen_parts[:4])

        # skip positions we have already seen
        if canonical_fen in seen_fens:
            stats["duplicate"] += 1
            continue

        seen_fens.add(canonical_fen)
        positions.append(result)
        stats["valid"] += 1

    # Step 3 — print a summary of what happened
    print("\n--- Pipeline Stats ---")
    for key, val in stats.items():
        print(f"{key.replace('_', ' ').title()}: {val}")

    # Step 4 — save the final positions to JSONL
    if positions:
        save_jsonl(positions, OUTPUT_PATH)
        # confirm the file was actually written to disk
        if os.path.exists(OUTPUT_PATH):
            size = os.path.getsize(OUTPUT_PATH)
            print(f"File verification: {OUTPUT_PATH} exists, size {size} bytes.")
    else:
        print("WARNING: No positions collected! Check Elo range and move range.")


# run this file directly with:
# python pipeline/hf_loader.py
if __name__ == "__main__":
    run()