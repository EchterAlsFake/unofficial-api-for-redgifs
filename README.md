<h1 align="center">RedGIFs API</h1>
<p align="center"><em>An asynchronous Python API wrapper and scraper for redgifs.com</em></p>

<div align="center">
    <a href="https://pepy.tech/project/unofficial-api-for-redgids"><img src="https://static.pepy.tech/badge/unofficial-api-for-redgifs" alt="Downloads"></a> +
    <a href="https://github.com/EchterAlsFake/unofficial-api-for-redgifs/workflows/"><img src="https://github.com/EchterAlsFake/unofficial-api-for-redgifs/workflows/CodeQL/badge.svg" alt="CodeQL Analysis"/></a>
    <a href="https://echteralsfake.me/ci/unofficial-api-for-redgifs/badge.svg"><img src="https://echteralsfake.me/ci/unofficial-api-for-unofficial-api-for-redgifs/badge.svg" alt="Sync API Tests"/></a>
    </div>

# Disclaimer
> [!IMPORTANT]
> This is an unofficial and unaffiliated project. Please read the full disclaimer before use:
> **[DISCLAIMER.md](https://github.com/EchterAlsFake/API_Docs/blob/master/Disclaimer.md)**
>
> By using this project you agree to comply with the target site's rules, copyright/licensing requirements,
> and applicable laws. Do not use it to bypass access controls or scrape at disruptive rates.

---

# Features

| Category | Details |
|---|---|
| **Video Fetching** | Rich API metadata, independent HTML titles/page metadata, and deferred source/field loading |
| **Video Downloading** | Direct MP4 downloads with `hd`, `sd`, `silent`, `best`, `half`, and `worst` where available |
| **User & Creator Profiles** | Profile metadata, separate video/image tabs, uploader relationships and public collections |
| **Collection Fetching** | Paginated public collections containing typed video and image objects |
| **Video Search** | Query and tag search, trending/latest/top ordering, verified-only filtering and creator search |
| **Images, Tags & Niches** | Image metadata/downloads, typed tag records, niche details and video streams |
| **Async-First** | Fully asynchronous (`async` / `await`) built on top of `asyncio` |
| **Built-in Caching** | Shared response caching with configurable limits to reduce redundant network requests |
| **CLI Support** | Single-video or URL-file downloads — run `redgifs_api -h` for options |
| **Type Safety** | Typed, source-aware `BaseMedia` dataclasses and structured `ScrapeResult` streams |

Accepted page hosts are `redgifs.com` and `www.redgifs.com`; media identity URLs from
`media.redgifs.com` are also supported. No language or proxy variants are accepted.
HLS URLs are exposed for inspection; downloads use `DownloadConfigRAW` because the current
shared HLS downloader does not preserve RedGIFs' byte ranges. Private/account actions
and gallery enumeration are not implemented.

Live validation remains incomplete: the final run recorded **38 passed, 12 failed,
0 skipped**, with all final failures caused by HTTP 429. Earlier runs also reproduced
upstream pagination omissions for equal-timestamp uploads. See the
[validation report](docs/validation.md) for evidence, quality measurements and limitations.

#### Networking Features

The networking layer is provided by the [`eaf_base_api`](https://github.com/EchterAlsFake/eaf_base_api) package and is fully configurable through `RuntimeConfig`:

| Feature | Description |
|---|---|
| **HTTP/1.1, HTTP/2, HTTP/3** | Configurable HTTP version (`v1`, `v2`, `v3` — defaults to HTTP/2) |
| **Browser Impersonation** | Built-in browser fingerprint impersonation via `curl_cffi` (defaults to Chrome) |
| **Custom JA3 Fingerprint** | Override the TLS fingerprint with a custom JA3 string for advanced use cases |
| **Proxy Support** | All proxy types supported (HTTP, HTTPS, SOCKS4, SOCKS5) |
| **Proxy Authentication** | Username/password authentication for proxies |
| **Bandwidth Limiting** | Set a maximum download speed in MB/s (e.g., `2.0`, `3.5`) |
| **DNS over HTTPS** | Configure DNS resolution over HTTPS |
| **SSL Verification** | Toggle SSL certificate verification on or off |
| **Request Delay** | Configurable delay between requests to respect rate limits |
| **Concurrency Control** | Tune video and page concurrency independently for optimal throughput |

---

# Supported Platforms
This API has been live-tested on:

- Linux with Python 3.15.2

Python 3.12 or newer is required. Other platforms have not been verified.

---

# Installation

Install from the local checkout before publication:

```bash
pip install .
```

For development with the neighboring shared backend checkout:

```bash
pip install -e ../eaf_base_api -e .
```

The distribution is named `unofficial-api-for-redgifs`; publication is not asserted.

---

# Quickstart

### Have a look at the [Documentation](https://docs.echteralsfake.me/redgifs) for more details

> [!NOTE]
> RedGIFs API can also be used from the command line. Do: redgifs_api -h to see the options

```python
import asyncio
from redgifs_api import Client, DownloadConfigRAW

async def main():
    # Initialize a Client and close its network resources when finished
    async with Client() as client:
        # Load API metadata and the HTML display title
        video_object = await client.get_video(
            "https://www.redgifs.com/watch/hotpinkacrobatickitfox",
            load_html=True,
        )

        # Information from Video objects
        print(video_object.title)

        # Download the video
        config = DownloadConfigRAW(quality="best", path="./")
        await video_object.download(config)

if __name__ == "__main__":
    asyncio.run(main())
```

---

# Support the Project ❤️

I develop all my projects entirely for free because I enjoy it and want to keep them accessible.
If you find my work useful, please consider supporting me with a small donation — even 1 € makes a big difference and keeps me motivated!

### ☕ Ko-fi
<a href="https://ko-fi.com/EchterAlsFake">https://ko-fi.com/EchterAlsFake</a>

### 💳 PayPal
<a href="https://paypal.me/EchterAlsFake">https://paypal.me/EchterAlsFake</a>

### 🪙 Crypto (350+ currencies supported)
<a href="https://nowpayments.io/donation?api_key=65b1acaf-735d-4d4b-b3d6-c2237c0b57e3" target="_blank" rel="noreferrer noopener">
   <img src="https://nowpayments.io/images/embeds/donation-button-black.svg" alt="Crypto donation button by NOWPayments">
</a>

---

# Contribution
Do you see any issues or having some feature requests? Simply open an Issue or talk
in the discussions.

Pull requests are also welcome.

# License
This API is licensed under the AGPLv3. See the `LICENSE` file for details.

> [!CAUTION]
> **Using this in a proprietary application?**
> Under the AGPLv3, if you integrate, modify, or host this API as part of your application (even over a network), you must open-source your entire application's code under the AGPL. 
>
> If you want to use this API without open-sourcing your own code, you must purchase a commercial license.
> 
> **For commercial licensing, contact:** EchterAlsFakeBS@proton.me
