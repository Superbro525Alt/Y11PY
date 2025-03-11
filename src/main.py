import threading
from time import sleep
from game import PandemicGame
from network import Client, Server

from typing import Dict, List, Set, Tuple, Optional
import random
from collections import defaultdict
from queue import PriorityQueue
import heapq

class PandemicBot:
    def __init__(self, client, team_bots=None):
        self.client = client
        self.team_bots = team_bots if team_bots else []
        self.name = client.player_name
        self.target_city = None
        self.current_mission = None
        
    def get_path_to_city(self, start: str, end: str) -> List[str]:
        """Find shortest path between cities using A* pathfinding."""
        if start == end:
            return []
            
        board = self.client.board
        cities = board["cities"]
        
        def heuristic(city1: str, city2: str) -> float:
            """Calculate approximate distance between cities using their coordinates."""
            x1, y1 = cities[city1]["x"], cities[city1]["y"]
            x2, y2 = cities[city2]["x"], cities[city2]["y"]
            return ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5
        
        frontier = [(0, start, [start])]
        visited = set()
        
        while frontier:
            _, current, path = heapq.heappop(frontier)
            
            if current == end:
                return path[1:]  # Exclude starting city
                
            if current in visited:
                continue
                
            visited.add(current)
            
            for neighbor in cities[current]["neighbors"]:
                if neighbor not in visited:
                    new_path = path + [neighbor]
                    priority = len(new_path) + heuristic(neighbor, end)
                    heapq.heappush(frontier, (priority, neighbor, new_path))
        
        return []  # No path found

    def assess_city_threat(self, city: str) -> float:
        """Calculate how threatening a city's disease situation is."""
        diseases = self.client.board["cities"][city].get("disease", {})
        threat = 0
        
        # Higher threat for cities with more disease cubes
        for color, count in diseases.items():
            threat += count * 2
            
        # Additional threat for cities with multiple disease types
        if len(diseases) > 1:
            threat *= 1.5
            
        # Consider neighboring cities' diseases
        for neighbor in self.client.board["cities"][city]["neighbors"]:
            neighbor_diseases = self.client.board["cities"][neighbor].get("disease", {})
            for count in neighbor_diseases.values():
                threat += count * 0.5
                
        return threat

    def find_most_threatened_cities(self) -> List[Tuple[str, float]]:
        """Return cities sorted by threat level."""
        threats = []
        for city in self.client.board["cities"]:
            threat = self.assess_city_threat(city)
            if threat > 0:
                threats.append((city, threat))
        
        return sorted(threats, key=lambda x: x[1], reverse=True)

    def get_team_positions(self) -> Dict[str, str]:
        """Get current locations of all team members."""
        return {player: data["location"] 
                for player, data in self.client.board["players"].items()}

    def coordinate_with_team(self) -> Optional[str]:
        """Coordinate actions with team members to avoid redundant moves."""
        threatened_cities = self.find_most_threatened_cities()
        team_positions = self.get_team_positions()
        
        # Don't target cities that other bots are already heading to or at
        claimed_cities = {pos for pos in team_positions.values()}
        for bot in self.team_bots:
            if bot.target_city:
                claimed_cities.add(bot.target_city)
                
        # Find the highest threat city that isn't claimed
        for city, threat in threatened_cities:
            if city not in claimed_cities:
                return city
                
        return None

    def should_build_research_station(self) -> bool:
        """Decide if we should build a research station at current location."""
        current_city = self.client.board["players"][self.name]["location"]
        
        # Don't build if there's already a station here
        if self.client.board["cities"][current_city]["research_center"]:
            return False
            
        # Count existing research stations
        existing_stations = sum(1 for city in self.client.board["cities"].values() 
                              if city["research_center"])
                              
        # Build if this is a high-threat city with no nearby stations
        if self.assess_city_threat(current_city) > 3:
            # Check if there's a station within 2 moves
            for neighbor in self.client.board["cities"][current_city]["neighbors"]:
                if self.client.board["cities"][neighbor]["research_center"]:
                    return False
                for neighbor2 in self.client.board["cities"][neighbor]["neighbors"]:
                    if self.client.board["cities"][neighbor2]["research_center"]:
                        return False
            return True
            
        return False

    def take_turn(self):
        """Execute the bot's turn with intelligent decision making."""
        if not self.client.is_my_turn:
            return
            
        while self.client.actions_remaining > 0:
            current_city = self.client.board["players"][self.name]["location"]
            
            # Priority 1: Treat diseases about to outbreak (3 cubes)
            current_diseases = self.client.board["cities"][current_city].get("disease", {})
            for disease, count in current_diseases.items():
                if count >= 3:
                    self.client.send_action("treat")
                    return
                    
            # Priority 2: Build research station if needed
            if self.should_build_research_station():
                self.client.send_action("build")
                return
                
            # Priority 3: Treat any disease in current city
            if current_diseases:
                self.client.send_action("treat")
                return
                
            # Priority 4: Move toward highest threat city
            if not self.target_city or self.target_city == current_city:
                self.target_city = self.coordinate_with_team()
                
            if self.target_city:
                path = self.get_path_to_city(current_city, self.target_city)
                if path:
                    self.client.send_action("move", {"destination": path[0]})
                    return
                    
            # If no other actions are possible, pass the turn
            self.client.send_action("pass")
            return

def create_bot_team(bots_clients) -> List[PandemicBot]:
    """Create a team of bots that can coordinate with each other."""
    bots = []
    for client in bots_clients:
        bot = PandemicBot(client)
        bots.append(bot)
    
    # Give each bot references to its teammates
    for bot in bots:
        bot.team_bots = [b for b in bots if b != bot]
    
    return bots

def main():
    # Start the server
    server = Server(5000)
    print("Server started on port 5000")
    
    # Create the game instance for visualization
    game = PandemicGame()
    
    # Create bot clients
    bot_clients = []
    bot_names = ["Bot1", "Bot2", "Bot3"]
    
    for bot_name in bot_names:
        client = Client("localhost", 5000, bot_name)
        bot_clients.append(client)
    
    # Create smart bot team
    bots = create_bot_team(bot_clients)
    
    # Bot AI loop - runs in background
    def bot_actions(bot):
        while True:
            sleep(0.2)  # Small delay between actions
            if bot.client.is_my_turn:
                bot.take_turn()

    # Start bot AI in background thread
    for bot in bots:
        bot_thread = threading.Thread(target=lambda: bot_actions(bot), daemon=True)
        bot_thread.start()
    
    # Update game board state from server
    def update_game_state():
        while True:
            if bot_clients and bot_clients[0].board:
                game.board.update_from_server(bot_clients[0].board)
            sleep(0.1)
    
    # Start state update thread
    
    # Start the game
    game.setup()
    game.start()

    state_thread = threading.Thread(target=update_game_state, daemon=True)
    state_thread.start()

    
    # Cleanup
    for client in bot_clients:
        client.close()

if __name__ == "__main__":
    main()
