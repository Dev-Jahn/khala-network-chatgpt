#!/usr/bin/env python3
"""Create a secret-free plugin ZIP pointing at an already deployed HTTPS MCP."""
import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlsplit
import zipfile

parser = argparse.ArgumentParser()
connection = parser.add_mutually_exclusive_group(required=True)
connection.add_argument("--mcp-url")
connection.add_argument("--app-id", help="Registered ChatGPT plugin_asdk_app connection ID")
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
if args.mcp_url:
    url = urlsplit(args.mcp_url)
    if url.scheme != "https" or not url.hostname or url.username or url.query or url.fragment or url.path != "/mcp":
        parser.error("--mcp-url must be https://your-host/mcp without credentials, query, or fragment")
if args.app_id and not re.fullmatch(r"plugin_asdk_app_[A-Za-z0-9_-]+", args.app_id):
    parser.error("--app-id must be the technical ID of your registered ChatGPT MCP connection")
root = Path(__file__).resolve().parents[1]
args.output.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(args.output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    manifest = json.loads((root / ".codex-plugin/plugin.json").read_text())
    if args.app_id:
        manifest.pop("mcpServers", None)
        manifest["apps"] = "./.app.json"
    archive.writestr(".codex-plugin/plugin.json", json.dumps(manifest, indent=2) + "\n")
    for path in sorted((root / "skills").rglob("*")):
        if path.is_file():
            archive.write(path, path.relative_to(root))
    if args.app_id:
        archive.writestr(".app.json", json.dumps({"apps": {"khala": {"id": args.app_id}}}, indent=2) + "\n")
    else:
        archive.writestr(".mcp.json", json.dumps({"mcpServers": {"khala": {"type": "http", "url": args.mcp_url}}}, indent=2) + "\n")
print(args.output)
