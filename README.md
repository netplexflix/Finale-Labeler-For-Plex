# TV Show Season Finale Label Script

This script checks [**Sonarr**](https://sonarr.tv/) for TV shows for which a **season finale** was downloaded which aired within the chosen timeframe, 
optionally labeling those shows in **Plex**. It can also filter out shows by genre in Plex and remove labels no longer matched.

I use this to label TV shows on my Plex server of which the season finale was recently added, which enables [**Kometa**](https://kometa.wiki/) to create an overlay for it.<br/>
The overlay serves as an easy visual indicator that the shows's Season Finale or Final Episode has been added to my Plex.

  ![ex3](https://github.com/user-attachments/assets/bb2e638a-d815-42f2-9c3c-cd2f09b8df1f) ![overlay](https://github.com/user-attachments/assets/9a44dcc0-d3da-4bb1-8c65-bf8a35026067)

## What It Does

1. **Fetches TV show data from Sonarr**  
   - Identifies each show’s **final season**.  
   - Checks if the last episode of that season **aired** within the past `RECENT_DAYS` (or is in the **future** but already downloaded).
     - Important to note: This script assumes that the last episode of the season in Sonarr is the Season Finale. Mid-Season Finales will not be detected.
       I chose this method over using the episode labels for finales found on tvdb/tmdb/trakt/?? because they are missing for many shows, especially less popular ones.
   - Splits them into **Downloaded** vs. **Not Downloaded** finales lists.


2. **Optionally Skips Unmonitored or Certain Genres**  
   - If `SKIP_UNMONITORED` is `True`, the script ignores shows that are unmonitored in Sonarr.  
   - If `SKIP_GENRES` is `True`, it checks **Plex** for any “skip” genres (`GENRES_TO_SKIP`) to exclude certain shows (e.g. “Talkshow,” “Stand-Up,” etc.).

3. **Plex Labeling** (Optional) 
   - **Adds** a label (e.g. `"Finale"`) to your matched shows if `LABEL_SERIES_IN_PLEX` is `True`.  
   - If `REMOVE_LABELS_IF_NO_LONGER_MATCHED` is **also** `True`, it **removes** that label from shows that no longer match the “finale” criteria.  
   - **Special Case**: If `LABEL_SERIES_IN_PLEX = False` but `REMOVE_LABELS_IF_NO_LONGER_MATCHED = True`, the script removes that label from **all** shows in Plex (essentially a cleanup scenario).

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

  - `SONARR_URL`
  - `SONARR_API_KEY` 
  - `PLEX_URL`
  - `PLEX_TOKEN`
  - `PLEX_LIBRARY_TITLE`
 
  - `RECENT_DAYS` (e.g., `14`)
  - `SKIP_UNMONITORED` (`True`/`False`)
  - `SKIP_GENRES` (`True`/`False`)  
  - `GENRES_TO_SKIP` (array of genres seperated by comma, e.g. `["Talkshow", "Stand-Up", "Awards Show"]`)

  - `LABEL_SERIES_IN_PLEX`: `True` (adds labels) or `False` (skip adding).
  - `PLEX_LABEL`: e.g. `"Finale"`.
  - `REMOVE_LABELS_IF_NO_LONGER_MATCHED`: `True`/`False` (cleanup logic).

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
   - Open the `.py` file in an editor. Adjust the **Configuration** variables (Sonarr, Plex, General) as described above.  
   - Save, then in your terminal:
     ```bash
     python Season-Finale-Label-Plex.py
     ```
   - The script will:
     1. Connect to Sonarr and find your “recent” or future **downloaded** finales.  
     2. Optionally skip shows in Plex by genre.  
     3. Print “Downloaded Finales” and “Not Downloaded Finales.”
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

## Notes / Troubleshooting

- **Plex token**: [Finding your Plex token](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/)  
- **No labeling in Plex?**  
  - Double-check `LABEL_SERIES_IN_PLEX = True`.  
  - Confirm your `PLEX_LIBRARY_TITLE` exactly matches the name of your Plex TV library.  
  - Ensure your Plex token (`PLEX_TOKEN`) is correct.

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
