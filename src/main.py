import threading
from game import Game, GameServer

if __name__ == "__main__":
    GameServer()
    [
        threading.Thread(target=lambda: Game(str(i)).start(), daemon=True).start()
        for i in range(2)
    ]

    while True:
        pass
