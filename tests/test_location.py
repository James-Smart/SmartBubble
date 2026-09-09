import asyncio

from fastapi.testclient import TestClient

from app.main import app
from app.models import LocationReport
from app.store import SessionStore


def test_set_and_get_location_round_trips_coordinates():
    store = SessionStore()

    async def scenario():
        await store.set_location(
            "alice",
            LocationReport(
                status="granted",
                latitude=51.4816,
                longitude=-2.5885,
                accuracy_m=12,
                label="M32 J2, Bristol",
            ),
        )
        return await store.get_location("alice")

    state = asyncio.run(scenario())
    assert state.status == "granted"
    assert state.latitude == 51.4816
    assert state.longitude == -2.5885
    assert state.accuracy_m == 12
    assert state.label == "M32 J2, Bristol"
    assert state.shared_at is not None


def test_unshared_session_reports_none():
    store = SessionStore()
    state = asyncio.run(store.get_location("nobody"))
    assert state.status == "none"
    assert state.latitude is None
    assert state.shared_at is None


def test_second_share_overwrites_the_first():
    store = SessionStore()

    async def scenario():
        await store.set_location(
            "alice", LocationReport(status="granted", latitude=1.0, longitude=2.0)
        )
        await store.set_location(
            "alice", LocationReport(status="granted", latitude=3.0, longitude=4.0)
        )
        return await store.get_location("alice")

    state = asyncio.run(scenario())
    assert state.latitude == 3.0
    assert state.longitude == 4.0


def test_denied_state_carries_no_coordinates():
    store = SessionStore()

    async def scenario():
        # A client could send coordinates alongside a denial; they must be dropped.
        await store.set_location(
            "alice", LocationReport(status="denied", latitude=1.0, longitude=2.0)
        )
        return await store.get_location("alice")

    state = asyncio.run(scenario())
    assert state.status == "denied"
    assert state.latitude is None
    assert state.longitude is None
    assert state.shared_at is not None


def test_clear_resets_location():
    store = SessionStore()

    async def scenario():
        await store.set_location(
            "alice", LocationReport(status="granted", latitude=1.0, longitude=2.0)
        )
        await store.clear("alice")
        return await store.get_location("alice")

    assert asyncio.run(scenario()).status == "none"


def test_sessions_have_independent_locations():
    store = SessionStore()

    async def scenario():
        await store.set_location(
            "alice", LocationReport(status="granted", latitude=1.0, longitude=2.0)
        )
        return await store.get_location("bob")

    assert asyncio.run(scenario()).status == "none"


def test_location_endpoint_reports_none_before_any_share():
    client = TestClient(app)
    resp = client.get("/api/sessions/loc-fresh/location")
    assert resp.status_code == 200
    # `none` is exactly one key — nothing for a poller to unpack by mistake.
    assert resp.json() == {"status": "none"}


def test_granted_report_is_readable_from_the_api():
    client = TestClient(app)
    session = "loc-granted"

    post = client.post(
        f"/{session}/location",
        json={
            "status": "granted",
            "latitude": 51.4816,
            "longitude": -2.5885,
            "accuracy_m": 12,
            "label": "M32 J2, Bristol",
        },
    )
    assert post.status_code == 200

    body = client.get(f"/api/sessions/{session}/location").json()
    assert body["status"] == "granted"
    assert body["latitude"] == 51.4816
    assert body["longitude"] == -2.5885
    assert body["accuracy_m"] == 12
    assert body["label"] == "M32 J2, Bristol"
    assert "shared_at" in body


def test_denied_report_is_readable_and_has_no_coordinates():
    client = TestClient(app)
    session = "loc-denied"

    client.post(f"/{session}/location", json={"status": "denied"})

    body = client.get(f"/api/sessions/{session}/location").json()
    assert body["status"] == "denied"
    assert "latitude" not in body
    assert "longitude" not in body
    assert "accuracy_m" not in body
    assert "label" not in body
    assert "shared_at" in body


def test_clear_endpoint_resets_the_shared_location():
    client = TestClient(app)
    session = "loc-cleared"

    client.post(
        f"/{session}/location",
        json={"status": "granted", "latitude": 1.0, "longitude": 2.0},
    )
    client.post(f"/{session}/clear")

    assert client.get(f"/api/sessions/{session}/location").json() == {"status": "none"}


def test_out_of_range_coordinates_are_rejected():
    client = TestClient(app)

    too_far_north = client.post(
        "/loc-invalid/location",
        json={"status": "granted", "latitude": 91.0, "longitude": 0.0},
    )
    too_far_east = client.post(
        "/loc-invalid/location",
        json={"status": "granted", "latitude": 0.0, "longitude": 181.0},
    )
    negative_accuracy = client.post(
        "/loc-invalid/location",
        json={
            "status": "granted",
            "latitude": 51.4816,
            "longitude": -2.5885,
            "accuracy_m": -1,
        },
    )

    assert too_far_north.status_code == 422
    assert too_far_east.status_code == 422
    assert negative_accuracy.status_code == 422


def test_shared_location_never_appears_in_the_replies_stream():
    client = TestClient(app)
    session = "loc-replies"

    # Put a real message in the session so the assertion below can't pass
    # vacuously against an empty stream.
    reply = client.post(f"/{session}/reply", data={"body": "On my way"})
    assert reply.status_code == 200

    post = client.post(
        f"/{session}/location",
        json={
            "status": "granted",
            "latitude": 51.4816,
            "longitude": -2.5885,
            "accuracy_m": 12,
            "label": "M32 J2, Bristol",
        },
    )
    assert post.status_code == 200

    body = client.get(f"/api/sessions/{session}/replies?since=0").json()
    assert len(body["messages"]) == 1
    assert body["messages"][0]["body"] == "On my way"
    for message in body["messages"]:
        assert "latitude" not in message
        assert "longitude" not in message
        assert "M32 J2, Bristol" not in message["body"]
