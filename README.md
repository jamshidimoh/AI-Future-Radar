# AI Future Radar

رادار هوشمند پایش آینده فناوری با محوریت **هوش مصنوعی**. محصول، مهم‌ترین سیگنال‌های AI و فناوری‌های پیشرفته را از پژوهش، صنعت، دانشگاه، مصاحبه، پادکست و اندیشه آینده جمع‌آوری، ارزیابی و به پیام فارسی قابل اتکا برای Telegram تبدیل می‌کند.

## وضعیت محصول

**وضعیت خط مبنای تولیدی:** `CLOSED / PRODUCTION BASELINE` — ۲۰۲۶-۱۱-۰۴. گیت رسمی بسته‌شدن پروژه سه اجرای متوالی موفق را روی اثرانگشت یکسان کد، همراه با شواهد انتشار واقعی تلگرام، عدم تکرار و عبور ۱۶ معیار پذیرش ثبت کرده است. گزارش قابل ممیزی در [docs/PRODUCTION_CLOSURE_STATUS.md](docs/PRODUCTION_CLOSURE_STATUS.md) قرار دارد و [Issue #69](https://github.com/jamshidimoh/AI-Future-Radar/issues/69) بسته شده است.

### تغییرات مهم پس از بسته‌شدن خط مبنا

- [PR #302](https://github.com/jamshidimoh/AI-Future-Radar/pull/302): شاخص‌گذاری و محدودسازی هزینهٔ تشخیص تکرار، بدون حذف کنترل‌های سراسری URL و عنوان.
- [PR #303](https://github.com/jamshidimoh/AI-Future-Radar/pull/303): سقف‌های چرخشی برای تنوع خبرهای پزشکی و ژنتیک.
- [PR #304](https://github.com/jamshidimoh/AI-Future-Radar/pull/304): ادغام خلاصه و چرایی خبر در صورت هم‌پوشانی معنایی.
- [PR #307](https://github.com/jamshidimoh/AI-Future-Radar/pull/307): بازطراحی برنامهٔ آموزشی ۱۳۰ درسی با ساختار علمی و منابع به‌روزشده؛ وضعیت فعلی پیشرفت در `data/education_state.json` نگهداری می‌شود.
- [PR #308](https://github.com/jamshidimoh/AI-Future-Radar/pull/308): گسترش پوشش فلسفهٔ ذهن، آگاهی و فلسفهٔ علم، مشروط به وجود پیوند محتوایی واقعی با AI.
- [PR #309](https://github.com/jamshidimoh/AI-Future-Radar/pull/309): مسیریابی سهمیه‌آگاه برای ارائه‌دهندگان رایگان؛ Gemini و Ollama در مسیر تولید فعال نیستند.
- [PR #310](https://github.com/jamshidimoh/AI-Future-Radar/pull/310): همگام‌سازی کاتالوگ مدل‌های OmniRoute و اصلاح fail-closed؛ اگر کاتالوگ مدل خالی بماند، OmniRoute آماده اعلام نمی‌شود و مسیر fallback حفظ می‌شود. هر هفت گیت CI این PR موفق شدند.

### مرز وضعیت عملیاتی

آخرین snapshot پایدار قابل مشاهده در `data/publication_state.json`، شمارهٔ اجرای ۹۱۴ و People Bootstrap برابر ۳۰/۳۰ را ثبت می‌کند. snapshot سلامت مدل‌ها نیز محدودیت نرخ برای دو مدل رایگان OpenRouter و خطاهای احراز هویت/اعتبار برای بعضی ارائه‌دهندگان را ثبت کرده است.

این snapshot پیش از ادغام PR #310 ذخیره شده است؛ بنابراین سبز بودن CI و موفقیت خط مبنای ۴ نوامبر، به‌تنهایی تحویل واقعی تلگرام پس از تغییر جدید را ثابت نمی‌کند. نسخهٔ فعلی باید با اجرای زندهٔ پس از ادغام، شامل همگام‌سازی مدل، استنتاج JSON و تحویل تأییدشدهٔ تلگرام، دوباره پایش شود. معیارهای کیفیت، شواهد، تنوع مأموریت و عدم انتشار تکراری نباید برای سبز کردن اجرا تضعیف شوند.

## استفاده دیگران

راهنمای کامل اجرای نسخه منتشرشده، تنظیم environment، اجرای Docker، نگهداری state، اتصال Telegram، ارتقا و rollback در `docs/USER_GUIDE.md` قرار دارد.

برای اجرای نمونهٔ شناخته‌شده از tag `v1.0.2` استفاده کنید. برای انتخاب آخرین tag منتشرشده، صفحهٔ [GitHub Releases](https://github.com/jamshidimoh/AI-Future-Radar/releases) را بررسی کنید؛ بسته‌شدن گیت تولیدی به‌تنهایی به معنای انتشار خودکار یک tag جدید نیست.

```bash
docker pull ghcr.io/jamshidimoh/ai-future-radar:v1.0.2
```

سپس container را با یک فایل `.env` و یک دایرکتوری persistent برای `/app/data` اجرا کنید. در صورت عمومی بودن Package، pull از GHCR بدون authentication امکان‌پذیر است.

## انتشار و Packages

بسته توزیعی رسمی پروژه، یک OCI container برای GitHub Container Registry است:

`ghcr.io/jamshidimoh/ai-future-radar`

آخرین GitHub Release ثبت‌شده `v1.0.2` است. Workflow انتشار در `.github/workflows/publish-container.yml` برای ایجاد `v1.1.0` و `latest` تنها پس از موفقیت `Production Closure Gate` تنظیم شده است. Image دارای OCI source metadata، SBOM و provenance است.

راهنمای انتشار در `docs/RELEASE.md` قرار دارد. قالب متغیرهای محیطی نمونه نیز در `.env.example` موجود است.
