# Styling Hybrid Guide

## Source of truth
- Design tokens live in `tokens.css`.
- Legacy page styles in `../styles.css` should consume token aliases, not raw hex values.

## Primitives
- `Card` (`../components/ui/Card.tsx`): Base surface container for dashboard sections and metrics.
- `Badge` (`../components/ui/Badge.tsx`): Status labels with semantic tones.
- `Stepper` (`../components/ui/Stepper.tsx`): Document pipeline progress (upload, chunk, vectorize, sync).

## Usage rules
- Prefer primitives for new admin UI before writing one-off classes.
- Use token variables (`--color-*`, `--space-*`, `--radius-*`, `--font-*`) in custom CSS.
- Keep responsive behavior mobile-first, then expand at tablet and desktop breakpoints.
