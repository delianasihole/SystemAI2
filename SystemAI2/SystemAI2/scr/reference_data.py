import csv
import json
import os
from functools import lru_cache

DATA_PATH = "data"


@lru_cache(maxsize=1)
def load_staff():
    path = os.path.join(DATA_PATH, "staff_directory.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_crm():
    path = os.path.join(DATA_PATH, "crm.csv")
    with open(path, newline="", encoding="utf-8") as f:
        return tuple(csv.DictReader(f))
