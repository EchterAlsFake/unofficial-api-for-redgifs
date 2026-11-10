from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import ClassVar, Literal
from urllib.parse import urlencode

from base_api import (BaseCore, BaseMedia, CachePolicy, DownloadConfigRAW, ErrorMode,
                      Helper, IteratorConfig, NotFound, ScrapeStream, media_field,
                      make_iterator_config)
from base_api.modules.errors import HTTPStatusError
from base_api.modules.provider import download_errors, prepare_download_config

from .modules.consts import API_URL, BASE_URL, identifier, iso_date, video_api, video_html
from .modules.sorting import ProfileSort, Sort


class _API:
    """Per-client anonymous session; every request uses the supplied BaseCore.

    Its fetch_text/configuration pair also lets the shared Helper make authenticated
    page requests without changing global or caller-owned session headers.
    """
    def __init__(self, core: BaseCore):
        self.core = core
        self.configuration = core.configuration
        self._token: str | None = None
        self._session: str | None = None
        self._lock = asyncio.Lock()

    async def _authenticate(self):
        async with self._lock:
            if self._token is None:
                data = json.loads(await self.core.fetch_text(
                    f"{API_URL}/v2/auth/temporary", cache_policy=CachePolicy.BYPASS))
                if not data.get("token"):
                    raise ValueError("RedGIFs did not issue an anonymous token")
                self._token, self._session = data["token"], data.get("session")

    async def fetch_text(self, url: str, *, method: str = "GET", refresh: bool = False):
        if not url.startswith(f"{API_URL}/"):
            raise ValueError("API requests must use api.redgifs.com")
        for attempt in range(2):
            await self._authenticate()
            token = self._token
            headers = {"Authorization": f"Bearer {token}", "Referer": f"{BASE_URL}/"}
            if self._session:
                headers["X-Session-Id"] = self._session
            try:
                return await self.core.fetch_text(url, headers=headers, method=method,
                    cache_policy=CachePolicy.REFRESH if refresh else CachePolicy.USE)
            except HTTPStatusError as error:
                if error.status_code != 401 or attempt:
                    raise
                async with self._lock:
                    if self._token == token:
                        self._token = None
        raise RuntimeError("Anonymous authentication exhausted")

    async def get(self, path: str, **kwargs):
        return json.loads(await self.fetch_text(f"{API_URL}/{path.lstrip('/')}", **kwargs))


def _api_for(media):
    if media._api is None:
        media._api = _API(media.core)
    return media._api


@dataclass(slots=True, kw_only=True, repr=False)
class Video(BaseMedia):
    url: str
    core: BaseCore
    video_id: str = field(init=False)
    _api: _API | None = field(default=None, repr=False)
    _seed: dict | None = field(default=None, repr=False)
    expected_type: ClassVar[int] = 1
    title: str | None = media_field("html")
    page_description: str | None = media_field("html")
    html_content_url: str | None = media_field("html")
    html_publish_date: str | None = media_field("html")
    html_metadata: dict | None = media_field("html")
    description: str | None = media_field("api", "html")
    thumbnail_url: str | None = media_field("api", "html")
    embed_url: str | None = media_field("api", "html")
    duration: float | None = media_field("api")
    length: str | None = media_field("api")
    publish_date: str | None = media_field("api")
    views: int | None = media_field("api")
    likes: int | None = media_field("api")
    tags: list[str] | None = media_field("api")
    width: int | None = media_field("api")
    height: int | None = media_field("api")
    has_audio: bool | None = media_field("api")
    verified: bool | None = media_field("api")
    published: bool | None = media_field("api")
    author: str | None = media_field("api")
    author_link: str | None = media_field("api")
    poster_url: str | None = media_field("api")
    preview_video_url: str | None = media_field("api")
    timeline_url: str | None = media_field("api")
    content_url: str | None = media_field("api")
    sources: dict[str, str] | None = media_field("api")
    available_qualities: list[str] | None = media_field("api")
    niche_ids: list[str] | None = media_field("api")
    sexuality: list[str] | None = media_field("api")
    content_type: str | None = media_field("api")
    average_color: str | None = media_field("api")
    gallery_id: str | None = media_field("api")
    media_type: int | None = media_field("api")
    hls_urls: dict[str, str] | None = media_field("api")
    raw_metadata: dict | None = media_field("api")
    loader_methods: ClassVar[dict[str, str]] = {"api": "_load_api", "html": "_load_html"}

    def __post_init__(self):
        self.video_id = identifier(self.url)
        self.url = f"{BASE_URL}/watch/{self.video_id}"

    async def _load_api(self):
        data = self._seed
        if data is None:
            data = (await _api_for(self).get(f"v2/gifs/{self.video_id}"))["gif"]
        return video_api(data, self.video_id, self.expected_type)

    async def _load_html(self):
        return video_html(await self.core.fetch_text(self.url), self.video_id, self.expected_type)

    async def get_author(self, *, load_api: bool = True) -> User | None:
        await self.load_fields("author_link")
        if not self.author_link:
            return None
        return await Client(self.core, _api=_api_for(self)).get_user(self.author_link, load_api=load_api)

    async def get_niches(self) -> list[Niche]:
        await self.load_fields("niche_ids")
        client = Client(self.core, _api=_api_for(self))
        return [await client.get_niche(n) for n in self.niche_ids or []]

    async def get_qualities(self) -> list[str]:
        await self.load_fields("available_qualities")
        return list(self.available_qualities or [])

    async def get_download_url(self, quality="best", *, refresh: bool = False) -> str:
        if refresh:
            data = (await _api_for(self).get(f"v2/gifs/{self.video_id}", refresh=True))["gif"]
            sources = video_api(data, self.video_id, self.expected_type)["sources"]
        else:
            await self.load_fields("sources")
            sources = self.sources or {}
        normal = [q for q in ("sd", "hd") if q in sources]
        if quality in {"hd", "sd", "silent"}:
            if quality not in sources:
                raise ValueError(f"Rendition {quality!r} unavailable; choose from {list(sources)}")
            return sources[quality]
        if quality not in {"best", "half", "worst"}:
            raise ValueError("RedGIFs exposes rendition labels, not resolution guarantees; use hd/sd/silent/best/half/worst")
        if not normal:
            raise NotFound("No downloadable media rendition")
        index = len(normal) - 1 if quality == "best" else (len(normal) - 1) // 2 if quality == "half" else 0
        return sources[normal[index]]

    @download_errors()
    async def download(self, configuration: DownloadConfigRAW) -> bool:
        if not isinstance(configuration, DownloadConfigRAW):
            raise TypeError("Use DownloadConfigRAW for RedGIFs MP4 or image downloads")
        source = await self.get_download_url(configuration.quality, refresh=True)
        title = self.title if self.is_field_loaded("title") and self.title else self.video_id
        config = prepare_download_config(configuration, title)
        if self.expected_type == 2 and not config.no_title:
            config.path = str(Path(config.path).with_suffix(Path(source.split('?')[0]).suffix))
        return await self.core.legacy_download(source, configuration=config)


@dataclass(slots=True, kw_only=True, repr=False)
class Image(Video):
    expected_type: ClassVar[int] = 2


@dataclass(slots=True, kw_only=True, repr=False)
class User(BaseMedia):
    url: str
    core: BaseCore
    username: str = field(init=False)
    _api: _API | None = field(default=None, repr=False)
    _seed: dict | None = field(default=None, repr=False)
    name: str | None = media_field("api")
    description: str | None = media_field("api")
    thumbnail_url: str | None = media_field("api")
    creation_date: str | None = media_field("api")
    followers: int | None = media_field("api")
    following: int | None = media_field("api")
    video_count: int | None = media_field("api")
    published_count: int | None = media_field("api")
    collection_count: int | None = media_field("api")
    views: int | None = media_field("api")
    likes: int | None = media_field("api")
    verified: bool | None = media_field("api")
    studio: bool | None = media_field("api")
    status: str | None = media_field("api")
    profile_url: str | None = media_field("api")
    links: list[dict] | None = media_field("api")
    raw_metadata: dict | None = media_field("api")
    loader_methods: ClassVar[dict[str, str]] = {"api": "_load_api"}

    def __post_init__(self):
        self.username = identifier(self.url, "users")
        self.url = f"{BASE_URL}/users/{self.username}"

    async def _load_api(self):
        data = self._seed if self._seed is not None else await _api_for(self).get(f"v1/users/{self.username}")
        if str(data.get("username", "")).lower() != self.username:
            raise NotFound(f"Mismatched profile: {self.username}")
        names = {"name": "name", "description": "description", "thumbnail_url": "profileImageUrl",
                 "followers": "followers", "following": "following", "video_count": "gifs",
                 "published_count": "publishedGifs", "collection_count": "publishedCollections",
                 "views": "views", "likes": "likes", "verified": "verified", "studio": "studio",
                 "status": "status", "profile_url": "profileUrl", "links": "links"}
        return {**{k: data.get(v) for k, v in names.items()},
                "creation_date": iso_date(data.get("creationtime")), "raw_metadata": dict(data)}

    def videos(self, *, pages: int | Literal["all"] = 1, start_page: int = 1, count: int = 40,
               sort: ProfileSort | str = ProfileSort.NEW, tags: list[str] | None = None,
               iterator_config: IteratorConfig | None = None) -> ScrapeStream[Video]:
        sort = ProfileSort(sort)
        return _listing(_api_for(self), f"v2/users/{self.username}/search", Video,
                        {"count": count, "order": sort, "type": "g", "tags": ','.join(tags or [])},
                        pages, start_page, iterator_config)

    def images(self, *, pages=1, start_page=1, count=40, iterator_config=None) -> ScrapeStream[Image]:
        return _listing(_api_for(self), f"v2/users/{self.username}/search", Image,
                        {"count": count, "order": "new", "type": "i"}, pages, start_page, iterator_config)

    def collections(self, *, pages=1, start_page=1, count=40, iterator_config=None) -> ScrapeStream[Collection]:
        return _listing(_api_for(self), f"v2/users/{self.username}/collections", Collection,
                        {"count": count}, pages, start_page, iterator_config, key="collections")


@dataclass(slots=True, kw_only=True, repr=False)
class Niche(BaseMedia):
    url: str
    core: BaseCore
    niche_id: str = field(init=False)
    _api: _API | None = field(default=None, repr=False)
    _seed: dict | None = field(default=None, repr=False)
    name: str | None = media_field("api")
    description: str | None = media_field("api")
    thumbnail_url: str | None = media_field("api")
    cover_url: str | None = media_field("api")
    video_count: int | None = media_field("api")
    subscribers: int | None = media_field("api")
    tags: list[str] | None = media_field("api")
    preferences: list[str] | None = media_field("api")
    raw_metadata: dict | None = media_field("api")
    loader_methods: ClassVar[dict[str, str]] = {"api": "_load_api"}

    def __post_init__(self):
        self.niche_id = identifier(self.url, "niches")
        self.url = f"{BASE_URL}/niches/{self.niche_id}"

    async def _load_api(self):
        # Directory cards omit description/cover: use the actual detail endpoint.
        data = (await _api_for(self).get(f"v2/niches/{self.niche_id}"))["niche"]
        if data.get("id") != self.niche_id:
            raise NotFound(f"Mismatched niche: {self.niche_id}")
        names = {"name": "name", "description": "description", "thumbnail_url": "thumbnail",
                 "cover_url": "cover", "video_count": "gifs", "subscribers": "subscribers",
                 "tags": "tags", "preferences": "preferences"}
        return {**{k: data.get(v) for k, v in names.items()}, "raw_metadata": dict(data)}

    def videos(self, *, pages=1, start_page=1, count=40, sort="new", iterator_config=None):
        sort = ProfileSort(sort)
        return _listing(_api_for(self), f"v2/niches/{self.niche_id}/gifs", Video,
                        {"count": count, "order": sort, "type": "g"}, pages, start_page, iterator_config)


@dataclass(slots=True, kw_only=True, repr=False)
class Collection(BaseMedia):
    url: str
    core: BaseCore
    username: str
    collection_id: str
    _api: _API | None = field(default=None, repr=False)
    _seed: dict | None = field(default=None, repr=False)
    name: str | None = media_field("api")
    description: str | None = media_field("api")
    thumbnail_url: str | None = media_field("api")
    content_count: int | None = media_field("api")
    publish_date: str | None = media_field("api")
    published: bool | None = media_field("api")
    raw_metadata: dict | None = media_field("api")
    loader_methods: ClassVar[dict[str, str]] = {"api": "_load_api"}

    async def _load_api(self):
        data = self._seed if self._seed is not None else await _api_for(self).get(
            f"v2/users/{self.username}/collections/{self.collection_id}")
        if data.get("folderId") != self.collection_id or data.get("userId") != self.username:
            raise NotFound("Mismatched collection")
        return {"name": data.get("folderName"), "description": data.get("description"),
                "thumbnail_url": data.get("thumbs"), "content_count": data.get("contentCount"),
                "publish_date": iso_date(data.get("createDate")), "published": data.get("published"),
                "raw_metadata": dict(data)}

    def items(self, *, pages=1, start_page=1, count=40, iterator_config=None):
        return _listing(_api_for(self), f"v2/users/{self.username}/collections/{self.collection_id}/gifs",
                        Video, {"count": count}, pages, start_page, iterator_config, mixed=True)


@dataclass(frozen=True, slots=True)
class Tag:
    name: str
    count: int | None


def _extract_items(content, *, kind, key, mixed):
    data = json.loads(content)
    if key not in data or not isinstance(data[key], list):
        raise ValueError(f"Missing RedGIFs listing array {key!r}")
    for item in data[key]:
        if kind in {Video, Image}:
            if not mixed and item.get("type") != kind.expected_type:
                raise ValueError("Unexpected media type in filtered listing")
            yield {"url": f"{BASE_URL}/watch/{item['id']}", "_seed": item}
        elif kind is User:
            yield {"url": f"{BASE_URL}/users/{item['username']}", "_seed": item}
        elif kind is Niche:
            yield {"url": f"{BASE_URL}/niches/{item['id']}"}
        else:
            yield {"url": f"{BASE_URL}/users/{item['userId']}/collections/{item['folderId']}",
                   "username": item['userId'], "collection_id": item['folderId'], "_seed": item}


def _listing(api, path, kind, params, pages, start_page, iterator_config, *, key="gifs", mixed=False):
    params = {key: value for key, value in params.items() if value not in (None, "")}
    if isinstance(pages, bool) or (pages != "all" and (not isinstance(pages, int) or pages < 1)):
        raise ValueError("pages must be a positive integer or 'all'")
    if isinstance(start_page, bool) or not isinstance(start_page, int) or start_page < 1:
        raise ValueError("start_page must be a positive integer")
    if isinstance(params.get("count"), bool) or not isinstance(params.get("count"), int) or not 1 <= params['count'] <= 100:
        raise ValueError("count must be between 1 and 100")
    config = iterator_config or make_iterator_config(("api",), page_error_mode=ErrorMode.RAISE,
                                                     item_error_mode=ErrorMode.RAISE)
    def construct(*, core, **data):
        actual = Image if mixed and data['_seed']['type'] == 2 else kind
        return actual(core=api.core, _api=api, **data)
    helper = Helper(core=api, constructor=construct)
    extractor = partial(_extract_items, kind=kind, key=key, mixed=mixed)
    def page_url(page):
        return f"{API_URL}/{path}?{urlencode({**params, 'page': page})}"
    async def generate():
        # Discover the server's actual last page; no guess based on result length.
        # Collections return HTTP 404 beyond the final page. Discover from page 1
        # so an invalid collection still raises, while a valid exhausted list ends.
        first = json.loads(await api.fetch_text(page_url(1)))
        last = first.get('pages')
        if not isinstance(last, int) or last < 0 or first.get('page') != 1:
            raise ValueError("Invalid RedGIFs pagination metadata")
        end = last if pages == "all" else min(last, start_page + pages - 1)
        if start_page > end:
            return
        urls = [page_url(page) for page in range(start_page, end + 1)]
        async with helper.iterator(urls, extractor, iterator_config=config) as stream:
            async for result in stream:
                yield result
    return ScrapeStream(generate())


class Client:
    def __init__(self, core: BaseCore | None = None, *, _api: _API | None = None):
        self.core = core if core is not None else BaseCore()
        self._owns_core = core is None
        self._api = _api or _API(self.core)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.close()

    async def close(self):
        if self._owns_core:
            await self.core.close()

    async def get_video(self, url: str, load_html: bool = False, load_api: bool = True) -> Video:
        video = Video(url=url, core=self.core, _api=self._api)
        await video.load_sources(*(source for source, enabled in (("api", load_api), ("html", load_html)) if enabled))
        return video

    async def get_image(self, url: str, *, load_api: bool = True, load_html: bool = False) -> Image:
        image = Image(url=url, core=self.core, _api=self._api)
        await image.load_sources(*(source for source, enabled in (("api", load_api), ("html", load_html)) if enabled))
        return image

    async def get_user(self, url: str, *, load_api: bool = True) -> User:
        user = User(url=url, core=self.core, _api=self._api)
        if load_api:
            await user.load_sources("api")
        return user

    async def get_niche(self, url: str, *, load_api: bool = True) -> Niche:
        niche = Niche(url=url, core=self.core, _api=self._api)
        if load_api:
            await niche.load_sources("api")
        return niche

    async def get_collection(self, username: str, collection_id: str, *, load_api: bool = True) -> Collection:
        username = identifier(username, "users")
        collection_id = identifier(collection_id)
        result = Collection(url=f"{BASE_URL}/users/{username}/collections/{collection_id}",
                            username=username, collection_id=collection_id, core=self.core, _api=self._api)
        if load_api:
            await result.load_sources("api")
        return result

    def search(self, query: str = "", *, tags: list[str] | None = None, sort: Sort | str = Sort.TRENDING,
               pages=1, start_page=1, count=40, verified=False, iterator_config=None):
        return _listing(self._api, "v2/gifs/search", Video,
                        {"query": query, "tags": ','.join(tags or []), "order": Sort(sort),
                         "count": count, "type": "g", "verified": "y" if verified else ""},
                        pages, start_page, iterator_config)

    def search_images(self, query="", *, tags=None, pages=1, start_page=1, count=40, iterator_config=None):
        return _listing(self._api, "v2/gifs/search", Image,
                        {"query": query, "tags": ','.join(tags or []), "order": "latest", "count": count, "type": "i"},
                        pages, start_page, iterator_config)

    def search_users(self, query="", *, pages=1, start_page=1, count=40, verified=False, iterator_config=None):
        return _listing(self._api, "v2/creators/search", User,
                        {"query": query, "count": count, "verified": "y" if verified else ""},
                        pages, start_page, iterator_config, key="items")

    def get_niches(self, *, pages=1, start_page=1, count=40, iterator_config=None):
        return _listing(self._api, "v2/niches/search", Niche, {"count": count},
                        pages, start_page, iterator_config, key="niches")

    async def get_tags(self, *, trending: bool = False) -> list[Tag]:
        data = await self._api.get("v2/tags/trending" if trending else "v1/tags")
        return [Tag(name=t['name'], count=t.get('count')) for t in data['tags']]


def create_parser():
    parser = argparse.ArgumentParser(description="Download public RedGIFs videos using eaf-base-api")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--download", "-d", help="RedGIFs watch/embed URL or ID")
    group.add_argument("--file", "-f", type=Path, help="UTF-8 file containing one video URL per line")
    parser.add_argument("--output", "-o", default="./", help="Output directory")
    parser.add_argument("--quality", "-q", default="best", choices=["best", "half", "worst", "hd", "sd", "silent"])
    return parser


async def run_main(argv=None):
    args = create_parser().parse_args(argv)
    urls = args.file.read_text(encoding="utf-8").splitlines() if args.file else [args.download]
    async with Client() as client:
        for url in urls:
            if url.strip():
                video = await client.get_video(url.strip())
                await video.download(DownloadConfigRAW(quality=args.quality, path=args.output))


def main():
    asyncio.run(run_main())
