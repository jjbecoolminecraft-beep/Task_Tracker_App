"""Task CRUD, optimistic concurrency, soft delete, and the audit guarantee."""

from __future__ import annotations

import pytest


@pytest.fixture
async def david(as_user):
    return await as_user("David Fischer")  # Project Admin on MKTG


async def test_create_read_update_complete_delete(david, world):
    # create
    resp = await david.post(
        f"/api/v1/projects/{world['mktg_id']}/tasks",
        json={"title": "Draft launch email", "priority": 2},
    )
    assert resp.status_code == 201
    task = resp.json()
    assert task["ref"].startswith("MKTG-")
    assert resp.headers["ETag"] == '"1"'
    tid = task["id"]

    # read carries an ETag
    resp = await david.get(f"/api/v1/tasks/{tid}")
    assert resp.headers["ETag"] == '"1"'

    # update requires If-Match
    resp = await david.patch(f"/api/v1/tasks/{tid}", json={"priority": 1})
    assert resp.status_code == 428

    # stale If-Match -> 412
    resp = await david.patch(f"/api/v1/tasks/{tid}", headers={"If-Match": '"99"'}, json={"priority": 1})
    assert resp.status_code == 412

    # correct If-Match -> 200, version bumps
    resp = await david.patch(f"/api/v1/tasks/{tid}", headers={"If-Match": '"1"'}, json={"priority": 1})
    assert resp.status_code == 200
    assert resp.json()["version"] == 2

    # complete moves to a done state and stamps completed_at
    resp = await david.post(f"/api/v1/tasks/{tid}/complete", headers={"If-Match": '"2"'})
    assert resp.status_code == 200
    assert resp.json()["completed_at"] is not None
    assert resp.json()["state_category"] == "done"

    # soft delete
    resp = await david.delete(f"/api/v1/tasks/{tid}", headers={"If-Match": '"3"'})
    assert resp.status_code == 204
    assert (await david.get(f"/api/v1/tasks/{tid}")).status_code == 404


async def test_subtask_depth_is_capped_at_two(david, world):
    parent = (await david.post(f"/api/v1/projects/{world['mktg_id']}/tasks", json={"title": "Parent"})).json()
    child = (
        await david.post(
            f"/api/v1/projects/{world['mktg_id']}/tasks",
            json={"title": "Child", "parent_task_id": parent["id"]},
        )
    ).json()
    resp = await david.post(
        f"/api/v1/projects/{world['mktg_id']}/tasks",
        json={"title": "Grandchild", "parent_task_id": child["id"]},
    )
    assert resp.status_code == 422


async def test_every_mutation_writes_an_audit_event(david, as_user, world):
    auditor = await as_user("Björn Neumann")
    before = len((await auditor.get("/api/v1/audit?limit=500")).json())

    created = await david.post(f"/api/v1/projects/{world['mktg_id']}/tasks", json={"title": "Audited task"})
    tid = created.json()["id"]
    await david.patch(f"/api/v1/tasks/{tid}", headers={"If-Match": '"1"'}, json={"title": "Audited task v2"})

    events = (await auditor.get("/api/v1/audit?limit=500")).json()
    assert len(events) >= before + 2
    actions = {e["action"] for e in events[:5]}
    assert "task.created" in actions
    assert "task.updated" in actions
    # the update event records the before/after of the changed field
    upd = next(e for e in events if e["action"] == "task.updated")
    assert upd["before"] != upd["after"]


async def test_optimistic_concurrency_blocks_lost_updates(as_user, world):
    a = await as_user("David Fischer")
    b = await as_user("Clara Schmidt")

    tid = (await a.post(f"/api/v1/projects/{world['mktg_id']}/tasks", json={"title": "Shared edit"})).json()[
        "id"
    ]

    # both read version 1
    etag_a = (await a.get(f"/api/v1/tasks/{tid}")).headers["ETag"]
    etag_b = (await b.get(f"/api/v1/tasks/{tid}")).headers["ETag"]
    assert etag_a == etag_b == '"1"'

    assert (
        await a.patch(f"/api/v1/tasks/{tid}", headers={"If-Match": etag_a}, json={"priority": 1})
    ).status_code == 200
    # b's write is now stale
    assert (
        await b.patch(f"/api/v1/tasks/{tid}", headers={"If-Match": etag_b}, json={"priority": 5})
    ).status_code == 412
