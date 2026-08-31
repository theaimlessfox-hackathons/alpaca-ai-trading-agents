---
name: demo-submission
status: completed
created: 2026-08-30T19:10:48Z
updated: 2026-08-30T22:00:00Z
progress: 100%
prd: .claude/prds/thetagate.md
github: (will be set on sync)
---

**What "completed" means here**: every doc/script this epic's subissues actually call for exists and matches its (correctly narrow) acceptance criteria -- see below. It does **not** mean the video is recorded, the slide deck is a rendered PDF, or the submission has been clicked -- those need a human, not more code, and are out of this epic's actual scope (its subissue ACs are things like "docs/VIDEO.md exists," not "the MP4 exists").

# Epic: demo-submission

## Overview

Everything that scores presentation and keeps the entry eligible: replay script, architecture + one-pager, slides, video shot list, social posts, form-field verification, submit checklist.

**Blocked by:** nothing for drafts. Video/screenshots need operator-desk + at least one real sandbox/competition transcript.

## Architecture Decisions

- Write-up is one page: AI logic, risk gates, MCP + CLI + API.
- Video ≤5 min MP4 upload. Core story is 90 seconds (GPT script).
- Social: 5 posts, show vetoes, tag both orgs.
- Confirm lablab form fields Sunday; do not wait until Friday.

## Technical Approach

### Frontend Components

None (uses the desk).

### Backend Services

- `scripts/replay_demo.py`

### Infrastructure

lablab.ai submission UI; X + LinkedIn; Streamlit host URL; public GitHub.

## Implementation Strategy

Form-field check + social #1 today. Docs in parallel mid-week. Video after desk exists. Submit Friday afternoon BST.

## Task Breakdown Preview

1. Verify lablab form fields
2. `replay_demo.py`
3. `docs/ARCHITECTURE.md`
4. `docs/WRITEUP.md`
5. Slides (8–10 pages)
6. Video script + shot list
7. Social calendar execution notes
8. Final submission checklist run

## Dependencies

- Real transcripts for video
- Hosted demo URL
- Competition account ID

## Success Criteria (Technical)

- All required upload slots have files that open. **Scripts/docs done** (ARCHITECTURE.md, WRITEUP.md, SLIDES.md, VIDEO.md, SOCIAL.md, SUBMIT.md, SUBMISSION_FIELDS.md all exist and match their ACs). **Still needs a human**: the actual MP4 recording and a rendered slides PDF/cover image -- nothing in this repo can produce those.
- Video plays the reject → critic → fill story in the first 90 seconds. Script (`docs/VIDEO.md`) is written and timed for this; not yet recorded.
- `.env` not in git; `setup_check.py` documented. **Done** -- confirmed `.env` is gitignored and untracked; `setup_check.py` now actually does what it's documented to (account/options-level/clock/Featherless checks were missing until this pass, see alpaca-stack epic).
- Submitted ≥6 hours before 20:00 UTC Friday. Not yet applicable -- future action.

### Corrected during closeout

- `docs/WRITEUP.md` claimed an "earnings" risk gate. SPY/QQQ/IWM are index ETFs with no earnings dates -- the real field (`risk/engine.py`'s `event_in_life`) is a structural slot for macro/ex-dividend risk that nothing currently populates. Wording fixed to not overclaim an active gate.
- `docs/ARCHITECTURE.md` said the critic was "wave 2" / not yet wired. It's now live-wired into `agents/cycle.py`. Fixed.
- `docs/SUBMIT.md` said the deadline was "9:00 PM Bangladesh Standard Time" alongside a 20:00 UTC figure that only matches British Summer Time (Bangladesh is UTC+6, would be 15:00 UTC). Same error was found and fixed in `CLAUDE.md` earlier; fixed here too.

## Estimated Effort

6–8 hours spread Sun–Fri. 8 tasks. Most can draft in parallel.

## Tasks Created

See `issues.md` for issue → subissue map.

Parent issues: 4
Subissues: 9

- [x] `issue-01-form` Submission form — Technical Writer (2 subissues; form fields still marked provisional pending the actual logged-in wizard, per docs/SUBMISSION_FIELDS.md itself)
- [x] `issue-02-docs` Write-up pack — Technical Writer (3 subissues; earnings→event-risk wording corrected)
- [x] `issue-03-demo` Replay and video — Technical Writer (2 subissues; script done, `scripts/replay_demo.py` exists, actual recording is a human task)
- [x] `issue-04-social` Social prize track — Technical Writer (2 subissues; all 5 posts drafted, not yet posted)

