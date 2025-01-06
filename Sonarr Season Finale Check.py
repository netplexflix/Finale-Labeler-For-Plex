import requests
from datetime import datetime, timedelta

# Configuration
SONARR_API_KEY = 'xxxxxxx' # Set your Sonarr API key found under settings => General
SONARR_URL = 'http://localhost:8989/sonarr/api/v3' # change if needed
RECENT_DAYS = 14 # Set past timeframe within which the finale was aired. Finales with future airdates but already downloaded will be included
SKIP_UNMONITORED = True  # Set to False to disable skipping unmonitored series

# ANSI color codes
GREEN = '\033[32m'
ORANGE = '\033[33m'
BLUE = '\033[34m'
RESET = '\033[0m'

# Helper functions
def get_sonarr_series():
    url = f"{SONARR_URL}/series?apikey={SONARR_API_KEY}"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

def get_sonarr_episodes(series_id):
    url = f"{SONARR_URL}/episode?seriesId={series_id}&apikey={SONARR_API_KEY}"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

def is_episode_downloaded(season_number, episode_number, series_id):
    url = f"{SONARR_URL}/episodefile?seriesId={series_id}&apikey={SONARR_API_KEY}"
    response = requests.get(url)

    if response.status_code == 400:
        return False  # Return False immediately if the request is bad
    
    response.raise_for_status()
    episode_files = response.json()

    # Look for the filename with SxxExx pattern (e.g., S02E07)
    for episode_file in episode_files:
        filename = episode_file['relativePath'].lower()
        if f"s{season_number:02d}e{episode_number:02d}" in filename:
            size = episode_file.get('size', 0)
            if size > 0:
                return True  # The episode is downloaded
    return False  # The episode is not downloaded

def get_recent_finales():
    recent_finales_downloaded = []
    recent_finales_not_downloaded = []
    cutoff_date = datetime.now() - timedelta(days=RECENT_DAYS)
    
    for series in get_sonarr_series():
        # Skip unmonitored series if SKIP_UNMONITORED is True
        if SKIP_UNMONITORED and not series.get('monitored', True):
            continue
        
        episodes = get_sonarr_episodes(series['id'])
        if not episodes:  # Skip series with no episodes
            continue
        last_season = max(ep['seasonNumber'] for ep in episodes if 'seasonNumber' in ep and ep['seasonNumber'] > 0)
        season_episodes = {ep['seasonNumber']: [] for ep in episodes if 'seasonNumber' in ep}
        
        for ep in episodes:
            if 'seasonNumber' in ep and 'episodeNumber' in ep and ep['seasonNumber'] > 0:
                season_episodes[ep['seasonNumber']].append(ep)
        
        for season, eps in season_episodes.items():
            if not eps:  # Skip empty episode lists
                continue
            last_episode = max(eps, key=lambda e: e['episodeNumber'])
            air_date = datetime.fromisoformat(last_episode['airDateUtc'][:-1]) if last_episode.get('airDateUtc') else None
            
            # Check if air date is in the past (within the last RECENT_DAYS) or future
            if air_date and (air_date >= cutoff_date and air_date <= datetime.now()):
                # If air date is in the past, handle as usual
                download_status = is_episode_downloaded(last_episode['seasonNumber'], last_episode['episodeNumber'], series['id'])
                tmdb_id = series.get('tmdbId', 'N/A')
                imdb_id = series.get('imdbId', 'N/A')
                if series.get('status', '').lower() == 'ended' and last_episode['seasonNumber'] == last_season:
                    if download_status:
                        recent_finales_downloaded.append((series['title'], last_episode['title'], air_date.date(), tmdb_id, imdb_id, series.get('monitored', False)))
                    else:
                        recent_finales_not_downloaded.append((series['title'], last_episode['title'], air_date.date(), tmdb_id, imdb_id, series.get('monitored', False)))
                elif series.get('status', '').lower() != 'ended' and last_episode['seasonNumber'] == last_season:
                    if download_status:
                        recent_finales_downloaded.append((series['title'], last_episode['title'], air_date.date(), tmdb_id, imdb_id, series.get('monitored', False)))
                    else:
                        recent_finales_not_downloaded.append((series['title'], last_episode['title'], air_date.date(), tmdb_id, imdb_id, series.get('monitored', False)))
            elif air_date and air_date > datetime.now():  # If air date is in the future
                # If the finale episode is in the future, check if it is downloaded
                download_status = is_episode_downloaded(last_episode['seasonNumber'], last_episode['episodeNumber'], series['id'])
                if download_status and last_episode['seasonNumber'] == last_season:
                    tmdb_id = series.get('tmdbId', 'N/A')
                    imdb_id = series.get('imdbId', 'N/A')
                    # Show future finale with blue text
                    recent_finales_downloaded.append((series['title'], last_episode['title'], air_date.date(), tmdb_id, imdb_id, series.get('monitored', False), True))  # True means future episode

    return recent_finales_downloaded, recent_finales_not_downloaded

# Output results
if __name__ == "__main__":
    # Print configuration variables at the beginning
    print()  # Add break line
    print(f"Recent Days: " + GREEN + f"{RECENT_DAYS}" + RESET)
    if SKIP_UNMONITORED:
        print(f"Skip Unmonitored: " + GREEN + f"{SKIP_UNMONITORED}" + RESET)
    else:
        print(f"Skip Unmonitored: " + ORANGE + f"{SKIP_UNMONITORED}" + RESET)
    print()  # Add break line between SKIP_UNMONITORED and Downloaded Finales title
    
    finales_downloaded, finales_not_downloaded = get_recent_finales()

    # If no finales aired in the last RECENT_DAYS, show a message in blue
    if not finales_downloaded and not finales_not_downloaded:
        print(BLUE + f"No finales aired in the last {RECENT_DAYS} days." + RESET)
    else:
        # Display downloaded finales in green
        if finales_downloaded:
            print(GREEN + f"Downloaded Finales in the Last {RECENT_DAYS} Days:" + RESET)
            for finale in finales_downloaded:
                if len(finale) == 7:  # Future episode
                    title, episode_title, air_date, tmdb_id, imdb_id, monitored, is_future = finale
                    line = f"- {title}: '{episode_title}' \033[94mwill air on {air_date}\033[0m | TMDb ID: {tmdb_id} | IMDb ID: {imdb_id}"
                else:
                    title, episode_title, air_date, tmdb_id, imdb_id, monitored = finale
                    line = f"- {title}: '{episode_title}' aired on {air_date} | TMDb ID: {tmdb_id} | IMDb ID: {imdb_id}"
                if not monitored and not SKIP_UNMONITORED:
                    line += f" {BLUE}(UNMONITORED){RESET}"
                print(line)
        
        # Display not downloaded finales in orange
        if finales_not_downloaded:
            print(ORANGE + f"\nNot Downloaded Finales in the Last {RECENT_DAYS} Days:" + RESET)
            for finale in finales_not_downloaded:
                if len(finale) == 7:  # Future episode
                    title, episode_title, air_date, tmdb_id, imdb_id, monitored, is_future = finale
                    line = f"- {title}: '{episode_title}' \033[94mwill air on {air_date}\033[0m | TMDb ID: {tmdb_id} | IMDb ID: {imdb_id}"
                else:
                    title, episode_title, air_date, tmdb_id, imdb_id, monitored = finale
                    line = f"- {title}: '{episode_title}' aired on {air_date} | TMDb ID: {tmdb_id} | IMDb ID: {imdb_id}"
                if not monitored and not SKIP_UNMONITORED:
                    line += f" {BLUE}(UNMONITORED){RESET}"
                print(line)
