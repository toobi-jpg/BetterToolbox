import json
from os import path

class json_class:
    fileDir = path.dirname(path.realpath(__file__))
    _json_path = path.join(fileDir, 'data.json')

    def __init__(self):
        self.existing_data = {}
        try:
            with open(self._json_path, 'r') as f:
                self.existing_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.existing_data = {}

    def loadJSON(self):
        try:
            with open(self._json_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def update_dict(self, new_data=None):
        if new_data is None:
            new_data = {}
        try:
            with open(self._json_path, 'r') as f:
                disk_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            disk_data = {}
        disk_data.update(new_data)
        self.existing_data = disk_data
        self.dumpJSON()

    def dumpJSON(self):
        json_object = json.dumps(self.existing_data, sort_keys=True, indent=4)
        with open(self._json_path, 'w') as f:
            f.write(json_object)
