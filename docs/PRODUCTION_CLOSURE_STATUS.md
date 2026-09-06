# AI Future Radar — Production Closure Status

Status date: 2026-09-06

## Purpose

این سند مرز پایان پروژه را ثابت می‌کند. پروژه فقط وقتی `Production Complete` اعلام می‌شود که همه قراردادهای deterministic و همه شواهد عملیاتی لازم سبز باشند.

## Current status

**وضعیت فعلی: `CLOSURE PENDING`**

پذیرش قبلی در تاریخ 2026-09-05 با workflow run `33948969943` سبز شده بود، اما اجرای بعدی Production Closure Gate در تاریخ 2026-09-06 با workflow run `34016810047` به علت unresolved بودن evidence معیار `02_publish_and_fail_closed_zero` متوقف شد. بنابراین closure قبلی باید به‌عنوان یک پذیرش تاریخی ثبت شود، نه وضعیت جاری محصول.

## Closure rule

وضعیت نهایی فقط در صورت تحقق هم‌زمان این سه شرط `CLOSED` است:

1. Deterministic acceptance suite سبز باشد.
2. Production evidence window کامل باشد.
3. هیچ FAIL باز در invariantهای frozen وجود نداشته باشد.

تا زمانی که Closure Gate جدید هر سه شرط را تأیید نکرده است، سند نباید `CLOSED` اعلام کند.

## Frozen deterministic invariants

- یک orchestration path اصلی برای Production وجود دارد.
- selection از ranked selector رسمی عبور می‌کند.
- normal publication capacity برابر 3 است و candidate window آن را افزایش نمی‌دهد.
- `normal_period_rank` پیوسته و بدون bypass است.
- adaptive baseline برای همه normal rankها اعمال می‌شود، از جمله `normal_rank=1`.
- community/aggregator در normal portfolio وارد نمی‌شود.
- source diversity و mission portfolio محدودیت‌های خود را حفظ می‌کنند.
- leader/interview protection فقط routing priority است و quality/evidence gate را دور نمی‌زند.
- duplicate publication و cross-language duplicate باید مسدود بمانند.
- publication state فقط پس از confirmed delivery جلو می‌رود.
- education stream مستقل است و failure آن نباید news orchestration را دوباره اجرا کند.
- language, editorial quality, evidence و terminology gates برای publication الزامی‌اند.
- provenance authority باید مستقل از discovery query tier باشد؛ ناشر ناشناخته نباید با Tier پرس‌وجو ارتقا یابد.

## Remediation completed before re-acceptance

یک نقص provenance در Google News اصلاح شد. در ingestion، `source_tier` دیگر مستقیماً از `q["tier"]` گرفته نمی‌شود. هویت ناشر و دامنه برای تعیین Tier مؤثر بررسی می‌شود؛ ناشر ناشناخته در Google News Tier-3 باقی می‌ماند و Tier پرس‌وجو فقط به‌عنوان `discovery_query_tier` حفظ می‌شود. برای این قرارداد، regression test نیز اضافه شده است.

## Historical operational evidence

پنجره‌ای که در پذیرش قبلی با موفقیت بررسی شده بود:

- Production workflow #329 با head `5f3775c1` — success.
- Production workflow #328 با head `fca900b7` — success.
- Production workflow #327 با head `9ac374ac` — success.

Closure Gate قبلی هر ۱۱ معیار را `PASS` ثبت کرده بود. این شواهد همچنان به‌عنوان سابقه معتبرند، اما برای اعلام closure جاری کافی نیستند؛ چون اجرای جدید Gate در 2026-09-06 معیار 02 را حل‌نشده گزارش کرده است.

## Current acceptance boundary

تا تولید یک پنجره شواهد جدید و سبز:

- `CLOSED` اعلام نشود.
- Gate یا تست‌ها برای حذف blocker تضعیف نشوند.
- provenance/authority regression حفظ شود.
- هر انتشار جدید همچنان fail-closed و evidence-driven باقی بماند.

## Next closure condition

پس از merge اصلاحات، باید Acceptance دوباره اجرا شود و فقط در صورت ثبت شواهد کامل برای publish و zero-publish/fail-closed، همراه با سه اجرای متوالی موفق و بدون invariant failure، وضعیت به `CLOSED` برگردد.

<!-- closure-validation-trigger: PENDING 2026-09-06 -->
