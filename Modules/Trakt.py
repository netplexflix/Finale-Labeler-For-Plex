import requests
import os
import sys
import yaml
from plexapi.server import PlexServer
from tqdm import tqdm  # For displaying progress bars
from datetime import datetime, timedelta
import time

# ANSI color codes
GREEN = '\033[32m'
ORANGE = '\033[33m'
BLUE = '\033[34m'
RED = '\033[31m'
RESET = '\033[0m'
BOLD = '\033[1m'

# Set up logging
script_name = os.path.splitext(os.path.basename(__file__))[0]
logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Logs", script_name)
os.makedirs(logs_dir, exist_ok=True)
log_file = os.path.join(logs_dir, f"log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")

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

# Clean up old logs
def clean_old_logs():
    log_files = sorted(
        [os.path.join(logs_dir, f) for f in os.listdir(logs_dir) if f.startswith("log_")],
        key=os.path.getmtime
    )
    while len(log_files) > 31:
        os.remove(log_files.pop(0))

clean_old_logs()

# ===================================
# Load Configuration from config.yml
# ==================================
def load_config():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(current_dir, "..", "config.yml")
    try:
        with open(config_path, "r") as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        print(f"{RED}ERROR: Could not find config.yml at {config_path}.{RESET}")
        sys.exit(1)
    except Exception as e:
        print(f"{RED}ERROR: An error occurred while loading config.yml: {e}{RESET}")
        sys.exit(1)

config = load_config()

TRAKT_CLIENT_ID = config['trakt']['client_id']
TRAKT_CLIENT_SECRET = config['trakt']['client_secret']
DESIRED_EPISODE_TYPES = config['trakt']['desired_episode_types']
PLEX_URL = config['plex']['url']
PLEX_TOKEN = config['plex']['token']
PLEX_LIBRARY_TITLE = config['plex']['library_title']

RECENT_DAYS = config['general']['recent_days']
LABEL_SERIES_IN_PLEX = config['general']['label_series_in_plex']
LABEL_EPISODE_IN_PLEX = config['general']['label_episode_in_plex']
REMOVE_LABELS_IF_NO_LONGER_MATCHED = config['general']['remove_labels_if_no_longer_matched']
SKIP_GENRES = config['general']['skip_genres']
GENRES_TO_SKIP = config['general']['genres_to_skip']
SKIP_LABELS = config['general']['skip_labels']
LABELS_TO_SKIP = config['general']['labels_to_skip']
ONLY_FINALE_UNWATCHED = config['general']['only_finale_unwatched']


# ============================
# Find Finales
# ============================

def normalize_plex_label(label):
    return label.capitalize()

def connect_plex(plex_url, plex_token, library_title):
    try:
        plex = PlexServer(plex_url, plex_token)
        library = plex.library.section(library_title)
        return library, plex
    except Exception as e:
        print(f"{RED}Failed to connect to Plex: {e}{RESET}")
        exit(1)

def get_all_tv_shows(library):
    try:
        shows = library.all()
        return shows
    except Exception as e:
        print(f"{RED}Failed to retrieve TV shows from Plex: {e}{RESET}")
        return []

def get_last_episode(show):
    try:
        show.reload()

        seasons = sorted(show.seasons(), key=lambda s: s.index, reverse=True)
        if not seasons:
            return None

        last_season = seasons[0]
        episodes = sorted(last_season.episodes(), key=lambda e: e.index, reverse=True)
        if not episodes:
            return None

        last_episode = episodes[0]
        season_number = last_season.index
        episode_number = last_episode.index
        episode_title = last_episode.title

        return (season_number, episode_number, episode_title)
    except Exception as e:
        print(f"{RED}Failed to get last episode for show '{show.title}': {e}{RESET}")
        return None

def search_trakt_show(show_title, client_id):
    search_url = "https://api.trakt.tv/search/show"
    headers = {
        "Content-Type": "application/json",
        "trakt-api-version": "2",
        "trakt-api-key": client_id
    }
    params = {
        "query": show_title,
        "limit": 1,
        "extended": "full"
    }

    try:
        response = requests.get(search_url, headers=headers, params=params)
        response.raise_for_status()
        results = response.json()

        if not results:
            return None

        show = results[0]['show']
        trakt_id = show['ids'].get('trakt')
        slug = show['ids'].get('slug')
        imdb_id = show['ids'].get('imdb')
        tmdb_id = show['ids'].get('tmdb')

        return {
            'trakt_id': trakt_id,
            'slug': slug,
            'imdb_id': imdb_id,
            'tmdb_id': tmdb_id
        }

    except requests.exceptions.HTTPError as http_err:
        if http_err.response.status_code != 404:
            print(f"{RED}HTTP error occurred while searching Trakt for '{show_title}': {http_err}{RESET}")
            print(f"Response Status Code: {http_err.response.status_code}")
            print(f"Response Body: {http_err.response.text}{RESET}")
    except Exception as err:
        print(f"{RED}An error occurred while searching Trakt for '{show_title}': {err}{RESET}")

    return None

def get_episode_details(trakt_identifier, season, episode, client_id):
    if isinstance(trakt_identifier, int):
        identifier = trakt_identifier
    else:
        identifier = trakt_identifier  # Assuming slug

    api_url = f"https://api.trakt.tv/shows/{identifier}/seasons/{season}/episodes/{episode}"
    headers = {
        "Content-Type": "application/json",
        "trakt-api-version": "2",
        "trakt-api-key": client_id
    }
    params = {
        "extended": "full,images,translations,ratings"
    }

    try:
        response = requests.get(api_url, headers=headers, params=params)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        episode_details = response.json()

        episode_type = episode_details.get('episode_type')
        first_aired_str = episode_details.get('first_aired')

        if first_aired_str:
            try:
                first_aired = datetime.strptime(first_aired_str, "%Y-%m-%dT%H:%M:%S.%fZ")
            except ValueError:
                try:
                    first_aired = datetime.strptime(first_aired_str, "%Y-%m-%dT%H:%M:%SZ")
                except ValueError:
                    print(f"{RED}Unable to parse date '{first_aired_str}' for Trakt episode.{RESET}")
                    first_aired = None
        else:
            first_aired = None

        return (episode_type, first_aired)

    except requests.exceptions.HTTPError as http_err:
        if http_err.response.status_code != 404:
            print(f"{RED}HTTP error occurred while fetching episode details from Trakt: {http_err}{RESET}")
            print(f"Response Status Code: {http_err.response.status_code}")
            print(f"Response Body: {http_err.response.text}{RESET}")
    except Exception as err:
        print(f"{RED}An error occurred while fetching episode details from Trakt: {err}{RESET}")

    return None

# ============================
# Labelling logic (show)
# ============================
def add_label_to_show(show, label):
    try:
        show.reload()

        existing_labels = [lab.tag for lab in show.labels]

        if label in existing_labels:
            return False

        show.addLabel(label)
        return True

    except AttributeError:
        print(f"{RED}The 'addLabel' method does not exist for show '{show.title}'. Please verify the Plex API version and method availability.{RESET}")
    except Exception as e:
        print(f"{RED}Failed to add label '{label}' to show '{show.title}': {e}{RESET}")

    return False

def remove_label_from_show(show, label):
    try:
        show.reload()

        existing_labels = [lab.tag for lab in show.labels]

        if label not in existing_labels:
            return False


        show.removeLabel(label)
        return True

    except AttributeError:
        print(f"{RED}The 'removeLabel' method does not exist for show '{show.title}'. Please verify the Plex API version and method availability.{RESET}")
    except Exception as e:
        print(f"{RED}Failed to remove label '{label}' from show '{show.title}': {e}{RESET}")

    return False

# ============================
# Labelling logic (Episode)
# ============================
def add_writer_to_episode(episode_obj, label):
    current_writers = [writer.tag for writer in episode_obj.writers]
    if label in current_writers:
        print(f"{GREEN}= Writer '{label}' already exists for S{episode_obj.seasonNumber:02d}E{episode_obj.index:02d} for show '{episode_obj.show().title}'{RESET}")
        return False
    episode_obj.addWriter(label)
    episode_obj.reload()
    return True

def remove_writer_from_episode(episode_obj, label):
    current_writers = [writer.tag for writer in episode_obj.writers]
    if label in current_writers:
        episode_obj.removeWriter(label)
        episode_obj.reload()
        return True
    return False

# ============================
# Main
# ============================
def main():
    # Start runtime timer
    start_time = time.time()

    # Step 1: Print Configuration Variables
    print("\n=== Configuration ===")
    print(f"Recent Days: {RECENT_DAYS}")
    print(f"Desired Episode Types: {DESIRED_EPISODE_TYPES}")

    # Print Skip Genres along with Genres to Skip on the same line
    genre_color = GREEN if SKIP_GENRES else ORANGE
    print(f"Skip Genres: {genre_color}{SKIP_GENRES}{RESET}  {GENRES_TO_SKIP}")

    # Print Skip Labels along with Labels to Skip on the same line
    label_color = GREEN if SKIP_LABELS else ORANGE
    print(f"Skip Labels: {label_color}{SKIP_LABELS}{RESET}  {LABELS_TO_SKIP}")

    def print_bool_with_label(var_name, var_value, label=None):
        color = GREEN if var_value else ORANGE
        label_text = f" ({label})" if var_value and label else ""
        print(f"{var_name}: {color}{var_value}{RESET}{label_text}")

    print_bool_with_label("Label Series in Plex:", LABEL_SERIES_IN_PLEX)
    print_bool_with_label("Label Episodes in Plex:", LABEL_EPISODE_IN_PLEX)
    print_bool_with_label("Remove Labels if No Longer Matched:", REMOVE_LABELS_IF_NO_LONGER_MATCHED)
    print_bool_with_label("Only Finale Unwatched:", ONLY_FINALE_UNWATCHED)
    print("====================\n")

    # Step 2: Connect to Plex and retrieve the library section
    library, plex = connect_plex(PLEX_URL, PLEX_TOKEN, PLEX_LIBRARY_TITLE)
    if not library:
        print("Cannot proceed without a valid library section.")
        return

    # Step 3: Get all TV shows in the Plex library
    shows = get_all_tv_shows(library)
    if not shows:
        print("No TV shows found in the library.")
        return

    print(f"Found {len(shows)} TV shows in the library '{PLEX_LIBRARY_TITLE}'.\n")

    # Step 4: Define the cutoff date for past episodes
    cutoff_past = datetime.now() - timedelta(days=RECENT_DAYS)

    # Step 5: Iterate through each show to find the last episode and its episode_type
    qualifying_shows = []
    labels_added = []
    labels_existed = []
    labels_removed = []
    episode_labels_added = []
    episode_labels_existed = []
    episode_labels_removed = []
    episodes_to_label = []

    for show in tqdm(shows, desc="Processing Shows", bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]'):
        show_title = show.title
        # Reload the show to ensure the latest labels and metadata are fetched
        try:
            show.reload()
        except Exception as e:
            continue

        # Apply Skipping Logic
        if SKIP_GENRES:
            show_genres = [genre.tag for genre in show.genres] if show.genres else []
            show_genres = [genre.strip() for genre in show_genres]
            if any(genre in GENRES_TO_SKIP for genre in show_genres):
                continue

        if SKIP_LABELS:
            show_labels = [lab.tag for lab in show.labels]
            if any(label in LABELS_TO_SKIP for label in show_labels):
                continue

        # Get the last episode details
        last_episode = get_last_episode(show)
        if not last_episode:
            continue

        season_number, episode_number, episode_title = last_episode

        # Search for the show on Trakt to get Trakt ID or slug and external IDs
        trakt_info = search_trakt_show(show_title, TRAKT_CLIENT_ID)
        if not trakt_info:
            continue

        trakt_id = trakt_info['trakt_id']
        trakt_slug = trakt_info['slug']
        imdb_id = trakt_info.get('imdb_id')
        tmdb_id = trakt_info.get('tmdb_id')

        # Fetch episode_type and first_aired from Trakt
        episode_details = get_episode_details(trakt_slug, season_number, episode_number, TRAKT_CLIENT_ID)
        if not episode_details:
            continue

        episode_type, first_aired = episode_details

        # Validate first_aired
        if not first_aired:
            continue

        # Determine if the episode has already aired or will air
        if first_aired <= datetime.now():
            if first_aired < cutoff_past:
                continue
            air_status = f"aired on {first_aired.strftime('%Y-%m-%d')}"
        else:
            air_status = f"{BLUE}will air on{RESET} {first_aired.strftime('%Y-%m-%d')}"

        # Check if episode_type is one of the desired types
        if episode_type and episode_type.lower() in [etype.lower() for etype in DESIRED_EPISODE_TYPES]:
            # Handle ONLY_FINALE_UNWATCHED check
            if ONLY_FINALE_UNWATCHED:
                try:
                    season_obj = show.season(season_number)
                    if not season_obj:
                        continue

                    finale_ep = season_obj.episode(episode_number)
                    if finale_ep.isWatched:
                        continue

                    all_others_watched = all(ep.isWatched for ep in season_obj.episodes() if ep != finale_ep)
                    if not all_others_watched:
                        continue
                except Exception:
                    continue

            # Add to qualifying shows
            qualifying_shows.append({
                "title": show_title,
                "season": season_number,
                "episode": episode_number,
                "episode_title": episode_title,
                "episode_type": episode_type,
                "air_status": air_status,
                "imdb_id": imdb_id,
                "tmdb_id": tmdb_id
            })

            # Handle show-level labeling
            if LABEL_SERIES_IN_PLEX:
                label = normalize_plex_label(episode_type)
                show.reload()
                current_labels = [lab.tag.capitalize() for lab in show.labels]
                
                if label in current_labels:
                    labels_existed.append((show_title, label))
                else:
                    # Remove any existing labels from DESIRED_EPISODE_TYPES
                    labels_to_remove = [
                        lab for lab in current_labels
                        if lab in [normalize_plex_label(etype) for etype in DESIRED_EPISODE_TYPES] 
                        and lab != label
                    ]
                    for existing_label in labels_to_remove:
                        removed = remove_label_from_show(show, existing_label)
                        if removed:
                            labels_removed.append((show_title, existing_label))
                    
                    # Add the new label
                    label_added = add_label_to_show(show, label)
                    if label_added:
                        labels_added.append((show_title, label))

            # Handle episode-level labeling
            if LABEL_EPISODE_IN_PLEX:
                try:
                    episode_obj = show.episode(season=season_number, episode=episode_number)
                    episodes_to_label.append({
                        'episode': episode_obj,
                        'show_title': show_title,
                        'season': season_number,
                        'episode_num': episode_number,
                        'label': normalize_plex_label(episode_type)
                    })
                except Exception as e:
                    print(f"{RED}Error accessing episode for '{show_title}' S{season_number:02d}E{episode_number:02d}: {e}{RESET}")

        # Optional: To prevent hitting Trakt rate limits
        time.sleep(0.5)


    # Step 6: Display the qualifying shows
    if qualifying_shows:
        print(f"\n{GREEN}=== Qualifying TV Shows with Finale Episodes === {RESET}")
        for item in qualifying_shows:
            imdb_display = item['imdb_id'] if item['imdb_id'] else "N/A"
            tmdb_display = item['tmdb_id'] if item['tmdb_id'] else "N/A"
            print(f"{item['title']} "
                  f"Season {item['season']} Episode {item['episode']} '{item['episode_title']}' "
                  f"({item['episode_type']}) {item['air_status']}")
    else:
        print(f"\n{BLUE}No TV shows found matching criteria.{RESET}")
        print("========================\n")

    # Step 7: Display label operations
    print("\n=== Label Operations ===")
    
    # Show-level label operations
    print("Processing show-level labels...")
    if LABEL_SERIES_IN_PLEX:
        for show_data in qualifying_shows:
            try:
                show = next(s for s in shows if s.title == show_data['title'])
                label = normalize_plex_label(show_data['episode_type'])
                
                current_labels = [lab.tag.capitalize() for lab in show.labels]
                if label in current_labels:
                    print(f"{ORANGE}={RESET} Label '{label}' already exists for show '{show.title}'")
                else:
                    print(f"{GREEN}+{RESET} Adding label '{label}' to show '{show.title}'")
                    if add_label_to_show(show, label):
                        pass 
            except StopIteration:
                print(f"{RED}Error: Could not find show '{show_data['title']}' in Plex library{RESET}")
            except Exception as e:
                print(f"{RED}Error processing show '{show_data['title']}': {str(e)}{RESET}")
    elif REMOVE_LABELS_IF_NO_LONGER_MATCHED:
        for show in shows:
            show.reload()
            current_labels = [lab.tag for lab in show.labels]
            labels_to_remove = [
                lab for lab in current_labels
                if normalize_plex_label(lab) in [normalize_plex_label(etype) 
                                               for etype in DESIRED_EPISODE_TYPES]
            ]
            for label in labels_to_remove:
                if remove_label_from_show(show, label):
                    print(f"{RED}-{RESET} Removing label '{label}' from show '{show.title}'")
    
    # Episode-level label operations
    print("\nProcessing episode-level labels...")
    if LABEL_EPISODE_IN_PLEX:
        for ep_data in episodes_to_label:
            episode_obj = ep_data['episode']
            label = ep_data['label']
            
            current_writers = [writer.tag for writer in episode_obj.writers]
            if label in current_writers:
                print(f"{ORANGE}={RESET} Writer '{label}' already exists for S{ep_data['season']:02d}E{ep_data['episode_num']:02d} for show '{ep_data['show_title']}'")
            else:
                if add_writer_to_episode(episode_obj, label):
                    print(f"{GREEN}+{RESET} Adding writer '{label}' to S{ep_data['season']:02d}E{ep_data['episode_num']:02d} for show '{ep_data['show_title']}'")
    elif REMOVE_LABELS_IF_NO_LONGER_MATCHED:
        for show in shows:
            show.reload()
            for episode in show.episodes():
                current_writers = [writer.tag for writer in episode.writers]
                labels_to_remove = [
                    lab for lab in current_writers
                    if normalize_plex_label(lab) in [normalize_plex_label(etype) 
                                                   for etype in DESIRED_EPISODE_TYPES]
                ]
                for label in labels_to_remove:
                    if remove_writer_from_episode(episode, label):
                        print(f"{RED}-{RESET} Removing writer '{label}' from S{episode.seasonNumber:02d}E{episode.index:02d} for show '{show.title}'")
    
    # Step 8: Print runtime
    end_time = time.time()
    runtime_seconds = int(end_time - start_time)
    hours, remainder = divmod(runtime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    print(f"\nRuntime: {hours:02}:{minutes:02}:{seconds:02}")

if __name__ == "__main__":
        main()
