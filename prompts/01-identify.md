Read the landing page and advertorial below and extract the basic facts. This is
extraction, not analysis — later stages do the thinking.

The pages may be in any language. Read them in whatever language they are in and
write your output in English.

## PAGES

These may include a landing page, an advertorial, and a checkout page. Pricing
and bundle structure usually live on the checkout page rather than the landing
page — read all of them before filling `price_summary`.

{{pages}}

## OPERATOR NOTES (may be empty)

{{notes}}

## OUTPUT

A single JSON object, nothing else. No preamble, no fences.

```
{
  "product_name": "as it appears on the page",
  "category": "e.g. skincare serum, hair supplement, posture brace",
  "problem_slug": "kebab-case, 2-3 words, the PROBLEM not the product",
  "problem_description": "one sentence describing the problem this solves",
  "price_summary": "every variant and price as stated, e.g. '1 bottle EUR 39.90 / 3 for EUR 89.70 / 5 for EUR 129'. If no pricing appears on any page, write 'not shown'.",
  "offer_summary": "guarantee, shipping, bundles, urgency — whatever the page offers",
  "primary_claims": ["the specific claims the page makes"],
  "language": "the language the page is written in"
}
```

## ON problem_slug — read this carefully

This is a cache key. Every future product solving the same problem reuses the
research filed under it, so consistency across products matters more than
precision on any one.

- Name the **problem**, never the product or its mechanism.
  `hair-thinning` yes. `biotin-serum` no. `follicle-stimulation` no.
- Use the broadest term that is still accurate. `dark-circles` rather than
  `under-eye-hollowing-from-poor-sleep` — the narrow version will never match
  another product and the cache never pays off.
- Prefer the term a sufferer would search for over the clinical one.
  `joint-pain` rather than `osteoarthritis`. `bloating` rather than
  `abdominal-distension`.
- Two to three words, kebab-case, no product words.

Good: `hair-thinning`, `dark-circles`, `joint-pain`, `bloating`,
`adult-acne`, `varicose-veins`, `dry-skin`, `snoring`, `back-pain`.

If the page is vague about what problem it solves, pick the one the copy spends
most of its words on. Do not invent a problem the page never mentions.
