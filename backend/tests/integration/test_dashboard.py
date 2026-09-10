"""Project dashboard (spec F-22): aggregated only, gated on PROJECT_READ, and it
never exposes a per-person breakdown (spec §8.4.1).
"""

from __future__ import annotations

import pytest


@pytest.fixture
async def david(as_user):
    return await as_user("David Fischer")  # Project Admin on MKTG


async def test_dashboard_shape_and_totals(david, world):
    resp = await david.get(f"/api/v1/projects/{world['mktg_id']}/dashboard")
    assert resp.status_code == 200
    d = resp.json()

    assert d["total"] == d["open"] + d["done"]
    assert d["by_state"] and sum(b["count"] for b in d["by_state"]) == d["total"]
    assert [b["priority"] for b in d["by_priority"]] == [1, 2, 3, 4, 5]
    assert len(d["throughput"]) == 8
    assert all("W" in w["week"] for w in d["throughput"])
    assert d["overdue"] >= 1  # the seed has an overdue MKTG task
    assert isinstance(d["contributor_count"], int)


async def test_dashboard_never_carries_a_per_person_breakdown(david, world):
    d = (await david.get(f"/api/v1/projects/{world['mktg_id']}/dashboard")).json()
    blob = str(d).lower()
    # a headcount is fine; a by-assignee list/map is not
    assert "assignee" not in blob
    assert "by_user" not in blob and "per_person" not in blob


async def test_dashboard_requires_project_read(as_user, world):
    hugo = await as_user("Hugo Bauer")  # no access to MKTG
    assert (await hugo.get(f"/api/v1/projects/{world['mktg_id']}/dashboard")).status_code == 403

    frank = await as_user("Frank Müller")  # Viewer — read is enough
    assert (await frank.get(f"/api/v1/projects/{world['mktg_id']}/dashboard")).status_code == 200


async def test_throughput_counts_completions_in_the_right_week(david, world):
    d = (await david.get(f"/api/v1/projects/{world['mktg_id']}/dashboard")).json()
    total_completed = sum(w["completed"] for w in d["throughput"])
    # the seed backdates several MKTG completions into the window
    assert total_completed >= 3
