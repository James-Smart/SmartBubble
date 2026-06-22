import asyncio

from fastapi.testclient import TestClient

from app.main import app
from app.store import SessionStore


def test_clear_empties_messages_and_preserves_next_id():
    store = SessionStore()

    async def scenario():
        await store.add_to_phone("alice", "first", None)
        await store.add_to_phone("alice", "second", None)
        await store.clear("alice")
        remaining = await store.list_all("alice")
        # next_id stays monotonic: the next message keeps counting up, not 1
        after = await store.add_to_phone("alice", "third", None)
        return remaining, after

    remaining, after = asyncio.run(scenario())
    assert remaining == []
    assert after.id == 3


def test_clear_endpoint_empties_conversation():
    client = TestClient(app)
    session = "clear-endpoint-demo"

    client.post(f"/api/sessions/{session}/messages", json={"body": "hello"})

    resp = client.post(f"/{session}/clear")
    assert resp.status_code == 200
    assert "hello" not in resp.text

    page = client.get(f"/{session}")
    assert "hello" not in page.text
