"""Verified RedGIFs routes and pure metadata extraction."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from urllib.parse import unquote, urlsplit

from selectolax.lexbor import LexborHTMLParser
from base_api import NotFound

BASE_URL = "https://www.redgifs.com"
API_URL = "https://api.redgifs.com"
PAGE_HOSTS = frozenset({"redgifs.com", "www.redgifs.com"})
MEDIA_HOSTS = frozenset({"media.redgifs.com"})


def identifier(value: str, kind: str = "watch") -> str:
    """Accept IDs or verified first-party URLs, never lookalike domains."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("A nonempty RedGIFs ID or URL is required")
    value = value.strip()
    if "://" in value:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password or parsed.port not in {None, 80, 443}:
            raise ValueError("Invalid RedGIFs URL")
        parts = [unquote(p) for p in parsed.path.strip('/').split('/')]
        if parsed.hostname in MEDIA_HOSTS and kind == "watch" and len(parts) == 1:
            value = re.sub(r"(?:-(?:mobile|silent|poster|small|medium|large|timeline))?\.(?:mp4|jpg|m4s)$", "", parts[0], flags=re.I)
        elif parsed.hostname in PAGE_HOSTS and len(parts) == 2 and parts[0] in ({"watch", "ifr"} if kind == "watch" else {kind}):
            value = parts[1]
        else:
            raise ValueError(f"Unsupported RedGIFs {kind} URL")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("Invalid RedGIFs identifier")
    return value.lower()


def iso_date(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat() if isinstance(value, (int, float)) else None


def video_api(data: dict, expected_id: str, expected_type: int) -> dict:
    if not isinstance(data, dict) or str(data.get("id", "")).lower() != expected_id or data.get("type") != expected_type:
        raise NotFound(f"Response does not identify the requested media: {expected_id}")
    urls = data.get("urls") or {}
    sources = {key: urls[key] for key in ("hd", "sd", "silent") if urls.get(key)}
    user = data.get("userName")
    duration = data.get("duration")
    return {
        "description": data.get("description"), "duration": duration,
        "length": str(duration) if duration is not None else None,
        "publish_date": iso_date(data.get("createDate")), "views": data.get("views"),
        "likes": data.get("likes"), "tags": data.get("tags"),
        "width": data.get("width"), "height": data.get("height"),
        "has_audio": data.get("hasAudio"), "verified": data.get("verified"),
        "published": data.get("published"), "author": user,
        "author_link": f"{BASE_URL}/users/{user}" if user else None,
        "thumbnail_url": urls.get("thumbnail"), "poster_url": urls.get("poster"),
        "preview_video_url": urls.get("vthumbnail"), "timeline_url": urls.get("timeline"),
        "content_url": urls.get("hd") or urls.get("sd"), "sources": sources,
        "available_qualities": list(sources), "embed_url": urls.get("html"),
        "niche_ids": data.get("niches"), "sexuality": data.get("sexuality"),
        "content_type": data.get("contentType"), "average_color": data.get("avgColor"),
        "gallery_id": data.get("gallery"), "media_type": data.get("type"),
        "hls_urls": {q: f"{API_URL}/v2/gifs/{expected_id}/{q}.m3u8" for q in ("hd", "sd") if q in sources} if data.get("hls") else {},
        "raw_metadata": dict(data),
    }


def video_html(content: str, expected_id: str, expected_type: int = 1) -> dict:
    parser = LexborHTMLParser(content)
    posting = None
    for script in parser.css('script[type="application/ld+json"]'):
        try:
            candidate = json.loads(script.text())
        except (ValueError, TypeError):
            continue
        if not isinstance(candidate, dict) or candidate.get("@type") != "SocialMediaPosting":
            continue
        try:
            matches = identifier(candidate.get("url", "")) == expected_id
        except ValueError:
            matches = False
        if matches:
            posting = candidate
            break
    if posting is None:
        raise NotFound(f"No matching structured media metadata for {expected_id}")
    media = posting.get("video" if expected_type == 1 else "image")
    if not isinstance(media, dict) or media.get("@type") != ("VideoObject" if expected_type == 1 else "ImageObject"):
        raise NotFound(f"Structured metadata has the wrong media type for {expected_id}")
    return {
        "title": media.get("name") or posting.get("headline"),
        "page_description": posting.get("description"),
        "description": posting.get("description"),
        "thumbnail_url": media.get("thumbnailUrl"),
        "embed_url": media.get("embedUrl"),
        "html_content_url": media.get("contentUrl"),
        "html_publish_date": posting.get("datePublished"),
        "html_metadata": posting,
    }
