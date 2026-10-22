"""Generate a small synthetic RGB-D fixture for input audit demonstrations.

This fixture is not an apple-tree experimental dataset and does not measure
reconstruction performance. It is used to verify pairing and mask formats.
"""
import csv
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def main() -> None:
    base = Path(__file__).resolve().parents[1] / "data" / "demo"
    base.mkdir(parents=True, exist_ok=True)
    width = height = 128
    visible_image = Image.new("L", (width, height), 0)
    whole_image = Image.new("L", (width, height), 0)
    # Synthetic upward-opening Y; the middle part of the right branch is hidden.
    lines = [(64, 117, 64, 70), (64, 70, 22, 22), (64, 70, 110, 20)]
    for image in (visible_image, whole_image):
        draw = ImageDraw.Draw(image)
        for line in lines:
            draw.line(line, fill=255, width=7)
    draw = ImageDraw.Draw(visible_image)
    draw.line((76, 58, 94, 40), fill=0, width=13)
    whole = np.asarray(whole_image)
    rgb = np.zeros((height, width, 3), dtype=np.uint8)
    rgb[..., 0] = 105
    rgb[..., 1] = 134
    rgb[..., 2] = 108
    rgb[whole > 0] = [119, 82, 52]
    depth = np.full((height, width), 1250, dtype=np.uint16)  # illustrative millimetres only
    depth[whole == 0] = 0
    Image.fromarray(rgb).save(base / "rgb.png")
    Image.fromarray(depth).save(base / "depth.png")
    visible_image.save(base / "visible.png")
    whole_image.save(base / "whole.png")
    (base / "calibration.json").write_text(json.dumps({
        "fx": 130.0, "fy": 130.0, "cx": 64.0, "cy": 64.0,
        "depth_unit_to_m": 0.001}, indent=2), encoding="utf-8")
    with (base / "manifest.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "sample_id", "season", "tree_id", "rgb_path", "depth_path",
            "visible_mask_path", "whole_mask_path", "calibration_path"])
        writer.writeheader()
        writer.writerow({"sample_id": "synthetic_y_001", "season": "winter",
                         "tree_id": "fixture_y_1", "rgb_path": "rgb.png",
                         "depth_path": "depth.png", "visible_mask_path": "visible.png",
                         "whole_mask_path": "whole.png", "calibration_path": "calibration.json"})
    print(f"Created synthetic format-demo at: {base}")


if __name__ == "__main__":
    main()
