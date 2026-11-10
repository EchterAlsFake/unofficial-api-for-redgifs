import pytest
from base_api import MediaLoadError
from redgifs_api import DownloadConfigRAW, Image
from .conftest import IMAGE_ID, collect, probe


async def test_image(client, reference, tmp_path):
    image = await client.get_image(IMAGE_ID)
    data = (await reference(f'v2/gifs/{IMAGE_ID}'))['gif']
    assert image.media_type == 2 and image.duration is None
    assert image.width == data['width'] and image.height == data['height']
    await image.load_sources('html')
    assert image.title and image.html_metadata
    for quality in image.available_qualities:
        target = tmp_path / f'{quality}.jpg'
        assert await image.download(DownloadConfigRAW(quality=quality, path=target, no_title=True, callback=lambda *_: None))
        result = probe(target)
        assert result['streams'][0]['codec_type'] == 'video'  # ffprobe represents still images as video streams.
        assert target.stat().st_size > 1000
        print(f'IMAGE {IMAGE_ID} {quality}: {target.stat().st_size} bytes '
              f'{result["streams"][0]["width"]}x{result["streams"][0]["height"]}')
    for url in (data['urls']['hd'], data['urls']['sd'], data['urls']['thumbnail']):
        fetched = await client.get_image(url)
        assert fetched.video_id == IMAGE_ID
    images = await collect(client.search_images(tags=['Amateur'], count=3))
    assert images and all(type(i) is Image for i in images)
    assert all('Amateur' in i.tags for i in images)


@pytest.mark.parametrize('mode', ['api', 'html', 'both', 'deferred'])
async def test_image_sources(client, mode):
    image = await client.get_image(IMAGE_ID, load_api=mode in {'api', 'both'},
                                   load_html=mode in {'html', 'both'})
    if mode == 'deferred':
        assert not image.loaded_sources
        await image.load_fields('media_type')
    if mode != 'html':
        assert image.media_type == 2 and image.duration is None
    if mode in {'html', 'both'}:
        assert image.title and image.html_metadata['image']['@type'] == 'ImageObject'
    with pytest.raises(MediaLoadError):
        await client.get_image('hotpinkacrobatickitfox', load_api=False, load_html=True)
