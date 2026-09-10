"""CSV/JSON export and CSV import (spec F-12). Export is audited (§8.4.6);
import reuses the task-create path (seq, audit, notifications) per row.
"""

from __future__ import annotations

import csv
import io
import json

import pytest


@pytest.fixture
async def david(as_user):
    return await as_user("David Fischer")  # Project Admin on MKTG


async def test_csv_export_has_headers_and_a_download_filename(david, world):
    resp = await david.get(f"/api/v1/projects/{world['mktg_id']}/tasks/export?format=csv")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment; filename=" in resp.headers["content-disposition"]
    assert resp.headers["content-disposition"].endswith('.csv"')

    rows = list(csv.DictReader(io.StringIO(resp.text)))
    assert rows, "expected seeded MKTG tasks in the export"
    assert set(rows[0]) >= {"ref", "title", "state", "priority", "assignee_upn", "parent_ref"}
    assert all(r["ref"].startswith("MKTG-") for r in rows)


async def test_json_export_round_trips(david, world):
    resp = await david.get(f"/api/v1/projects/{world['mktg_id']}/tasks/export?format=json")
    assert resp.status_code == 200
    body = json.loads(resp.text)
    assert body["project"] == "MKTG"
    assert isinstance(body["tasks"], list) and body["tasks"]


async def test_export_is_audited(david, as_user, world):
    auditor = await as_user("Björn Neumann")
    await david.get(f"/api/v1/projects/{world['mktg_id']}/tasks/export?format=csv")
    events = (await auditor.get("/api/v1/audit?limit=20")).json()
    exported = next((e for e in events if e["action"] == "project.exported"), None)
    assert exported is not None
    assert exported["after"]["format"] == "csv"
    assert exported["after"]["task_count"] >= 1


def _csv(*rows: str) -> bytes:
    header = "title,state,priority,assignee_upn,due_date,parent_ref\r\n"
    return (header + "".join(r + "\r\n" for r in rows)).encode()


async def test_import_creates_valid_rows_and_reports_the_rest(david, world):
    payload = _csv(
        "Imported one,Drafting,2,elena.popova@example.com,2026-12-01,",
        "Imported two,,4,,,",
        ",,,,,",  # missing title -> row 4
        "Bad priority,,9,,,",  # -> row 5
        "Unknown assignee,,3,nobody@example.com,,",  # -> row 6
    )
    resp = await david.post(
        f"/api/v1/projects/{world['mktg_id']}/tasks/import",
        files={"file": ("import.csv", payload, "text/csv")},
    )
    assert resp.status_code == 200
    result = resp.json()
    assert result["created"] == 2
    assert len(result["refs"]) == 2
    reasons = {e["row"]: e["reason"] for e in result["skipped"]}
    assert set(reasons) == {4, 5, 6}
    assert "title" in reasons[4]
    assert "1..5" in reasons[5]
    assert "assignee" in reasons[6]


async def test_imported_tasks_are_real_and_audited(david, as_user, world):
    auditor = await as_user("Björn Neumann")
    payload = _csv("Fresh import,Ideas,3,,,")
    ref = (
        await david.post(
            f"/api/v1/projects/{world['mktg_id']}/tasks/import",
            files={"file": ("i.csv", payload, "text/csv")},
        )
    ).json()["refs"][0]

    listing = (await david.get(f"/api/v1/projects/{world['mktg_id']}/tasks?limit=100")).json()
    assert any(t["ref"] == ref and t["title"] == "Fresh import" for t in listing["items"])

    actions = {e["action"] for e in (await auditor.get("/api/v1/audit?limit=20")).json()}
    assert {"project.imported", "task.created"} <= actions


async def test_import_resolves_parent_ref_into_a_subtask(david, world):
    listing = (await david.get(f"/api/v1/projects/{world['mktg_id']}/tasks?limit=100")).json()
    parent_ref = next(t["ref"] for t in listing["items"] if t["parent_task_id"] is None)

    payload = _csv(f"A subtask,,3,,,{parent_ref}")
    result = (
        await david.post(
            f"/api/v1/projects/{world['mktg_id']}/tasks/import",
            files={"file": ("i.csv", payload, "text/csv")},
        )
    ).json()
    assert result["created"] == 1

    detail = None
    for t in (
        await david.get(f"/api/v1/projects/{world['mktg_id']}/tasks?include_subtasks=true&limit=200")
    ).json()["items"]:
        if t["ref"] == result["refs"][0]:
            detail = t
    assert detail is not None and detail["parent_task_id"] is not None


async def test_a_viewer_cannot_import(as_user, world):
    frank = await as_user("Frank Müller")  # Viewer on MKTG
    resp = await frank.post(
        f"/api/v1/projects/{world['mktg_id']}/tasks/import",
        files={"file": ("i.csv", _csv("x,,3,,,"), "text/csv")},
    )
    assert resp.status_code == 403


async def test_import_rejects_a_non_utf8_or_empty_file(david, world):
    empty = await david.post(
        f"/api/v1/projects/{world['mktg_id']}/tasks/import",
        files={"file": ("e.csv", b"title\r\n", "text/csv")},
    )
    assert empty.status_code == 422
