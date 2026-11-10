import pytest
from .conftest import collect


@pytest.mark.parametrize('sort', ['trending', 'latest', 'top'])
async def test_search(client, reference, sort):
    videos = await collect(client.search(tags=['Amateur'], sort=sort, count=5, pages=2))
    assert videos
    assert all(v.media_type == 1 and 'Amateur' in v.tags for v in videos)
    assert len({v.video_id for v in videos}) == len(videos)
    if sort != 'latest':
        page = await reference(f'v2/gifs/search?tags=Amateur&order={sort}&count=5&type=g&page=1')
        # Ranked feeds can change; compare IDs on a stable top page.
        if sort == 'top':
            assert [v.video_id for v in videos[:5]] == [g['id'] for g in page['gifs']]


async def test_query_users_and_tags(client):
    assert await collect(client.search('Amateur', count=3))
    verified_videos = await collect(client.search(tags=['Amateur'], verified=True, sort='latest', count=3))
    assert verified_videos and all(v.verified for v in verified_videos)
    users = await collect(client.search_users('nature', count=3, verified=True))
    assert users and all(u.verified for u in users)
    for trending in (False, True):
        tags = await client.get_tags(trending=trending)
        assert tags and all(t.name and isinstance(t.count, int) for t in tags)
