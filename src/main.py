import threading
import random
from time import sleep
from engine import EngineFrameData, FullGameEngine
from game import Board, PandemicGame, pretty_print_board
from network import Server, Client
from pipeline import Event, FramePipeline, StateData


def run_server():
    """Starts the game server."""
    server = Server(port=5000)

    while True:
        pretty_print_board(server.board.broadcast_state())
        sleep(1)

class SmartBot:
    """An AI player that plays strategically."""

    def __init__(self, player_name):
        self.client = Client(address="127.0.0.1", port=5000, player_name=player_name)

    def get_most_infected_city(self):
        """Finds the city with the highest disease cubes."""
        max_cubes = 0
        target_city = None

        for city, data in self.client.board["cities"].items():
            total_cubes = sum(data.get("disease", {}).values())
            if total_cubes > max_cubes:
                max_cubes = total_cubes
                target_city = city

        return target_city, max_cubes

    def get_best_move(self, current_city):
        """Finds the best move to reach the most infected city faster."""
        target_city, _ = self.get_most_infected_city()
        if not target_city:
            return None  

        neighbors = self.client.board["cities"][current_city]["neighbors"]
        if target_city in neighbors:
            return target_city  # Move directly if possible

        # Otherwise, move toward it by choosing a neighbor that gets closer
        best_choice = None
        min_distance = float("inf")

        for neighbor in neighbors:
            distance = len(set(self.client.board["cities"][neighbor]["neighbors"]) & {target_city})
            if distance < min_distance:
                best_choice = neighbor
                min_distance = distance

        return best_choice

    def play_turn(self):
        """Executes an AI turn with improved decision-making."""
        while True:
            sleep(0.1) 
            if self.client.is_my_turn:
                current_location = self.client.board["players"][self.client.player_name]["location"]

                if self.client.board["cities"][current_location]["disease"]:
                    self.client.send_action("treat")
                    continue

                best_move = self.get_best_move(current_location)
                if best_move:
                    self.client.send_action("move", {"destination": best_move})
                    continue

                self.client.send_action("pass")


def run_bot(player_name):
    """Creates a bot and makes it play automatically with improved AI."""
    bot = SmartBot(player_name)
    bot.play_turn()


def find_missing_neighbors(cities):
    missing_neighbors = set()
    
    for city, data in cities.items():
        for neighbor in data["neighbors"]:
            if neighbor not in cities:
                missing_neighbors.add(neighbor)
    
    if missing_neighbors:
        print("The following neighbors are missing from the top-level dictionary:")
        for neighbor in sorted(missing_neighbors):
            print(neighbor)
    else:
        print("All neighbors are accounted for.")

if __name__ == "__main__":
    # Start server
    # find_missing_neighbors(Board.CITIES)
    # threading.Thread(target=run_server, daemon=True).start()
    # #
    # # # Start bot players
    # bot_names = ["Bot1", "Bot2", "Bot3", "Bot4"]
    # for name in bot_names:
    #     threading.Thread(target=run_bot, args=(name,), daemon=True).start()
    # #
    # while True:
        # sleep(1)
    game = PandemicGame()
    game.with_callback(lambda this: [this.board.end_turn() for i in range(500)])
    game.start()
