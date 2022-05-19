import logging
import time

import click
import requests


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
        elif now - self.last_call >= (self.interval / self.limit):
            self.uses -= 1
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
        logger.info(f"Summoner '{summoner.name}' with puuid '{summoner.puuid}' found")
    except Exception as e:
        logger.error(f"Failed to get summoner: {e}: {e.__traceback__}")
        return
    try:
        matches = getMatches(server, summoner.puuid, apikey)
        logger.info(f"{len(matches)} matches found")
    except Exception as e:
        logger.error(f"Failed to get matches: {e}: {e.__traceback__}")
        return
    try:
        hours = sumDurationAsHours(server, matches, apikey)
    except Exception as e:
        logger.error(f"Failed to sum time: {e}: {e.__traceback__}")
        return
    formattedHours = formatHours(hours)
    click.echo(f"{summoner.name} has played League Of Legends for {formattedHours}")


def check_ratelimit():
    secondRateLimit.Wait()
    twoMinuteRateLimit.Wait()


def formatHours(hours):
    hours = round(hours, 2)
    minutes = int((hours % 1) * 60)
    hours = int(hours)
    return f"{hours}h {minutes}m"


def sumDurationAsHours(server, matches, apikey):
    logger.info(
        f"Starting to sum {len(matches)} match durations (this may take a bit!)"
    )
    duration = 0

    for index, match in enumerate(matches):
        if index % 20 == 0 and index != 0:
            logger.info(
                f"Processed {index} matches, total duration: {duration} seconds. {len(matches) - index} matches left to go!"
            )
        logger.debug(f"Processing match {index}")
        duration += getMatchDuration(match, server, apikey)
    return duration / 3600


def getMatchDuration(matchid, server, apikey):
    logger.debug(f"Querying match '{matchid}' in server region '{server}'")
    routing = ROUTING[server.lower()]
    url = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/{matchid}"
    headers = {"X-Riot-Token": apikey}
    check_ratelimit()
    response = requests.get(url=url, headers=headers)
    response.raise_for_status()

    apiResponse = response.json()
    gameDuration = apiResponse["info"]["gameDuration"]
    if "gameEndTimestamp" in apiResponse["info"]:
        return gameDuration
    else:
        return gameDuration / 1000


def getMatches(server, puuid, apikey):
    logger.debug(f"Querying matches for puuid '{puuid}' in server region '{server}'")
    routing = ROUTING[server.lower()]
    nextIndex = 0
    headers = {"X-Riot-Token": apikey}
    matches = []

    while True:
        check_ratelimit()
        url = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start={nextIndex}&count=100"
        response = requests.get(url=url, headers=headers)
        response.raise_for_status()
        apiResponse = response.json()
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
    response = requests.get(url=url, headers=headers)
    response.raise_for_status()

    apiResponse = response.json()
    return Summoner(apiResponse["name"], apiResponse["puuid"])


if __name__ == "__main__":
    main()
