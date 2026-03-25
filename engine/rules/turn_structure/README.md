# Turn Structure Perturbations

Turn structure perturbations alter the sequence or number of moves each player can make during their turn. These are typically implemented by overriding the `push`, `pop`, or `generate_legal_moves` methods in `PerturbedBoard`.

## Rules Summary

| Rule Name | Class Name | Difficulty | Description |
| :--- | :--- | :--- | :--- |
| two_moves_per_turn | TwoMovesPerTurnBoard | hard | Each player makes two consecutive moves before the turn passes to the opponent. |
| no_repeat_piece | NoRepeatPieceBoard | medium | A player cannot move the same piece to the same square that was occupied by the opponent's last move. |

## Per-Rule Details

### Two Moves Per Turn (`two_moves_per_turn`)

**Class**: `TwoMovesPerTurnBoard`

The `two_moves_per_turn` rule allows each player to make two moves in succession. After the first move, the turn does not flip to the opponent; instead, the same player moves again.

- **Hook Points**: `push`, `pop`
- **Logic**: Overrides `push` and `pop` to manage the turn state, ensuring that the same player moves twice before the turn is passed.

**Example Usage**:
```python
from engine.registry import get_board
board = get_board("two_moves_per_turn", fen)
# 1. e2e4 1. d2d4 (White moves twice)
# 2. e7e5 2. d7d5 (Black moves twice)
```

### No Repeat Piece (`no_repeat_piece`)

**Class**: `NoRepeatPieceBoard`

In the `no_repeat_piece` rule, a player is forbidden from moving a piece from the square that the opponent just moved to. This prevents immediate "re-captures" or "returning" to the same square in some contexts.

- **Hook Points**: `push`, `pop`, `generate_legal_moves`
- **Logic**: Tracks the target square of the last move in a stack and filters legal moves that start from that square.

**Example Usage**:
```python
# If White moves a bishop to d5, Black cannot move any piece that is currently on d5 (if any were there after a capture).
```
