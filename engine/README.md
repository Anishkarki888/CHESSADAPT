# Chess Perturbation Engine

The Chess Perturbation Engine is a modular Python library built on top of `python-chess`. It allows for the creation and validation of chess variants by modifying core rules such as piece movement, win conditions, and turn structure.

## Overview

The engine provides a framework to "perturb" standard chess rules. Each perturbation is implemented as a subclass of `PerturbedBoard`, which inherits from `chess.Board`. This design ensures compatibility with existing chess tools while allowing for deep customization of game logic.

## Class Hierarchy

- `chess.Board` (from `python-chess`)
  - `PerturbedBoard` (base class for all perturbations)
    - `MovementBoard` subclasses (e.g., `BishopAsRookBoard`)
    - `WinConditionBoard` subclasses (e.g., `CaptureAllPawnsBoard`)
    - `TurnStructureBoard` subclasses (e.g., `TwoMovesPerTurnBoard`)

## Rule Categories

| Category | Description | Examples |
| :--- | :--- | :--- |
| Movement | Modifies how specific pieces move or capture. | Bishop as Rook, Knight Two Squares |
| Win Condition | Changes the criteria for winning the game. | Capture All Pawns, Centre Race |
| Turn Structure | Alters the sequence or number of moves per turn. | Two Moves Per Turn, No Repeat Piece |

Detailed documentation for each category can be found here:
- [Movement Rules](rules/movement/README.md)
- [Win Condition Rules](rules/win_conditions/README.md)
- [Turn Structure Rules](rules/turn_structure/README.md)

## Public Interface

The engine exposes several high-level functions for interacting with perturbed boards.

### get_board(rule_name, fen)

Returns an instance of a `PerturbedBoard` subclass based on the provided rule name.

```python
from engine.registry import get_board

# Initialize a board with a specific rule and FEN
fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
board = get_board("bishop_as_rook", fen)
```

### validate_move(fen, rule_name, uci)

Validates if a move is legal under a specific perturbation rule and compares it with standard chess rules.

```python
from engine.validator import validate_move

result = validate_move(fen, "knight_two_squares", "g1f3")
# result = {
#     "legal": True,
#     "is_old_rule": False,
#     "uci_move": "g1f3"
# }
```

### get_legal_moves(fen, rule_name)

Returns a list of all legal moves in UCI format for a given board state and rule.

```python
from engine.legal_moves import get_legal_moves

moves = get_legal_moves(fen, "two_moves_per_turn")
# moves = ("e2e4", "d2d4", ...)
```

## Testing and Visual Validation

The engine includes a suite of tests to verify the correctness of each rule.

### Running Tests

To run the movement rule tests:
```bash
pytest engine/tests/test_movement_rules.py
```

### Visual Verification

A visualizer utility is available in `engine/utils/visualizer.py` to inspect board states and legal moves interactively.
