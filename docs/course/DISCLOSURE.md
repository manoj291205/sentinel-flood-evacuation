Disclosure level: RESTRICTED

This pack is a private draft for the student's review. The provisional filing is on hold. Its final disclosure level remains a user decision.

The following material is withheld from submission and public display: implementation details of the dispatch certification mechanism, its sampling and statistical construction, the unreleased specifications and source code, certificate input structure, internal evaluation traces, and any confidential patent claims. The evidence ledger records results for internal checking; it is not a release clearance.

The only mechanism description cleared for drafting is:

> Before any dispatch is executed, Sentinel checks it against many sampled hazard futures and allows it only when a statistical lower bound on its success clears a fixed threshold; otherwise it holds and escalates to a human (fail-closed). Every decision gets a hash-chained certificate that anyone can replay bit-for-bit.

Nothing in this folder is submitted, posted or shown outside the project until the user approves the text. The level changes to FULL only when the user records it in STATUS.md (after P0 is filed, or if the user decides not to file and releases the mechanism).
