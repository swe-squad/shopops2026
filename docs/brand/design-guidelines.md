# ShopOps design guidelines

Use [brand direction](brand-direction.md) for the creative rationale, [tokens](assets/tokens/brand-tokens.json) for exact values, and the [asset index](README.md) for exports. This kit records the selected design for designers and developers; review the mark for trademark clearance before public release.

## Logo

Use the primary lockup on light, quiet backgrounds and the reversed lockup on dark backgrounds. Use the mark alone for compact surfaces such as an app icon or avatar, where the ShopOps name is otherwise clear. Leave at least one quarter of the mark's width as clear space around a lockup. Keep the proportions fixed; avoid outlines, gradients, effects, rotation, and placing the mark over busy imagery. Use the dedicated monochrome or reversed asset when the primary version lacks contrast.

The lockup's text is editable SVG text, not outlined artwork. Its rendering depends on installed fonts. Use the SVG source for adaptation and create outlined masters after confirming the licensed font for distribution. Do not interpret the generative concept's lettering or UI as exact product assets.

## Color and contrast

Use warm off-white for the overall canvas, white for content surfaces, ink for text, and bright orange for brand marks and selected accents. Cobalt is the secondary accent; use text and icon cues alongside color for success, warning, and error states.

Bright orange `#F4511E` on white has approximately **3.48:1** contrast: do not use that pairing for normal-size text or white text in normal-size buttons. Use action orange `#B5310B` with white for primary buttons or links on white (approximately **6.16:1**). Ink on the warm canvas is approximately **15.94:1**. Check each real foreground/background combination, disabled and hover states included; these examples do not certify an entire interface. Use a distinct visible focus indicator, including for keyboard navigation.

The JSON token file is the reference for values; the CSS file mirrors it for web consumption. If values change, update both and verify their equivalence. The delivered files are standalone assets and are not imported by an app automatically.

## Type and layout

Use Inter when available, with a system sans-serif fallback supporting Vietnamese; use the mono stack for code and identifiers. Body copy should be readable at typical device sizes, and hierarchy should rely on weight and spacing before extra decoration. Use the supplied spacing and radius tokens consistently. Avoid neon AI effects, stock robot imagery, heavy shadows, and decorative gradients.

## Product surfaces

- **Browser app:** Let the seller scan incidents, evidence, recommendations, and actions. Place destructive or consequential actions behind clear labels and appropriate confirmation in the product flow.
- **Mobile chat app:** Keep the Telegram-style conversation readable, with comfortable touch targets, visible focus, a persistent composer, legible links, and an obvious way to recover from interrupted messages. Respect mobile safe areas and on-screen keyboards. It is a separate client from the browser app.
- **Landing page:** Lead with the seller's problem and a clear explanation of the product. The hero illustration is an editable conceptual image, not an implemented screenshot.
- **Responsive and motion:** Avoid page-level overflow, allow wide tables to scroll inside their container, and respect reduced-motion preferences. Verify actual screens at phone, tablet, and desktop widths.

## Asset use

Use the SVGs for scalable web graphics; use the appropriately sized PNG or ICO for browser and mobile-web metadata. The rounded PNG app icons are web assets, not certified native-store icons: check each target platform's requirements and safe area before native release. Use 1200×630 for the provided open-graph artwork; square and story images are supplied separately. External websites, app stores, and social platforms may crop artwork differently, so review final placements.
