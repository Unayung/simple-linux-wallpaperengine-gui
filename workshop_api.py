"""Steam Workshop API client for browsing and searching Wallpaper Engine items."""

import json
import urllib.request
import urllib.parse
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional


WALLPAPER_ENGINE_APP_ID = 431960


@dataclass
class WorkshopItem:
    id: str
    title: str
    preview_url: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    subscriptions: int = 0
    file_size: int = 0
    description: Optional[str] = None


class SortOrder(IntEnum):
    TRENDING = 0
    MOST_RECENT = 1
    MOST_POPULAR = 2
    MOST_SUBSCRIBED = 3

    @property
    def display_name(self) -> str:
        return {
            SortOrder.TRENDING: "Trending",
            SortOrder.MOST_RECENT: "Most Recent",
            SortOrder.MOST_POPULAR: "Most Popular",
            SortOrder.MOST_SUBSCRIBED: "Most Subscribed",
        }[self]

    @property
    def query_type(self) -> int:
        return {
            SortOrder.TRENDING: 3,        # RankedByTrend
            SortOrder.MOST_RECENT: 1,      # RankedByPublicationDate
            SortOrder.MOST_POPULAR: 0,     # RankedByVote
            SortOrder.MOST_SUBSCRIBED: 9,  # RankedByTotalUniqueSubscriptions
        }[self]

    def query_type_for_search(self, has_text: bool) -> int:
        return 12 if has_text else self.query_type  # 12 = RankedByTextSearch


CONTENT_RATING_TAGS = ["Everyone", "Questionable", "Mature"]
TYPE_TAGS = ["Scene", "Video", "Web", "Application"]
GENRE_TAGS = [
    "Abstract", "Animal", "Anime", "Cartoon", "CGI",
    "Cyberpunk", "Fantasy", "Game", "Girls", "Guys",
    "Landscape", "Medieval", "Memes", "MMD", "Music",
    "Nature", "Pixel Art", "Relaxing", "Retro", "Sci-Fi",
    "Sports", "Technology", "Television", "Vehicle",
]


class WorkshopAPIError(Exception):
    pass


class NoAPIKeyError(WorkshopAPIError):
    pass


class InvalidAPIKeyError(WorkshopAPIError):
    pass


def search_items(
    api_key: str,
    query: str = "",
    tags: list[str] | None = None,
    sort_order: SortOrder = SortOrder.TRENDING,
    page: int = 1,
    per_page: int = 20,
) -> list[WorkshopItem]:
    """Search workshop items using the Steam Web API."""
    if not api_key:
        raise NoAPIKeyError("Steam Web API key required. Get one at steamcommunity.com/dev/apikey")

    tags = tags or []
    has_text = bool(query)

    params = {
        "query_type": str(sort_order.query_type_for_search(has_text)),
        "page": str(page),
        "numperpage": str(per_page),
        "appid": str(WALLPAPER_ENGINE_APP_ID),
        "return_tags": "true",
        "return_previews": "true",
        "return_metadata": "true",
        "return_short_description": "true",
        "key": api_key,
    }

    if query:
        params["search_text"] = query

    for i, tag in enumerate(tags):
        params[f"requiredtags[{i}]"] = tag

    url = "https://api.steampowered.com/IPublishedFileService/QueryFiles/v1/?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 403:
                raise InvalidAPIKeyError("Invalid API key")
            if resp.status != 200:
                raise WorkshopAPIError(f"Steam API returned HTTP {resp.status}")
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 403:
            raise InvalidAPIKeyError("Invalid API key. Get a valid key at steamcommunity.com/dev/apikey")
        raise WorkshopAPIError(f"Steam API returned HTTP {e.code}")
    except urllib.error.URLError as e:
        raise WorkshopAPIError(f"Network error: {e.reason}")

    return _parse_query_response(data)


def get_item_details(workshop_ids: list[str]) -> list[WorkshopItem]:
    """Get details for specific workshop items by ID (no API key needed)."""
    url = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"

    body_parts = [f"itemcount={len(workshop_ids)}"]
    for i, wid in enumerate(workshop_ids):
        body_parts.append(f"publishedfileids[{i}]={wid}")

    body = "&".join(body_parts).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status != 200:
                raise WorkshopAPIError(f"API request failed with HTTP {resp.status}")
            data = json.loads(resp.read())
    except urllib.error.URLError as e:
        raise WorkshopAPIError(f"Network error: {e.reason}")

    return _parse_query_response(data)


def _parse_query_response(data: dict) -> list[WorkshopItem]:
    response = data.get("response", {})
    files = response.get("publishedfiledetails", [])
    items = []
    for f in files:
        pid = f.get("publishedfileid")
        title = f.get("title")
        if not pid or not title:
            continue
        tags_list = [t["tag"] for t in f.get("tags", []) if "tag" in t]
        items.append(WorkshopItem(
            id=pid,
            title=title,
            preview_url=f.get("preview_url"),
            tags=tags_list,
            subscriptions=f.get("subscriptions", 0) or f.get("lifetime_subscriptions", 0),
            file_size=f.get("file_size", 0),
            description=f.get("short_description") or f.get("description"),
        ))
    return items
