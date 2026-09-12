"""Persist safe, bounded LLM failure state observed during a production run."""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "data" / "llm_health.json"

MODEL_COOLDOWN = {
    "quota": 3600.0,
    "rate_limit": 3600.0,
    "auth": 86400.0,
    "model": 21600.0,
}
PROVIDER_COOLDOWN = {
    "quota": 21600.0,
    "auth": 86400.0,
}
# A zero-wallet KiraAI account cannot recover within the next run without a
# balance change, so treat wallet exhaustion as provider-scoped for 24 hours.
KIRAAI_WALLET_PROVIDER_COOLDOWN = 86400.0

FAIL_RE = re.compile(
    r"\[(?:LiteLLM Router|Production Circuit)\]\s+"
    r"failed=(?P<deployment>\S+)(?:\s+reason=\S+)?(?:\s+scope=\S+:)?\s*(?P<message>.*)$"
)
SUCCESS_RE = re.compile(
    r"\[(?:LiteLLM Router|Production Circuit)\]\s+"
    r"success=(?P<deployment>\S+)"
)
KIRAAI_WALLET_RE = re.compile(
    r"insufficient.*(?:vnd|wallet|balance)|wallet.*balance|vnd.*balance",
    re.IGNORECASE,
)


def family(deployment: str) -> str:
    return deployment.split(":", 1)[0].strip().casefold()


def is_kira_wallet_only(deployment: str, message: str) -> bool:
    return family(deployment) == "kiraai" and bool(KIRAAI_WALLET_RE.search(str(message or "")))


def classify(message: str) -> str:
    text = str(message or "").lower()
    if re.search(r"\b401\b|unauthorized|unauthenticated|invalid.*(?:api|credential|key|token)|authentication", text):
        return "auth"
    if re.search(r"\b402\b|account_limit|payment required|account.*(?:limit|quota)|monthly.*(?:credit|quota)|daily.*(?:limit|quota)|depleted|insufficient.*(?:credit|balance)", text):
        return "quota"
    if re.search(r"\b429\b|rate.?limit|too many requests|resource_exhausted|upstream_provider_shared_pool", text):
        return "rate_limit"
    if re.search(r"\b(?:403|404)\b|model.*(?:blocked|disabled|not found|unavailable)|not found|permission", text):
        return "model"
    return "transient"


def load() -> dict:
    try:
        value = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def prune(section: dict, now: float) -> dict:
    out = {}
    for key, row in section.items():
        if not isinstance(row, dict):
            continue
        try:
            until = float(row.get("disabled_until", 0) or 0)
        except (TypeError, ValueError):
            continue
        if until > now:
            out[str(key)] = row
    return out


def main() -> int:
    log_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "run.log"
    if not log_path.exists():
        print(f"[LLM Health Persistence] no_log=1 path={log_path}")
        return 0

    state = load()
    now = time.time()
    models = prune(state.get("models", {}) if isinstance(state.get("models"), dict) else {}, now)
    providers = prune(state.get("providers", {}) if isinstance(state.get("providers"), dict) else {}, now)
    successes: set[str] = set()
    failures: list[tuple[str, str, str, bool]] = []

    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        success = SUCCESS_RE.search(line)
        if success:
            successes.add(success.group("deployment"))
            continue
        failure = FAIL_RE.search(line)
        if failure:
            deployment = failure.group("deployment")
            message = failure.group("message").strip()
            failures.append((deployment, family(deployment), classify(message), is_kira_wallet_only(deployment, message)))

    for deployment in successes:
        models.pop(deployment, None)
        providers.pop(family(deployment), None)

    for deployment, provider, kind, kira_wallet_only in failures:
        if deployment in successes:
            continue
        model_seconds = MODEL_COOLDOWN.get(kind)
        if model_seconds:
            models[deployment] = {
                "failures": int(models.get(deployment, {}).get("failures", 0) or 0) + 1,
                "disabled_until": round(now + model_seconds, 3),
                "last_error": kind,
                "last_success": 0,
            }
        if kira_wallet_only:
            old = providers.get(provider, {})
            providers[provider] = {
                "failures": int(old.get("failures", 0) or 0) + 1,
                "disabled_until": round(now + KIRAAI_WALLET_PROVIDER_COOLDOWN, 3),
                "last_error": "wallet_quota",
                "last_success": 0,
            }
            continue
        provider_seconds = PROVIDER_COOLDOWN.get(kind)
        if provider_seconds and kind in {"auth", "quota"}:
            old = providers.get(provider, {})
            providers[provider] = {
                "failures": int(old.get("failures", 0) or 0) + 1,
                "disabled_until": round(now + provider_seconds, 3),
                "last_error": kind,
                "last_success": 0,
            }

    payload = {
        "version": 1,
        "updated_at": round(now, 3),
        "models": models,
        "providers": providers,
    }
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(STATE_PATH.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(STATE_PATH)
    print(f"[LLM Health Persistence] failures={len(failures)} successes={len(successes)} models={len(models)} providers={len(providers)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
