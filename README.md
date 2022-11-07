## Simple Steam game statistic correlation analysis tool

Currently in development.
A tool to correlate steam game statistics using the steam API.
Currently supports receiving the statistics from the API and storing in a file.
Currently boilerplated for game size and positive review percentage.

Tested on python 3.10.8.
#### Requirements
- A `config.json` file of form:
```json
{
    "steam_api_key": "<YOUR_STEAM_API_KEY>"
}
```
