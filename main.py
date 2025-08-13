from game import Game
from constants import NANO, MINI, FOUR_1, FOUR_0, HUMAN, LLAMA_3_3B
players = [
    LLAMA_3_3B,
    LLAMA_3_3B,
    LLAMA_3_3B,
    LLAMA_3_3B,
    LLAMA_3_3B,

]

if __name__ == "__main__":
    Game(players=players).run()
