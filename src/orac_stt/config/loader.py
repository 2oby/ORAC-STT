"""Configuration loader with TOML support and environment variable overrides."""

import os
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from .settings import Settings


class ConfigLoader:
    """Load configuration from TOML files with environment variable overrides."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize configuration loader.
        
        Args:
            config_path: Path to TOML configuration file
        """
        self.config_path = config_path or self._get_default_config_path()
        self._raw_config: Dict[str, Any] = {}
        
    def _get_default_config_path(self) -> Path:
        """Get default configuration file path."""
        config_env = os.getenv("ORAC_CONFIG_FILE")
        if config_env:
            return Path(config_env)
        
        # Look for config in common locations
        config_locations = [
            Path("config.toml"),
            Path("/etc/orac-stt/config.toml"),
            Path.home() / ".config" / "orac-stt" / "config.toml",
        ]
        
        for path in config_locations:
            if path.exists():
                return path
                
        return Path("config.toml")
    
    def load_toml(self) -> Dict[str, Any]:
        """Load configuration from TOML file."""
        if not self.config_path.exists():
            return {}
            
        with open(self.config_path, "rb") as f:
            return tomllib.load(f)
    
    def merge_env_vars(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Merge environment variables into configuration.
        
        Environment variables override TOML values.
        """
        # Environment variables are handled by pydantic BaseSettings
        # This method is for any custom merging logic if needed
        return config
    
    def load(self) -> Settings:
        """Load complete configuration with all overrides applied."""
        toml_config = self.load_toml()
        config = self.merge_env_vars(toml_config)
        
        # Pydantic will handle environment variable overrides
        return Settings(**config)


def load_config(config_path: Optional[Path] = None) -> Settings:
    """Load configuration from TOML file and environment variables.
    
    Args:
        config_path: Optional path to configuration file
        
    Returns:
        Loaded configuration settings
    """
    loader = ConfigLoader(config_path)
    return loader.load()