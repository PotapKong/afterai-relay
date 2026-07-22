# Editing authenticated Tiptap pages through Relay CDP

Use this only after the user has authenticated the persistent Relay profile and explicitly asked to edit the private page.

## Safe sequence

1. Open the exact editor URL in the Relay profile and preserve its current document as a local JSON backup.
2. Connect Playwright to the loopback CDP endpoint (`chromium.connect_over_cdp(...)`).
3. Check whether the editable DOM node exposes a Tiptap editor instance:

```js
const editor = document.querySelector('[contenteditable="true"]')?.editor
```

Do not assume this exists on arbitrary editors.

4. Read `editor.getJSON()` before editing. Reuse existing custom-node attributes (for example, product cards, image URLs, CTA links and IDs) instead of reconstructing opaque nodes from rendered HTML.
5. Build a valid Tiptap JSON document and call:

```js
editor.commands.setContent(documentJson)
```

This uses the editor’s update pipeline. Do not assign `innerHTML` directly: it can bypass React/Tiptap state and corrupt custom node views.

6. Wait for the page’s autosave debounce. Verify a successful mutation response when observable, then reload the editor and compare key headings plus CTA/product-card attributes from `editor.getJSON()`.

## Landing-page implementation notes

- Prefer headings, short paragraphs, bullet lists, one relevant course-map image, and one existing product/CTA card.
- Ground claims in the actual course structure. Count modules/lessons from the course editor rather than inventing programme size.
- Keep the editor’s existing purchase URL and price unless the user instructed a commercial change.
- An editor status label can be stale; successful API response plus a fresh reload containing the new JSON is the persistence check.

## Safety

- Never expose cookies, CDP WebSocket URLs, profile files, auth headers, or private content outside the authorized user conversation.
- Stop the temporary noVNC/tunnel immediately after login verification; the persistent Relay profile remains available for the approved editing work.
