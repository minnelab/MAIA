---
applyTo: "**"
# GitHub Copilot Code Review Instructions



Assume:
- Code formatting, linting, and style compliance are **already enforced** via tooling.
- The author prefers **few, high-value comments** over incremental or speculative feedback.

## Explicitly Skip These Checks (Do NOT Comment On)
Do **not** raise comments or suggestions related to:

- Code formatting or styling (e.g. whitespace, line length, quotes)
- Linting or static style tools (e.g. ruff, black, isort, flake8, pylint)
- Naming conventions unless they cause real ambiguity or bugs
- Minor refactors, “nice-to-have” cleanups, or personal preferences

If a change is stylistically suboptimal but **correct and safe**, accept it.

---

## What You SHOULD Review
Only comment if one of the following applies:

1. **Correctness**
   - Logical errors
   - Incorrect edge-case handling
   - Broken assumptions
2. **Security**
   - Unsafe defaults
   - Injection risks
   - Credential or secret exposure
3. **Concurrency / Distributed Systems Risks**
   - Race conditions
   - Deadlocks
   - Incorrect async usage
4. **API / Contract Violations**
   - Breaking backward compatibility
   - Incorrect schema or interface usage
5. **Performance Issues**
   - Only if they are clearly harmful or scale-blocking

If none of the above apply, **approve without comment**.

---

## Review Structure (VERY IMPORTANT)
Produce **one single, consolidated review** per request.

Your response must follow this structure:

1. **Overall Verdict**
   - One of: `APPROVE`, `APPROVE WITH MINOR NOTES`, or `REQUEST CHANGES`
2. **Critical Issues (if any)**
   - Bullet list, maximum clarity
   - Only blocking issues
3. **Optional Notes (at most 3)**
   - Only if genuinely helpful
   - No speculative or future-work comments

❌ Do NOT add inline comments  
❌ Do NOT split feedback across multiple responses  
❌ Do NOT introduce new concerns in follow-up review rounds unless the code has materially changed

---

## Follow-Up Review Rounds
When reviewing an updated version:

- **Only verify that previously raised blocking issues are resolved**
- Do **not** introduce new feedback categories
- If issues are resolved, respond with:

> “All previously identified issues are resolved. Approved.”

---

## Acceptance Bias
Default to **APPROVE** unless there is a strong, objective reason to block the change.

The target outcome is:
- Approval in **1 round**
- **Maximum 2–3 rounds** under exceptional circumstances
- Zero repetitive or newly introduced comments after the first review
---
