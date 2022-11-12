"""Request game data from steamAPI and store it."""

import json
import time
import logging
from typing import Iterable
from random import choice
import re
import asyncio
import requests
import aiohttp
from bs4 import BeautifulSoup
# import grequests


LOGGING_LEVEL = logging.DEBUG
logging.basicConfig(filename='.log',
                    filemode='w',
                    level=LOGGING_LEVEL,
                    format='[%(levelname)s] %(asctime)s %(message)s', )

# Get name to appid dict.
try:
    with open('data/helpers/app_id_list.json', 'r', encoding='utf-8') as f:
        APP_NAME_TO_ID_DICT: dict[str, int] = json.load(f)
except FileNotFoundError:
    r = requests.get('http://api.steampowered.com/ISteamApps/GetAppList/v0002/',
                    timeout=10)

    APP_NAME_TO_ID_DICT = r.json()['applist']['apps']
    APP_NAME_TO_ID_DICT: dict[str, int] = {game['name']: game['appid'] for game in APP_NAME_TO_ID_DICT}

    with open('data/helpers/app_id_list.json', 'w', encoding='utf-8') as f:
        json.dump(APP_NAME_TO_ID_DICT, f, indent=4, ensure_ascii=False)

STEAM_SEARCH_URL = 'https://store.steampowered.com/search/?term='
STEAM_APPID_URL = 'https://store.steampowered.com/api/appdetails?appids='
STEAM_REVIEW_URL = 'https://store.steampowered.com/appreviews/'

async def async_req(session: aiohttp.ClientSession, url: str, resp_type: str):
    """
    Async request from url during a session.
    ---
    `resp_type`:
        - `json`
        - `text`
    """
    async with session.get(url) as response:
        if resp_type == 'json':
            return await response.json()
        elif resp_type == 'text':
            return await response.text()

        raise ValueError('Invalid resp_type.')

def size_regex(text: str) -> re.Match[str] | None:
    """Regex to get size match from text."""
    size_match = re.search(
        r'(Storage:|Space:|Drive:)[^\d]*(\d+ ?[kKMGT]?B)',
        text)
    return size_match

async def get_app_ids(game_names: list[str]) -> tuple[list[int], list[str]]:
    """
    Get appids for steam game names. If a game name is not found, searches steam and updates `game_names` with the new name.
    
    returns: `appids`, `game_names` (with names of games looked up on steam updated).
        - returns -1 for failed games.

    """
    app_ids = []
    tasks = []
    not_found_ids = []
    # loop over. get app_id from known list or plan a steam search.
    async with aiohttp.ClientSession() as session:

        for i, game_name in enumerate(game_names):
            if game_name in APP_NAME_TO_ID_DICT:
                app_id =  APP_NAME_TO_ID_DICT[game_name]
            else:
                url = STEAM_SEARCH_URL + game_name
                tasks.append(asyncio.ensure_future(async_req(session, url, 'text')))
                app_id = None
                not_found_ids.append(i)
            app_ids.append(app_id)

        responses = await asyncio.gather(*tasks)

    # steam search for unknown games.
    for i, response in enumerate(responses):

        soup = BeautifulSoup(response, 'html.parser')
        try:
            # TODO search gives the closest, not the exact, game name.
            # UPDATE GAME NAME from search result (updated_game_names = [], update, ...)
            app_id = soup.find(class_='search_result_row')['data-ds-appid']
            app_id = int(app_id)
            game_names[not_found_ids[i]] = soup.find(class_='title').text
        except TypeError:
            logging.warning('get_app_id failed. Returning -1.')
            app_id =  -1

        app_ids[not_found_ids[i]] = app_id


    assert None not in app_ids, 'NONE FOUND IN APP_IDS'
    assert len(app_ids) == len(game_names), 'app_ids and game_names are not the same length???'

    return app_ids, game_names


async def get_game_sizes(appids: list[str | int]) -> list[float]:
    """
    Get game sizes in GB from steamAPI.
    
    RETURNS -1.0 for failed games.
    """
    if not all(isinstance(appid, str) for appid in appids):
        appids = list(map(str, appids))

    tasks = []
    async with aiohttp.ClientSession() as session:
        for appid in appids:
            tasks.append(asyncio.ensure_future(async_req(session, STEAM_APPID_URL + appid, 'json')))

        responses = await asyncio.gather(*tasks)
    
    bad_requirements = []
    size_list = []
    for i, response in enumerate(responses):

        pc_requirements: str = response[str(appids[i])]['data']['pc_requirements']['minimum']

        soup = BeautifulSoup(pc_requirements, "html.parser")
        # strip off any html tags
        pc_requirements = soup.get_text()

        # text -> ('10', 'MB')
        storage_match = size_regex(pc_requirements)

        if storage_match is None:
            logging.warning('%s get_game_size failed. Returning -1.', appids[i])
            bad_requirements.append(pc_requirements)
            size_list.append(-1)
            continue

        size = storage_match.groups()[-1]
        if ' ' in size:
            size = size.split(' ')
        else:
            size = re.split(r'(\d+)', size)

        if size[1] == 'TB':
            size_list.append(float(size[0]) * 1000)
        elif size[1] == 'GB':
            size_list.append(float(size[0]))
        elif size[1] == 'MB':
            size_list.append(float(size[0]) / 1000)
        elif size[1] in ['KB', 'kB']:
            size_list.append(float(size[0]) / 1000000)
        elif size[1] == 'B':
            size_list.append(float(size[0]) / 1000000000)
        else:
            size_list.append(-1)

    logging.debug('bad_requirements: %s', '\n'.join(bad_requirements))

    return size_list


async def get_game_review_ratios(appids: list[str | int]) -> list[float]:
    """Get game review ratios from steamAPI."""
    if not all(isinstance(appid, str) for appid in appids):
        appids = list(map(str, appids))

    tasks = []
    async with aiohttp.ClientSession() as session:
        for appid in appids:
            tasks.append(asyncio.ensure_future(async_req(
                session,
                STEAM_REVIEW_URL + appid + "?json=1&num_per_page=0&language=all", 'json')))

        responses = await asyncio.gather(*tasks)
    
    review_ratios = []
    for i, response in enumerate(responses):
        data = response
        total_reviews = data['query_summary']['total_reviews']
        positive_reviews = data['query_summary']['total_positive']

        if total_reviews == 0:
            ratio = 0.0
        else:
            ratio = positive_reviews / total_reviews

        review_ratios.append(ratio)

    return review_ratios


def random_game_names(n: int) -> list[str]:
    """Get random game names."""
    game_names = [choice(list(APP_NAME_TO_ID_DICT.keys())) for _ in range(n)]
    return game_names


async def process(game_names: Iterable[str]) -> list[dict]:
    """Process data."""
    # get appid, size, review ratio for each game.
    appids, game_names = await get_app_ids(game_names)
    sizes = await get_game_sizes(appids)
    review_ratios = await get_game_review_ratios(appids)

    new_data = [{'name': game_names[i], 'appid': appids[i], 'size': sizes[i], 'review_ratio': review_ratios[i]}
                for i in range(len(game_names))]
    
    return new_data


async def main():
    """Main. Run, save.

    For higher number of games, requests should be sent periodically.
    Steam api accepts 10req/s.
    """
    start = time.time()


    test_names = random_game_names(10)
    # with open('data/helpers/sample_game_names.json', 'r', encoding='utf-8') as f:
    #     test_names: list[str] = json.load(f)

    processed = await process(test_names)

    with open('data/output/test_out.json', 'w', encoding='utf-8') as f:
        json.dump(processed, f, indent=4, ensure_ascii=False)


    print(f'Finished in {time.time() - start} seconds.')


if __name__ == '__main__':
    asyncio.run(main())