# Implementation and verification

September 24, 2026. Version 0.11.0, implemented locally on `DEV`. This document does not establish a production release. The design was approved before implementation.

## Source map

| Component | Application source | Contract |
|---|---|---|
| Shell, progress, footer, dialog | `templates/index.html` | One 460px column; Hosted on DigitalOcean and Terms of Service share one row |
| Tokens and responsive styles | `static/css/style.css` | Paper + Pine palette, system fonts, 320px reflow, focus states and reduced motion |
| Workflow and client state | `static/js/app.js` | Add details, processing, review, correction and export; recoverable failures retain work |
| Sample walkthrough | `static/example-images-and-prompts.html` | Real sample upload asset, two fictional events, correction and export instructions |
| Sample photography | `static/images/example-event-cards-2026-09.png` | AI-generated image, disclosed in the walkthrough; [prompt and provenance](SAMPLE_IMAGE.md) |
| Favicon | `static/icons/`, template links and `/favicon.ico` | Approved Checked date mark, SVG/PNG/ICO and Apple touch icon |
| Full legal text | `static/terms.html` | Existing copy loaded into the native dialog |
| Input and endpoint validation | `routes.py`, `app.py` | Five images, 4 MiB each, 21 MiB request envelope; typed empty-result errors |
| Extraction and corrections | `utils/ai_processor.py` | One extraction per request; text-only results returned; timezone included in corrections |
| Calendar serialization | `utils/calendar.py` | Preserve aware instants and repeated DST hours; reject invalid ranges |

The application uses local CSS and native browser controls. Bootstrap, jQuery and Lightbox are no longer required. `preview.html` remains a standalone design reference with synthetic states, not a second application implementation. `tokens.css` is the dated token reference; keep the application's token block aligned with it.

## State behavior

Selections retain valid files when another file is rejected. Removing or resetting files revokes their object URLs. Uploading locks input until the request completes. Empty results, connection failures and other processing errors return to the input view with the request preserved.

Review places event cards before corrections. Dates include their year; times use the browser timezone, which is also shown above the cards. Text from users and AI responses is escaped before rendering. Unknown locations do not become map links. Corrections preserve the prior events and draft when they fail. Pending corrections disable export, and successful changes mark affected cards as updated. The conversation is bounded and scrollable.

Export starts a file download and explains the separate calendar import step. It never claims that events have already been added to a calendar. Export failure retains the events and offers retry. Reset requires confirmation when there is work to lose. Native dialogs support Escape and return focus to their opener.

The in-memory session expires after one hour without an extension. Successful extraction, correction activity and export activity extend it. A five-minute warning offers Keep working; pending operations defer expiration. Refreshing or closing the page clears this client state.

## Verification performed

| Check | Result |
|---|---|
| Safari desktop | Narrow centered shell, readable event cards, footer links on one line |
| Safari responsive modes | 390px review and 320px upload/example layouts inspected; footer remained on one row |
| Text-only processing | Real AI request returned two synthetic events with expected dates and times |
| Image processing | Synthetic upload and new sample photo both returned two expected events |
| New sample details | Community dinner: October 8, 2026, 6 to 8 PM; Garden morning: October 10, 2026, 9 to 11 AM, America/New_York |
| Correction | Real AI correction changed the requested title/time while retaining the second event |
| Download | Safari downloaded a two-event ICS; parsed timestamps matched corrected events and America/New_York |
| Recovery | Stopping the local server reproduced correction and export connection errors; drafts/events survived and retry succeeded after restart |
| No events | Real image with no appointments returned typed `no_events`; UI retained the image and offered useful guidance |
| Dialogs and reset | Image preview, example, full terms, Escape/focus return and cancel/confirm reset exercised |
| Backend regression suite | 13 tests pass: extraction count, text-only result, empty/malformed results, request/file limits, correction validation, aware timezone and DST serialization |
| Static checks | JavaScript syntax and Git whitespace checks pass |

The test suite makes no external API requests. Run it with `.venv/bin/python -m unittest discover -s tests -v`. Live extraction checks do use the configured AI service.

## Remaining validation limits

Safari responsive mode is not physical iPhone testing. The one-hour expiry was implemented and reviewed but was not observed for a full hour. Slow-request timeout, every file-picker edge case, 200% browser zoom, VoiceOver and other browser engines still need dedicated coverage. These checks do not establish production load capacity or calendar import behavior in every calendar client. AI may enrich location addresses, so the review notice explicitly asks users to check them.

## Future design changes

Create a new sibling folder named `<design-name>-YYYY-MM` when adopting a different system. Keep this dated reference intact, link the new active system from `docs/design-system/README.md`, and update the application README. Record changed tokens, component behavior and actual test results together. Keep private management records and credentials outside these public documents.
