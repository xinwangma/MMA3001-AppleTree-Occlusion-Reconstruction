# AI Use Declaration and Reflection Log

## Entry 001 — Initial project planning and starter code (2026-10-22)

**Tool:** OpenAI ChatGPT (GPT-6).

**Use:** Assisted with interpreting the project brief, scoping a specific
occlusion-reconstruction task, drafting English documentation, designing the
source-code structure, generating a provisional manifest auditor and unit
tests, and identifying references for the proposed dataset and method.

**Approximate contribution:** High for initial writing and scaffolding.
The proportion in the final submission must be reassessed after the student
has edited and independently verified all substantive work.

**Why AI was used:** To develop a maintainable project organisation and
explicit validation plan within the course timeframe.

**Verification performed:** Initial automated unit tests executed in the
working environment. The real Monash dataset has NOT been inspected and no
physical reconstruction accuracy has been established.

**Student responsibility:** Confirm project and data source, dataset access
and permissions, test all functions on actual data, select methods and
parameters, check equations and numerical results, explain limitations,
and present the work without AI assistance.

**Known limitations:** AI proposals for label layout, camera calibration,
3D lifting and grouping information are hypotheses until validated against
original dataset documentation and files.

## Further entries
Add a dated entry for each meaningful AI-assisted code or report change.
Include rejected suggestions, detected errors, and independent corrections.

## Entry 002 — Step 3 implementation (2026-10-23)

Codex assisted with the NumPy thinning implementation, pixel-graph and runner design, tests, documentation and synthetic execution. Rejected using Summer whole GT as visible input because it leaks hidden geometry. Verification: 36 tests passed; synthetic overlay reviewed; input hashes/mtime unchanged. These are software checks, not independent real-tree validation. The student must review the algorithm, graph convention and limitations, and independently confirm real visible annotations before evaluation.

Step 3 readiness follow-up: Codex prepared RGB-only annotation/review scaffolding and executed integrity/negative-input checks. It did not fabricate visible annotations or treat GT alignment as validated. Independent human annotation/review is outstanding; 36 automated tests pass.

## Entry 003 ? Step 3 real-RGB annotation drafts and review (2026-10-23)

Codex visually inspected 12 new Summer RGBs and traced 30 conservative polygon
patches without using their Summer GT, winter or depth. These are AI-authored
RGB-only partial drafts, not manual human labels or independent truth. Provenance
and pending review status are explicit in data/annotations/step3_rgb_only_drafts.json.
Codex also wrote the manual editor, rasteriser, validation runner and tests,
reviewed the 12-panel contact sheet plus six detailed outputs, and documented
annotation gaps and graft-induced skeleton spur. 50 tests pass. Independent
human drawing/review and anatomical accuracy assessment are still required;
no annotator agreement or real accuracy results were invented.


## Entry 004 ? Step 3 coverage correction (2026-10-23)

Codex reviewed all 12 real RGBs and the old partial masks, improved the manual
editor and review/approval workflow, added QA/tests and generated final v4
before/after outputs. Important rejected AI work: initial v2 candidates overlapped
leaves, fruit or ground vegetation on magnified inspection; v3 polygon additions
created tiny loops/spurs at joins. Those runs are explicitly superseded. Final v4
uses narrower RGB-supported pieces and explicit right-arm replacements; 10 images
changed and 2 stayed unchanged due to ambiguity. All final labels remain AI drafts,
not student drawing or independent human review. More visible pixels do not prove
accuracy. No Summer GT/depth was used to make masks, no hidden connections were
added and no original RGB-D was written. 63 tests pass; human usability and full
coverage review still require actual people. Details: docs/13_step3_annotation_revision.md.


## 2026-10-25 — Step 6.1 interrupted-work recovery

Codex recovered the uncommitted fork-anchored detector/tests/evaluation script, ran development and frozen evaluation, and generated evidence-based documentation. Initial test setup errors were due to a missing temporary parent and then the raw-output protection gate; using an external temporary directory produced 171 passing tests without algorithm changes. Synthetic results and AI draft real-image hypotheses require student review; no human acceptance or real calibration is implied.


## Step 7 — repository preparation and verification

Codex read the local 2026 Project Brief, audited source/docstring presence and
main-branch inventory, updated repository documentation and the standard-library
HTML generator, and ran tests in the workspace and a fresh installed snapshot.
Google Drive discovery did not locate the Brief; the actual local PDF was used.
The pypdf helper was temporary tooling, not a project dependency. A blocked
sandbox network request was rerun with approval; an initial PDF console encoding
error was resolved by UTF-8 extraction. A clean install initially exposed two
missing-Matplotlib test failures (169 passed); the dev extra was corrected and
the complete isolated suite rerun. API text hashes normalise CRLF/LF so the
Windows-generated documentation remains checkable after a Linux checkout.
No algorithm or result was changed.
AI contribution to this preparation's draft documentation/tooling is substantial;
the student must review it and supply their own overall estimate, decisions and
personal learning reflection. No student approval, assessor access or real accuracy
has been inferred from automated checks. No commit/push/submission was performed.


## Completed-project documentation and reproducibility repair

AI assistance inspected actual code purpose before removing temporary preparation
scripts and PDF helper code. Source/hash backups and the per-file removal manifest
preserve accountability. It updated generic docs/setup, added saved-result replay,
and tested the published clone separately from the locally repaired clone. Numeric
results and conclusions were preserved. The student must review these changes;
no commit, push, dataset upload, human annotation acceptance or online CI success
was inferred. All numerical inference code and original tests remain unchanged.
