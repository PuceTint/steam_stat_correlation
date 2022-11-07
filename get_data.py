"""Request game data from steamAPI and store it."""

import json
import time
import logging
from typing import Iterable
import asyncio
import requests
# import aiohttp
from bs4 import BeautifulSoup
# import grequests


LOGGING_LEVEL = logging.WARNING
logging.basicConfig(filename='.log',
                    filemode='w',
                    level=LOGGING_LEVEL,
                    format='[%(levelname)s] %(asctime)s %(message)s', )

with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)
STEAM_API_KEY: str = config['steam_api_key']

# Get {name: appid} dict.
try:
    with open('data/helpers/app_id_list.json', 'r', encoding='utf-8') as f:
        APP_NAME_TO_ID_DICT: dict[str, int] = json.load(f)
except FileNotFoundError:
    r = requests.get(f'http://api.steampowered.com/ISteamApps/GetAppList/v0002/?key={STEAM_API_KEY}',
                    timeout=10)

    APP_NAME_TO_ID_DICT = r.json()['applist']['apps']
    APP_NAME_TO_ID_DICT: dict[str, int] = {game['name']: game['appid'] for game in APP_NAME_TO_ID_DICT}

    with open('data/helpers/app_id_list.json', 'w', encoding='utf-8') as f:
        json.dump(APP_NAME_TO_ID_DICT, f, indent=4, ensure_ascii=False)


async def get_app_id(game_name: str) -> int:
    """Get appid from steamAPI."""
    logging.debug('%s started.', game_name)
    try:
        app_id = APP_NAME_TO_ID_DICT[game_name]
    except KeyError:
        response = requests.get(url=f'https://store.steampowered.com/search/?term={game_name}&category1=998&key={STEAM_API_KEY}',
                                timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        app_id = soup.find(class_='search_result_row')['data-ds-appid']

    logging.debug('%s finished.', game_name)
    return int(app_id)


async def get_game_size(appid: int) -> float:
    """
    Get game size in GB from steamAPI.

    RETURNS -1. ON FAILURE.
    """
    logging.debug('%s get_game_size started.', appid)
    r = requests.get(f"https://store.steampowered.com/api/appdetails/?appids={appid}&key={STEAM_API_KEY}",
                    timeout=10)
    data = r.json()
    pc_requirements: str = data[str(appid)]['data']['pc_requirements']['minimum']
    if 'Storage:' in pc_requirements:
        storage_start = pc_requirements.find('Storage:') + len('Storage: </strong>')
        storage_end = pc_requirements.find(' available', storage_start)
    elif 'Drive:' in pc_requirements:
        storage_start = pc_requirements.find('Drive:') + len('Drive: </strong>')
        storage_end = pc_requirements.find(' free', storage_start)
    else:
        logging.warning('%s get_game_size failed. Returning -1.', appid)
        return -1

    size = pc_requirements[storage_start:storage_end].split(' ')
    logging.debug('%s get_game_size, pc requirements string:\n%s', appid, pc_requirements)

    if size[1] == 'TB':
        return float(size[0]) * 1000
    elif size[1] == 'GB':
        return float(size[0])
    elif size[1] == 'MB':
        return float(size[0]) / 1000
    elif size[1] == 'KB':
        return float(size[0]) / 1000000
    elif size[1] == 'B':
        return float(size[0]) / 1000000000
    raise ValueError(f'Unknown size unit: {size[1]}')


async def get_game_review_ratio(appid: int) -> float:
    """Get game review ratio from steamAPI."""
    logging.debug('%s get_game_review_ratio started.', appid)

    r = requests.get(f"https://store.steampowered.com/appreviews/{appid}?json=1&filter=recent&language=all&key={STEAM_API_KEY}",
                    timeout=10)
    data = r.json()
    total_reviews = data['query_summary']['total_reviews']
    positive_reviews = data['query_summary']['total_positive']

    if total_reviews == 0:
        ratio = 0.0
    else:
        ratio = positive_reviews / total_reviews

    logging.debug('%s get_game_review_ratio finished.', appid)
    return ratio


async def process(game_names: Iterable[str]) -> list[dict]:
    """Process data."""
    # TODO aiohttp
    # get appid, size, review ratio for each game.
    appids = await asyncio.gather(*[get_app_id(game_name) for game_name in game_names])
    sizes = await asyncio.gather(*[get_game_size(appid) for appid in appids])
    review_ratios = await asyncio.gather(*[get_game_review_ratio(appid) for appid in appids])

    new_data = [{'name': game_names[i], 'appid': appids[i], 'size': sizes[i], 'review_ratio': review_ratios[i]}
                for i in range(len(game_names))]
    
    return new_data


async def main():
    start = time.time()


    with open('data/test/sample_game_names.json', 'r', encoding='utf-8') as f:
        test_names: list[str] = json.load(f)

    processed = await process(test_names)

    with open('data/output/test_out.json', 'w', encoding='utf-8') as f:
        json.dump(processed, f, indent=4, ensure_ascii=False)


    print(f'Finished in {time.time() - start} seconds.')


if __name__ == '__main__':
    asyncio.run(main())
