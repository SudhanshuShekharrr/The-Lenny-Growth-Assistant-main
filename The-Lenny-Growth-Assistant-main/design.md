# Design — The Lenny Growth Assistant

## 1. UI/UX Principles

- **Answers over interfaces.** The chat is the product; everything else
  (session list, artifact viewer) supports getting to a grounded answer
  fast, without decoration.
- **Grounding is visible, not hidden.** Every assistant response shows its
  sources inline — this is a trust feature, not an afterthought, since the
  entire value proposition is "advice you can verify," not "AI opinion."
- **Honesty over confidence.** When the assistant doesn't have relevant
  source material, the UI should make that state look distinct from a
  normal answer (not just plain text saying "I don't know" buried in a
  paragraph) — visually flagged, so the user isn't misled into trusting an
  ungrounded answer.

## 2. Information Architecture
App
├── Session sidebar (list of past sessions, "New chat" button)
├── Chat panel (message thread, input box)
│ └── Assistant message
│ ├── Answer text
│ └── Source citations (collapsible list: title + link to transcript)
└── Artifact viewer panel (appears beside chat when an artifact is generated)
└── Sandboxed iframe (Markdown/HTML rendering)


Two-panel layout: chat on the left, artifact viewer opens on the right
when relevant (collapses when not in use, to keep the chat full-width by default).

## 3. Interaction States

| State | Behavior |
|---|---|
| Sending a message | Input disabled, subtle loading indicator on the pending assistant turn |
| Grounded answer | Answer + visible source chips/list below it |
| Ungrounded answer ("no relevant info") | Visually distinct (e.g. muted/outlined style) so it doesn't look like a confident answer |
| LLM/Ollama unavailable (503) | Inline error message in the chat thread with a retry action — never a silent failure |
| Empty session (no messages yet) | Friendly prompt suggesting example questions |
| Artifact generated | Right panel opens automatically with the rendered artifact; chat narrows to make room |

## 4. Responsive Behavior

- **Desktop (≥1024px):** two-column layout, chat + artifact viewer side by side
- **Tablet/narrow (<1024px):** artifact viewer becomes a full-screen overlay
  with a back button, rather than a squeezed side panel
- **Mobile (<640px):** session sidebar collapses into a hamburger/drawer;
  single-column chat; artifact viewer opens as a full-screen sheet

## 5. Accessibility

- All interactive elements (send button, session items, source links)
  reachable via keyboard, with visible focus states
- Loading/error states announced via `aria-live` regions so screen reader
  users aren't left waiting silently
- Sufficient color contrast for the "ungrounded answer" visual treatment —
  distinct by more than color alone (e.g. an icon + label, not just a
  lighter shade)
- Sandboxed artifact iframe has a descriptive `title` attribute for
  assistive technology

## 6. Key Design Decisions

- **No streaming in this step:** responses are returned as a single JSON
  payload rather than token-streamed. This was a deliberate scope
  trade-off given the timeline — streaming is a natural follow-up
  enhancement and doesn't change the underlying grounding architecture.
- **Citations as structured data, not inline text:** sources are returned
  as a separate `sources[]` array (title, source_path, chunk_index) rather
  than embedded in the answer text, so the frontend can render them
  consistently (e.g. as chips) regardless of how the LLM phrases its answer.
- **Sandboxed iframe over `dangerouslySetInnerHTML`:** any approach that
  injects LLM-generated HTML directly into the parent page's DOM risks XSS
  against the app itself. An iframe with `sandbox="allow-scripts"` (no
  `allow-same-origin`) isolates that risk to a blank context with no
  access to cookies, local storage, or the parent page.