# Step 6.1: fork-anchored matching study

The new detector uses a visible three-arm fork to assign provisional branch roles,
then matches a fork-connected terminal to a detached simple fragment in the same
upright Y sector. It requires a unique compatible match and checks direction and
local curvature over 12 support points. The existing linear/quadratic fitters and
the Step 6 v2 angular ambiguity policy are unchanged.

## Protocol and evidence separation

The frozen plan contains 24 development cases and 96 evaluation cases, using new
seeds and configurations from the SAME Step 6 simulator. These are not independent
real trees or an independent generator. Matching policy and source hashes were
frozen before evaluation. Development completed with settings_changed=false.
Old holdout_39 is a historical failure diagnosis, never a new test case.

All five methods use the same observed mask, depth and occlusion inputs. Inference
does not consume whole-reference arrays; the evaluator uses those only for metrics.
The anchored variants change matching AND the completion support window (12 versus
8), so this comparison cannot isolate the effect of matching alone.

## Frozen evaluation results

All-case means include refusals. Recall uses a 2-pixel tolerance. Connection errors
compare endpoint roles from the simulator; these are not real anatomical identities.

| Method | Accepted / 96 | Correct connections | Wrong connections | Wrong role labels | Added hidden recall | Full 2D Chamfer (px) | 3D Chamfer (m) | Coverage within 3 cm | Median runtime (ms) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| visible_only | 0 / 96 | 0 | 0 | 0 | 0.00000 | 1.81460 | 0.04846 | 0.76639 | 9.001 |
| linear | 3 / 96 | 3 | 0 | 0 | 0.03125 | 1.80709 | 0.04829 | 0.76848 | 11.542 |
| quadratic | 4 / 96 | 3 | 1 | 1 | 0.03260 | 1.80388 | 0.04821 | 0.76888 | 11.360 |
| anchored_linear | 3 / 96 | 3 | 0 | 0 | 0.03125 | 1.80604 | 0.04827 | 0.76931 | 10.827 |
| anchored_quadratic | 3 / 96 | 3 | 0 | 0 | 0.03125 | 1.80652 | 0.04828 | 0.76931 | 10.677 |

Runtime includes thinning, matching, completion and 3D lifting, excluding I/O and metrics; median of three runs after warmup, with cyclic method order. Detector timings are saved separately.

linear → anchored_linear: 2 gained cases, 2 lost cases, 1 cases accepted by both. See paired_comparison.json for paired metric changes and case identifiers.

quadratic → anchored_quadratic: 2 gained cases, 3 lost cases, 1 cases accepted by both. See paired_comparison.json for paired metric changes and case identifiers.

Compared with linear, anchored_linear changes accepted cases by +0, wrong connections by +0, and all-case added hidden recall by +0.00000. These observed tradeoffs do not support an unconditional superiority claim.

Compared with quadratic, anchored_quadratic changes accepted cases by -1, wrong connections by -1, and all-case added hidden recall by -0.00135. These observed tradeoffs do not support an unconditional superiority claim.

## Interpretation and limits

Higher completion acceptance alone does not establish improvement: compare hidden
recall and geometric errors alongside incorrect connections and refusals. A missing
or ambiguous visible fork deliberately prevents anchored completion. The detector
assumes one upright isolated Y and can reject valid branches outside that scope.
The study does not establish performance on other topologies or real observations.

Historical rejection counts are first-failure pair reasons. A case can contain
multiple rejection categories, so totals are not disjoint causal case counts.
The holdout_39 investigation demonstrates why matching image-axis labels and a
cycle-free bridge do not establish common anatomical identity.

## Real-image review

12 saved real-image draft masks were reviewed by the pipeline. Cases with accepted hypotheses: linear=3, quadratic=3, anchored_linear=0, anchored_quadratic=0. The anchored detector refuses all 12 real drafts: 11 lack a visible fork and R06N02 has ambiguous fork roles. This is a practical coverage limitation, not evidence of successful real completion or verified safety. They remain AI DRAFT and require independent human review. Mask complement
is used ONLY as an unverified display carrier, not confirmed occlusion evidence.
No real accuracy, verified connection, camera calibration or metric 3D claim is made.
See real/contact_sheet.png and real/qualitative_review.json for every hypothesis
and rejection, including the difficult R06/R08/R09/R10 samples.

## Verification and artifacts

- Full existing/new unit suite: 171 passed.
- Saved-observation replay: 480 graphs; topology, identity and status checked exactly, coordinates within archived tolerances. No simulator or reference arrays used by replay.
- Preservation: 8864 pre-existing files retain SHA-256, size and modification time.
- frozen_plan.json and development_complete.json record the fixed policy and phase boundary.
- comparison_summary.csv, evaluation/metrics.csv and rejection_reasons.csv contain numeric evidence.
- index.html contains synthetic comparisons and the real draft gallery.
- Historical data and results are preserved. No commit or push performed.

To reproduce in a fresh checkout with no Step 6.1 output directory, set PYTHONPATH
to src and run `python scripts/evaluate_step61.py develop`, then
`python scripts/evaluate_step61.py evaluate`. Existing output directories are
deliberately protected; do not rerun into this evidence directory.
