# lichess_loader.py
# Downloads a Lichess monthly PGN dump (.pgn.zst) directly from lichess.org,
# streams + decompresses on the fly (never writes the raw .zst to disk),
# filters by Elo and move range, picks stratified middlegame positions,
# deduplicates by FEN, and saves exactly TARGET_POSITIONS records to JSONL.
#
# Dependencies:
#   pip install zstandard chess tqdm requests
#
# Usage:
#   python lichess_loader.py                        # uses MONTH in config
#   python lichess_loader.py --month 2025-04        # override month
#   python lichess_loader.py --month 2025-04 --out data/positions/april.jsonl

import argparse
import io
import json
import os
import random
import time
import warnings
from pathlib import Path
from typing import Iterator, Optional

import chess
import chess.pgn
import requests
import zstandard as zstd
from tqdm import tqdm

# ── CONFIG ──────────────────────────────────────────────────────────────
MONTH            = "2025-05"          # yyyy-mm  →  the 30.7 GB May 2025 dump
TARGET_POSITIONS = 500
MIN_ELO          = 1800
MAX_ELO          = 2400
MIN_MOVE         = 15
MAX_MOVE         = 35

# Where output goes — relative to this file's directory
OUTPUT_PATH      = "data/positions/positions.jsonl"

# Lichess open-database base URL (no trailing slash)
LICHESS_BASE_URL = "https://database.lichess.org"

# Chunk size for the HTTP streaming download (4 MB)
DOWNLOAD_CHUNK   = 4 * 1024 * 1024

# Stratified move buckets — positions drawn equally from each
MOVE_BUCKETS = [
    (15, 20),
    (21, 27),
    (28, 35),
]

# How many games to scan before giving up (safety limit)
MAX_GAMES_TO_SCAN = 500_000
# ────────────────────────────────────────────────────────────────────────


# ── URL BUILDER ─────────────────────────────────────────────────────────

def lichess_pgn_url(month: str) -> str:
    """
    Build the direct download URL for a Lichess monthly PGN dump.

    Format: https://database.lichess.org/standard/lichess_db_standard_rated_{yyyy-mm}.pgn.zst
    Example for May 2025:
        https://database.lichess.org/standard/lichess_db_standard_rated_2025-05.pgn.zst
    """
    filename = f"lichess_db_standard_rated_{month}.pgn.zst"
    return f"{LICHESS_BASE_URL}/standard/{filename}"


# ── STREAMING DOWNLOAD + DECOMPRESSION ──────────────────────────────────

def stream_pgn_lines(url: str) -> Iterator[str]:
    """
    HTTP-stream the .pgn.zst file, decompress with zstandard on the fly,
    and yield decoded text lines one at a time.

    The raw .zst is never written to disk — bytes flow:
        Lichess server → HTTP chunks → zstd decompressor → text lines

    Raises:
        requests.HTTPError  if the server returns a non-200 status
        RuntimeError        if zstd decompression fails
    """
    print(f"Connecting to: {url}")
    response = requests.get(url, stream=True, timeout=30)
    response.raise_for_status()

    total_bytes = int(response.headers.get("Content-Length", 0))
    print(
        f"File size: {total_bytes / 1e9:.2f} GB  "
        f"(streaming — not fully downloaded)"
    )

    dctx        = zstd.ZstdDecompressor()
    leftover    = b""                     # incomplete line from previous chunk

    with tqdm(
        total=total_bytes,
        unit="B",
        unit_scale=True,
        unit_divisor=1024,
        desc="Downloading",
        leave=False,
    ) as pbar:
        with dctx.stream_reader(
            _ChunkedSource(response, DOWNLOAD_CHUNK, pbar),
            read_size=DOWNLOAD_CHUNK,
        ) as reader:
            while True:
                chunk = reader.read(DOWNLOAD_CHUNK)
                if not chunk:
                    break

                # Combine leftover bytes from the previous chunk
                raw = leftover + chunk
                lines = raw.split(b"\n")

                # The last element may be an incomplete line — save for next round
                leftover = lines[-1]

                for line in lines[:-1]:
                    yield line.decode("utf-8", errors="replace")

    # Flush any remaining bytes
    if leftover:
        yield leftover.decode("utf-8", errors="replace")


class _ChunkedSource:
    """
    Wraps a requests streaming response as a readable source for
    zstd.ZstdDecompressor.stream_reader(), updating a tqdm progress bar.
    """

    def __init__(self, response: requests.Response, chunk_size: int, pbar: tqdm):
        self._iter       = response.iter_content(chunk_size=chunk_size)
        self._pbar       = pbar
        self._buf        = b""
        self._exhausted  = False

    def read(self, size: int = -1) -> bytes:
        while not self._exhausted and len(self._buf) < (size if size > 0 else 1):
            try:
                chunk = next(self._iter)
                self._buf += chunk
                self._pbar.update(len(chunk))
            except StopIteration:
                self._exhausted = True
                break

        if size < 0:
            data, self._buf = self._buf, b""
        else:
            data, self._buf = self._buf[:size], self._buf[size:]

        return data


# ── PGN BLOCK PARSER ────────────────────────────────────────────────────

def iter_pgn_games(lines: Iterator[str]) -> Iterator[dict]:
    """
    Group raw text lines into PGN game blocks and yield each as a dict:
        {
            "headers": {"White": "...", "BlackElo": "...", ...},
            "movetext": "1. e4 e5 2. Nf3 ...",
            "site": "https://lichess.org/abc123",
        }

    Lichess PGN format:
        [Tag "Value"]          ← header lines (one per line)
        (blank line)
        1. e4 e5 2. Nf3 ...    ← movetext (may span multiple lines)
        (blank line)           ← game separator
    """
    headers  : dict[str, str] = {}
    movetext : list[str]      = []
    in_moves : bool           = False

    for line in lines:
        line = line.rstrip()

        if line.startswith("[") and line.endswith("]"):
            # Header line — parse [Tag "Value"]
            if in_moves and movetext:
                # We hit a new header after movetext — emit the completed game
                yield {
                    "headers":  headers,
                    "movetext": " ".join(movetext).strip(),
                    "site":     headers.get("Site", ""),
                }
                headers  = {}
                movetext = []
                in_moves = False

            try:
                tag, _, value = line[1:-1].partition(" ")
                headers[tag] = value.strip('"')
            except ValueError:
                pass

        elif line == "":
            if in_moves and movetext:
                # Blank line after movetext — game complete
                yield {
                    "headers":  headers,
                    "movetext": " ".join(movetext).strip(),
                    "site":     headers.get("Site", ""),
                }
                headers  = {}
                movetext = []
                in_moves = False

        else:
            # Non-empty, non-header line → movetext
            in_moves = True
            movetext.append(line)

    # Flush last game if file doesn't end with a blank line
    if movetext:
        yield {
            "headers":  headers,
            "movetext": " ".join(movetext).strip(),
            "site":     headers.get("Site", ""),
        }


# ── ELO FILTER ──────────────────────────────────────────────────────────

def valid_elo(headers: dict) -> bool:
    """Return True only if both players are within [MIN_ELO, MAX_ELO]."""
    try:
        w = int(headers.get("WhiteElo", 0))
        b = int(headers.get("BlackElo", 0))
    except (ValueError, TypeError):
        return False
    return MIN_ELO <= w <= MAX_ELO and MIN_ELO <= b <= MAX_ELO


# ── POSITION EXTRACTOR ───────────────────────────────────────────────────

def parse_positions(movetext: str) -> dict[tuple[int, int], list[str]]:
    """
    Replay a game from raw SAN movetext and collect FENs bucketed by move range.
    Skips game-over positions (checkmate / stalemate — no legal moves to test).

    Move number formula:
        full_move = (board.ply() + 1) // 2
    This is correct for both sides, unlike board.fullmove_number which
    only increments after Black's reply.
    """
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

    board   = game_node.board()
    buckets : dict[tuple[int, int], list[str]] = {b: [] for b in MOVE_BUCKETS}

    try:
        for move in game_node.mainline_moves():
            board.push(move)
            full_move = (board.ply() + 1) // 2

            if full_move > MAX_MOVE:
                break
            if full_move < MIN_MOVE:
                continue
            if board.is_game_over():
                continue

            for lo, hi in MOVE_BUCKETS:
                if lo <= full_move <= hi:
                    buckets[(lo, hi)].append(board.fen())
                    break
    except Exception:
        return {}

    return buckets


def pick_fen_stratified(
    game: dict,
    seen: set[str],
) -> Optional[dict]:
    """
    Pick one deduplicated FEN from a random non-empty bucket.
    Returns a TaskItem-ready dict or None.
    """
    buckets = parse_positions(game["movetext"])

    bucket_keys = list(MOVE_BUCKETS)
    random.shuffle(bucket_keys)

    for key in bucket_keys:
        fens = buckets.get(key, [])
        if not fens:
            continue

        random.shuffle(fens)
        for fen in fens:
            canonical = " ".join(fen.split()[:4])
            if canonical in seen:
                continue

            fen_parts = fen.split()
            move_no   = int(fen_parts[5]) if len(fen_parts) >= 6 else -1
            headers   = game["headers"]
            site      = game["site"]
            game_id   = site.split("/")[-1] if "/" in site else "unknown"

            return {
                "fen":            fen,
                "source_game_id": game_id,
                "move_number":    move_no,
                "white_elo":      int(headers.get("WhiteElo", 0)),
                "black_elo":      int(headers.get("BlackElo", 0)),
            }

    return None


# ── OUTPUT ───────────────────────────────────────────────────────────────

def save_positions(positions: list[dict], path: str) -> None:
    """Write positions to JSONL — one JSON object per line."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for pos in positions:
            f.write(json.dumps(pos) + "\n")
    print(f"\nSaved {len(positions)} positions → {out.resolve()}")


# ── MAIN ─────────────────────────────────────────────────────────────────

def run(month: str = MONTH, output_path: str = OUTPUT_PATH) -> None:
    url = lichess_pgn_url(month)

    print(f"\nChessAdapt — Lichess position extractor")
    print(f"Month    : {month}")
    print(f"URL      : {url}")
    print(f"Target   : {TARGET_POSITIONS} positions")
    print(f"Elo range: {MIN_ELO}–{MAX_ELO}")
    print(f"Moves    : {MIN_MOVE}–{MAX_MOVE}")
    print(f"Output   : {Path(output_path).resolve()}\n")

    positions : list[dict]  = []
    seen      : set[str]    = set()
    stats = {
        "scanned":     0,
        "invalid_elo": 0,
        "parse_fail":  0,
        "no_bucket":   0,
        "duplicate":   0,
        "valid":       0,
    }

    start = time.time()

    try:
        raw_lines  = stream_pgn_lines(url)
        game_iter  = iter_pgn_games(raw_lines)

        with tqdm(desc="Positions found", total=TARGET_POSITIONS, unit="pos") as pos_bar:
            for game in game_iter:
                if stats["scanned"] >= MAX_GAMES_TO_SCAN:
                    warnings.warn(
                        f"Reached MAX_GAMES_TO_SCAN={MAX_GAMES_TO_SCAN:,} "
                        f"with only {len(positions)}/{TARGET_POSITIONS} positions.",
                        stacklevel=2,
                    )
                    break

                stats["scanned"] += 1

                if not valid_elo(game["headers"]):
                    stats["invalid_elo"] += 1
                    continue

                if not game["movetext"]:
                    stats["parse_fail"] += 1
                    continue

                result = pick_fen_stratified(game, seen)

                if result is None:
                    buckets = parse_positions(game["movetext"])
                    if not any(buckets.values()):
                        stats["no_bucket"] += 1
                    else:
                        stats["duplicate"] += 1
                    continue

                canonical = " ".join(result["fen"].split()[:4])
                seen.add(canonical)
                positions.append(result)
                stats["valid"] += 1
                pos_bar.update(1)

                if len(positions) >= TARGET_POSITIONS:
                    break

    except KeyboardInterrupt:
        print("\nInterrupted — saving what we have...")
    except requests.HTTPError as e:
        print(f"\nHTTP error: {e}")
        print("Check that the month/URL is correct: "
              "https://database.lichess.org/#standard_games")
        raise

    elapsed = time.time() - start

    # ── Stats summary ───────────────────────────────────────────────────
    print("\n── Pipeline stats ─────────────────────────────────────────")
    col_w = max(len(k) for k in stats) + 2
    for k, v in stats.items():
        print(f"  {k.replace('_', ' ').title():<{col_w}} {v:>8,}")
    print(f"  {'Elapsed':<{col_w}} {elapsed:>7.1f}s")

    if len(positions) < TARGET_POSITIONS:
        warnings.warn(
            f"\nWARNING: Only collected {len(positions)}/{TARGET_POSITIONS} positions. "
            f"Try an earlier month with more games, or raise MAX_GAMES_TO_SCAN.",
            stacklevel=2,
        )

    if positions:
        save_positions(positions, output_path)
    else:
        print("\nNo positions saved — check Elo filters and URL above.")


# ── CLI ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Download Lichess PGN dump and extract middlegame positions."
    )
    parser.add_argument(
        "--month",
        default=MONTH,
        help="Month to download in yyyy-mm format (default: %(default)s)",
    )
    parser.add_argument(
        "--out",
        default=OUTPUT_PATH,
        help="Output JSONL path (default: %(default)s)",
    )
    args = parser.parse_args()
    run(month=args.month, output_path=args.out)