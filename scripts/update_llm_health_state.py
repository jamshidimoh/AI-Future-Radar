"""Persist safe, bounded LLM failure state observed during a production run."""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.llm_health_state_merge import prune_removed_provider_health_records
from src.state_io import load_json_state

STATE_PATH = ROOT / "data" / "llm_health.json"

MODEL_COOLDOWN = {
    "quota": 3600.0,
    "rate_limit": 3600.0,
    "auth": 86400.0,
    "model": 21600.0,
    "invalid_response": 3600.0,
}
# Only authentication failures are inherently provider-wide. Quota scope is
# persisted from the routing decision's explicit [Quota Cooldown] record:
# Groq limits are model-scoped, while OpenRouter's free daily cap is key-scoped.
PROVIDER_COOLDOWN = {
    "auth": 86400.0,
}
KIRAAI_WALLET_PROVIDER_COOLDOWN = 86400.0

FAIL_RE = re.compile(
    r"\[(?:LiteLLM Router|Light Router|Production Circuit)\]\s+"
    r"failed=(?P<deployment>\S+)(?:\s+.*)?$",
)
PROVIDER_FAIL_RE = re.compile(
    r"Provider(?:\s+quota)?\s+attempt\s+failed\s+"
    r"provider=(?P<provider>\S+)\s+model=(?P<model>\S+)\s+"
    r"exception=(?P<message>.*)$",
    re.IGNORECASE,
)
SUCCESS_RE = re.compile(
    r"\[(?:LiteLLM Router|Light Router|Production Circuit)\]\s+"
    r"success=(?P<deployment>\S+)"
)
KIRAAI_WALLET_RE = re.compile(
    r"insufficient.*(?:vnd|wallet|balance)|wallet.*balance|vnd.*balance",
    re.IGNORECASE,
)
QUOTA_COOLDOWN_RE = re.compile(
    r"\[Quota Cooldown\]\s+scope=(?P<scope>provider|model)\s+"
    r"target=(?P<target>\S+)\s+disabled_until=(?P<until>[0-9]+(?:\.[0-9]+)?)"
    r"(?:\s+delay_seconds=[0-9.]+)?\s+window=(?P<window>minute|daily)(?:\s+.*)?$",
)

_PROVIDER_CANONICAL = {
    "groq": "Groq",
    "nararouter": "NaraRouter",
    "openrouter": "OpenRouter",
    "kiraai": "KiraAI",
    "huggingface": "HuggingFace",
    "cloudflare-ai": "Cloudflare Workers AI",
}


def family(deployment: str) -> str:
    return deployment.split(":", 1)[0].strip().casefold()


def canonical_deployment(provider: str, model: str) -> str:
    prefix = str(provider).strip().casefold()
    model_text = str(model).strip()
    if model_text.casefold().startswith(f"{prefix}:"):
        model_text = model_text.split(":", 1)[1]
    return f"{prefix}:{model_text}"


def normalize_state_keys(section: dict) -> dict:
    """Migrate legacy case-sensitive deployment keys to the runtime canonical form."""
    result = {}
    for key, row in (section or {}).items():
        if not isinstance(row, dict):
            continue
        normalized = str(key).strip().casefold()
        existing = result.get(normalized)
        if not isinstance(existing, dict):
            result[normalized] = dict(row)
            continue
        try:
            existing["failures"] = max(int(existing.get("failures", 0) or 0), int(row.get("failures", 0) or 0))
            existing["disabled_until"] = max(float(existing.get("disabled_until", 0) or 0), float(row.get("disabled_until", 0) or 0))
            existing["last_success"] = max(float(existing.get("last_success", 0) or 0), float(row.get("last_success", 0) or 0))
        except (TypeError, ValueError):
            pass
        if not existing.get("last_error") and row.get("last_error"):
            existing["last_error"] = row.get("last_error")
    return result


def is_kira_wallet_only(deployment: str, message: str) -> bool:
    return family(deployment) == "kiraai" and bool(KIRAAI_WALLET_RE.search(str(message or "")))


def is_provider_scoped_failure(deployment: str, failure_kind: str, wallet_only: bool = False) -> bool:
    """Return whether a failure blocks the whole provider/account, not one model.

    OpenRouter's free daily allowance and account_limit responses are shared
    across all :free model variants on the API key. Groq limits are per model,
    so Groq quota exhaustion must never disable sibling models.
    """
    if wallet_only or failure_kind in PROVIDER_COOLDOWN:
        return True
    return (
        (family(deployment) == "openrouter" and failure_kind == "quota")
        or (family(deployment) == "cloudflare-ai" and failure_kind in {"quota", "rate_limit"})
    )


def classify(message: str) -> str:
    text = str(message or "").lower()
    # Empty/incomplete successful responses indicate that a deployment is not
    # usable for this structured editorial workload; persist a model cooldown.
    if re.search(r"response has no content|content not found|no choices|empty response", text):
        return "invalid_response"
    # Account gates and wallet exhaustion are never retryable.
    if re.search(r"telegram_required|join the required telegram|relink at /settings", text):
        return "auth"
    if "cloudflare workers ai" in text and re.search(r"\b403\b", text):
        return "auth"
    if re.search(r"\b401\b|unauthorized|unauthenticated|invalid.*(?:api|credential|key|token)|authentication", text):
        return "auth"
    # Daily/account ceilings are classified before generic 429 so they retain
    # their correct day-long reset window.
    if re.search(
        r"\b402\b|account_limit|payment required|account.*(?:limit|quota)|"
        r"monthly.*(?:credit|quota)|daily.*(?:limit|quota)|free-models-per-day|"
        r"\bTPD\b|tokens?\s+per\s+day|requests?\s+per\s+day|"
        r"depleted|insufficient.*(?:credit|balance)",
        text,
    ):
        return "quota"
    if re.search(
        r"\b429\b|rate.?limit|too many requests|resource_exhausted|"
        r"upstream_provider_shared_pool|free-models-per-minute|tokens?\s+per\s+minute",
        text,
    ):
        return "rate_limit"
    if re.search(r"\b(?:403|404)\b|model.*(?:blocked|disabled|not found|unavailable)|not found|permission", text):
        return "model"
    return "transient"

def load() -> dict:
    value = load_json_state(STATE_PATH, {}, label="LLM health state")
    return value if isinstance(value, dict) else {}


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


def _iter_events(lines: list[str]):
    """Yield ordered (deployment, event_kind, failure_kind, wallet_only) events."""
    for line in lines:
        success = SUCCESS_RE.search(line)
        if success:
            raw_deployment = success.group("deployment")
            deployment = canonical_deployment(family(raw_deployment), raw_deployment)
            yield deployment, "success", "", False
            continue

        failure = FAIL_RE.search(line)
        if failure:
            raw_deployment = failure.group("deployment")
            deployment = canonical_deployment(family(raw_deployment), raw_deployment)
            yield deployment, "failure", classify(line), is_kira_wallet_only(deployment, line)
            continue

        provider_failure = PROVIDER_FAIL_RE.search(line)
        if provider_failure:
            provider = provider_failure.group("provider").strip()
            model = provider_failure.group("model").strip()
            deployment = canonical_deployment(provider, model)
            message = provider_failure.group("message").strip()
            yield deployment, "failure", classify(message), is_kira_wallet_only(deployment, message)



def clear_successful_health_records(state: dict, lines: list[str]) -> dict:
    """Reapply ordered model/provider success and quota events after state merge."""
    last_model_event: dict[str, str] = {}
    last_provider_event: dict[str, str] = {}

    # Process every line in source order. A later quota event must survive an
    # earlier successful request, while a later successful probe may clear a
    # short-window rate-limit cooldown after its reset.
    for line in lines:
        for deployment, event_kind, failure_kind, wallet_only in _iter_events([line]):
            normalized = deployment.strip().casefold()
            provider = family(deployment)
            last_model_event[normalized] = event_kind
            if event_kind == "success":
                last_provider_event[provider] = "success"
            elif is_provider_scoped_failure(deployment, failure_kind, wallet_only):
                last_provider_event[provider] = "failure"

        match = QUOTA_COOLDOWN_RE.search(line)
        if match:
            target = match.group("target").strip().casefold()
            if match.group("scope") == "provider":
                last_provider_event[target] = "failure"
            else:
                last_model_event[target] = "failure"

    result = dict(state) if isinstance(state, dict) else {}
    models = normalize_state_keys(result.get("models", {}) if isinstance(result.get("models"), dict) else {})
    providers = normalize_state_keys(result.get("providers", {}) if isinstance(result.get("providers"), dict) else {})
    for deployment, event_kind in last_model_event.items():
        if event_kind == "success":
            models.pop(deployment, None)
    for provider, event_kind in last_provider_event.items():
        if event_kind == "success":
            providers.pop(provider, None)
    result["models"] = models
    result["providers"] = providers
    return prune_removed_provider_health_records(result)

def main() -> int:
    log_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "run.log"
    if not log_path.exists():
        print(f"[LLM Health Persistence] no_log=1 path={log_path}")
        return 0

    state = prune_removed_provider_health_records(load())
    now = time.time()
    models = normalize_state_keys(prune(state.get("models", {}) if isinstance(state.get("models"), dict) else {}, now))
    providers = normalize_state_keys(prune(state.get("providers", {}) if isinstance(state.get("providers"), dict) else {}, now))
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    events = list(_iter_events(lines))
    observed_failures = [event for event in events if event[1] == "failure"]
    quota_cooldowns: dict[tuple[str, str], tuple[float, str]] = {}
    for line in lines:
        match = QUOTA_COOLDOWN_RE.search(line)
        if not match:
            continue
        try:
            quota_cooldowns[(match.group("scope"), match.group("target").casefold())] = (
                float(match.group("until")),
                match.group("window"),
            )
        except (TypeError, ValueError):
            continue

    last_event: dict[str, tuple[str, str, bool]] = {}
    for deployment, event_kind, failure_kind, wallet_only in events:
        last_event[deployment] = (event_kind, failure_kind, wallet_only)

    for deployment, (event_kind, _, _) in last_event.items():
        if event_kind == "success":
            models.pop(deployment, None)

    for deployment, (event_kind, kind, kira_wallet_only) in last_event.items():
        if event_kind != "failure":
            continue
        model_seconds = MODEL_COOLDOWN.get(kind)
        if model_seconds:
            models[deployment] = {
                "failures": int(models.get(deployment, {}).get("failures", 0) or 0) + 1,
                "disabled_until": round(now + model_seconds, 3),
                "last_error": kind,
                "last_success": 0,
            }
        provider = family(deployment)
        if kira_wallet_only:
            old = providers.get(provider, {})
            providers[provider] = {
                "failures": int(old.get("failures", 0) or 0) + 1,
                "disabled_until": round(now + KIRAAI_WALLET_PROVIDER_COOLDOWN, 3),
                "last_error": "wallet",
            }
        elif kind in PROVIDER_COOLDOWN or (provider == "openrouter" and kind == "quota"):
            # Explicit [Quota Cooldown] records below replace this conservative
            # fallback with the exact provider reset instant when present.
            fallback_seconds = PROVIDER_COOLDOWN.get(kind, 21600.0)
            old = providers.get(provider, {})
            providers[provider] = {
                "failures": int(old.get("failures", 0) or 0) + 1,
                "disabled_until": round(now + fallback_seconds, 3),
                "last_error": kind,
            }

    # Clear provider-level cooldown only when the last provider-scoped event in
    # this run is a success. Model-specific failures remain independently tracked.
    last_provider_event: dict[str, str] = {}
    for deployment, event_kind, failure_kind, wallet_only in events:
        provider = family(deployment)
        if event_kind == "success":
            last_provider_event[provider] = "success"
        elif is_provider_scoped_failure(deployment, failure_kind, wallet_only):
            last_provider_event[provider] = "failure"
    for provider, event_kind in last_provider_event.items():
        if event_kind == "success":
            providers.pop(provider, None)

    # Apply provider/model reset instants emitted by the live router. These
    # exact reset times supersede generic cooldown defaults so requests resume
    # when the free quota replenishes, not on an arbitrary fixed timer.
    for ( (scope, target), (disabled_until, window) ) in quota_cooldowns.items():
        if disabled_until <= now:
            continue
        if scope == "model":
            row = models.setdefault(target, {"failures": 1, "last_success": 0})
            row["disabled_until"] = round(disabled_until, 3)
            row["last_error"] = "rate_limit" if window == "minute" else "quota"
        else:
            row = providers.setdefault(target, {"failures": 1})
            row["disabled_until"] = round(disabled_until, 3)
            row["last_error"] = "rate_limit" if window == "minute" else "quota"


    state["models"] = models
    state["providers"] = providers
    state["telemetry"] = {
        "observed_failures": len(observed_failures),
        "observed_events": len(events),
        "updated_at": now,
    }
    state["updated_at"] = now
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"[LLM Health Persistence] failures={len(observed_failures)} "
        f"successes={sum(1 for e in events if e[1] == 'success')} "
        f"models={len(models)} providers={len(providers)}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
