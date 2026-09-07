import asyncio
import hashlib
import jwt
from mcp.server.auth.provider import AccessToken

from .config import Settings

SCOPES = {"khala:connect", "khala:read", "khala:send", "khala:ack", "khala:fleet"}


def principal(issuer: str, subject: str) -> str:
    return hashlib.sha256((issuer + "\0" + subject).encode()).hexdigest()


class JWTVerifier:
    """Pinned issuer/JWKS/audience; never follow an issuer supplied by a token."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.jwks = jwt.PyJWKClient(settings.jwks_url, cache_jwk_set=True, lifespan=300, timeout=5)

    def verify_sync(self, token: str) -> AccessToken | None:
        try:
            if len(token) > 16384:
                return None
            key = self.jwks.get_signing_key_from_jwt(token)
            claims = jwt.decode(token, key.key, algorithms=self.settings.algorithms,
                                issuer=self.settings.issuer, audience=self.settings.resource_url,
                                options={"require": ["exp", "iss", "aud", "sub", "iat"]})
            if claims["sub"] not in self.settings.allowed_subjects:
                return None
            scope = claims.get("scope", "")
            if not isinstance(scope, str):
                return None
            scopes = set(scope.split()) & SCOPES
            if "khala:connect" not in scopes:
                return None
            return AccessToken(token=token, client_id=str(claims.get("client_id", "chatgpt")),
                               subject=claims["sub"], scopes=sorted(scopes),
                               expires_at=int(claims["exp"]), resource=self.settings.resource_url,
                               claims={"iss": claims["iss"]})
        except (jwt.PyJWTError, ValueError, TypeError, KeyError):
            return None

    async def verify_token(self, token: str) -> AccessToken | None:
        return await asyncio.to_thread(self.verify_sync, token)
