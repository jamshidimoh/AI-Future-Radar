# AI Future Radar

رادار هوشمند پایش آینده فناوری با محوریت **هوش مصنوعی**. هدف محصول، پیدا کردن مهم‌ترین سیگنال‌های AI از پژوهش، صنعت، دانشگاه، مصاحبه، پادکست و اندیشه آینده و تبدیل آن‌ها به پیام فارسی قابل اتکا برای Telegram است.

## وضعیت محصول

هسته Production و مسیر انتشار عملیاتی هستند، اما برچسب **Production Complete** فقط پس از عبور از Final Production Acceptance صادر می‌شود. این مرز عمداً بین «کد و قراردادهای deterministic سبز» و «شواهد واقعی از اجرای متوالی Production» تفاوت می‌گذارد. جزئیات معیار پایان در `docs/PRODUCTION_FINAL_ACCEPTANCE.md` و وضعیت جاری در `docs/PRODUCTION_CLOSURE_STATUS.md` ثبت می‌شود.

Production با GitHub Actions هر ۴ ساعت یک‌بار اجرا می‌شود. اجرای دستی نیز از Actions ممکن است. اجرای خودکار با Push به `main` عمداً فعال نیست تا Commitهای فنی باعث انتشار ناخواسته Story نشوند.

## قرارداد خروجی Telegram

- عنوان خبر درشت و برجسته است.
- خلاصه و «چرا مهم است؟» در بلوک‌های جداگانه قرار می‌گیرند.
- نام منبع و «مطالعه منبع اصلی» در یک بلوک مستقل قرار دارند.
- «بررسی بیشتر با ChatGPT» در ردیف مستقل، Bold و قابل کلیک است.
- Model و Date در پایین کارت به‌عنوان metadata کم‌اهمیت نمایش داده می‌شوند.
- برای تراز RTL/LTR از فاصله‌های ثابت یا Directional Mark استفاده نمی‌شود؛ چیدمان عمودی برای سازگاری بهتر با کلاینت‌های مختلف Telegram استفاده می‌شود.
- Telegram Native Reactions و Channel Comments تجربه تعامل اصلی هستند و نیازی به دکمه‌های مصنوعی HTML ندارند.

## پیکربندی کانال

1. یک Discussion Group به کانال متصل باشد.
2. قابلیت Comments برای پست‌های کانال فعال باشد.
3. Reactionهای Native کانال فعال باشند.
4. Bot ارسال‌کننده Administrator کانال باشد.

## قرارداد محتوایی

- حداقل ۷۵٪ ظرفیت هر اجرا باید AI یا موضوعی با پیوند مستقیم و قابل اثبات با AI باشد.
- کوانتوم، ژنتیک، ذهن/آگاهی و آینده‌پژوهی فقط وقتی منتشر می‌شوند که ارتباط مشخص با AI/AGI داشته باشند.
- مصاحبه، پادکست، سخنرانی و دیدگاه افراد اثرگذار، در صورت کیفیت کافی، کلاس مستقل محتوا محسوب می‌شوند.
- Reddit و منابع community برای discovery مجازند، اما انتشار آن‌ها نیازمند امتیاز بالاتر است.
- از هر منبع در هر اجرا حداکثر یک Story انتخاب می‌شود و مصرف منابع در بازه ۷ روزه جریمه می‌شود.
- Storyهای تکراری در همان اجرا و نسبت به تاریخچه حذف می‌شوند و بهترین روایت حفظ می‌شود.
- نقل‌قول فقط وقتی نمایش داده می‌شود که عبارت واقعاً در متن منبع وجود داشته باشد.

## People & Ideas Radar

Watchlist مستقل شامل رهبران AI، آینده‌پژوهان و متفکران بلندمدت، و پژوهشگران ذهن/آگاهی مرتبط با AI است. برای افراد مهم query اختصاصی و پنجره کشف ۷روزه وجود دارد؛ candidate معتبر Leader/Thinker جایگاه انتخابی دریافت می‌کند.

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

Google News یک منبع اختیاری است و در برابر `429/5xx` با retry محدود و circuit-breaker عمل می‌کند؛ شکست آن نباید کل Radar را متوقف کند. YouTube و RSS مسیرهای جایگزین Discovery هستند.

Router مدل نیز در صورت `429` یا خطای provider به مدل بعدی سوئیچ می‌کند. سیاست Hugging Face `free-first` است و نباید با `HF_MODEL` دور زده شود.

## CI/CD

Quality CI روی تغییرات Repository قراردادهای compile، YAML، AI-first، Leader slot، Story dedup، quote evidence و Telegram formatting را کنترل می‌کند. Production فقط طبق Schedule چهار‌ساعته یا اجرای دستی اجرا می‌شود.

Workflow تولیدی concurrency دارد تا دو Run همزمان روی state اشتراکی اجرا نشوند. Diagnostics هر Run برای ۷ روز به‌عنوان Artifact نگهداری می‌شوند.

## Secrets

`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL`, `TELEGRAM_CHANNEL_USERNAME`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `HF_TOKEN`

متغیر اختیاری: `HF_MODEL`. سیاست پیش‌فرض: `HF_POLICY=free-first`.
