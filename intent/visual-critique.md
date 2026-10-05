# FitLab: Critique the generated looks

Status: Draft — Under review.
Named team approver: Patrick.

## Purpose

Help users judge whether each generated outfit meets their request, and identify mismatches they may want to change.

## User experience

A vision model examines each actual generated image alongside the outfit brief. It provides a concise assessment of the visible clothing's suitability for the occasion, requested aesthetic, styling preference, and available event weather.

Each critique includes scores alongside short explanations. Scores express the model's assessment against the brief, not objective measures of fashion quality.

For a remixed or revised look, the critique also checks whether the visible result follows the selected pieces and requested changes.

When uploaded clothing is selected, the vision model also examines the original reference images and checks that the generated look preserves their visible colors, patterns, shape, and distinguishing details, except for changes explicitly requested by the user. Preservation mismatches use the same two-retry limit.

When the critique identifies a mismatch with the brief, the app automatically regenerates the affected look using the feedback and critiques the new image. This applies to initial options and user-requested revisions. Allow at most two automatic retries per affected look after its initial generation (three generation attempts total). If a mismatch remains after both retries, stop and explain the unresolved issue to the user.

## Success criteria

- The critique receives and examines the generated image itself, not just its generation prompt.
- Each initial outfit and subsequent revision has its own critique.
- Feedback describes visible matches and mismatches with the brief in understandable language.
- Each completed critique displays scores with short explanations, using a consistent scoring rubric across alternatives and revisions.
- When weather is unavailable, weather suitability is marked as not assessed and excluded from scoring; missing weather alone does not trigger regeneration.
- The critique acknowledges uncertainty where an image cannot establish a property such as fabric warmth or waterproofing.
- If critique fails, the app identifies the missing assessment rather than implying the outfit passed.
- A detected mismatch triggers an automatic retry for the affected look, followed by a new image-based critique.
- Each initial or user-requested revised look has a maximum of two automatic retries; successful alternatives are not regenerated because another look failed.
- After the retry limit, unresolved mismatches are disclosed rather than reported as a successful match.

## Open decisions

- Score scale, scoring categories, and the criteria that trigger an automatic retry.
