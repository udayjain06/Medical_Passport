# UI/UX audit and remediation

## Audit findings, worst first

1. **Controls had no immediate pressed response.** Buttons only changed on hover, so touch users received no feedback at pointer-down. The hover lift also moved the control in a direction unrelated to the press.
2. **Document details behaved like a desktop center modal.** It could not be dragged, had no velocity-aware dismissal, did not return keyboard focus, and did not trap keyboard focus inside the dialog.
3. **The account navigation lacked a clear material treatment.** The header had a translucent fill but no blur/saturation layer or high-transparency fallback, and its active link state was only color.
4. **The account bar crowded small screens.** Navigation links were squeezed or wrapped along with profile controls, making common destinations harder to reach.
5. **Motion and contrast preferences were incomplete.** Reduced motion only shortened existing transitions; reduced transparency, increased contrast, and forced-colors layouts had no dedicated variants.
6. **Headlines used overly tight tracking and nearly identical line-height at all sizes.** The hero used `-0.045em` tracking, which made large text visually cramped.
7. **The button hover animation used a fixed easing curve and moved the button upward.** This conflicted with the requested spring and direct-manipulation model. Motion was not isolated to compositor-friendly properties.
8. **The document modal lacked Escape dismissal and focus management.** Background interaction was not reliably contained while the modal was open.
9. **No sound or haptic feedback was present.** The web UI keeps feedback visual and avoids unexpected audio or vibration; browser haptic support and permission are not uniform.

## Top five remediations

1. Added a `scale(.97)` press state that begins on pointer-down and returns over the specified 100 ms. Reduced-motion users receive an opacity response instead.
2. Replaced the document details center modal with a bottom sheet. The drag handle uses pointer capture, a 10 px commit threshold, 1:1 movement, 0.55 edge resistance, release-velocity handoff, and an interruptible spring (damping 1.0 while settling; 0.8 when dismissing). It traps Tab, closes with Escape, restores focus, and uses a cross-fade under reduced motion.
3. Added a single translucent account navigation layer with `blur(20px) saturate(180%)`; reduced-transparency and forced-colors preferences force an opaque surface.
4. Changed mobile account navigation to a horizontally scrollable, non-wrapping destination row, separate from account controls.
5. Added reduced-motion, reduced-transparency, increased-contrast, and forced-colors variants; normalized headline tracking to `-0.02em` and tuned line-height by text role/size.

## Verification

- Frontend lint: passed.
- TypeScript check: passed.
- Optimized Next.js production build: passed; 13 app routes produced.
- Full Playwright end-to-end journey: **1 passed (1.6 minutes)** on an isolated frontend/backend pair and a separate SQLite database. It checks the press state, glass preference fallback, sheet open/drag/close, reduced-motion dismissal, the existing document/review/timeline/emergency/family journeys, and 375 px responsive routes.
- The isolated backend had no AI provider credentials. Local OCR and human review completed. Test data stayed in the temporary UI audit database, not the configured local application database.

## Limitations

- This is a web implementation of the provided interaction guidance, not native iOS behavior. Haptics are not available consistently across browsers.
- The named `apple-design` skill and its attachment were not available in the installed skill directory; this audit follows the detailed design rules included in the user request. The skill does not claim Apple authorship or endorsement.
- The spring implementation is custom and should still be evaluated on a physical touch device with users, particularly for drag feel and assistive-technology interaction.
