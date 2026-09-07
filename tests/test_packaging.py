import json
from pathlib import Path
import subprocess
import sys
import zipfile


def test_registered_connection_package_excludes_server_state(tmp_path):
    root = Path(__file__).resolve().parents[1]
    output = tmp_path / "plugin.zip"
    subprocess.run([sys.executable, str(root / "scripts/package-plugin.py"),
                    "--app-id", "plugin_asdk_app_test", "--output", str(output)], check=True, capture_output=True)
    with zipfile.ZipFile(output) as archive:
        assert set(archive.namelist()) == {".codex-plugin/plugin.json", ".app.json", "skills/khala/SKILL.md"}
        manifest = json.loads(archive.read(".codex-plugin/plugin.json"))
        assert manifest["apps"] == "./.app.json"
        assert "mcpServers" not in manifest
        assert json.loads(archive.read(".app.json"))["apps"]["khala"]["id"] == "plugin_asdk_app_test"


def test_remote_package_rejects_credentials_in_url(tmp_path):
    root = Path(__file__).resolve().parents[1]
    output = tmp_path / "plugin.zip"
    result = subprocess.run([sys.executable, str(root / "scripts/package-plugin.py"),
                             "--mcp-url", "https://user:secret@khala.example/mcp", "--output", str(output)],
                            capture_output=True)
    assert result.returncode != 0
    assert not output.exists()
