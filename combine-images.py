import re
import shutil
import tkinter as tk
from pathlib import Path

from PIL import Image, ImageTk

INPUT_DIR = Path("out/images")
OUTPUT_DIR = Path("out/merged")
OUTPUT_DIR.mkdir(exist_ok=True)

SPLIT_PATTERN = re.compile(
    r"^([A-Za-z]{1,2}\d{1,3})_(\d+)_of_(\d+)\.jpe?g$", re.IGNORECASE
)
NORMAL_PATTERN = re.compile(r"^([A-Za-z]{1,2}\d{1,3})\.jpe?g$", re.IGNORECASE)


# ---------- Image helpers ----------


def resize_to_width(img, target_width):
    if img.width == target_width:
        return img
    ratio = target_width / img.width
    new_height = int(img.height * ratio)
    return img.resize((target_width, new_height), Image.Resampling.LANCZOS)


def resize_to_height(img, target_height):
    if img.height == target_height:
        return img
    ratio = target_height / img.height
    new_width = int(img.width * ratio)
    return img.resize((new_width, target_height), Image.Resampling.LANCZOS)


def combine_vertical(images):
    max_width = max(img.width for img in images)
    resized = [resize_to_width(img, max_width) for img in images]

    total_height = sum(img.height for img in resized)
    result = Image.new("RGB", (max_width, total_height))

    y = 0
    for img in resized:
        result.paste(img, (0, y))
        y += img.height
    return result


def combine_horizontal(images):
    max_height = max(img.height for img in images)
    resized = [resize_to_height(img, max_height) for img in images]

    total_width = sum(img.width for img in resized)
    result = Image.new("RGB", (total_width, max_height))

    x = 0
    for img in resized:
        result.paste(img, (x, 0))
        x += img.width
    return result


# ---------- GUI ----------


class ChoiceWindow:
    def __init__(self, vertical_img, horizontal_img):
        self.choice = None
        self.root = tk.Tk()
        self.root.title("Choose merge orientation")

        preview = self.build_preview(vertical_img, horizontal_img)

        # Scale preview if too large
        max_preview_width = 1200
        if preview.width > max_preview_width:
            ratio = max_preview_width / preview.width
            preview = preview.resize(
                (int(preview.width * ratio), int(preview.height * ratio)),
                Image.Resampling.LANCZOS,
            )

        self.tk_image = ImageTk.PhotoImage(preview)

        label = tk.Label(self.root, image=self.tk_image)
        label.pack(padx=10, pady=10)

        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=10)

        tk.Button(
            btn_frame,
            text="Vertical",
            width=15,
            command=self.choose_vertical,
        ).pack(side=tk.LEFT, padx=10)

        tk.Button(
            btn_frame,
            text="Horizontal",
            width=15,
            command=self.choose_horizontal,
        ).pack(side=tk.LEFT, padx=10)

        self.root.mainloop()

    def build_preview(self, vertical_img, horizontal_img):
        gap = 20
        bg = (30, 30, 30)

        width = vertical_img.width + horizontal_img.width + gap
        height = max(vertical_img.height, horizontal_img.height)

        preview = Image.new("RGB", (width, height), bg)
        preview.paste(vertical_img, (0, 0))
        preview.paste(horizontal_img, (vertical_img.width + gap, 0))
        return preview

    def choose_vertical(self):
        self.choice = "v"
        self.root.destroy()

    def choose_horizontal(self):
        self.choice = "h"
        self.root.destroy()


# ---------- Main ----------


def main():
    files = list(INPUT_DIR.glob("*.jp*g"))

    grouped = {}
    singles = []

    # Scan files
    for file in files:
        name = file.name

        split_match = SPLIT_PATTERN.match(name)
        normal_match = NORMAL_PATTERN.match(name)

        if split_match:
            base, idx, total = split_match.groups()
            grouped.setdefault(base, []).append((int(idx), file))
        elif normal_match:
            singles.append(file)

    # Copy non-split images
    for file in singles:
        shutil.copy2(file, OUTPUT_DIR / file.name)
        print(f"Copied {file.name}")

    # Process split images
    for base, parts in grouped.items():
        parts.sort(key=lambda x: x[0])
        image_paths = [p for _, p in parts]

        print(f"\nProcessing {base}")

        images = [Image.open(p).convert("RGB") for p in image_paths]

        vertical = combine_vertical(images)
        horizontal = combine_horizontal(images)

        chooser = ChoiceWindow(vertical, horizontal)
        choice = chooser.choice

        result = vertical if choice == "v" else horizontal
        output_path = OUTPUT_DIR / f"{base}.jpg"
        result.save(output_path, "JPEG", quality=95)

        print(f"Saved {output_path.name}")

        for img in images:
            img.close()


if __name__ == "__main__":
    main()
