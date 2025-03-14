from threading import Thread
import threading
from game import AuthState, Game, GameNetworkClient, GameServer, GameState
from game_packet import PacketType
from network import Packet, Server
from concurrent.futures import ThreadPoolExecutor
from time import sleep

if __name__ == "__main__":
    GameServer()
    g1 = Game("0")
    g2 = Game("1")
    threading.Thread(target=lambda: g1.start(), daemon=True).start()
    threading.Thread(target=lambda: g2.start(), daemon=True).start()

    while True:
        pass
