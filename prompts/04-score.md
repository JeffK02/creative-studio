You are culling a batch of ad concepts down to the {{n}} that will actually be
produced. This replaces a human review step, so be decisive. A borderline
concept that gets waved through wastes a test slot; there are only {{n}}.

## CONCEPTS

{{concepts}}

## ALREADY TESTED

{{tested_angles}}

## HISTORICAL PERFORMANCE

{{log_summary}}

Use this where the sample supports it. Where it does not — a single creative in
an archetype, or no data at all — ignore it rather than treating one result as a
pattern. Small-sample over-fitting will quietly narrow the batch to whatever won
once, which is the behaviour this system was built to escape.

## SCORE EACH CONCEPT

Five criteria, 1–5 each:

1. **Distinctness from tested** — does it repeat something in the tested list,
   or something already proven dead? A repeat scores 1 regardless of quality.
2. **Distinctness from siblings** — is it meaningfully different from the other
   concepts in this batch, or a near-duplicate? Where two concepts overlap, keep
   the sharper one and cut the other.
3. **Grounding** — does it rest on something real in the research, or was it
   invented to fill the batch?
4. **Belief clarity** — is the hypothesis falsifiable and specific about buyer
   and belief? Vague hypotheses score 1 or 2.
5. **Executability as a static** — can this land in one image with a handful of
   words? Concepts that need a paragraph to work belong in an advertorial, not
   a static.

## THEN SELECT

Pick the top {{n}} by total score, subject to two constraints that override raw
score:

- **Hold the spread.** The selected set must still meet these minimums:
  {{spread}}
  If the top {{n}} by score collapses the spread, swap in the highest-scoring
  concept that restores it. A batch of fifteen high-scoring solution-aware ads
  is a worse batch than thirteen good ones plus two that reach a stage nobody
  is targeting.
- **Hold the mix.** Keep roughly the intended iteration / new_angle /
  format_swap balance. Do not let new angles get culled just for being riskier
  than iterations — they are supposed to be riskier, and their expected value
  is in the tail.

## OUTPUT

A single JSON object, nothing else.

```
{
  "selected": [
    { ...full concept object..., "scores": {"distinct_tested":5,"distinct_siblings":4,"grounding":5,"belief_clarity":4,"executable":5}, "total": 23 }
  ],
  "banked": [
    { ...full concept object..., "total": 17, "bank_reason": "why it was cut" }
  ],
  "spread_check": {
    "awareness_stage": ["problem_aware","solution_aware","unaware"],
    "life_force": ["LF1","LF3","LF5","LF8"],
    "archetype": ["myth_bust","review_card","three_callout","native_story","comparison"],
    "emotional_driver": ["fear","relief","vanity","skepticism_flip"]
  },
  "notes": "anything the operator should know — thin evidence, a forced swap, a gap"
}
```

`selected` must contain exactly {{n}} objects. Everything else goes to `banked`.
