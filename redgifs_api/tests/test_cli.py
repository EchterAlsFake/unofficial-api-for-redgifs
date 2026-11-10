import asyncio
import sys
from pathlib import Path

import pytest
from .conftest import probe


@pytest.mark.parametrize('source', ['argument', 'file'])
async def test_live_cli(tmp_path, source):
    args = ['--output', str(tmp_path), '--quality', 'worst']
    url = 'https://www.redgifs.com/watch/hotpinkacrobatickitfox'
    if source == 'file':
        urls = tmp_path / 'urls.txt'
        urls.write_text(url + '\n', encoding='utf-8')
        args += ['--file', str(urls)]
    else:
        args += ['--download', url]
    process = await asyncio.create_subprocess_exec(sys.executable, '-m', 'redgifs_api', *args,
                                                  stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)
    assert process.returncode == 0, stderr.decode()[-3000:]
    files = list(tmp_path.glob('*.mp4'))
    assert len(files) == 1 and probe(files[0])['streams'][0]['width'] == 480
