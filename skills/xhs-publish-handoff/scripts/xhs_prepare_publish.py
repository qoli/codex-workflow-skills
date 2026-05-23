#!/usr/bin/env python3
"""Prepare a Xiaohongshu image post without clicking publish.

The script validates an approved Xiaohongshu post package, then can optionally
reuse the existing Arc CDP browser session to open the creator composer, upload
images, and fill title/body. It deliberately stops before the final publish
action.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import re
import struct
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable, Sequence


DEFAULT_CDP = "http://localhost:9222"
DEFAULT_PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publish?from=menu&target=image"
DEFAULT_MAX_TITLE_CHARS = 20
DEFAULT_MAX_BODY_CHARS = 1000
DEFAULT_EXPECTED_WIDTH = 2160
DEFAULT_EXPECTED_HEIGHT = 2880
DEFAULT_EXPECTED_COUNT = 6
RISK_TERMS = (
    "打开网址",
    "点击链接",
    "复制链接",
    "官网",
    "下载",
    "App Store",
    "应用商店",
    "微信",
    "VX",
    "私信",
    "加群",
)


class PublishError(Exception):
    """A validation or browser-preparation error."""


@dataclasses.dataclass(frozen=True)
class ImageInfo:
    path: Path
    width: int
    height: int
    format: str
    size_bytes: int


@dataclasses.dataclass(frozen=True)
class PostPackage:
    draft: Path
    image_dir: Path
    title: str
    body: str
    images: list[ImageInfo]
    warnings: list[str]


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        package = build_package(args)
        print_summary(package, args)

        if args.package_json:
            write_package_json(package, Path(args.package_json))

        if args.open_browser or args.fill_browser:
            prepare_browser(package, args)

        if package.warnings and not args.allow_warnings:
            print(
                "\nWarnings found. Review them before publishing, or rerun with "
                "--allow-warnings after review.",
                file=sys.stderr,
            )
            return 2

        return 0
    except PublishError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate and prepare a Xiaohongshu image post package.",
    )
    parser.add_argument("--draft", required=True, help="Markdown draft or published record.")
    parser.add_argument("--images", required=True, help="Directory containing card images.")
    parser.add_argument(
        "--image-glob",
        default="*.png",
        help="Image glob inside --images. Files are naturally sorted unless --image-manifest is set.",
    )
    parser.add_argument(
        "--image-manifest",
        help=(
            "Optional newline or JSON manifest listing image file names in publish order. "
            "Entries are resolved relative to --images unless absolute."
        ),
    )
    parser.add_argument(
        "--strict-card-names",
        action="store_true",
        help="Require card-01.png..card-NN.png names after collecting images.",
    )
    parser.add_argument("--expected-count", type=int, default=DEFAULT_EXPECTED_COUNT)
    parser.add_argument("--expected-width", type=int, default=DEFAULT_EXPECTED_WIDTH)
    parser.add_argument("--expected-height", type=int, default=DEFAULT_EXPECTED_HEIGHT)
    parser.add_argument("--max-title-chars", type=int, default=DEFAULT_MAX_TITLE_CHARS)
    parser.add_argument("--max-body-chars", type=int, default=DEFAULT_MAX_BODY_CHARS)
    parser.add_argument("--title", help="Override title instead of reading from draft.")
    parser.add_argument("--body", help="Override body instead of reading from draft.")
    parser.add_argument("--body-file", help="Read body override from a text file.")
    parser.add_argument(
        "--expected-hashtags",
        help="Comma/space separated hashtags expected to be recognized after browser fill.",
    )
    parser.add_argument(
        "--no-append-tags",
        action="store_true",
        help="Do not append the draft's ## Tags block when the body has no hashtags.",
    )
    parser.add_argument(
        "--allow-warnings",
        action="store_true",
        help="Return success even when copy warnings are found.",
    )
    parser.add_argument(
        "--package-json",
        help="Optional output path for the validated title/body/image manifest.",
    )
    parser.add_argument(
        "--open-browser",
        action="store_true",
        help="Open the Xiaohongshu creator publish page in the existing Arc CDP session.",
    )
    parser.add_argument(
        "--fill-browser",
        action="store_true",
        help="Upload images and fill title/body in the existing Arc CDP session. Never publishes.",
    )
    parser.add_argument("--cdp-url", default=DEFAULT_CDP, help="Arc CDP endpoint.")
    parser.add_argument("--publish-url", default=DEFAULT_PUBLISH_URL)
    parser.add_argument(
        "--browser-timeout-ms",
        type=int,
        default=45000,
        help="Timeout for browser actions.",
    )
    parser.add_argument(
        "--skip-browser-health-check",
        action="store_true",
        help="Skip the /json/version health check before browser work.",
    )
    return parser.parse_args(argv)


def build_package(args: argparse.Namespace) -> PostPackage:
    draft = Path(args.draft).expanduser().resolve()
    image_dir = Path(args.images).expanduser().resolve()
    if not draft.is_file():
        raise PublishError(f"draft not found: {draft}")
    if not image_dir.is_dir():
        raise PublishError(f"image directory not found: {image_dir}")

    markdown = draft.read_text(encoding="utf-8")
    title = normalize_text(args.title) if args.title else extract_title(markdown)
    body = read_body(args, markdown)
    images = collect_images(
        image_dir=image_dir,
        image_glob=args.image_glob,
        image_manifest=args.image_manifest,
        expected_count=args.expected_count,
        expected_width=args.expected_width,
        expected_height=args.expected_height,
        strict_card_names=args.strict_card_names,
    )
    warnings = validate_copy(
        title=title,
        body=body,
        max_title_chars=args.max_title_chars,
        max_body_chars=args.max_body_chars,
    )
    return PostPackage(
        draft=draft,
        image_dir=image_dir,
        title=title,
        body=body,
        images=images,
        warnings=warnings,
    )


def read_body(args: argparse.Namespace, markdown: str) -> str:
    if args.body_file:
        body = Path(args.body_file).expanduser().read_text(encoding="utf-8")
    elif args.body:
        body = args.body
    else:
        body = extract_body(markdown)
        if not args.no_append_tags and "#" not in body:
            tags = extract_tags(markdown)
            if tags:
                body = f"{body.rstrip()}\n\n{tags}"
    return normalize_text(body)


def extract_title(markdown: str) -> str:
    candidates = [
        extract_fenced_after_heading(markdown, "Title"),
        extract_fenced_after_label(markdown, "Recommended title:"),
    ]
    for candidate in candidates:
        if candidate:
            return normalize_text(candidate)

    match = re.search(r"^1\.\s+(.+)$", markdown, re.MULTILINE)
    if match:
        return normalize_text(match.group(1))
    raise PublishError("could not extract title; pass --title")


def extract_body(markdown: str) -> str:
    for heading in ("Body", "Body Copy"):
        body = extract_fenced_after_heading(markdown, heading)
        if body:
            return normalize_text(body)
    raise PublishError("could not extract body; pass --body or --body-file")


def extract_tags(markdown: str) -> str:
    tags = extract_fenced_after_heading(markdown, "Tags")
    return normalize_text(tags) if tags else ""


def extract_fenced_after_heading(markdown: str, heading: str) -> str:
    pattern = rf"^##\s+{re.escape(heading)}\s*$([\s\S]*?)(?=^##\s+|\Z)"
    match = re.search(pattern, markdown, re.MULTILINE)
    if not match:
        return ""
    return first_fenced_block(match.group(1))


def extract_fenced_after_label(markdown: str, label: str) -> str:
    index = markdown.find(label)
    if index < 0:
        return ""
    return first_fenced_block(markdown[index + len(label) :])


def first_fenced_block(text: str) -> str:
    match = re.search(r"```(?:[a-zA-Z0-9_-]+)?\s*\n([\s\S]*?)\n```", text)
    return match.group(1) if match else ""


def normalize_text(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(lines).strip()


def collect_images(
    image_dir: Path,
    image_glob: str,
    image_manifest: str | None,
    expected_count: int,
    expected_width: int,
    expected_height: int,
    strict_card_names: bool,
) -> list[ImageInfo]:
    if image_manifest:
        paths = read_image_manifest(Path(image_manifest), image_dir)
    else:
        paths = sorted(
            (path for path in image_dir.glob(image_glob) if path.is_file()),
            key=lambda path: natural_sort_key(path.name),
        )
    if len(paths) != expected_count:
        raise PublishError(
            f"expected {expected_count} images matching {image_glob}, found {len(paths)}"
        )
    if strict_card_names:
        expected_names = [f"card-{index:02d}.png" for index in range(1, expected_count + 1)]
        actual_names = [path.name for path in paths]
        if actual_names != expected_names:
            raise PublishError(
                "image order/names are not the expected card sequence: "
                f"expected {expected_names}, found {actual_names}"
            )

    images = []
    for path in paths:
        info = read_image_info(path)
        if info.width != expected_width or info.height != expected_height:
            raise PublishError(
                f"{path} is {info.width} x {info.height}, expected "
                f"{expected_width} x {expected_height}"
            )
        images.append(info)
    return images


def natural_sort_key(value: str) -> list[object]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", value)]


def read_image_manifest(manifest_path: Path, image_dir: Path) -> list[Path]:
    manifest_path = manifest_path.expanduser().resolve()
    if not manifest_path.is_file():
        raise PublishError(f"image manifest not found: {manifest_path}")
    text = manifest_path.read_text(encoding="utf-8").strip()
    if not text:
        raise PublishError(f"image manifest is empty: {manifest_path}")

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        entries = [
            line.strip()
            for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
    else:
        if not isinstance(payload, list):
            raise PublishError("image manifest JSON must be a list")
        entries = []
        for item in payload:
            if isinstance(item, str):
                entries.append(item)
            elif isinstance(item, dict) and isinstance(item.get("path"), str):
                entries.append(item["path"])
            else:
                raise PublishError("image manifest entries must be strings or objects with a path")

    paths = []
    for entry in entries:
        path = Path(entry).expanduser()
        if not path.is_absolute():
            path = image_dir / path
        path = path.resolve()
        if not path.is_file():
            raise PublishError(f"image listed in manifest not found: {path}")
        paths.append(path)
    return paths


def read_image_info(path: Path) -> ImageInfo:
    data = path.read_bytes()
    if len(data) >= 24 and data.startswith(b"\x89PNG\r\n\x1a\n"):
        width, height = struct.unpack(">II", data[16:24])
        return ImageInfo(path=path, width=width, height=height, format="PNG", size_bytes=len(data))
    raise PublishError(f"unsupported or invalid image file: {path}")


def validate_copy(
    title: str,
    body: str,
    max_title_chars: int,
    max_body_chars: int,
) -> list[str]:
    if not title:
        raise PublishError("title is empty")
    if not body:
        raise PublishError("body is empty")
    warnings = []
    title_chars = len(title)
    body_chars = len(body)
    if title_chars > max_title_chars:
        warnings.append(f"title has {title_chars} chars; configured limit is {max_title_chars}")
    if body_chars > max_body_chars:
        warnings.append(f"body has {body_chars} chars; configured limit is {max_body_chars}")

    hashtags = re.findall(r"#[\w\u4e00-\u9fff]+", body)
    if len(hashtags) > 12:
        warnings.append(f"body has {len(hashtags)} hashtags; consider keeping the set tighter")
    if not hashtags:
        warnings.append("body has no hashtags")

    url_like = re.findall(r"https?://\S+|[A-Za-z0-9.-]+\.[A-Za-z]{2,}", body)
    if url_like:
        warnings.append("body contains URL-like text; review Xiaohongshu traffic-risk wording")

    for term in RISK_TERMS:
        if term in body:
            warnings.append(f"body contains risk term: {term}")
    return warnings


def extract_hashtags(text: str) -> list[str]:
    hashtags = re.findall(r"#[\w\u4e00-\u9fff]+", text)
    return list(dict.fromkeys(hashtags))


def parse_expected_hashtags(args: argparse.Namespace, body: str) -> list[str]:
    if not args.expected_hashtags:
        return extract_hashtags(body)
    tokens = re.split(r"[\s,，]+", args.expected_hashtags.strip())
    return [token if token.startswith("#") else f"#{token}" for token in tokens if token]


def print_summary(package: PostPackage, args: argparse.Namespace) -> None:
    print("Xiaohongshu publish package")
    print(f"- draft: {package.draft}")
    print(f"- image dir: {package.image_dir}")
    print(f"- images: {len(package.images)}")
    for index, image in enumerate(package.images, start=1):
        mb = image.size_bytes / 1024 / 1024
        print(f"  {index:02d}. {image.path.name} {image.width}x{image.height} {mb:.2f} MB")
    print(f"- title ({len(package.title)} chars): {package.title}")
    print(f"- body chars: {len(package.body)} / {args.max_body_chars}")
    hashtags = re.findall(r"#[\w\u4e00-\u9fff]+", package.body)
    print(f"- hashtags ({len(hashtags)}): {' '.join(hashtags) if hashtags else '(none)'}")
    if package.warnings:
        print("- warnings:")
        for warning in package.warnings:
            print(f"  - {warning}")
    else:
        print("- warnings: none")
    print("- final publish click: disabled by this script")


def write_package_json(package: PostPackage, output_path: Path) -> None:
    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "draft": str(package.draft),
        "image_dir": str(package.image_dir),
        "title": package.title,
        "body": package.body,
        "images": [
            {
                "path": str(image.path),
                "width": image.width,
                "height": image.height,
                "format": image.format,
                "size_bytes": image.size_bytes,
            }
            for image in package.images
        ],
        "warnings": package.warnings,
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"- package json: {output_path}")


def prepare_browser(package: PostPackage, args: argparse.Namespace) -> None:
    if not args.skip_browser_health_check:
        check_cdp(args.cdp_url)
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - depends on local runtime
        raise PublishError(f"Playwright is required for browser mode: {exc}") from exc

    timeout = args.browser_timeout_ms
    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(args.cdp_url, timeout=timeout)
        if not browser.contexts:
            raise PublishError("Arc CDP has no reusable browser context")
        context = browser.contexts[0]
        page = choose_page(context, args.publish_url)
        page.set_default_timeout(timeout)
        if not is_image_publish_url(page.url):
            page.goto(args.publish_url, wait_until="domcontentloaded")
        page.wait_for_load_state("domcontentloaded")
        ensure_image_publish_page(page, args.publish_url)
        print(f"- browser page: {page.url}")
        if not args.fill_browser:
            print("- browser opened only; not filling composer")
            return
        upload_images(page, package.images)
        wait_for_upload_ready(page, len(package.images))
        fill_composer(page, package.title, package.body)
        verify_browser_state(page, package, parse_expected_hashtags(args, package.body))
        print("- composer prepared; review manually and click publish yourself")
        # Do not call browser.close(): this connection is the user's live Arc.


def check_cdp(cdp_url: str) -> None:
    version_url = cdp_url.rstrip("/") + "/json/version"
    try:
        with urllib.request.urlopen(version_url, timeout=5) as response:
            if response.status != 200:
                raise PublishError(f"CDP health check failed: HTTP {response.status}")
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise PublishError(f"CDP health check failed for {version_url}: {exc}") from exc
    print(f"- CDP: {data.get('Browser', 'ok')}")


def choose_page(context, publish_url: str):
    for page in context.pages:
        if "creator.xiaohongshu.com" in page.url:
            return page
    if context.pages:
        return context.pages[-1]
    return context.new_page()


def is_image_publish_url(url: str) -> bool:
    return "creator.xiaohongshu.com/publish/publish" in url and "target=image" in url


def ensure_image_publish_page(page, publish_url: str) -> None:
    if is_image_publish_url(page.url):
        wait_for_image_upload_panel(page)
        return

    try:
        page.get_by_text("发布笔记", exact=True).click(timeout=3000)
        page.get_by_text("上传图文", exact=True).click(timeout=5000)
    except Exception:
        page.goto(publish_url, wait_until="domcontentloaded")
    wait_for_image_upload_panel(page)


def wait_for_image_upload_panel(page) -> None:
    try:
        page.wait_for_selector('input[type="file"]', state="attached", timeout=15000)
    except Exception as exc:
        raise PublishError("could not find Xiaohongshu image upload input") from exc


def upload_images(page, images: Iterable[ImageInfo]) -> None:
    image_paths = [str(image.path) for image in images]
    wait_for_image_upload_panel(page)
    input_locator = page.locator("input[type=file]").first
    if callable(input_locator):
        input_locator = input_locator()
    try:
        input_locator.set_input_files(image_paths)
    except Exception as exc:
        raise PublishError(
            "could not set image files. Make sure the Xiaohongshu upload panel is visible "
            "or upload images manually, then rerun with --open-browser only."
        ) from exc
    print(f"- uploaded image files: {len(image_paths)}")


def wait_for_upload_ready(page, expected_count: int) -> None:
    try:
        page.wait_for_function(
            """(expected) => {
                const text = document.body.innerText || '';
                const hasCount = text.includes(`${expected}/18`) || text.includes(`1/${expected}`);
                const hasTitle = Boolean(Array.from(document.querySelectorAll('input'))
                  .find((el) => (el.placeholder || '').includes('标题')));
                const hasEditor = Boolean(Array.from(document.querySelectorAll('[contenteditable="true"], textarea'))
                  .find((el) => el.offsetWidth || el.offsetHeight || el.getClientRects().length));
                return hasCount && hasTitle && hasEditor;
            }""",
            expected_count,
            timeout=45000,
        )
    except Exception as exc:
        raise PublishError(
            f"uploaded files, but composer was not ready for {expected_count} images"
        ) from exc
    print(f"- upload ready: {expected_count} image(s) detected")


def fill_composer(page, title: str, body: str) -> None:
    result = page.evaluate(
        """({title, body}) => {
            const visible = (el) => Boolean(
              el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length)
            );
            const setNativeValue = (el, value) => {
              const proto = Object.getPrototypeOf(el);
              const descriptor = Object.getOwnPropertyDescriptor(proto, 'value');
              if (descriptor && descriptor.set) descriptor.set.call(el, value);
              else el.value = value;
              el.dispatchEvent(new InputEvent('input', {bubbles: true, inputType: 'insertText', data: value}));
              el.dispatchEvent(new Event('change', {bubbles: true}));
            };
            const titleEl = Array.from(document.querySelectorAll('input, textarea, [contenteditable="true"]'))
              .find((el) => visible(el) && /标题|填写标题/.test(
                `${el.getAttribute('placeholder') || ''} ${el.getAttribute('data-placeholder') || ''} ${el.getAttribute('aria-label') || ''}`
              ));
            const editorEl = Array.from(document.querySelectorAll('[contenteditable="true"], textarea'))
              .find((el) => visible(el) && el !== titleEl);
            if (!titleEl) return {ok: false, error: 'title field not found'};
            if (!editorEl) return {ok: false, error: 'body editor not found'};

            titleEl.focus();
            if ('value' in titleEl) setNativeValue(titleEl, title);
            else titleEl.innerText = title;

            editorEl.focus();
            if ('value' in editorEl) {
              setNativeValue(editorEl, body);
            } else {
              editorEl.innerHTML = '';
              const paragraphs = body.split(/\\n{2,}/).flatMap((block) => {
                const lines = block.split('\\n').map((line) => line.trim()).filter(Boolean);
                return lines.length ? lines : [''];
              });
              for (const paragraphText of paragraphs) {
                const p = document.createElement('p');
                p.textContent = paragraphText || '\\u00a0';
                editorEl.appendChild(p);
              }
              editorEl.dispatchEvent(new InputEvent('input', {bubbles: true, inputType: 'insertText', data: body}));
              editorEl.dispatchEvent(new Event('change', {bubbles: true}));
            }
            return {
              ok: true,
              title: 'value' in titleEl ? titleEl.value : titleEl.innerText,
              body: 'value' in editorEl ? editorEl.value : editorEl.innerText
            };
        }""",
        {"title": title, "body": body},
    )
    if not result.get("ok"):
        raise PublishError(result.get("error", "could not fill composer"))
    print("- filled title/body")


def verify_browser_state(page, package: PostPackage, expected_hashtags: Sequence[str]) -> None:
    state = page.evaluate(
        """() => {
            const visible = (el) => Boolean(
              el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length)
            );
            const titleEl = Array.from(document.querySelectorAll('input, textarea, [contenteditable="true"]'))
              .find((el) => visible(el) && /标题|填写标题/.test(
                `${el.getAttribute('placeholder') || ''} ${el.getAttribute('data-placeholder') || ''} ${el.getAttribute('aria-label') || ''}`
              ));
            const editorEl = Array.from(document.querySelectorAll('[contenteditable="true"], textarea'))
              .find((el) => visible(el) && el !== titleEl && ((el.innerText || el.value || '').includes('#') || el.getAttribute('role') === 'textbox'));
            const editorText = editorEl ? ('value' in editorEl ? editorEl.value : editorEl.innerText) : '';
            const topicMarked = Array.from(new Set(
              (editorText.match(/#[^#\\n]*?\\[话题\\]#/g) || [])
                .map((item) => item.replace(/\\[话题\\]#/, '').trim())
            ));
            const previewHashtags = Array.from(new Set(
              Array.from(document.querySelectorAll('*'))
                .map((el) => (el.innerText || '').trim())
                .filter((text) => /^#[\\w\\u4e00-\\u9fff]+$/.test(text))
            ));
            const buttons = Array.from(document.querySelectorAll('button, xhs-publish-btn'))
              .map((el) => ({
                text: (el.innerText || el.textContent || el.getAttribute('text') || '').trim(),
                disabled: Boolean(el.disabled) || el.getAttribute('submit-disabled') === 'true' ||
                  el.getAttribute('disabled') !== null || el.getAttribute('aria-disabled') === 'true'
              }))
              .filter((button) => /发布|Publish|暂存/.test(button.text));
            const pageText = document.body.innerText || '';
            const countMatch = pageText.match(/\\b\\d+\\s*\\/\\s*18\\b/) || pageText.match(/\\b1\\s*\\/\\s*\\d+\\b/);
            return {
              title: titleEl ? ('value' in titleEl ? titleEl.value : titleEl.innerText) : '',
              bodyChars: editorText.length,
              editorText,
              topicMarked,
              previewHashtags,
              buttons,
              imageCountText: countMatch ? countMatch[0].replace(/\\s+/g, '') : ''
            };
        }"""
    )
    print(f"- browser title: {state.get('title', '')}")
    print(f"- browser body chars: {state.get('bodyChars', 0)}")
    print(f"- browser image count: {state.get('imageCountText') or 'unknown'}")
    print(f"- recognized topics: {' '.join(state.get('topicMarked') or []) or '(none)'}")
    suggestions = [
        tag for tag in state.get("previewHashtags", [])
        if tag not in state.get("topicMarked", []) and tag not in expected_hashtags
    ]
    print(f"- suggested/visible extra topics: {' '.join(suggestions) if suggestions else '(none)'}")
    missing = [tag for tag in expected_hashtags if tag not in state.get("topicMarked", [])]
    if missing:
        raise PublishError(f"expected hashtags not recognized as topics: {' '.join(missing)}")
    if package.title and state.get("title") != package.title:
        raise PublishError(f"browser title mismatch: expected {package.title!r}, found {state.get('title')!r}")
    print(f"- publish controls detected: {json.dumps(state.get('buttons', []), ensure_ascii=False)}")


if __name__ == "__main__":
    raise SystemExit(main())
