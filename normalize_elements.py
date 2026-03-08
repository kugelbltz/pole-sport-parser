#   - Read CSV
#   - Normalize codes → `id`
#   - Normalize categories (enum)
#   - Normalize technical value (float → int)
#   - Normalize criteria keys
#   - Store criteria as list of {type, raw}
#   - Add additionnal data like aliases, tips...etc
#   - Output canonical JSON per element

from dataclasses import dataclass, is_dataclass, asdict
from constants import OUTPUT_DIR, INPUT_DIR
import json
import logging

from extract_pdf import EXTRACTED_ELEMENTS_PATH
import pandas as pd
from pathlib import Path
from enum import StrEnum

NORMALIZED_OUTPUT_DIR=OUTPUT_DIR.joinpath("normalized")
NORMALIZED_ELEMENTS_DIR = NORMALIZED_OUTPUT_DIR.joinpath("elements")
INPUT_ELEMENT_DATA_DIR = INPUT_DIR.joinpath("elements")

logger = logging.getLogger("normalize_elements")
logging.basicConfig(level=logging.INFO)

def read_raw_elements_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)

class ElementCategory(StrEnum):
    SPIN = "spin"
    STATIC = "static"
    STRENGTH = "strength"
    FLEXIBILITY = "flexibility"
    UNKNOWN = "unknown"

    @classmethod
    def fromCode(cls, code: str) -> "ElementCategory":
        if code.startswith("SP"):
            return cls.SPIN
        elif code.startswith("ST"):
            return cls.STATIC
        elif code.startswith("S"):
            return cls.STRENGTH
        elif code.startswith("F"):
            return cls.FLEXIBILITY
        else:
            return cls.UNKNOWN

class CriteriaType(StrEnum):
    ARM_GRIP = "arm_grip"
    BODY_POSITION = "body_position"
    HOLD = "hold"
    POINTS_OF_CONTACT = "points_of_contact"
    LEG_POSITION = "leg_position"
    ANGLE_OF_SPLIT = "angle_of_split"
    STARTING_POSITION = "starting_position"
    UNKNOWN = "unknown"

def normalize_name(name: str):
    return name.replace("\n", " - ")

def get_criteria_type(key: str) -> CriteriaType:
    match key:
        case "grip_is" | "arm_position" |"grip" |"arm_position/grip" | "grip/arm_position" | "arm/position_grip" | "arm_position_/_grip":
            return CriteriaType.ARM_GRIP

        case "body_position" | "-_body_position":
            return CriteriaType.BODY_POSITION

        case "hold_the_position":
            return CriteriaType.HOLD

        case "points_of_contact":
            return CriteriaType.POINTS_OF_CONTACT

        case "leg_position":
            return CriteriaType.LEG_POSITION

        case "angle_of_split":
            return CriteriaType.ANGLE_OF_SPLIT

        case "starting_position":
            return CriteriaType.STARTING_POSITION

        case _:
            return CriteriaType.UNKNOWN

class DataclassJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if is_dataclass(o):
            return asdict(o)  # convert dataclass to dict
        return super().default(o)

@dataclass
class Criterion:
    type: CriteriaType
    items: list[str]

def normalize_criteria(text: str) -> list[Criterion]:
    data: dict[CriteriaType, list[str]] = {}

    # Split into bullet points
    bullets = text.strip().split("\n- ")
    bullets[0] = bullets[0].lstrip("- ")


    for bullet in bullets:
        if ":" in bullet:
            key, value = bullet.split(":", 1)
            key = key.strip().lower().replace(" ", "_")
            value = value.strip().replace("\n"," ")

            criterion_type = get_criteria_type(key)
            data.setdefault(criterion_type, []).append(value)

    return [ Criterion(type=type, items=items) for type, items in data.items()]



def save_rows_as_json(df: pd.DataFrame, output_dir: Path, id_column="id"):
    output_dir.mkdir(parents=True, exist_ok=True)

    for _, row in df.iterrows():
        record = row.dropna().to_dict()
        file_id = record[id_column]

        filepath = output_dir.joinpath(f"{file_id}.json")

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=4, ensure_ascii=False, cls=DataclassJSONEncoder)

def merge_normalized_with_manual_data(normalized_dir: Path, input_data_dir: Path):
    for element_path in normalized_dir.iterdir():
        with element_path.open() as f:
            element = json.load(f)

        element_data_path = input_data_dir.joinpath(element_path.name)
        if element_data_path.exists():
            with element_data_path.open() as f:
                data = json.load(f)

            element.update(data)

            with element_path.open("w") as f:
                json.dump(element, f, indent=4)

if __name__ == "__main__":
    logger.info("Normalize element data")

    df = read_raw_elements_csv(EXTRACTED_ELEMENTS_PATH)

    df = df.rename(columns={'code': 'id'})
    df["name"] = df["name"].apply(normalize_name)
    df["category"] = df["id"].apply(ElementCategory.fromCode)
    df["criteria"] = df["criteria"].apply(normalize_criteria)

    save_rows_as_json(df, NORMALIZED_ELEMENTS_DIR)
    merge_normalized_with_manual_data(NORMALIZED_ELEMENTS_DIR, INPUT_ELEMENT_DATA_DIR)
