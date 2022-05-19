# leaguetimestats

A simple little script that's **heavily** inspired by [wastedonlol](https://github.com/Bios-Marcel/wastedonlol) and [wol.gg](https://wol.gg/). It sums up the time that a summoner has spent in any League match over the course of their career.

## Usage

1. Get an API key at https://developer.riotgames.com/
2. Figure out the endpoint of your account

I have no clue where to find it, but take heart! Statistically, you'll probably only have to try 6 times before you get your endpoint. Here are the possible endpoints:

- br1
- eun1
- euw1
- jp1
- kr
- la1
- la2
- na1
- oc1
- ru
- tr1

3. Install the requirements:

```shell
pip install -r .\requirements.txt
```

4. Launch the program:

```shell
python ./main.py --server="na1" --apikey="YOUR_KEY" --summonername="YOUR_SUMMONER_NAME"
```
