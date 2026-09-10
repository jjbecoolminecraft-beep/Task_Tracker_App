"""The log-redaction filter (spec §7.4, §12): a test that fails if it is bypassed.

    "No personal data in logs. Enforced by a redaction filter with a test that
     fails if the filter is bypassed."
"""

from __future__ import annotations

from app.core.logging import redact_personal_data


def _redact(event: dict) -> dict:
    return redact_personal_data(None, "info", event)


def test_direct_identifier_keys_are_removed():
    out = _redact(
        {
            "event": "user_provisioned",
            "email": "alice@corp.example",
            "display_name": "Alice Example",
            "upn": "alice@corp.example",
            "user_id": "1c3f…",  # an opaque id is fine to keep
        }
    )
    assert out["email"] == "«redacted»"
    assert out["display_name"] == "«redacted»"
    assert out["upn"] == "«redacted»"
    assert out["user_id"] == "1c3f…"
    assert out["event"] == "user_provisioned"


def test_free_text_content_keys_are_removed():
    out = _redact({"title": "Fire Bob", "description": "sensitive note", "comment": "hi"})
    assert set(out.values()) == {"«redacted»"}


def test_emails_are_scrubbed_from_free_string_values():
    out = _redact({"reason": "requested by alice@corp.example on behalf of bob@corp.example"})
    assert "@corp.example" not in out["reason"]
    assert out["reason"].count("«redacted»") == 2


def test_nested_structures_are_scrubbed():
    out = _redact(
        {
            "payload": {
                "actor_id": "keep-me",
                "email": "x@y.z",
                "notes": ["ping a@b.co", {"display_name": "Deep Name"}],
            }
        }
    )
    assert out["payload"]["actor_id"] == "keep-me"
    assert out["payload"]["email"] == "«redacted»"
    assert "@b.co" not in out["payload"]["notes"][0]
    assert out["payload"]["notes"][1]["display_name"] == "«redacted»"


def test_authorization_header_and_token_are_redacted():
    out = _redact({"authorization": "Bearer abc.def.ghi", "token": "secret"})
    assert out["authorization"] == "«redacted»"
    assert out["token"] == "«redacted»"
