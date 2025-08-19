from datetime import datetime, timezone
import json

from pathlib import Path

class BaseLogger:
    def log(self, event: str, details: dict):
        raise NotImplementedError


class NullLogger(BaseLogger):
    """A logger that ignores all messages (default)."""
    def log(self, event: str, details: dict):
        pass


class GameLogger(BaseLogger):
    """Logs game events to a JSONL file."""
    def __init__(self, game_id=None, filepath: str = "game_log.jsonl"):
        self.filepath = Path(filepath)
        self.log_dir = self.filepath.parent
        self.log_dir.mkdir(parents=True, exist_ok=True)
        if game_id is None:
            self.game_id = self._generate_unique_game_id()
    
    def _generate_unique_game_id(self):
        """
        Generate a unique game id based on timestamp and existing files.
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        base_id = timestamp
        existing_ids = {f.stem for f in self.log_dir.glob("*.jsonl")}
        counter = 1
        unique_id = base_id
        while unique_id in existing_ids:
            counter += 1
            unique_id = f"{base_id}_{counter}"
        return unique_id

    def log(self, event: str, details: dict):
        log_entry = {
            "game_id": self.game_id,
            "timestamp": datetime.now(timezone.utc).isoformat(), 
            "event": event,
            "details": preprocess_details(details),
        }
        with open(self.filepath, "a") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")  # keep Unicode


def preprocess_details(details):
    """Preprocess details for logging, converting non-serializable objects."""
    def serialize(obj):
        if isinstance(obj, str):
            return obj
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return str(obj)  # Fallback to string representation for non-serializable objects

    return {key: serialize(value) for key, value in details.items()}
