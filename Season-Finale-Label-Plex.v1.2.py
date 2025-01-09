#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
This script checks Sonarr for TV shows for which a season finale was downloaded within the set timeframe,
and optionally labels/unlabels these shows in Plex based on the chosen criteria.
The added labels can then be used to apply overlays like "Season Finale" or "Final Episode" using Kometa)

Important to note: 
The script assumes that the last listed episode in a season is the season finale.
"""

import os
import sys
import re
import time
import datetime
from datetime import timedelta, datetime as dt

import requests
try:
    from plexapi.server import PlexServer
except ImportError:
    print("ERROR: python-plexapi is not installed. Run: pip install plexapi")
    sys.exit(1)
VERSION = '1.2'

# --------------------------#
# Configuration (Sonarr)    #
# --------------------------#
SONARR_URL = 'http://localhost:8989/sonarr/api/v3'  # Edit if needed
SONARR_API_KEY = 'xxxxxxxxxxxxxxx' 					# Replace with your Sonarr API Key found under settings => General

# --------------------------#
# Configuration (Plex)      #
# --------------------------#
PLEX_URL = "http://localhost:32400"     # Edit if needed
PLEX_TOKEN = "xxxxxxxxxxxxxxx"     		# Replace with your Plex Token (see https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/)
PLEX_LIBRARY_TITLE = "TV Shows"         # Edit if needed

# --------------------------#
# Configuration (General)   #
# --------------------------#

RECENT_DAYS = 14               # Timeframe in days within which the finale needs to have aired (Downloaded finales with future air dates will also be included)
SKIP_UNMONITORED = True        # Ignore shows that are unmonitored in Sonarr
SKIP_GENRES = True             # Ignore shows with genres specified with GENRES_TO_SKIP
GENRES_TO_SKIP = ["Talk Show","News","Stand-Up","Awards Show"]
SKIP_LABELS = True             # Ignore shows with labels specified with LABELS_TO_SKIP
LABELS_TO_SKIP = ["Skip", "Exclude"]
LABEL_SERIES_IN_PLEX = True    # Add label specified with PLEX_LABEL to shows in Plex matching all criteria 
PLEX_LABEL = "Finale"
REMOVE_LABELS_IF_NO_LONGER_MATCHED = True # Remove label specified with PLEX_LABEL from shows in Plex no longer matching all criteria
ONLY_FINALE_UNWATCHED = False  # Label only shows where the finale episode itself is the only unwatched episode in the season

"""
Label logic:
 - If LABEL_SERIES_IN_PLEX = True and REMOVE_LABELS_IF_NO_LONGER_MATCHED = True  => Add label to matched shows, remove label from unmatched shows
 - If LABEL_SERIES_IN_PLEX = True and REMOVE_LABELS_IF_NO_LONGER_MATCHED = False => Add label to matched shows, does not remove label from unmatched shows
 - If LABEL_SERIES_IN_PLEX = False and REMOVE_LABELS_IF_NO_LONGER_MATCHED = True => Remove the label from ALL shows, also matched
 - If LABEL_SERIES_IN_PLEX = False and REMOVE_LABELS_IF_NO_LONGER_MATCHED = False => Do not add nor remove labels
"""

# ANSI color codes
GREEN = '\033[32m'
ORANGE = '\033[33m'
BLUE = '\033[34m'
RED = '\033[31m'
RESET = '\033[0m'

# ----------------------#
#  Sonarr Finale Logic  #
# ----------------------#
def get_sonarr_series():
    url = f"{SONARR_URL}/series?apikey={SONARR_API_KEY}"
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json()

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
        if needle in ef.get('relativePath', '').lower() and ef.get('size', 0) > 0:
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
            show_obj = show_obj.reload()  # Fetch full show data, including all genres
        except Exception as e:
            print(f"{RED}ERROR: Failed to reload show '{show_obj.title}': {e}{RESET}")
            continue  # Skip this show and proceed with others

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
                # Get the specific season
                season_obj = plex_show.season(snum)
                if not season_obj:
                    continue

                # Get the specific episode
                try:
                    finale_ep = season_obj.episode(enum)
                except Exception:
                    continue

                # Check if the finale episode is unwatched
                if finale_ep.isWatched:
                    continue  # Finale episode is watched, skip

                # Check if all other episodes are watched
                all_others_watched = all(ep.isWatched for ep in season_obj.episodes() if ep != finale_ep)

                if all_others_watched:
                    filtered.append(finale)
            except Exception:
                continue  # Skip this show silently

    return filtered

# -------------------------------#
#   Label Add/Remove Functions   #
# -------------------------------#
def add_label_to_show(show_obj, label):
    current_labels = [lab.tag for lab in show_obj.labels]
    if label in current_labels:
        print(f"{GREEN}={RESET} Label '{label}' already exists for show '{show_obj.title}' (ratingKey={show_obj.ratingKey}), skipping.")
        return
    print(f"{ORANGE}+{RESET} Adding label '{label}' to show '{show_obj.title}' (ratingKey={show_obj.ratingKey})")
    show_obj.addLabel(label)
    show_obj.reload()

def remove_label_if_present(show_obj, label):
    current_labels = [lab.tag for lab in show_obj.labels]
    if label in current_labels:
        print(f"{RED}-{RESET} Removing label '{label}' from show '{show_obj.title}' (ratingKey={show_obj.ratingKey})")
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
    """Add label to all matched shows in `finales_downloaded`."""
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

def handle_label_logic(finales_downloaded):
    if not LABEL_SERIES_IN_PLEX:
        if REMOVE_LABELS_IF_NO_LONGER_MATCHED:
            # Remove from ALL shows
            remove_label_from_all_shows(PLEX_LABEL)
    else:
        # LABEL_SERIES_IN_PLEX == True
        matched_shows(finales_downloaded, PLEX_LABEL)
        if REMOVE_LABELS_IF_NO_LONGER_MATCHED:
            remove_label_only_unmatched(finales_downloaded, PLEX_LABEL)

# -------------------------------#
#   Update Check Functions       #
# -------------------------------#
def is_newer_version(remote_version, current_version):
    def parse_version(v):
        return [int(x) for x in v.strip('v').split('.')]
    
    try:
        return parse_version(remote_version) > parse_version(current_version)
    except:
        return False

def check_for_updates(current_version):
    GITHUB_API_URL = "https://api.github.com/repos/netplexflix/Season-Finale-Label-Plex/releases/latest"
    try:
        response = requests.get(GITHUB_API_URL)
        response.raise_for_status()
        data = response.json()
        remote_version = data.get("tag_name", "").lstrip('v')  # Remove 'v' prefix if present
        if not remote_version:
            print(f"{RED}Could not determine the latest version from GitHub Releases.{RESET}")
            return
        if is_newer_version(remote_version, current_version):
            print(f"{ORANGE}A newer version (v{remote_version}) is available.{RESET}")
    except Exception as e:
        print(f"{RED}ERROR: Failed to check for updates: {e}{RESET}")

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

    # Print script version
    print(f"{GREEN}Season Finale Label Script Version: {VERSION}{RESET}")

    # Check for updates
    check_for_updates(VERSION)

    # Print configuration summary
    print()
    print(f"Recent Days: {RECENT_DAYS}")
    print(f"Skip Unmonitored: {color_bool_generic(SKIP_UNMONITORED)}")
    print(f"Skip Plex Genres: {color_bool_skip_genres()}")
    print(f"Skip Plex Labels: {color_bool_skip_labels()}")
    print(f"Label in Plex: {color_bool_label_in_plex()}")
    print(f"Remove Labels if No Longer Matched: {color_bool_remove_labels()}")
    print(f"Only Finale Unwatched: {color_bool_only_finale_unwatched()}")
    print()

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
            print(GREEN + f"Downloaded Finales in the Last {RECENT_DAYS} Days ({len(filtered_downloaded)}):" + RESET)
            for finale in filtered_downloaded:
                if len(finale) == 9:
                    title, snum, enum, ep_title, air_date, tmdb_id, imdb_id, monitored, is_future = finale
                    if is_future:
                        line = (f"- {title}: Season {snum} Episode {enum} '{ep_title}' "
                                f"{BLUE}will air on {air_date}{RESET} | TMDb ID: {tmdb_id} | IMDb ID: {imdb_id}")
                    else:
                        line = (f"- {title}: Season {snum} Episode {enum} '{ep_title}' aired on {air_date} "
                                f"| TMDb ID: {tmdb_id} | IMDb ID: {imdb_id}")
                elif len(finale) == 8:
                    title, snum, enum, ep_title, air_date, tmdb_id, imdb_id, monitored = finale
                    line = (f"- {title}: Season {snum} Episode {enum} '{ep_title}' aired on {air_date} "
                            f"| TMDb ID: {tmdb_id} | IMDb ID: {imdb_id}")
                if not monitored and not SKIP_UNMONITORED:
                    line += f" {BLUE}(UNMONITORED){RESET}"
                print(line)

        if filtered_not_downloaded:
            print(ORANGE + f"\nNot Downloaded Finales in the Last {RECENT_DAYS} Days ({len(filtered_not_downloaded)}):" + RESET)
            for finale in filtered_not_downloaded:
                if len(finale) == 9:
                    title, snum, enum, ep_title, air_date, tmdb_id, imdb_id, monitored, is_future = finale
                    if is_future:
                        line = (f"- {title}: Season {snum} Episode {enum} '{ep_title}' "
                                f"{BLUE}will air on {air_date}{RESET} | TMDb ID: {tmdb_id} | IMDb ID: {imdb_id}")
                    else:
                        line = (f"- {title}: Season {snum} Episode {enum} '{ep_title}' aired on {air_date} "
                                f"| TMDb ID: {tmdb_id} | IMDb ID: {imdb_id}")
                elif len(finale) == 8:
                    title, snum, enum, ep_title, air_date, tmdb_id, imdb_id, monitored = finale
                    line = (f"- {title}: Season {snum} Episode {enum} '{ep_title}' aired on {air_date} "
                            f"| TMDb ID: {tmdb_id} | IMDb ID: {imdb_id}")
                if not monitored and not SKIP_UNMONITORED:
                    line += f" {BLUE}(UNMONITORED){RESET}"
                print(line)

    print()

    # Label logic
    handle_label_logic(filtered_downloaded)

    print()
    print("Run completed")

    end_time = time.time()
    elapsed_seconds = int(end_time - start_time)  # Truncate decimals
    formatted_duration = str(datetime.timedelta(seconds=elapsed_seconds))
    print(f"Total runtime: {formatted_duration}\n")
