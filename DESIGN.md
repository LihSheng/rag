# Design System — RAG

## Product Context
- **What this is:** A RAG web app that turns corpus retrieval into a simple single-query chat workflow with evidence-on-demand.
- **Who it's for:** A solo technical operator managing query quality, retrieval trust, and iteration speed.
- **Space/industry:** AI search, RAG tooling, internal knowledge retrieval.
- **Project type:** Web app with query workspace now and admin dashboard follow-up.

## Aesthetic Direction
- **Direction:** Industrial Editorial
- **Decoration level:** intentional
- **Mood:** Quiet, precise, and credible. Reading-first interface where answers feel authoritative and evidence is one click away.
- **Reference sites:** Perplexity, Glean, You.com, Notion AI interaction patterns (research-informed synthesis).

## Typography
- **Display/Hero:** Satoshi — clean, technical, high-contrast hierarchy for product framing.
- **Body:** Instrument Sans — highly readable at UI paragraph sizes and response text blocks.
- **UI/Labels:** Satoshi medium for headings and controls, Instrument Sans for helper text.
- **Data/Tables:** IBM Plex Mono — precise numeric readability with tabular intent.
- **Code:** IBM Plex Mono.
- **Loading:** Google Fonts CDN links for Satoshi + Instrument Sans + IBM Plex Mono in the frontend entry HTML.
- **Scale:**
  - display-xl: 48px / 1.05
  - display-lg: 40px / 1.1
  - h1: 32px / 1.15
  - h2: 24px / 1.2
  - h3: 20px / 1.25
  - body-lg: 18px / 1.5
  - body: 16px / 1.5
  - body-sm: 14px / 1.45
  - label: 13px / 1.3
  - mono-sm: 12px / 1.35

## Color
- **Approach:** Restrained
- **Primary:** #2D66F6 — key actions, selected states, high-attention controls.
- **Secondary:** #8B95A7 — secondary text and low-priority metadata.
- **Neutrals:**
  - lightest: #F6F7F9
  - surface: #FFFFFF
  - border: #DFE3EA
  - text-strong: #0E1116
  - text-muted: #8B95A7
  - dark-surface: #161B23
  - dark-bg: #0E1116
- **Semantic:**
  - success: #18A572
  - warning: #D98E04
  - error: #C23B3B
  - info: #2D66F6
- **Dark mode:** Keep structure identical to light mode, invert surfaces, reduce saturation 10-15% for non-primary accents, preserve contrast priority for response content.

## Spacing
- **Base unit:** 8px
- **Density:** Comfortable-compact
- **Scale:** 2xs(2) xs(4) sm(8) md(16) lg(24) xl(32) 2xl(48) 3xl(64)

## Layout
- **Approach:** Hybrid
- **Grid:**
  - mobile (<=768): 4 columns
  - tablet (769-1024): 8 columns
  - desktop (>=1025): 12 columns
- **Max content width:** 1160px for primary app shell.
- **Border radius:** sm:6px, md:10px, lg:14px, full:9999px.

## Motion
- **Approach:** minimal-functional
- **Easing:** enter(ease-out), exit(ease-in), move(ease-in-out)
- **Duration:** micro(50-100ms), short(120-220ms), medium(240-360ms), long(380-600ms)

## Interaction Principles (Phase 1 Query UX)
- One dominant action path: type question -> send -> read -> verify evidence.
- Evidence is visible on demand, collapsed by default, preference remembered locally.
- Trust state always shown: grounded vs insufficient context.
- Preserve user input on errors and offer clear retry.

## Anti-Patterns to Avoid
- No purple-heavy gradient branding as default.
- No generic 3-column feature-card blocks in query workflow.
- No icon-in-circle decorative grids.
- No overloaded top navigation on operator screens.

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-27 | Initial design system created | Based on office-hours + plan-design-review outcomes and design consultation preview approval. |
| 2026-03-27 | Query-first scope locked | Single-query workflow is the highest-leverage UX simplification before admin redesign. |
