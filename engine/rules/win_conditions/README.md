# Win Condition Perturbations

Win condition perturbations change the criteria for winning the game, overriding standard checkmate rules. These are typically implemented by overriding `is_game_over`, `is_checkmate`, and `outcome` methods in `PerturbedBoard`.

## Rules Summary

| Rule Name | Class Name | Difficulty | Description |
| :--- | :--- | :--- | :--- |
| capture_all_pawns | CaptureAllPawnsBoard | easy | Win by capturing all of the opponent's pawns. |
| centre_race | CentreRaceBoard | medium | Win by moving any piece to one of the central squares (e4, e5). |

## Per-Rule Details

### Capture All Pawns (`capture_all_pawns`)

**Class**: `CaptureAllPawnsBoard`

The `capture_all_pawns` rule changes the objective of the game. Instead of checkmating the king, a player wins by capturing all of the opponent's pawns.

- **Hook Points**: `is_game_over`, `is_checkmate`, `outcome`
- **Logic**: The game ends when one player has no pawns left. Standard checkmate is disabled.

**Example Usage**:
```python
from engine.registry import get_board
board = get_board("capture_all_pawns", fen)
# Game ends when all pawns of one side are captured.
```

### Centre Race (`centre_race`)

**Class**: `CentreRaceBoard`

In the `centre_race` rule, the first player to move any of their pieces to one of the four central squares (e4, e5, d4, d5) wins the game.

- **Hook Points**: `push`, `pop`, `is_game_over`, `outcome`
- **Logic**: Tracks if a move lands on a central square and sets the winner accordingly.

**Example Usage**:
```python
# A move like 1. e2e4 would immediately end the game if it is the first move to reach the centre.
```
