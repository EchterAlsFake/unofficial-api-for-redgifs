from .conftest import collect


async def test_niche_directory_and_complete_listing(client, reference):
    niches = await collect(client.get_niches(count=3))
    assert len(niches) == 3 and all(n.name and n.description for n in niches)
    niche = await client.get_niche('duo-chastity')
    raw = (await reference('v2/niches/duo-chastity'))['niche']
    assert niche.name == raw['name'] and niche.tags == raw['tags']
    expected = []
    first = await reference('v2/niches/duo-chastity/gifs?count=2&page=1&order=new&type=g')
    assert first['gifs'] and first['pages'] > 1
    for page in range(1, first['pages'] + 1):
        data = first if page == 1 else await reference(f'v2/niches/duo-chastity/gifs?count=2&page={page}&order=new&type=g')
        expected.extend(g['id'] for g in data['gifs'])
        actual = await collect(niche.videos(count=2, start_page=page))
        assert [v.video_id for v in actual] == [g['id'] for g in data['gifs']]
    actual = await collect(niche.videos(count=2, pages='all'))
    assert [v.video_id for v in actual] == expected
    assert len(expected) == first['total'] == len(set(expected))
    assert await collect(niche.videos(count=2, start_page=first['pages'] + 1)) == []
    assert await collect(niche.videos(count=2, sort='top'))
    related = await actual[0].get_niches()
    assert related and niche.niche_id in {n.niche_id for n in related}
    print(f'RECONCILE niche duo-chastity: expected={len(expected)} actual={len(actual)}; niche gifs={niche.video_count}')
