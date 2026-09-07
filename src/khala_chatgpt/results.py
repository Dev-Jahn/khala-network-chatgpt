"""Explicit MCP structured output schemas."""
from typing_extensions import NotRequired, TypedDict


class SessionResult(TypedDict):
    mailbox_id: str
    address: str
    receive_mode: str
    wake: bool


class MessageMetadata(TypedDict):
    id: str
    to: str
    subject: str
    date: str
    type: str
    in_reply_to: str | None
    priority: str
    state: str
    trust: str


# 'from' is a Python keyword, hence functional TypedDict declaration.
MessageMetadata = TypedDict("MessageMetadata", {**MessageMetadata.__annotations__, "from": str})
ListItem = TypedDict("ListItem", {**MessageMetadata.__annotations__, "bytes": int})


class ListError(TypedDict):
    id: str
    error: str


class InboxResult(TypedDict):
    messages: list[ListItem | ListError]
    next_cursor: str | None
    read_semantics: str


class ReadResult(TypedDict):
    message: MessageMetadata
    body: str
    offset: int
    complete: bool
    next_cursor: str | None
    read_receipt: str | None
    instruction: str


class AckResult(TypedDict):
    acknowledged_ids: list[str]
    meaning: str


SendResult = TypedDict("SendResult", {"id": str, "request_id": str, "from": str, "to": str,
                                    "status": str, "meaning": str})


class StatusResult(TypedDict):
    id: NotRequired[str | None]
    status: str
    retry_same_request_id: NotRequired[bool | None]
    meaning: NotRequired[str | None]


class Presence(TypedDict):
    address: str
    activity: str
    last_seen: str
    watching: str


class FleetResult(TypedDict):
    sessions: list[Presence]
    truncated: bool
    meaning: str
    chatgpt_receive_mode: str
