# ChessAdapt: Rule-Perturbed Chess Benchmark

## Project Structure

- `engine/`: The core perturbation engine built on `python-chess`.
- `pipeline/`: Scripts for data collection and benchmark generation.
- `data/`: Extracted board positions and benchmark files.

## Installation

The project uses `uv` for fast dependency management.

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Linux/macOS

# Install dependencies
uv pip install -r requirements.txt
```

## Usage

### 1. Generating the Benchmark Data

To load real chess games from Hugging Face and extract unique middlegame positions:

```bash
python pipeline/hf_loader.py
```

This script will:
- Stream games from the Lichess dataset.
- Filter for quality (1800-2400 Elo).
- Extract 500 unique middlegame positions.
- Save the results to `data/positions/positions.jsonl`.

### 2. Using the Perturbation Engine

The engine allows you to apply various "perturbation" rules to standard chess positions.

```python
from engine.registry import get_board

# Initialize a board with a specific rule
board = get_board("bishop_as_rook", fen)

# Check legal moves
print(board.legal_moves)
```

Refer to [engine/README.md](engine/README.md) for detailed documentation on all available rules and categories.

### 3. Running Tests

To verify the implementation of various rules:

```bash
pytest engine/tests/test_movement_rules.py
```

## Documentation

- [Engine Overview](engine/README.md)
- [Movement Rules](engine/rules/movement/README.md)
- [Win Condition Rules](engine/rules/win_conditions/README.md)
- [Turn Structure Rules](engine/rules/turn_structure/README.md)