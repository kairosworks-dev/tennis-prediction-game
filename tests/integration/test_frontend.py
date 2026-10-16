"""The frontend is served, not only the API, over plain HTTP against the stack.

Every request goes to the app root (`APP_URL`), not the `/api` base URL, with
redirects not followed. The tests read and write nothing: the only sign-in is
the one the `running_game` fixture needs to discover a game id by state. They
assert on `id="root"` and on what the page itself references, never on the
product name, the title or asset file names.
"""

from __future__ import annotations

import uuid
from html.parser import HTMLParser

import httpx
import pytest

SHELL_MARKER = 'id="root"'


class _Assets(HTMLParser):
    """Collect the `/assets/` URLs a page references, by kind."""

    def __init__(self) -> None:
        super().__init__()
        self.scripts: list[str] = []
        self.stylesheets: list[str] = []
        self.other: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "script":
            url = values.get("src")
            if url and url.startswith("/assets/"):
                self.scripts.append(url)
        elif tag == "link":
            url = values.get("href")
            if url and url.startswith("/assets/"):
                if "stylesheet" in (values.get("rel") or "").split():
                    self.stylesheets.append(url)
                else:
                    self.other.append(url)


@pytest.fixture(scope="module")
def root(app_url: str):
    with httpx.Client(base_url=app_url, timeout=30, follow_redirects=False) as client:
        yield client


@pytest.fixture(scope="module")
def index(root: httpx.Client) -> httpx.Response:
    return root.get("/")


def _is_html(response: httpx.Response) -> bool:
    return response.headers.get("content-type", "").startswith("text/html")


def test_index_is_the_app_shell(index: httpx.Response) -> None:
    assert index.status_code == 200
    assert _is_html(index), index.headers.get("content-type")
    assert SHELL_MARKER in index.text


def test_assets_referenced_by_the_page_are_served(
    root: httpx.Client, index: httpx.Response
) -> None:
    page = _Assets()
    page.feed(index.text)
    referenced = page.scripts + page.stylesheets + page.other
    assert referenced, "the page references no /assets/ URL (script src or link href)"

    for url in referenced:
        response = root.get(url)
        assert response.status_code == 200, url
        assert response.content, f"{url} answered with an empty body"

    for url in page.scripts:
        assert "javascript" in root.get(url).headers.get("content-type", ""), url
    for url in page.stylesheets:
        assert "css" in root.get(url).headers.get("content-type", ""), url


@pytest.mark.parametrize("suffix", ["sign-in", "games/{id}", "admin/{id}/results"])
def test_deep_link_serves_the_same_shell(
    root: httpx.Client, index: httpx.Response, running_game: dict, suffix: str
) -> None:
    response = root.get("/" + suffix.format(id=running_game["tournament"]["id"]))
    assert response.status_code == 200
    assert _is_html(response), response.headers.get("content-type")
    assert response.content == index.content


@pytest.mark.parametrize("path", ["/no-such-page", "/no/such/page"])
def test_unknown_client_route_serves_the_same_shell(
    root: httpx.Client, index: httpx.Response, path: str
) -> None:
    response = root.get(path)
    assert response.status_code == 200
    assert response.content == index.content


def test_head_on_a_deep_link(root: httpx.Client, running_game: dict) -> None:
    response = root.head(f"/games/{running_game['tournament']['id']}")
    assert response.status_code == 200
    assert _is_html(response), response.headers.get("content-type")


def test_missing_asset_is_a_404_not_the_shell(root: httpx.Client) -> None:
    response = root.get(f"/assets/does-not-exist-{uuid.uuid4().hex}.js")
    assert response.status_code == 404
    assert SHELL_MARKER not in response.text


def test_unknown_api_path_is_json_not_html(root: httpx.Client) -> None:
    response = root.get(f"/api/no-such-route-{uuid.uuid4().hex}")
    content_type = response.headers.get("content-type", "")
    assert response.status_code == 404
    assert "json" in content_type
    assert not content_type.startswith("text/html")


def test_wrong_method_on_an_api_path_is_405_not_the_shell(root: httpx.Client) -> None:
    response = root.get("/api/auth/login")
    assert response.status_code == 405
    assert "POST" in response.headers.get("allow", "")
    assert not _is_html(response)
