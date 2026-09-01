# Research profile schema

`config/research_profile.json` is intentionally blank in the public package. Set `configured` to `true` only after the required fields are populated.

## Required fields

- `profile_name`: a short name shown in run metadata.
- `research_context`: concise background that helps interpret relevance.
- `target_system`: the organism, disease, material, technology, population, or other main research object.
- `priority_questions`: the scientific questions that should drive final evidence review.
- `queries`: Boolean-style API queries used by the default `all` mode.
- `topic_groups`: deterministic preliminary-scoring groups. Each item has `label`, `weight` from 1 to 100, and a non-empty `terms` array.

At least one query and one topic group are required. A blank profile stops with a configuration error instead of returning unrelated papers.

## Optional fields

- `modes`: named focused modes. Each key maps to an object containing a `queries` array.
- `cross_topic_bonuses`: items with `labels`, `bonus`, and optional `reason`. A bonus applies only when every listed topic group matches.
- `method_groups`: items with `label` and `terms`; these extend the built-in generic method detector.
- `quality_tiers`: `tier_1`, `tier_2`, and `tier_3` arrays of normalized journal names.
- `exclusion_terms`: terms that trigger preliminary exclusion when found in title or abstract. Keep this list conservative.
- `mechanistic_terms`: domain-specific terms suggesting mechanistic or high-information evidence.
- `strong_recommendation_rules`: items with `labels`, optional `methods`, `min_score`, and `reason`. Every configured condition must match.
- `roadmap_stages`: items with `label` and `keywords`, used only to classify confirmed reports in research memory.
- `tags`: preferred report tags.

Weights and keyword matches are preliminary routing aids, not final evidence. Codex must still read available abstracts or full text and independently re-score every finalist.
