# AI Future Radar — راهنمای استفاده برای کاربران دیگر

این راهنما برای کسی است که می‌خواهد نسخه منتشرشده AI Future Radar را بدون ورود به فرایند توسعه مخزن اجرا کند.

## 1. آنچه دریافت می‌کنید

بسته رسمی پروژه یک OCI container است که در GitHub Container Registry منتشر شده است.

آخرین GitHub Release ثبت‌شده `V1.0.1.On.Publish` است. Workflow انتشار image را از tagهای semantic تولید می‌کند؛ برای اجرای قابل تکرار، از tag دقیق image یا digest همان artifact استفاده کنید.

```text
ghcr.io/jamshidimoh/ai-future-radar:latest
```

در صورتی که tag semantic مربوط به Release فعلی در GHCR موجود باشد، همان tag دقیق را به‌جای `latest` استفاده کنید. GitHub Container Registry از pull عمومی بدون احراز هویت پشتیبانی می‌کند فقط وقتی Package عمومی باشد؛ Package خصوصی نیازمند احراز هویت مناسب است.

## 2. پیش‌نیازها

حداقل‌های عملی:

- Docker با پشتیبانی از imageهای Linux/OCI
- دسترسی شبکه به `ghcr.io`
- یک محل persistent برای دایرکتوری `data/`
- دسترسی به APIهای providerهایی که برای تحلیل فعال می‌کنید
- در صورت انتشار به Telegram: یک Bot و یک Channel که Bot در آن Administrator باشد

## 3. دریافت image

برای آخرین نسخه stable:

```bash
docker pull ghcr.io/jamshidimoh/ai-future-radar:latest
```

برای اجرای قابل بازتولید، از tag دقیق موجود در GHCR یا digest استفاده کنید. Release repository فعلی `V1.0.1.On.Publish` است؛ موجودبودن دقیق همین نام به‌عنوان image tag باید در GHCR بررسی شود، زیرا workflow tag container را از semantic `v*.*.*` می‌سازد.

برای بررسی digest محلی:

```bash
docker image inspect ghcr.io/jamshidimoh/ai-future-radar:latest
```

## 4. تنظیم متغیرهای محیطی

قالب رسمی در `.env.example` قرار دارد. یک فایل محلی مانند `.env` ایجاد کنید و فقط مقادیر واقعی خودتان را در آن قرار دهید.

```dotenv
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHANNEL=
TELEGRAM_CHANNEL_USERNAME=
GEMINI_API_KEY=
GROQ_API_KEY=
OPENROUTER_API_KEY=
HF_TOKEN=
YOUTUBE_API_KEY=

HF_MODEL=
HF_POLICY=free-first
AI_RADAR_EDITORIAL_REVIEW=1
```

همه providerها الزاماً لازم نیستند؛ فقط credentialهایی را تنظیم کنید که واقعاً در محیط شما استفاده می‌شوند. هیچ credential واقعی را در Git، Dockerfile یا image قرار ندهید.

## 5. اجرای ساده

برای اجرای container با فایل محیطی و state پایدار:

```bash
docker run --rm \
  --env-file .env \
  -v "$(pwd)/data:/app/data" \
  ghcr.io/jamshidimoh/ai-future-radar:latest
```

در Windows PowerShell:

```powershell
docker run --rm `
  --env-file .env `
  -v "${PWD}\data:/app/data" `
  ghcr.io/jamshidimoh/ai-future-radar:latest
```

دایرکتوری `data/` را حذف نکنید اگر می‌خواهید حافظه اجرایی، deduplication و state بین اجراها حفظ شود.

## 6. چرا persistent state مهم است؟

Runtime بخشی از state عملیاتی را در `data/` نگهداری می‌کند؛ از جمله تاریخچه دیده‌شدن محتوا، state انتشار و پیشرفت Education. بنابراین container را می‌توان تعویض یا به‌روزرسانی کرد، ولی volume یا directory مربوط به `data/` باید حفظ شود.

برای محیط production بهتر است `data/` روی storage پایدار میزبان قرار گیرد و قبل از تغییر نسخه از آن backup گرفته شود.

## 7. راه‌اندازی Telegram

برای انتشار در Telegram حداقل این موارد لازم است:

1. Bot در Channel به‌عنوان Administrator اضافه شود.
2. Comments/Discussion در صورت استفاده فعال باشد.
3. Native Reactions در صورت نیاز فعال باشند.
4. `TELEGRAM_BOT_TOKEN` و شناسه/نام کانال در environment تنظیم شوند.

رادار قبل از publication از دروازه‌های زبان، کیفیت و evidence عبور می‌کند؛ وجود candidate به‌تنهایی به معنی انتشار نیست. سیستم در شرایط نامعتبر باید fail-closed عمل کند.

## 8. رفتار محتوایی

Radar برای feed عمومی و بدون فیلتر طراحی نشده است. تمرکز اصلی روی AI و فناوری‌های پیشرفته است و برخی حوزه‌های نزدیک مانند quantum، genetics، consciousness/cognition و future studies فقط وقتی وارد خروجی عادی می‌شوند که ارتباط روشن و قابل دفاعی با AI/AGI داشته باشند.

مصاحبه، podcast و سخنرانی افراد اثرگذار می‌توانند به‌عنوان کلاس محتوایی مستقل وارد شوند، اما همچنان quality و evidence gate را دور نمی‌زنند.

## 9. رتبه‌بندی و انتشار

سیستم از selection رسمی، diversity، freshness و duplicate suppression استفاده می‌کند. ظرفیت normal publication ثابت است و candidate window به‌تنهایی ظرفیت انتشار را زیاد نمی‌کند.

Leader/Interview protection یک اولویت routing است، نه مجوز عبور از quality/evidence gate.

در صورت ردشدن candidate توسط Editorial QA یا سایر gateهای الزامی، عدم انتشار نتیجه صحیح سیستم است و نباید با کاهش کورکورانه thresholdها جبران شود.

## 10. Providers و fallback

Router مدل می‌تواند در صورت خطای provider به provider بعدی سوئیچ کند. سیاست Hugging Face در پیکربندی فعلی `free-first` است.

Google News یک منبع اختیاری است و خطاهای آن نباید کل Radar را متوقف کنند؛ مسیرهای RSS و YouTube نقش fallback در Discovery دارند.

## 11. اجرای دستی و اجرای زمان‌بندی‌شده

در استقرار مرجع GitHub Actions، Production طبق Schedule یا اجرای دستی اجرا می‌شود و Push عادی به `main` نباید به‌طور ناخواسته یک publication production را شروع کند.

در یک استقرار Docker مستقل، زمان‌بندی اجرای container به scheduler محیط شما واگذار می‌شود؛ برای نمونه می‌توانید از cron، systemd timer یا scheduler سرویس cloud استفاده کنید.

اجرای موازی روی یک `data/` مشترک توصیه نمی‌شود، چون state اجرایی باید به‌صورت کنترل‌شده و ترتیبی تغییر کند.

## 12. ارتقای نسخه

نسخه image را صریح تعیین کنید. برای production توصیه می‌شود از tag دقیق موجود در GHCR یا digest استفاده شود، نه صرفاً `latest`.

قبل از ارتقای نسخه:

```bash
cp -a data data-backup
```

سپس container نسخه جدید را با همان persistent `data/` اجرا کنید.

برای rollback، به image tag قبلی برگردید. تا زمانی که قرارداد state سازگار باشد، state را نگه دارید؛ اگر یک release به migration state نیاز داشته باشد، باید release notes همان نسخه را ملاک قرار دهید.

## 13. عیب‌یابی اولیه

اگر container فوراً متوقف شد، ابتدا environment variables و دسترسی شبکه را بررسی کنید.

اگر publication انجام نشد، log را از خود برنامه بررسی کنید و مشخص کنید candidate در کدام gate متوقف شده است؛ ردشدن Editorial یا evidence به معنی failure زیرساختی نیست.

اگر duplicate یا state غیرمنتظره مشاهده شد، اجرای موازی روی یک `data/` مشترک را متوقف و آخرین backup معتبر state را بررسی کنید.

اگر provider خاصی خطا می‌دهد، credential و quota همان provider را جداگانه بررسی کنید؛ طراحی Router این است که خطای یک provider کل pipeline را زمین نزند.

## 14. نکات امنیتی

Credentialها فقط باید از environment، secret manager یا CI/CD secrets تأمین شوند. فایل `.env` را commit نکنید.

اگر Package عمومی باشد، image قابل pull است، ولی این به معنی عمومی بودن secrets یا داده‌های runtime نیست. Secrets و `data/` باید خارج از image نگهداری شوند. GitHub نیز برای Container Registry استفاده از authentication مناسب برای packageهای خصوصی را الزامی می‌داند.

## 15. معماری عملیاتی مرجع

```text
Source discovery
      ↓
Canonical URL / story dedup
      ↓
AI relevance + policy gates
      ↓
Quality / freshness / rotation
      ↓
AI-first + diversity selection
      ↓
Editorial validation
      ↓
LLM routing / fallback
      ↓
Telegram formatting
      ↓
Publication
      ↓
Persistent state in /app/data
```

## 16. مستندات تکمیلی

- معماری: `ARCHITECTURE.md`
- وضعیت نهایی Production: `docs/PRODUCTION_CLOSURE_STATUS.md`
- راهنمای Release و Package: `docs/RELEASE.md`
- نمونه environment: `.env.example`

## وضعیت نسخه مرجع

این راهنما از وضعیت `Production Complete / CLOSED` در تاریخ 2026-09-05 تبعیت می‌کند. آخرین GitHub Release ثبت‌شده `V1.0.1.On.Publish` است. برای image باید tag semantic یا digest واقعی موجود در GHCR را ملاک قرار داد؛ این راهنما عمداً `v1.0.0` را به‌عنوان release مرجع اعلام نمی‌کند، چون چنین GitHub Releaseای در repository ثبت نشده است.
