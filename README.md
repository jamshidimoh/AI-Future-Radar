# AI Future Radar

رادار هوشمند پایش آینده فناوری با محوریت **هوش مصنوعی**. محصول، مهم‌ترین سیگنال‌های AI و فناوری‌های پیشرفته را از پژوهش، صنعت، دانشگاه، مصاحبه، پادکست و اندیشه آینده جمع‌آوری، ارزیابی و به پیام فارسی قابل اتکا برای Telegram تبدیل می‌کند.

## وضعیت محصول

**Production Complete / CLOSED**

مرز پایان پروژه در `docs/PRODUCTION_CLOSURE_STATUS.md` ثبت شده است. پنجره نهایی شواهد شامل انتشار موفق News، انتشار واقعی Education و یک رد کامل fail-closed در Editorial QA بود و Production Closure Gate نیز هر ۱۱ معیار خود را PASS کرد.

مسیر تولید اصلی با GitHub Actions فقط در زمان‌بندی مشخص یا با اجرای دستی فعال است؛ Push به `main` باعث اجرای ناخواسته Production نمی‌شود. پس از بسته‌شدن پروژه، تغییرات جدید باید در مسیر مستقل Maintenance/Evolution انجام شوند، مگر اینکه یک frozen invariant یا production contract شکسته باشد.

## استفاده دیگران

راهنمای کامل اجرای نسخه منتشرشده، تنظیم environment، اجرای Docker، نگهداری state، اتصال Telegram، ارتقا و rollback در `docs/USER_GUIDE.md` قرار دارد.

برای شروع سریع، image رسمی را دریافت کنید:

```bash
docker pull ghcr.io/jamshidimoh/ai-future-radar:v1.0.0
```

سپس container را با یک فایل `.env` و یک دایرکتوری persistent برای `/app/data` اجرا کنید. در صورت عمومی بودن Package، pull از GHCR بدون authentication امکان‌پذیر است.

## انتشار و Packages

بسته توزیعی رسمی پروژه، یک OCI container برای GitHub Container Registry است:

`ghcr.io/jamshidimoh/ai-future-radar`

Workflow انتشار در `.github/workflows/publish-container.yml` قرار دارد و فقط با tagهای semantic مانند `v1.0.0` یا با اجرای دستی یک tag موجود image را build، validate و publish می‌کند. Image دارای OCI source metadata، SBOM و provenance است.

راهنمای انتشار در `docs/RELEASE.md` قرار دارد. قالب متغیرهای محیطی نمونه نیز در `.env.example` موجود است.

## قرارداد خروجی Telegram

عنوان خبر برجسته است و خلاصه و «چرا مهم است؟» جداگانه ارائه می‌شوند. منبع و دسترسی به منبع اصلی در بلوک مستقل قرار دارند و «بررسی بیشتر با ChatGPT» در ردیف جداگانه نمایش داده می‌شود. Model و Date به‌عنوان metadata کم‌اهمیت در پایین کارت قرار می‌گیرند.

برای RTL/LTR از فاصله‌های ثابت یا Directional Mark استفاده نمی‌شود و چیدمان عمودی برای سازگاری بهتر با کلاینت‌های Telegram استفاده می‌شود. Native Reactions و Channel Comments نیز تعامل اصلی هستند.

## پیکربندی کانال

1. یک Discussion Group به کانال متصل باشد.
2. قابلیت Comments فعال باشد.
3. Reactionهای Native فعال باشند.
4. Bot ارسال‌کننده Administrator کانال باشد.

## قرارداد محتوایی

- حداقل ۷۵٪ ظرفیت هر اجرا باید AI یا موضوعی با پیوند مستقیم و قابل اثبات با AI باشد.
- کوانتوم، ژنتیک، ذهن/آگاهی و آینده‌پژوهی فقط در صورت وجود ارتباط روشن با AI/AGI منتشر می‌شوند.
- مصاحبه، پادکست، سخنرانی و دیدگاه افراد اثرگذار در صورت کیفیت کافی کلاس مستقل محتوا هستند.
- Reddit و منابع community برای discovery مجازند، اما برای انتشار به کیفیت بالاتر نیاز دارند.
- از هر منبع در هر اجرا حداکثر یک Story انتخاب می‌شود و مصرف منبع در بازه ۷ روزه جریمه می‌شود.
- Storyهای تکراری در اجرا و نسبت به تاریخچه حذف می‌شوند و بهترین روایت حفظ می‌شود.
- نقل‌قول فقط در صورت وجود عبارت واقعی در متن منبع نمایش داده می‌شود.

## People & Ideas Radar

Watchlist مستقل شامل رهبران AI، آینده‌پژوهان، متفکران بلندمدت و پژوهشگران ذهن/آگاهی مرتبط با AI است. برای افراد مهم query اختصاصی و پنجره کشف ۷روزه وجود دارد و candidate معتبر Leader/Thinker جایگاه انتخابی دریافت می‌کند.

نمونه شخصیت‌ها: Sam Altman، Dario Amodei، Demis Hassabis، Jensen Huang، Elon Musk، Geoffrey Hinton، Yann LeCun، Yuval Noah Harari، Nick Bostrom، Max Tegmark، David Chalmers، Anil Seth، Joscha Bach، Christof Koch و Murray Shanahan.

## معماری

```text
RSS / YouTube / Google News / Leader Watchlist
                    ↓
          Discovery + Fail-safe Sources
                    ↓
             Canonical URL Dedup
                    ↓
             Canonical Story Dedup
                    ↓
        AI Policy + Low-Signal Gate
                    ↓
      Leader / Interview Protection
                    ↓
      Quality + Freshness + Rotation
                    ↓
        AI-first / Diversity Selection
                    ↓
       Draft JSON → Editorial JSON
                    ↓
          Evidence-safe Validation
                    ↓
             LLM Router/Fallback
                    ↓
              Telegram HTML
                    ↓
 Telegram Native Reactions + Comments
                    ↓
       seen.json + source memory
```

## Resilience و LLM Router

Google News منبع اختیاری است و خطاهای `429/5xx` با retry محدود و circuit-breaker مدیریت می‌شوند؛ شکست آن نباید کل Radar را متوقف کند. YouTube و RSS مسیرهای جایگزین Discovery هستند.

Router مدل نیز در خطاهای provider به مدل بعدی سوئیچ می‌کند. سیاست Hugging Face `free-first` است.

## CI/CD

Quality CI قراردادهای compile، YAML، AI-first، Leader slot، Story dedup، quote evidence و Telegram formatting را کنترل می‌کند. Production طبق Schedule یا اجرای دستی اجرا می‌شود و state مشترک با concurrency محافظت شده است.

Diagnostics هر Production Run به‌عنوان Artifact نگهداری می‌شوند.

## Secrets

`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL`, `TELEGRAM_CHANNEL_USERNAME`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `HF_TOKEN`, `YOUTUBE_API_KEY`

متغیرهای اختیاری: `HF_MODEL`, `HF_POLICY`, `AI_RADAR_EDITORIAL_REVIEW`.
