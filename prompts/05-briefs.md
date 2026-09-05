Write the production brief for each selected concept. Each brief is everything a
designer and an image model need to build the ad, and nothing else.

## SELECTED CONCEPTS

{{selected}}

## PRODUCT BRIEF

{{product_brief}}

## TEMPLATES AND THEIR FIELDS

Every field below has a HARD character limit. Canva Bulk Create does not shrink
text to fit — an overrun means broken layout on that asset, fixed by hand.

Count the characters of every field you write, including spaces, and put the
count in `char_counts`. If a line runs over, cut it down. Do not deliver a line
that exceeds the limit and note it as slightly long; rewrite it shorter.

Write tight. A headline at 30 characters usually beats the same idea at 42 —
the limit is a ceiling, not a target.

{{templates}}

## FRAMEWORKS

{{frameworks}}

## TRANSLATING FRAMEWORKS INTO STATIC ADS

{{static_translation}}

## VOICE

Use the buyer's own vocabulary from the product brief. Keep out the words the
brief lists as ones this buyer would never use. Copy that sounds like a
marketer is copy that gets scrolled past.

## THE IMAGE PROMPT

Each brief includes `image_prompt` — the instruction for generating the base
visual. The product's reference image is supplied separately to the image model,
so:

- Do **not** describe the packaging, label, or product design. It is provided.
  Describing it fights the reference and produces a warped product.
- **Do** describe: scene, subject, framing, lighting, mood, colour, camera
  distance, and how the product sits in the frame.
- Leave clear space where the template's text sits. A brilliant image with the
  headline landing over a face is a wasted asset. Say where the space is.
- Match the design level to the archetype. `native_story` wants an image that
  looks like a phone snapshot — slightly imperfect lighting, real room, no
  studio polish. `authority_stack` wants clean studio work. Getting this wrong
  is the most common reason a static reads as an ad and gets scrolled.
- **Check the archetype's `render_mode`.** For `template` archetypes, generate
  no text at all — the template applies it, and generated text underneath a
  template layer is a ruined asset. For `full_generate` archetypes the image
  model renders the text itself, so leave it a clean, high-contrast area to sit
  in and keep the wording short; long lines are where generated text breaks.

## OUTPUT

A JSON array, one object per concept, nothing else. Include the template's
fields as top-level keys, using the exact field names from the template spec.

```
[
  {
    "concept_id": "c_07",
    "template": "myth_bust",
    "myth": "…",
    "truth": "…",
    "cta": "…",
    "char_counts": {"myth": 41, "truth": 55, "cta": 18},
    "image_prompt": "…",
    "angle": "…",
    "desire": "…",
    "life_force": "LF3",
    "awareness_stage": "problem_aware",
    "emotional_driver": "skepticism_flip",
    "archetype": "myth_bust",
    "source": "new_angle",
    "parent_creative_id": null,
    "hypothesis": "…"
  }
]
```

Carry `angle`, `desire`, `life_force`, `awareness_stage`, `emotional_driver`,
`source`, `parent_creative_id`, and `hypothesis` through unchanged from the
concept. They are what the results log is built on.
