from dataclasses import replace
from types import SimpleNamespace
import time

from cryptography.hazmat.primitives.asymmetric import rsa
import jwt
import pytest
from starlette.testclient import TestClient

from khala_chatgpt.auth import JWTVerifier, SCOPES
from khala_chatgpt.server import create_server


@pytest.fixture
def oauth(bridge, monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    # Only replace JWKS network retrieval; the real JWT signature/claim verifier runs.
    monkeypatch.setattr(jwt.PyJWKClient, "get_signing_key_from_jwt", lambda self, token: SimpleNamespace(key=key.public_key()))
    settings = replace(bridge.settings, transport="http", resource_url="https://khala.example/mcp",
                       issuer="https://identity.example", jwks_url="https://identity.example/jwks",
                       allowed_subjects=["jahn", "second-owner"])

    def token(**overrides):
        claims = {"iss": settings.issuer, "aud": settings.resource_url, "sub": "jahn",
                  "iat": int(time.time()), "exp": int(time.time()) + 300, "scope": " ".join(sorted(SCOPES))}
        claims.update(overrides)
        return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test"})

    return settings, token


@pytest.mark.parametrize("claims", [
    {"aud": "https://other.example/mcp"}, {"iss": "https://evil.example"},
    {"sub": "unapproved"}, {"exp": 1}, {"iat": int(time.time()) + 3600},
    {"scope": "khala:read"}, {"scope": ["khala:connect"]},
])
def test_reject_wrong_or_expired_credentials(oauth, claims):
    settings, token = oauth
    assert JWTVerifier(settings).verify_sync(token(**claims)) is None


def test_valid_token_and_unsigned_token(oauth):
    settings, token = oauth
    result = JWTVerifier(settings).verify_sync(token())
    assert result.subject == "jahn"
    assert set(result.scopes) == SCOPES
    forged = jwt.encode({"sub": "jahn"}, "", algorithm="none")
    assert JWTVerifier(settings).verify_sync(forged) is None


def test_http_discovery_auth_scopes_and_subject_isolation(oauth):
    settings, token = oauth
    app = create_server(settings).streamable_http_app()
    headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    with TestClient(app, base_url="https://khala.example") as client:
        metadata = client.get("/.well-known/oauth-protected-resource/mcp").json()
        assert metadata["resource"] == settings.resource_url
        assert set(metadata["scopes_supported"]) == SCOPES
        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        denied = client.post("/mcp", json=request, headers=headers)
        assert denied.status_code == 401
        assert "resource_metadata=" in denied.headers["www-authenticate"]
        authed = {**headers, "Authorization": "Bearer " + token()}
        tools = client.post("/mcp", json=request, headers=authed).json()["result"]["tools"]
        assert len(tools) == 7
        assert all("outputSchema" in tool for tool in tools)
        assert all("securitySchemes" in tool for tool in tools)

        def call(name, arguments, credential=None):
            response = client.post("/mcp", headers={**headers, "Authorization": "Bearer " + (credential or token())},
                                   json={"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                                         "params": {"name": name, "arguments": arguments,
                                                    "_meta": {"openai/session": "same-session-metadata"}}})
            assert response.status_code == 200
            return response.json()["result"]

        opened = call("khala_session_open", {})
        assert not opened.get("isError")
        mailbox = opened["structuredContent"]["mailbox_id"]
        # Same OpenAI session metadata is never a substitute for OAuth ownership.
        forbidden = call("khala_inbox_list", {"mailbox_id": mailbox}, token(sub="second-owner"))
        assert forbidden["isError"]
        narrow = token(scope="khala:connect khala:read")
        allowed = call("khala_inbox_list", {"mailbox_id": mailbox}, narrow)
        assert not allowed.get("isError")
        denied = call("khala_message_send", {"mailbox_id": mailbox, "to": "worker@chatgpt",
                                           "subject": "test", "body": "test", "request_id": "one"}, narrow)
        assert denied["isError"]
        origin = client.post("/mcp", json=request, headers={**authed, "Origin": "https://evil.example"})
        assert origin.status_code == 403
