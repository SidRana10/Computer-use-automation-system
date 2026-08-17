Review this take-home as a skeptical senior/staff engineer from the hiring team, then fix the repository rather than only listing criticisms.

Focus in this order:
1. Does the artifact actually function as a typed agent-invocable capability rather than a glorified recording?
2. Is replay genuinely deterministic and LLM-free?
3. Are runtime errors deliberately classified and handled, especially business outcomes vs recoverable vs hard failures?
4. Are locator strategies robust and checkpointed rather than brittle selectors/sleeps?
5. Is human handoff real, same-session, ownership-safe, resumable, and evidenced?
6. Can the LLM bypass safety policy or cause arbitrary execution/navigation?
7. Can sensitive values/secrets leak into artifact/log/evidence/human event capture?
8. Does the SurfaceAdapter/artifact design support a credible future desktop/legacy/multi-tenant story without pretending it is implemented?
9. Are there unnecessary abstractions/infrastructure that obscure the vertical slice?
10. Can a reviewer clone the repository and reproduce the demo from README?

Use `reference/ORIGINAL_ASSIGNMENT.txt` as the source of truth. For each issue you find, fix it, add/adjust a test where appropriate, and rerun the suite. End only when the repository is stronger and the documentation reflects the implementation exactly.
