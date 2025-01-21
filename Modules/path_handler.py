from pathlib import Path
import os
import yaml
import platform
from typing import Dict, Optional

class PathHandler:
    def __init__(self, config: dict):
        self.path_mappings = config.get('paths', {}).get('path_mappings', {})
        self.platform = config.get('paths', {}).get('platform', self.detect_platform())
        
    @staticmethod
    def detect_platform() -> str:
        """Automatically detect the platform."""
        system = platform.system().lower()
        if system == 'windows':
            return 'windows'
        elif system == 'linux':
            # Check if running in Docker
            if os.path.exists('/.dockerenv'):
                return 'docker'
            return 'linux'
        return 'unknown'

    def normalize_path(self, path: str) -> str:
        """Normalize path for current platform."""
        # Convert to Path object for cross-platform compatibility
        path_obj = Path(path)
        
        # Convert to string representation appropriate for the platform
        if self.platform == 'windows':
            return str(path_obj.as_posix())
        return str(path_obj)

    def map_path(self, path: str, reverse: bool = False) -> str:
        """
        Map paths between different systems (e.g., local to NAS or vice versa)
        
        Args:
            path: The path to map
            reverse: If True, map from NAS to local path instead of local to NAS
        """
        if not path:
            return path

        normalized_path = self.normalize_path(path)
        
        # No mappings defined, return normalized path
        if not self.path_mappings:
            return normalized_path

        # Get the correct mapping direction
        mappings = self.path_mappings.items()
        if reverse:
            mappings = {v: k for k, v in self.path_mappings.items()}.items()

        # Try each mapping
        for source, target in mappings:
            source = self.normalize_path(source)
            target = self.normalize_path(target)
            
            if normalized_path.startswith(source):
                return normalized_path.replace(source, target, 1)
                
        return normalized_path

    def get_absolute_path(self, path: str) -> str:
        """Convert relative path to absolute path."""
        return str(Path(path).resolve())