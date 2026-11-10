"""Live fixtures. Nothing in this suite mocks or replays network responses."""
import json
import subprocess

import pytest_asyncio
from base_api import BaseCore
from base_api.modules.config import RuntimeConfig
from redgifs_api import Client

VIDEO_IDS = ("hotpinkacrobatickitfox", "ivoryhauntingblackbird", "happyfrenchindianspinyloach")
IMAGE_ID = "deliciousfrontelephant"


def live_config():
    configuration = RuntimeConfig()
    configuration.request_delay = 2
    configuration.request_retry_initial_delay = 2
    return configuration


@pytest_asyncio.fixture(scope='session')
async def client():
    async with BaseCore(live_config()) as core:
        async with Client(core) as value:
            yield value


@pytest_asyncio.fixture(scope='session')
async def reference():
    """Independent live listing reader, without production auth or extractors."""
    async with BaseCore(live_config()) as core:
        auth = json.loads(await core.fetch_text('https://api.redgifs.com/v2/auth/temporary'))
        headers = {'Authorization': f"Bearer {auth['token']}"}
        async def get(path):
            return json.loads(await core.fetch_text('https://api.redgifs.com/' + path, headers=headers))
        yield get


async def collect(stream):
    async with stream:
        return [result.unwrap() async for result in stream]


def probe(path):
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format',
                             '-of', 'json', str(path)], capture_output=True, text=True, check=True)
    return json.loads(result.stdout)
