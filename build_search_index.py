from constants import OUTPUT_DIR
from normalize_elements import NORMALIZED_ELEMENTS_DIR

import json

import logging


logger = logging.getLogger("search_index")
logging.basicConfig(level=logging.INFO)


if __name__ == "__main__":
    search_index = []

    for file in NORMALIZED_ELEMENTS_DIR.iterdir():
        with file.open() as f:
            element = json.load(f)
            tokens = [element["name"]] + element.get("aliases", []) + [c["type"] for c in element["criteria"]]
            tokens_flat = []
            for t in tokens:
                tokens_flat += t.replace("-", " ").split()  # flatten multi-word tokens

            entry = {
                "id": element["id"],
                "name": element["name"],
                "aliases": element.get("aliases", []),
                "category": element["category"],
                "technicalValue": element["technicalValue"],
                "criteriaTypes": [c["type"] for c in element["criteria"]],
                "searchTokens": list(set(tokens_flat)),  # remove duplicates
            }
            search_index.append(entry)

    OUTPUT_PATH = OUTPUT_DIR.joinpath("normalized", "element_index.json")
    with OUTPUT_PATH.open("w") as f:
        json.dump(search_index, f, indent=4)
