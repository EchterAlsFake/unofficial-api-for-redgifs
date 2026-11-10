from .conftest import collect


async def test_collection_complete(client, reference):
    user = await client.get_user('weirdjack')
    collections = await collect(user.collections(pages='all', count=5))
    raw_list = await reference('v2/users/weirdjack/collections?count=5&page=1')
    assert [c.collection_id for c in collections] == [c['folderId'] for c in raw_list['collections']]
    assert collections
    collection = await client.get_collection(user.username, 'd7ddef5fb0')
    detail = await reference('v2/users/weirdjack/collections/d7ddef5fb0')
    assert collection.name == detail['folderName']
    assert collection.content_count == detail['contentCount']
    expected = []
    first = await reference('v2/users/weirdjack/collections/d7ddef5fb0/gifs?count=100&page=1')
    assert first['gifs'] and first['pages'] > 1
    for page in range(1, first['pages'] + 1):
        data = first if page == 1 else await reference(f'v2/users/weirdjack/collections/d7ddef5fb0/gifs?count=100&page={page}')
        ids = [g['id'] for g in data['gifs']]
        expected.extend(ids)
        actual = await collect(collection.items(count=100, start_page=page))
        assert [v.video_id for v in actual] == ids
    actual = await collect(collection.items(pages='all', count=100))
    assert [v.video_id for v in actual] == expected
    assert len(expected) == first['total'] == len(set(expected))
    assert await collect(collection.items(pages='all', count=100, start_page=first['pages']+1)) == []
    print(f'RECONCILE collection weirdjack/d7ddef5fb0: public expected={len(expected)} actual={len(actual)}; stored contentCount={collection.content_count}; delta={collection.content_count-len(actual)}')
