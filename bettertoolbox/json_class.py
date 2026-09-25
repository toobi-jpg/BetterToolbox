import copy
import json
import os
import time
from os import path

class json_class:
    fileDir = path.dirname(path.realpath(__file__))
    _json_path = path.join(fileDir, 'data.json')
    _cached_data = None

    def __init__(self):
        self.load_if_needed()

    @classmethod
    def load_if_needed(cls):
        if cls._cached_data is not None:
            return
        try:
            with open(cls._json_path, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)
            cls._cached_data = data if isinstance(data, dict) else {}
        except FileNotFoundError:
            cls._cached_data = {}
        except ValueError:
            # Unreadable settings (bad JSON or encoding): set the file aside rather than
            # silently overwriting it with defaults on the next save
            try:
                os.replace(cls._json_path, cls._json_path + '.corrupt')
            except OSError:
                pass
            cls._cached_data = {}
        except OSError:
            cls._cached_data = {}

    def loadJSON(self):
        json_class.load_if_needed()
        # Deep copy: callers edit nested presets/custom_tools before saving
        return copy.deepcopy(json_class._cached_data)

    def update_dict(self, new_data=None):
        json_class.load_if_needed()
        json_class._cached_data.update(copy.deepcopy(new_data or {}))
        self.dumpJSON()

    def dumpJSON(self):
        json_class.load_if_needed()
        text = json.dumps(json_class._cached_data, sort_keys=True, indent=4)
        # Write to a temp file and swap it in, so a crash mid-write can't leave an empty data.json
        tmp_path = self._json_path + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        for attempt in range(5):
            try:
                os.replace(tmp_path, self._json_path)
                return
            except PermissionError:
                # Windows: antivirus/indexer can briefly hold the target open
                if attempt == 4:
                    raise
                time.sleep(0.05)
