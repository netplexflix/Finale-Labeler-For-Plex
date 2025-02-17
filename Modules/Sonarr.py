import os
import sys
import yaml
import re
import time
import datetime
from datetime import timedelta, datetime as dt
from pathlib import Path
from path_handler import PathHandler

# Set up logging
script_name = os.path.splitext(os.path.basename(__file__))[0]
logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Logs", script_name)
os.makedirs(logs_dir, exist_ok=True)
log_file = os.path.join(logs_dir, f"log_{dt.now().strftime('%Y%m%d_%H%M%S')}.txt")

class Logger:
    def __init__(self, log_file):
        self.terminal = sys.stdout
        self.log = open(log_file, "a", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)

    def flush(self):
        self.terminal.flush()
        self.log.flush()

sys.stdout = Logger(log_file)
sys.stderr = Logger(log_file)

def clean_old_logs():
    log_files = sorted(
        [os.path.join(logs_dir, f) for f in os.listdir(logs_dir) if f.startswith("log_")],
        key=os.path.getmtime
    )
    while len(log_files) > 31:
        os.remove(log_files.pop(0))

clean_old_logs()

import requests
try:
    from plexapi.server import PlexServer
except ImportError:
    print("ERROR: python-plexapi is not installed. Run: pip install plexapi")
    sys.exit(1)
	
# ANSI color codes
GREEN = '\033[32m'
ORANGE = '\033[33m'
BLUE = '\033[34m'
RED = '\033[31m'
RESET = '\033[0m'

def normalize_sonarr_url(url):
    url = url.rstrip('/')
    
    if not url.endswith('/api/v3'):
        if url.endswith('/sonarr'):
            url = f"{url}/api/v3"
        elif '/sonarr' not in url:
            url = f"{url}/api/v3"
    
    return url

def load_config():
    current_dir = Path(__file__).parent
    config_path = current_dir.parent / "config.yml"
    try:
        with open(config_path, "r") as file:
            config = yaml.safe_load(file)
            
            if 'sonarr' in config and 'url' in config['sonarr']:
                config['sonarr']['url'] = normalize_sonarr_url(config['sonarr']['url'])
            else:
                print(f"{RED}ERROR: Sonarr URL not found in config.yml. Please check your configuration.{RESET}")
                sys.exit(1)
                
            if not config['sonarr'].get('api_key'):
                print(f"{RED}ERROR: Sonarr API key not found in config.yml. Please check your configuration.{RESET}")
                sys.exit(1)
            
            global path_handler
            path_handler = PathHandler(config)
            return config
    except FileNotFoundError:
        print(f"{RED}ERROR: Could not find config.yml at {config_path}.{RESET}")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"{RED}ERROR: Invalid YAML format in config.yml: {str(e)}{RESET}")
        sys.exit(1)
    except Exception as e:
        print(f"{RED}ERROR: An error occurred while loading config.yml: {str(e)}{RESET}")
        sys.exit(1)

config = load_config()

# Extract configurations
SONARR_URL = config['sonarr']['url']
SONARR_API_KEY = config['sonarr']['api_key']

PLEX_URL = config['plex']['url']
PLEX_TOKEN = config['plex']['token']
PLEX_LIBRARY_TITLE = config['plex']['library_title']

RECENT_DAYS = config['general']['recent_days']
SKIP_UNMONITORED = config['general']['skip_unmonitored']
SKIP_GENRES = config['general']['skip_genres']
GENRES_TO_SKIP = config['general']['genres_to_skip']
SKIP_LABELS = config['general']['skip_labels']
LABELS_TO_SKIP = config['general']['labels_to_skip']
LABEL_SERIES_IN_PLEX = config['general']['label_series_in_plex']
LABEL_EPISODE_IN_PLEX = config['general']['label_episode_in_plex']
PLEX_LABEL = config['general']['plex_label']
REMOVE_LABELS_IF_NO_LONGER_MATCHED = config['general']['remove_labels_if_no_longer_matched']
ONLY_FINALE_UNWATCHED = config['general']['only_finale_unwatched']

# ----------------------#
#  Sonarr Finale Logic  #
# ----------------------#
def get_sonarr_series():
    try:
        url = f"{SONARR_URL}/series?apikey={SONARR_API_KEY}"
        resp = requests.get(url, timeout=10)
        
        if resp.status_code == 401:
            print(f"{RED}ERROR: Invalid API key for Sonarr. Please check your config.yml{RESET}")
            sys.exit(1)
        elif resp.status_code == 404:
            print(f"{RED}ERROR: Sonarr API not found at {SONARR_URL}. Please check your URL configuration.{RESET}")
            sys.exit(1)
        elif resp.status_code != 200:
            print(f"{RED}ERROR: Sonarr returned status code {resp.status_code}{RESET}")
            sys.exit(1)
            
        try:
            return resp.json()
        except requests.exceptions.JSONDecodeError:
            print(f"{RED}ERROR: Invalid response from Sonarr. Please check if your Sonarr URL is correct.{RESET}")
            print(f"URL used: {url}")
            sys.exit(1)
            
    except requests.exceptions.ConnectionError:
        print(f"{RED}ERROR: Could not connect to Sonarr at {SONARR_URL}{RESET}")
        print("Please check:")
        print("1. If Sonarr is running")
        print("2. If the URL in config.yml is correct")
        print("3. If you can access Sonarr in your browser")
        sys.exit(1)
    except requests.exceptions.Timeout:
        print(f"{RED}ERROR: Connection to Sonarr timed out. Please check if Sonarr is responding.{RESET}")
        sys.exit(1)
    except Exception as e:
        print(f"{RED}ERROR: Unexpected error while connecting to Sonarr: {str(e)}{RESET}")
        sys.exit(1)

def get_sonarr_episodes(series_id):
    url = f"{SONARR_URL}/episode?seriesId={series_id}&apikey={SONARR_API_KEY}"
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json()

def is_episode_downloaded(season_number, episode_number, series_id):
    url = f"{SONARR_URL}/episodefile?seriesId={series_id}&apikey={SONARR_API_KEY}"
    resp = requests.get(url)
    if resp.status_code == 400:
        return False
    resp.raise_for_status()

    episode_files = resp.json()
    needle = f"s{season_number:02d}e{episode_number:02d}"
    for ef in episode_files:
        relative_path = path_handler.map_path(ef.get('relativePath', ''))
        if needle in relative_path.lower() and ef.get('size', 0) > 0:
            return True
    return False

def get_recent_finales():
    cutoff_date = dt.now() - timedelta(days=RECENT_DAYS)
    finales_downloaded = []
    finales_not_downloaded = []

    all_series = get_sonarr_series()
    for s in all_series:
        if SKIP_UNMONITORED and not s.get('monitored', True):
            continue

        episodes = get_sonarr_episodes(s['id'])
        if not episodes:
            continue

        valid_seasons = [e['seasonNumber'] for e in episodes if e.get('seasonNumber', 0) > 0]
        if not valid_seasons:
            continue
        last_season = max(valid_seasons)

        season_map = {}
        for e in episodes:
            snum = e.get('seasonNumber', 0)
            if snum > 0:
                season_map.setdefault(snum, []).append(e)

        for snum, eps in season_map.items():
            if not eps:
                continue
            last_ep = max(eps, key=lambda x: x['episodeNumber'])
            air_date_utc = last_ep.get('airDateUtc')
            if not air_date_utc:
                continue

            try:
                air_date = dt.fromisoformat(air_date_utc.rstrip('Z'))
            except ValueError:
                print(f"{RED}ERROR: Invalid airDateUtc format for episode '{last_ep.get('title', 'N/A')}' in show '{s.get('title', 'N/A')}'{RESET}")
                continue

            tmdb_id = s.get('tmdbId', 'N/A')
            imdb_id = s.get('imdbId', 'N/A')
            monitored = s.get('monitored', False)

            if snum == last_season:
                if cutoff_date <= air_date <= dt.now():
                    downloaded = is_episode_downloaded(last_ep['seasonNumber'], last_ep['episodeNumber'], s['id'])
                    if downloaded:
                        finales_downloaded.append((
                            s['title'], snum, last_ep['episodeNumber'], last_ep['title'],
                            air_date.date(), tmdb_id, imdb_id, monitored
                        ))
                    else:
                        finales_not_downloaded.append((
                            s['title'], snum, last_ep['episodeNumber'], last_ep['title'],
                            air_date.date(), tmdb_id, imdb_id, monitored
                        ))
                elif air_date > dt.now():
                    downloaded = is_episode_downloaded(last_ep['seasonNumber'], last_ep['episodeNumber'], s['id'])
                    if downloaded:
                        finales_downloaded.append((
                            s['title'], snum, last_ep['episodeNumber'], last_ep['title'],
                            air_date.date(), tmdb_id, imdb_id, monitored, True
                        ))

    return finales_downloaded, finales_not_downloaded

# --------------------#
#   Plex Connection   #
# --------------------#
def connect_plex():
    try:
        plex = PlexServer(PLEX_URL, PLEX_TOKEN)
        return plex.library.section(PLEX_LIBRARY_TITLE)
    except Exception as e:
        print(f"{RED}ERROR: Failed to connect to Plex: {e}{RESET}")
        sys.exit(1)

def build_plex_id_map(plex_shows):
    id_map = {}
    for show_obj in plex_shows:
        try:
            show_obj = show_obj.reload()
        except Exception as e:
            print(f"{RED}ERROR: Failed to reload show '{show_obj.title}': {e}{RESET}")
            continue

        for guid in show_obj.guids:
            raw_id = guid.id.lower()
            if raw_id.startswith("imdb://"):
                imdb_clean = raw_id.split("imdb://", 1)[1].split("?")[0]
                id_map[("imdb", imdb_clean)] = show_obj
            elif raw_id.startswith("tmdb://"):
                tmdb_clean = raw_id.split("tmdb://", 1)[1].split("?")[0]
                id_map[("tmdb", tmdb_clean)] = show_obj

    return id_map

def get_plex_show_by_ids(imdb_id, tmdb_id, show_map):
    if imdb_id and str(imdb_id).lower() != "n/a":
        candidate = ("imdb", str(imdb_id).lower())
        if candidate in show_map:
            return show_map[candidate]
    if tmdb_id and str(tmdb_id).lower() != "n/a":
        candidate = ("tmdb", str(tmdb_id).lower())
        if candidate in show_map:
            return show_map[candidate]
    return None

def skip_show_for_genre(show_obj, genres_to_skip):
    show_genres_lower = [genre.tag.lower() for genre in show_obj.genres]
    skip_genres_lower = [g.lower() for g in genres_to_skip]
    for sg in skip_genres_lower:
        if sg in show_genres_lower:
            return True
    return False

def skip_show_for_labels(show_obj, labels_to_skip):
    current_labels = [lab.tag.lower() for lab in show_obj.labels]
    labels_to_skip_lower = [label.lower() for label in labels_to_skip]
    for label in labels_to_skip_lower:
        if label in current_labels:
            return True
    return False

def filter_out_plex_genres_and_labels(finales_list, show_map, skip_genres, skip_labels, genres_to_skip, labels_to_skip):
    filtered = []
    for finale in finales_list:
        if len(finale) == 9:
            _, snum, enum, _, _, tmdb_id, imdb_id, _, _ = finale
        elif len(finale) == 8:
            _, snum, enum, _, _, tmdb_id, imdb_id, _ = finale

        plex_show = get_plex_show_by_ids(imdb_id, tmdb_id, show_map)
        if plex_show:
            if skip_genres and skip_show_for_genre(plex_show, genres_to_skip):
                continue
            if skip_labels and skip_show_for_labels(plex_show, labels_to_skip):
                continue
        filtered.append(finale)
    return filtered

def filter_shows_with_one_unwatched(finales_list, show_map):
    filtered = []
    for finale in finales_list:
        if len(finale) == 9:
            title, snum, enum, ep_title, air_date, tmdb_id, imdb_id, monitored, _ = finale
        elif len(finale) == 8:
            title, snum, enum, ep_title, air_date, tmdb_id, imdb_id, monitored = finale

        plex_show = get_plex_show_by_ids(imdb_id, tmdb_id, show_map)
        if plex_show:
            try:
                season_obj = plex_show.season(snum)
                if not season_obj:
                    continue

                try:
                    finale_ep = season_obj.episode(enum)
                except Exception:
                    continue

                if finale_ep.isWatched:
                    continue

                all_others_watched = all(ep.isWatched for ep in season_obj.episodes() if ep != finale_ep)

                if all_others_watched:
                    filtered.append(finale)
            except Exception:
                continue

    return filtered

# -------------------------------#
#   Label Add/Remove Functions   #
# -------------------------------#
def add_label_to_show(show_obj, label):
    current_labels = [lab.tag for lab in show_obj.labels]
    if label in current_labels:
        print(f"{GREEN}={RESET} Label '{label}' already exists for show '{show_obj.title}', skipping.")
        return
    print(f"{ORANGE}+{RESET} Adding label '{label}' to show '{show_obj.title}'")
    show_obj.addLabel(label)
    show_obj.reload()

def remove_label_if_present(show_obj, label):
    current_labels = [lab.tag for lab in show_obj.labels]
    if label in current_labels:
        print(f"{RED}-{RESET} Removing label '{label}' from show '{show_obj.title}'")
        show_obj.removeLabel(label)
        show_obj.reload()

def remove_label_from_all_shows(label):
    plex = PlexServer(PLEX_URL, PLEX_TOKEN)
    tv_library = plex.library.section(PLEX_LIBRARY_TITLE)
    shows = tv_library.all()

    for show_obj in shows:
        if label in [lab.tag for lab in show_obj.labels]:
            remove_label_if_present(show_obj, label)

def remove_label_only_unmatched(finales_downloaded, label):
    print("\nChecking for Show labels to be removed..")
    plex = PlexServer(PLEX_URL, PLEX_TOKEN)
    tv_library = plex.library.section(PLEX_LIBRARY_TITLE)
    shows = tv_library.all()
    show_map = build_plex_id_map(shows)

    matched_shows_set = set()
    for f in finales_downloaded:
        if len(f) == 9:
            _, snum, enum, _, _, tmdb_id, imdb_id, _, _ = f
        elif len(f) == 8:
            _, snum, enum, _, _, tmdb_id, imdb_id, _ = f
        plex_show = get_plex_show_by_ids(imdb_id, tmdb_id, show_map)
        if plex_show:
            matched_shows_set.add(plex_show)

    for sh in shows:
        if label in [lab.tag for lab in sh.labels]:
            if sh not in matched_shows_set:
                remove_label_if_present(sh, label)

def matched_shows(finales_downloaded, label):
    print("Checking for Show labels to be added..")
    plex = PlexServer(PLEX_URL, PLEX_TOKEN)
    tv_library = plex.library.section(PLEX_LIBRARY_TITLE)
    shows = tv_library.all()
    show_map = build_plex_id_map(shows)

    matched = set()
    for f in finales_downloaded:
        if len(f) == 9:
            _, snum, enum, _, _, tmdb_id, imdb_id, _, _ = f
        elif len(f) == 8:
            _, snum, enum, _, _, tmdb_id, imdb_id, _ = f
        plex_show = get_plex_show_by_ids(imdb_id, tmdb_id, show_map)
        if plex_show:
            matched.add(plex_show)

    for s in matched:
        add_label_to_show(s, label)

# -------------------------------#
#   Episode labelling (writer)   #
# -------------------------------#
def add_writer_to_episode(episode_obj, label, show_title=None):
    current_writers = [writer.tag for writer in episode_obj.writers]
    if label in current_writers:
        print(f"{GREEN}={RESET} Writer '{label}' already exists for S{episode_obj.seasonNumber:02d}E{episode_obj.index:02d} for show '{show_title or episode_obj.show().title}'")
        return
    print(f"{ORANGE}+{RESET} Adding writer '{label}' to S{episode_obj.seasonNumber:02d}E{episode_obj.index:02d} for show '{show_title or episode_obj.show().title}'")
    episode_obj.addWriter(label)
    episode_obj.reload()

def remove_writer_from_episode(episode_obj, label, show_title=None):
    current_writers = [writer.tag for writer in episode_obj.writers]
    if label in current_writers:
        print(f"{RED}-{RESET} Removing writer '{label}' from S{episode_obj.seasonNumber:02d}E{episode_obj.index:02d} for show '{show_title or episode_obj.show().title}'")
        episode_obj.removeWriter(label)
        episode_obj.reload()

def remove_writer_from_unmatched_episodes(finales_downloaded, label):
    print("\nChecking for Episode labels to be removed..")
    
    plex = PlexServer(PLEX_URL, PLEX_TOKEN)
    tv_library = plex.library.section(PLEX_LIBRARY_TITLE)
    shows = tv_library.all()
    show_map = build_plex_id_map(shows)

    matched_episodes = set()
    for finale in finales_downloaded:
        if len(finale) == 9:
            _, snum, enum, _, _, tmdb_id, imdb_id, _, _ = finale
        elif len(finale) == 8:
            _, snum, enum, _, _, tmdb_id, imdb_id, _ = finale

        plex_show = get_plex_show_by_ids(imdb_id, tmdb_id, show_map)
        if plex_show:
            matched_episodes.add((plex_show.ratingKey, snum, enum))

    processed = set()

    for show in shows:
        show = show.reload()
        
        labeled_episodes = []
        for episode in show.episodes():
            if label in [writer.tag for writer in episode.writers]:
                labeled_episodes.append(episode)

        for episode in labeled_episodes:
            episode_key = (show.ratingKey, episode.seasonNumber, episode.index)
            
            if episode_key in processed:
                continue
                
            if episode_key not in matched_episodes:
                remove_writer_from_episode(episode, label, show.title)
                processed.add(episode_key)

def label_matched_episodes(finales_downloaded, label):
    print("\nChecking for Episode labels to be added..")
    plex = PlexServer(PLEX_URL, PLEX_TOKEN)
    tv_library = plex.library.section(PLEX_LIBRARY_TITLE)
    shows = tv_library.all()
    show_map = build_plex_id_map(shows)

    for finale in finales_downloaded:
        if len(finale) == 9:
            _, snum, enum, _, _, tmdb_id, imdb_id, _, _ = finale
        elif len(finale) == 8:
            _, snum, enum, _, _, tmdb_id, imdb_id, _ = finale

        plex_show = get_plex_show_by_ids(imdb_id, tmdb_id, show_map)
        if plex_show:
            try:
                episode = plex_show.episode(season=snum, episode=enum)
                add_writer_to_episode(episode, label)
            except Exception as e:
                print(f"{RED}ERROR: Failed to label episode S{snum:02d}E{enum:02d} for {plex_show.title}: {str(e)}{RESET}")

# -------------------------------#
#       Handle label logic       #
# -------------------------------#
def handle_label_logic(finales_downloaded):
    # Handle show-level labels
    if not LABEL_SERIES_IN_PLEX:
        if REMOVE_LABELS_IF_NO_LONGER_MATCHED:
            remove_label_from_all_shows(PLEX_LABEL)
    else:
        matched_shows(finales_downloaded, PLEX_LABEL)
        if REMOVE_LABELS_IF_NO_LONGER_MATCHED:
            remove_label_only_unmatched(finales_downloaded, PLEX_LABEL)

    # Handle episode-level labels
    if LABEL_EPISODE_IN_PLEX:
        label_matched_episodes(finales_downloaded, PLEX_LABEL)
        if REMOVE_LABELS_IF_NO_LONGER_MATCHED:
            remove_writer_from_unmatched_episodes(finales_downloaded, PLEX_LABEL)
    else:
        if REMOVE_LABELS_IF_NO_LONGER_MATCHED:
            remove_writer_from_unmatched_episodes([], PLEX_LABEL) 

# -----------------#
#   TERMINAL RUN   #
# -----------------#
if __name__ == "__main__":
    start_time = time.time()

    def color_bool_generic(val):
        return f"{GREEN}True{RESET}" if val else f"{ORANGE}False{RESET}"

    def color_bool_label_in_plex():
        if LABEL_SERIES_IN_PLEX:
            return f"{GREEN}True{RESET} ({PLEX_LABEL})"
        else:
            return f"{ORANGE}False{RESET}"

    def color_bool_label_episode_in_plex():
        if LABEL_EPISODE_IN_PLEX:
            return f"{GREEN}True{RESET} ({PLEX_LABEL})"
        else:
            return f"{ORANGE}False{RESET}"
		
    def color_bool_remove_labels():
        if REMOVE_LABELS_IF_NO_LONGER_MATCHED:
            return f"{GREEN}True{RESET}"
        else:
            return f"{ORANGE}False{RESET}"

    def color_bool_skip_genres():
        if SKIP_GENRES:
            return f"{GREEN}True{RESET} ({', '.join(GENRES_TO_SKIP)})"
        else:
            return f"{ORANGE}False{RESET}"

    def color_bool_skip_labels():
        if SKIP_LABELS:
            return f"{GREEN}True{RESET} ({', '.join(LABELS_TO_SKIP)})"
        else:
            return f"{ORANGE}False{RESET}"

    def color_bool_only_finale_unwatched():
        return f"{GREEN}True{RESET}" if ONLY_FINALE_UNWATCHED else f"{ORANGE}False{RESET}"

    # Print configuration summary
    print("\n=== Configuration ===")
    print(f"Recent Days: {RECENT_DAYS}")
    print(f"Skip Unmonitored: {color_bool_generic(SKIP_UNMONITORED)}")
    print(f"Skip Genres: {color_bool_skip_genres()}")
    print(f"Skip Labels: {color_bool_skip_labels()}")
    print(f"Label Show in Plex: {color_bool_label_in_plex()}")
    print(f"Label Episode in Plex: {color_bool_label_episode_in_plex()}")
    print(f"Remove Labels if No Longer Matched: {color_bool_remove_labels()}")
    print(f"Only Finale Unwatched: {color_bool_only_finale_unwatched()}")
    print("====================\n")
    print("Searching for finales...")

    # Fetch recent finales from Sonarr
    finales_downloaded, finales_not_downloaded = get_recent_finales()

    # Connect to Plex and build show map
    plex_section = connect_plex()
    all_plex_shows = plex_section.all()
    show_map = build_plex_id_map(all_plex_shows)

    # If skipping genres or labels, filter out based on genres and labels
    if SKIP_GENRES or SKIP_LABELS:
        filtered_downloaded = filter_out_plex_genres_and_labels(
            finales_downloaded, show_map, SKIP_GENRES, SKIP_LABELS, GENRES_TO_SKIP, LABELS_TO_SKIP
        )
        filtered_not_downloaded = filter_out_plex_genres_and_labels(
            finales_not_downloaded, show_map, SKIP_GENRES, SKIP_LABELS, GENRES_TO_SKIP, LABELS_TO_SKIP
        )
    else:
        filtered_downloaded = finales_downloaded
        filtered_not_downloaded = finales_not_downloaded

    # Apply the new filter if enabled
    if ONLY_FINALE_UNWATCHED:
        filtered_downloaded = filter_shows_with_one_unwatched(filtered_downloaded, show_map)
        filtered_not_downloaded = filter_shows_with_one_unwatched(filtered_not_downloaded, show_map)

    # Print results
    if not filtered_downloaded and not filtered_not_downloaded:
        print(BLUE + f"No finales aired in the last {RECENT_DAYS} days (or all were skipped by genre, label, and unwatched condition)." + RESET)
    else:
        if filtered_downloaded:
            print(GREEN + f"=== Downloaded Finales in the Last {RECENT_DAYS} Days ({len(filtered_downloaded)}) ===" + RESET)
            for finale in filtered_downloaded:
                if len(finale) == 9:
                    title, snum, enum, ep_title, air_date, tmdb_id, imdb_id, monitored, is_future = finale
                    if is_future:
                        line = (f"- {title}: Season {snum} Episode {enum} '{ep_title}' "
                                f"{BLUE}will air on {air_date}{RESET}")
                    else:
                        line = (f"- {title}: Season {snum} Episode {enum} '{ep_title}' aired on {air_date} ")
                elif len(finale) == 8:
                    title, snum, enum, ep_title, air_date, tmdb_id, imdb_id, monitored = finale
                    line = (f"- {title}: Season {snum} Episode {enum} '{ep_title}' aired on {air_date} ")
                if not monitored and not SKIP_UNMONITORED:
                    line += f" {BLUE}(UNMONITORED){RESET}"
                print(line)

        if filtered_not_downloaded:
            print(ORANGE + f"\n=== Not Downloaded Finales in the Last {RECENT_DAYS} Days ({len(filtered_not_downloaded)}) ===" + RESET)
            for finale in filtered_not_downloaded:
                if len(finale) == 9:
                    title, snum, enum, ep_title, air_date, tmdb_id, imdb_id, monitored, is_future = finale
                    if is_future:
                        line = (f"- {title}: Season {snum} Episode {enum} '{ep_title}' "
                                f"{BLUE}will air on {air_date}{RESET}")
                    else:
                        line = (f"- {title}: Season {snum} Episode {enum} '{ep_title}' aired on {air_date} ")
                elif len(finale) == 8:
                    title, snum, enum, ep_title, air_date, tmdb_id, imdb_id, monitored = finale
                    line = (f"- {title}: Season {snum} Episode {enum} '{ep_title}' aired on {air_date} ")
                if not monitored and not SKIP_UNMONITORED:
                    line += f" {BLUE}(UNMONITORED){RESET}"
                print(line)

    print()
    print("\n=== Label Operations ===")
    handle_label_logic(filtered_downloaded)

    end_time = time.time()
    elapsed_seconds = int(end_time - start_time)
    formatted_duration = str(datetime.timedelta(seconds=elapsed_seconds))
    print(f"Runtime: {formatted_duration}\n")
