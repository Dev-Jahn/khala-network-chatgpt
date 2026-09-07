# Validation — 2026-09-07

This repository contains the ChatGPT MCP bridge, plugin package, deployment
examples and automated tests for pull-only Khala mailboxes.

Upstream compatibility is published as
[khala-network PR #1](https://github.com/Dev-Jahn/khala-network/pull/1), commit
`ee7845c4b4e6df156f2d0791b248fce2a90f829c`, based on main
`3b1bbbdb87f139b322535742682ffa7635b7642d`. Main was not updated or merged.

Local validation completed:

- 20 bridge tests: actual MCP stdio round trip, authenticated HTTP discovery and
  tools, signed JWT validation, scope/owner isolation, message pagination,
  receipt binding, concurrent idempotent sends, persistent mappings, package
  contents and credential-bearing URL rejection.
- 9 native compatibility tests, including simulated process interruption
  boundaries and concurrent retries.
- 9 existing Khala local-roundtrip checks covering normal send, ACK, dedup,
  drain, expiry and presence.
- Plugin and bundled skill schema validation; Bash syntax and diff whitespace.

Runtime used here: Python 3.12, MCP SDK 1.29.1, PyJWT 2.13.0,
cryptography 46.0.0, Starlette 1.6.0, uvicorn 0.52.4. Two dependency deprecation
warnings occurred in Starlette's test client; no failing tests.

CI is configured for Python 3.11 and 3.12 with a pinned upstream dependency.
See the repository's Actions tab for the current remote results. Python 3.11
was not run locally.

No production credentials were accessed, no production Khala messages were sent,
and no existing server configuration was modified. Deployment, real OAuth
authorization/refresh UX, Secure MCP Tunnel access and ChatGPT UI installation
still require the owner's actual server and connection configuration. The
included services, configs and packaging helper make those choices explicit.
