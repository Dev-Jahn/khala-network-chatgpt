import os
from pathlib import Path
import subprocess
import pytest

from khala_chatgpt.bridge import Bridge
from khala_chatgpt.config import Settings


@pytest.fixture
def bridge(tmp_path):
    cli = Path(os.environ["KHALA_TEST_BIN"]).resolve()
    home = tmp_path / "node"
    subprocess.run([str(cli), "init", "chatgpt"], env={**os.environ, "KHALA_HOME": str(home)},
                   check=True, capture_output=True)
    return Bridge(Settings(khala_bin=cli, khala_home=home, state_dir=tmp_path / "state",
                           transport="stdio", local_principal="test-owner"))


def deliver(bridge, mailbox, body="hello"):
    message_id = bridge.run("send", f"{mailbox}@chatgpt", "-s", "test", mailbox="sender", body=body)
    bridge.run("reconcile")
    return message_id
