# Movement Perturbations

Movement perturbations modify how specific pieces move or capture. These rules are implemented by overriding the `generate_pseudo_legal_moves` method in `PerturbedBoard`.

## Rules Summary

| Rule Name | Class Name | Difficulty | Description |
| :--- | :--- | :--- | :--- |
| bishop_as_rook | BishopAsRookBoard | medium | Bishops move and capture like rooks. |
| knight_two_squares | KnightTwoSquaresBoard | medium | Knights move two squares in any cardinal or diagonal direction, instead of their L-shape. |
| queen_no_backwards | QueenNoBackwardsBoard | easy | Queens cannot move backwards relative to the player's side. |
| pawn_forward_capture | PawnForwardCaptureBoard | hard | Pawns can capture pieces directly in front of them, but they can also be blocked. |

## Per-Rule Details

### Bishop as Rook (`bishop_as_rook`)

**Class**: `BishopAsRookBoard`

The `bishop_as_rook` rule allows bishops to move like rooks. This change applies to all bishops on the board.

- **Hook Points**: `generate_pseudo_legal_moves`
- **Logic**: For each bishop on the board, it temporarily acts as a rook to generate sliding attacks.

**Example Usage**:
```python
from engine.registry import get_board
board = get_board("bishop_as_rook", fen)
# Bishops now move horizontally and vertically.
```

### Knight Two Squares (`knight_two_squares`)

**Class**: `KnightTwoSquaresBoard`

The `knight_two_squares` rule modifies the knight's movement. Instead of the traditional L-shape, knights can move exactly two squares in any of the eight cardinal and diagonal directions.

- **Hook Points**: `generate_pseudo_legal_moves`
- **Logic**: A custom attack table is generated for knights moving two squares in any direction.

**Example Usage**:
```python
# A knight on e4 can move to e6, e2, g4, c4, g6, c6, g2, or c2.
```

### Queen No Backwards (`queen_no_backwards`)

**Class**: `QueenNoBackwardsBoard`

The `queen_no_backwards` rule prevents queens from moving "backwards" towards the player's own starting rank.

- **Hook Points**: `generate_pseudo_legal_moves`
- **Logic**: Filters queen moves based on the rank change relative to the player's turn (white cannot move to a lower rank, black cannot move to a higher rank).

**Example Usage**:
```python
# A white queen on d4 can move to d5, d6, d7, d8, but not to d3 or below.
```

### Pawn Forward Capture (`pawn_forward_capture`)

**Class**: `PawnForwardCaptureBoard`

The `pawn_forward_capture` rule allows pawns to capture pieces that are directly in front of them, in addition to their normal diagonal captures.

- **Hook Points**: `generate_pseudo_legal_moves`
- **Logic**: Adds forward-one moves that consider enemy pieces as valid targets.

**Example Usage**:
```python
# A white pawn on e2 can capture an enemy piece on e3.
```
