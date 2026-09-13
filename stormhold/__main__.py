"""Start Stormhold.

    python -m stormhold                 play (host or join from the menu)
    python -m stormhold --serve         run a dedicated server, no window
    python -m stormhold --help          all the options
"""

import argparse
import sys
import time


def main(argv=None):
    parser = argparse.ArgumentParser(prog="stormhold", description="Stormhold")
    parser.add_argument("--serve", action="store_true",
                        help="run a dedicated server with no game window")
    parser.add_argument("--port", type=int, default=7777, help="port to use (default 7777)")
    parser.add_argument("--host", default="0.0.0.0", help="address to bind when serving")
    parser.add_argument("--seed", type=int, default=None, help="fixed world seed")
    parser.add_argument("--name", default=None, help="character name to prefill")
    parser.add_argument("--save", default=None, help="path to the party save file")
    parser.add_argument("--fullscreen", action="store_true", help="start full screen")
    args = parser.parse_args(argv)

    if args.serve:
        return serve(args)
    return play(args)


def serve(args):
    import os
    from .net.server import GameServer, lan_addresses

    save = args.save or os.path.join(os.getcwd(), "data", "party.json")
    server = GameServer(args.host, args.port, args.seed, save).start()
    print()
    print("  S T O R M H O L D  -  the keep is open")
    print()
    for address in lan_addresses() or ["(no network interface found)"]:
        print(f"    others join at   {address}  port {args.port}")
    print(f"    world seed       {server.world.seed}")
    print(f"    characters saved {save}")
    print()
    print("  Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n  Saving and shutting down...")
        server.stop()
    return 0


def play(args):
    try:
        import pygame  # noqa: F401
    except ImportError:
        print("Stormhold needs pygame. Install it with:\n")
        print("    python -m pip install pygame-ce\n")
        return 1
    from .ui.app import App
    App(args).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
