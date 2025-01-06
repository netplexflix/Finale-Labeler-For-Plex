# Sonarr-Season-Finale
Lists TV shows for which a season finale was downloaded by Sonarr within the chosen timeframe.

I use this to identify TV shows on my Plex server of which the season finale was recently added, so that I can manually label them in Plex which enables Kometa to create an overlay for it.<br/>
The idea/hope is to one day see something like this used within Kometa to create a 'season finale' overlay default.

Set the configuration at the beginning of the script:
# Configuration

SONARR_API_KEY = 'xxxxxxx' # Set your Sonarr API key found under settings => General<br/>
SONARR_URL = 'http://localhost:8989/sonarr/api/v3' # change if needed<br/>
RECENT_DAYS = 14 # Set past timeframe within which the finale was aired. Finales with future airdates but already downloaded will be included<br/>
SKIP_UNMONITORED = True  # Set to False to disable skipping unmonitored series<br/>

![ex1](https://github.com/user-attachments/assets/4f860fb3-f758-43d6-a785-e3fb035c418a)

![overlay](https://github.com/user-attachments/assets/9a44dcc0-d3da-4bb1-8c65-bf8a35026067)
