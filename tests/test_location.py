import asyncio

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
