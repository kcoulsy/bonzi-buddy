"""Web features ported from the original: search engines, surf links, share."""

from __future__ import annotations

import urllib.parse
import webbrowser

# name -> query URL prefix (the user's text is appended, URL-encoded).
# Mirrors BonziWORLD.cs's SearchEngine switch.
SEARCH_ENGINES: dict[str, str] = {
    "Google (Default)": "https://www.google.com/search?q=",
    "Bing": "https://www.bing.com/search?q=",
    "DuckDuckGo": "https://duckduckgo.com/?q=",
    "Yahoo": "https://search.yahoo.com/search?p=",
    "Baidu": "https://www.baidu.com/s?wd=",
    "Yandex": "https://yandex.com/search/?text=",
    "AOL": "https://search.aol.com/aol/search?q=",
    "Ecosia": "https://www.ecosia.org/search?method=index&q=",
    "Internet Archive": "https://archive.org/search?query=",
}

DEFAULT_ENGINE = "Google (Default)"

# quick links from the original's toolbar / About box
LINKS: dict[str, str] = {
    "BonziBUDDY home (tmafe)": "https://www.tmafe.com/bonzibuddy",
    "Get more themes": "https://tmafe.com/bonzibuddy/themes",
    "Support": "https://www.tmafe.com/bonzibuddy/support",
    "MS Agent revival": "https://tmafe.com/msagent",
}


def search(query: str, engine: str) -> None:
    prefix = SEARCH_ENGINES.get(engine, SEARCH_ENGINES[DEFAULT_ENGINE])
    webbrowser.open(prefix + urllib.parse.quote_plus(query))


def open_url(url: str) -> None:
    webbrowser.open(url)
