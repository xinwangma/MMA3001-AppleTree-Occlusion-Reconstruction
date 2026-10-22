# Real Apple Tree dataset inspection

Inspection date: 22 October 2026. Scope: the entire local
`data/raw/monash_y_tree/TreeID` tree. This report describes the supplied files,
not the completeness of an upstream download or claims from a publication.

## Method and reproducibility

`scripts/inspect_monash_dataset.py` recursively inventories every file, computes
SHA-256 of its bytes, fully decodes every PNG with Pillow, records image format,
size, mode, dtype, range, metadata keys and EXIF, and computes decoded-pixel hashes.
For depth and GT it also counts unique colours, zero pixels, channel equality and
the eight most frequent colours. It groups modalities by leading tree ID and
season, checks pairing, timestamps and dimensions, and compares the two folders
by names, bytes and decoded pixels. It emits JSON to stdout and has no write API.
Size and modification time are checked again at the end to detect source changes
during inspection; these checks are not a second independent content hash.

From the repository root:

```powershell
python scripts/inspect_monash_dataset.py | Out-File -LiteralPath results/monash_inspection.json -Encoding utf8
```

The actual scan output is retained locally in the ignored `results` directory.
Windows PowerShell adds a UTF-8 BOM with this command, so Python readers should
use `encoding="utf-8-sig"`. Dependencies are the existing NumPy and Pillow project
dependencies. `--root PATH` supports another local copy. There is no sampling flag:
the numerical inspection covers all files. Visual review was limited to summer
RGB/depth/GT for R01N01, summer/winter RGB and summer GT for R04N01, R10N01 and
R20N01, and the satellite overview. Preview composites were written only under
`results`; originals were opened for reading only.

## Recursive structure and formats

```text
TreeID/
  FANK_Sat.png
  Dataset/                   # flat; no nested directories
  Dataset (With Summer GT)/  # flat; no nested directories
```

There are **4,987 files**, all PNG, totalling **1,517,628,069 bytes**.
There are no other directories, text descriptions, manifests, calibration files,
JSON/XML labels, point clouds, meshes, skeleton graphs or position tables.

| Property | Dataset | Dataset (With Summer GT) |
|---|---:|---:|
| Files | 2,176 | 2,810 |
| Bytes | 744,483,564 | 770,270,225 |
| Leading tree IDs | 544 | 562 |
| Summer RGB | 544 | 562 |
| Summer depth (`D`) | 544 | 562 |
| Summer GT | 0 | 562 |
| Winter RGB | 544 | 562 |
| Winter depth (`D`) | 544 | 562 |
| Winter GT | 0 | 0 |

RGB and depth images are all **640×480, PNG RGB, uint8**. Summer GT images are
all **256×256, PNG L, uint8**. `FANK_Sat.png` is **1329×929, PNG RGBA, uint8**,
2,874,280 bytes. Visual inspection shows an aerial orchard overview with red
markings; it is not a per-tree RGB/depth observation or a metric camera model.

## IDs, seasonal distribution and pairing

Typical names are `R01U01_Summer_RGB-12-40-50.png` in the first folder and
`R01N01_Summer_RGB-12-40-50.png` in the second; these examples illustrate the
grammar, not a verified cross-folder correspondence. Leading IDs use `U` in
Dataset and `N` in With Summer GT. A row prefix, tree number, season, modality
and time-like suffix are encoded in each name. Their physical meanings and the
time zone/date of acquisition are not documented locally.

An exceptional winter grammar embeds another ID, for example
`R04U01_Winter_D-R04N03_RGB_12-17-14.png`. There are 62 such files in Dataset
(31 RGB/depth pairs) and 42 in With Summer GT (21 pairs). The embedded `RGB`
token does not override the leading `D` modality. The script retains the embedded
source ID separately instead of dropping these records or assuming that it is
the leading tree ID. A parser accepting only a numeric timestamp would
incorrectly report missing winter observations.

Each folder contains equal summer and winter RGB/depth observation counts:
1,088 seasonal observations in Dataset and 1,124 in With Summer GT. All leading
tree IDs occur in both seasons, and summer GT covers every summer observation
in the second folder. This is filename-based pairing; it does not prove correct
physical tree identity, identical camera viewpoint or cross-season registration.
There are no supplied train/validation/test splits. Keep seasons of the same
verified physical tree together when designing splits, and resolve cross-release
identity before combining releases.

Leading row-prefix distributions are substantially different:

| Row | Dataset trees | With Summer GT trees |
|---|---:|---:|
| R01 | 20 | 44 |
| R02 | 20 | 43 |
| R03 | 25 | 34 |
| R04 | 31 | 21 |
| R05 | 19 | 34 |
| R06 | 18 | 32 |
| R07 | 17 | 32 |
| R08 | 25 | 22 |
| R09 | 9 | 34 |
| R10 | 14 | 29 |
| R11 | 22 | 22 |
| R12 | 13 | 34 |
| R13 | 13 | 33 |
| R14 | 13 | 30 |
| R15 | 18 | 28 |
| R16 | 21 | 24 |
| R17 | 21 | 23 |
| R18 | 20 | 26 |
| R19 | 30 | 11 |
| R20 | 38 | 6 |
| R21 | 46 | 0 |
| R22 | 44 | 0 |
| R23 | 47 | 0 |

## Comparison of the two releases

With Summer GT has 18 more leading tree IDs and 634 more files: 72 additional
RGB/depth files by count and 562 masks. This arithmetic does **not** establish
that it contains Dataset as a subset. There are **zero common filenames** and
**zero exact RGB decoded-pixel matches** across the two folders. Similar scenes
could still represent the same trees after re-export or other processing; hash
inequality cannot exclude that possibility. Simply replacing `U` with `N` is
not a verified identity mapping.

Only **21 Dataset files** have a byte-identical counterpart anywhere in the GT
folder; **31** have an exact decoded-pixel counterpart. All are winter depth
images, not RGB. There is a particularly concerning duplication: all 31
embedded-ID winter depth files in Dataset have the **same decoded image**, and
the same image occurs in 22 GT-folder depth files (the 21 embedded-ID files plus
`R03N34_Winter_D-11-39-13.png`). These are not all-black placeholders: the shared
image has 155 distinct grayscale values spanning 0–167. Associated RGB frames
are different. This supports flagging these depth observations for investigation;
the files alone cannot establish whether a capture, export or association error
caused the duplication. Do not treat their depth as independently verified.

Within Dataset, the 1,088 RGB files are all distinct by decoded pixels; the
1,088 depth files have 1,058 distinct decoded images. Within With Summer GT,
all 1,124 RGBs and all 562 GTs are distinct, while 1,124 depth files have 1,103
distinct decoded images. These are exact-duplicate checks, not perceptual scene
matching or physical-tree identification.

## RGB and depth

Sampled summer images contain foliage and fruit that obscure the main branches;
winter views expose the branch structure. Background trees, supports and ground
remain in the frames. Full decoding establishes file readability, not image
quality or annotation correctness for every scene.

All depth PNGs store equal red, green and blue channels: they are grayscale
values replicated into an RGB container, not 16-bit scalar depth PNGs. Black
regions are visible in previews. The local files do not establish whether values
were normalized, clipped, inverted or scaled, or whether zero denotes an invalid
measurement. A uint8 value must not be interpreted directly as millimetres.
Equal RGB/depth dimensions and matching suffixes establish nominal pairing only;
pixel registration, lens distortion and RGB-to-depth extrinsics remain unverified.

The all-pixel statistics below count zeros without assuming their meaning.
Ranges include zero; distinct levels are reported as the per-image minimum and
maximum, and zero percentages pool all pixels in the stated group.

| Folder/season | Depth images | Stored range | Distinct levels/image | Zero pixels |
|---|---:|---|---|---:|
| Dataset summer | 544 | 0–245 | 113–178 | 13.7622% |
| Dataset winter | 544 | 0–244 | 51–166 | 57.5501% |
| With Summer GT summer | 562 | 0–194 | 74–180 | 16.1517% |
| With Summer GT winter | 562 | 0–242 | 22–164 | 55.7591% |

Winter has substantially more zero-valued depth pixels in both releases.
This is an observed seasonal difference in stored values, not a verified sensor
failure rate or measure of branch visibility.

## Visible branches and whole-branch ground truth

There are **no separately named visible-branch annotations** in either folder.
Winter RGB images are observations, not visible masks or whole-tree labels.
There are **562 summer GT raster masks**, exclusively in With Summer GT, and no
winter GT. Every GT contains exactly two values, **0 and 255**, so the stored
labels are binary rather than coloured classes, polygons or keypoint tables.
White foreground occupies 5.8807–10.4340% of individual GT images, averaging
7.5450%; none of the masks is empty or entirely foreground.

The reviewed masks show a filled central trunk and two main arms, including
portions hidden by summer foliage. They are consistent with a 2D whole-main-branch
or amodal target. The local files do not document the annotation protocol, how
hidden branches were inferred, whether masks were derived from winter images,
or whether secondary branches should be included. Calling these exhaustive
whole-tree ground truth would exceed the evidence. There is no 3D GT, depth for
occluded branch surfaces, branch connectivity table or visibility flag per pixel.

Every summer triplet has a dimension mismatch: **640×480 RGB/depth versus
256×256 GT**. A direct resize would change aspect ratio. The files do not specify
whether GT was generated after resizing, cropping, padding or registration.
Verify the transform before using these masks for pixelwise evaluation; do not
silently resize and claim established alignment. Once confirmed, use nearest
neighbour interpolation for binary labels and keep any converted data outside raw.

## Camera calibration and unverifiable assumptions

No intrinsic matrix, focal lengths, principal point, distortion coefficients,
depth scale, RGB/depth extrinsics, camera poses or sensor model were found.
All 4,987 images have empty EXIF; the 4,986 dataset images have no Pillow metadata
keys. Only the satellite image contains `dpi`, `gamma` and `srgb`, which do not
provide camera calibration or georeferencing.

Consequently metric 3D reconstruction is not validated by this package alone.
The following require upstream documentation or independent verification:

- depth units, transfer function and invalid-value conventions;
- camera calibration and RGB/depth spatial registration;
- the exact 640×480-to-256×256 annotation transform;
- identity correspondence across seasons and between `U` and `N` releases;
- meaning of embedded source IDs, acquisition dates and annotation policy;
- provenance, download completeness and redistribution/licence terms.

The supported next step is to verify the 2D annotation transform and obtain or
create visible-branch labels before claiming supervised occlusion evaluation.
Metric 3D experiments require additional calibration and depth documentation.

## Validation and data protection

The full scan decoded all 4,987 PNGs without errors and detected no size or
modification-time changes during inspection. Synthetic tests cover recursive
inventory, missing modalities, mismatched dimensions and timestamps, renamed
content duplicates, corrupt PNG reporting, both filename grammars and source
byte/mtime preservation. The complete repository suite passed: **17 tests**.

The installed Python lacked pytest. After the sandbox blocked a dependency
download, an approved installation placed pytest under ignored
`results/test_dependencies`; no project dependency declarations were changed.
The test command was:

```powershell
$env:PYTHONPATH = "$PWD/results/test_dependencies;$PWD/src"
python -m pytest -q
```

Raw data is covered by `data/raw/` in `.gitignore`, and `git ls-files data/raw`
returned no tracked files. JSON inventories and preview images remain ignored
under `results/`. No original image was rewritten, and no commit or push was made.
