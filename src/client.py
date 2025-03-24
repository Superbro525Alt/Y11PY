import argparse
from game import Game

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start the game server.")
    parser.add_argument(
        "--name", type=str, default="0", help="Name of the game instance."
    )
    parser.add_argument(
        "--ip", type=str, default="0.0.0.0", help="IP address to bind the server to."
    )
    args = parser.parse_args()

    Game(args.name, ip=args.ip).start()

    while True:
        pass
