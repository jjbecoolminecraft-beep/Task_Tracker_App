"""In-app notifications (spec F-10): created in the same transaction as the
change, scoped strictly to the recipient, never for the actor's own action.
"""

from __future__ import annotations

import pytest


@pytest.fixture
async def actors(as_user, dev_users):
    return {
        "david": await as_user("David Fischer"),  # Project Admin MKTG
        "elena": await as_user("Elena Popova"),  # Contributor MKTG
        "clara": await as_user("Clara Schmidt"),
        "ids": {k: v["id"] for k, v in dev_users.items()},
    }


async def _unread(client) -> int:
    return (await client.get("/api/v1/me/notifications/unread-count")).json()["unread"]


async def test_assigning_a_task_notifies_the_assignee_not_the_actor(actors, world):
    david, elena = actors["david"], actors["elena"]
    resp = await david.post(
        f"/api/v1/projects/{world['mktg_id']}/tasks",
        json={"title": "Notify me", "assignee_id": actors["ids"]["Elena Popova"]},
    )
    assert resp.status_code == 201
    ref = resp.json()["ref"]

    assert await _unread(elena) == 1
    assert await _unread(david) == 0  # actor never notified of own action

    feed = (await elena.get("/api/v1/me/notifications")).json()
    assert feed[0]["kind"] == "task.assigned"
    assert feed[0]["actor_name"] == "David Fischer"
    assert feed[0]["task_ref"] == ref
    assert feed[0]["is_read"] is False


async def test_reassignment_notifies_only_the_new_assignee(actors, world):
    david = actors["david"]
    tid = (await david.post(f"/api/v1/projects/{world['mktg_id']}/tasks", json={"title": "reassign"})).json()[
        "id"
    ]
    # assign to Elena
    await david.patch(
        f"/api/v1/tasks/{tid}",
        headers={"If-Match": '"1"'},
        json={"assignee_id": actors["ids"]["Elena Popova"]},
    )
    assert await _unread(actors["elena"]) == 1
    # reassign to Clara
    await david.patch(
        f"/api/v1/tasks/{tid}",
        headers={"If-Match": '"2"'},
        json={"assignee_id": actors["ids"]["Clara Schmidt"]},
    )
    assert await _unread(actors["clara"]) == 1
    assert await _unread(actors["elena"]) == 1  # unchanged — not re-notified


async def test_comment_mention_and_assignee_fanout(actors, world):
    david, elena, clara = actors["david"], actors["elena"], actors["clara"]
    tid = (
        await david.post(
            f"/api/v1/projects/{world['mktg_id']}/tasks",
            json={"title": "discuss", "assignee_id": actors["ids"]["Elena Popova"]},
        )
    ).json()["id"]

    await david.post(
        f"/api/v1/tasks/{tid}/comments",
        json={"body": f"@[Clara Schmidt]({actors['ids']['Clara Schmidt']}) take a look"},
    )

    clara_feed = (await clara.get("/api/v1/me/notifications")).json()
    assert clara_feed[0]["kind"] == "comment.mention"
    assert "@Clara Schmidt" in clara_feed[0]["snippet"]  # markup stripped
    assert "](" not in clara_feed[0]["snippet"]

    elena_feed = (await elena.get("/api/v1/me/notifications?unread=true")).json()
    kinds = {n["kind"] for n in elena_feed}
    assert "comment.added" in kinds  # assignee heard about the comment
    assert "task.assigned" in kinds


async def test_mark_read_and_read_all(actors, world):
    david, elena = actors["david"], actors["elena"]
    for i in range(3):
        await david.post(
            f"/api/v1/projects/{world['mktg_id']}/tasks",
            json={"title": f"n{i}", "assignee_id": actors["ids"]["Elena Popova"]},
        )
    assert await _unread(elena) == 3

    first = (await elena.get("/api/v1/me/notifications")).json()[0]["id"]
    assert (await elena.post(f"/api/v1/me/notifications/{first}/read")).status_code == 204
    assert await _unread(elena) == 2

    assert (await elena.post("/api/v1/me/notifications/read-all")).json()["unread"] == 0
    assert await _unread(elena) == 0


async def test_a_user_cannot_touch_another_users_notifications(actors, world):
    david, elena = actors["david"], actors["elena"]
    await david.post(
        f"/api/v1/projects/{world['mktg_id']}/tasks",
        json={"title": "mine", "assignee_id": actors["ids"]["Elena Popova"]},
    )
    nid = (await elena.get("/api/v1/me/notifications")).json()[0]["id"]

    assert (await david.post(f"/api/v1/me/notifications/{nid}/read")).status_code == 404
    assert await _unread(elena) == 1  # still unread
