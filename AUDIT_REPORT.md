# Audit and remediation report

Audit date: 2026-09-27. Upstream baseline: `47ed00b746cd59f4881eee3268ef3e4c6e6ac71c` (2.2.0).

## Scope and method

Reviewed application entry points, CLI/GUI, controller/task lifecycle, browser/DOM agents, credentials/forms/CV parsing, storage/configuration/telemetry, model integration, extension JavaScript, dependency manifests, existing tests, and GitHub workflows. Three parallel review agents owned distinct areas; integration fixes and cross-area checks were completed in the parent audit.

This is a source and regression audit of the current tree, not a penetration test of LinkedIn, a guarantee of platform compatibility, or a credential-history audit. No real login, job application, email, paid API request, or production release was performed.

## Confirmed defects repaired

| Priority | Finding and impact | Remediation and regression coverage |
| --- | --- | --- |
| High | Profile IDs and CSV filenames escaped configured storage paths, including delete operations. | Reject path components, Windows device names and escaping symlinks; test unsafe IDs and paths. |
| High | CSV profile serialization lost lists/nulls; schema-changing appends silently misaligned columns; failed writes could truncate files. | Lossless JSON field encoding with safe legacy decoding, column validation/reordering, atomic replacement and process-local locking. |
| High | Browser/form presence checks reported success after timeouts; clicking Submit was recorded as applied. | Require actual elements and fresh confirmation, reject stale confirmation, bound forms and require explicit answers/consent. |
| High | Automatic retries could replay a submission or whole completed plan. | No automatic submission or whole-plan replay after ambiguous failure; false results stop dependent steps. |
| High | CLI/GUI could not start or execute commands correctly; GUI moved browser objects to an unrelated thread/loop. | Async command dispatch, cancellable console input, one-loop GUI event pumping, real controls and cancellation. |
| High | Millisecond constants were passed to asyncio as seconds; listing/modal loops could run indefinitely. | Explicit time conversions, bounded iterations, duplicate listing checks, finite browser step deadlines. |
| High | Task cancellation relabeled work without stopping it; rapid tasks collided on timestamp IDs; queues were not initialized. | Cancel/gather actual runners, UUID IDs, initialized queue accounting and semaphore-controlled execution. |
| High | Raw credentials/form payloads appeared in diagnostics; telemetry duplicated events and mishandled disabled mode. | Recursive diagnostic redaction, DOM secret filtering, single-write events, disabled-mode no writes, metric/date fixes. |
| High | Provider calls used a removed OpenAI interface and shared global credentials; missing awaits broke normal chat. | Isolated AsyncOpenAI clients, awaited replies/streams, deterministic cleanup, real vision calls and explicit provider errors. |
| High | Old release dependencies had 34 npm findings; PyPDF2 had a known parser denial-of-service vulnerability. | Upgrade release tools and compatible transitives; migrate to patched pypdf; pin full Python runtime/development trees and audit both ecosystems. |
| Medium | Session retries/state validation used missing fields; Stop/Start retained paused state; shared loggers were mishandled. | Validated state snapshots, idempotent lifecycle, reset pause on restart, explicit logger ownership and configurable long-flow timeout. |
| Medium | Attached browser created a fresh unauthenticated context; partial failures leaked the Playwright driver. | Reuse existing context and separate owned-browser closing from attached-driver disconnection; cleanup after partial startup. |
| Medium | CV text could be overwritten by empty LLM defaults; DOCX was read as text; caches survived file changes. | Preserve extracted text, parse DOCX, cap file/archive/page sizes, invalidate caches by file metadata; test PDF/DOCX/TXT. |
| Medium | GUI constructors used unsupported ttk options; callbacks deadlocked or called Tk from workers; profile versions collided. | Correct ttk styling, callback/lock separation, main-thread dispatch queue, explicit component data contracts, stable version IDs. |
| Medium | Tracker logging was silently bypassed by default, timestamp comparisons failed, and restart history was lost. | Restore default persistence, typed filters/history, explicit disabled/bypass behavior, diagnostic redaction. |
| Medium | Invalid numeric configuration crashed before validation and configured data directories were ignored. | Bounded finite parsing with defaults and consistent DATA_DIR propagation. |
| High | Bulk applications ignored their disabled setting and job limits; a search could proceed with only one requested criterion filled. | Require explicit bulk enablement, enforce configured job limits/timing, and require both title and location before search in either layout. |
| Medium | Model utilities imported a nonexistent model and referenced nonexistent fields; merging mutated input descriptions. | Align with current models, preserve source inputs, use supported application metrics. |
| Medium | Extension reported sent commands while disconnected and retained stale status on native-host failure. | Connection handshake, accurate errors/status reset, bounded reconnect scheduling, sender/site checks; six JavaScript regressions. |
| Medium | Tests used obsolete Selenium APIs, invalid async fixtures and crashing Tk teardown; CI never ran Python tests. | Replace stale expectations with real current contracts, separate live/display tests, add offline CI and block release on checks. |

## Verification

- Python offline suite: 158 passed, 15 explicitly skipped (14 display tests and one live website/provider diagnostic).
- Extension JavaScript: 6 tests passed.
- Ruff syntax/undefined-name checks passed.
- Synthetic offline Edge/Playwright checks passed for DOM reconstruction, repeated highlight cleanup, secret filtering, presence detection, and confirmed form submission against local HTML.
- Complete pinned Python development tree and npm release lockfile: **zero known vulnerabilities** in the final database scan. This is point-in-time evidence, not a guarantee of undiscovered vulnerability absence.
- High-confidence credential-pattern scan of tracked source files found no matches; full Git history was not scanned.
- Linux GitHub CI passed with Xvfb, including the complete GUI suite, extension tests, static checks, and both dependency audits. Local Windows display runs intermittently failed while Tcl read its installed runtime files; the clean Linux run verifies the application independently of that local runtime issue. [Initial full CI evidence](https://github.com/ZouhairMudakka/Autonomous-Job-Seeker/actions/runs/36321005619).

## Remaining limits

1. Real LinkedIn selectors, authenticated workflows, and actual submissions were not exercised. Layout changes can still require selector updates.
2. Several pre-existing features are incomplete: structured LLM CV enrichment, advanced matching, automatic login/challenge-token integration, and extension installation/native host. Documentation now labels these accurately.
3. Profiles and local browser/session files are plaintext. Diagnostic redaction covers new known structured fields and recognizable credentials, not every possible secret in arbitrary text. Existing data is not migrated or scrubbed automatically.
4. File locks coordinate one process. Run independent application processes with independent DATA_DIR values.
5. API tests use mocked SDK responses; model availability, provider authentication and billing were not validated.
6. Optional dashboard UI/deployment and package release publication were not executed. Release configuration and dependency audit were checked without publishing.

## Reproduce

Use the commands in [README.md](README.md). The default test suite does not require browser downloads or credentials. Enable `--run-gui` on a machine with Tk and a display; live diagnostics additionally require `--run-live` and explicit credentials. Dependency inputs are `requirements*.txt`; resolved trees are `requirements.lock` and `requirements-dev.lock`.
