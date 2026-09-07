import argparse
import os
from pathlib import Path

from .bridge import Bridge
from .config import load_settings
from .server import create_server


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description="Khala MCP bridge for ChatGPT")
    parser.add_argument("command", choices=["serve", "check"])
    parser.add_argument("--config", type=Path,
                        default=Path(os.environ.get("KHALA_CHATGPT_CONFIG", "/etc/khala-chatgpt/config.toml")))
    args = parser.parse_args()
    settings = load_settings(args.config)
    if args.command == "check":
        bridge = Bridge(settings)
        print(f"Ready: node={bridge.node}, transport={settings.transport}, receipt storage initialized")
        return
    server = create_server(settings)
    server.run(transport="stdio" if settings.transport == "stdio" else "streamable-http")


if __name__ == "__main__":
    main()
