import requests
import os
import yaml
from plexapi.server import PlexServer
from tqdm import tqdm  # For displaying progress bars
from datetime import datetime, timedelta
import time
from colorama import init, Fore, Style

# Initialize colorama
init(autoreset=True)

# ============================
# Load Configuration from config.yml
# ============================
def load_config():
    # Determine the directory where this script resides
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Construct the path to config.yml in the parent folder
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
REMOVE_LABELS_IF_NO_LONGER_MATCHED = config['general']['remove_labels_if_no_longer_matched']
SKIP_GENRES = config['general']['skip_genres']
GENRES_TO_SKIP = config['general']['genres_to_skip']
SKIP_LABELS = config['general']['skip_labels']
LABELS_TO_SKIP = config['general']['labels_to_skip']
ONLY_FINALE_UNWATCHED = config['general']['only_finale_unwatched']


# ============================
# End of Configuration
# ============================

def normalize_plex_label(label):
    return label.capitalize()

def connect_plex(plex_url, plex_token, library_title):
    """
    Connects to the Plex server and retrieves the specified library section.
    """
    try:
        plex = PlexServer(plex_url, plex_token)
        library = plex.library.section(library_title)
        return library, plex
    except Exception as e:
        print(f"{Fore.RED}Failed to connect to Plex: {e}{Style.RESET_ALL}")
        exit(1)

def get_all_tv_shows(library):
    """
    Retrieves all TV shows from the specified Plex library section.
    """
    try:
        shows = library.all()
        return shows
    except Exception as e:
        print(f"{Fore.RED}Failed to retrieve TV shows from Plex: {e}{Style.RESET_ALL}")
        return []

def get_last_episode(show):
    """
    Determines the last episode of a TV show based on the highest season and episode numbers.
    """
    try:
        # Reload the show to ensure the latest data is fetched
        show.reload()

        # Get all seasons and sort them by season number descending
        seasons = sorted(show.seasons(), key=lambda s: s.index, reverse=True)
        if not seasons:
            return None

        last_season = seasons[0]
        # Get all episodes in the last season and sort them by episode number descending
        episodes = sorted(last_season.episodes(), key=lambda e: e.index, reverse=True)
        if not episodes:
            return None

        last_episode = episodes[0]
        season_number = last_season.index
        episode_number = last_episode.index
        episode_title = last_episode.title

        return (season_number, episode_number, episode_title)
    except Exception as e:
        print(f"{Fore.RED}Failed to get last episode for show '{show.title}': {e}{Style.RESET_ALL}")
        return None

def search_trakt_show(show_title, client_id):
    """
    Searches for a TV show on Trakt and retrieves its Trakt ID, slug, IMDb ID, and TMDB ID.
    """
    search_url = "https://api.trakt.tv/search/show"
    headers = {
        "Content-Type": "application/json",
        "trakt-api-version": "2",
        "trakt-api-key": client_id
    }
    params = {
        "query": show_title,
        "limit": 1,  # Fetch the top result
        "extended": "full"  # Get full details
    }

    try:
        response = requests.get(search_url, headers=headers, params=params)
        response.raise_for_status()
        results = response.json()

        if not results:
            return None

        # Extract the first result
        show = results[0]['show']
        trakt_id = show['ids'].get('trakt')
        slug = show['ids'].get('slug')
        imdb_id = show['ids'].get('imdb')  # Extract IMDb ID
        tmdb_id = show['ids'].get('tmdb')  # Extract TMDB ID

        return {
            'trakt_id': trakt_id,
            'slug': slug,
            'imdb_id': imdb_id,
            'tmdb_id': tmdb_id
        }

    except requests.exceptions.HTTPError as http_err:
        if http_err.response.status_code != 404:
            print(f"{Fore.RED}HTTP error occurred while searching Trakt for '{show_title}': {http_err}{Style.RESET_ALL}")
            print(f"Response Status Code: {http_err.response.status_code}")
            print(f"Response Body: {http_err.response.text}{Style.RESET_ALL}")
    except Exception as err:
        print(f"{Fore.RED}An error occurred while searching Trakt for '{show_title}': {err}{Style.RESET_ALL}")

    return None

def get_episode_details(trakt_identifier, season, episode, client_id):
    """
    Retrieves the episode_type and first_aired date of a specific episode from Trakt.
    """
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
            # Handle both 'Z' and fractional seconds
            try:
                # Example format: '2024-03-21T07:00:00.000Z'
                first_aired = datetime.strptime(first_aired_str, "%Y-%m-%dT%H:%M:%S.%fZ")
            except ValueError:
                try:
                    # Example format without milliseconds: '2024-03-21T07:00:00Z'
                    first_aired = datetime.strptime(first_aired_str, "%Y-%m-%dT%H:%M:%SZ")
                except ValueError:
                    print(f"{Fore.RED}Unable to parse date '{first_aired_str}' for Trakt episode.{Style.RESET_ALL}")
                    first_aired = None
        else:
            first_aired = None

        return (episode_type, first_aired)

    except requests.exceptions.HTTPError as http_err:
        if http_err.response.status_code != 404:
            print(f"{Fore.RED}HTTP error occurred while fetching episode details from Trakt: {http_err}{Style.RESET_ALL}")
            print(f"Response Status Code: {http_err.response.status_code}")
            print(f"Response Body: {http_err.response.text}{Style.RESET_ALL}")
    except Exception as err:
        print(f"{Fore.RED}An error occurred while fetching episode details from Trakt: {err}{Style.RESET_ALL}")

    return None

def add_label_to_show(show, label):
    """
    Adds a label to the given Plex show using the addLabel method.
    """
    try:
        # Reload the show to ensure the latest labels are fetched
        show.reload()

        # Extract label tags as strings
        existing_labels = [lab.tag for lab in show.labels]

        # Check if the label already exists
        if label in existing_labels:
            return False  # Label already exists; do nothing

        # Add the label using the addLabel method
        show.addLabel(label)
        return True  # Indicate that label was added

    except AttributeError:
        print(f"{Fore.RED}The 'addLabel' method does not exist for show '{show.title}'. Please verify the Plex API version and method availability.{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Failed to add label '{label}' to show '{show.title}': {e}{Style.RESET_ALL}")

    return False  # Indicate that label was not added

def remove_label_from_show(show, label):
    """
    Removes a label from the given Plex show using the removeLabel method.
    """
    try:
        # Reload the show to ensure the latest labels are fetched
        show.reload()

        # Extract label tags as strings
        existing_labels = [lab.tag for lab in show.labels]

        # Check if the label exists
        if label not in existing_labels:
            return False  # Label does not exist; do nothing

        # Remove the label using the removeLabel method
        show.removeLabel(label)
        return True  # Indicate that label was removed

    except AttributeError:
        print(f"{Fore.RED}The 'removeLabel' method does not exist for show '{show.title}'. Please verify the Plex API version and method availability.{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Failed to remove label '{label}' from show '{show.title}': {e}{Style.RESET_ALL}")

    return False  # Indicate that label was not removed

def main():
    # Start runtime timer
    start_time = time.time()

    # Step 1: Print Configuration Variables
    print("\n=== Configuration ===")
    print(f"Recent Days: {RECENT_DAYS}")
    print(f"Desired Episode Types: {DESIRED_EPISODE_TYPES}")

    # Print Skip Genres along with Genres to Skip on the same line
    genre_color = Fore.GREEN if SKIP_GENRES else Fore.YELLOW
    print(f"Skip Genres: {genre_color}{SKIP_GENRES}{Style.RESET_ALL}  {GENRES_TO_SKIP}")

    # Print Skip Labels along with Labels to Skip on the same line
    label_color = Fore.GREEN if SKIP_LABELS else Fore.YELLOW
    print(f"Skip Labels: {label_color}{SKIP_LABELS}{Style.RESET_ALL}  {LABELS_TO_SKIP}")

    # For the remaining boolean configuration variables, print using colors
    def print_bool(var_name, var_value):
        color = Fore.GREEN if var_value else Fore.YELLOW
        print(f"{var_name}: {color}{var_value}{Style.RESET_ALL}")

    print_bool("Label in Plex:", LABEL_SERIES_IN_PLEX)
    print_bool("Remove Labels if No Longer Matched:", REMOVE_LABELS_IF_NO_LONGER_MATCHED)
    print_bool("Only Finale Unwatched:", ONLY_FINALE_UNWATCHED)
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

    for show in tqdm(shows, desc="Processing Shows"):
        show_title = show.title
        # Reload the show to ensure the latest labels and metadata are fetched
        try:
            show.reload()
        except Exception as e:
            # Optionally log the error or handle it silently
            continue

        # Apply Skipping Logic
        if SKIP_GENRES:
            show_genres = [genre.tag for genre in show.genres] if show.genres else []
            # Clean genre names by stripping any leading/trailing whitespace
            show_genres = [genre.strip() for genre in show_genres]
            if any(genre in GENRES_TO_SKIP for genre in show_genres):
                continue  # Skip this show

        if SKIP_LABELS:
            show_labels = [lab.tag for lab in show.labels]
            if any(label in LABELS_TO_SKIP for label in show_labels):
                continue  # Skip this show

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
        imdb_id = trakt_info.get('imdb_id')  # Retrieve IMDb ID
        tmdb_id = trakt_info.get('tmdb_id')  # Retrieve TMDB ID

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
            # Episode has already aired; check if within RECENT_DAYS
            if first_aired < cutoff_past:
                continue  # Skip episodes aired before the cutoff
            air_status = f"aired on {first_aired.strftime('%Y-%m-%d')}"
        else:
            # Episode is scheduled to air in the future; include regardless of days
            air_status = f"{Fore.BLUE}will air on{Style.RESET_ALL} {first_aired.strftime('%Y-%m-%d')}"

        # Check if episode_type is one of the desired types
        if episode_type and episode_type.lower() in [etype.lower() for etype in DESIRED_EPISODE_TYPES]:
            # If ONLY_FINALE_UNWATCHED is True, check if finale is the only unwatched episode in the season
            if ONLY_FINALE_UNWATCHED:
                try:
                    # Get the specific season
                    season_obj = show.season(season_number)
                    if not season_obj:
                        continue

                    # Get the specific episode
                    try:
                        finale_ep = season_obj.episode(episode_number)
                    except Exception:
                        continue

                    # Check if the finale episode is unwatched
                    if finale_ep.isWatched:
                        continue  # Finale episode is watched, skip

                    # Check if all other episodes are watched
                    all_others_watched = all(ep.isWatched for ep in season_obj.episodes() if ep != finale_ep)

                    if not all_others_watched:
                        continue  # There are other unwatched episodes, skip
                except Exception as e:
                    # Optionally log the error or handle it silently
                    continue

            # Append to qualifying shows
            qualifying_shows.append({
                "title": show_title,
                "season": season_number,
                "episode": episode_number,
                "episode_title": episode_title,
                "episode_type": episode_type,
                "air_status": air_status,
                "imdb_id": imdb_id,   # Add IMDb ID
                "tmdb_id": tmdb_id    # Add TMDB ID
            })

            # Apply label to the show if enabled
            if LABEL_SERIES_IN_PLEX:
                # Define the label based on episode_type (normalize to Plex case behavior)
                label = normalize_plex_label(episode_type)

                # Reload the show again to ensure we get the latest labels
                show.reload()

                # Check if the desired label already exists
                current_labels = [lab.tag.capitalize() for lab in show.labels]  # Normalize to Plex capitalization
                if label in current_labels:
                    labels_existed.append((show_title, label))
                else:
                    # Remove any existing labels from DESIRED_EPISODE_TYPES but not the current label
                    labels_to_remove = [
                        lab for lab in current_labels
                        if lab in [normalize_plex_label(etype) for etype in DESIRED_EPISODE_TYPES] and lab != label
                    ]
                    for existing_label in labels_to_remove:
                        removed = remove_label_from_show(show, existing_label)
                        if removed:
                            labels_removed.append((show_title, existing_label))
                    # Add the new label
                    label_added = add_label_to_show(show, label)
                    if label_added:
                        labels_added.append((show_title, label))
        # Optional: To prevent hitting Trakt rate limits, add a short delay
        time.sleep(0.5)  # Sleep for 0.5 seconds


    # Step 6: Remove labels from shows if configured to do so
    if REMOVE_LABELS_IF_NO_LONGER_MATCHED:
        try:
            # If LABEL_SERIES_IN_PLEX is False, remove all labels in DESIRED_EPISODE_TYPES from all shows
            if not LABEL_SERIES_IN_PLEX:
                for show in shows:
                    show.reload()  # Ensure we have the latest metadata
                    current_labels = [lab.tag for lab in show.labels]
                    labels_to_remove = [
                        lab for lab in current_labels
                        if normalize_plex_label(lab) in [normalize_plex_label(etype) for etype in DESIRED_EPISODE_TYPES]
                    ]
                    for label in labels_to_remove:
                        try:
                            removed = remove_label_from_show(show, label)
                            if removed:
                                labels_removed.append((show.title, label))
                        except Exception as e:
                            print(f"{Fore.RED}Error removing label '{label}' from show '{show.title}': {e}{Style.RESET_ALL}")
            else:
                # Standard logic: Remove outdated labels for non-qualifying shows
                qualifying_show_titles = set([show['title'] for show in qualifying_shows])
                for show in shows:
                    show.reload()  # Ensure we have the latest metadata
                    current_labels = [lab.tag for lab in show.labels]
                    labels_to_remove = [
                        lab for lab in current_labels
                        if normalize_plex_label(lab) in [normalize_plex_label(etype) for etype in DESIRED_EPISODE_TYPES]
                        and show.title not in qualifying_show_titles
                    ]
                    for label in labels_to_remove:
                        try:
                            removed = remove_label_from_show(show, label)
                            if removed:
                                labels_removed.append((show.title, label))
                        except Exception as e:
                            print(f"{Fore.RED}Error removing label '{label}' from show '{show.title}': {e}{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}An error occurred while removing outdated labels: {e}{Style.RESET_ALL}")

    # Step 7: Display the qualifying shows
    if qualifying_shows:
        print(f"\n{Fore.GREEN}=== Qualifying TV Shows with Finale Episodes === {Style.RESET_ALL}")
        for item in qualifying_shows:
            imdb_display = item['imdb_id'] if item['imdb_id'] else "N/A"
            tmdb_display = item['tmdb_id'] if item['tmdb_id'] else "N/A"
            print(f"{item['title']} (TMDB: {tmdb_display}, IMDB: {imdb_display}): "
                  f"Season {item['season']} Episode {item['episode']} '{item['episode_title']}' "
                  f"({item['episode_type']}) {item['air_status']}")
    else:
        print(f"\n{Fore.BLUE}No TV shows found matching criteria.{Style.RESET_ALL}")
        print("========================\n")

    # Step 8: Display label operations
    print("\n=== Label Operations ===")

    if LABEL_SERIES_IN_PLEX or REMOVE_LABELS_IF_NO_LONGER_MATCHED:
        # Display labels added
        if labels_added:
            for title, label in labels_added:
                print(f"{Fore.GREEN}+ Added label '{label}' to show '{title}'{Style.RESET_ALL}")
        
        # Display labels that already existed
        if labels_existed:
            for title, label in labels_existed:
                print(f"{Fore.YELLOW}= Label '{label}' already exists for show '{title}'{Style.RESET_ALL}")
        
        # Display labels removed
        if labels_removed:
            for title, label in labels_removed:
                print(f"{Fore.RED}- Removed label '{label}' from show '{title}'{Style.RESET_ALL}")

    # Step 9: Print runtime
    end_time = time.time()
    runtime_seconds = int(end_time - start_time)
    hours, remainder = divmod(runtime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    print("\nRun completed")
    print(f"Runtime: {hours:02}:{minutes:02}:{seconds:02}")

if __name__ == "__main__":
        main()
