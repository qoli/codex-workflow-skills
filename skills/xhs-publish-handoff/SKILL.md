---
name: xhs-publish-handoff
description: >-
  Use when preparing, validating, filling, or recording a Xiaohongshu/XHS post after the user has approved the content and images. This skill handles the publishing handoff: validate title, body, hashtags, image order, and image dimensions; optionally open the Xiaohongshu creator composer through the user's existing Arc CDP session; optionally upload images and fill title/body; stop before the final publish click unless the user explicitly delegates that live action.
---

# XHS Publish Handoff

Use this only after the post content and image assets are approved.

## Prerequisites

This skill handles the publishing handoff. It does not design image cards. For
Figma card creation, use `xhs-figma-cards` with a working Figma automation
adapter. The workflow was tested with
[qoli/figma-mcp-go](https://github.com/qoli/figma-mcp-go), but other Figma MCP
or automation adapters can work if they expose equivalent read/write operations.
Without a working Figma adapter, the upstream card-design workflow cannot
inspect or update Figma.

Browser filling requires an existing CDP-enabled browser session, such as Arc or
Chrome at `http://localhost:9222`.

## Workflow

1. Confirm the inputs: title/body or draft file, image directory, image order, target account, and whether this is immediate or scheduled publishing.
2. Validate the package with `scripts/xhs_prepare_publish.py` before opening the browser.
3. Review warnings with the user, especially URL-like text, App Store/download wording, private-contact wording, title length, body length, hashtag count, image count, and image dimensions.
4. Use the existing Arc CDP browser session for Xiaohongshu creator work. Do not create a separate account state unless the user asks.
5. Prefer the image composer URL (`target=image`). If Xiaohongshu opens the home page or video tab, switch to `发布笔记` -> `上传图文` before filling.
6. With approval, open the creator composer. With a separate approval, fill images/title/body and wait until the uploaded image count and editor fields are visible.
7. After filling, verify the browser state: account, image count, title, body length, recognized `[话题]` hashtags, suggested extra hashtags, and visible publish controls.
8. Stop before the final publish click unless the user explicitly delegates that live action in this publishing step.
9. After publishing, record the public URL if available, or creator-manager evidence if the public URL is not available yet.

## Script

Resolve `scripts/xhs_prepare_publish.py` relative to this skill directory.

Validation only:

```sh
python3 skills/xhs-publish-handoff/scripts/xhs_prepare_publish.py \
  --draft <approved-post.md> \
  --images <image-directory> \
  --expected-count <image-count> \
  --expected-width <width> \
  --expected-height <height>
```

Open creator page:

```sh
python3 skills/xhs-publish-handoff/scripts/xhs_prepare_publish.py \
  --draft <approved-post.md> \
  --images <image-directory> \
  --expected-count <image-count> \
  --open-browser
```

Fill composer after approval:

```sh
python3 skills/xhs-publish-handoff/scripts/xhs_prepare_publish.py \
  --draft <approved-post.md> \
  --images <image-directory> \
  --expected-count <image-count> \
  --fill-browser
```

The script defaults to natural sorting for `*.png` files, so Figma exports like
`01-cover.png`, `02-method.png`, and `07-closing.png` can be used directly.
Use `--image-manifest <file>` when order cannot be inferred from file names.
Use `--strict-card-names` only when the package must follow the old
`card-01.png` sequence.

Use `--expected-count`, `--expected-width`, `--expected-height`, `--title`,
`--body`, or `--body-file` when the package differs from the defaults. Use
`--expected-hashtags "#A #B #C"` when the final browser verification must confirm
specific Xiaohongshu `[话题]` recognition.

Browser fill behavior:

- Opens the image composer URL by default:
  `https://creator.xiaohongshu.com/publish/publish?from=menu&target=image`
- Uploads images through the current Arc CDP session.
- Waits for the uploaded count and editor fields before filling copy.
- Fills title/body and then reports recognized topics, extra suggested topics,
  image count, and publish controls.
- Never clicks final `发布` by itself.

## Boundaries

- Do not design or revise the image cards here; use the Figma image-card workflow first.
- Do not run unattended account operations, mass posting, mass commenting, mass liking, mass collecting, or follow automation.
- Do not store cookies, QR codes, tokens, browser profiles, or session exports in a project repo.
- Do not treat validation warnings as blockers automatically; report them and let the user decide.
- Do not click final publish/save without explicit live approval.
