import asyncio
import logging
import time

import aiohttp
import click


class Summoner:
    def __init__(self, name, puuid):
        self.name = name
        self.puuid = puuid


class Match:
    def __init__(self, matchid, region, match_data):
        self.matchid = matchid
        self.region = region
        self.match_data = match_data


class RateLimit:
    def __init__(self, limit, interval):
        self.limit = limit
        self.interval = interval
        self.uses = 0
        self.last_call = 0

    def Wait(self):
        now = time.time()
        self.uses += 1
        if (now - self.last_call < self.interval) and (self.uses > self.limit):
            logger.debug(
                f"Waiting for {round((self.interval - (now - self.last_call))/1000, 2)} seconds"
            )
            time.sleep((self.interval - (now - self.last_call)) / 1000)
            self.uses = 0
        self.last_call = time.time()


secondRateLimit = RateLimit(20, 1000)
twoMinuteRateLimit = RateLimit(100, 120000)

ROUTING = {
    "br1": "americas",
    "eun1": "europe",
    "euw1": "europe",
    "jp1": "asia",
    "kr": "asia",
    "la1": "americas",
    "la2": "americas",
    "na1": "americas",
    "oc1": "americas",
    "ru": "europe",
    "tr1": "europe",
}

FORMAT = "%(asctime)s %(levelname)s - %(message)s"
logging.basicConfig(format=FORMAT)
logger = logging.getLogger("main")
logger.setLevel(logging.INFO)


@click.command()
# @click.option('--count', default=1, help='Number of greetings.')
@click.option(
    "--server",
    prompt="What is the server?",
    required=True,
    help="Specifies the server region to query",
)
@click.option(
    "--summonername",
    prompt="What is the summoner name?",
    required=True,
    help="Specifies the summoner to query for",
)
@click.option(
    "--apikey",
    prompt="What is the API key?",
    required=True,
    help="Specifies the API key",
)
@click.option(
    "--verbose",
    default=False,
    is_flag=True,
    help="Specifies whether additional information should be given out",
)
def main(server, summonername, apikey, verbose):
    if verbose:
        logger.setLevel(logging.DEBUG)
    try:
        summoner = getSummoner(server, summonername, apikey)
        logger.info(f"Found Summoner '{summoner.name}' with puuid '{summoner.puuid}'")
    except Exception as e:
        logger.error(f'Failed to get summoner: {e}')
        return
    try:
        matches = getMatches(server, summoner.puuid, apikey)
        logger.info(f"Found {len(matches)} matches")
    except Exception as e:
        logger.error(f"Failed to get matches: {e}")
        return
    try:
        hours = asyncio.run(sumDurationAsHours(server, matches, apikey))
    except Exception as e:
        logger.error(f"Failed to sum time: {e}")
        return
    formattedHours = formatHours(hours)
    click.echo(f"{summoner.name} has played League Of Legends for {formattedHours}")


def check_ratelimit():
    secondRateLimit.Wait()
    twoMinuteRateLimit.Wait()


def formatHours(hours):
    hours = round(hours, 5)
    minutes = (hours % 1) * 60
    seconds = int((minutes % 1) * 60)
    hours = int(hours)
    minutes = int(minutes)
    return f"{hours}h {minutes}m {seconds}s"

async def sumDurationAsHours(server, matches, apikey):
    logger.info(
        f"Starting to sum {len(matches)} match durations"
    )
        
    async with aiohttp.ClientSession() as session:
        duration = 0
        tasks = []
        if len(matches) > 98:
            # If they've got a lot of matches, we'll end up subject to the 2 minute rate limit and have to go very slow.
            estimatedTime = formatHours(len(matches) * ((120/95)/3600))
            logger.info(
                f"Due to rate limits, this will take {estimatedTime} to complete"
            )
            for index, match in enumerate(matches):
                if index % 20 == 0 and index != 0:
                    estimatedTime = formatHours((len(matches) - index) * (120/95)/3600)
                    logger.info(
                        f"Processed {index}/{len(matches)} matches. {estimatedTime} left"
                    )
                await asyncio.sleep(120/95) #We can do 100 requests/120 seconds. Best to wait to avoid angering the API gods
                tasks.append(asyncio.ensure_future(getMatchDurationAsync(session, match, server, apikey)))
        else: 
            # Otherwise, we're only going to be subject to the 1 minute rate limit
            for index, match in enumerate(matches):
                if index % 20 == 0 and index != 0:
                    logger.info(
                        f"Processed {index}/{len(matches)} matches."
                    )
                await asyncio.sleep(1/19) #We can do 20 requests/1 second. Best to wait to avoid angering the API gods
                tasks.append(asyncio.ensure_future(getMatchDurationAsync(session, match, server, apikey)))

        times = await asyncio.gather(*tasks)
        for time in times:
            duration += int(time)
    return duration / 3600

async def getMatchDurationAsync(session, matchid, server, apikey) -> int:
    logger.debug(f"Querying match '{matchid}' in server region '{server}'")
    routing = ROUTING[server.lower()]
    url = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/{matchid}"
    headers = {"X-Riot-Token": apikey}
    async with session.get(url=url, headers=headers) as resp:
        if resp.status == 429:
            logger.debug(f"Rate limit exceeded. Trying again in 5 seconds")
            await asyncio.sleep(5)
            return await getMatchDurationAsync(session, matchid, server, apikey)
        response = await resp.json()
        gameDuration = int(response["info"]["gameDuration"])
        if "gameEndTimestamp" in response["info"]:
            return gameDuration
        else:
            return gameDuration / 1000

async def asyncGet(url, headers):
    async with aiohttp.ClientSession() as session:
        async with session.get(url=url, headers=headers, raise_for_status=True) as resp:
            response = await resp.json()
            return response

def getMatches(server, puuid, apikey):
    logger.debug(f"Querying matches for puuid '{puuid}' in server region '{server}'")
    routing = ROUTING[server.lower()]
    nextIndex = 0
    headers = {"X-Riot-Token": apikey}
    matches = []

    while True:
        check_ratelimit()
        url = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start={nextIndex}&count=100"
        apiResponse = asyncio.run(asyncGet(url, headers))
        logger.debug(f"Response: {apiResponse}")
        matches.extend(apiResponse)
        if len(apiResponse) != 100:
            break
        else:
            nextIndex += 100
    return matches


def getSummoner(server, summonername, apikey):
    logger.debug(f"Querying summoner '{summonername}' in server region '{server}'")
    url = f"https://{server}.api.riotgames.com/lol/summoner/v4/summoners/by-name/{summonername}"
    headers = {"X-Riot-Token": apikey}
    check_ratelimit()
    apiResponse = asyncio.run(asyncGet(url, headers))
    return Summoner(apiResponse["name"], apiResponse["puuid"])


if __name__ == "__main__":
    main()
