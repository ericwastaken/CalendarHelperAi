# Calendar Helper AI: Paper + Pine

Status: approved by Eric on September 24, 2026 and implemented locally on DEV as version 0.11.0. Production remains on the previous release until a separate deployment. The state inventory below records the pre-refresh baseline at `00d1f45`; see [IMPLEMENTATION.md](IMPLEMENTATION.md) for the changes and verification results.

Open `preview.html` directly in a browser. It contains its own styles, sample data, and interaction code with no network dependencies. The state selector is a review tool, not proposed application UI. Selecting “Download sample file again” produces a clearly named sample `.ics`; no calendar is opened or changed.

## Direction

Make an everyday utility feel like a small, considered piece of software: a warm paper surface, dark pine controls, confident typography, and a quiet three-step flow. The app helps people get to a trustworthy calendar file. It should not look like a generic chat client or an AI dashboard.

The visual identity uses a system sans serif for controls and readable details, with Georgia for short introductory headlines. A small calendar mark provides recognition without taking space away from the task. Photography, gradients, decorative illustrations, and floating toolbars are unnecessary.

The primary journey is **Add details, Review, Export**. Reviewing comes before editing and exporting, because the extracted events are the main result. The original request remains available in a collapsible section.

## Layout contract

| Property | Requirement |
|---|---|
| App width | `width: min(100%, 460px)` at every breakpoint |
| Desktop | Center one 460px column with a paper surface, 24px corner radius, light border, and shallow shadow |
| Mobile | Use available width up to 460px; remove the outer shell border, corner radius, and shadow below 600px |
| Content inset | 24px on desktop; 20px on phones; 16px below 360px |
| Minimum supported viewport | 320 CSS px, without horizontal page scrolling |
| Vertical layout | Natural page height and normal document scrolling |
| Footer | Normal document flow, inside the same column, after actions; never cover content |
| Event cards | Always a single column, including on wide desktop screens |
| Image previews | Two columns; wrap to new rows rather than squeezing five thumbnails together |
| Dialog | `min(100% - 24px, 436px)` wide; at most `100dvh - 32px` high, independently scrollable |
| Safe areas | In production, account for bottom safe-area inset in the final footer padding |

Do not widen review results, correction fields, action bars, or legal content to the old 1200px layout. Do not add a fake device frame. The narrow experience is the product, not a desktop mockup of a phone.

## Foundation tokens

`tokens.css` records this design version's foundation tokens. The active application token block is in `static/css/style.css`; keep these values aligned when changing this system. The self-contained preview duplicates the colors and key geometry so it also works when copied alone.

| Role | Value | Use |
|---|---|---|
| Canvas | `#EEEAE2` | Desktop background |
| Paper surface | `#FFFEFA` | App, controls, dialogs |
| Quiet surface | `#F5F3EC` | Upload target, request summary, user messages |
| Ink | `#20352E` | Titles and body text |
| Muted text | `#59665E` | Secondary copy with readable contrast |
| Primary pine | `#245944` | Primary actions, active progress, links |
| Primary hover | `#174631` | Pointer hover for primary controls |
| Primary tint | `#E7F0E8` | Success feedback and assistant replies |
| Structural border | `#DCDED4` | Cards and dividers, not sole control identification |
| Control border | `#7A867D` | Text inputs and secondary buttons |
| Review foreground / tint | `#6D4C16` / `#FAF0D9` | Verify-the-result notice |
| Error foreground / tint | `#9B302E` / `#FBECEA` | Validation and recoverable failures |
| Focus | `#176FBC` | 3px visible keyboard outline with 3px offset |

Use 4, 8, 12, 16, 20, 24, 32, and 40px spacing. Inputs and buttons use 12px radii, cards 16 to 18px, and the desktop shell 24px. Avoid combining many nested shadows.

| Text role | Size / line height | Style |
|---|---|---|
| Initial headline | 40px / 1.08; 35px under 360px | Georgia, regular, modest negative tracking |
| Subsequent headline | 32px / 1.08 | Georgia, regular |
| Section title | 21px / 1.25 | System, bold |
| Event title | 18px / 1.4 | System, semibold |
| Form input | 16px / 1.5 | System, regular, avoids mobile focus zoom |
| Body | 15 to 16px / 1.5 to 1.65 | System, regular |
| Supporting copy | 12 to 13px / 1.5 | System, regular |
| Eyebrow | 11px / 1.5 | Uppercase, bold, restrained tracking |

Small text is reserved for supplementary copy. Dates, times, event names, errors, and primary instructions must remain plainly readable.

## State inventory and proposed behavior

The “Current behavior” column below combines source inspection of `templates/index.html`, `static/js/app.js`, and `routes.py` with parent-task API tests on September 24, 2026. It is not a claim that every branch has been reproduced in the live browser. The preview is deliberately deterministic and uses invented event content.

| State | Current behavior | Design proposal |
|---|---|---|
| Start | Images and optional text; UI offers text-only input, but a live text-only request returned 500 | Clear upload target, persistent format/size guidance, labeled details field, “Find my events” action; text-only is intended UX and requires a backend repair before release |
| Selected images | Up to 5; count, preview, and removal | Two-column thumbnails, count badge, visible Remove controls with filename in accessible label |
| Image limit | Rejects additions exceeding 5 | Explain limit beside uploads; retain valid selections; at limit, keep upload control discoverable with an explanation |
| File validation | Types from config; backend validates each file and total | Validate each file before submission, name offending file, retain other inputs |
| Processing | Process button and existing previews disabled; spinner label and long-request hint | Lock all input mutation while processing, retain context, indeterminate status and elapsed-neutral copy; no fabricated percentage |
| Review | Original request, chat, warning, event cards | Original request collapsed, warning, event cards, then correction form and export |
| Correction pending | Input/send disabled; user message appended | Preserve current event cards, show pending message, disable export until the correction resolves |
| Correction success | Replaces all events; generic success message | Summarize actual differences when available and mark changed fields briefly; never claim a change without comparing responses |
| Correction failure | Error appended; typed correction already cleared | Retain the correction draft for retry and keep prior events unchanged |
| Export pending | Posts events; `showLoading` looks for absent spinner | Dedicated “Preparing calendar...” button state, prevent duplicate submissions |
| Export response | Blob download; no explicit success panel | Say “Your download has started” only after successful response and download initiation, with import instructions and return action |
| Export failure | Error in chat | Inline notice beside download action, with retry and all events retained |
| Network failure | Bootstrap error dialog | Inline recoverable notice near the action; keep input and re-enable controls |
| No events | A `no_events` branch exists, but a live image without events returned generic 500 `processing_error` | “No events found this time”, clearer-image and missing-date guidance, retain input; requires a typed empty-result backend repair before release |
| Prompt rejection | Backend `unsafe_prompt` message | Use the same input error pattern; show safe `user_message` via textContent |
| Reset | Immediate clear | Confirm once when useful input/results exist; offer “Keep working” and “Clear and start over” |
| Session timeout | Silent reset one hour after initial processing success | Before expiration, explain the actual session lifetime and offer export; after expiration, announce session ended rather than silently losing context |
| Example | HTML loaded into custom modal | Native accessible dialog explaining all three steps |
| Terms | Existing HTML loaded into custom modal | Readable dialog with full existing terms, headings, links, and visible close control; preserve legal copy during visual changes |
| Image inspection | Lightbox and object URL thumbnails | Accessible image dialog, natural aspect ratio, meaningful alt text, image navigation and zoom where implemented |

The preview includes 16 selectable states plus example, terms, image, and reset dialogs. The terms and image dialogs demonstrate the shell only, with explicit prototype notes. Full legal text, genuine source images, image zoom/navigation, elapsed timers, and the actual AI service are production implementation concerns, not simulated features to mistake for working integration.

The preview has explicit “Preview” advance controls for pending operations. It does not make fake network requests or pretend to discover data. Phase selection resets sample count where needed; its fake “Choose images” control adds examples rather than opening a file picker.

## Component behavior

**Progress**: three labels with a visible active border and `aria-current="step"`. Use completed and active styling in addition to numbers. Do not let progress navigation accidentally discard state. The preview progress is informational.

**Uploads**: keep a native file input with an accessible label in production; the large styled trigger activates it. Get allowed types and limits from `/api/config`. Current values are JPG/JPEG, PNG, and TIFF with a 4 MB per-image limit and 5-image maximum. Maximum combined payload is therefore 20 MB. Distinguish preview and removal targets. Removing one image must not submit the form. Revoke object URLs when removing or resetting files. Reset file input value so the same file may be reselected.

**Event card**: show day, full date including year, title, time range, location link, and optional description in that order. Always make the relevant timezone visible in the result group, and handle cross-day/mixed-timezone results explicitly rather than compressing away information. Long names and addresses wrap. Omit absent locations and suppress non-location placeholders such as `unknown - ` rather than creating nonsense map links. Do not infer all-day status, recurrence, or confidence from absent backend data. Render returned text safely without using it as HTML.

**Corrections**: keep a readable conversation below the result cards. Use explicit speaker names. Preserve the last successful events on every failure. For long histories, collapse older turns or provide an accessible scroll region; never trap keyboard scrolling. A pending correction blocks export to prevent stale data downloads.

**Export**: full-width primary action with subordinate `.ics` explanation. The file is compatible with calendar import, but the application does not confirm a user's calendar import. “Your download has started” is the strongest supportable confirmation; “Events added” would be inaccurate. Keep return-to-events and download-again available.

**Dialogs**: use native `<dialog>` where supported, with a labeled title, close control, Escape dismissal, modal focus containment, and focus return to the opener. Destructive reset defaults to keeping the work. An image dialog can use a larger height, but never a wider application layout. Include explicit loading/failure feedback if terms or example content cannot load.

**Footer**: normal document flow with “Hosted on DigitalOcean” and “Terms of Service” on the same row, including at 320px. Eric explicitly required this alignment when approving the design. The DigitalOcean link is https://m.do.co/c/a45d31d9506d, verified in the account and confirmed by Eric. Acceptance copy and “Referral link: we may receive account credit.” appear below the row. Do not hard-code changing incentive amounts into the app.

DigitalOcean has a referral program. Its official page states the referrer receives $25 account credit after a referred customer spends their first $25. The verified referral link is used in the app footer. Program details belong on the linked program page, not hard-coded in a permanent app footer. Source checked by parent task on September 24, 2026: [DigitalOcean referral program](https://www.digitalocean.com/referral-program).

## Accessibility and resilience

1. Keep every interaction reachable by keyboard. Buttons, thumbnail controls, and links need at least 44px touch targets; primary buttons are at least 48px high.
2. Give each input a persistent label. Place errors close to the field and connect production errors with `aria-describedby` and `aria-invalid`.
3. Announce meaningful results with polite live regions and errors with `role="alert"`. Use `aria-busy` for the actual operation container. Avoid announcing every animation frame.
4. On page-phase changes, move focus to the new heading. After corrections, announce success and leave the user's position stable. After removing a file, place focus on the next valid removal/preview control or upload trigger.
5. Preserve strong foreground contrast and visible control outlines. Meaning cannot depend on color alone. Support forced colors.
6. Respect `prefers-reduced-motion`. Use at most a 160ms color/opacity transition. Do not bounce, shimmer, parallax, or animate the full page. Progress text remains useful when the spinner is static.
7. Support 200% zoom and narrow reflow, long event names, multiline addresses, large user text, iOS virtual keyboard, and landscape screens.
8. Treat config/terms/example failures as recoverable. Do not blank out the application while fetching supporting content.
9. Retain genuine user data during failures, disable duplicate submissions, and restore every disabled control in a `finally` path.
10. Never store uploaded images, conversation text, or API secrets in design files, analytics, or console logs as part of this refresh.

## Integration guardrails

Keep the existing endpoint contract: `/api/config`, `/process`, `/correct`, `/download-ics`, and browser timezone via `X-Timezone`. Preserve the existing form/element identifiers when practical to reduce migration risk, or change JS and templates together deliberately.

The redesign should remove dependence on Bootstrap, icon fonts, and Lightbox only as a coordinated implementation step, after all their behavior has replacements. The prototype has no such dependencies; it is not a drop-in template. Remove stale fixed-footer padding and broad desktop breakpoints rather than layering overrides indefinitely.

Separate visual implementation from backend behavior changes. Gaps identified in the source that matter for implementation:

- Selection-time file checks enforce combined size; submit-time client size validation examines only the first image. The server validates every image. Implement consistent per-file client checks.
- Failed processing disables existing removal controls but does not clearly restore them. Restore all controls on recoverable errors.
- A `loadingSpinner` is referenced but absent from the template. Replace this with real pending button states.
- Upload input and details textarea remain mutable during processing, even though previews are disabled. Freeze the whole request or explicitly snapshot it.
- Image thumbnail code reparents the image out of its anchor and uses nested click forwarding. Replace with straightforward semantic controls.
- Existing event HTML inserts AI-derived strings directly. Use safe text rendering for the refreshed cards.
- The current automatic one-hour reset is independent of correction activity. Do not imply an idle-based timeout unless behavior is changed.
- Existing legal privacy/retention assertions are outside visual design scope. Preserve and separately review them against actual behavior rather than inventing new promises.
- Parent API testing reproduced a 500 for text-only input; source inspection found parsed text-only events never appended to the final result. Repair before advertising working text-only support.
- Parent API testing reproduced a generic 500 for an image with no events. Distinguish an empty valid result from an internal processing failure before shipping the proposed empty state.

## Acceptance checks for implementation

| Check | Expected result |
|---|---|
| 1440px desktop | App remains exactly 460px maximum, including review and dialogs |
| 768px tablet | Same narrow column; comfortable surrounding space |
| 390px and 320px phones | No horizontal page scroll, clipped controls, footer obstruction, or 5-column thumbnail squeeze |
| 200% zoom | Single-column reflow with all controls reachable |
| Images | Add/remove/reselect, 5 maximum, invalid type, oversized first and later images, each image inspectable |
| Text-only | Can submit without an image; empty request shows actionable validation |
| AI flow | Pending, success, no events, prompt rejection, malformed response, and connection failure all recover |
| Corrections | Retained draft on error, prior events stable, export blocked while pending, result changes visible |
| ICS | Correct title, full date, time, timezone, location, and description; pending/retry states; accurate success wording |
| Dialogs | Tab containment, Escape, visible Close, opener focus restored, small-height scrolling |
| Reset and expiry | Explicit data-loss handling, fresh clean state, no stale errors or disabled controls |
| Reduced motion | Pending status still understandable without animation |
| Keyboard | Full flow operable without a pointer; visible focus at every step |

## Files and verification

- `preview.html`: standalone interactive design study with inline CSS/JS and invented sample events.
- `tokens.css`: reusable CSS custom properties for implementation.
- `DESIGN_SYSTEM.md`: rationale, state mapping, constraints, component behavior, and implementation acceptance checks.

Parent live API tests confirmed image extraction (2 synthetic events), a targeted correction preserving the other event, and two correctly timed ICS VEVENTs using America/New_York. Six-image and invalid-MIME requests returned specific 400 validation errors; empty ICS export returned 400 `no_events`. Text-only and no-event image failures remain as described above.

Static checks passed: inline JavaScript syntax, all 16 render functions in a lightweight DOM stub, correction state preserved through export/return, export blocked during pending correction, no external runtime assets, and no em dashes. Calculated contrast: body 12.92:1, muted text 5.97:1, primary button 8.12:1, review notice 6.87:1, error notice 6.40:1, and control border 3.76:1 against the relevant surface.

These static checks do not validate actual layout or browser interaction. Safari desktop and responsive-mode verification is recorded in IMPLEMENTATION.md. The prototype is a design reference; local implementation and production deployment remain separate.
