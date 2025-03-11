from threading import Thread
from game import AuthState, Game, GameServer, GameState
from game_packet import PacketType
from network import Packet, Server


if __name__ == "__main__":
    GameServer()
    [Thread(target=lambda: Game(str(i)).start(), daemon=True).start() for i in range(2)]

    try:
        while True:
            pass
    except KeyboardInterrupt:
        exit(0)
