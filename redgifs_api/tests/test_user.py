from urllib.parse import urlencode
from collections import Counter

import pytest
from base_api import ErrorMode, ResultOrder, make_iterator_config
from .conftest import collect


@pytest.mark.parametrize('username,count', [
    ('dainty-blossomx2', 6), ('dainty-blossomx2', 5),
    ('naughtygardengirl', 40), ('nickiipeach', 6), ('rubycammilf', 2),
])
async def test_complete_profile(client, reference, username, count):
    profile = await client.get_user(username)
    raw_profile = await reference(f'v1/users/{username}')
    assert profile.name == raw_profile['name']
    assert profile.description == raw_profile.get('description')
    expected = []
    per_page = []
    first = await reference(f'v2/users/{username}/search?' + urlencode(dict(count=count, page=1, order='new', type='g')))
    assert first['gifs'] and first['pages'] > 1
    for page in range(1, first['pages'] + 1):
        data = first if page == 1 else await reference(f'v2/users/{username}/search?' + urlencode(dict(count=count, page=page, order='new', type='g')))
        ids = [g['id'] for g in data['gifs']]
        per_page.append(ids)
        expected.extend(ids)
        actual = await collect(profile.videos(pages=1, start_page=page, count=count))
        assert [v.video_id for v in actual] == ids
    assert len(expected) == first['total']
    # Check against an independent single-page snapshot when possible. The public
    # API's equal-timestamp ordering can overlap page boundaries and omit records;
    # preserve a failing completeness gate rather than treating duplicates as pass.
    duplicates = {key: value for key, value in Counter(expected).items() if value > 1}
    snapshot = await reference(f'v2/users/{username}/search?count=100&page=1&order=new&type=g')
    if snapshot['pages'] == 1:
        snapshot_ids = {g['id'] for g in snapshot['gifs']}
        assert len(set(expected)) == len(expected), (
            f'Public API pagination is incomplete: duplicate IDs={duplicates}; '
            f'missing from single-page snapshot={sorted(snapshot_ids - set(expected))}; '
            f'count={count}, total={first["total"]}'
        )
        assert set(expected) == snapshot_ids
    else:
        assert not duplicates, f'Public API pagination duplicates: {duplicates}'
    actual = await collect(profile.videos(pages='all', count=count))
    assert [v.video_id for v in actual] == expected
    assert await collect(profile.videos(pages='all', start_page=first['pages'] + 1, count=count)) == []
    tail = await collect(profile.videos(pages='all', start_page=2, count=count))
    assert [v.video_id for v in tail] == expected[len(per_page[0]):]
    images = await collect(profile.images(pages='all', count=count))
    image_ref = await reference(f'v2/users/{username}/search?count=100&page=1&order=new&type=i')
    assert [i.video_id for i in images] == [i['id'] for i in image_ref['gifs']]
    print(f'RECONCILE {username}: video IDs expected={len(expected)} actual={len(actual)}; images={len(images)}; profile publishedGifs={profile.published_count}; public media={len(actual)+len(images)}')
    if username == 'dainty-blossomx2':
        assert len(actual) + len(images) == profile.published_count


async def test_profile_filters_and_partial_close(client):
    user = await client.get_user('naughtygardengirl', load_api=False)
    assert not user.loaded_sources
    config = make_iterator_config((), order=ResultOrder.ORIGINAL,
                                  page_error_mode=ErrorMode.RAISE, item_error_mode=ErrorMode.RAISE)
    async with user.videos(count=3, iterator_config=config) as stream:
        first = (await anext(stream)).unwrap()
        assert first.loaded_sources == frozenset()
    assert stream._closed
    await first.load_sources('api')
    assert first.author == user.username
    top = await collect(user.videos(sort='top', count=3))
    assert top and all(v.author == user.username for v in top)
    tags = [top[0].tags[0]]
    filtered = await collect(user.videos(tags=tags, count=3))
    assert filtered and all(tags[0] in v.tags for v in filtered)


async def test_injected_core_ownership(client):
    from redgifs_api import Client
    sibling = Client(client.core)
    await sibling.get_video('hotpinkacrobatickitfox')
    session = client.core.session
    headers = dict(session.headers)
    await sibling.close()
    assert client.core.session is session
    await client.get_user('dainty-blossomx2')
    assert dict(session.headers) == headers


async def test_single_page_complete_profile(client, reference):
    user = await client.get_user('dainty-blossomx2')
    raw = await reference('v2/users/dainty-blossomx2/search?count=40&page=1&order=new&type=g')
    videos = await collect(user.videos(pages='all', count=40))
    assert raw['pages'] == 1
    assert [v.video_id for v in videos] == [g['id'] for g in raw['gifs']]
    assert len(videos) == len({v.video_id for v in videos}) == raw['total'] == user.published_count
    assert await collect(user.videos(pages='all', count=40, start_page=2)) == []
    print(f'RECONCILE dainty-blossomx2 single page: expected={raw["total"]} actual={len(videos)}')
