# Showdown exhibit 1 — live run, 2026-10-12

Q: "Which fosters are free right now if we needed to place a couple of new
dogs this week?" · Both arms: same model, prompt, 20-command budget; Arm B
adds read-only SQL. Run via the /showdown command's subagent orchestration.

ARM A (connector-style): "only two vetted fosters free (Uma Quintero, Flynn
Lindqvist) + three applicants; everyone else is full — 54 fosters have
dogs; the ~10 freed by recent adoptions were immediately refilled by the
Oct 15-16 intake." Method: 6 searches + 12 thread reads incl. both RSVP
mega-threads; hit the budget ceiling; bridged the gap with the refill
inference.

ARM B (tables+email): 15 free cross-checked with per-name evidence + 9
almost-certainly-freed (stale statuses, evidenced via RSVP deltas and
catchall silence) + a do-NOT-use list flagging 7 DB errors it caught
(Monsoon absent, Shasta's foster recorded as "Dana", Sferic unassigned,
stale pending_adoption statuses, etc.) + 22 open applications.

Verdict vs ground truth (~27 actually free): B ~24 named with evidence;
A's "2 free / everyone refilled" is a confident overgeneralization — the
customer-facing failure class. A's process was strong; the budget ceiling
plus one plausible inference produced the wrong operational answer. B's
map-then-verify also functioned as a live DB audit.

Known follow-up from this run: investigate dogs.Shasta foster_name="Dana"
extraction defect.
