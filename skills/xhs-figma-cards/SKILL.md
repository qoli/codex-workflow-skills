---
name: xhs-figma-cards
description: >-
  Use when creating or revising Xiaohongshu/XHS share image cards in Figma for
  any project. Trigger when the user asks to turn a Blog, markdown draft, product
  idea, launch note, or existing Figma canvas into Xiaohongshu image-card
  designs. Use Figma as the review and assembly surface; route generated bitmap
  visuals, poster-style covers, illustrations, and style-heavy cards through
  imagegen before placing the selected output back into Figma.
---

# XHS Figma Cards

Use Figma as the working surface for Xiaohongshu share images. Choose the
production route before drawing: editable Figma layout, generated bitmap, or a
hybrid of both.

## Figma Automation

Figma canvas work requires a configured Figma automation adapter with read/write
operations for inspecting pages, creating or updating frames, editing text
layers, and importing assets. This workflow was tested with
[qoli/figma-mcp-go](https://github.com/qoli/figma-mcp-go), but other Figma MCP
or automation adapters can work if they expose equivalent capabilities.

If no working Figma adapter is available, do not claim that the canvas was
created or updated. You may still draft card copy, propose a card structure, or
prepare imagegen prompts, but the Figma execution step is blocked until adapter
access works.

## Capability routing

- Use **Figma MCP or equivalent Figma automation** for canvas work: inspect the current page, create or update
  `1080 x 1440` frames, edit text layers, place screenshots/assets, import final
  images, and export checks.
- Use **imagegen** when the card needs a generated bitmap: high-impact poster
  covers, style-heavy visuals, ad-like compositions, illustrations, photo/image
  treatments, or when the user explicitly asks for image generation.
- Use a **hybrid route** when appropriate: generate the main visual with
  imagegen, then import the selected bitmap into Figma and keep only practical
  labels or final copy editable.
- Do not substitute Python/PIL, HTML, or CSS for image generation when the user
  asks for generated visual design.

## Workflow

1. Read the source content the user provides, such as a Blog, markdown draft,
   product note, launch note, or current Figma frame.
2. Convert it into a short multi-card Xiaohongshu structure before drawing:
   - one job per card;
   - short headline, punchline, or optional subline;
   - product UI, screenshot, or relevant visual proof when available.
3. Use Simplified Chinese for Xiaohongshu-facing copy by default, including
   card text, Figma text drafts, and visible Chinese text requested in imagegen
   prompts. Use Traditional Chinese or bilingual copy only when the user
   explicitly asks for it.
4. Decide the route: editable Figma layout, generated bitmap, or hybrid.
5. For Figma layout work, use the configured Figma adapter to create or update
   `1080 x 1440` frames unless the user specifies another size. Keep text as
   editable Figma text layers.
6. For generated bitmap work, use the imagegen skill and built-in `image_gen`
   by default. Inspect the result for composition, text accuracy, and unwanted
   artifacts. Copy the chosen output from `$CODEX_HOME/generated_images/...`
   into the workspace before importing it into Figma.
7. Use visually confirmed image assets. Do not choose screenshots only from file
   names.
8. Let the user intervene directly in Figma. When they make changes, inspect the
   current Figma canvas and continue from their version.
9. Discuss design issues against the visible artifact: focus, hierarchy,
   readability, crop, text accuracy, and whether each card has one clear purpose.

## Boundaries

- Do not use HTML as the default image-card workflow.
- Do not claim Figma was updated unless a Figma adapter write/import operation
  succeeded.
- Do not claim image generation succeeded unless there is a real imagegen
  artifact or saved output path.
- Do not leave a Figma-used generated asset only under `$CODEX_HOME`; copy the
  final selected image into the workspace or another user-approved durable path.
- Do not export final PNGs unless the user explicitly asks.
- Do not enter Xiaohongshu publishing flow unless the user explicitly asks.
- Do not rebuild user-edited Figma work from scratch when you can continue from the current canvas.
