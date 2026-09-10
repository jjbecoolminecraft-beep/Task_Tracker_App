"""Collection endpoints must never return rows outside the caller's scope
(spec §7.2: "a missing check cannot leak data")."""

from __future__ import annotations


async def test_project_list_is_scoped(as_user):
    hugo = await as_user("Hugo Bauer")  # no roles
    keys = {p["key"] for p in (await hugo.get("/api/v1/projects")).json()}
    assert keys == {"OPS"}, "only the internally-visible project should be listed"

    greta = await as_user("Greta Lang")  # ENG contributor + one MKTG guest share
    keys = {p["key"] for p in (await greta.get("/api/v1/projects")).json()}
    assert keys == {"ENG", "MKTG", "OPS"}
    # MKTG only appears because of the guest share; membership is not implied.


async def test_guest_task_list_returns_only_shared_tasks(as_user, world):
    greta = await as_user("Greta Lang")
    resp = await greta.get(f"/api/v1/projects/{world['mktg_id']}/tasks")
    assert resp.status_code == 200
    ids = [t["id"] for t in resp.json()["items"]]
    assert ids == [world["mktg_shared_task_id"]], "guest saw more than the shared task"


async def test_my_tasks_never_crosses_into_inaccessible_projects(as_user):
    david = await as_user("David Fischer")  # MKTG + OPS only
    mine = (await david.get("/api/v1/me/tasks?limit=200")).json()["items"]
    assert mine, "expected David to have assigned tasks"
    assert all(t["project_key"] in {"MKTG", "OPS"} for t in mine)


async def test_search_is_scoped_to_accessible_projects(as_user):
    david = await as_user("David Fischer")
    elena = await as_user("Elena Popova")  # ENG admin

    # "platform" matches an ENG task; David has no ENG access.
    david_hits = (await david.get("/api/v1/search?q=platform")).json()["items"]
    assert all(h["project_key"] in {"MKTG", "OPS"} for h in david_hits)

    elena_hits = (await elena.get("/api/v1/search?q=platform")).json()["items"]
    assert any(h["project_key"] == "ENG" for h in elena_hits)
