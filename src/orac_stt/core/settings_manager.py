"""Settings manager for runtime-modifiable configuration."""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from threading import RLock
import logging

logger = logging.getLogger(__name__)


class SettingsManager:
    """Manages runtime settings that can be modified via API."""
    
    def __init__(self, data_dir: str = "/app/data"):
        """Initialize settings manager.
        
        Args:
            data_dir: Directory for persisting settings
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.settings_file = self.data_dir / "settings.yaml"
        self._settings: Dict[str, Any] = {}
        self._lock = RLock()
        self.load()
    
    def load(self) -> None:
        """Load settings from YAML file."""
        if not self.settings_file.exists():
            logger.info("No existing settings file, using defaults")
            # Set defaults
            self._settings = {
                "orac_core_url": "http://192.168.8.192:8000"
            }
            self.save()
            return
        
        try:
            with open(self.settings_file, 'r') as f:
                data = yaml.safe_load(f) or {}
            
            self._settings = data
            logger.info(f"Loaded settings from {self.settings_file}")
        except Exception as e:
            logger.error(f"Failed to load settings: {e}")
            # Use defaults if load fails
            self._settings = {
                "orac_core_url": "http://192.168.8.192:8000"
            }
    
    def save(self) -> None:
        """Save settings to YAML file."""
        try:
            with self._lock:
                with open(self.settings_file, 'w') as f:
                    yaml.safe_dump(self._settings, f, default_flow_style=False)
                
                logger.debug(f"Saved settings to {self.settings_file}")
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get setting value.
        
        Args:
            key: Setting key
            default: Default value if key not found
            
        Returns:
            Setting value or default
        """
        with self._lock:
            return self._settings.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set setting value.
        
        Args:
            key: Setting key
            value: Setting value
        """
        with self._lock:
            self._settings[key] = value
            self.save()
    
    def get_all(self) -> Dict[str, Any]:
        """Get all settings.
        
        Returns:
            Dictionary of all settings
        """
        with self._lock:
            return self._settings.copy()
    
    def update(self, updates: Dict[str, Any]) -> None:
        """Update multiple settings.
        
        Args:
            updates: Dictionary of setting updates
        """
        with self._lock:
            self._settings.update(updates)
            self.save()


# Global settings manager instance
_settings_manager: Optional[SettingsManager] = None


def get_settings_manager() -> SettingsManager:
    """Get or create the global settings manager instance."""
    global _settings_manager
    if _settings_manager is None:
        _settings_manager = SettingsManager()
    return _settings_manager