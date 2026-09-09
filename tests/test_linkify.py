from fastapi.testclient import TestClient

from app.linkify import linkify
from app.main import app


def test_plain_text_passes_through_unchanged():
    assert str(linkify("Your patrol is on the way")) == "Your patrol is on the way"


def test_html_in_the_body_is_escaped():
    # Message bodies come straight from the API; they must never inject markup.
    assert "<script>" not in str(linkify("<script>alert(1)</script>"))
    assert "&lt;script&gt;" in str(linkify("<script>alert(1)</script>"))


def test_url_becomes_an_anchor_carrying_the_raw_url():
    result = str(linkify("Tap https://aa-assist.co.uk/loc/x7k2 now"))
    assert 'class="sms-link"' in result
    assert 'data-url="https://aa-assist.co.uk/loc/x7k2"' in result
    assert result.startswith("Tap ")
    assert result.endswith(" now")


def test_trailing_punctuation_stays_outside_the_anchor():
    result = str(linkify("Go to https://aa-assist.co.uk/loc/x7k2."))
    assert 'data-url="https://aa-assist.co.uk/loc/x7k2"' in result
    assert result.endswith("</a>.")


def test_multiple_urls_are_all_linked():
    result = str(linkify("http://a.example/1 and https://b.example/2"))
    assert result.count('class="sms-link"') == 2


def test_quotes_in_a_url_cannot_break_out_of_the_attribute():
    result = str(linkify('https://evil.example/"onmouseover="x'))
    # The quote ends the URL match, and both quotes come back escaped, so no
    # attribute can be closed early.
    assert 'onmouseover="' not in result
    assert "&#34;" in result


def test_message_page_renders_a_url_as_a_tappable_link():
    client = TestClient(app)
    session = "linkify-page"

    client.post(
        f"/api/sessions/{session}/messages",
        json={"body": "AA Assist: https://aa-assist.co.uk/loc/x7k2", "from": "AA"},
    )

    page = client.get(f"/{session}")
    assert 'class="sms-link"' in page.text
    assert 'data-url="https://aa-assist.co.uk/loc/x7k2"' in page.text
