# AI Future Radar

رادار هوشمند پایش آینده فناوری با محوریت **هوش مصنوعی**. محصول، مهم‌ترین سیگنال‌های AI و فناوری‌های پیشرفته را از پژوهش، صنعت، دانشگاه، مصاحبه، پادکست و اندیشه آینده جمع‌آوری، ارزیابی و به پیام فارسی قابل اتکا برای Telegram تبدیل می‌کند.

## وضعیت محصول

**وضعیت به‌روزرسانی‌شده: ۲۰۲۶-۱۰-۲۷ — `CLOSURE PENDING`.** اصلاحات کد مربوط به توازن محتوای کارشناسان و بازیابی پوشش حوزه‌های مأموریت در `main` ادغام شده‌اند؛ انتشار پایدار `v1.1.0` هنوز انجام نشده و تا عبور از گیت سه اجرای زندهٔ موفق متوالی، آمادهٔ انتشار محسوب نمی‌شود.

اصلاحات اخیر:
- [PR #269](https://github.com/jamshidimoh/AI-Future-Radar/pull/269): نصب OmniRoute از commit ثابت‌شده، نصب وابستگی‌های لازم برای اسکریپت `prepare` و حفظ مسیر بازگشت محدودشده در صورت شکست.
- [PR #271](https://github.com/jamshidimoh/AI-Future-Radar/pull/271): تشخیص `telegram_required` در NaraRouter به‌عنوان خطای احراز هویت در سطح ارائه‌دهنده؛ NaraRouter به‌صورت پیش‌فرض از auto-pool در OmniRoute کنار گذاشته شده و فقط پس از رفع مانع حساب، با `OMNIROUTE_ENABLE_NARA=1` قابل فعال‌سازی است.
- [PR #272](https://github.com/jamshidimoh/AI-Future-Radar/pull/272): تثبیت قرارداد و تست‌ها برای سبد AI-first با هدف ترجیحی دو خبر AI؛ خبر دوم سهمیهٔ اجباری نیست و همچنان با کیفیت و پوشش Mind/Cognition، آینده‌پژوهی و همگرایی رقابت می‌کند.
- [PR #262](https://github.com/jamshidimoh/AI-Future-Radar/pull/262) توازن AI و سقف محتوای ژنتیک‌محور را اضافه کرد؛ [PR #263](https://github.com/jamshidimoh/AI-Future-Radar/pull/263) Gemini و Ollama را از runtime حذف کرد.
- [PR #279–#282](https://github.com/jamshidimoh/AI-Future-Radar/pulls?q=is%3Apr+is%3Amerged) مسیر نصب OmniRoute، smoke test مبتنی بر JSON و بازیابی timeout را تقویت کردند؛ [PR #283](https://github.com/jamshidimoh/AI-Future-Radar/pull/283) محتوای سرگرمی بازی را از مأموریت رادار خارج کرد.
- [PR #284](https://github.com/jamshidimoh/AI-Future-Radar/pull/284) فهرست کشف ۵۱ متخصص را از baseline بوت‌استرپ ۳۰ نفره جدا می‌کند، برای هر متخصص سه خانوادهٔ جست‌وجو می‌سازد، تا دو صدای خبره از افراد متمایز را انتخاب می‌کند و سقف یک خبر ژنتیک‌محور و یک خبر پزشکی‌محور را در مرز تحویل اعمال می‌کند.
- [PR #285](https://github.com/jamshidimoh/AI-Future-Radar/pull/285) بازیابی را بر اساس حوزه‌های متمایز محاسبه می‌کند، پس از رد کیفیت یک نامزد تلاش جایگزین را نگه می‌دارد و اجازه نمی‌دهد خروجی خلاصه‌ساز طبقه‌بندی سیستمی خبر را تغییر دهد. آزمون‌های پذیرش و رگرسیون این اصلاح موفق بوده‌اند.

نسخهٔ PR #272 با **۹۹۷ تست موفق** و هر هفت گیت قطعی (Test Radar Quality، Production Quality Gate، Final Production Acceptance، Signal Engine CI، TypeSafe، Graphify و P1 Audit) بررسی شد؛ سپس در [commit `75c7ad2`](https://github.com/jamshidimoh/AI-Future-Radar/commit/75c7ad2aac13801ff9af39085fb7143f9861825e) ادغام شد.

در اجرای زندهٔ پیش از اصلاح پوشش، تلاش‌های اخیر (`#1544` تا `#1546`) به‌ترتیب به‌دلیل صفر تحویل از سبد غیرخالی، ناسازگاری حسابداری Tier-0 و ناهماهنگی پوشش حوزه‌های مأموریت در گیت پذیرش متوقف شدند. PR #285 خطای بازیابی را اصلاح کرده است؛ هر اجرای آغازشده پیش از ادغام این اصلاح، شاهد معتبر برای تأیید آن محسوب نمی‌شود. بسته‌شدن تولیدی همچنان نیازمند سه اجرای موفق متوالی روی اثرانگشت کد یکسان و تحویل تأییدشده است.

مانع بیرونی NaraRouter نیز روشن است: پاسخ `telegram_required` مستلزم عضویت در گروه/کانال اعلام‌شده و اتصال مجدد حساب در تنظیمات NaraRouter است. کد نمی‌تواند این اقدام حسابی را به‌جای مالک حساب انجام دهد؛ تا آن زمان سرویس از auto-pool کنار گذاشته می‌شود. وضعیت سلامت ذخیره‌شده اکنون این مشکل را به‌عنوان `auth` در سطح ارائه‌دهنده ثبت می‌کند.

**بسته‌شدن رسمی انجام نشده است.** [Issue #69](https://github.com/jamshidimoh/AI-Future-Radar/issues/69) باز می‌ماند تا سه اجرای تولیدی متوالی روی یک اثرانگشت کد، تحویل Telegram و پوشش مأموریت را اثبات کنند؛ سبز بودن CI یا صرف ادغام PR برای اعلام Production-ready کافی نیست.

## استفاده دیگران

راهنمای کامل اجرای نسخه منتشرشده، تنظیم environment، اجرای Docker، نگهداری state، اتصال Telegram، ارتقا و rollback در `docs/USER_GUIDE.md` قرار دارد.

برای شروع سریع، آخرین release ثبت‌شده `v1.0.2` است. نسخهٔ `v1.1.0` تا زمان موفقیت گیت بسته‌شدن تولیدی منتشرشده محسوب نمی‌شود:

```bash
docker pull ghcr.io/jamshidimoh/ai-future-radar:v1.0.2
```

سپس container را با یک فایل `.env` و یک دایرکتوری persistent برای `/app/data` اجرا کنید. در صورت عمومی بودن Package، pull از GHCR بدون authentication امکان‌پذیر است.

## انتشار و Packages

بسته توزیعی رسمی پروژه، یک OCI container برای GitHub Container Registry است:

`ghcr.io/jamshidimoh/ai-future-radar`

آخرین GitHub Release ثبت‌شده `v1.0.2` است. Workflow انتشار در `.github/workflows/publish-container.yml` برای ایجاد `v1.1.0` و `latest` تنها پس از موفقیت `Production Closure Gate` تنظیم شده است. Image دارای OCI source metadata، SBOM و provenance است.

راهنمای انتشار در `docs/RELEASE.md` قرار دارد. قالب متغیرهای محیطی نمونه نیز در `.env.example` موجود است.
