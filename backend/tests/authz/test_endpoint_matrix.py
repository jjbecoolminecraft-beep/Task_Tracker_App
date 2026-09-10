"""Endpoint × role authorization matrix (spec §7.2, §12).

    "Automated test suite asserting that each endpoint rejects each role that
     should not have access. This suite is the primary control evidence for
     access-control audits."

Each row is one (actor, request) → expected allow/deny against the seeded world.
A change that widens access fails here loudly.
"""

from __future__ import annotations

import uuid

import pytest

# Seeded roles (see app/seed.py):
#   Anna Weber       System Admin   (global)      — platform admin, NOT a content reader
#   Björn Neumann    Auditor        (global)      — audit log only
#   Clara Schmidt    Portfolio Owner (Corporate)  — owns MKTG + OPS
#   David Fischer    Project Admin  MKTG, Contributor OPS
#   Elena Popova     Project Admin  ENG,  Contributor MKTG
#   Frank Müller     Viewer         MKTG
#   Greta Lang       Contributor    ENG,  Guest on one MKTG task
#   Hugo Bauer       — no roles at all

ALLOW = "allow"
DENY = "deny"


def _key() -> str:
    return "T" + uuid.uuid4().hex[:6].upper()


# label -> (method, path_key, body_factory)
# path_key is formatted with the `world` dict.
REQUESTS: dict[str, tuple[str, str, object]] = {
    "read_project": ("GET", "/api/v1/projects/{mktg_id}", None),
    "update_project": ("PATCH", "/api/v1/projects/{mktg_id}", {"name": "Renamed"}),
    "archive_project": ("POST", "/api/v1/projects/{mktg_id}/archive", {}),
    "manage_members": (
        "POST",
        "/api/v1/projects/{mktg_id}/members",
        {"role": "viewer"},  # user_id filled per-test
    ),
    "list_project_tasks": ("GET", "/api/v1/projects/{mktg_id}/tasks", None),
    "create_task": ("POST", "/api/v1/projects/{mktg_id}/tasks", {"title": "x"}),
    "read_task": ("GET", "/api/v1/tasks/{mktg_task_id}", None),
    "update_task": (
        "PATCH",
        "/api/v1/tasks/{mktg_task_id}",
        {"title": "y"},
    ),
    "comment_task": ("POST", "/api/v1/tasks/{mktg_task_id}/comments", {"body": "hi"}),
    "export_tasks": ("GET", "/api/v1/projects/{mktg_id}/tasks/export?format=csv", None),
    "dashboard": ("GET", "/api/v1/projects/{mktg_id}/dashboard", None),
    "read_audit": ("GET", "/api/v1/audit", None),
}

# request label -> {actor display name: ALLOW|DENY}
EXPECTATIONS: dict[str, dict[str, str]] = {
    "read_project": {
        "Anna Weber": DENY,
        "Björn Neumann": DENY,
        "Clara Schmidt": ALLOW,
        "David Fischer": ALLOW,
        "Elena Popova": ALLOW,
        "Frank Müller": ALLOW,
        "Greta Lang": ALLOW,  # guest may resolve project context
        "Hugo Bauer": DENY,
    },
    "update_project": {
        "Anna Weber": DENY,
        "Clara Schmidt": ALLOW,
        "David Fischer": ALLOW,
        "Elena Popova": DENY,  # only Contributor on MKTG
        "Frank Müller": DENY,
        "Greta Lang": DENY,
        "Hugo Bauer": DENY,
    },
    "archive_project": {
        "Clara Schmidt": ALLOW,
        "David Fischer": ALLOW,
        "Elena Popova": DENY,
        "Frank Müller": DENY,
        "Hugo Bauer": DENY,
    },
    "manage_members": {
        "Anna Weber": DENY,
        "Clara Schmidt": ALLOW,
        "David Fischer": ALLOW,
        "Elena Popova": DENY,
        "Frank Müller": DENY,
        "Hugo Bauer": DENY,
    },
    "list_project_tasks": {
        "Anna Weber": DENY,
        "Björn Neumann": DENY,
        "Clara Schmidt": ALLOW,
        "David Fischer": ALLOW,
        "Elena Popova": ALLOW,
        "Frank Müller": ALLOW,
        "Greta Lang": ALLOW,  # but scoped to shared tasks — see test_row_level_filtering
        "Hugo Bauer": DENY,
    },
    "create_task": {
        "Anna Weber": DENY,
        "Clara Schmidt": ALLOW,
        "David Fischer": ALLOW,
        "Elena Popova": ALLOW,  # Contributor on MKTG
        "Frank Müller": DENY,  # Viewer
        "Greta Lang": DENY,
        "Hugo Bauer": DENY,
    },
    "read_task": {
        "Anna Weber": DENY,
        "Björn Neumann": DENY,
        "Clara Schmidt": ALLOW,
        "David Fischer": ALLOW,
        "Elena Popova": ALLOW,
        "Frank Müller": ALLOW,
        "Greta Lang": DENY,  # this task is NOT the one shared with her
        "Hugo Bauer": DENY,
    },
    "update_task": {
        "Clara Schmidt": ALLOW,
        "David Fischer": ALLOW,
        "Elena Popova": ALLOW,
        "Frank Müller": DENY,
        "Greta Lang": DENY,
        "Hugo Bauer": DENY,
    },
    "comment_task": {
        "Clara Schmidt": ALLOW,
        "David Fischer": ALLOW,
        "Elena Popova": ALLOW,
        "Frank Müller": DENY,
        "Greta Lang": DENY,
        "Hugo Bauer": DENY,
    },
    "export_tasks": {
        # Export == PROJECT_READ. Audited (§8.4.6) but not a write.
        "Anna Weber": DENY,
        "Björn Neumann": DENY,
        "Clara Schmidt": ALLOW,
        "David Fischer": ALLOW,
        "Elena Popova": ALLOW,
        "Frank Müller": ALLOW,  # Viewer may export
        "Hugo Bauer": DENY,
    },
    "dashboard": {
        # Aggregated project reporting == PROJECT_READ (spec §8.4.2).
        "Anna Weber": DENY,
        "Björn Neumann": DENY,
        "Clara Schmidt": ALLOW,
        "David Fischer": ALLOW,
        "Elena Popova": ALLOW,
        "Frank Müller": ALLOW,
        "Hugo Bauer": DENY,
    },
    "read_audit": {
        "Björn Neumann": ALLOW,
        "Anna Weber": DENY,  # System Admin is not an Auditor
        "Clara Schmidt": DENY,
        "David Fischer": DENY,
        "Hugo Bauer": DENY,
    },
}

_CASES = [
    (label, actor, verdict) for label, actors in EXPECTATIONS.items() for actor, verdict in actors.items()
]


@pytest.mark.parametrize(
    ("label", "actor", "verdict"),
    _CASES,
    ids=[f"{label}:{actor.split()[0]}={v}" for label, actor, v in _CASES],
)
async def test_endpoint_matrix(as_user, world, dev_users, label, actor, verdict):
    method, path_tpl, body = REQUESTS[label]
    path = path_tpl.format(**world)
    payload = dict(body) if isinstance(body, dict) else body
    if label == "manage_members":
        payload = {**payload, "user_id": dev_users["Hugo Bauer"]["id"]}

    client = await as_user(actor)
    if method in ("POST", "PATCH", "PUT"):
        resp = await client.request(method, path, json=payload if payload is not None else {})
    else:
        resp = await client.request(method, path)

    if verdict == ALLOW:
        # 428 = authorization passed, the handler now wants an If-Match precondition
        # (optimistic concurrency). That is still an "allowed" outcome for this matrix.
        assert (
            resp.status_code < 400 or resp.status_code == 428
        ), f"{actor} should be allowed to {label}, got {resp.status_code}: {resp.text}"
    else:
        assert resp.status_code in (
            401,
            403,
            404,
        ), f"{actor} should be denied {label}, got {resp.status_code}: {resp.text}"


async def test_unauthenticated_is_rejected(client, world):
    for method, path_tpl, body in REQUESTS.values():
        resp = await client.request(method, path_tpl.format(**world), json=body or {})
        assert resp.status_code == 401, f"{method} {path_tpl} leaked without a token"
