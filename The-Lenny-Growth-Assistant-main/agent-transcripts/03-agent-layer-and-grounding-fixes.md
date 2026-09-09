# Session 3: Agent Layer, Chat Endpoint & Grounding Fixes

## LLM provider abstraction

Built `generate_chat_completion()` as a single entry point routing to
Ollama (local, mandatory) or Anthropic (cloud, optional), with automatic
fallback to Ollama if the cloud provider fails or its API key is missing
— rather than hard-failing the request.

---

## Bug: `IndentationError` crash-looped the backend after a manual edit

**Symptom:** Backend container stuck in `Restarting` after adding
`max_tokens` support to the Ollama client call.

**Root cause:** A copy-paste error left `if max_tokens:` indented 8
spaces instead of 4, misaligning it relative to the enclosing function
body — a plain Python `IndentationError` visible directly in the
container logs' traceback.

**Fix:** Corrected indentation to match the function's 4-space body
level; rebuilt and confirmed the container reached `Up`/`healthy` status.

---

## Bug: Chat requests timed out (503) when ingestion was running concurrently

**Symptom:** A chat request failed with `Ollama is unavailable` after
exactly 90 seconds — the configured timeout — while the background
ingestion script was also running.

**Root cause:** Ollama processes one request at a time by default
(`OLLAMA_NUM_PARALLEL=1`). The chat request was queued behind ingestion's
embedding calls and never got a turn before the client timeout.

**Fix:** This is intended resilience behavior, not a bug to hide — the
request failed gracefully with a clear 503 rather than hanging or
crashing, exactly per the assignment's "model timeout" resilience
requirement. Documented the trade-off (Ollama serializes requests) and
advised pausing ingestion during interactive testing. Also increased the
client-side timeout for the longer Ship 30 essay-generation calls
specifically (90s → 180s) since 1,250-word generations on a small local
model genuinely need more time.

---

## Critical bug: Fabricated statistics on an off-topic question

**Symptom (caught during manual testing, not by automated tests):** Asked
"According to Lenny, what was the exact percentage increase in Airbnb's
revenue after implementing the growth strategy?" — a question with no
basis in the ingested corpus. The model confidently answered
**"Airbnb's revenue grew by 70%"**, complete with an invented timestamp
(`00:07:05`) and attributed the claim generically to "Lenny," while the
actual retrieved source was an unrelated episode (Nilan Peiris, CPO of
Wise, discussing word-of-mouth growth — nothing about Airbnb revenue).

**Root cause (three compounding issues):**
1. The relevance-distance threshold (0.42, per the recalibration in
   Session 2) was still loose enough to admit topically unrelated chunks
   as "context."
2. The system prompt permitted synthesis from "topically related" context
   without an explicit prohibition on inventing specific numbers.
3. The prompt didn't require attributing claims to the *specific* guest
   in the source — allowing the model to default to a generic "Lenny
   said" framing regardless of which guest's transcript was actually used.

**Fix:**
- Tightened the distance threshold back down (0.42 → 0.40).
- Added explicit "absolute rules" to the system prompt: never state a
  number/statistic/date/timestamp not verbatim in context; never
  attribute claims generically to "Lenny" (must cite the specific
  guest/episode); if context is off-topic for the question, say so
  plainly instead of extracting a tangential answer.
- Added per-chunk retrieval distance into the context block so the model
  has an explicit relevance signal, not just raw text.
- **Verified the fix**: re-ran the exact same Airbnb question — response
  correctly stated "There is no mention of Airbnb's revenue in the
  provided transcripts," with no invented numbers.
- **Verified no regression**: re-ran a genuinely on-topic question
  (public speaking confidence) — still returned a grounded answer with
  accurate, relevant sources.

**Known residual limitation (documented, not hidden):** In one later
test, the small 1B local model still appended a generic closing line
attributed loosely to "Lenny Rachitsky" despite the specific-attribution
rule. This is markedly less severe than the original bug (an on-topic,
mostly-accurate answer with one soft misattributed closing remark, vs. a
completely fabricated statistic on an unrelated topic) and is documented
in PRD.md as a known limitation of small local models' instruction-
following rather than silently left unaddressed.

---

## Bug: Over-correction risk when tightening grounding rules

**Context:** After initially making the system prompt very strict ("only
answer if context CLEARLY answers the question"), a **different** failure
mode appeared — the model refused to answer a genuinely relevant question
about company culture principles, even though a closely-matching episode
(Netflix culture, CTO Elizabeth Stone) was in the retrieved context.

**Root cause:** An overly rigid system prompt caused a small model to
default to refusal whenever there wasn't an exact word-for-word match,
rather than reasonably synthesizing from topically relevant material.

**Fix:** Rebalanced the prompt to allow synthesis from genuinely
topically-relevant context while still prohibiting invented specifics —
the two failure modes (fabrication vs. over-refusal) pull in opposite
directions, so the final prompt wording was iterated against both test
cases until each passed without regressing the other.