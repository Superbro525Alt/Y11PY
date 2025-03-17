from threading import Thread
import threading
from game import AuthState, Game, GameNetworkClient, GameServer, GameState
from game_packet import PacketType
from network import Packet, Server
from concurrent.futures import ThreadPoolExecutor
from time import sleep

if __name__ == "__main__":
    GameServer()
    [
        threading.Thread(target=lambda: Game(str(i)).start(), daemon=True).start()
        for i in range(2)
    ]

    while True:
        pass
