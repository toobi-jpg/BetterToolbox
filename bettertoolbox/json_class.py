import json
from os import path

class json_class:
    fileDir = path.dirname(path.realpath(__file__))
    _json_path = path.join(fileDir, 'data.json')
    _cached_data = None

    def __init__(self):
        self.load_if_needed()
        self.existing_data = json_class._cached_data.copy()

    @classmethod
    def load_if_needed(cls):
        if cls._cached_data is None:
            try:
                with open(cls._json_path, 'r') as f:
                    cls._cached_data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                cls._cached_data = {}

    def loadJSON(self):
        json_class.load_if_needed()
        return json_class._cached_data.copy()

    def update_dict(self, new_data=None):
        if new_data is None:
            new_data = {}
        json_class.load_if_needed()
        json_class._cached_data.update(new_data)
        self.existing_data = json_class._cached_data.copy()
        self.dumpJSON()

    def dumpJSON(self):
        json_class._cached_data = self.existing_data.copy()
        json_object = json.dumps(self.existing_data, sort_keys=True, indent=4)
        with open(self._json_path, 'w') as f:
            f.write(json_object)
