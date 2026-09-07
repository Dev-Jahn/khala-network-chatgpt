from dataclasses import dataclass, field
from pathlib import Path
import tomllib
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Settings:
    khala_bin: Path
    khala_home: Path
    state_dir: Path
    transport: str = "http"
    host: str = "127.0.0.1"
    port: int = 8765
    resource_url: str = ""
    issuer: str = ""
    jwks_url: str = ""
    allowed_subjects: list[str] = field(default_factory=list)
    algorithms: list[str] = field(default_factory=lambda: ["RS256"])
    allowed_origins: list[str] = field(default_factory=list)
    allowed_recipients: list[str] = field(default_factory=list)
    local_principal: str = ""

    def validate(self):
        for path in (self.khala_bin, self.khala_home, self.state_dir):
            if not path.is_absolute():
                raise ValueError("All filesystem paths must be absolute")
        if self.transport not in {"http", "stdio"}:
            raise ValueError("transport must be http or stdio")
        if self.transport == "stdio":
            if not self.local_principal:
                raise ValueError("stdio requires an explicit local_principal for this private connection")
        else:
            for url in (self.resource_url, self.issuer, self.jwks_url):
                parsed = urlsplit(url)
                if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.fragment:
                    raise ValueError("HTTP mode requires explicit HTTPS resource_url, issuer and jwks_url")
            if urlsplit(self.resource_url).path != "/mcp" or urlsplit(self.resource_url).query:
                raise ValueError("resource_url must end in /mcp without a query")
            if not self.allowed_subjects:
                raise ValueError("Private HTTP deployments require allowed_subjects")
        if not self.algorithms or not set(self.algorithms) <= {"RS256", "ES256", "EdDSA"}:
            raise ValueError("Only asymmetric JWT algorithms RS256, ES256, EdDSA are supported")


def load_settings(path: Path) -> Settings:
    with path.open("rb") as stream:
        data = tomllib.load(stream)
    for key in ("khala_bin", "khala_home", "state_dir"):
        data[key] = Path(data[key]).expanduser()
    settings = Settings(**data)
    settings.validate()
    return settings
