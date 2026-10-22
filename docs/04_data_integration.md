# Step 2 — Dataset Integration Checklist

The dataset described on Monash University's LMGA website is our **candidate**
source. The official page lists image counts and annotation categories but
does not specify all raw file details required by the project.

Source page:
https://www.monash.edu/engineering/lmga/news/y-shaped-tree-dataset-for-tree-branch-prediction
Download link on that page:
https://drive.google.com/file/d/1-6akVXezq26ihtDrVH9czGUQDFd8Py81/view?usp=drive_web

## Inspect before writing any reconstruction code

1. Obtain the dataset through a permitted source; record access date and terms.
2. Inventory RGB, depth, position, visible-branch, whole-branch annotation files.
3. Determine whether labels are PNG masks, polygons, keypoints or another format.
4. Inspect RGB/depth spatial registration, resolution and any camera intrinsic matrix.
5. Verify raw depth units and invalid-pixel codes (zero, NaN, maximum values).
6. Establish sample/tree IDs and whether scenes repeat between seasons.
7. Decide if whole-branch GT is 2D, 3D, or both.
8. Implement a dataset-specific loader that converts original labels to
   internal masks **without modifying the originals**.
9. Create `data/manifest.csv` using the columns in `manifest.py` (adapter format).
10. Run the audit on genuine images and retain a reproducible summary.

## Provisional manifest header

```
sample_id,season,tree_id,rgb_path,depth_path,visible_mask_path,whole_mask_path,calibration_path
```

Paths resolve relative to the CSV file. `tree_id` and `calibration_path` can
be empty. The official folder structure is **unknown** until inspected.

## Decision gate

If camera intrinsics/depth scale or registration cannot be established,
complete and validate **2D amodal branch segmentation** first. Present 3D
as conditional or qualitative, not experimentally verified metric output.
