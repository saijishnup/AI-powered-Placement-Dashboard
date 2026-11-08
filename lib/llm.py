"""The only LLM entry point. One OpenAI-compatible endpoint from .env (the OmniRoute gateway; no local models).
LLM_MODEL is a comma list tried in order: each model gets one retry (error or failed check), then the next."""
import os
import re
from functools import cache
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

THINK_RE = re.compile(r"<think>.*?</think>|^.*?</think>", re.S)
CAPS = {"qa": 600, "overview": 800, "summary": 300, "seed": 3000}
CALLS = []  # (model, prompt_tokens, completion_tokens); tests read this to count calls


def models():
    return [m.strip() for m in os.getenv("LLM_MODEL", "").split(",") if m.strip()]


@cache
def client():
    return OpenAI(base_url=os.getenv("LLM_BASE_URL"), api_key=os.getenv("LLM_API_KEY") or "none",
                  timeout=60, max_retries=0)


def clean(text):
    """Drop think blocks and odd spaces (models emit U+202F before [R#])."""
    text = THINK_RE.sub("", text or "")
    return re.sub("[\u202f\u00a0\u2009]", " ", text).strip()


def chat(messages, kind="qa", model=None):
    """One completion. Returns (text, usage). Raises on failure; caller decides fallback."""
    # "name@low" in LLM_MODEL overrides LLM_REASONING_EFFORT for that model (gpt-oss rejects "none")
    model, _, effort = (model or models()[0]).partition("@")
    effort = effort or os.getenv("LLM_REASONING_EFFORT")  # optional: only sent when set
    resp = client().chat.completions.create(
        model=model, messages=messages, max_tokens=CAPS[kind], temperature=0.9 if kind == "seed" else 0.2,
        **({"reasoning_effort": effort} if effort else {}))
    u = resp.usage
    CALLS.append((model, getattr(u, "prompt_tokens", 0), getattr(u, "completion_tokens", 0)))
    return clean(resp.choices[0].message.content), u


def chat_with_fallback(messages, kind="qa", ok=lambda text: True):
    """Returns (text, model_index). Raises RuntimeError if every model fails."""
    last = None
    for i, model in enumerate(models()):
        for _ in range(2):
            try:
                text, _ = chat(messages, kind, model=model)
                if ok(text):
                    return text, i
                last = ValueError(f"validation failed: {text[:80]!r}")
            except Exception as e:  # network, rate limit, unknown model
                last = e
    raise RuntimeError(f"all LLM providers failed: {str(last)[:200]}")
