import chess
from engine.registry import get_board


def print_board(board: chess.Board):
    print(board)
    print(f"\nTurn: {'White' if board.turn else 'Black'}")


def print_legal_moves(board: chess.Board):
    moves = list(board.legal_moves)
    print(f"\nLegal moves ({len(moves)}):")
    print(", ".join(m.uci() for m in moves))


def interactive_session(fen: str, rule_name: str):
    board = get_board(rule_name, fen)

    while True:
        print("\n" + "=" * 40)
        print_board(board)

        # FIX: store moves ONCE
        legal_moves = list(board.legal_moves)

        print(f"\nLegal moves ({len(legal_moves)}):")
        print(", ".join(m.uci() for m in legal_moves))

        move_uci = input("\nEnter move (or 'q'): ").strip()
        if move_uci == "q":
            break

        try:
            move = chess.Move.from_uci(move_uci)
        except:
            print("Invalid UCI format")
            continue

        # use stored list
        if move not in legal_moves:
            print("Illegal move under this rule")
            continue

        board.push(move)