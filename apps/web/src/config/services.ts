/**
 * کاتالوگ سرویس‌ها و متغیرهای محیطی لازم.
 * این فایل فقط «توضیح» است؛ مقدار واقعی کلیدها فقط در فایل .env سرور نگه‌داری می‌شود.
 * برای افزودن سرویس جدید: یک آبجکت به SERVICES اضافه کنید.
 */
export type VarKind = "secret" | "url" | "model" | "flag" | "text";

export interface EnvVar {
  name: string;
  kind: VarKind;
  required: boolean;
  /** مقدار پیش‌فرض Backend (برای secret خالی) */
  def?: string;
  help: string;
}

export type Support = "implemented" | "not_implemented" | "no_key";

export interface Service {
  id: string;
  group: "ai" | "data" | "infra" | "security";
  name: string;
  /** وضعیت پشتیبانی در Backend فعلی (بر اساس کد پروژه) */
  support: Support;
  purpose: string;
  /** مدخل واقعی در GET /api/ai/providers (فقط برای ارائه‌دهندگان AI) */
  providerId?: string;
  vars: EnvVar[];
  getKeyUrl?: string;
  docsUrl?: string;
  /** فایلی در Backend که این متغیرها را می‌خواند */
  usedBy: string;
  /** چیزهایی که «فقط با کلید» کافی نیستند */
  alsoNeeded: string[];
}

const RESTART = "بعد از ویرایش .env، کانتینر Backend باید دوباره ساخته شود: docker compose up -d --force-recreate backend";

export const SERVICES: Service[] = [
  {
    id: "gemini", group: "ai", name: "Google Gemini", support: "implemented", providerId: "gemini",
    purpose: "مدل زبانی برای طبقه‌بندی، استخراج رویداد/ادعا، تحلیل و گزارش‌نویسی.",
    getKeyUrl: "https://aistudio.google.com/apikey", docsUrl: "https://ai.google.dev/gemini-api/docs/models",
    usedBy: "backend/ai/providers/gemini.py",
    vars: [
      { name: "GEMINI_API_KEY", kind: "secret", required: true, help: "کلید از Google AI Studio (در هدر x-goog-api-key ارسال می‌شود)." },
      { name: "GEMINI_BASE_URL", kind: "url", required: false, def: "https://generativelanguage.googleapis.com", help: "فقط برای پروکسی/میرور تغییر دهید." },
      { name: "GEMINI_MODEL", kind: "model", required: true, def: "gemini-1.5-flash", help: "نام مدل. مقدار پیش‌فرض gemini-1.5-flash توسط گوگل بازنشسته شده؛ یک مدل فعلی (مثلاً gemini-2.5-flash) بگذارید و در صفحهٔ مدل‌های گوگل تأیید کنید." },
    ],
    alsoNeeded: [
      "MOCK_MODE=false (وگرنه حتی با کلید معتبر، فقط داده نمونه ساخته می‌شود)",
      "AI_DEFAULT_PROVIDER=gemini",
      "مدل معتبر و فعال در GEMINI_MODEL",
      "دسترسی شبکهٔ سرور به generativelanguage.googleapis.com (در برخی کشورها نیاز به شبکهٔ مناسب دارد)",
      RESTART,
    ],
  },
  {
    id: "openai", group: "ai", name: "OpenAI", support: "implemented", providerId: "openai",
    purpose: "مدل‌های GPT برای تحلیل و استخراج ساختاریافته.",
    getKeyUrl: "https://platform.openai.com/api-keys", docsUrl: "https://platform.openai.com/docs/models",
    usedBy: "backend/ai/providers/openai.py",
    vars: [
      { name: "OPENAI_API_KEY", kind: "secret", required: true, help: "کلید از platform.openai.com. نیازمند اعتبار/Billing فعال." },
      { name: "OPENAI_BASE_URL", kind: "url", required: false, def: "https://api.openai.com/v1", help: "برای سرویس‌های سازگار با OpenAI (مثلاً Azure یا gateway) تغییر دهید." },
      { name: "OPENAI_MODEL", kind: "model", required: true, def: "gpt-4o-mini", help: "نام مدل؛ قبل از استفاده در فهرست مدل‌های حساب خود تأیید کنید." },
    ],
    alsoNeeded: ["MOCK_MODE=false", "AI_DEFAULT_PROVIDER=openai", "Billing فعال در حساب OpenAI", RESTART],
  },
  {
    id: "anthropic", group: "ai", name: "Anthropic (Claude)", support: "implemented", providerId: "anthropic",
    purpose: "مدل‌های Claude برای تحلیل عمیق و نقش منتقد.",
    getKeyUrl: "https://console.anthropic.com/settings/keys", docsUrl: "https://docs.claude.com/en/docs/about-claude/models",
    usedBy: "backend/ai/providers/anthropic.py",
    vars: [
      { name: "ANTHROPIC_API_KEY", kind: "secret", required: true, help: "کلید از Anthropic Console. نیازمند اعتبار فعال." },
      { name: "ANTHROPIC_BASE_URL", kind: "url", required: false, def: "https://api.anthropic.com", help: "معمولاً تغییر نمی‌کند." },
      { name: "ANTHROPIC_MODEL", kind: "model", required: true, def: "claude-3-5-haiku-latest", help: "نام مدل را با فهرست فعلی مدل‌ها تطبیق دهید؛ مثلاً claude-haiku-5-5 برای مدل سریع." },
    ],
    alsoNeeded: ["MOCK_MODE=false", "AI_DEFAULT_PROVIDER=anthropic", "اعتبار فعال در Console", RESTART],
  },
  {
    id: "openrouter", group: "ai", name: "OpenRouter", support: "implemented", providerId: "openrouter",
    purpose: "یک کلید برای دسترسی به مدل‌های چند شرکت (مناسب fallback).",
    getKeyUrl: "https://openrouter.ai/keys", docsUrl: "https://openrouter.ai/models",
    usedBy: "backend/ai/providers/openrouter.py",
    vars: [
      { name: "OPENROUTER_API_KEY", kind: "secret", required: true, help: "کلید از openrouter.ai." },
      { name: "OPENROUTER_BASE_URL", kind: "url", required: false, def: "https://openrouter.ai/api/v1", help: "معمولاً تغییر نمی‌کند." },
      { name: "OPENROUTER_MODEL", kind: "model", required: true, def: "openai/gpt-4o-mini", help: "قالب «شرکت/مدل»؛ از فهرست OpenRouter انتخاب کنید." },
    ],
    alsoNeeded: ["MOCK_MODE=false", "AI_DEFAULT_PROVIDER=openrouter", "اعتبار در حساب OpenRouter", RESTART],
  },
  {
    id: "ollama", group: "ai", name: "Ollama (مدل محلی)", support: "not_implemented",
    purpose: "اجرای مدل روی سرور خودتان بدون کلید.",
    usedBy: "— (آداپتور در Backend وجود ندارد)",
    vars: [
      { name: "OLLAMA_BASE_URL", kind: "url", required: false, def: "http://localhost:11434", help: "فقط وقتی آداپتور Backend اضافه شود کاربرد دارد." },
    ],
    alsoNeeded: ["افزودن آداپتور در backend/ai/providers (کار Backend است، در این مأموریت انجام نشده)"],
  },
  {
    id: "free-data", group: "data", name: "بانک جهانی، بانک مرکزی اروپا، قیمت ارز و طلا، Yahoo، RSS", support: "no_key",
    purpose: "منابع داده‌ای که Backend فعلی بدون هیچ کلیدی از آن‌ها می‌خواند.",
    docsUrl: "https://datahelpdesk.worldbank.org/knowledgebase/articles/889386",
    usedBy: "domains/macro/fetchers.py ، domains/markets/fetchers.py ، domains/news/fetchers.py",
    vars: [
      { name: "USER_AGENT", kind: "text", required: false, def: "GlobalIntelligenceBot/0.1 (+https://example.local; contact@example.local)", help: "هویت درخواست‌ها؛ بهتر است ایمیل تماس واقعی خودتان را بگذارید تا منابع مسدود نکنند." },
      { name: "SOURCE_MIN_INTERVAL_SECONDS", kind: "text", required: false, def: "60", help: "حداقل فاصلهٔ درخواست به هر منبع." },
    ],
    alsoNeeded: [
      "دسترسی اینترنت سرور به دامنه‌های api.worldbank.org، ecb.europa.eu، open.er-api.com، api.gold-api.com و query1.finance.yahoo.com",
      "برای خبر: منبع RSS با feed_url معتبر و «فعال» در صفحهٔ «منابع اطلاعاتی»",
      "Yahoo رسمی نیست و ممکن است محدود یا مسدود شود",
    ],
  },
  {
    id: "fred", group: "data", name: "FRED (فدرال رزرو سنت‌لوئیس)", support: "not_implemented",
    purpose: "سری‌های اقتصادی آمریکا. در فهرست منابع ثبت شده، اما Backend فعلی fetcher ندارد.",
    getKeyUrl: "https://fred.stlouisfed.org/docs/api/api_key.html", docsUrl: "https://fred.stlouisfed.org/docs/api/fred/",
    usedBy: "— (هیچ کدی در Backend از آن استفاده نمی‌کند)",
    vars: [{ name: "FRED_API_KEY", kind: "secret", required: true, help: "کلید رایگان. تا وقتی Backend آن را نخواند، ثبت آن اثری ندارد." }],
    alsoNeeded: ["نوشتن fetcher و افزودن متغیر به backend/core/config.py (کار Backend)"],
  },
  {
    id: "acled", group: "data", name: "ACLED (داده‌های درگیری)", support: "not_implemented",
    purpose: "رویدادهای ژئوپلیتیک و درگیری. ثبت در فهرست منابع هست، fetcher ندارد.",
    getKeyUrl: "https://acleddata.com/", usedBy: "— (پیاده‌سازی‌نشده)",
    vars: [
      { name: "ACLED_API_KEY", kind: "secret", required: true, help: "کلید حساب ACLED." },
      { name: "ACLED_EMAIL", kind: "text", required: true, help: "ایمیل ثبت‌نام‌شده؛ ACLED علاوه بر کلید ایمیل هم می‌خواهد." },
    ],
    alsoNeeded: ["حساب تأییدشده در ACLED و رعایت شرایط استفاده", "نوشتن fetcher در Backend"],
  },
  {
    id: "alphavantage", group: "data", name: "Alpha Vantage", support: "not_implemented",
    purpose: "قیمت سهام/ارز. فقط به‌عنوان «کاندید» در مستندات آمده.",
    getKeyUrl: "https://www.alphavantage.co/support/#api-key", usedBy: "— (پیاده‌سازی‌نشده)",
    vars: [{ name: "ALPHAVANTAGE_API_KEY", kind: "secret", required: true, help: "کلید رایگان با سقف درخواست کم." }],
    alsoNeeded: ["نوشتن fetcher در Backend", "رعایت سقف درخواست در طرح رایگان"],
  },
  {
    id: "api-key", group: "security", name: "کلید داخلی API (X-API-Key)", support: "implemented",
    purpose: "محافظت از endpointهای Backend. همین کلید باید در «تنظیمات» رابط وارد شود و n8n هم از آن استفاده می‌کند.",
    usedBy: "backend/auth/deps.py ، backend/core/config.py",
    vars: [
      { name: "API_KEY", kind: "secret", required: true, help: "با python -c \"import secrets; print(secrets.token_urlsafe(32))\" بسازید. در production الزامی است." },
      { name: "ALLOWED_ORIGINS", kind: "url", required: true, def: "http://localhost:5173,http://localhost:3000", help: "آدرس دقیق رابط (با پورت) باید اینجا باشد، وگرنه مرورگر درخواست‌ها را با خطای CORS رد می‌کند." },
    ],
    alsoNeeded: ["همان مقدار API_KEY را در صفحهٔ «تنظیمات» رابط وارد کنید (فقط در حافظهٔ مرورگر می‌ماند)", RESTART],
  },
  {
    id: "secrets", group: "security", name: "رمزها و کلیدهای زیرساخت", support: "implemented",
    purpose: "در production مقدار پیش‌فرض «change-me» باعث توقف Backend می‌شود.",
    usedBy: "backend/core/config.py (validate_production) ، docker-compose.yml",
    vars: [
      { name: "SECRET_KEY", kind: "secret", required: true, help: "با secrets.token_urlsafe(48) بسازید." },
      { name: "POSTGRES_PASSWORD", kind: "secret", required: true, help: "رمز دیتابیس؛ در production نباید پیش‌فرض باشد." },
      { name: "N8N_ENCRYPTION_KEY", kind: "secret", required: true, help: "کلید رمزنگاری n8n؛ بعد از شروع استفاده تغییرش اطلاعات ذخیره‌شده را ناخوانا می‌کند." },
      { name: "MOCK_MODE", kind: "flag", required: true, def: "true", help: "برای داده و AI واقعی false کنید. در production باید false باشد." },
      { name: "AI_DEFAULT_PROVIDER", kind: "text", required: true, def: "mock", help: "یکی از: mock، gemini، openai، anthropic، openrouter." },
    ],
    alsoNeeded: ["VITE_API_BASE_URL هنگام «build» رابط خوانده می‌شود؛ بعد از تغییر باید ایمیج frontend دوباره ساخته شود", RESTART],
  },
];

export const GROUP_TITLES: Record<Service["group"], string> = {
  ai: "هوش مصنوعی",
  data: "منابع داده",
  security: "امنیت و راه‌اندازی",
  infra: "زیرساخت",
};
