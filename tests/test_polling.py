from fastapi.testclient import TestClient

from app.main import app


def test_page_declares_the_message_list_exactly_once():
    """A duplicated #messages container gives two htmx pollers racing to swap
    the same region, which destroys clicks landing on links inside it."""
    client = TestClient(app)

    page = client.get("/poll-shape").text

    assert page.count('id="messages"') == 1


def test_polled_fragment_does_not_rearm_its_load_trigger():
    """The fragment replaces itself via outerHTML. htmx fires `load` on content
    it swaps in, so a `load` trigger here re-triggers the fetch immediately and
    the list churns continuously instead of every 1.5s."""
    client = TestClient(app)

    fragment = client.get("/poll-shape/stream").text

    assert "every 1.5s" in fragment
    assert "load" not in fragment.split(">")[0]
