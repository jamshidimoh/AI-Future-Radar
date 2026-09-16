from src.claim_verification import deterministic_precheck, semantic_verify


def test_numeric_and_model_claims_require_source_support():
    result = deterministic_precheck(
        "GPT-5 یک مدل جدید",
        "این مدل با 95% دقت بهبود یافته است.",
        "نسخه 5 در آزمایش معرفی شد.",
        "GPT-5 در آزمایش معرفی شد اما عددی درباره 95 درصد ارائه نشده است.",
    )
    assert result["risk_flags"]["numeric_claim"] is True
    assert "numeric_mismatch" in result["flags"]
    assert result["risk_flags"]["model_version_claim"] is True


def test_comparison_translation_does_not_create_false_mismatch():
    result = deterministic_precheck(
        "مدل جدید سریع‌تر است",
        "مدل جدید سریع‌تر از نسخه قبلی اجرا شد.",
        "منبع این بهبود را گزارش می‌کند.",
        "The new model is faster than the previous version.",
    )
    assert result["risk_flags"]["comparison_claim"] is True
    assert "unsupported_comparison" not in result["flags"]


def test_semantic_verifier_unavailable_is_not_rejected():
    precheck = deterministic_precheck(
        "GPT-5 بهبود یافت",
        "این مدل 30 درصد سریع‌تر است.",
        "این بهبود کاربردی گزارش شده است.",
        "GPT-5 is 30 percent faster in the reported test.",
    )

    def unavailable(*args, **kwargs):
        return None, None

    result = semantic_verify(
        source_text="GPT-5 is 30 percent faster in the reported test.",
        title="GPT-5 بهبود یافت",
        summary="این مدل 30 درصد سریع‌تر است.",
        why_it_matters="این بهبود کاربردی گزارش شده است.",
        precheck=precheck,
        call_fn=unavailable,
    )
    assert result.status == "UNAVAILABLE"
    assert "verifier_provider_failure" in result.flags


def test_semantic_verifier_accepts_structured_response():
    precheck = deterministic_precheck(
        "GPT-5 بهبود یافت",
        "این مدل 30 درصد سریع‌تر است.",
        "این بهبود در آزمون گزارش شده است.",
        "GPT-5 is 30 percent faster in the reported test.",
    )

    def verifier(*args, **kwargs):
        return (
            '{"status":"VERIFIED","overall_confidence":0.94,'
            '"claims":[{"id":"n1","support":"SUPPORTED","confidence":0.98,"reason_code":null}]}'
        ), "test-provider"

    result = semantic_verify(
        source_text="GPT-5 is 30 percent faster in the reported test.",
        title="GPT-5 بهبود یافت",
        summary="این مدل 30 درصد سریع‌تر است.",
        why_it_matters="این بهبود در آزمون گزارش شده است.",
        precheck=precheck,
        call_fn=verifier,
    )
    assert result.status == "VERIFIED"
    assert result.provider == "test-provider"
    assert result.claims[0]["support"] == "SUPPORTED"
