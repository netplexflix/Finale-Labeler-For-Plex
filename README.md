# TV Show Season Finale Label Script

This script checks [**Sonarr**](https://sonarr.tv/) for TV shows for which a season finale was downloaded within the set timeframe,
and optionally labels/unlabels these shows in Plex based on chosen criteria.
The added labels can then be used to apply overlays like "Season Finale" or "Final Episode" using [**Kometa**](https://kometa.wiki/).

These overlays can serve as an easy visual indicator that the shows's Season Finale or Final Episode has been added to your Plex.

  ![ex3](https://github.com/user-attachments/assets/bb2e638a-d815-42f2-9c3c-cd2f09b8df1f) ![overlay](https://github.com/user-attachments/assets/9a44dcc0-d3da-4bb1-8c65-bf8a35026067)

## What It Does

1. **Fetches TV show data from Sonarr**  
   - Identifies each show’s **final season**.  
   - Checks if the last episode of that season **aired** within the past `RECENT_DAYS` (or is in the **future** but already downloaded).
     - Important to note: This script assumes that the last episode of the season in Sonarr is the Season Finale. Mid-Season Finales will not be detected.
       I chose this method over using the episode labels for finales found on tvdb/tmdb/trakt/?? because they are missing for many shows, especially less popular ones.
   - Splits them into **Downloaded** vs. **Not Downloaded** finales lists.


2. **Optionally Filters/Skips shows based on the following criteria**  
   - If `SKIP_UNMONITORED` is `True`, the script ignores shows that are unmonitored in Sonarr.  
   - If `SKIP_GENRES` is `True`, it checks **Plex** for any “skip” genres (`GENRES_TO_SKIP`) to exclude certain shows (e.g. “Talk Show”,“Stand-Up”,"Award Show" etc.).
   - If `SKIP_LABELS` is `True`, it checks **Plex* for any "skip" labels (`LABELS_TO_SKIP`) to exclude certain shows (e.g. "Skip","Exclude" etc)
   - If `ONLY_FINALE_UNWATCHED` is 'True`, labels will only be applied if the identified finale episode is the only remaining unwatched episode that season.

3. **Plex Labeling** (Optional) 
   - **Adds** a label (e.g. `"Finale"`) to your matched shows if `LABEL_SERIES_IN_PLEX` is `True` and all skip criteria are met.  
   - If `REMOVE_LABELS_IF_NO_LONGER_MATCHED` is **also** `True`, it **removes** that label from shows that no longer match the “finale” criteria.  
   - **Special Case**: If `LABEL_SERIES_IN_PLEX = False` and `REMOVE_LABELS_IF_NO_LONGER_MATCHED = True`, the script removes that label from **all** shows in Plex (essentially a cleanup scenario).

## Requirements

- **Python 3.7+**  
- **Sonarr** running (with valid API key).  
- **Plex** with a valid Plex token.  
- **python-plexapi** and **requests** installed:
  ```bash
  pip install requests plexapi
  ```


## Configuration

Open the script in any text editor (e.g., Notepad++) and look for the **Configuration** sections near the top.<br/>
You need to fill in or adjust these variables:

# Sonarr and Plex connection:
  - `SONARR_URL`			Default: `http://localhost:8989/sonarr/api/v3`. Edit if needed
  - `SONARR_API_KEY` 		Can be found in Sonarr under settings => General
  - `PLEX_URL`				Default: `http://localhost:32400`. Edit if needed
  - `PLEX_TOKEN`			[Finding your Plex token](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/)  
  - `PLEX_LIBRARY_TITLE`	Default: `TV Shows`. Edit if your TV show library is different

# Criteria: 
  - `RECENT_DAYS` (e.g., `14`). Timeframe in days within which the finale needs to have aired (Downloaded finales with future air dates will also be included).
  
  - `SKIP_UNMONITORED` (`True`/`False`). Ignore shows that are unmonitored in Sonarr.
  - `SKIP_GENRES` (`True`/`False`). Ignore shows with genres specified with GENRES_TO_SKIP.  
	- `GENRES_TO_SKIP` (array of genres seperated by comma, e.g. `["Talk Show", "Stand-Up", "Awards Show"]`)
  - `SKIP_LABELS` (`True`/`False`). Ignore shows with labels specified with LABELS_TO_SKIP.  
	- `LABELS_TO_SKIP` (array of genres seperated by comma, e.g. `["Skip", "Exclude"]`)

  - `LABEL_SERIES_IN_PLEX`: `True` (adds labels) or `False` (skip adding).
  - `PLEX_LABEL`: e.g. `"Finale"`.
  - `REMOVE_LABELS_IF_NO_LONGER_MATCHED` (`True`/`False`) (cleanup logic).
  - `ONLY_FINALE_UNWATCHED` (`True`/`False`) (Label only shows for which the finale episode itself is the only unwatched episode in the season)

## Installation & Usage

1. **Install Python 3.7 or Higher**  
   - Make sure you can run `python --version` in a terminal or command prompt (Windows users can search “Command Prompt,” Mac/Linux users can open “Terminal”).

2. **Install Dependencies**  
   - In your terminal (Command Prompt for Windows, Terminal for Mac/Linux), type:
     ```bash
     pip install requests plexapi
     ```
     > **Tip**: If you see an error like `'pip' is not recognized`, try `python -m pip install requests plexapi` or `pip3 install requests plexapi` depending on your setup.

3. **Edit & Run the Script**  
   - Open the `.py` file in a text editor such as [***Notepad++***](https://notepad-plus-plus.org/). Adjust the **Configuration** variables (Sonarr, Plex, General) as described above.  
   - Save, then in your terminal:
     ```bash
     python Season-Finale-Label-Plex.v1.2.py
     ```
   - The script will:
     1. Connect to Sonarr and find your “recent” or future **downloaded** finales.  
     2. Optionally skip shows based on criteria.  
     3. Print “Downloaded Finales” and “Not Downloaded Finales.” that match the criteria.
     4. Mark which Shows are unmonitored (If SKIP_UNMONITORED is set to false)
     5. Add/remove labels in Plex if configured.  

---

## Examples

1. **Labeling “Season Finales”**  
   - `LABEL_SERIES_IN_PLEX = True`  
   - `REMOVE_LABELS_IF_NO_LONGER_MATCHED = True`  
   - **Outcome**: Script adds the “Finale” label in Plex for newly detected finales and cleans up that label for shows that no longer match.

2. **Cleaning Up Old Labels**  
   - `LABEL_SERIES_IN_PLEX = False`  
   - `REMOVE_LABELS_IF_NO_LONGER_MATCHED = True`  
   - **Outcome**: No new labels are added, but any existing “Finale” labels are removed from every show in Plex.

3. **Print-Only Mode**  
   - `LABEL_SERIES_IN_PLEX = False`  
   - `REMOVE_LABELS_IF_NO_LONGER_MATCHED = False`  
   - **Outcome**: The script prints which finales are downloaded/not downloaded, without changing Plex labels.

---

## Notes

- **Why not use the Finale labels available via tvdb/tmdb/trakt?**
   
These labels are applied manually by people and are missing for a considerable amount of shows, especially foreign and lesser popular ones.
This approach avoids this issue, but has two downsides:
1.  If the last episode of a season in Sonarr is NOT the season finale, then it will be wrongfully identified as one. (I did not find instances where this is the case but it is theoretically possible)
2.  This script does not detect "mid-season finales"

## Kometa Overlay Config

You can use the following logic to add overlays:

For season Finale:
```
  SEASON:
    name: SEASON
    plex_search:
      all:
        label: Finale
```

For Final Episode:
```
  FINAL:
    name: FINAL
    plex_search:
      all:
        label: Finale
    filters:
      tvdb_status:
           - Ended
           - Cancelled
    suppress_overlays:
       - SEASON
```
<br/>
<br/>
<br/>


[!["Buy Me A Coffee"](https://github.com/user-attachments/assets/5c30b977-2d31-4266-830e-b8c993996ce7)](https://www.buymeacoffee.com/neekokeen)
