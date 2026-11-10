import asyncio

import pytest
from redgifs_api import DownloadConfigRAW
from .conftest import probe


@pytest.mark.parametrize('video_id', ['hotpinkacrobatickitfox', 'ivoryhauntingblackbird', 'toughlongtermbanteng', 'happyfrenchindianspinyloach'])
async def test_all_available_renditions(client, tmp_path, video_id):
    video = await client.get_video(video_id)
    assert video.available_qualities
    if video_id == 'happyfrenchindianspinyloach':
        assert video.available_qualities == ['hd', 'sd'] and video.has_audio is False
        with pytest.raises(ValueError):
            await video.get_download_url('silent')
        with pytest.raises(ValueError):
            await video.get_download_url('1080p')
    for quality in [*video.available_qualities, 'best', 'half', 'worst']:
        target = tmp_path / f'{video_id}-{quality}.mp4'
        callbacks = []
        config = DownloadConfigRAW(quality=quality, path=target, no_title=True,
                                   callback=lambda done, total: callbacks.append((done, total)))
        assert await video.download(config)
        assert config.path == target and config.quality == quality
        data = probe(target)
        streams = data['streams']
        picture = next(s for s in streams if s['codec_type'] == 'video')
        duration = float(data['format']['duration'])
        assert abs(duration - video.duration) < .3
        if quality in {'hd', 'silent', 'best'}:
            assert (picture['width'], picture['height']) == (video.width, video.height)
        if quality in {'sd', 'worst', 'half'} and video_id == 'hotpinkacrobatickitfox':
            assert (picture['width'], picture['height']) == (480, 854)
        audio = any(s['codec_type'] == 'audio' for s in streams)
        # This legacy API flag is inaccurate: its real MP4 contains audible AAC.
        # Keep the reported metadata, but verify this observed variant explicitly.
        expected_audio = video_id == 'happyfrenchindianspinyloach' or (video.has_audio and quality != 'silent')
        assert audio == expected_audio
        assert target.stat().st_size > 1000 and callbacks
        print(f'DOWNLOAD {video_id} {quality}: {target.stat().st_size} bytes {picture["width"]}x{picture["height"]} {duration:.3f}s audio={audio}')


async def test_concurrent_repeat_downloads(client, tmp_path):
    first, second = await asyncio.gather(client.get_video('hotpinkacrobatickitfox'), client.get_video('ivoryhauntingblackbird'))
    async def download(video, name):
        target = tmp_path / name
        assert await video.download(DownloadConfigRAW(quality='sd', path=target, no_title=True, callback=lambda *_: None))
        return target, probe(target)
    (one, a), (_, b) = await asyncio.gather(download(first, 'one.mp4'), download(second, 'two.mp4'))
    repeated, c = await download(first, 'repeat.mp4')
    assert one.read_bytes() == repeated.read_bytes()
    assert abs(float(a['format']['duration']) - first.duration) < .3
    assert abs(float(b['format']['duration']) - second.duration) < .3
    assert a['streams'][0]['width'] == c['streams'][0]['width']
