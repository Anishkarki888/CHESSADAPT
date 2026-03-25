"rule_name → class mapping"

from engine.rules.movement.bishop_as_rook import BishopAsRookBoard
from engine.rules.movement.knight_two_squares import KnightTwoSquaresBoard
from engine.rules.movement.queen_no_backwards import QueenNoBackwardsBoard
from engine.rules.movement.pawn_forward_capture import PawnForwardCaptureBoard

from engine.rules.win_conditions.capture_all_pawns import CaptureAllPawnsBoard
from engine.rules.win_conditions.centre_race import CentreRaceBoard

from engine.rules.turn_structure.two_moves_per_turn import TwoMovesPerTurnBoard
from engine.rules.turn_structure.no_repeat_piece import NoRepeatPieceBoard


REGISTRY = {
    cls.rule_name: cls
    for cls in [
        BishopAsRookBoard,
        KnightTwoSquaresBoard,
        QueenNoBackwardsBoard,
        PawnForwardCaptureBoard,
        CaptureAllPawnsBoard,
        CentreRaceBoard,
        TwoMovesPerTurnBoard,
        NoRepeatPieceBoard,
    ]
}


def get_board(rule_name: str, fen: str):
    if rule_name not in REGISTRY:
        raise ValueError(f"Unknown rule: {rule_name}")
    return REGISTRY[rule_name](fen)