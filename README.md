# AI Future Radar

رادار هوشمند پایش آینده فناوری با محوریت **هوش مصنوعی**. محصول، مهم‌ترین سیگنال‌های AI و فناوری‌های پیشرفته را از پژوهش، صنعت، دانشگاه، مصاحبه، پادکست و اندیشه آینده جمع‌آوری، ارزیابی و به پیام فارسی قابل اتکا برای Telegram تبدیل می‌کند.

## وضعیت محصول

**مرحله فعلی: اصلاحات کد ادغام شده؛ اعتبارسنجی تولید نسخهٔ نهایی در حال انجام — ۱۵ اکتبر ۲۰۲۶**

اصلاحات پذیرش تولید در [PR شمارهٔ ۲۲۹](https://github.com/jamshidimoh/AI-Future-Radar/pull/229) با موفقیت بررسی و در شاخهٔ `main` ادغام شده‌اند. commit ادغام: [`6f93c82a7211`](https://github.com/jamshidimoh/AI-Future-Radar/commit/6f93c82a7211af1b8bd686c9fb6466dbd629d565).

گیت‌های پیش از ادغام روی نسخهٔ اصلاح‌شده سبز شدند: [Test Radar Quality](https://github.com/jamshidimoh/AI-Future-Radar/actions/runs/38711548964)، [Production Quality Gate](https://github.com/jamshidimoh/AI-Future-Radar/actions/runs/38711549214)، [Final Production Acceptance](https://github.com/jamshidimoh/AI-Future-Radar/actions/runs/38711549281)، به‌علاوهٔ Signal Engine، TypeSafe، P1 Audit و Graphify.

اصلاحات اعمال‌شده:
- پذیرش پوشش مأموریتی بین «نبود سیگنال پس از کشف» و «وجود گزینه‌ای که در پردازش، ترجمه، کنترل کیفیت یا دسترسی به مدل شکست خورده» تمایز می‌گذارد. شکست پردازش دیگر به‌عنوان نبود گزینه پذیرفته نمی‌شود.
- کنترل طبیعی‌بودن فارسی علت ردشدن را گزارش می‌کند و آن را به تلاش محدود بازنویسی می‌دهد؛ کنترل شواهد، هم‌ترازی ادعاها، ارتباط موضوعی و حد کیفیت تضعیف نشده‌اند.
- مسیرهای اضطراری مدل هم سلامت پایدارشدهٔ ارائه‌دهنده و مدارشکن حافظه‌ای را رعایت می‌کنند تا خطاهای احراز هویت بارها برای گزینه‌های بعدی تکرار نشوند.

اجرای تولید [شمارهٔ ۱۴۴۲](https://github.com/jamshidimoh/AI-Future-Radar/actions/runs/38711837970) یک پیام را به تلگرام تحویل داد، اما پذیرش سخت‌گیرانه به‌درستی شکست خورد: فقط یک حوزه از سه حوزهٔ مورد انتظار بازیابی شد و دو حوزه به‌دلیل شکست پردازش/کنترل کیفیت گزینهٔ قابل‌انتشار نداشتند (`nonpublishable_lanes=2`). سپس [PR شمارهٔ ۲۳۰](https://github.com/jamshidimoh/AI-Future-Radar/pull/230) برای جلوگیری از انتخاب خبر نامرتبط در جریان افراد کلیدی و [PR شمارهٔ ۲۳۱](https://github.com/jamshidimoh/AI-Future-Radar/pull/231) برای اصلاح قطعی نیم‌فاصله‌های رایج فارسی ادغام شدند. آزمون‌های PR شمارهٔ ۲۳۱ شامل Ruff، مجموعهٔ کامل کیفیت، رگرسیون تولید و گیت پذیرش، همگی سبز شدند. اجرای تولید [شمارهٔ ۱۴۴۴](https://github.com/jamshidimoh/AI-Future-Radar/actions/runs/38715164080) روی نسخهٔ نهایی هنوز در صف/مرحلهٔ شروع است؛ اجرای شمارهٔ ۱۴۴۳ به مرحلهٔ اجرای ربات و انتشار نرسید و شاهد پذیرش محسوب نمی‌شود. **وضعیت رسمی پروژه همچنان `CLOSURE PENDING` است** تا پس از نسخهٔ نهایی، سه اجرای متوالی با اثرانگشت یکسان شواهد عملیاتی کامل و موفق ارائه کنند. Issue نهایی [شمارهٔ ۶۹](https://github.com/jamshidimoh/AI-Future-Radar/issues/69) باز می‌ماند.

جزئیات قواعد و شواهد در `docs/PRODUCTION_CLOSURE_STATUS.md` و `docs/PRODUCTION_FINAL_ACCEPTANCE.md` ثبت شده‌اند. سبز بودن یک اجرای CI یا بسته‌شدن دستی Issue به‌تنهایی به‌معنای پایان واقعی پروژه نیست.

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
