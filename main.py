from game import Game
from constants import NANO, MINI, FOUR_1, FOUR_0, HUMAN
players = [HUMAN,
           HUMAN,
           HUMAN]

if __name__ == "__main__":
    Game(players=players).run()
