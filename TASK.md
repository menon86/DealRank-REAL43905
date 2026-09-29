# TASK: UI/UX — Deal form & deal list

## Why
The core MVP flow (build, form fields, API wiring) already works end to end
— this is polish, not new functionality. Grading likely weighs on the app
being pleasant and clear to actually use, not just functionally correct.

## Where
- `frontend/src/components/DealForm.tsx`
- `frontend/src/components/DealList.tsx`
- Shared CSS: `frontend/src/styles.css`

## What to do

1. **Leasing-mode toggle clarity.** The per-unit vs. per-bed switch changes
   which fields are live (units/rent-per-unit vs. beds/rent-per-bed). Make
   sure it's visually obvious which mode is active and which fields are
   irrelevant/hidden in the other mode — right now this is functional but
   worth a pass for a first-time user.

2. **Validation & error states.** `DealForm.tsx` should mirror the API's 422
   rules client-side (per D7 in `docs/build-plan.md`: percentages are whole
   numbers in the UI, decimal fractions behind the API boundary — don't
   break that conversion). Add inline field-level error messages instead of
   relying on a failed submit.

3. **Empty states.** What does `DealList.tsx` show with zero deals? Should
   prompt toward "Add deal," not just render an empty table.

4. **Responsive layout.** Check the form and list at narrower widths —
   they're likely fine on desktop but unverified below ~900px.

5. **Field grouping/labels.** Group related inputs (e.g. all debt terms
   together, all growth-rate assumptions together) with clear section
   labels so the form reads as sections, not one long list.

## Constraints
- Hand-written CSS only, per D5 in `docs/build-plan.md` — no component
  library.
- Don't touch `frontend/src/lib/client.ts` or the API contract unless a bug
  surfaces; this task is presentation-layer only.

## Acceptance
- A first-time user can fill out a per-bed student housing deal and a
  per-unit suburban garden deal without confusion about which fields apply.
- Invalid input shows a clear, field-level message before submit.
- Looks intentional at both desktop and ~400px width.
