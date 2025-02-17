import subprocess
import sys
import os
import requests
import yaml
from datetime import datetime, timedelta
from pathlib import Path

VERSION = '2.5b01'

# Get the directory of the script being executed
script_dir = Path(__file__).parent
requirements_path = script_dir / "requirements.txt"
config_path = script_dir / "config.yml"

# ANSI color codes
GREEN = '\033[32m'
ORANGE = '\033[33m'
BLUE = '\033[34m'
RED = '\033[31m'
RESET = '\033[0m'
BOLD = '\033[1m'

def load_config():
    try:
        with config_path.open("r", encoding="utf-8") as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        sys.exit(f"{RED}ERROR: Could not find config.yml at {config_path}{RESET}")
    except Exception as e:
        sys.exit(f"{RED}ERROR: An error occurred while loading config.yml: {e}{RESET}")

# Load configuration
config = load_config()
# Retrieve launch_method from config.yml
general_config = config.get("general", {})
launch_method = general_config.get("launch_method", 0)

def check_requirements():
    print("\nChecking requirements:")
    try:
        with open(requirements_path, "r") as req_file:
            requirements = req_file.readlines()

        unmet_requirements = []
        for req in requirements:
            req = req.strip()
            if not req:  # Skip empty lines
                continue
            try:
                pkg_name, required_version = req.split("==")
                installed_version = subprocess.check_output(
                    [sys.executable, "-m", "pip", "show", pkg_name]
                ).decode().split("Version: ")[1].split("\n")[0]

                if installed_version == required_version:
                    print(f"{pkg_name}: {GREEN}OK{RESET}")
                elif installed_version < required_version:
                    print(f"{pkg_name}: {ORANGE}Upgrade needed{RESET}")
                    unmet_requirements.append(req)
                else:
                    print(f"{pkg_name}: {GREEN}OK{RESET}")
            except (IndexError, subprocess.CalledProcessError):
                print(f"{pkg_name}: {RED}Missing{RESET}")
                unmet_requirements.append(req)

        if unmet_requirements:
            answer = input("Install requirements? (y/n): ").strip().lower()
            if answer == "y":
                subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(requirements_path)])
            else:
                sys.exit(f"{RED}Script ended due to unmet requirements.{RESET}")

    except Exception as e:
        sys.exit(f"{RED}Error checking requirements: {e}{RESET}")

def is_newer_version(remote_version, current_version):
    def parse_version(v):
        return [int(x) for x in v.strip('v').split('.')]
    
    try:
        return parse_version(remote_version) > parse_version(current_version)
    except Exception:
        return False

def check_for_updates(current_version):
    GITHUB_API_URL = "https://api.github.com/repos/netplexflix/Finale-Labeler-For-Plex/releases/latest"
    try:
        response = requests.get(GITHUB_API_URL)
        response.raise_for_status()
        data = response.json()
        remote_version = data.get("tag_name", "").lstrip('v')
        if not remote_version:
            print(f"{RED}Could not determine the latest version from GitHub Releases.{RESET}")
            return
        if is_newer_version(remote_version, current_version):
            print(f"{ORANGE}A newer version (v{remote_version}) is available.{RESET}")
    except Exception as e:
        print(f"{RED}ERROR: Failed to check for updates: {e}{RESET}")

def run_script(script_name):
    try:
        script_path = script_dir / "Modules" / script_name
        subprocess.run([sys.executable, str(script_path)], check=True)
    except subprocess.CalledProcessError as error:
        print(f"{RED}An error occurred while running {script_name}: {error}{RESET}")

def display_title_and_methods():
    title = f"{BOLD}{BLUE}{'*' * 40}\nPlex Finale Labeler {VERSION}\n{'*' * 40}{RESET}"
    print(title)
    check_for_updates(VERSION)
    explanation = f"""
Make sure you have correctly configured config.yml

{BOLD}{BLUE}Method 1: Sonarr{RESET}
Connects to Sonarr to identify the latest episode of the latest season and checks if it's downloaded.

{BOLD}{BLUE}Method 2: Trakt{RESET}
Uses your Trakt API to get the episode_types.
"""
    print(explanation)

def validate_path_config(config):
    paths_config = config.get('paths', {})
    platform = paths_config.get('platform')
    
    if platform and platform not in ['windows', 'linux', 'nas', 'docker']:
        print(f"{RED}ERROR: Invalid platform in config. Must be one of: windows, linux, nas, docker{RESET}")
        sys.exit(1)
        
    mappings = paths_config.get('path_mappings', {})
    if mappings:
        for source, target in mappings.items():
            if not source or not target:
                print(f"{RED}ERROR: Invalid path mapping: {source} -> {target}{RESET}")
                sys.exit(1)

def main():
    if launch_method == 0:
        check_requirements()
    
    start_time = datetime.now()
    consecutive_run = False

    validate_path_config(config)

    if launch_method in [1, 2, 3]:
        if launch_method in [1, 3]:
            print(f"{BOLD}{BLUE}Running Method 1: Sonarr{RESET}")
            run_script("Sonarr.py")
        if launch_method in [2, 3]:
            print(f"{BOLD}{BLUE}Running Method 2: Trakt{RESET}")
            run_script("Trakt.py")
        consecutive_run = launch_method == 3
    else:
        display_title_and_methods()
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
            consecutive_run = True
            print(f"{BOLD}{BLUE}Running Method 1: Sonarr{RESET}")
            run_script("Sonarr.py")
            print(f"{BOLD}{BLUE}Running Method 2: Trakt{RESET}")
            run_script("Trakt.py")
        else:
            print(f"{RED}Invalid selection. Please run the script again and choose 1, 2, or 3.{RESET}")
            return
    
    if consecutive_run:
        end_time = datetime.now()
        total_runtime = str(timedelta(seconds=int((end_time - start_time).total_seconds())))
        print(f"\nTotal Runtime: {total_runtime}")

if __name__ == "__main__":
    main()