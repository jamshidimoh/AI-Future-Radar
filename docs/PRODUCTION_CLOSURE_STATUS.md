# AI Future Radar — Production Closure Status

Status date: 2026-08-31

## Purpose

این سند مرز پایان پروژه را ثابت می‌کند. پروژه فقط وقتی `Production Complete` اعلام می‌شود که همه قراردادهای deterministic و همه شواهد عملیاتی لازم سبز باشند. بعد از آن، تغییرات جدید Maintenance/Evolution محسوب می‌شوند و پروژه را دوباره وارد فاز توسعه نمی‌کنند مگر اینکه یک invariant شکسته شود.

## Closure rule

وضعیت نهایی فقط در صورت تحقق هم‌زمان این سه شرط `CLOSED` است:

1. Deterministic acceptance suite سبز باشد.
2. Production evidence window کامل باشد.
3. هیچ FAIL باز در invariantهای frozen وجود نداشته باشد.

اگر هر سه شرط برقرار نباشند، وضعیت باید `ACCEPTANCE IN PROGRESS` باقی بماند.

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

## Operational evidence required

حداقل سه Production run متوالی روی یک code lineage پذیرفته‌شده باید بدون timeout یا intervention دستی مشاهده شود.

در این پنجره باید هر دو حالت مشاهده شود:

- حداقل یک اجرای دارای candidate معتبر که publication موفق دارد.
- حداقل یک اجرای بدون candidate بالاتر از adaptive baseline که به‌صورت fail-closed صفر خبر منتشر کند.

همچنین باید ثابت شود:

- duplicate Telegram publication رخ نمی‌دهد.
- failure تصویر متن canonical را از بین نمی‌برد.
- candidate خارج از replacement window منتشر نمی‌شود.
- rank هیچ bypassی برای quality baseline ایجاد نمی‌کند.
- پس از failure در transformation/editorial QA، replacement فقط با همان contract انجام می‌شود.
- leader/interview معتبر در صورت وجود و عبور از quality gate قابل انتشار باقی می‌ماند.
- providerهای 429/5xx/timeout/empty-response مسیرهای مستقل انتشار را متوقف نمی‌کنند.
- publication state بعد از run معتبر و فقط بر اساس delivery confirmed است.
- mission portfolio به generic low-signal feed فرو نمی‌ریزد.

## Current evidence snapshot

- Repository is public and the default branch is `main`.
- Latest observed production evidence window: `Run AI Future Radar Bot #171`, `#172`, `#173`, all completed successfully.
- Quality validation for the router-policy correction is green on commit `bdbbdb619366bce479df293a30f795dc34f983a2`.
- The production router has an explicit model-scoped quota policy with provider-family isolation for permanent/authentication failures.
- The repository contains the frozen acceptance contracts, ranking audit, production acceptance tests and real publication baseline.
- A fresh production run on the current `main` lineage is required to validate the stricter closure gate against current runtime evidence.

## Current declaration

`ACCEPTANCE IN PROGRESS`

The project must **not** be called `Production Complete` merely because the repository is deployable or because one scheduled run passed. The final label is reserved for the evidence window above and the deeper evidence checks.

## Project stop boundary

Once the deterministic suite is green and the required production evidence window has been observed with no regression, the project is closed. No further architectural improvement is part of this project. New providers, new sources, ranking experiments, UI changes, model upgrades and optimization ideas become separate maintenance/evolution work.
