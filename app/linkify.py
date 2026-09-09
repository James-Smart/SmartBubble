import re

from markupsafe import Markup, escape

# Deliberately permissive: the URLs in a demo are fake, so the only job here is
# to find something that looks like a link and stop before whitespace or markup.
_URL_RE = re.compile(r'https?://[^\s<>"]+')

# Sentence punctuation that a URL at the end of a sentence should not swallow.
_TRAILING = ".,;:!?)]}'\""


def linkify(text: str) -> Markup:
    """Escape a message body and wrap any http(s) URLs in tappable anchors.

    Runs server side because HTMX swaps the whole message list every 1.5s;
    anything the client decorated would be wiped by the next poll.
    """
    parts: list[str] = []
    position = 0

    for match in _URL_RE.finditer(text):
        url = match.group(0)
        trailing = ""
        while url and url[-1] in _TRAILING:
            trailing = url[-1] + trailing
            url = url[:-1]

        parts.append(str(escape(text[position : match.start()])))
        if url:
            safe = escape(url)
            parts.append(f'<a class="sms-link" href="#" data-url="{safe}">{safe}</a>')
        parts.append(str(escape(trailing)))
        position = match.end()

    parts.append(str(escape(text[position:])))
    return Markup("".join(parts))
