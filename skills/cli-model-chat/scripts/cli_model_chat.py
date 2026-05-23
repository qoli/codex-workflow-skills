#!/usr/bin/env python3
"""Small one-to-one chat wrapper for DeepSeek's OpenAI-compatible API."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


PROVIDER_DEEPSEEK = "deepseek"
PROVIDER_CODEX = "codex"
DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-v4-pro"
DEFAULT_MAX_OUTPUT_TOKENS = 384_000
DEFAULT_TEMPERATURE = 1.3
DEFAULT_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
STATE_DIR = Path.home() / ".local" / "state" / "cli-model-chat"


class ChatError(RuntimeError):
    """Raised when the chat API cannot return a usable response."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ask DeepSeek or Codex through a narrow one-to-one CLI chat wrapper.",
    )
    parser.add_argument("prompt", nargs="?", help="Prompt text. Reads stdin when omitted.")
    parser.add_argument(
        "--provider",
        choices=(PROVIDER_DEEPSEEK, PROVIDER_CODEX),
        default=PROVIDER_DEEPSEEK,
        help="Backend to use for this request. Defaults to deepseek.",
    )
    parser.add_argument("--prompt-file", help="Read prompt text from this file.")
    parser.add_argument("--system", help="Optional system message.")
    parser.add_argument("--model", help=f"Provider model id. DeepSeek defaults to DEEPSEEK_MODEL or {DEFAULT_MODEL}.")
    parser.add_argument("--base-url", help=f"API base URL. Defaults to DEEPSEEK_BASE_URL or {DEFAULT_BASE_URL}.")
    parser.add_argument("--api-key-env", default="DEEPSEEK_API_KEY")
    parser.add_argument(
        "--env-file",
        default=str(DEFAULT_ENV_FILE),
        help="Local env file to load before reading credentials. Use 'none' to disable.",
    )
    parser.add_argument(
        "--thinking",
        choices=("enabled", "disabled"),
        default="enabled",
        help="DeepSeek V4 thinking mode. Defaults to enabled.",
    )
    parser.add_argument(
        "--reasoning-effort",
        choices=("high", "max"),
        default="high",
        help="Reasoning effort when thinking mode is enabled.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=DEFAULT_TEMPERATURE,
        help="Sampling temperature for non-thinking mode only. Defaults to 1.3.",
    )
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--session", help="Persist conversation under a local session name.")
    parser.add_argument("--new-session", action="store_true", help="Ignore existing session history.")
    parser.add_argument("--no-save", action="store_true", help="Do not update session history.")
    parser.add_argument("--list-models", action="store_true", help="List available model ids and exit.")
    parser.add_argument("--codex-bin", default=os.environ.get("CODEX_BIN", "codex"))
    parser.add_argument("--codex-model", default=os.environ.get("CODEX_MODEL"))
    parser.add_argument("--codex-profile", default=os.environ.get("CODEX_PROFILE"))
    parser.add_argument(
        "--codex-allow-user-config",
        action="store_true",
        help="Allow Codex to load user config/profiles. Disabled by default for isolation.",
    )
    parser.add_argument("--json", action="store_true", help="Print response metadata as JSON.")
    return parser.parse_args()


def load_env_file(path_text: str) -> None:
    if path_text.lower() == "none":
        return
    path = Path(path_text).expanduser()
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key.removeprefix("export ").strip()
        value = value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


def api_key_from_env(name: str) -> str:
    api_key = os.environ.get(name, "").strip()
    if not api_key:
        raise ChatError(f"Missing API key. Set {name} in the environment.")
    return api_key


def endpoint(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def request_json(
    url: str,
    api_key: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: float,
) -> dict[str, Any]:
    data = None
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise ChatError(f"HTTP {exc.code} from {url}: {body}") from exc
    except urllib.error.URLError as exc:
        raise ChatError(f"Request failed for {url}: {exc.reason}") from exc


def prompt_text(args: argparse.Namespace) -> str:
    if args.prompt_file:
        return Path(args.prompt_file).read_text(encoding="utf-8")
    if args.prompt is not None:
        return args.prompt
    if not sys.stdin.isatty():
        return sys.stdin.read()
    raise ChatError("Provide a prompt argument, --prompt-file, or stdin.")


def safe_session_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", name.strip()).strip(".-")
    if not cleaned:
        raise ChatError("Session name must contain at least one safe character.")
    return cleaned


def session_path(provider: str, name: str) -> Path:
    return STATE_DIR / provider / f"{safe_session_name(name)}.json"


def load_session(provider: str, name: str, *, new_session: bool) -> list[dict[str, str]]:
    path = session_path(provider, name)
    if new_session or not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    messages = data.get("messages", [])
    if not isinstance(messages, list):
        raise ChatError(f"Invalid session file: {path}")
    return messages


def save_session(provider: str, name: str, messages: list[dict[str, str]]) -> None:
    path = session_path(provider, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"provider": provider, "model_default": DEFAULT_MODEL, "messages": messages}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def list_models(args: argparse.Namespace, api_key: str) -> None:
    data = request_json(endpoint(args.base_url, "models"), api_key, timeout=args.timeout)
    for item in data.get("data", []):
        model_id = item.get("id")
        if model_id:
            print(model_id)


def build_messages(args: argparse.Namespace, user_prompt: str) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if args.session:
        messages.extend(load_session(args.provider, args.session, new_session=args.new_session))
    if args.system and not any(message.get("role") == "system" for message in messages):
        messages.insert(0, {"role": "system", "content": args.system})
    messages.append({"role": "user", "content": user_prompt})
    return messages


def chat_deepseek(args: argparse.Namespace, api_key: str) -> dict[str, Any]:
    messages = build_messages(args, prompt_text(args))
    payload: dict[str, Any] = {
        "model": args.model,
        "messages": messages,
        "thinking": {"type": args.thinking},
        "max_tokens": DEFAULT_MAX_OUTPUT_TOKENS,
        "stream": False,
    }
    if args.thinking == "enabled":
        payload["reasoning_effort"] = args.reasoning_effort
    else:
        payload["temperature"] = args.temperature
    data = request_json(
        endpoint(args.base_url, "chat/completions"),
        api_key,
        method="POST",
        payload=payload,
        timeout=args.timeout,
    )
    choices = data.get("choices") or []
    if not choices:
        raise ChatError(f"No choices returned: {json.dumps(data, ensure_ascii=False)}")
    message = choices[0].get("message") or {}
    content = message.get("content")
    reasoning_content = message.get("reasoning_content")
    if not isinstance(content, str):
        raise ChatError(f"No assistant content returned: {json.dumps(data, ensure_ascii=False)}")

    if args.session and not args.no_save:
        messages.append({"role": "assistant", "content": content})
        save_session(args.provider, args.session, messages)

    return {
        "provider": PROVIDER_DEEPSEEK,
        "model": data.get("model", args.model),
        "content": content,
        "reasoning_content": reasoning_content,
        "max_tokens_requested": DEFAULT_MAX_OUTPUT_TOKENS,
        "usage": data.get("usage"),
        "id": data.get("id"),
    }


def prompt_for_codex(args: argparse.Namespace, user_prompt: str) -> str:
    safety = (
        "You are being used as a plain one-to-one chat model. "
        "Do not inspect the filesystem, run shell commands, edit files, open network resources, "
        "or use tools. Answer only from the prompt content provided here."
    )
    if args.session:
        messages = load_session(args.provider, args.session, new_session=args.new_session)
        messages.append({"role": "user", "content": user_prompt})
        chunks = [safety]
        if args.system:
            chunks.append(f"System instruction:\n{args.system}")
        chunks.append("Continue this one-to-one conversation and answer the latest user message.")
        for message in messages:
            chunks.append(f"{message['role'].upper()}:\n{message['content']}")
        return "\n\n".join(chunks)
    if args.system:
        return f"{safety}\n\nSystem instruction:\n{args.system}\n\nUser request:\n{user_prompt}"
    return f"{safety}\n\nUser request:\n{user_prompt}"


def chat_codex(args: argparse.Namespace) -> dict[str, Any]:
    if args.list_models:
        raise ChatError("--list-models is only available for --provider deepseek.")
    if args.codex_profile and not args.codex_allow_user_config:
        raise ChatError("--codex-profile requires --codex-allow-user-config because profiles load user config.")
    user_prompt = prompt_text(args)

    with tempfile.NamedTemporaryFile(prefix="cli-model-chat-codex-", suffix=".txt", delete=False) as tmp:
        output_path = Path(tmp.name)
    try:
        with tempfile.TemporaryDirectory(prefix="cli-model-chat-codex-cwd-") as codex_cwd:
            command = [
                args.codex_bin,
                "exec",
                "--ephemeral",
                "--skip-git-repo-check",
                "--ignore-rules",
                "--sandbox",
                "read-only",
                "--cd",
                codex_cwd,
                "--color",
                "never",
                "--output-last-message",
                str(output_path),
            ]
            if not args.codex_allow_user_config:
                command.append("--ignore-user-config")
            codex_model = args.codex_model or args.model
            if codex_model:
                command.extend(["--model", codex_model])
            if args.codex_profile:
                command.extend(["--profile", args.codex_profile])
            command.append("-")

            completed = subprocess.run(
                command,
                input=prompt_for_codex(args, user_prompt),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=args.timeout,
                check=False,
            )
            content = output_path.read_text(encoding="utf-8").strip() if output_path.exists() else ""
    finally:
        output_path.unlink(missing_ok=True)

    if completed.returncode != 0:
        raise ChatError(f"Codex exited {completed.returncode}: {completed.stderr.strip()}")
    if not content:
        content = completed.stdout.strip()
    if not content:
        raise ChatError("Codex returned no final message.")

    if args.session and not args.no_save:
        messages = load_session(args.provider, args.session, new_session=args.new_session)
        messages.append({"role": "user", "content": user_prompt})
        messages.append({"role": "assistant", "content": content})
        save_session(args.provider, args.session, messages)

    return {
        "provider": PROVIDER_CODEX,
        "model": codex_model,
        "profile": args.codex_profile,
        "isolated": not args.codex_allow_user_config,
        "sandbox": "read-only",
        "content": content,
    }


def main() -> int:
    args = parse_args()
    try:
        load_env_file(args.env_file)
        if args.provider == PROVIDER_DEEPSEEK:
            args.model = args.model or os.environ.get("DEEPSEEK_MODEL", DEFAULT_MODEL)
            args.base_url = args.base_url or os.environ.get("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL)
            api_key = api_key_from_env(args.api_key_env)
            if args.list_models:
                list_models(args, api_key)
                return 0
            result = chat_deepseek(args, api_key)
        elif args.provider == PROVIDER_CODEX:
            result = chat_codex(args)
        else:
            raise ChatError(f"Unsupported provider: {args.provider}")
    except ChatError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["content"].strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
