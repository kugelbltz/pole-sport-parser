import shutil
from constants import OUTPUT_DIR, INPUT_DIR
import logging
from dataclasses import astuple, dataclass
from pathlib import Path

import pandas as pd
import pdfplumber
from pdfminer.image import ImageWriter
from pdfminer.layout import LTImage
from pdfplumber.table import Table

logger = logging.getLogger("extract_pdf")
logging.basicConfig(level=logging.INFO)

INPUT_PDF = INPUT_DIR.joinpath("ipsf_pole_sports_code_of_points_2025-2027_final_070120240.pdf")

EXTRACTED_DIR = OUTPUT_DIR.joinpath("extracted")
EXTRACTED_IMAGES_DIR = EXTRACTED_DIR.joinpath("images")
EXTRACTED_ELEMENTS_PATH = EXTRACTED_DIR.joinpath("raw_elements.csv")

FIRST_FLEXIBILITY_PAGE = 26
FIRST_STRENGTH_PAGE = 54
FIRST_SPIN_STATIC_PAGE = 76
FIRST_SPIN_SPIN_PAGE = 84
LAST_SPIN_SPIN_PAGE = 100

FIRST_PAGE = FIRST_FLEXIBILITY_PAGE
LAST_PAGE = LAST_SPIN_SPIN_PAGE
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

def get_format(page_number: int):
    if page_number >= FIRST_FLEXIBILITY_PAGE and page_number <= LAST_SPIN_SPIN_PAGE:
        return "single"
    else:
        return "unknown"

def extract_element_data(table: Table) -> pd.DataFrame:
    table_data = table.extract()

    df = pd.DataFrame(table_data[1:], columns=table_data[0])
    df.columns = ["code", "name", "element", "technicalValue", "criteria"]

    return df

def extract_table_images(table: Table, df: pd.DataFrame):
    for row_index, row in enumerate(
        table.rows[1:]
    ):  # skip first row because its the header
        image_cell = row.cells[2]

        if image_cell is None:
            logger.warning(f"No image found for in row {row_index}")
            continue

        cropped_to_image = page.crop(image_cell)
        if len(cropped_to_image.images) < 1:
            logger.warning("ISSUE WITH IMAGE")
            continue

        code = df["code"].iloc[row_index]

        lt_images = list(
            map(
                lambda image: create_image(image),
                cropped_to_image.images,
            )
        )

        imagewriter = ImageWriter(str(EXTRACTED_IMAGES_DIR))
        for index, lt_image in enumerate(lt_images):
            name = (
                f"{code}_{index + 1}_of_{len(lt_images)}"
                if len(lt_images) > 1
                else code
            )

            lt_image.name = name
            imagewriter.export_image(lt_image)


if __name__ == "__main__":
    PAGES_TO_DEBUG = []

    logger.info("Removing image output directory")
    shutil.rmtree(EXTRACTED_IMAGES_DIR, ignore_errors=True)

    with pdfplumber.open(INPUT_PDF) as pdf:
        dfs: list[pd.DataFrame] = []

        for page_number, page in enumerate(
            pdf.pages[FIRST_PAGE_INDEX:LAST_PAGE_INDEX], FIRST_PAGE
        ):
            logger.info("Parsing page number %i", page_number)

            # Crop page to an area aound the table
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
                image.show()
                continue

            table = cropped.find_table(table_settings=table_settings)
            if not table:
                logger.warning(f"No table found in page {page_number}")
                continue

            df = extract_element_data(table)
            df["page"] = page_number
            df["format"] = get_format(page_number)
            dfs.append(df)

            # extract images
            extract_table_images(table, df)

            dfs.append(df)

        df = pd.concat(dfs)

        df = df.drop(
            ["element"], axis=1, errors="ignore"
        )
        df = df.astype({"technicalValue": float, "page": int})

        df.to_csv(EXTRACTED_ELEMENTS_PATH, index=False)
