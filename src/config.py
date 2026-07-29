
import json
import os
from pathlib import Path
from typing import TypedDict, Optional

class pyspliceConfig(TypedDict):
    sampleDir: str
    placeholders: bool
    darkMode: bool
    configured: bool

DEFAULT_CFG: pyspliceConfig = {
    "sampleDir": str(Path.home() / "Samples"),
    "darkMode": True,
    "placeholders": False,
    "configured": False
}

class ConfigManager:
    def __init__(self):
        self.config_dir = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "pysplice"
        self.config_file = self.config_dir / "config.json"
        self._cfg: pyspliceConfig = DEFAULT_CFG.copy()

    def load(self):
        if not self.config_dir.exists():
            self.config_dir.mkdir(parents=True, exist_ok=True)
        
        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    loaded_cfg = json.load(f)
                    self._cfg.update(loaded_cfg)
            except (json.JSONDecodeError, IOError):
                pass
    
    def save(self):
        if not self.config_dir.exists():
            self.config_dir.mkdir(parents=True, exist_ok=True)
        
        with open(self.config_file, "w") as f:
            json.dump(self._cfg, f, indent=2)

    def get(self) -> pyspliceConfig:
        return self._cfg

    def mutate(self, **kwargs):
        self._cfg.update(kwargs)
        self.save()

config = ConfigManager()
config.load()
