"""
Web-fetch tool for the Discovery & Vetting Agent.

Kept separate from tools.py because it's the one tool that reaches
outside resources.db onto the open web — used both to re-check existing
resources' source_url for staleness and to read known hub/directory
pages (e.g. 211 Tampa Bay, hcfl.gov resource listings) for new
candidates.
"""

import re

import requests
from bs4 import BeautifulSoup
from strands import tool

USER_AGENT = (
    "Mozilla/5.0 (compatible; MacknificientWorldResourceNavigator/1.0; "
    "+https://mackworldinc.org)"
)
TIMEOUT_SECONDS = 10


@tool
def fetch_url(url: str, max_chars: int = 4000) -> dict:
    """Fetch a web page and return its status and visible text.

    Use this to (a) re-check whether an existing resource's source_url
    still resolves and whether its content still matches what's stored
    (look for phrases like "discontinued", "closed", "no longer
    available"), or (b) read a known hub/directory page to find new
    resource candidates.

    Args:
        url: the page to fetch.
        max_chars: truncate the extracted text to this many characters
            (default 4000) to keep results manageable.

    Returns:
        dict with: ok (bool), status_code (int or None), final_url (str,
        after redirects), text (str, visible page text, truncated), and
        error (str, present only on failure).
    """
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT_SECONDS,
            allow_redirects=True,
        )
    except requests.RequestException as e:
        return {"ok": False, "status_code": None, "final_url": url, "text": "", "error": str(e)}

    text = ""
    content_type = resp.headers.get("Content-Type", "")
    if "html" in content_type or resp.text.strip().startswith("<"):
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        text = re.sub(r"\n\s*\n+", "\n", soup.get_text("\n", strip=True))
    else:
        text = resp.text

    return {
        "ok": resp.ok,
        "status_code": resp.status_code,
        "final_url": resp.url,
        "text": text[:max_chars],
    }
