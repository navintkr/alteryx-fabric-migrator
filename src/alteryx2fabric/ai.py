"""LLM provider abstraction for a2f.

Two providers:
- "github"    — GitHub Models inference API (uses GITHUB_TOKEN or `gh auth token`).
                OpenAI-compatible endpoint at https://models.github.ai/inference.
- "anthropic" — Anthropic Messages API (uses ANTHROPIC_API_KEY).

Default model targets Claude Opus 4-class; override per command with --model.
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass

import requests

GITHUB_BASE = "https://models.github.ai/inference"
ANTHROPIC_BASE = "https://api.anthropic.com/v1"

DEFAULT_MODELS = {
    "github": "anthropic/claude-opus-4",
    "anthropic": "claude-opus-4-20250514",
}


@dataclass
class LLMClient:
    provider: str = "github"
    model: str | None = None
    timeout: int = 600

    def __post_init__(self) -> None:
        if self.provider not in DEFAULT_MODELS:
            raise ValueError(f"unknown provider: {self.provider}")
        if not self.model:
            self.model = DEFAULT_MODELS[self.provider]

    def _github_token(self) -> str:
        tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if tok:
            return tok
        try:
            tok = subprocess.check_output(
                ["gh", "auth", "token"], text=True, stderr=subprocess.STDOUT
            ).strip()
            if tok:
                return tok
        except (OSError, subprocess.SubprocessError):
            tok = ""
        raise RuntimeError(
            "No GitHub token found. Set GITHUB_TOKEN or run `gh auth login`."
        )

    def _anthropic_key(self) -> str:
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY not set.")
        return key

    def chat(self, system: str, user: str, *, max_tokens: int = 4096) -> str:
        if self.provider == "github":
            return self._chat_github(system, user, max_tokens=max_tokens)
        return self._chat_anthropic(system, user, max_tokens=max_tokens)

    def _chat_github(self, system: str, user: str, *, max_tokens: int) -> str:
        url = f"{GITHUB_BASE}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._github_token()}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        r = requests.post(url, headers=headers, json=body, timeout=self.timeout)
        if r.status_code >= 400:
            raise RuntimeError(f"GitHub Models {r.status_code}: {r.text[:500]}")
        data = r.json()
        return data["choices"][0]["message"]["content"]

    def _chat_anthropic(self, system: str, user: str, *, max_tokens: int) -> str:
        url = f"{ANTHROPIC_BASE}/messages"
        headers = {
            "x-api-key": self._anthropic_key(),
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        r = requests.post(url, headers=headers, json=body, timeout=self.timeout)
        if r.status_code >= 400:
            raise RuntimeError(f"Anthropic {r.status_code}: {r.text[:500]}")
        data = r.json()
        # Anthropic returns content as a list of blocks
        return "".join(b.get("text", "") for b in data.get("content", []))
