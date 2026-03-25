from engine.utils.visualizer import interactive_session
import chess

board = interactive_session(chess.STARTING_FEN, "bishop_as_rook") 
print(list(board)) 