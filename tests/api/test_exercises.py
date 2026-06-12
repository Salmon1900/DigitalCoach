"""API test for /api/v1/exercises (uses the real analyzer registry)."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_exercises_lists_name_slug_type():
    resp = client.get("/api/v1/exercises")
    assert resp.status_code == 200
    rows = resp.json()["exercises"]
    assert rows  # non-empty
    for row in rows:
        assert set(row) == {"name", "slug", "type"}
        assert row["type"] in {"reps", "timed"}
    by_slug = {r["slug"]: r for r in rows}
    assert by_slug["handstand"]["type"] == "timed"
    assert by_slug["push_up"]["type"] == "reps"


def test_exercises_response_has_schema_in_openapi():
    schema = client.get("/openapi.json").json()
    # The /exercises route should reference a named component schema, not an inline bare object.
    get_op = schema["paths"]["/api/v1/exercises"]["get"]
    content = get_op["responses"]["200"]["content"]["application/json"]["schema"]
    assert "$ref" in content  # a concrete Pydantic model, not an untyped object
