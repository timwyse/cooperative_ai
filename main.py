from game import Game
from player import NANO, MINI, FOUR_1, FOUR_0, HUMAN, LLAMA_3_3B
players = [
    HUMAN,
    LLAMA_3_3B,
]

if __name__ == "__main__":
    Game().run()
