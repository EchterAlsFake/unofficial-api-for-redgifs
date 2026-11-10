import json
from datetime import datetime, timezone

import pytest
from base_api import DataNotLoadedError, MediaLoadError
from .conftest import VIDEO_IDS, IMAGE_ID


@pytest.mark.parametrize('video_id', VIDEO_IDS)
@pytest.mark.parametrize('mode', ['api', 'html', 'both', 'api_then_html', 'html_then_api', 'deferred'])
async def test_sources(client, reference, video_id, mode):
    expected = (await reference(f'v2/gifs/{video_id}'))['gif']
    video = await client.get_video(video_id, load_api=False)
    assert video.loaded_sources == frozenset()
    assert 'duration' not in video.to_dict()
    with pytest.raises(DataNotLoadedError):
        _ = video.duration
    if mode == 'api':
        await video.load_sources('api')
    elif mode == 'html':
        await video.load_sources('html')
    elif mode == 'api_then_html':
        await video.load_sources('api')
        await video.load_sources('html')
    elif mode == 'html_then_api':
        await video.load_sources('html')
        await video.load_sources('api')
    elif mode == 'deferred':
        await video.load_fields('duration')
    else:
        video = await client.get_video(video_id, load_api=True, load_html=True)
    if 'api' in video.loaded_sources:
        assert video.duration == expected['duration']
        assert video.width == expected['width'] and video.height == expected['height']
        assert video.author == expected['userName']
        assert video.tags == expected['tags']
        assert video.description == expected.get('description')
        assert video.publish_date == datetime.fromtimestamp(expected['createDate'], timezone.utc).isoformat()
        assert video.sources == {k: v for k, v in expected['urls'].items() if k in {'hd', 'sd', 'silent'}}
        assert video.media_type == 1
        assert set(await video.get_qualities()) == set(video.sources)
        author = await video.get_author()
        assert author.username == expected['userName']
        assert author.name
    if 'html' in video.loaded_sources:
        assert video.title and video.html_metadata['url'].endswith(video_id)
        assert video.page_description == video.html_metadata['description']
        assert video.html_content_url == video.html_metadata['video']['contentUrl']
    if mode in {'api', 'deferred'}:
        assert video.loaded_sources == {'api'}
        assert not video.is_field_loaded('title')
    if mode == 'html':
        assert not video.is_field_loaded('duration')
        assert video.description == video.page_description
    json.dumps(video.to_dict())


@pytest.mark.parametrize('route', [
    'https://www.redgifs.com/watch/hotpinkacrobatickitfox',
    'https://redgifs.com/watch/hotpinkacrobatickitfox',
    'https://www.redgifs.com/ifr/hotpinkacrobatickitfox',
    'https://redgifs.com/ifr/hotpinkacrobatickitfox',
])
async def test_real_hosts(client, route):
    html = await client.core.fetch_text(route)
    assert 'hotpinkacrobatickitfox' in html
    video = await client.get_video(route, load_html=True)
    assert video.video_id == 'hotpinkacrobatickitfox' and video.duration > 0


async def test_media_urls_and_errors(client):
    for suffix in ['', '-mobile', '-silent']:
        url = f'https://media.redgifs.com/HotpinkAcrobaticKitfox{suffix}.mp4'
        response = await client.core.request(url, method='HEAD')
        assert response.status_code == 200
        video = await client.get_video(url)
        assert video.video_id == 'hotpinkacrobatickitfox'
    with pytest.raises(ValueError):
        await client.get_video('https://redgifs.com.attacker.invalid/watch/hotpinkacrobatickitfox')
    with pytest.raises(MediaLoadError):
        await client.get_video('thisisnotarealredgifsidentifier')
    with pytest.raises(MediaLoadError):
        await client.get_video(IMAGE_ID)
    with pytest.raises(MediaLoadError):
        await client.get_video(IMAGE_ID, load_api=False, load_html=True)


async def test_hls_inspection_and_relationships(client, reference):
    video = await client.get_video(VIDEO_IDS[0])
    assert set(video.hls_urls) == {'hd', 'sd'}
    for url in video.hls_urls.values():
        playlist = await client._api.fetch_text(url)
        assert playlist.startswith('#EXTM3U') and '#EXT-X-BYTERANGE' in playlist
        assert '#EXT-X-ENDLIST' in playlist
    other = await client.get_video('toughlongtermbanteng')
    expected = (await reference('v2/gifs/toughlongtermbanteng'))['gif']
    assert other.description and other.description == expected['description']
    # Promoted cards carry extra preview URLs that the detail endpoint omits.
    assert other.preview_video_url == expected['urls'].get('vthumbnail')
    assert other.timeline_url == expected['urls'].get('timeline')
    for niche in await other.get_niches():
        assert niche.name and niche.niche_id in other.niche_ids
