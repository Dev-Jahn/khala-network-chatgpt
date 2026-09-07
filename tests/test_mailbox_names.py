import concurrent.futures
import hashlib
import re
import time

import pytest

from khala_chatgpt.bridge import Bridge
from conftest import deliver


def test_short_names_and_stable_binding_across_modes(bridge):
    chat = bridge.session_open("owner", "chat")
    work = bridge.session_open("owner", "work", client_mode="work")
    assert re.fullmatch(r"gpt-chat-[0-9a-f]{8}@chatgpt", chat["address"])
    assert re.fullmatch(r"gpt-work-[0-9a-f]{8}@chatgpt", work["address"])
    assert bridge.session_open("owner", "chat", client_mode="work") == chat
    assert bridge.session_open("owner", "resume", work["mailbox_id"]) == work
    assert Bridge(bridge.settings).session_open("owner", "work") == work
    with pytest.raises(ValueError, match="client_mode"):
        bridge.session_open("owner", "invalid", client_mode="../other")


def test_short_identifier_collision_does_not_share_mailboxes(bridge, monkeypatch):
    candidates = iter(["deadbeef", "deadbeef", "cafebabe"])
    monkeypatch.setattr("khala_chatgpt.store.secrets.token_hex", lambda n: next(candidates))
    first = bridge.session_open("one", "same")
    second = bridge.session_open("two", "same")
    assert first["mailbox_id"] == "gpt-chat-deadbeef"
    assert second["mailbox_id"] == "gpt-chat-cafebabe"
    with pytest.raises(ValueError):
        bridge.inbox_list("two", first["mailbox_id"])
    monkeypatch.setattr("khala_chatgpt.store.secrets.token_hex", lambda n: "deadbeef")
    with pytest.raises(RuntimeError, match="unique mailbox"):
        bridge.session_open("three", "new")
    with bridge.store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM mailboxes").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM bindings").fetchone()[0] == 2


def test_concurrent_open_allocates_one_address(bridge):
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: bridge.session_open("owner", "shared", client_mode="work"),
                                range(8)))
    assert len({r["mailbox_id"] for r in results}) == 1
    with bridge.store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM mailboxes").fetchone()[0] == 1


def test_existing_cg_address_preserves_mail_receipts_and_retry_records(bridge):
    mailbox = "cg-0123456789abcdef01234567"
    with bridge.store.connect() as db:
        db.execute("INSERT INTO mailboxes VALUES (?, ?, ?)", (mailbox, "owner", int(time.time())))
        db.execute("INSERT INTO bindings VALUES (?, ?, ?)",
                   ("owner", hashlib.sha256(b"existing").hexdigest(), mailbox))
    message_id = deliver(bridge, mailbox)
    receipt = bridge.message_read("owner", mailbox, message_id)["read_receipt"]
    send = dict(owner="owner", mailbox=mailbox, to=f"{mailbox}@chatgpt",
                subject="retry", body="preserve", request_id="existing-send")
    sent = bridge.message_send(**send)
    reopened = Bridge(bridge.settings)
    assert reopened.session_open("owner", "existing", client_mode="work")["mailbox_id"] == mailbox
    assert reopened.session_open("owner", "resume", mailbox)["mailbox_id"] == mailbox
    assert reopened.message_send(**send) == sent
    reopened.inbox_ack_read("owner", mailbox, [receipt])
    assert (bridge.root / "inbox" / mailbox / "cur" / message_id).is_file()
