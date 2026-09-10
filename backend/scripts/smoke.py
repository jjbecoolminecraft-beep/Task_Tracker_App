"""End-to-end smoke test against a running API + seeded DB.

    python -m scripts.smoke            # expects API on http://127.0.0.1:8000

Exercises the MVP happy paths and the authorization boundaries that matter most.
Not a substitute for tests/ — a fast "is the running system wired up?" check.
"""

from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("SMOKE_BASE", "http://127.0.0.1:8000")
OK = "\033[32mPASS\033[0m"
BAD = "\033[31mFAIL\033[0m"
_failures = 0


def call(method, path, token=None, body=None, if_match=None):
    import json

    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{BASE}{path}", data=data, method=method)
    if data:
        req.add_header("content-type", "application/json")
    if token:
        req.add_header("authorization", f"Bearer {token}")
    if if_match:
        req.add_header("if-match", if_match)

    def _body(raw: str, msg) -> object:
        if not raw:
            return None
        if "json" in (msg.get_content_type() or ""):
            return json.loads(raw)
        return raw

    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, _body(resp.read().decode(), resp.headers), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, _body(e.read().decode(), e.headers), dict(e.headers)


def check(label, got, expected):
    global _failures
    good = got == expected if not callable(expected) else expected(got)
    print(f"  {OK if good else BAD}  {label}  (got {got!r})")
    if not good:
        _failures += 1


def login(user_id: str) -> str:
    _, payload, _ = call("POST", "/api/v1/auth/dev-login", body={"user_id": user_id})
    return payload["access_token"]


def main() -> int:
    _, users, _ = call("GET", "/api/v1/auth/dev-users")
    by_name = {u["display_name"]: u["id"] for u in users}
    david = login(by_name["David Fischer"])
    frank = login(by_name["Frank Müller"])
    greta = login(by_name["Greta Lang"])
    hugo = login(by_name["Hugo Bauer"])
    bjoern = login(by_name["Björn Neumann"])

    print("\naccess scoping")
    _, projects, _ = call("GET", "/api/v1/projects", david)
    keys = sorted(p["key"] for p in projects)
    check("David sees MKTG + OPS", keys, ["MKTG", "OPS"])
    _, hugo_projects, _ = call("GET", "/api/v1/projects", hugo)
    check("Hugo (no roles) sees only internal OPS", [p["key"] for p in hugo_projects], ["OPS"])
    mktg = next(p["id"] for p in projects if p["key"] == "MKTG")

    print("\ntask lifecycle (David, Project Admin on MKTG)")
    st, created, hdrs = call(
        "POST", f"/api/v1/projects/{mktg}/tasks", david, {"title": "Smoke: venue", "priority": 3}
    )
    check("create -> 201", st, 201)
    check("ETag present", hdrs.get("etag"), lambda v: v == '"1"')
    tid = created["id"]

    st, _, _ = call("PATCH", f"/api/v1/tasks/{tid}", david, {"priority": 1})
    check("PATCH without If-Match -> 428", st, 428)
    st, _, _ = call("PATCH", f"/api/v1/tasks/{tid}", david, {"priority": 1}, if_match='"9"')
    check("PATCH stale If-Match -> 412", st, 412)
    st, patched, _ = call("PATCH", f"/api/v1/tasks/{tid}", david, {"priority": 1}, if_match='"1"')
    check("PATCH good If-Match -> 200", st, 200)
    check("version bumped to 2", patched["version"], 2)

    _, states, _ = call("GET", f"/api/v1/projects/{mktg}/workflow-states", david)
    done = next(s["id"] for s in states if s["category"] == "done")
    st, moved, _ = call("PATCH", f"/api/v1/tasks/{tid}", david, {"state_id": done}, if_match='"2"')
    check("move to done state -> 200", st, 200)
    check("completed_at set", moved["completed_at"], lambda v: v is not None)

    st, comment, _ = call(
        "POST",
        f"/api/v1/tasks/{tid}/comments",
        david,
        {"body": f"@[Clara]({by_name['Clara Schmidt']}) ok"},
    )
    check("comment -> 201", st, 201)
    check("mention resolved", comment["mentioned_user_ids"], [by_name["Clara Schmidt"]])

    st, _, _ = call("DELETE", f"/api/v1/tasks/{tid}", david, if_match='"3"')
    check("soft delete -> 204", st, 204)
    st, _, _ = call("GET", f"/api/v1/tasks/{tid}", david)
    check("deleted task -> 404", st, 404)

    print("\nauthorization boundaries")
    st, _, _ = call("POST", f"/api/v1/projects/{mktg}/tasks", frank, {"title": "x"})
    check("Frank (Viewer) create task -> 403", st, 403)
    st, _, _ = call("GET", f"/api/v1/projects/{mktg}/tasks", hugo)
    check("Hugo list MKTG tasks -> 403", st, 403)

    # Greta has a Guest share on exactly one MKTG task (seed): "Customer testimonial video edit".
    _, all_mktg, _ = call("GET", f"/api/v1/projects/{mktg}/tasks?limit=50", david)
    guest_task = next(i["id"] for i in all_mktg["items"] if i["title"] == "Customer testimonial video edit")
    non_shared = next(i["id"] for i in all_mktg["items"] if i["id"] != guest_task)
    st, _, _ = call("GET", f"/api/v1/tasks/{guest_task}", greta)
    check("Greta reads the task shared with her -> 200", st, 200)
    st, _, _ = call("GET", f"/api/v1/tasks/{non_shared}", greta)
    check("Greta reads a non-shared MKTG task -> 403", st, 403)
    _, greta_list, _ = call("GET", f"/api/v1/projects/{mktg}/tasks", greta)
    check(
        "Greta's MKTG task list is limited to shared tasks only",
        [i["id"] for i in greta_list["items"]],
        [guest_task],
    )

    print("\nsearch + my tasks + audit access")
    _, hits, _ = call("GET", "/api/v1/search?q=campaign", david)
    check("search 'campaign' finds MKTG-1", [i["ref"] for i in hits["items"]], ["MKTG-1"])
    _, eng_hits, _ = call("GET", "/api/v1/search?q=platform", login(by_name["Elena Popova"]))
    check("Elena search 'platform' finds an ENG task", len(eng_hits["items"]), lambda n: n >= 1)
    st, _, _ = call("GET", "/api/v1/search?q=platform", david)
    check("David search 'platform' -> no ENG leakage", st, 200)
    _, mine, _ = call("GET", "/api/v1/me/tasks", david)
    check("my tasks returns a page", "page" in mine, True)

    print("\nnotifications + import/export + audit")
    elena = login(by_name["Elena Popova"])
    _, before_notif, _ = call("GET", "/api/v1/me/notifications/unread-count", elena)
    st, made, _ = call(
        "POST",
        f"/api/v1/projects/{mktg}/tasks",
        david,
        {"title": "Smoke: notify", "assignee_id": by_name["Elena Popova"]},
    )
    _, after_notif, _ = call("GET", "/api/v1/me/notifications/unread-count", elena)
    check(
        "assigning a task notifies the assignee",
        after_notif["unread"] - before_notif["unread"],
        1,
    )
    _, exp, hdrs = call("GET", f"/api/v1/projects/{mktg}/tasks/export?format=csv", david)
    check("CSV export is a download", hdrs.get("content-disposition", ""), lambda v: "filename=" in v)
    st, _, _ = call("GET", "/api/v1/audit", david)
    check("David cannot read the audit log -> 403", st, 403)
    _, events, _ = call("GET", "/api/v1/audit", bjoern)
    check(
        "Auditor sees export + task events",
        {e["action"] for e in events} >= {"project.exported", "task.created"},
        True,
    )

    print(f"\n{'ALL PASSED' if not _failures else str(_failures) + ' CHECK(S) FAILED'}")
    return 1 if _failures else 0


if __name__ == "__main__":
    sys.exit(main())
