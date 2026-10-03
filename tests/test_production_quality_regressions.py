from src.claim_verification import hard_publication_flags
from src.editorial_quality_policy import persian_editorial_naturalness_ok
from src.unified_editorial_selection import candidate_score


def test_special_lane_score_has_precedence():
    item = {
        "_portfolio_selection_score": 74.0,
        "final_editorial_score": 55.0,
        "editorial_score": 60.0,
    }
    assert candidate_score(item) == 74.0


def test_hard_claim_flags_are_blocking_but_provider_failure_is_not():
    flags = hard_publication_flags(
        {
            "unsupported_named_entity",
            "causal_overreach",
            "verifier_provider_failure",
        }
    )
    assert flags == {"unsupported_named_entity", "causal_overreach"}
    assert "verifier_provider_failure" not in flags


def test_observed_persian_orthography_regressions_are_rejected():
    assert not persian_editorial_naturalness_ok(
        "شبکههای عصبی",
        "این شبکهها دادههای تصویربرداری را تحلیل میکند.",
        "این روش میتواند دقت ارزیابی را افزایش دهد و محدودیت آن در کیفیت دادههاست.",
    )


def test_normal_persian_with_zwnj_remains_valid():
    assert persian_editorial_naturalness_ok(
        "شبکه‌های عصبی در تصویربرداری پزشکی",
        "این روش داده‌های تصویربرداری را با یک مدل Transformer تحلیل می‌کند و نتیجه پژوهش را روی چند نمونه ارزیابی می‌کند.",
        "اهمیت آن در این است که بهبود دقت می‌تواند ارزیابی بالینی را دقیق‌تر کند، هرچند کیفیت داده و اعتبارسنجی مستقل همچنان محدودیت اصلی است.",
    )
