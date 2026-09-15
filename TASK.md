# TASK: UI/UX — Comparison table & ranking view, and export verification

## Why
Same rationale as the deal-form/list task — functionality is done, this is
the polish pass. This lane also owns the one functionally-unverified piece
of the MVP: PDF/PPTX export has never actually been clicked against a live
API in testing.

## Where
- `frontend/src/components/ComparisonTable.tsx`
- `frontend/src/components/RankingView.tsx`
- Shared CSS: `frontend/src/styles.css`

## What to do

1. **Verify PDF/PPTX export actually works.** Click "Download PDF" and
   "Download PPTX" in `ComparisonTable.tsx` against a running backend with
   real seeded deals, and open both output files. This has not been tested
   end-to-end anywhere yet — treat it as a bug hunt, not just a UI task, if
   it's broken.

2. **Table readability at 3-5 columns.** `ComparisonTable.tsx` puts deals as
   columns — check it doesn't get cramped or force horizontal scroll
   awkwardly at 5 deals, and that the waterfall rows (GPR → vacancy → EGI →
   OpEx → turnover → NOI) read clearly against the headline metrics below
   them.

3. **Loading/error states.** Both the comparison table and ranking view, and
   the PDF/PPTX download buttons, should show a visible loading state and a
   real error message on failure — not a silent no-op.

4. **Headline metric hierarchy.** Both IRRs are shown per the charter, but
   unlevered IRR is the ranking basis — make sure that's visually
   unambiguous (per `docs/build-plan.md` 5.4/5.5), not just a text label
   easy to miss.

5. **Ranking view disclosure text.** `RankingView.tsx` already states that
   ranking uses unlevered IRR against a user-entered hurdle — polish this so
   it reads as a clear methodology note, not a buried disclaimer, since a
   grader will specifically look for this per the charter's "Defense under
   questioning" section.

## Constraints
- Hand-written CSS only, per D5 in `docs/build-plan.md` — no component
  library.
- Don't change what's sorted on or how rank score is computed
  (`app/api/rank.py`) — presentation and export only, unless export is
  actually broken.

## Acceptance
- PDF and PPTX both download and open correctly with real data.
- Comparison table is legible at 5 deals without awkward overflow.
- A user glancing at the ranking view can immediately tell which IRR basis
  ranking uses and why.
