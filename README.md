# AI Future Radar

رادار هوشمند پایش آینده فناوری با محوریت **هوش مصنوعی**. محصول، مهم‌ترین سیگنال‌های AI و فناوری‌های پیشرفته را از پژوهش، صنعت، دانشگاه، مصاحبه، پادکست و اندیشه آینده جمع‌آوری، ارزیابی و به پیام فارسی قابل اتکا برای Telegram تبدیل می‌کند.

## وضعیت محصول

**Production hardening / CLOSURE PENDING — 2026-09-06**

پذیرش قبلی در `2026-09-05` با workflow run `33948969943` سبز شده بود، اما اجرای بعدی Production Closure Gate در `2026-09-06` با run `34016810047` به دلیل ناقص بودن شواهد معیار `02_publish_and_fail_closed_zero` متوقف شد. بنابراین برچسب `CLOSED` فعلاً معتبر نیست و تا تولید یک پنجره شواهد جدید و سبز نباید دوباره اعلام شود.

در همین بازنگری، یک نقص واقعی در provenance نیز اصلاح شد: Google News دیگر نمی‌تواند Tier پرس‌وجو را به ناشر ناشناخته منتقل کند؛ Tier مؤثر از هویت ناشر/دامنه تعیین می‌شود و ناشر ناشناخته در Google News حداکثر Tier-3 باقی می‌ماند. تست‌های regression مربوط به این قاعده نیز اضافه شده‌اند.

پروژه اکنون در مرز **Production Hardening** قرار دارد. هیچ Gate برای سبز شدن مصنوعی ضعیف نشده است؛ ابتدا نقص‌های داده، provenance و شواهد اصلاح و سپس Acceptance دوباره اجرا می‌شود.

وضعیت تفصیلی در `docs/PRODUCTION_CLOSURE_STATUS.md` ثبت شده است. مسیر تولید اصلی با GitHub Actions طبق زمان‌بندی یا اجرای دستی فعال است و Push به `main` نباید به‌تنهایی Production را اجرا کند.

## استفاده دیگران

راهنمای کامل اجرای نسخه منتشرشده، تنظیم environment، اجرای Docker، نگهداری state، اتصال Telegram، ارتقا و rollback در `docs/USER_GUIDE.md` قرار دارد.

برای شروع سریع، release مرجع ثبت‌شده فعلی `V1.0.1.On.Publish` است:

```bash
docker pull ghcr.io/jamshidimoh/ai-future-radar:V1.0.1.On.Publish
```

سپس container را با یک فایل `.env` و یک دایرکتوری persistent برای `/app/data` اجرا کنید. در صورت عمومی بودن Package، pull از GHCR بدون authentication امکان‌پذیر است.

## انتشار و Packages

بسته توزیعی رسمی پروژه، یک OCI container برای GitHub Container Registry است:

`ghcr.io/jamshidimoh/ai-future-radar`

آخرین GitHub Release ثبت‌شده `V1.0.1.On.Publish` است. Workflow انتشار در `.github/workflows/publish-container.yml` قرار دارد و tagهای semantic را build، validate و publish می‌کند. Image دارای OCI source metadata، SBOM و provenance است.

راهنمای انتشار در `docs/RELEASE.md` قرار دارد. قالب متغیرهای محیطی نمونه نیز در `.env.example` موجود است.
