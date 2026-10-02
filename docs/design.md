# Interface design

The interface should feel like a financial research publication: readable tables, explicit units, and a clear path from summaries to source evidence. The visual hierarchy should come from typography, spacing, and distinct grouped surfaces.

## Direction

- Use horizontal text navigation for the four main views. Avoid decorative navigation icons.
- Use an off-white background, charcoal text, and a restrained Akash-inspired red accent for links, selection, and primary chart series. Keep most surfaces white or warm neutral, with a pale red tint on selected blocks. Red identifies interaction and series, not negative price performance.
- Use self-hosted IBM Plex Sans for headings, controls, and readable body text, with tabular figures. Use IBM Plex Mono for identifiers and exact amounts. Font files retain their upstream SIL Open Font License and pinned source attribution in `apps/web/public/fonts/`.
- Group metrics on a shared surface. Use subtle warm background tones, spacing, and varied corner radii to distinguish blocks. Avoid repeated divider lines and uniform elevated tiles; retain faint table rules only where they aid comparison.
- Keep tables dense enough for comparison, with clear headers and horizontal scrolling on small screens. Keep the surrounding document within the viewport.
- Show missing evidence as concise text. Never fill empty charts with invented observations to improve the composition.

## Research constraints

Synthetic mode must remain explicitly labeled. Native amounts retain their precision and units; an unavailable conversion stays unavailable. API response time must not imply recent source collection. A selected historical sample must not imply complete market coverage.

Keyboard focus, contrast, loading/error states, and mobile navigation are part of the design. Avoid gratuitous motion and decorative graphics that compete with data.

## References

Reviewed [Ornn’s market page](https://data.ornn.com/markets) for restrained typography and neutral surfaces, adapted to a light interface with an Akash-inspired red accent.

Reviewed the [Blockworks research interface](https://app.blockworks.com/) and [Artemis](https://classic.artemis.ai/) for compact sans-serif typography and navigation. DeFiLlama’s public page structure was reviewed, but browser verification blocked visual inspection. These are references for information density, not templates to copy.

## Review

The visual audit used the [Taste redesign skill](https://github.com/Leonxlnx/taste-skill/blob/main/skills/redesign-skill/SKILL.md). Apply its guidance selectively to research software: typography, restrained surfaces, and usable states matter here; stock imagery, cinematic motion, and fabricated example data do not.

Review the market, order list, order detail, providers, and research views in a browser at desktop and phone widths. Verify table scrolling, filter submission, exports, navigation, exact bid amounts, and honest empty states alongside production build and adapter checks.
