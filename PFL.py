import subprocess
import sys
import os
import requests

VERSION = '2.0'

# ANSI color codes
GREEN = '\033[32m'
ORANGE = '\033[33m'
BLUE = '\033[34m'
RED = '\033[31m'
RESET = '\033[0m'
BOLD = '\033[1m'

# -------------------------------#
#   Update Check Functions       #
# -------------------------------#
def is_newer_version(remote_version, current_version):
    def parse_version(v):
        return [int(x) for x in v.strip('v').split('.')]
    
    try:
        return parse_version(remote_version) > parse_version(current_version)
    except Exception as e:
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

def run_script(script_name):
    try:
        # Construct the path to the script inside the Modules subfolder
        script_path = os.path.join("Modules", script_name)
        # Using sys.executable to ensure the same Python interpreter is used.
        subprocess.run([sys.executable, script_path], check=True)
    except subprocess.CalledProcessError as error:
        print(f"{RED}An error occurred while running {script_name}: {error}{RESET}")

def display_title_and_methods():
    # Title
    title = f"{BOLD}{BLUE}{'*' * 40}\nPlex Finale Labeler {VERSION}\n{'*' * 40}{RESET}"
    print(title)
    check_for_updates(VERSION)	    
    # Explanation for each method
    explanation = f"""
Make sure you have correctly configured config.yml

{BOLD}{BLUE}Method 1: Sonarr{RESET}
Connects to Sonarr to identify the latest episode of the latest season and checks if it's downloaded.
    {GREEN}+{RESET} Will identify every final episode
    {GREEN}+{RESET} Faster
    {ORANGE}-{RESET} Could incorrectly identify an episode as a finale (if not all episodes of a season are listed in Sonarr)
    {ORANGE}-{RESET} Does not identify mid season finales

{BOLD}{BLUE}Method 2: Trakt{RESET}
Uses your Trakt API to get the episode_types.
    {GREEN}+{RESET} Identifies mid season finales
    {ORANGE}-{RESET} 'finale' flags are currently missing for many shows, especially less popular and foreign ones
    {ORANGE}-{RESET} Could incorrectly identify a finale episode if info on Trakt is wrong
    {ORANGE}-{RESET} Slower
"""
    print(explanation)

def main():
    # Print the title and methods explanation
    display_title_and_methods()

    # Prompt user for method choice
    print(f"{BOLD}{GREEN}Select a method:{RESET}")
    print("1: Method 1 (Sonarr)")
    print("2: Method 2 (Trakt)")
    print("3: Both (Runs both methods consecutively)")
    
    choice = input("Enter your choice (1, 2, or 3): ").strip()
    print("===================\n")

    if choice == "1":
        print(f"{BOLD}{BLUE}Running Method 1: Sonarr{RESET}")
        run_script("Sonarr.py")
    elif choice == "2":
        print(f"{BOLD}{BLUE}Running Method 2: Trakt{RESET}")
        run_script("Trakt.py")
    elif choice == "3":
        print(f"{BOLD}{BLUE}Running Method 1: Sonarr{RESET}")
        run_script("Sonarr.py")
        print(f"{BOLD}{BLUE}Running Method 2: Trakt{RESET}")
        run_script("Trakt.py")
    else:
        print(f"{RED}Invalid selection. Please run the script again and choose 1, 2, or 3.{RESET}")

if __name__ == "__main__":
    main()
