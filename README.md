# Plex Finale Labeler

This script checks your Plex TV library and lists your TV shows for which a (season) finale is present which aired within the set timeframe, <br/>
and optionally labels/unlabels these shows in Plex based on chosen criteria.<br/>

The added labels can then be used to create "Ready to Binge" collections<br/>
and/or apply overlays (E.g.: "Season Finale", "Final Episode",..) using [**Kometa**](https://kometa.wiki/).

Overlays can serve as an easy visual indicator that the shows's Season Finale or Final Episode has been added to your Plex.

![github example](https://github.com/user-attachments/assets/ba858c1f-3408-4103-9f46-73dcb6811ace)

## What It Does

1. **One, or both, of two methods are used:** <br/>
- **METHOD 1: Sonarr**:<br/>
  Uses [**Sonarr**](https://sonarr.tv/) to identify Shows for which the last episode of a season was downloaded.
   
	>**+** Will identify every final episode<br/>
	>**+** Faster<br/>
	>**-** Could incorrectly identify episode as a finale (if not all episodes of season are listed in Sonarr)<br/>
	>**-** Does not identify mid season finales

- **METHOD 2: Trakt**:<br/>
  Uses your [**Trakt**](https://trakt.tv/) API to check each TV show's most recent episode for (mid)season or series finale status.<br/>
  	>**+** Identifies mid season finales<br/>
  	>**+** Clear differentiation between Mid-Season Finales, Season Finales and Series Finales<br/>
	>**-** 'finale' flags are currently missing for many shows, especially less popular and foreign ones<br/>
	>**-** Could incorrectly identify finale episode if info on Trakt is wrong<br/>
	>**-** Slower


2. **Optionally Filters/Skips shows based on the following criteria**  
	- If `Skip_Unmonitored` is `True`, the script ignores shows that are unmonitored in Sonarr.  (When using Method 1)
	- If `Skip_Genres` is `True`, it checks Plex for genres (`Genres_to_Skip`) to exclude certain shows (e.g. “Talk Show”,“Stand-Up”,"Award Show" etc.).
	- If `Skip_Labels` is `True`, it checks Plex for labels (`Labels_to_Skip`) to exclude certain shows (e.g. "Skip","Exclude" etc)
	- If `Only_Finale_Unwatched` is `True`, only include shows for which the identified finale episode is the only remaining unwatched episode that season.

3. **Lists the Qualifying TV Shows**
	- The script will show you a list of TV Shows on your Plex that qualify the set criteria.
	- When using Method 1 (Sonarr) it will also
		- Mark Unmonitored shows (in case `Skip_Unmonitored` was set to false).
 		- Show a seperate list of aired finales (matching the criteria) which you haven't downloaded yet.
 
4. **Adds/Removes labels in Plex on TV Show level** (Optional) 
	- **Adds** labels to your matched shows if `Label_series_in_plex` is `True` and all criteria are met.<br/>
		- Method 1 (Sonarr) applies the label chosen under `plex_label` <br/>
	 	- Method 2 (Trakt) applies the `episode_status` as label to differentiate between the possible statuses (mid_season_finale, season_finale and series_finale by default)
	- **Removes** labels if `remove_labels_if_no_longer_matched` is `True` and the criteria are no longer met.  
> [!TIP]  
> **Special Case**: If `label_series_in_plex = False` and `remove_labels_if_no_longer_matched = True`, the script removes the labels from **all** shows in Plex (essentially a cleanup scenario).

## Requirements

- **Plex** with a valid Plex token.
- **[Sonarr](https://sonarr.tv/)** (Required for Method 1)
- **[Trakt API credentials](https://trakt.docs.apiary.io/#introduction/create-an-app)** (Required for Method 2)
- **Python 3.7+**      
- **dependencies** Can be installed using the requirements.txt (See "Installation & Usage" below)


## Configuration

Open config.yml in any text editor (e.g., Notepad++).<br/>
You need to fill in or adjust the variables:

### Sonarr: (Needed for Method 1)
  - `url`		Default: `http://localhost:8989/sonarr/api/v3`. Edit if needed
  - `api_key` 		Can be found in Sonarr under settings => General
### Trakt: (Needed for Method 2)
  - `client_id`			Found under [Your API Apps](https://trakt.tv/oauth/applications). See [HERE](https://trakt.docs.apiary.io/#introduction/create-an-app) for more info on how to get Trakt API credentials.
  - `client_secret`		
  - `desired_episode_types`	These episode statuses will be used to identify and label. If you don't wish to have mid season finales you can remove that line
### Plex:
  - `url`			Default: `http://localhost:32400`. Edit if needed.
  - `token`			[Finding your Plex token](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/)  
  - `library_title`		Default: `TV Shows`. Edit if your TV show library is named differently.

### General: 
  - `recent_days` (e.g., `14`). Timeframe in days within which the finale needs to have aired (Downloaded finales with future air dates will also be included).
  - `skip_unmonitored` (`true`/`false`). Ignore shows that are unmonitored in Sonarr. (Only used by Method 1)
  - `skip_genres` (`true`/`false`). Ignore shows with genres specified with `genres_to_skip`.  
	- `genres_to_skip` (which genres to skip)
  - `skip_labels` (`true`/`false`). Ignore shows with labels specified with `labels_to_skip`.  
	- `labels_to_skip` (which labels to skip)

  - `label_series_in_plex`: (`true`/`false`). Whether or not to add labels to your TV Shows in Plex. If set to `false` the script will simply list the qualifying shows.
  - `plex_label`: default `"Finale"`. Which label to apply when using Method 1 (Sonarr). When using Method 2 (Trakt), the types specified under `desired_episode_types` will be used as labels
  - `remove_labels_if_no_longer_matched` (`true`/`false`) Removes the label set under `plex_label` if using Method 1, or labels set under `desired_episode_types` if using Method 2 for any show that no longer qualifies for it.
  - `only_finale_unwatched` (`true`/`false`) Label only shows for which the finale episode itself is the only unwatched episode in the season.

## Installation & Usage

> [!IMPORTANT]
> Make sure you first correctly edit the **Configuration** variables (Sonarr, Trakt, Plex, General) as described above.
     
1. **Install Python 3.7 or Higher**
- Go to python.org and install the latest version of Python
- Make sure you can run `python --version` in a terminal or command prompt (Windows users can search “Command Prompt,” Mac/Linux users can open “Terminal”). If correctly installed it should return a version number e.g. "Python 3.11.2"

2. **Install Dependencies**  
In your terminal, make sure you are in your script path and type:
     ```bash
     python -m pip install -r requirements.txt
     ```
     
3. **Launch the Script**
In your terminal, make sure you are in your script path and type:
     ```bash
     python PFL.py
     ```
> [!TIP]
> Windows users can create a batch file to quickly launch the script:
> Open a text editor, paste the following code and Save as a .bat file
> (Edit the paths to the python.exe and your PFL.py according to where they are on your computer.)

  ```bash
  "C:\Users\User1\AppData\Local\Programs\Python\Python311\python.exe" "C:\Scripts\Finale\PFL.py" -r
  pause
  ```
> [!IMPORTANT]
> If you want to schedule this script (for example right before your kometa is sheduled to run) then use the Sonarr.py and/or Trakt.py scripts found in the Modules folder, depending on which method(s) you want to schedule.<br/>
> PFL.py only functions as the method selector intended for manual runs.

---

## Notes

- **Which Method should I use?**
   
This comes down to personal preference. I prefer Method 1 as it correctly applies the labels to all season Finales and I don't really care about midseason finales.
I know that this method could theoretically incorrectly label in case not all episodes of a season are listed yet in Sonarr, but
A) I could not find any such instances in my library and B) If I come across one I'll either go edit TVDB myself or exclude said TV Show with a label.

The 'finale' labels found via Trakt are applied manually by people and are missing for a considerable amount of shows, especially foreign and lesser popular ones.
(TRAKT, TVDB and TMDB seem to aggregated these flags from the same source (TVDB?))
Using Method 2 will make it very unlikely an episode is incorrectly identified as a finale, but will result in more Shows being looked over.

---
## Kometa Overlay Configs

You can use the following logic examples to add overlays with Kometa:

### METHOD 1:
For Season Finale:
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

### METHOD 2:
For Season Finale:
```
  SEASON:
    name: SEASON
    plex_search:
      all:
        label: mid_season_finale
```

For Mid-Season Finale:
```
  FINAL:
    name: MIDSEASON
    plex_search:
      all:
        label: series_finale
```

For Final Episode:
```
  FINAL:
    name: FINAL
    plex_search:
      all:
        label: series_finale
```
<br/>
<br/>
<br/>


[!["Buy Me A Coffee"](https://github.com/user-attachments/assets/5c30b977-2d31-4266-830e-b8c993996ce7)](https://www.buymeacoffee.com/neekokeen)
