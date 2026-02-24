import json
import logging
from dataclasses import astuple, dataclass

import pandas as pd
import pdfplumber
from pdfminer.image import ImageWriter
from pdfminer.layout import LTImage

logger = logging.getLogger("parser")
logging.basicConfig(level=logging.INFO)

FIRST_FLEXIBILITY_PAGE = 26
FIRST_STRENGTH_PAGE = 54
FIRST_SPIN_STATIC_PAGE = 76
FIRST_SPIN_SPIN_PAGE = 84
LAST_SPIN_SPIN_PAGE = 100

FIRST_PAGE = FIRST_FLEXIBILITY_PAGE
FIRST_PAGE_INDEX = FIRST_FLEXIBILITY_PAGE - 1
LAST_PAGE_INDEX = LAST_SPIN_SPIN_PAGE

VERTICAL_LINES = [35, 75, 175, 305, 350, 564]


@dataclass
class Boundaries:
    left: int
    top: int
    right: int
    bottom: int


def get_crop_boundaries(page_number: int) -> Boundaries:
    boundaries = Boundaries(35, 45, 565, 775)

    match page_number:
        case 26:
            boundaries.top = 210
        case 54 | 76 | 84:
            boundaries.top = 75

    return boundaries


def get_vertical_lines(page_number: int) -> list:
    match page_number:
        case 29 | 30 | 31 | 32 | 33:
            return [35, 75, 170, 305, 345, 564]
        case 69 | 70 | 83:
            return [35, 75, 175, 305, 350, 560]
        case _:
            return [35, 75, 175, 305, 350, 565]


def parse_criteria(text):
    data = {}

    # Split into bullet points
    bullets = text.strip().split("\n- ")
    bullets[0] = bullets[0].lstrip("- ")

    for bullet in bullets:
        if ":" in bullet:
            key, value = bullet.split(":", 1)
            key = key.strip().lower().replace(" ", "_")
            value = value.strip()
            data[key] = value

    bad_columns = {
        "grip/arm_position": "arm_position/grip",
        "arm/position_grip": "arm_position/grip",
        "arm_position_/_grip": "arm_position/grip",
        "angle_of_the_split": "angle_of_split",
        "-_angle_of_split": "angle_of_split",
        "-_body_position": "body_position",
        "grip_is": "grip",
    }

    for bad_key, good_key in bad_columns.items():
        if (criteria := data.get(bad_key)) is not None:
            data.setdefault(good_key, criteria)
            data.pop(bad_key, None)

    return data


def create_image(image_data: dict, name: str = "image") -> LTImage:
    bbox = (
        image_data["x0"],
        image_data["y0"],
        image_data["x1"],
        image_data["y1"],
    )
    return LTImage(name, image_data["stream"], bbox)


def get_category(code: str):
    if code.startswith("SP"):
        return "spin"
    elif code.startswith("ST"):
        return "static"
    elif code.startswith("S"):
        return "strength"
    elif code.startswith("F"):
        return "flexibility"
    else:
        return "unknown"


PAGES_TO_DEBUG = []
with pdfplumber.open(
    "ipsf_pole_sports_code_of_points_2025-2027_final_070120240.pdf"
) as pdf:
    dfs = []

    # iterate over each page
    for page_number, page in enumerate(
        pdf.pages[FIRST_PAGE_INDEX:LAST_PAGE_INDEX], FIRST_PAGE
    ):
        logger.info("Parsing page number %i", page_number)

        crop_boundaries = get_crop_boundaries(page_number=page_number)
        cropped = page.crop(astuple(crop_boundaries))
        table_settings = {
            "vertical_strategy": "explicit",
            "explicit_vertical_lines": get_vertical_lines(page_number),
        }

        # Debug visually.
        if page_number in PAGES_TO_DEBUG:
            image = cropped.to_image(resolution=200)
            image.reset().debug_tablefinder(table_settings)
            image.save(f"debug/page_{page_number}.png", format="PNG")

            continue

        table = cropped.extract_table(table_settings=table_settings)

        if not table:
            logger.warning(f"No table found in page {page_number}")
            continue

        df = pd.DataFrame(table[1:], columns=table[0])
        df.columns = ["code", "name", "element", "technicalValue", "criteria"]

        # Apply to dataframe
        df["criteria"] = df["criteria"].apply(parse_criteria)
        df["page_number"] = page_number
        df["image"] = df["code"].apply(lambda code: f"/images/{code}.jpg")
        df["category"] = df["code"].apply(get_category)

        # {
        #   "name": "Ballerina",
        #   "code": "F4",
        #   "image": "/38.jpg",
        #   "technicalValue": 0.1,
        #   "criteria": { "hold": "5 seconds", "armPosition": "upper" },
        #   "category": "flexibility"
        # },

        df = df.drop(
            ["please_refer_to_the_glossary", "element"], axis=1, errors="ignore"
        )

        # # extract images
        # table_data = cropped.find_table(table_settings=table_settings)
        # if not table_data:
        #     logger.warning(f"No table found in page {page_number}")
        #     continue

        # for row_index, row in enumerate(
        #     table_data.rows[1:]
        # ):  # skip first row because its the header
        #     image_cell = row.cells[2]

        #     if image_cell:
        #         cropped_to_image = page.crop(image_cell)
        #         if len(cropped_to_image.images) < 1:
        #             logger.warning("ISSUE WITH IMAGE")
        #         else:
        #             code = df["Code No."].iloc[row_index]

        #             lt_images = list(
        #                 map(
        #                     lambda image: create_image(image),
        #                     cropped_to_image.images,
        #                 )
        #             )

        #             imagewriter = ImageWriter("out/images")
        #             for index, lt_image in enumerate(lt_images):
        #                 name = (
        #                     f"{code}_{index + 1}_of_{len(lt_images)}"
        #                     if len(lt_images) > 1
        #                     else code
        #                 )

        #                 lt_image.name = name
        #                 imagewriter.export_image(lt_image)

        dfs.append(df)

    df = pd.concat(dfs)

    df = df.astype({"technicalValue": float, "page_number": int})

    df.to_json("out/singles_elements.json", orient="records", indent=4)
