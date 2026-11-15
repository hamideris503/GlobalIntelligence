# نقشه‌راه اجرایی تکمیل GlobalIntelligence
## نسخهٔ ۲٫۲ — اصلاح‌شده بر اساس اقدامات و تصمیم‌های تأییدشدهٔ مالک

**تاریخ مبنا:** ۱۴ نوامبر ۲۰۲۶ — ویرایش ۲٫۲ بر اساس اطلاعات تکمیلی مالک  
**مبنای حسابرسی:** چهار گزارش ارائه‌شده توسط مالک، وضعیت تاریخی Branch `step6a-analysis-dashboard` و HEAD `2d0e1bc` در تاریخ ممیزی، و اسناد مرجع پروژه  
**محیط هدف این نسخه:** کامپیوتر محلی Windows  
**محدودهٔ اصلی:** تکمیل محصول محلی GlobalIntelligence؛ نه استقرار VPS یا انتشار عمومی اینترنتی

---

## 0.A. تصمیم‌ها و کارهای قبلاً انجام‌شده توسط مالک — مرجع قطعی نسخهٔ ۲٫۲

این بخش بر اساس اعلام مستقیم مالک در ۱۴ نوامبر ۲۰۲۶ ثبت شده است. این موارد دیگر نباید به شکل «کار انجام‌نشدهٔ مالک» یا سؤال تکراری مطرح شوند. وظیفهٔ AI ابتدا **پیداکردن، اعتبارسنجی، اتصال و ثبت شواهد** است.

| مورد | اعلام مالک | وضعیت اجرایی در Roadmap 2.2 | اقدام AI |
|---|---|---|---|
| Gold Set انسانی | مجموعهٔ حدود ۲۰۰ برچسب خبر در `H:\GIRuntime\labeling` آماده شده است | `OWNER_REPORTED_PRESENT / VALIDATION_REQUIRED` | مسیر را خارج از Repository نیز بررسی کند؛ تعداد، فرمت، labelها، provenance، duplicates، زبان/موضوع و SHA را بدون تغییر اصل فایل‌ها اعتبارسنجی کند و به evaluation harness موجود متصل کند. درخواست برچسب‌گذاری مجدد ممنوع، مگر فقط کسری واقعی یا نقص اعتبارسنجی اثبات شود. |
| SMTP برای Auth/Email | تنظیمات Gmail در `.env` قرار گرفته و مالک قبلاً ارسال را تست کرده است | `OWNER_REPORTED_CONFIGURED_AND_TESTED / CREDENTIAL_ROTATION_REQUIRED` | وجود متغیرها را فقط به‌شکل masked بررسی کند؛ مقدار هیچ Secret را نخواند/چاپ/کپی نکند. چون App Password در گفتگو افشا شده، آن credential باید توسط مالک revoke و جایگزین شود؛ پس از آن تست محدود و امن دوباره اجرا شود. |
| Country Profile دوم | آمریکا انتخاب شده است | `OWNER_DECIDED_US` | از کد/دادهٔ موجود برای US استفاده کند؛ دیگر دربارهٔ انتخاب کشور دوم سؤال نپرسد. اگر profile یا دادهٔ معتبر US وجود ندارد، آن را پیاده‌سازی/seed کنترل‌شده کند و دادهٔ اقتصادی ساختگی نسازد. |
| AI Provider credentials | کلیدهای چهار Provider یعنی Gemini، OpenRouter، Groq و Cloudflare در `.env` موجودند | `OWNER_REPORTED_PRESENT / VALIDITY_AND_POLICY_UNVERIFIED` | فقط configured/present بودن را بدون چاپ مقدار بررسی کند؛ اعتبار اتصال، Model، Free Policy، quota، billing و Gateway را جداگانه و با تست کم‌هزینه اعتبارسنجی کند. درخواست دوبارهٔ API Key ممنوع، مگر یک Provider واقعاً فاقد credential باشد. |
| AI budget | تعیین بودجه به AI واگذار شده است | `OWNER_DELEGATED_POLICY` | سیاست محافظه‌کارانهٔ بخش 3.3.2 را اعمال کند؛ هزینهٔ پنهان، fallback پولی و عبور از سقف ممنوع. |
| حذف Legacy UI | مالک حذف فایل‌های Legacy را تأیید کرده است | `OWNER_APPROVED_WITH_SAFETY_GATES` | فایل‌های Legacy UI را پس از manifest، بررسی dependency/reference، backup و hash حذف کند؛ برای تک‌تک فایل‌هایی که قطعاً Legacy UI و بدون مصرف‌اند تأیید مجدد نخواهد خواست. فایل‌های `SHARED`, `NEW_UI_PROTECTED`, `UNKNOWN_PROTECTED`, test fixtures، Backend/API و migrationها مشمول این اجازه نیستند. |
| Retention / Auto-Purge | سیاست حذف داده قبلاً توسط مالک تعیین شده است | `OWNER_POLICY_ALREADY_EXISTS / LOCATE_AND_PRESERVE` | سیاست را از v1.9، Roadmapها، config و کد موجود استخراج و به یک منبع مرجع تبدیل کند. سؤال عمومی تکراری دربارهٔ سیاست نپرسد و threshold جدید نسازد. Toggle موجود حفظ شود؛ Auto-Purge به‌صورت پیش‌فرض خاموش بماند. |
| Forecast targets | طلا، دلار، نفت، تورم و رمزارزها؛ انتخاب افق به AI واگذار شده است | `OWNER_DECIDED_TARGETS / HORIZON_DEFINED_BY_ROADMAP` | سبد و افق‌های بخش 19.7 را اجرا کند؛ هدف اصلی رمزارز در شروع BTC و ETH باشد. انتخاب منبع داده و اعتبارسنجی لازم است، نه درخواست دوبارهٔ انتخاب دارایی از مالک. |
| ثبت‌نام و مدیریت حساب | ثبت‌نام عمومی آزاد و امکان ساخت حساب توسط مدیر | `OWNER_CONFIRMED_PRODUCT_POLICY` | هر دو قابلیت را حفظ/تکمیل کند؛ ایجاد اولین Admin از CLI جایگزین قابلیت Admin برای ایجاد حساب کاربران عادی نیست. |

### 0.A.1. مرز مهم دربارهٔ SMTP Secret

مالک قبلاً SMTP را تنظیم و تست کرده، اما App Password آن در پیام گفتگو افشا شده است. آن credential از این لحظه **compromised** تلقی شود. AI باید:

1. هرگز Secret افشاشده را در report، source code، command history، issue، test fixture یا فایل جدید تکرار نکند.
2. مالک را فقط برای اقدام ضروری revoke/rotate راهنمایی کند؛ این اقدام به حساب Google مالک نیاز دارد.
3. بعد از جایگزینی Secret در `.env` محلی، متغیرها را فقط به‌شکل `SET/MISSING` و masked presence گزارش کند.
4. Secret scanning را روی Git history، tracked files، logs، backups و artifacts اجرا کند، بدون چاپ مقدار.
5. SMTP را مجدداً با مقصد آزمایشی تأیید کند. نتیجهٔ قدیمی مالک به‌عنوان `OWNER_REPORTED_TEST_SUCCESS` حفظ شود، نه اینکه بدون تست تازه به‌عنوان runtime فعلی ثبت شود.

### 0.A.2. قاعدهٔ عدم تکرار درخواست از مالک

پیش از هر درخواست ورودی، AI باید به این جدول و سپس Repository/`.env`/مسیرهای محلی دسترسی‌پذیر مراجعه کند. پرسیدن دوبارهٔ «۲۰۰ برچسب داری؟»، «کشور دوم چیست؟»، «API Keyها را بده»، «سیاست Retention چیست؟» یا «آیا حذف Legacy را تأیید می‌کنی؟» ممنوع است. فقط یک نیاز جدید و دقیق که پس از بررسی مستقیم ثابت شده باشد می‌تواند به مالک ارجاع شود.

---

# 0. دستور اصلی به AI کدنویس

تو مهندس ارشد مسئول **تکمیل پروژهٔ موجود GlobalIntelligence** هستی. این پروژه از ابتدا ساخته نمی‌شود. وظیفهٔ تو این است که ابتدا وضعیت واقعی checkout را مشخص کنی، قابلیت‌های سالم را حفظ کنی، شکاف‌های واقعی را پیدا کنی و آن‌ها را به‌ترتیب وابستگی ببندی.

**قاعدهٔ اصلی: آنچه سالم و اثبات‌شده است حفظ شود؛ آنچه ناقص است تکمیل شود؛ آنچه وجود ندارد فقط پس از تأیید نبود آن طراحی و ساخته شود.**

هیچ‌گاه صرف وجود فایل، کلاس، Endpoint، صفحه، تست یا مستند را معادل تکمیل قابلیت ندان.

هر قابلیت باید جداگانه در این پنج سطح ارزیابی شود:

1. **Implementation:** کد و قرارداد فنی وجود دارد.
2. **Integration:** اجزای لازم به یکدیگر متصل شده‌اند.
3. **Runtime:** قابلیت در محیط محلی موردنظر واقعاً اجرا شده است.
4. **User Acceptance:** گردش کار واقعی کاربر از ابتدا تا انتها درست کار می‌کند.
5. **Operational Safety:** امنیت، خطا، retry، بازیابی، backup و محدودیت‌های عملیاتی بررسی شده‌اند.

فقط وقتی معیارهای قابل‌اعمال هر پنج سطح پاس شدند، قابلیت را `VERIFIED_COMPLETE` اعلام کن.

## 0.1. قوانین اجرای کار

- در هر نوبت ابتدا `WP-00` را فقط‌خواندنی اجرا کن.
- بعد از ممیزی، فقط **یک Work Package و یک زیرمرحلهٔ محدود** را انتخاب و اجرا کن.
- Stage بعدی را در همان نوبت خودکار شروع نکن.
- قبل از تغییر، وابستگی‌ها، فایل‌های درگیر، خطرات و معیار پذیرش را مشخص کن.
- پس از تغییر، تست‌های متناسب را اجرا کن، گزارش کامل بده و متوقف شو.
- اگر قابلیت از قبل کامل و دارای شواهد تازه است، فقط آن را ثبت کن و از توسعهٔ مجدد خودداری کن.
- اگر شواهد قدیمی‌اند یا کد مؤثر تغییر کرده، فقط revalidation انجام بده؛ اصلاح تاریخی سالم را دوباره پیاده‌سازی نکن.
- اگر ورودی مالک یا سرویس خارجی لازم است، فقط همان بخش را `BLOCKED_OWNER_INPUT` ثبت کن و کارهای مستقل را متوقف نکن.
- هیچ عدد، نتیجهٔ تست، وضعیت زنده، هزینه، زمان اجرا، Provider یا رکورد دیتابیس را حدس نزن.

## 0.2. محدودهٔ مجاز و ممنوع

**مجاز:** بررسی، تغییر محدود کد محلی، تکمیل تست، اجرای تست روی محیط آزمایشی، اصلاح مستندات، ایجاد migration جدید پس از بررسی و فقط در DB آزمایشی، اجرای کنترل‌شدهٔ قابلیت‌های محلی با دادهٔ مجاز.

**ممنوع مگر با دستور جداگانهٔ مالک:**

- VPS، deployment عمومی، دامنهٔ اینترنتی، reverse proxy تولیدی و تنظیم سرور Production.
- `git push`، `git pull`، `commit`، `merge`، ساخت PR یا تغییر Remote توسط AI.
- `git reset --hard`، `git clean -fd`، حذف/بازنویسی فایل‌های محلی بدون تأیید دقیق.
- `docker compose down -v`، حذف Volume، reset دیتابیس ارزشمند یا حذف واقعی رکوردها.
- فعال‌سازی خودکار Provider پولی، ارسال واقعی پیام، Telegram destination جدید یا Workflow ناشناس.
- نصب package یا ابزار ناشناس صرفاً برای رفع سریع مشکل.
- حذف Archive، Retention، Source history، Article history، Event، Claim، Evidence یا Memory.
- روشن‌کردن Auto-Purge.

---

# 1. مرجع تصمیم و ترتیب اعتبار شواهد

در صورت تعارض، ترتیب زیر را رعایت کن:

1. تصمیم صریح و جدید مالک پروژه.
2. قراردادهای تأییدشدهٔ مالک و فایل‌های مرجع UI/محصول که در Repository یا پوشهٔ کاری موجودند.
3. کد و تست‌های checkout فعلی، با SHA مشخص.
4. Migration و Schema واقعی دیتابیس مورد استفاده.
5. اجرای مستقیم و قابل‌بازتولید روی محیط آزمایشی.
6. نتایج CI که به همان SHA متصل‌اند.
7. گزارش‌های ممیزی A، B، C و D به‌عنوان شواهد تاریخی.
8. Roadmapها، READMEها و اسناد قدیمی؛ مگر آنکه مالک صریحاً آن‌ها را مرجع جاری معرفی کرده باشد.

**فایل `GlobalIntelligence_Roadmap_v1.9_Auth_UI_Animated_and_Security_Completion` باید در شروع کار خوانده شود، اگر در Repository/فایل‌های پروژه موجود است.** قراردادهای تأییدشدهٔ آن حفظ شوند. اگر فایل پیدا نشد، محتوای آن را حدس نزن؛ نبود آن را ثبت کن و فقط از تصمیم‌های صریح مالک و این سند استفاده کن.

همین قاعده دربارهٔ HTMLهای مرجع UI، فایل‌های Design و نقشه‌راه‌های قبلی برقرار است: ابتدا فایل دقیق را پیدا کن، سپس نسخه و SHA آن را ثبت کن.

## 1.1. شواهد تاریخی چهار ممیزی

| شناسه | نوع گزارش | استفادهٔ مجاز |
|---|---|---|
| A | گزارش عملیاتی قبلی، شامل Runtime/DB/Services | سرنخ برای اختلاف‌های داده و سرویس؛ نه وضعیت امروز |
| B | گزارش معماری و شکاف قابلیت‌های تحلیلی | سرنخ برای Memory، Domain Coverage، Causal، Ensemble و Backtesting |
| C | ممیزی جامع فنی ۱۴ نوامبر، بخش‌های A تا V | موجودی معماری، Stageها، UI، CI، AI، DB و تست‌ها |
| D | حسابرسی مستقل ۱۴ نوامبر | شواهد مستقیم گزارش‌شده دربارهٔ Git، Ruff، Alembic و شمارش‌ها |

هیچ‌یک از گزارش‌ها به‌تنهایی مرجع قطعی وضعیت فعلی نیست. وضعیت واقعی باید در `WP-00` از checkout حاضر استخراج شود.

## 1.2. Snapshot تاریخی که نباید به‌عنوان وضعیت امروز فرض شود

گزارش‌های C و D این وضعیت را در زمان حسابرسی ثبت کرده‌اند:

- Branch: `step6a-analysis-dashboard`
- HEAD: `2d0e1bc768ecbedde9dc58a91ef914e1e6a5be97`
- Working Tree: شش فایل Modified و دو فایل Untracked
- فاصلهٔ Branch با `origin/main`: حدود ۲۲ Commit طبق گزارش D
- PostgreSQL: نتیجهٔ ۱۸۱۴ موفق و صفر شکست روی HEAD `ebe1292` طبق گزارش مستندات
- SQLite: ۱۸۱۳ موفق، یک Skip و صفر شکست طبق گزارش مستندات
- Playwright: ۳۴ موفق و صفر شکست، اجرای محلی گزارش‌شده
- CI راه‌دور GitHub: `NOT_VERIFIED`
- Ruff روی Working Tree: چهار خطا طبق گزارش D؛ Ruff روی نسخهٔ HEAD فایل `alerts.py` پاک گزارش شده است
- Alembic: یک Head با نام `f0auth_users_accounts` و حدود ۵۱ Revision طبق گزارش D

این اعداد فقط Snapshot تاریخی‌اند. آن‌ها را به Commit جدید تعمیم نده.

---

# 2. وضعیت‌های استاندارد و سیاست پذیرش

## 2.1. وضعیت‌های مجاز

| وضعیت | معنی |
|---|---|
| `VERIFIED_COMPLETE` | کد، اتصال، Runtime، User Flow و Safety با شواهد تازه پذیرفته شده‌اند |
| `IMPLEMENTED_NOT_ACCEPTED` | کد وجود دارد، اما بخشی از Integration/Runtime/Acceptance باز است |
| `PARTIALLY_VERIFIED` | فقط بخشی از معیارها با اجرای مستقیم ثابت شده‌اند |
| `NOT_VERIFIED` | صرفاً کد، مستند یا تست موجود است؛ اجرای لازم تأیید نشده |
| `EVIDENCE_STALE` | کد، تنظیمات، DB یا محیط پس از آخرین شاهد تغییر کرده است |
| `BLOCKED_OWNER_INPUT` | credential، برچسب انسانی، destination یا تصمیم مالک لازم است |
| `BLOCKED_EXTERNAL` | سرویس یا وابستگی خارجی در دسترس نیست |
| `FAILED` | اجرای واقعی شکست خورده و علت ریشه‌ای رفع نشده است |
| `DEFERRED_BY_OWNER` | مالک صریحاً کار را از Scope خارج کرده است |
| `NOT_APPLICABLE` | قابلیت با معماری/نیاز مصوب پروژه ارتباطی ندارد و دلیل ثبت شده است |

## 2.2. ممنوعیت درصدسازی

در این نقشه‌راه درصد کلی پیشرفت نساز. به‌جای آن برای هر Work Package این موارد را گزارش کن:

- تعداد معیارهای پذیرش کل.
- تعداد معیارهای پاس‌شده.
- تعداد معیارهای شکست‌خورده.
- تعداد موارد `NOT_VERIFIED`.
- تعداد موارد `BLOCKED`.
- شواهد و SHA هر نتیجه.

وجود ۱۰۰٪ کد به معنی ۱۰۰٪ عملکرد واقعی نیست.

---

# 3. سیاست‌های قطعی محصول که نباید خودسرانه تغییر کنند

## 3.1. ثبت‌نام و مدیریت حساب

- ثبت‌نام عمومی کاربران آزاد باشد.
- کاربر بتواند با Email معتبر، Username معتبر و Password مطابق سیاست امنیتی پروژه حساب بسازد.
- مدیر سیستم نیز باید امکان ساخت حساب کاربری از مسیر مدیریتی مجاز را داشته باشد؛ این قابلیت را به ایجاد اولین Admin از CLI محدود نکن.
- ایجاد اولین Admin/Bootstrap اولیه می‌تواند از CLI امن و با `getpass` انجام شود، اما **مدیریت و ساخت حساب‌های کاربران توسط Admin** یک قابلیت جداگانه و لازم است.
- سیاست قطعی مالک: ثبت‌نام عمومی برای کاربران آزاد باشد و Admin نیز از پنل/مسیر مدیریتی دارای RBAC بتواند حساب جدید بسازد. این دو مسیر باید مستقل، audit‌شده و دارای validation باشند.
- نقش کاربر از Registration Request، Query، localStorage یا API Key قابل ارتقا نباشد.
- تعیین نقش‌های بالاتر فقط با Permission واقعی Backend، Audit و سیاست مصوب انجام شود.
- API Key برای حساب انسانی و Login UI استفاده نشود؛ در صورت نیاز فقط برای Service Integrationهای مجاز باقی بماند.
- سیاست فعلی Session حفظ شود. گزارش‌ها Session کاربر عادی حدود ۳۰ روز و Admin حدود ۳۶۵ روز را ثبت کرده‌اند؛ پیش از هر تغییر، کد و قرارداد جاری را بخوان. `expires_at=NULL` یا نشست Admin بدون انقضا را بدون تصمیم صریح مالک ایجاد نکن.
- Email Verification واقعی باشد؛ اگر SMTP تنظیم نیست، وضعیت `EMAIL_DELIVERY_NOT_CONFIGURED` نمایش داده شود. تأیید ساختگی ممنوع.

## 3.2. UI و فایل‌های مرجع مالک

- هر HTML/UI Mockup ارائه‌شده توسط مالک، Reference/Design Source محسوب می‌شود و نباید کورکورانه جایگزین کل Frontend شود.
- فایل‌های UI مرجع، فایل Auth انیمیشنی و فایل WorldMonitor/Map در صورت وجود باید دقیقاً شناسایی، Hash و Protected شوند.
- طراحی مرجع باید به Component/Routeهای Frontend واقعی پروژه منتقل شود؛ HTML خام نباید به‌عنوان یک Frontend موازی و جداگانه باقی بماند، مگر آنکه معماری فعلی صریحاً چنین چیزی را نیاز داشته باشد.
- Backend، Auth، API، DB، Dispatch و Business Logic موجود نباید برای شبیه‌سازی ظاهر Mockup بازنویسی شوند.
- مالک در نسخهٔ ۲٫۲ حذف Legacy UI را به‌صورت کلی تأیید کرده است؛ بنابراین برای هر فایل Legacy UI که با dependency/import/route/config/runtime audit قطعاً بدون مصرف تشخیص داده شود، پس از backup و ثبت exact path + SHA می‌توان حذف محدود انجام داد و تأیید مجدد تک‌فایل لازم نیست.
- این اجازه شامل `SHARED`, `NEW_UI_PROTECTED`, `UNKNOWN_PROTECTED`, test fixtures، فایل‌های مرجع UI، Backend/API، مدل‌ها، Migrationها، داده‌ها و هر فایل دارای consumer فعال نیست. موارد مبهم فقط گزارش شوند.

## 3.3. هوش مصنوعی

- تمام فراخوانی‌های AI از AI Gateway موجود عبور کنند.
- Free Policy، Budget، Retry، Fallback و Secret Management دور زده نشوند.
- Mock و Real همیشه جدا گزارش شوند.
- هیچ Provider پولی بدون مجوز و Budget مصوب به‌صورت fallback پنهان فعال نشود.
- Kev/Laya تا پذیرش Gold Set فقط Advisory باشند و هرگز Ground Truth انسانی تلقی نشوند.


### 3.3.1. وضعیت Credentialهای AI که مالک اعلام کرده است

- چهار credential مربوط به Gemini، OpenRouter، Groq و Cloudflare طبق اعلام مالک در `.env` محلی موجودند.
- AI باید `.env` را در محیط محلی بررسی کند، اما مقدار Secret را هرگز چاپ، در report کپی، در prompt ذخیره یا در Git ثبت نکند.
- برای هر Provider فقط این وضعیت‌ها گزارش شود: `MISSING`, `PRESENT_UNVERIFIED`, `CONNECTIVITY_VERIFIED`, `MODEL_VERIFIED`, `POLICY_APPROVED`, `BILLING_CLASSIFIED`, `ENABLED`.
- وجود API Key به معنی اعتبار، رایگان‌بودن، فعال‌بودن Model یا اجازهٔ هزینه نیست.
- هیچ Provider پولی/دارای billing نامعلوم بدون تأیید سیاست و سقف هزینه فعال نشود.

### 3.3.2. بودجهٔ اولیهٔ مصوب برای شروع محافظه‌کارانه

مالک تعیین سقف بودجه را به AI واگذار کرده است. این سقف‌ها به‌عنوان **حداکثر مجاز اولیه** هستند، نه هدف خرج‌کردن:

| کنترل | مقدار شروع | رفتار |
|---|---:|---|
| Paid calls | خاموش (`AI_PAID_ENABLED=false`) | تا وقتی فعال‌سازی صریح و آگاهانه انجام نشده، هیچ fallback پولی اجرا نشود |
| سقف کل روزانهٔ Paid | `USD 1.00` | مجموع همهٔ Providerها؛ نه سقف جدا برای هر Provider |
| سقف کل ماهانهٔ Paid | `USD 15.00` | سقف سخت ماهانه؛ reset بر اساس ماه تقویمی در timezone پروژه |
| سقف هر درخواست تعاملی پولی | `USD 0.10` | درخواست گران‌تر به‌جای اجرا `BUDGET_APPROVAL_REQUIRED` شود |
| سقف هر Article background پولی | `USD 0.05` | اگر هزینهٔ تخمینی بیشتر است، به مدل Free مجاز route شود یا pending بماند |
| هم‌زمانی درخواست پولی | ۱ | جلوگیری از جهش ناگهانی مصرف و race در Budget |
| مدل/Provider با قیمت نامعلوم | ممنوع | تا ثبت قیمت/شرایط معتبر در catalog، Paid call اجرا نشود |

قواعد اجرایی:
1. اولویت با مدل واقعاً رایگان و policy-verified است؛ رایگان بودن فقط از روی نام Provider حدس زده نشود.
2. همهٔ Providerها از یک Global Budget مشترک تبعیت کنند؛ تقسیم مخفی سقف بین کلیدها ممنوع.
3. قبل از فراخوانی، هزینهٔ بدبینانه reserve شود؛ بعد از پاسخ، usage واقعی settle شود.
4. retry/fallback نیز در Budget محاسبه شود؛ هر retry یک درخواست رایگان فرض نشود.
5. وقتی سقف روزانه/ماهانه پر شد، Paid requests متوقف و jobها با status قابل‌بازیابی `BUDGET_EXHAUSTED` یا معادل فعلی ثبت شوند؛ از Provider پولی دیگر دور نزن.
6. کلیدهای موجود را بدون نیاز دوباره از مالک درخواست نکن. تست connectivity کم‌هزینه و یک‌به‌یک انجام شود؛ تست مدل پولی فقط وقتی مجاز است که Paid calls صریحاً فعال شده باشند.
7. تنظیمات باید در Settings قابل مشاهده و audit باشند؛ تغییر سقف‌ها از سقف مصوب اولیه بالاتر نرود مگر owner approval جدید.

## 3.4. داده، Archive و Retention

- Dedup تشخیص است، نه حذف.
- استقلال Sourceها و شواهد مستقل حفظ شود.
- Archive با Purge دو قابلیت مستقل هستند.
- سیاست Retention قبلاً توسط مالک تعیین شده است؛ آن را از نسخهٔ v1.9 و اسناد/کد فعلی پیدا کن و همان را حفظ/یکپارچه کن. از مالک دوباره سیاست کلی نپرس.
- `ARCHIVE_AUTO_PURGE_ENABLED=false` و `PURGE_DRY_RUN=true` به‌عنوان پیش‌فرض ایمن باقی بمانند؛ Toggle روشن/خاموشی که قبلاً طراحی/درخواست شده حفظ و تکمیل شود، اما مقدار پیش‌فرض خاموش باشد.
- هیچ Event، Claim، Evidence، Forecast، Outcome، Audit، Memory یا Source Provenance بدون سیاست رسمی و تأیید مالک حذف نشود.

## 3.5. محیط اجرا

- هدف این نسخه، اجرای کامل و قابل استفاده روی Windows محلی است.
- VPS و Deployment عمومی خارج از Scope است.
- اجرای پایدار محلی ۲۴/۷، در صورت نیاز محصول، داخل Scope است و باید در Work Package جداگانه آزموده شود.

---

# 4. فهرست دارایی‌های موجود که باید حفظ و دوباره استفاده شوند

در `WP-00` برای هر مورد path، SHA/commit، consumer، تست و وضعیت فعلی را استخراج کن. این فهرست حکم تأیید نهایی نیست؛ حکم «قبل از ساخت مجدد، آن را بررسی و reuse کن» است.

| ID | دارایی موجود گزارش‌شده | سیاست |
|---|---|---|
| KEEP-01 | FastAPI App Factory و Modular Monolith | حفظ؛ فقط Gap اثبات‌شده اصلاح شود |
| KEEP-02 | SQLAlchemy Models و Alembic chain | حفظ؛ Migration تاریخی rewrite/delete نشود |
| KEEP-03 | Auth، Argon2id، Session، CSRF، RBAC، AuthToken | حفظ و تکمیل سیاست‌های قطعی بخش ۳ |
| KEEP-04 | AI Gateway و Provider adapters | حفظ؛ اتصال واقعی جداگانه ارزیابی شود |
| KEEP-05 | Free Policy، Budget و Credential Encryption | حفظ؛ hidden paid fallback ممنوع |
| KEEP-06 | ArticleDispatch، idempotency، retry و recovery | حفظ؛ concurrency روی PostgreSQL revalidate شود |
| KEEP-07 | Source Bot و Ingestion adapters | حفظ؛ مسیر ingest واحد و real E2E تکمیل شود |
| KEEP-08 | Dedup، MinHash/LSH/Union-Find و cluster | حفظ؛ استقلال منابع از بین نرود |
| KEEP-09 | Priority و relevance logic | حفظ؛ این دو تصمیم مستقل بمانند |
| KEEP-10 | Kev/Laya local screening و tri-state | حفظ؛ فقط Advisory تا پذیرش Gold Set |
| KEEP-11 | Event، Claim، Evidence، Entity و Graph | حفظ؛ lineage و صحت اتصال‌ها اثبات شود |
| KEEP-12 | Memory raw/event/state و Timeline | حفظ؛ مصرف مؤثر در تحلیل تکمیل شود |
| KEEP-13 | ZIP Archive، manifest و checksum | حفظ؛ restore و Telegram round-trip تکمیل شود |
| KEEP-14 | Retention dry-run و disk monitoring | حفظ؛ حذف خودکار خاموش بماند |
| KEEP-15 | World Map، WorldState history و ingest stats | حفظ؛ Runtime و داده واقعی revalidate شوند |
| KEEP-16 | Frontend و ۲۵ صفحهٔ گزارش‌شده | حفظ؛ تعداد واقعی و عملکرد هر صفحه کشف شود |
| KEEP-17 | CI سه‌Job و E2E محلی گزارش‌شده | حفظ؛ کیفیت و اجرای فعلی revalidate شود |
| KEEP-18 | n8n workflowهای موجود | حفظ؛ غیرفعال بودن پیش‌فرض تا بررسی مسئولیت و Approval |

ساخت Auth دوم، Gateway دوم، Pipeline موازی، Queue دوم، Dedup engine دوم، UI موازی یا Archive/Purge مستقل ممنوع است.

---

# 5. معماری شناسه‌ها و ترتیب کلان اجرا

نسخهٔ ۲٫۰ از `F00`, `F13` و `Stage 96–104` به‌شکلی استفاده می‌کرد که با شناسه‌های قدیمی F-13/F-20/F-23 اشتباه می‌شد. از این نسخه به بعد:

- شناسهٔ Work Package: `WP-00` تا `WP-18`.
- شناسهٔ باگ/بدهی: `GI-SEC-###`, `GI-DB-###`, `GI-AI-###`, `GI-UI-###`, `GI-DATA-###`, `GI-OPS-###`, `GI-TEST-###`, `GI-DOC-###`.
- `Stage 96–104` فقط به‌عنوان شناسهٔ تاریخی نقشه‌راه قبلی نگهداری شود.
- F-xx قدیمی فقط Historical Alias است؛ هرگز به‌عنوان ID جدید استفاده نشود.

## 5.1. ترتیب Work Packageها

| ترتیب | شناسه | عنوان | وابستگی اصلی |
|---:|---|---|---|
| 0 | WP-00 | Read-only Reconciliation | ندارد |
| 1 | WP-01 | حفاظت Working Tree و Secret Hygiene | WP-00 |
| 2 | WP-02 | Revalidation فنی، PostgreSQL، Tests و CI | WP-01 |
| 3 | WP-03 | UI Inventory، Design References و Manifest | WP-00 |
| 4 | WP-04 | Auth و مدیریت حساب‌ها | WP-02 و WP-03 |
| 5 | WP-05 | تکمیل UI و اتصال ۲۵ صفحه | WP-02 تا WP-04 |
| 6 | WP-06 | Configuration Control Plane و Settings | WP-02 و UI foundation |
| 7 | WP-07 | AI Provider/Model Catalog و تست واقعی Gateway | WP-06 |
| 8 | WP-08 | اعتبارسنجی Gold Set موجود و Screening Evaluation | مسیر `H:\GIRuntime\labeling`؛ ابتدا validation |
| 9 | WP-09 | Ingestion مرکزی و Source Management | WP-02 و WP-06 |
| 10 | WP-10 | امنیت Adapter، SSRF و محدودیت شبکه | WP-09 و WP-07 |
| 11 | WP-11 | Dedup، Provenance، Priority و Relevance | WP-09 و WP-10 |
| 12 | WP-12 | Durable Jobs، Dispatch، Retry و Recovery | WP-02 و WP-09 تا WP-11 |
| 13 | WP-13 | تحلیل End-to-End و تکمیل هوشمندی | WP-07، WP-08 و WP-12 |
| 14 | WP-14 | Operations، Alerts، Country Profile و Translation | WP-05 تا WP-13 بر حسب قابلیت |
| 15 | WP-15 | Archive، Restore و Retention | WP-12 و WP-14 |
| 16 | WP-16 | اجرای پایدار ۲۴/۷ روی Windows | WP-02، WP-05، WP-12 و WP-14 |
| 17 | WP-17 | Technical Debt، Security Hardening و Docs | بر اساس Gapهای اثبات‌شده |
| 18 | WP-18 | Local Product Acceptance نهایی | تمام Work Packageهای در Scope |

**قانون:** ترتیب جدول، ترتیب وابستگی کلان است. اگر یک substage مستقل آماده است، فقط پس از ثبت دلیل و بدون دور زدن وابستگی‌های فنی اجرا شود. کارهای مسدودشدهٔ مالک مانع کارهای مستقل نیستند.

---

# 6. WP-00 — ممیزی فقط‌خواندنی و تطبیق وضعیت واقعی

## هدف
ثبت وضعیت واقعی Repository، DB، Runtime، UI و نقشه‌راه، بدون تغییر در هیچ‌چیز.

## اقدامات

1. Repository root واقعی را پیدا و ثبت کن؛ مسیرهای گزارش را فرض نکن.
2. این موارد را بخوان:
   - `git rev-parse --show-toplevel`
   - `git status --porcelain=v2 --branch`
   - `git branch --show-current`
   - `git rev-parse HEAD`
   - `git log -10 --oneline --decorate`
   - `git diff --stat`
   - `git diff --cached --stat`
3. فهرست exact فایل‌های staged، modified، untracked و فایل‌های محافظت‌شده را تولید کن.
4. مسیر خارجی `H:\GIRuntime\labeling` را که مالک اعلام کرده، فقط‌خواندنی inventory کن؛ path existence، file list، extensions، sizes و record count را ثبت کن. اصل فایل‌ها را تغییر نده.
5. وجود متغیرهای شناخته‌شدهٔ SMTP و چهار Provider را در `.env` فقط به‌صورت `SET/MISSING` بررسی کن؛ هیچ value، username، token یا password را چاپ نکن. محتوای `.env` را در گزارش paste نکن.
6. Remote tracking را فقط بخوان؛ pull/fetch/push نکن.
7. فایل‌های نقشه‌راه و گزارش موجود را بخوان؛ از جمله v1.9 در صورت وجود، `ROADMAP_STAGE96_104.md`, `FIXES_BACKLOG.md`, `TASKS.md`, `PROGRESS.md`, `PRODUCTION_READINESS.md`, `STAGE_STATUS.md`, `AGENTS.md` و Manifest رابط کاربری.
8. فهرست واقعی این موارد را با دستور ثابت استخراج کن:
   - Python file count در scopeهای جداگانه.
   - Domain directory/module count.
   - Router file count، Router object ثبت‌شده در App، route/method واقعی در OpenAPI.
   - Migration file، Revision، Head و Current revision.
   - Test file، function، class، collected test case و parametrized case.
   - Provider adapter module، provider kind، local runtime و model record.
   - UI route/page، HTML line count و تعداد callsiteهای API.
9. نسخهٔ Python، Node، Docker، Compose و PostgreSQL را ثبت کن.
10. سرویس‌ها، پورت‌ها، کانتینرها، Volumeها، DB target و UI entrypoint را فقط‌خواندنی inventory کن؛ هیچ‌کدام را متوقف/حذف نکن.
11. دیتابیس مورد استفاده را با روش فقط‌خواندنی شناسایی کن: host، database name، schema، migration current و نوع محیط. مقدار secret/DSN کامل را چاپ نکن.
12. نام جدول‌ها و ستون‌ها را از Schema واقعی کشف کن؛ سپس count فقط‌خواندنی برای Source، Document، Article، Dispatch، JobRun، Event، Claim، Evidence، Memory، Provider، Model، Alert، AlertDelivery و Archive اجرا کن. اگر اتصال ممکن نیست، `NOT_VERIFIED` ثبت کن؛ به دیتابیس دیگری حدساً وصل نشو.
13. برای هر قابلیت، Implementation/Integration/Runtime/User Acceptance/Safety را جداگانه تعیین کن.
14. Stageها و Gapها را با شواهد فعلی reconcile کن.
15. P0/P1 و اولین substage قابل اجرا را مشخص کن.
## ممنوعیت‌های WP-00

- هیچ فایل یا Manifest را ویرایش نکن.
- هیچ تست، Build، Migration یا Seed اجرا نکن.
- هیچ دیتابیس، Volume، container یا سرویس را mutate نکن.
- هیچ Secret را در خروجی چاپ نکن.

## خروجی و پذیرش

گزارش باید root، Branch، HEAD، Working Tree، protected files، آمار قابل بازتولید، وضعیت DB/Runtime، Stage ledger، تناقض‌ها، blockers و **فقط یک substage بعدی** را مشخص کند.

---

# 7. WP-01 — حفاظت تغییرات محلی و Secret Hygiene

## هدف
جلوگیری از از دست‌رفتن کار مالک و تعیین تکلیف Secretهای بالقوه افشاشده.

### WP-01.1 — حفاظت Working Tree

1. وضعیت فعلی را با WP-00 تطبیق بده؛ اعداد تاریخی ۶ Modified + ۲ Untracked را فرض نکن.
2. تمام Diffها را کامل بخوان و هر فایل را با دستهٔ `OWNER_WORK`, `PROJECT_CHANGE`, `GENERATED`, `UNKNOWN_PROTECTED` مشخص کن.
3. فایل‌های Modified/Untracked را بدون اجازه حذف، reset، rename یا overwrite نکن.
4. از تغییرات ارزشمند Snapshot/Backup قابل‌بازیابی همراه SHA-256 تهیه کن؛ مسیر و checksum را ثبت کن.
5. فایل Secret خام، `.env` و credential را در Backup عمومی/گزارش کپی نکن.
6. Scriptهای patch مثل `fix_alerts_router.py` و `fix_ui.py` را قبل از بررسی Diff و impact اجرا نکن.

### WP-01.2 — Secret Hygiene

1. مالک اعلام کرده SMTP Gmail در `.env` محلی تنظیم و قبلاً تست شده است؛ این وضعیت را `OWNER_REPORTED_CONFIGURED_AND_TESTED` ثبت کن.
2. App Password در گفتگو افشا شده؛ آن را `COMPROMISED` فرض کن. AI حق خواندن/چاپ/تکرار مقدار را ندارد.
3. مالک باید App Password افشاشده را در Google Account باطل کند و credential تازه بسازد. فقط این اقدام مشخص نیازمند مالک است.
4. پس از چرخش، مالک credential جدید را فقط در `.env` محلی جایگزین می‌کند. AI فقط وجود متغیرها را به‌صورت SET/MISSING بررسی می‌کند.
5. Git history، working tree، logs، backups، test outputs و docs را برای Secret بررسی کن؛ مقدار پیدا‌شده را چاپ نکن. اگر سابقهٔ Git حاوی credential است، فقط گزارش امن بده؛ history rewrite/push ممنوع است.
6. پس از rotate، ارسال آزمایشی محدود را با sink/recipient مشخص و بدون افشای token انجام بده. تا تست تازه، نتیجهٔ قدیمی صرفاً `OWNER_REPORTED_TEST_SUCCESS` است.
7. اگر مالک چرخش را هنوز انجام نداده، فقط SMTP live re-test را `BLOCKED_OWNER_CREDENTIAL_ROTATION` ثبت کن؛ سایر کارها را ادامه بده.
8. تمام logs، reports و exports باید secret-redaction داشته باشند.

### WP-01.3 — Lint و محافظت کد محلی

1. Ruff را روی Working Tree اجرا کن.
2. اگر چهار خطای گزارش D هنوز وجود دارند، فایل و خط دقیق، علت و ارتباط با تغییر محلی را مشخص کن.
3. فقط همان خطاها را با حداقل Diff رفع کن؛ کد سالم اطراف را بازنویسی نکن.
4. scope واقعی CI را اجرا کن؛ در گزارش‌ها `backend domains tests scripts source_bot` ذکر شده است، اما فرمان نهایی را از CI فعلی بخوان.
5. `git diff --check` و Secret Scan را اجرا کن.

## پذیرش WP-01

- همهٔ local/untracked files شناسایی و حفظ شده‌اند.
- Snapshot قابل‌بازیابی از تغییرات مجاز موجود است.
- هیچ Secret در خروجی/گزارش/Backup جدید افشا نشده است.
- Secret افشاشده rotate شده یا blocker مالک ثبت شده است.
- Lint روی Working Tree پاک است یا failure دقیق و بدون پنهان‌کاری ثبت شده است.

---

# 8. WP-02 — تثبیت فنی، PostgreSQL، Migration، Tests و CI

## هدف
پذیرش مجدد Stage 96 روی SHA فعلی، بدون تکرار بی‌دلیل Fixهای تاریخی.

### WP-02.1 — Inventory و Collection تست

1. `pytest --collect-only` اجرا کن و test file/function/class/case/parametrization را جداگانه ثبت کن.
2. اختلاف ۱۶۵۳ تابع static و ۱۸۱۴ test case گزارش تاریخی را با خروجی واقعی توضیح بده.
3. اختلاف ۳۷/۱۵۴ فایل تست را با root و include/exclude دقیق حل کن.
4. تعداد تست را به یک دستور قابل‌بازتولید وصل کن؛ عدد Hard-coded در docs مرجع نباشد.

### WP-02.2 — PostgreSQL و Dispatch

1. از DB آزمایشی PostgreSQL 16 استفاده کن؛ DB ارزشمند را reset نکن.
2. `alembic heads`, `alembic history`, `alembic current` و Revision graph را ثبت کن.
3. تعداد migration file، revision و head را جداگانه اعلام کن.
4. migration up/down/up فقط روی DB disposable اجرا شود؛ اگر Migration غیرقابل‌rollback است، دلیل را ثبت و با restore آزمایشی جایگزین کن.
5. اطمینان حاصل کن تست PG واقعاً به PG وصل است؛ وجود متغیر `DATABASE_URL` کافی نیست.
6. `test_claim_is_atomic` و concurrency واقعی روی دو Session/Worker اجرا شود.
7. اگر `SKIP LOCKED`/atomic claim موجود و سالم است، آن را بازنویسی نکن.
8. crash، retry، stale lease، FK، unique constraints و transaction boundary بررسی شوند.

### WP-02.3 — تست‌های تاریخی PG

موارد تاریخی F-02 تا F-11 و F-20/F-23 را فقط در صورت ارتباط با کد فعلی یا Evidence Stale بررسی کن:

- PostgreSQL deadlock در Dispatch.
- DNS mock و DSN/NullPool در تست Settings.
- Foreign Key در تست missing article.
- SQLite-specific assertions.
- Offline DNS guard در source_bot.
- CWD-dependent tests.
- Windows temporary-directory isolation.
- `SKIP LOCKED`/atomic claim.
- JobRun uniqueness و race.
- ETag/Last-Modified persistence.

تست را حذف، Skip یا ضعیف نکن تا سبز شود. FK و DNS guard را خاموش نکن. افزایش Timeout فقط با Root Cause مجاز است.

### WP-02.4 — CI و E2E

1. Workflow جاری را بخوان و Jobهای واقعی را کشف کن؛ گزارش تاریخی سه Job را فرض نکن.
2. Backend lane باید full suite را واقعاً روی PostgreSQL اجرا کند.
3. SQLite lane فقط مکمل compatibility است.
4. Migration verification روی PostgreSQL واقعی انجام شود.
5. Frontend lint/typecheck/build باید با package/config موجود اجرا شوند.
6. Playwright critical E2E باید در CI اضافه یا وضعیت عدم امکان آن با دلیل و تصمیم مالک ثبت شود.
7. CI remote تنها پس از Push مالک قابل تأیید است؛ تا آن زمان `BLOCKED_OWNER_PUSH / NOT_VERIFIED` بماند.
8. هر Test Run به Branch و SHA دقیق متصل شود.

## پذیرش WP-02

- Full Suite PG روی SHA مورد پذیرش، صفر failure.
- SQLite lane با نتیجهٔ مستقل.
- Migration chain دارای یک Head و تست واقعی روی DB disposable.
- E2E critical در CI یا استثنای مستند و تأییدشده.
- تعداد Test caseها قابل توضیح و بازتولید.
- Remote CI فقط در صورت مشاهدهٔ Run همان SHA، `VERIFIED` شود.

---

# 9. WP-03 — UI Inventory و اتصال طراحی HTML مرجع مالک

## هدف
یک رابط کاربری اصلی، یکپارچه، فارسی/RTL و متصل به Backend واقعی ایجاد شود؛ نه چند UI موازی یا چند صفحهٔ نمایشی.

### WP-03.1 — حفاظت و کشف UI

1. تمام فایل‌های UI، HTML Mockup، Auth Reference، WorldMonitor/Map Reference، assets، CSS، route، components و UI legacy را از Repository و پوشهٔ کاری کشف کن.
2. برای هر فایل SHA-256، path، source، مالکیت، کاربرد و status ثبت کن.
3. دسته‌بندی:
   - `NEW_UI_PROTECTED`
   - `OWNER_REFERENCE_PROTECTED`
   - `LEGACY_UI_CANDIDATE`
   - `SHARED`
   - `TEST_FIXTURE`
   - `UNKNOWN_PROTECTED`
4. هیچ Mockup مرجع را به‌عنوان Runtime نهایی فرض نکن؛ هیچ‌کدام را نیز حذف/بازنویسی نکن.
5. یک `UI_MIGRATION_MANIFEST` یا معادل موجود را تکمیل کن.

### WP-03.2 — Page/API Inventory

برای تمام صفحه‌های موجود checkout، این ماتریس را بساز:

`page_id | route | component/file | reference_html_section | backend_endpoint | method | request_schema | response_schema | auth/role | loading | empty | error | action | test | current_status | gap`.

صفحه‌های گزارش‌شده شامل موارد زیرند؛ تعداد و نام واقعی را از کد کشف کن، نه اینکه فهرست را کورکورانه تحمیل کنی:

`overview`, `ai-analysis`, `ai-chat`, `debate`, `evaluation`, `evidence`, `entity-graph`, `forecasts`, `risk`, `decisions`, `inbox`, `world`, `geopolitics`, `iran`, `macro`, `markets`, `portfolio`, `screening`, `sources`, `providers`, `operations`, `alerts`, `archive`, `reports`, `settings`.

هر API call باید از نظر Auth، validation، permission، response handling، loading، empty، error، retry و audit بررسی شود. شمارش ۹۴ call تاریخی را تعداد اتصال واقعی تلقی نکن.

### WP-03.3 — قرارداد Design Integration

- HTMLهای طراحی مالک را به‌عنوان Reference دقیق بصری/تعاملی بخوان.
- ساختار، layout، theme، RTL، navigation، chart/map behavior و Auth reference را به Componentهای Frontend موجود منتقل کن.
- Backend API، DB و منطق موجود را به‌خاطر طراحی جدید تغییر نده، مگر contract gap مشخص باشد.
- CSS/JS inline را فقط در صورت وجود دلیل مهاجرتی و با تغییرهای محدود به ساختار قابل نگهداری تبدیل کن.
- از ساخت یک UI دوم در مسیر دیگری خودداری کن.
- بخش‌های فاقد Backend نباید با داده ساختگی فعال نشان داده شوند.

## پذیرش WP-03

- همهٔ صفحات فعلی Inventory شده‌اند.
- تمام Reference HTMLهای مالک حفظ شده‌اند.
- هر صفحه API/permission/status/gap مشخص دارد.
- مسیر اصلی UI و مسیر Legacy مشخص‌اند.
- هیچ فایل UI محافظت‌شده حذف یا overwrite نشده است.

---

# 10. WP-04 — Auth، ثبت‌نام عمومی و مدیریت حساب

## هدف
چرخهٔ امن و کامل ورود، ثبت‌نام، تأیید ایمیل، بازیابی حساب و مدیریت کاربران تکمیل شود؛ Backend Auth موجود حفظ شود.

### WP-04.1 — Backend Auth Audit

مدل‌ها، endpointها، middleware، permission matrix و token/session فعلی را پیدا کن. سیستم Auth دوم نساز.

حداقل گردش‌های بررسی:

- Register عمومی.
- Login با Email یا Username.
- Logout و revoke session.
- `me` و account profile.
- Email verification و resend.
- Forgot username/password، reset password و change password در صورت وجود قرارداد.
- Admin bootstrap.
- Admin-created account.
- Role management.

### WP-04.2 — سیاست حساب‌ها

- Registration عمومی باز باشد.
- Admin بتواند از پنل مدیریتی حساب کاربری بسازد.
- کاربر عادی نتواند role خود را افزایش دهد.
- ثبت‌نام عمومی نباید بتواند Admin بسازد.
- ایجاد اولین Admin از CLI امن قابل استفاده است؛ این مسیر جایگزین Admin User Management نیست.
- ایجاد/غیرفعال‌سازی/تغییر نقش کاربر توسط مدیر باید Permission، Confirmation و Audit داشته باشد.
- اگر سیاست ایجاد Admin دوم مشخص نیست، آن عملیات را به Owner-only محدود کن و تصمیم را ثبت کن؛ خودسرانه نقش Admin صادر نکن.

### WP-04.3 — Session/Password/Verification

- Argon2id یا مکانیزم فعلی حفظ شود.
- Session cookie برای UI؛ API Key فقط برای Service Integration مجاز.
- CSRF برای state-changing requests.
- Sessionهای کاربر عادی و Admin مطابق policy فعلی، نه مدت دلخواه جدید. مقدار تاریخی گزارش‌شده: ۳۰ روز کاربر عادی و ۳۶۵ روز Admin؛ کد فعلی را بررسی کن.
- Session بدون انقضا نساز مگر مالک صریحاً تصمیم امنیتی جدیدی داده باشد.
- Verify token یک‌بارمصرف، زمان‌دار و hash شده باشد.
- SMTP unavailable باید خطای قابل فهم بدهد؛ موفقیت جعلی ممنوع.
- Unverified user فقط به Verify/Account محدود/resend/logout دسترسی داشته باشد.
- Backend تمام APIهای Data/Analysis/Settings را enforce کند؛ مخفی‌سازی UI کافی نیست.

### WP-04.4 — Auth UI

- Design Reference احراز هویت مالک حفظ و integrate شود.
- Login: Email/Username + Password؛ Login با API Key برای کاربر انسانی ممنوع.
- Register: Email، Username، Password، Confirm Password.
- Field-level errorهای فارسی و پیام‌های عمومی امن.
- Forgot/Reset/Verify/Account و Admin user management متصل به API واقعی.
- animation سبک، reduced-motion، mobile، keyboard و RTL/LTR.

### WP-04.5 — تست‌های الزامی

Anonymous/verified/unverified/admin/service، API_KEY خالی/غیرخالی، Session معتبر/منقضی/revoked، CSRF، Register، duplicate account، Password policy، Verify token، SMTP unconfigured، resend/reset، Admin create user، Role escalation، Rate limit، Logout و Playwright end-to-end.

## پذیرش WP-04

کاربر جدید به‌صورت عمومی حساب بسازد، تأیید واقعی را انجام دهد و وارد برنامه شود؛ Admin بتواند حساب جدید بسازد؛ Permissionها در Backend enforce شوند؛ هیچ راهی برای ارتقای نقش از سمت کاربر وجود نداشته باشد؛ Session policy فعلی حفظ شود.

---

# 11. WP-05 — تکمیل رابط کاربری و اتصال واقعی تمام صفحات

## هدف
هر صفحه‌ای که در Scope نهایی محصول قرار می‌گیرد، باید یک گردش کار واقعی و قابل استفاده داشته باشد. ظاهر دکمه یا تعداد API call به‌تنهایی پذیرش نیست.

برای هر صفحه این چرخه اجرا شود:

`User Action → Frontend Validation → Backend API → Authorization → Business Logic → Database/Provider → Response → UI State → Audit/Trace`.

## 11.1. حداقل گردش‌کارهای صفحات

| صفحه/حوزه | گردش‌کار مورد انتظار |
|---|---|
| Overview | KPI واقعی، Health، Freshness، Ingestion Funnel، Queue و Alerts؛ Drill-down |
| AI Analysis | انتخاب Article/Domain، اجرای تحلیل مجاز، نمایش نتیجه و Attribution |
| AI Chat | فراخوانی AI Gateway، تاریخچه، Usage، Error و Permission |
| Debate | اجرای موتور واقعی Debate، ذخیره Run، نمایش موافقت/اختلاف و Evidence |
| Evaluation | Dataset/Version، اجرای Evaluation، Metrics و Limitations |
| Evidence | Claim، شواهد موافق/مخالف، Source و Verification status |
| Entity Graph | Node/Edge واقعی، Lineage، فیلتر و Detail |
| Forecasts | Target/Horizon، Assumptions، Uncertainty، Outcome state |
| Risk | Risk assessment واقعی یا `NO_DATA` صریح |
| Decisions | Decision، Rationale، Alternatives، Evidence و Approval state |
| Inbox | Article واقعی، Search/Filter/Sort/Pagination و Detail |
| World | WorldState، Timestamp و Regime واقعی |
| Geopolitics | تحلیل و پیوند Source/Event/Entity |
| Iran/Country | تحلیل ایران از طریق Country Profile؛ بدون شکستن رفتار فعلی ایران |
| Macro | Macro observation، Unit، Period، Source و Assessment |
| Markets | نماد/دوره، قیمت، timestamp، freshness و Source |
| Portfolio | ورودی/خروجی و فرض‌های ریسک؛ بدون داده ساختگی |
| Screening | Relevant/Irrelevant/Uncertain، provenance و Human Review |
| Sources | Draft، Validate، Preview، Test، Enable/Disable و Status |
| Providers | Catalog، Credential status، Model verification، Policy و Usage |
| Operations | Jobs، Dispatch، Failures، Retry، Recovery و Health |
| Alerts | Rules، Evaluation، Channels، Deliveries و History |
| Archive | Eligibility، Build، Catalog، Download، Verify و Restore |
| Reports | گزارش‌های واقعی همراه بازه، نسخه داده و Evidence |
| Settings | Configuration، Credential write-only، User/Session و Integration controls |

اگر صفحه یا قابلیت در محصول فعلی وجود ندارد، آن را با status واقعی `NOT_IMPLEMENTED`, `NEEDS_ADAPTER`, `NO_DATA`, `NOT_CONNECTED` یا `BLOCKED` نشان بده؛ صفحهٔ نمایشی موفقیت جعلی ایجاد نکن.

## 11.2. وضعیت‌های مشترک تمام صفحات

هر صفحه باید stateهای زیر را متناسب با نوع قابلیت داشته باشد:

- Loading/Skeleton.
- Empty/No data.
- Error با پیام فارسی و Request/Correlation ID.
- Offline/Backend unavailable.
- Stale data و زمان آخرین به‌روزرسانی.
- Permission denied.
- Retry در عملیات امن.
- Success فقط پس از پاسخ واقعی Backend.
- Mock/Real indicator.

## 11.3. UI کیفیت و دسترس‌پذیری

- RTL/LTR کامل و نمایش درست اعداد/تاریخ/متن فارسی و انگلیسی.
- Responsive در عرض‌های 360، 390، 768، 1024 و 1440 پیکسل.
- Keyboard navigation، focus visible، label، contrast و reduced-motion.
- جدول‌های بزرگ: pagination سمت سرور در صورت نیاز.
- Chart/Map: timestamp، unit، source، confidence و limitation قابل مشاهده.
- نمودار یا نقشه بدون دادهٔ واقعی، دادهٔ تصادفی نشان ندهد.
- طراحی باید با HTML Reference مالک هم‌خوان باشد؛ Design System موازی ایجاد نشود.

## 11.4. پذیرش UI و Legacy

- route refresh، deep link، back/forward، 403/404 و permission gate.
- Playwright برای گردش‌کارهای حیاتی.
- Visual regression روی صفحات اصلی.
- تمام صفحه‌ها در Manifest status روشن داشته باشند.
- حذف Legacy UI فقط بعد از پذیرش رابط جدید و تأیید صریح مالک روی **مسیرهای دقیق فایل** مجاز است.

---

# 12. WP-06 — Settings و Configuration Control Plane

## هدف
مدیر بتواند تنظیمات Integrationهای پشتیبانی‌شده را از UI مدیریت کند؛ بدون اینکه برای هر تغییر نیاز به ویرایش کد باشد.

## اقدامات

1. Settings API، DB model، encryption، audit، runtime consumer، cache و UI موجود را map کن؛ Store موازی نساز.
2. هر Setting را با این چرخه بررسی کن:
   `Definition → Storage → API → Validation → Test → Activation → Runtime Consumer → Audit → Rollback`.
3. گروه‌های تنظیمات: General، AI Providers، Sources، Email/Telegram، Processing، Scheduling، Archive/Retention، UI Preferences و Access/Security.
4. هر setting بر حسب نیاز type، default، allowed range، sensitive flag، permission، revision، last updated/by، effective runtime state و validation داشته باشد.
5. Secretها write-only و encrypted باشند. GET فقط `configured`, `masked` یا `key_hint` امن برگرداند.
6. مقدار Secret قبلی با Update بدون Secret جدید حفظ شود؛ حذف Secret action صریح و audited باشد.
7. lifecycle: `DRAFT → VALIDATED → TESTED → ACTIVE → DISABLED/ROLLED_BACK`.
8. Save Draft نباید Runtime را تغییر دهد.
9. Test اتصال نباید بدون قصد مالک داده را ingest کند یا پیام واقعی بفرستد.
10. Config revision در ابتدای Job مشخص شود؛ تغییر Config وسط Job باعث رفتار مبهم نشود.
11. Optimistic locking و cache invalidation با revision پیاده شود.
12. برای integration فاقد adapter، `NEEDS_ADAPTER` نمایش داده شود؛ قابلیت ساختگی نساز.

## پذیرش WP-06

حداقل یک Integration موجود از UI، Draft تا Validate، Test، Activate، Runtime consumption و Rollback کامل کار کند؛ Permission، Audit و Secret protection برقرار باشند.

---

# 13. WP-07 — AI Provider/Model Catalog و اجرای واقعی Gateway

## هدف
وجود Adapter، پیکربندی Credential، اعتبار Model، مجاز بودن Policy و پاسخ واقعی Gateway مستقل از هم اثبات شوند.

## اقدامات

1. Gateway، Provider registry، Adapterها، Free Policy، Budget، Credentials Store، Usage و retry/fallback را حفظ کن.
2. ماتریس بساز:
   `adapter_exists | provider_kind | UI_visible | credentials_configured | connectivity_test | model_discovered | model_verified | policy_approved | gateway_task_test | usage_recorded | routing_enabled`.
3. تعداد Provider را به adapter module، provider kind، local runtime و model catalog تفکیک کن؛ عدد ۱۲/۱۳ گزارش‌ها را بدون این تفکیک انتخاب نکن.
4. Kev/Laya را Local Screening Runtime بدان؛ Provider Cloud عمومی محسوب نکن.
5. Provider credential فقط از مسیر امن Settings وارد شود.
6. Connectivity test، Model discovery/verification، Free Policy approval و Gateway task test جدا باشند.
7. Model ID باید از منبع رسمی/کاتالوگ معتبر تأیید شود؛ حدس نزن.
8. Provider جدید ابتدا Draft باشد؛ فعال‌سازی بدون تست و policy ممنوع.
9. تمام درخواست‌ها از Gateway و Free Policy عبور کنند.
10. Mock از Real جدا و در production chain حذف شود.
11. Hidden paid fallback ممنوع؛ در نبود Provider مجاز، status صریح `BLOCKED/PROVIDER_UNAVAILABLE` برگردان.
12. Token/usage واقعی، model/provider، خطا، fallback و Budget ثبت شوند؛ Secret یا raw body افشا نشود.
13. خطاهای 401/403/404/429/5xx، timeout، quota و malformed output تست شوند.
14. OpenAI-compatible custom endpoint فقط با HTTPS، SSRF guard، Secret encryption و adapter مجاز.
15. Catalog refresh کنترل‌شده و Offline cache معتبر داشته باشد.

## پذیرش WP-07

حداقل یک Provider واقعی و مجاز از UI تنظیم شود، Model آن تأیید شود، یک Task واقعی از Gateway اجرا و Usage ثبت شود. چهار credential از پیش اعلام‌شده باید ابتدا از `.env` به‌صورت masked inventory شوند. اگر یکی واقعاً missing/invalid بود، discrepancy دقیق Provider ثبت شود؛ هرگز مقدار Secret در گفتگو درخواست یا چاپ نشود. اگر اصلاح حساب/credential لازم شد، فقط همان اقدام مشخص مالک ارجاع شود؛ Mock نباید جای Real را بگیرد.

---

# 14. WP-08 — اعتبارسنجی و اتصال Gold Set موجود، سپس ارزیابی Kev/Laya/Screening

## وضعیت مالک
مالک اعلام کرده حدود ۲۰۰ برچسب انسانی را قبلاً آماده کرده و فایل‌ها در مسیر محلی زیر قرار دارند:

`H:\GIRuntime\labeling`

بنابراین **جمع‌آوری/برچسب‌گذاری دوباره جزو کارهای پیش‌فرض مالک نیست**. این Stage ابتدا یک Stage کشف و اعتبارسنجی داده است. تنها اگر تعداد نمونه‌های معتبر کمتر از حداقل واقعی harness باشد یا بخشی از داده فاقد label/provenance لازم باشد، کمبود دقیق گزارش شود؛ درخواست کلی برای ۲۰۰ برچسب مجدد ممنوع است.

## اقدامات

1. مسیر `H:\GIRuntime\labeling` را روی کامپیوتر Windows بررسی کن؛ فرض نکن این مسیر زیر Repository است یا در گزارش‌های قبلی دیده شده است.
2. inventory فقط‌خواندنی از فایل‌ها، نوع فرمت، حجم، timestamp، تعداد رکورد و پوشه‌ها بساز. متن خبر و اطلاعات شخصی را در گزارش چاپ نکن.
3. تعداد کل نمونه‌ها، تعداد نمونه‌های دارای label انسانی، تعداد نامعتبر/خالی، duplicateها، وضعیت نامشخص، زبان، کشور، domain، source و توزیع label را جداگانه بشمار.
4. schema و label values را با قرارداد فعلی harness تطبیق بده: `RELEVANT`, `IRRELEVANT`, `UNCERTAIN` یا مقادیر معادل مستندشده. Mapping را بدون حفظ original label و provenance انجام نده.
5. مشخص کن هر label واقعاً human-authored است یا model/rule output؛ فقط برچسب انسانی می‌تواند Gold Ground Truth باشد. اگر metadata annotator وجود ندارد، `OWNER_PROVIDED_HUMAN_LABELS` و limitation را ثبت کن؛ مقدار جعلی برای annotator نساز.
6. فایل‌های مرجع `H:\GIRuntime\labeling` را **هرگز ویرایش، rename، move یا delete نکن**. قبل از هر import، SHA-256 بگیر و original را immutable نگه دار.
7. `backend/ai/evaluation/local_screening.py` و `MIN_LABELED_SAMPLES` واقعی را بخوان. اگر ۲۰۰ نمونهٔ معتبر موجود است، Stage از `BLOCKED_OWNER_LABELS` خارج شود و به import/validation برود.
8. bundle را با `prepare_bundle`, `validate_bundle`, `merge_bundle`, `report` موجود بساز/استفاده کن؛ harness دوم نساز.
9. اگر staging copy لازم است، آن را در مسیر local/gitignored و با حفظ SHA/source mapping بساز؛ دادهٔ خصوصی یا متن کامل خبر وارد Git، public docs یا backup اشتراکی نشود.
10. dataset manifest شامل dataset version، SHA-256، sample IDs، label source، guideline version، زمان تهیه، record count و exclusion reasons باشد.
11. Dev/Tuning و Held-out Final جدا شوند. هیچ نمونهٔ Final برای تنظیم threshold/prompt مصرف نشود.
12. Rules، Kev، Laya و مدل مجاز Gateway روی ورودی یکسان سنجیده شوند؛ Mock/Real و version هر اجرا جدا ثبت شود.
13. Metrics: per-class Precision/Recall/F1، Macro/Weighted F1، Accuracy، Confusion Matrix، abstain/uncertain rate، pending/fallback/failure، False Positive/Negative، latency، RAM/CPU و cost واقعی.
14. عملکرد فارسی و زبان‌های دیگر جدا گزارش شود. اگر dataset پوشش کافی ندارد، ادعای تعمیم نکن.
15. label انسانی و prediction مدل جدا بمانند؛ overwrite ممنوع.
16. دو-annotator agreement فقط اگر دادهٔ دو annotator از قبل موجود است محاسبه شود؛ ایجاد الزام جدید برای annotator دوم نباید کل Stage را متوقف کند. در نبود آن، limitation ثبت شود.
17. Kev/Laya تا پذیرش Gold Set فقط Advisory باشند؛ فعال‌شدن به‌عنوان تصمیم‌گیرنده نیازمند acceptance و approval مستقل است.

## معیار پذیرش

- مسیر منبع اصلی پیدا و بدون تغییر حفظ شده باشد.
- حداقل نمونهٔ معتبر با MIN_LABELED_SAMPLES واقعی مقایسه شده باشد.
- همهٔ labelهای Gold دارای provenance قابل دفاع باشند.
- dataset manifest و SHA قابل بازتولید باشند.
- held-out evaluation و گزارش metrics تولید شده باشد.
- اگر تعداد معتبر کمتر از حداقل باشد، فقط کسری دقیق و علت آن گزارش شود.
- Stage 97 از «منتظر اقدام اولیهٔ مالک» به وضعیت واقعی `VALIDATION`, `READY_FOR_EVALUATION`, `PARTIAL` یا `BLOCKED_DATA_QUALITY` منتقل شود.

## وابستگی مالک

مالک وجود مجموعهٔ برچسب انسانی را اعلام کرده و مسیر دقیق داده را ارائه داده است؛ هیچ کار برچسب‌گذاری جدیدی فعلاً از مالک درخواست نکن. تنها در صورت اثبات کسری واقعی/برچسب نامعتبر، مقدار و علت دقیق کمبود را اعلام کن.
---

# 15. WP-09 — Ingestion مرکزی و مدیریت منابع

## هدف
هر منبع مجاز از مسیر استاندارد ingestion موجود عبور کند؛ مسیر موازی یا SQL مستقیم جدید ایجاد نشود.

## اقدامات

1. تمام ورودی‌ها را inventory کن: Source Bot، RSS، REST، CSV، XML، HTML، API، economic/market fetcher، Job و n8n.
2. Raw Item/Document، Source Registry، BaseFetcher، pipeline، normalizer، store و hookهای موجود را بخوان.
3. fetch/discovery/robots/retry/limits از extraction و persistence تفکیک شود.
4. قرارداد مورد تأیید مالک برای HTML رعایت شود: Scrapy برای fetch/discovery/robots/retry/domain controls؛ Trafilatura فقط روی HTML از قبل دانلودشده و بدون fetch دوم.
5. Raw payload یا reference پایدار پیش از پردازش حفظ شود.
6. metadata واقعی شامل source ID، external ID، original/canonical/final URL، title، text/raw reference، author، language، published/retrieved/processed time، hash، provenance و status باشد؛ فقط فیلدهای سازگار با schema فعلی اضافه شوند.
7. زمان انتشار، زمان دریافت، زمان پردازش و period سری زمانی یکی نشوند.
8. Source validation و preview از Ingestion واقعی جدا باشد؛ Preview نباید تعداد رکوردهای DB را تغییر دهد.
9. یک Source فعال مجاز از Registry تا Document/Article عبور کند.
10. Source failure باید ایزوله و به‌صورت `partial` یا status معادل ثبت شود.
11. Economic/Market observations با News Article یکی نشوند؛ contract مشترک فقط در صورت نیاز فنی.
12. همهٔ ورودی‌های فعال به pipeline واحد وصل یا با دلیل مستند خارج Scope شوند.

## پذیرش WP-09

حداقل یک Source واقعی و مجاز از Registry تا persistence و lineage کامل کار کند؛ rerun duplicate غیرمجاز نسازد؛ Preview هیچ ingest ناخواسته‌ای انجام ندهد.

---

# 16. WP-10 — امنیت Adapter، SSRF و محدودیت شبکه

## هدف
تمام Fetcherها و Custom Endpointها از گارد امنیتی واحد و قابل‌آزمایش عبور کنند.

## اقدامات

- scheme فقط HTTP/HTTPS مجاز؛ userinfo و schemeهای دیگر رد شوند.
- loopback، private، link-local، multicast، reserved، unspecified، metadata و IPهای ممنوع IPv4/IPv6 مسدود شوند.
- همهٔ A/AAAA بررسی شوند.
- DNS rebinding با مکانیزم امن اتصال/pinning یا کنترل معادل مدیریت شود.
- هر Redirect hop دوباره resolve/validate شود.
- تعداد redirect، response bytes، page count، crawl depth، concurrency، timeout، rate و retry محدود شوند.
- Proxy environment نتواند validation را دور بزند.
- TLS verification خاموش نشود.
- XML parser در برابر DTD/XXE امن باشد.
- CSV encoding، delimiter، size و period identity کنترل شود.
- REST pagination، 304، auth، timeout و statusهای 4xx/5xx درست مدیریت شوند.
- HTML extraction روی response دریافت‌شده انجام شود.
- token و query secret در URL/log/output افشا نشود.
- تست عادی Offline باشد؛ Live network test فقط opt-in و با مقصد مجاز انجام شود.

## پذیرش WP-10

SSRF، IPv4/IPv6، redirect-hop، mixed public/private DNS، DNS rebinding simulation، metadata IP، payload حجیم، XXE، timeout، rate limit و No-External-Network tests پاس شوند. Fixهای تاریخی F-08/F-27 فقط در صورت Regression تغییر کنند.

---

# 17. WP-11 — Dedup، Provenance، Priority و Relevance

## 17.1 Dedup

- الگوریتم موجود Shingling/MinHash/LSH/Union-Find را حفظ کن.
- Exact ID، source ID، canonical URL، exact content hash و near duplicate cluster را طبق قرارداد موجود تفکیک کن.
- raw text غیرقابل‌تغییر بماند؛ normalization فقط روی copy برای fingerprint.
- title similarity به‌تنهایی دلیل حذف/ادغام نیست.
- دو Source مستقل برای یک خبر باید provenance مستقل داشته باشند.
- global hash نباید استقلال شواهد را از بین ببرد.
- Revision جدید به‌عنوان Revision/Observation ثبت شود؛ history حذف نشود.
- Time-series identity باید dataset/indicator/period را در نظر بگیرد.
- PostgreSQL concurrent upsert و uniqueness تست شوند.
- UI cluster، اعضا و source lineage را نشان دهد.

## 17.2 Priority

مقادیر P0 تا P4 را از contract فعلی پروژه بخوان. گزارش‌های تاریخی این نگاشت اولیه را آورده‌اند:

- P0: 90–100
- P1: 75–کمتر از 90
- P2: 50–کمتر از 75
- P3: 25–کمتر از 50
- P4: کمتر از 25

این مرزها فقط در صورتی اعمال شوند که config فعلی/تصمیم مالک آن را تأیید کند. یک منبع تنظیمات مرجع داشته باش؛ thresholdهای تکراری نساز.

هر تصمیم باید reason، score/confidence، `decided_by`، rule/model version و timestamp قابل بازیابی داشته باشد.

## 17.3 Relevance

- `RELEVANT/IRRELEVANT/UNCERTAIN` از Priority جدا باشد.
- `relevant=false` معادل P4 نیست.
- `relevant=true` به‌تنهایی P0 ایجاد نمی‌کند.
- Kev/Laya تا پذیرش Gold Set advisory باقی بمانند.
- model unavailable یا confidence ناکافی باعث حذف Article نشود؛ `PENDING/UNCERTAIN` یا status مناسب ثبت شود.
- prompt injection از متن خبر نباید به دستور اجرایی تبدیل شود.

## پذیرش WP-11

Dedup واقعی در ingest، بدون hard delete، با provenance مستقل و Revision حفظ‌شده کار کند. Priority، relevance و analysis attribution مستقل و قابل‌ردیابی باشند.

---

# 18. WP-12 — Durable Jobs، Dispatch، Retry و Recovery

## هدف
منطق موجود `ArticleDispatch` و `JobRun` حفظ شود و رفتار واقعی restart/concurrency قابل‌اثبات باشد.

## اقدامات

1. Service/Runner/claim/recovery و وضعیت‌های `pending`, `running`, `completed`, `retryable`, `terminal`, `blocked` را از کد فعلی بخوان.
2. idempotency و unique constraint موجود حفظ شود.
3. claim اتمیک و PostgreSQL-safe باشد؛ `SKIP LOCKED` موجود را بی‌دلیل بازنویسی نکن.
4. JobRun race تاریخی فقط اگر روی checkout فعلی بازتولید شد اصلاح شود.
5. ETag/Last-Modified را در runtime واقعی revalidate کن؛ اگر adapter دوباره ساخته می‌شود، state باید در مکان پایدار مجاز نگهداری شود.
6. Retry فقط برای خطاهای transient، با سقف، backoff و jitter.
7. Auth، invalid model، invalid schema و permanent error بی‌نهایت retry نشوند.
8. crash/restart باعث Job گمشده یا اجرای تکراری نشود.
9. Job با Config revision ثابت آغاز و تا پایان همان revision را مصرف کند.
10. source failure isolation.
11. endpoint کار سنگین Job ID و Status برگرداند، نه request طولانی.
12. عملیات pause/resume/retry/cancel/recover فقط با Permission و Audit.
13. stale lease، worker kill، retry storm، duplicate request و shutdown امن تست شوند.
14. ابتدا قابلیت موجود in-process را اندازه‌گیری کن؛ Redis/queue خارجی بدون نیاز اثبات‌شده اضافه نشود.

## پذیرش WP-12

دو Worker یک task را دوبار claim نکنند؛ crash/restart باعث loss/duplicate نشود؛ وضعیت و recovery از API/UI دیده شود؛ هیچ pending orphan یا lock leak باقی نماند.

---

# 19. WP-13 — تکمیل هوشمندی و تحلیل End-to-End

## هدف
تحلیل موجود را از ابتدا بازنویسی نکن؛ یک Article واقعی را از ingestion تا خروجی نهایی دنبال کن و Gapهای engine/domain/memory/forecast را ببند.

## 19.1. Data/Analysis Trace

برای یک Article واقعی و مجاز این اطلاعات ثبت شود:

- `source_id`, `document_id`, `article_id`
- job/dispatch IDs
- task name/version/status/attempt
- input/output record IDs
- timestamp و time window
- provider/model/prompt/rule version
- Mock/Real و `decided_by`
- event/claim/evidence/entity/graph IDs
- memory retrieval IDs
- error/retry/block reason

هیچ ID یا خروجی ساختگی وارد گزارش نکن.

## 19.2. Domain Coverage Matrix

تمام Domain directoryهای checkout فعلی را کشف کن؛ فهرست تاریخی گزارش‌ها شامل ai_routing، alerts، analogue، analyses، archive، audit، briefings، claims، country_profile، debate، decision، entities، events، forecast، geo، geopolitics، graph، inbox، iran، learning، macro، markets، memory، narratives، news، ops، portfolio، research، retention، risk، scenarios، selfeval، society، translation و worldstate است. این فهرست را با Repository جاری تطبیق بده.

برای هر Domain ثبت کن:

`domain | code | API | model/persistence | task/handler | scheduler/mode | sources | output/lineage | UI | tests | runtime status | gap | owner/dependency`.

حوزه‌های اولویت‌دار برای بررسی per-article و aggregate:

- Geopolitics
- Society
- Macro
- Markets
- Energy، فقط اگر در Scope و کد فعلی وجود دارد یا مالک تأیید کند
- Iran/Country transmission
- Events/Claims/Evidence
- Risk/Scenarios/Forecast
- Narrative/WorldState

Domainی که aggregate یا scheduled است صرفاً برای پرکردن جدول per-article نشود. Module بدون Handler/Consumer کامل نیست. `NotImplementedError` عمدی باید `NEEDS_ADAPTER` یا `INTENTIONALLY_UNSUPPORTED` داشته باشد، نه success.

## 19.3. Event، Claim، Evidence، Entity و Graph

- extraction و clustering با schema فعلی انجام شود.
- هر Event/Claim/Evidence به Source/Article/Document و provenance متصل باشد.
- corroboration حداقل دو Source مستقل را رعایت کند؛ mention به‌تنهایی corroboration نیست.
- conflicting evidence و uncertainty حفظ شود.
- Graph relationship بدون source lineage ساخته نشود.
- نتیجهٔ تحلیل ناقص یا کم‌شاهد `INSUFFICIENT_EVIDENCE` باشد.

## 19.4. Memory فعال

گزارش‌ها سه لایهٔ raw/event/state و لایه‌های رزروشدهٔ forecast/outcome/model/decision را مطرح کرده‌اند. وضعیت واقعی را از کد فعلی بخوان.

- حافظهٔ موجود حذف یا دوباره ساخته نشود.
- حداقل یک مسیر تحلیل باید از Memory مرتبط و point-in-time استفاده کند.
- query بر اساس `as_of`, time, domain, entity, importance و provenance محدود شود.
- دادهٔ آینده وارد تحلیل گذشته نشود.
- stale، contradicted و uncertain memory صریح باشد.
- retrieval در Analysis Trace ثبت شود.
- history و superseded records overwrite نشوند.

## 19.5. Causal Analysis

ابتدا با جست‌وجوی کد و تست ثابت کن این قابلیت واقعاً وجود ندارد یا ناقص است. اگر Gap تأیید شد، آن را جدا از Correlation، Sentiment و Debate تکمیل کن.

حداقل قرارداد:

- causal question، outcome، factor/treatment و time window
- hypothesis و versioned DAG/causal graph در صورت استفاده
- confounders، assumptions و temporal ordering
- evidence برای هر رابطه
- alternative explanations و falsification criteria
- confidence/uncertainty و identification limitations
- source/claim/event lineage
- status: `HYPOTHESIS`, `SUPPORTED`, `CONTRADICTED`, `INSUFFICIENT_EVIDENCE`

مدل AI حق ندارد از متن خبر رابطهٔ causal قطعی جعل کند. بدون داده/روش کافی فقط hypothesis یا insufficient evidence تولید شود.

## 19.6. Independent Ensemble

ابتدا ثابت کن Ensemble مستقل از Debate فعلی وجود ندارد یا ناقص است. اگر Gap تأیید شد:

- حداقل دو ارزیابی مستقل با provider/model attribution مستقل.
- Gateway و Free Policy واحد.
- ورودی و نسخهٔ task/prompt قابل مقایسه.
- agreement/disagreement/abstention آشکار.
- provider correlation و وابستگی مشترک ثبت شود.
- missing vote ناشی از timeout خطای منفی تلقی نشود.
- aggregation versioned و قابل replay باشد.
- میانگین احتمال بدون calibration مجاز نباشد.
- هیچ Human Label یا Evidence واقعی overwrite نشود.
- budget/latency/privacy اعمال شود.

چند پاسخ از یک Provider یا Model Debate فعلی به‌تنهایی Ensemble مستقل محسوب نمی‌شود.

## 19.7. Forecast، Outcome و Backtesting

### اهداف و افق‌های مصوب مالک

مالک اهداف اصلی را تعیین کرده است؛ این موارد را دوباره از او نپرس:

| حوزه | سری/دارایی آغازین | افق‌های آغازین | تناوب داده/قواعد |
|---|---|---|---|
| طلا | جهانی `XAUUSD`؛ قیمت طلای داخلی فقط به‌صورت سری جدا و با تبدیل FX مشخص | ۱ روز، ۷ روز، ۳۰ روز، ۹۰ روز | قیمت جهانی و قیمت داخلی/سکه با هم مخلوط نشوند؛ زمان بازار و منبع ثبت شود |
| دلار | `USD/IRR` با تفکیک نرخ بازار آزاد، نرخ رسمی و نرخ‌های مرجع؛ هیچ‌کدام جای دیگری را نگیرد | ۱ روز، ۷ روز، ۳۰ روز، ۹۰ روز | منشأ هر نرخ، نوع بازار، timestamp و محدودیت دسترسی/اعتبار صریح باشد |
| نفت | `Brent` و `WTI` به‌عنوان دو سری مستقل | ۱ روز، ۷ روز، ۳۰ روز، ۹۰ روز | قرارداد/نقطهٔ مرجع/واحد و تاریخ سررسید در صورت futures ثبت شود |
| تورم | CPI کل و در صورت وجود دادهٔ معتبر CPI هسته؛ منطقه/کشور جدا | پیش‌بینی انتشار بعدی، ۳ ماه، ۶ ماه، ۱۲ ماه | داده ماهانه است؛ nowcast از پیش‌بینی رقم رسمی انتشار جدا بماند |
| رمزارز | شروع با `BTC` و `ETH`؛ دارایی‌های دیگر پس از بررسی کیفیت داده | ۱ روز، ۷ روز، ۳۰ روز، ۹۰ روز | Spot/reference venue، timezone، missing candle و کیفیت exchange data ثبت شود |

این افق‌ها baseline طراحی هستند. اگر تناوب واقعی داده، market calendar یا source coverage برای یک افق کافی نیست، آن افق `NOT_SUPPORTED_BY_DATA` بماند؛ دادهٔ کم‌تناوب را به دادهٔ پرتواتر تبدیل نکن.

### قرارداد مشترک Forecast

- Forecast دارای target، asset/indicator ID، horizon، issued_at، input data version/timestamp، assumptions، evidence، model/provider/prompt/rule version، probability یا range، uncertainty و due date باشد.
- outcome source of truth و روش resolution پیش از مشاهدهٔ نتیجه تعیین شود.
- walk-forward/rolling backtest؛ random shuffle برای time series ممنوع.
- temporal leakage، look-ahead bias، revision data و survivorship bias کنترل شود.
- baseline ساده و مناسب برای هر سری محاسبه شود.
- MAE/RMSE برای forecast عددی؛ Brier/LogLoss و calibration plot برای probability.
- sample کم با uncertainty و limitation گزارش شود.
- forecast/outcome تاریخی overwrite یا delete نشوند.
- auto-adjust routing/weight فقط پس از minimum sample، held-out evaluation، audit، replay و rollback مجاز باشد.
- خروجی Forecast یک تحلیل احتمالاتی است، نه تضمین قیمت یا دستور معامله؛ confidence و محدودیت منبع باید واضح باشد.

## پذیرش WP-13

حداقل یک Article واقعی و مجاز تا خروجی تحلیل و UI trace شود. Domain Coverage Matrix کامل باشد. Memory در یک تحلیل واقعی مصرف شود. Causal/Ensemble فقط با contract، تست، provenance و limitation پذیرفته شوند؛ در غیر این صورت صادقانه `NOT_STARTED/BLOCKED` باقی بمانند. Forecast calibration بدون outcome واقعی اعلام نشود.

---

# 20. WP-14 — Operations، Alerts، Country Profile، Translation و n8n

این Work Package به زیرمرحله‌های مستقل تقسیم شود؛ در هر نوبت فقط یکی اجرا شود.

## 20.1. Operations و Monitoring

- Source، JobRun، Dispatch، Screening، Provider، Model، AlertDelivery، Archive، Backup و Runtime status از DB/API واقعی خوانده شوند.
- Health: `healthy`, `degraded`, `unavailable` همراه دلیل و timestamp.
- Pending/retryable/blocked/terminal، stale jobs، retry count و duration نمایش داده شوند.
- error summary بدون Secret/raw sensitive payload.
- retry/pause/recover فقط با role و confirmation.
- هر action دستی correlation ID و audit داشته باشد.

## 20.2. Alert Delivery — نگاشت تاریخی Stage 98

- مدل/سرویس `AlertDelivery` و commitهای موجود را reuse کن.
- اختلاف `enabled/active`, `cooldown_seconds/cooldown_hours` و `Alert.status` را با model/schema/router/migration فعلی تطبیق بده.
- scriptهای patch را کورکورانه اجرا نکن.
- side-effect ارسال پیام فقط در POST/action route باشد؛ GET فقط read-only.
- Test Delivery route باید Admin-only و dry-run پیش‌فرض/اجباری باشد.
- Live Test فقط با اقدام صریح Admin، مقصد آزمایشی و credential مالک.
- idempotency، bounded retry، timeout، transient/permanent error و delivery history.
- Telegram و Email جداگانه تست شوند.
- در صورت وجود receipt واقعی، `message_id`/provider receipt ذخیره شود.
- Token/SMTP credential هرگز در URL log، UI یا response نیاید؛ URL Telegram redaction شود.
- UI آخرین وضعیت و خطا را نشان دهد؛ credential presence به معنی اتصال موفق نیست.

**پذیرش:** lint-clean، security-gated، migration-tested و integration-tested. Live delivery فقط با رسید واقعی `VERIFIED` است؛ در غیر این صورت `BLOCKED_OWNER_CREDENTIAL`.

## 20.3. Country Profile — نگاشت تاریخی Stage 99

- model/schema/migration/registry/matching/router فعلی را reconcile کن.
- رفتار Iran profile فعلی حفظ شود.
- generic Country Profile برای sources، languages، aliases، indicators، regions، transmission channels و metadata طبق مدل موجود.
- CRUD با RBAC.
- Source matching و Domain Routing از Profile مصرف کنند.
- کشور دوم طبق تصمیم مالک **ایالات متحده آمریکا (`US`)** است؛ دیگر برای انتخاب کشور سؤال نپرس.
- پروفایل US را با identifiers و metadata معتبر بساز/seed کن؛ هیچ indicator/metric ساختگی ایجاد نکن.
- UI عمومی Country Profile بساز/تکمیل کن؛ صفحه Iran تنها implementation نباشد.
- country metric ساختگی یا بدون source ممنوع.

**پذیرش:** CRUD، matching، parity ایران و کشور دوم، Migration، permission و UI.

## 20.4. Offline Translation — نگاشت تاریخی Stage 101

- TranslationService، cache و Protocol/backend موجود را reuse کن.
- backend واقعی و language pair را از checkout کشف کن.
- mock translation را Real معرفی نکن.
- اگر backend آفلاین واقعی وجود ندارد، `NEEDS_BACKEND` ثبت کن.
- ترجمه فقط derived display content باشد؛ متن اصلی حفظ شود.
- cache key به text hash، source/target language و model/backend version متصل باشد.
- provenance ترجمه ثبت شود.

**پذیرش:** مسیر واقعی ترجمه با cache و attribution یا blocker دقیق.

## 20.5. Source Management UI

- Adapter descriptors از Registry/Backend.
- Wizard: Adapter → Metadata → Auth → Request/Limits → Mapping → Schedule → Validate/Test Fetch → Preview → Save Draft → Activate.
- Preview نباید ingest کند.
- credential write-only.
- SSRF guard از WP-10.
- delete به‌جای hard delete ترجیحاً deprecate باشد تا provenance حفظ شود.

## 20.6. n8n

- همه Workflowهای موجود را از JSON واقعی inventory کن.
- `active:false` به‌تنهایی نقص محسوب نمی‌شود.
- purpose، schedule، auth، retry، overlap با Source Bot/Dispatch و failure isolation بررسی شود.
- هیچ credential در JSON hard-code نشود.
- Workflow بی‌نیاز `INTENTIONALLY_DISABLED` با دلیل ثبت شود.
- فعال‌سازی تک‌به‌تک، محدود، ابتدا dry-run و فقط با approval مالک.
- n8n صف موازی یا Source of Truth مستقل نسازد.

---

# 21. WP-15 — Archive، Telegram، Restore و Retention

## 21.1. حفظ Archive

- Archive ZIP، manifest، checksum، eligibility، validation، catalog و security checks موجود reuse شوند.
- محتویات ZIP را از کد واقعی استخراج کن؛ عدد ۹/۱۰ فایل تاریخی را فرض نکن.
- path traversal، zip bomb، compression ratio و entry-size safeguards حفظ شوند.
- archive version، archive ID، timestamp، item count، omitted reasons، checksums و schema/app version ثبت شوند.
- Secret و credential هرگز در Archive نباشند.

## 21.2. Eligibility و Protected Records

Eligibility موجود را از کد بخوان: classification، active dispatch، document/raw text/hash، provenance، event reference، importance، screening metadata و uncertainty.

P0/P1، high uncertainty، Event، Claim، Evidence، Forecast، Outcome، Audit، AI logs، Memory، WorldState و lineage باید طبق policy از purge محافظت شوند.

## 21.3. Telegram Archive

- Telegram archive از Alert notification جداست.
- destination private/channel فقط با تأیید مالک.
- Bot Token write-only و encrypted.
- upload receipt شامل message/file ID، timestamp، size، checksum و archive version.
- split parts دارای manifest/checksum مستقل.
- retry قابل‌تطبیق با receipt؛ duplicate upload کنترل شود.
- stateهای catalog از کد فعلی استخراج و تکمیل شوند.

## 21.4. Download/Verify/Restore

1. archive از catalog انتخاب شود.
2. remote metadata تطبیق داده شود.
3. فایل دوباره دریافت شود.
4. checksum تمام parts و package بررسی شود.
5. ZIP و Manifest validate شوند.
6. restore فقط به DB sandbox؛ هرگز روی live DB overwrite نکن.
7. row count، ID، hash، relationship و provenance با Snapshot مقایسه شوند.
8. corruption/mismatch باعث `RESTORE_FAILED` شود؛ Source data پاک نشود.

## 21.5. Retention و Disk Monitoring — نگاشت تاریخی Stage 100

- Retention فعلی و candidate ages را از کد بخوان؛ اعداد ۹۰/۱۸۰/۳۰ روز گزارش سوم فقط baseline تاریخی‌اند.
- disk warning/critical thresholds فعلی را از config بخوان؛ ۷۰٪/۸۵٪ فقط اعداد گزارش‌شده‌اند.
- UI: candidate count، protected count، approximate bytes، blocked reason، policy version و disk state.
- `dry_run` پیش‌فرض باقی بماند.
- انتقال/حذف واقعی فقط با backup verified، restore test، audit، allowlist و approval صریح.
- سیاست Retention قبلاً توسط مالک تعیین شده است؛ policy دقیق را از `GlobalIntelligence_Roadmap_v1.9_Auth_UI_Animated_and_Security_Completion`، مستندات، config و implementation فعلی استخراج کن و بدون تغییر معنای آن یک مرجع واحد بساز.
- از مالک دوباره دربارهٔ policy، protected entities، سن retention یا toggle سؤال عمومی نپرس؛ فقط conflict مشخصی را که با شواهد قابل حل نیست گزارش کن.
- Toggle روشن/خاموش Auto-Purge را حفظ/تکمیل کن؛ default حتماً OFF و `PURGE_DRY_RUN=true` باشد. Live purge فقط وقتی اجرا شود که همان policy موجود، backup/restore/audit و مجوز صریح قبلی مالک آن را پوشش دهند؛ در غیر این صورت خاموش بماند. هیچ threshold یا entity جدیدی از خودت اختراع نکن.

## پذیرش WP-15

ZIP build/verify/restore محلی موفق؛ Telegram round-trip در صورت داشتن credential/approval؛ Retention dry-run با گزارش کامل؛ هیچ حذف ناخواسته‌ای رخ نداده؛ Auto-Purge خاموش.

---

# 22. WP-16 — اجرای پایدار محلی ۲۴/۷ روی Windows

## هدف
برنامه در کامپیوتر محلی Windows بتواند به‌صورت پایدار اجرا شود، سرویس‌ها و Jobها را کنترل کند و پس از crash/restart بازیابی امن داشته باشد؛ بدون VPS.

## اقدامات

1. پیش‌فرض طراحی این نسخه: Windows Task Scheduler فقط برای شروع/بازیابی stack محلی هنگام startup/reboot Windows استفاده شود؛ اجرای Jobهای داخلی توسط یک scheduler/runner مرجع و موجود پروژه انجام شود. n8n هم‌زمان مسئول همان schedule نباشد.
2. اگر بررسی فنی نشان داد Docker Desktop/Compose یا معماری فعلی با این روش سازگار نیست، گزینهٔ جایگزین را با شواهد پیشنهاد بده؛ از مالک سؤال کلی نپرس مگر دسترسی Windows واقعاً لازم و موجود نباشد.
3. یک Job زمان‌بندی‌شده نباید از چند مسیر هم‌زمان trigger شود.
4. سرویس‌های ضروری، startup dependency و health check مشخص شوند.
5. روش startup خودکار پس از ورود/روشن‌شدن Windows را طراحی کن؛ ابتدا runbook و سپس implementation. نصب سرویس با دسترسی Administrator فقط در صورت ضرورت و approval.
6. single-instance/leader lock برای scheduler و bot بررسی شود.
7. shutdown ویندوز/بستن برنامه باید Job state را درست ثبت کند؛ `running` orphan باقی نماند.
8. restart recovery برای JobRun، Dispatch، Source Bot و Archive بررسی شود.
9. log rotation، disk usage، DB connection health و process memory پایش شوند.
10. secretها از environment/secret store محلی بارگذاری شوند؛ در Task Scheduler command line یا log قرار نگیرند.
11. اگر شبکه/Provider قطع شد، queue و داده از بین نرود؛ retry محدود و circuit-breaker/blocked state مناسب استفاده شود.
12. اجرای هم‌زمان چند instance باعث duplicate ingestion یا dispatch نشود.
13. Windows user permission حداقلی؛ اجرای دائمی با Administrator ممنوع مگر دلیل فنی.
14. stop/start، restart سیستم، قطع شبکه، DB restart، Provider outage و low disk آزمایش شوند.
15. n8n فقط در صورت انتخاب به‌عنوان scheduler owner فعال شود؛ Workflowهای دیگر خاموش بمانند.
## پذیرش WP-16

- startup/shutdown طبق Runbook قابل تکرار.
- پس از restart، هیچ Job/Dispatch گم یا دوباره اجرا نشود.
- scheduler duplicate فعال نباشد.
- health، disk، queue، last successful run و error قابل مشاهده باشد.
- Soak test محلی با زمان و بار ثبت‌شده پاس شود.
---

# 23. WP-17 — Technical Debt، Security Hardening و Document Governance

## 23.1. Defect Register واحد

تمام F-xx تاریخی فقط alias باقی بمانند. نقص جدید شناسهٔ یکتا بگیرد:

- `GI-SEC-###`
- `GI-DB-###`
- `GI-AI-###`
- `GI-UI-###`
- `GI-DATA-###`
- `GI-OPS-###`
- `GI-TEST-###`
- `GI-DOC-###`

برای هر نقص: exact title، path/line، root cause، severity، status، source report، affected SHA، reproduction command، owner/dependency، fix plan، acceptance test و evidence ثبت شود.

## 23.2. اختلاف F-20 و F-23

**F-20:** گزارش‌ها دو معنی متفاوت دارند: `ArticleDispatch.meta` و `topics/entities` از نوع Text. ابتدا آن‌ها را به دو موضوع مستقل یا یک موضوع واحد با شواهد schema تقسیم کن. Migration فقط پس از بررسی query consumer، index need، SQLite compatibility، backfill، rollback و backup.

**F-23:** Auth limiter مبتنی بر جدول و Middleware/API limiter درون‌حافظه‌ای دو مسئله جدا هستند. محل storage، window، atomicity و multi-worker behavior هرکدام را بررسی کن. Redis فقط در صورت نیاز اندازه‌گیری‌شده و تأیید معماری.

## 23.3. Adaptive Router

گزارش‌ها وضعیت متفاوتی ثبت کرده‌اند: وجود `record`، bootstrap خاموش، و مصرف‌کنندهٔ خودکار نامعلوم. آن را با Archive یا Stage ID اشتباه نگیر.

- callsite و runtime consumer را پیدا کن.
- mock behavior، one-record-per-logical-generate، session ownership، DB failure isolation و race را تست کن.
- اگر خاموش‌بودن عمدی و policy-based است، `DISABLED_BY_POLICY` ثبت شود؛ خاموش بودن به‌تنهایی باگ نیست.
- فعال‌سازی فقط پس از evaluation، test و rollback plan.

## 23.4. Performance

- ابتدا baseline واقعی query count، latency، memory و row count.
- سپس N+1، full-table load، graph adjacency، replay و macro context بررسی شوند.
- batching/pagination/index/cache فقط با دلیل.
- بعد از تغییر، نتیجهٔ business/API باید ثابت بماند مگر هدف تغییر صریح باشد.
- ادعای بهبود بدون عدد ممنوع.

## 23.5. Security

- CSP و `unsafe-inline`، API key در localStorage، XSS، Telegram URL token redaction، file handling و SSRF را ارزیابی کن.
- session cookie برای UI مسیر اصلی باشد؛ Machine API Key از Login انسانی جدا بماند.
- اگر تغییر CSP نیازمند refactor UI است، کوچک و سازگار انجام شود؛ CSP را خاموش نکن.
- فایل‌های خصوصی مثل imported conversation attachments فقط inventory/privacy review شوند؛ حذف کور ممنوع.
- Legacy directoryها تا بررسی import/route/config/lock/owner و approval حذف نشوند.

## 23.6. Frontend Quality Gates

از package/config واقعی استفاده کن:

- lint موجود.
- TypeScript typecheck اگر Stack واقعاً TypeScript دارد.
- build.
- component/integration tests.
- Playwright E2E.
- dependency/lockfile consistency.

گزارش‌های قدیمی ESLint/F-22 متعارض‌اند؛ وضعیت فعلی باید اجرا شود.

## 23.7. Documentation Governance

یک منبع وضعیت واحد ایجاد/تکمیل شود:

- Roadmap جاری.
- `docs/STAGE_STATUS.md` یا معادل: وضعیت Work Packageها و نگاشت Stage تاریخی.
- `docs/DEFECT_REGISTER.md` یا معادل: Defect IDهای یکتا.
- `docs/EVIDENCE_INDEX.md`: SHA، command، run، evidence path.

README، ARCHITECTURE، TASKS، PROGRESS، PRODUCTION_READINESS، AGENTS و CI commands هم‌راستا شوند. اسناد تاریخی حذف یا بی‌صدا بازنویسی نشوند؛ با تاریخ و status archive شوند.

## پذیرش WP-17

هیچ Defect ID مبهم جدیدی وجود ندارد؛ P0/P1های باز یا رفع شده‌اند یا blocker روشن دارند؛ Security/lint/build/test/docs هم‌راستا هستند؛ cleanup فقط با evidence و rollback انجام شده است.

---

# 24. WP-18 — پذیرش نهایی محصول محلی

## 24.1. Backup/Restore

- DB backup با timestamp و checksum.
- Restore واقعی در DB ایزوله.
- row count، FK، unique و provenance integrity تطبیق داده شوند.
- archive ZIP نیز download/verify/restore sandbox داشته باشد.
- وجود فایل backup بدون restore موفق، پذیرش نیست.

## 24.2. Test Matrix

- Unit: parser، normalization، priority، dedup، retry و archive serialization.
- Contract: RawItem، API schema، AIError، provider response، dispatch payload، archive manifest و configuration.
- Integration: source → raw → normalize → dedup → priority → relevance → dispatch → analysis → UI.
- PostgreSQL: locking، race، FK، unique، migration، persistence و restart.
- Security: SSRF، redirect، DNS rebinding، XXE، Auth، prompt injection و secret redaction.
- Auth E2E: register/login/verify/reset/admin account management.
- UI E2E: تمام گردش‌کارهای حیاتی.
- Recovery: crash وسط fetch/job/archive/upload/restore.
- Live smoke: فقط source/provider/Telegram مجاز با opt-in و approval.
- Soak: اجرای چندساعته و در صورت امکان چندروزه روی Windows، با restart کنترل‌شده و پایش queue/DB/disk/RAM/CPU.

## 24.3. Local Product Acceptance Flow

1. Startup سرویس‌های لازم.
2. Health و DB connectivity.
3. Alembic Head/Current.
4. DB backup و restore sandbox.
5. Backend/UI version و SHA.
6. Anonymous → Register → Verify → Login → Logout.
7. Admin user creation و role checks.
8. Provider مجاز از Gateway یا blocker credential صریح.
9. Source واقعی و مجاز از Registry تا Document/Article.
10. Raw provenance، dedup، revision و cluster.
11. Priority و relevance مستقل.
12. یک Article pilot از Dispatch تا Event/Claim/Evidence/Entity/Graph.
13. Domain analysis و Memory retrieval با trace.
14. UI همان رکوردها را از API واقعی نشان دهد.
15. Restart در میانه Job و recovery idempotent.
16. Archive build/verify/restore.
17. Telegram round-trip در صورت approval/credential.
18. Retention dry-run؛ بدون purge.
19. Full tests، Ruff، frontend lint/typecheck/build و E2E.
20. Soak، shutdown و startup مجدد.

## 24.4. Windows Runbook

Runbook باید فقط فرمان‌های PowerShell آزموده‌شده داشته باشد:

- Start/Stop/Restart.
- Health diagnostics.
- DB connectivity/migration state.
- User/Admin bootstrap و مدیریت حساب.
- Provider config/test.
- Source add/validate/preview/enable.
- Controlled ingest.
- Job/Dispatch recovery.
- Alert delivery test.
- Archive build/verify/restore.
- Retention dry-run.
- Backup/restore.
- Emergency stop و safe shutdown.

نام Script، Service و Port را از checkout واقعی کشف کن؛ حدس نزن.

## معیار نهایی پذیرش محلی

GlobalIntelligence فقط زمانی `LOCALLY_ACCEPTED` است که:

- هیچ blocker بحرانی در data integrity، security، data loss و recovery باز نباشد.
- تست‌های لازم روی SHA مورد پذیرش اجرا شده باشند.
- Auth و مدیریت حساب‌ها طبق سیاست مالک کار کنند.
- UI اصلی با Backend واقعی متصل باشد و طراحی مرجع مالک در آن اعمال شده باشد.
- حداقل یک Source واقعی تا UI trace شده باشد.
- حداقل یک Provider واقعی مجاز از Gateway اجرا شده باشد یا blocker دقیق credential ثبت شده باشد.
- Backup/Restore DB و Archive اثبات شده باشند.
- Retention امن و Auto-Purge خاموش باشد.
- اجرای پایدار محلی و Recovery طبق Scope آزموده شده باشد.
- Runbook و Evidence Index وجود داشته باشند.
- limitationها و owner blockers پنهان نشده باشند.

`LOCALLY_ACCEPTED` به معنی Production/Internet-ready یا VPS deployed نیست.

---

# 25. Owner-dependent blockers و ورودی‌های از قبل تأمین‌شده

## 25.1. ورودی‌هایی که مالک قبلاً فراهم کرده یا تصمیم آن را داده است

این موارد blocker عمومی نیستند و نباید دوباره از مالک درخواست شوند:

1. Gold Set: مالک مسیر `H:\GIRuntime\labeling` را ارائه کرده؛ اعتبارسنجی/اتصال بر عهده AI است.
2. SMTP: متغیرهای Gmail در `.env` محلی بوده و مالک قبلاً آن را تست کرده؛ فقط App Password افشاشده باید توسط مالک revoke/rotate شود و سپس تست دوباره انجام شود.
3. Provider credentials: مالک وجود کلیدهای Gemini، OpenRouter، Groq و Cloudflare در `.env` را اعلام کرده؛ AI باید بدون چاپ Secret اعتبارسنجی کند.
4. Country Profile دوم: آمریکا (`US`) انتخاب شده است.
5. Budget: سیاست اولیهٔ Free-first و سقف‌های بخش 3.3.2 تعیین شده‌اند.
6. Legacy UI: حذف فایل‌های Legacy UI تأیید شده، مشروط به audit، backup، نبود consumer و عدم حذف shared/protected files.
7. Retention: سیاست قبلی مالک مرجع است؛ باید از اسناد/کد پیدا و حفظ شود. سؤال تکراری ممنوع.
8. Forecast targets: طلا، USD/IRR، نفت، تورم، BTC و ETH برای شروع؛ افق‌ها طبق بخش 19.7.
9. ثبت‌نام عمومی و قابلیت ساخت حساب کاربران توسط Admin از سیاست‌های قطعی محصول‌اند.

## 25.2. مواردی که هنوز ممکن است واقعاً نیازمند مالک باشند

1. **SMTP App Password rotation:** مالک باید App Password افشاشده را از Google Account باطل و جایگزین کند. تا آن زمان فقط تست زندهٔ SMTP مسدود است.
2. **Telegram:** اگر Bot Token/destination خصوصی در `.env` یا secret store موجود نیست، فقط همین ورودی را درخواست کن؛ مقدار را در گفتگو نخواه، از Settings امن استفاده شود.
3. **GitHub Actions:** Push/Actions verification توسط مالک انجام می‌شود؛ AI فقط دستورات، گزارش و SHA را آماده می‌کند.
4. **Paid AI enablement:** Paid calls به‌صورت پیش‌فرض خاموش‌اند. افزایش سقف اولیه یا فعال‌سازی Paid بالاتر از حدود تعیین‌شده فقط با تصمیم صریح جدید مالک مجاز است.
5. **فقدان واقعی داده در Gold Set:** فقط اگر inventory مسیر اعلام‌شده نشان داد تعداد معتبر/انواع label کمتر از حداقل harness است، مقدار دقیق کسری را گزارش کن؛ سؤال کلی «۲۰۰ برچسب آماده است؟» ممنوع.
6. **SMTP recipient یا تست مقصد:** ابتدا `.env` را به‌صورت masked بررسی کن؛ فقط اگر متغیر لازم واقعاً وجود ندارد، مقصد تستی حداقلی بخواه.

برای هر blocker ثبت کن: exact input، دلیل فنی، اثر عدم ارائه، کارهای قابل انجام بدون آن و وضعیت فعلی. سؤال تکراری نپرس و هیچ Secret را در گفتگو مطالبه نکن.
---

# 26. نگاشت Stageهای تاریخی به Work Package جدید

| شناسه تاریخی | محل پیگیری در نسخهٔ ۲٫۲ | نکته |
|---|---|---|
| Stage 96 | WP-02 | پذیرش مجدد روی SHA فعلی و CI؛ Fixهای تاریخی سالم حفظ شوند |
| Stage 97 | WP-08 | Gold Set انسانی و Screening evaluation |
| Stage 98 | WP-14.2 | Alert Delivery؛ هستهٔ Commit‌شده از UI/Test uncommitted جدا شود |
| Stage 99 | WP-14.3 | Country Profile عمومی و UI |
| Stage 100 | WP-15.5 | Retention dry-run و تصمیم مستقل برای purge |
| Stage 101 | WP-14.4 | Offline Translation |
| Stage 102 | WP-17 | Technical Debt و Defect Register |
| Stage 103 | خارج از Scope | VPS؛ فقط با نقشه‌راه و مجوز جداگانه |
| Stage 104 | WP-13.7 | Forecast outcome و Calibration پیوسته با داده واقعی |
| F03.UX و F03.0 تاریخی | WP-03 تا WP-06 | UI integration و Settings؛ شناسه‌های قدیمی به‌عنوان alias |

این جدول مانع تداخل `F-13` قدیمی با WP-13 جدید می‌شود. برای نقص‌ها فقط `GI-...` استفاده کن.

---

# 27. قالب اجباری گزارش هر نوبت

```text
Work Package/Substage:
Date and local time:
Repository root:
Branch:
HEAD SHA:
Working Tree before:
Working Tree after:
Owner/Protected files preserved:
Previous evidence reused:
Evidence stale checks:
Scope and reason this stage is next:
Dependencies:
Root cause / gap:
Files changed:
Files added:
Files deleted (exact paths + owner approval):
Migration(s):
Database environment:
Data changed (exact counts; no secrets):
Commands executed (exact):
Exit codes:
Unit tests:
Contract tests:
Integration tests:
PostgreSQL tests:
SQLite tests:
Full suite:
Ruff / frontend lint:
Typecheck:
Build:
Playwright/E2E:
Live test (separate from Mock):
Provider / Model / Free Policy:
Auth / Role / Session / Email verification:
Security and secret scan:
Backup/restore evidence:
Performance before/after:
Known limitations:
Owner inputs needed:
Documents/evidence updated:
Acceptance criteria passed:
Acceptance criteria failed:
Status:
Next single Work Package/Substage:
```

اگر چیزی اجرا نشده `NOT RUN` بنویس. اگر اجرا شده ولی خروجی در دسترس نیست `RESULT_NOT_CAPTURED` بنویس. هیچ‌گاه نتیجه را حدس نزن.

---

# 28. قوانین غیرقابل‌مذاکرهٔ نهایی

1. WP-00 در هر اجرای جدید اول و فقط‌خواندنی است.
2. فایل Modified/Untracked مالک بدون backup، inventory و مجوز حذف نمی‌شود.
3. هیچ Migration تاریخی rewrite/delete نمی‌شود.
4. هیچ Test برای سبزشدن حذف، Skip یا تضعیف نمی‌شود.
5. هیچ Secret در log، UI، browser storage، report، ZIP یا Git افشا نمی‌شود.
6. Auth، AI Gateway، DB، Dispatch، Ingestion، Dedup و Archive موازی ساخته نمی‌شوند.
7. AI call فقط از Gateway و Free Policy.
8. Kev/Laya advisory تا پذیرش Gold Set.
9. Mock از Real جدا.
10. Dedup hard-delete نیست و استقلال Source حفظ می‌شود.
11. Priority، Relevance و Content Analysis مستقل.
12. Archive و Purge مستقل؛ Auto-Purge خاموش.
13. n8n فقط پس از بررسی و approval فعال شود.
14. UI Reference مالک Protected؛ Legacy فقط با تأیید exact paths حذف شود.
15. ثبت‌نام عمومی باز؛ Admin قابلیت ساخت حساب داشته باشد؛ role escalation ممنوع.
16. Session Admin بدون انقضا نشود مگر مالک سیاست جدید را صریحاً تعیین کند.
17. VPS و deployment خارج Scope.
18. Commit/Push/PR/Merge توسط AI ممنوع.
19. یک Work Package/Substage در هر نوبت؛ بعد از گزارش توقف.
20. هر ادعای Complete باید evidence، SHA، command و acceptance result داشته باشد.

---

# 29. متن شروع برای OpenCode

متن زیر را همراه همین فایل به OpenCode بده:

> تو Senior/Staff Engineer مسئول تکمیل پروژهٔ موجود GlobalIntelligence هستی. فایل `GlobalIntelligence_Roadmap_v2.2.md` را کامل بخوان و قراردادهای معتبر نسخهٔ v1.9 و تصمیم‌های صریح مالک را نیز از Repository پیدا کن.
>
> وظیفهٔ تو بازنویسی پروژه نیست. ابتدا وضعیت واقعی checkout را بررسی کن، همهٔ دارایی‌های سالم را حفظ کن و فقط Gapهای واقعی را ببند. وجود فایل، Endpoint، صفحه، تست یا سند به معنی تکمیل قابلیت نیست.
>
> در اولین گام فقط WP-00 را اجرا کن. آن مرحله باید کاملاً read-only باشد: Git status، Branch، HEAD، Diff، فایل‌های Modified/Untracked، اسناد، UI references، شمارش‌ها، Alembic، runtime و DB census فقط‌خواندنی. در WP-00 هیچ فایل، دیتابیس، container، service، migration، test environment یا config را تغییر نده و تست/build اجرا نکن.
>
> چهار ممیزی A/B/C/D را فقط evidence تاریخی بدان. گزارش‌های C/D، PG 1814/0 را روی `ebe1292` و HEAD ممیزی را `2d0e1bc` ثبت کرده‌اند؛ نتیجه را بدون اجرای دوباره به SHA فعلی تعمیم نده. Remote GitHub Actions در گزارش‌ها `NOT_VERIFIED` است.
>
> Working Tree تاریخی ۶ فایل Modified و ۲ فایل Untracked داشته است؛ وضعیت امروز را دوباره بخوان. تمام تغییرات مالک را حفظ کن. اسکریپت‌های patch را کورکورانه اجرا نکن. هیچ `git reset`, `git clean`, حذف Volume، reset DB، purge یا حذف فایل Protected انجام نده.
>
> معماری موجود FastAPI، PostgreSQL/Alembic، Auth، AI Gateway، Free Policy، Budget، Dispatch، Source Bot، Dedup، Screening، Event/Claim/Evidence/Graph، Memory، Archive و UI را حفظ و reuse کن. قبل از ساخت هر قابلیت، consumer و contract فعلی آن را پیدا کن تا implementation موازی ایجاد نشود.
>
> ثبت‌نام عمومی باید آزاد باشد و Admin نیز از طریق مسیر مدیریتی مجاز بتواند حساب کاربری ایجاد کند. ایجاد اولین Admin از CLI با `getpass` با قابلیت Admin برای ساخت حساب‌های عادی متفاوت است. API Key روش Login کاربر انسانی نیست. Session policy فعلی را حفظ کن؛ Admin session بدون انقضا نساز.
>
> HTMLهای طراحی و Referenceهای UI مالک را Protected بدان. آن‌ها را به UI runtime موجود integrate کن؛ Frontend موازی نساز. هر صفحه باید API، Permission، loading، empty، error، action و test واقعی داشته باشد یا status صریح `NOT_IMPLEMENTED/NOT_CONNECTED/BLOCKED` نشان دهد.
>
> تمام AI callها از Gateway و Free Policy عبور کنند. Mock و Real تفکیک شوند؛ hidden paid fallback ممنوع. Kev/Laya تا پذیرش Gold Set انسانی advisory باقی بمانند. مالک Gold Set را در `H:\GIRuntime\labeling` آماده کرده؛ ابتدا آن را validate و به harness موجود متصل کن و از مالک دوباره درخواست برچسب‌گذاری نکن. Label مصنوعی یا prediction مدل Ground Truth نیست.
>
> Source Bot را به ingestion contract موجود متصل نگه دار. Dedup فقط تشخیص است؛ حذف سخت ممنوع. Priority و Relevance جدا باشند. Dispatch باید idempotent، concurrency-safe و قابل بازیابی باشد.
>
> Causal Analysis، Independent Ensemble، Memory فعال، domain coverage و walk-forward Backtesting را فقط پس از بررسی کد موجود و اثبات Gap تکمیل کن. اهداف Forecast از قبل تعیین شده‌اند: XAUUSD، USD/IRR با تفکیک نرخ‌ها، Brent/WTI، CPI، BTC و ETH؛ افق‌های ۱/۷/۳۰/۹۰ روز برای بازارها و next-release/۳/۶/۱۲ ماه برای تورم. Correlation را causal و Debate را Ensemble مستقل معرفی نکن.
>
> بودجه AI را طبق بخش 3.3.2 با Free-first، Paid-off، سقف روزانه ۱ دلار و سقف ماهانه ۱۵ دلار رعایت کن؛ هیچ hidden paid fallback اجرا نکن. چهار Provider credential (Gemini/OpenRouter/Groq/Cloudflare) طبق اعلام مالک در `.env` وجود دارند؛ فقط masked presence و تست کنترل‌شده انجام بده. SMTP قبلاً تنظیم/تست شده، اما App Password افشا شده و باید توسط مالک rotate شود. Country دوم US است. Legacy UI deletion از طرف مالک تأیید شده، اما فقط پس از audit و backup و برای فایل‌های قطعاً unused مجاز است. سیاست Retention قبلاً تعیین شده؛ آن را پیدا کن و دوباره سؤال نپرس.
>
> Archive و Retention مستقل‌اند. Auto-Purge خاموش بماند. Telegram live send فقط با credential، مقصد تستی و approval مالک. VPS/deployment خارج Scope است.
>
> بعد از WP-00 فقط یک Work Package/Substage باز و دارای وابستگی آماده را اجرا کن. یک change set محدود انجام بده، تست‌های واقعی و متناسب اجرا کن، گزارش کامل با branch/HEAD/commands/exit codes/evidence بده و متوقف شو. Commit/Push/PR/Merge نکن.
>
> از مالک دوباره Gold Set، API Keyهای چهار Provider، انتخاب کشور دوم، سیاست Retention، انتخاب Forecast targets یا تأیید کلی Legacy deletion را درخواست نکن؛ این موارد اعلام/تأیید شده‌اند. فقط SMTP App Password افشاشده نیازمند revoke/rotate توسط مالک است. اگر Telegram destination واقعاً موجود نیست یا Push GitHub لازم شد، فقط همان blocker مشخص را درخواست کن و کارهای مستقل را ادامه بده. هیچ قابلیت ناقصی را Complete اعلام نکن.

---

# 30. حکم نسخهٔ ۲٫۲

این نقشه‌راه برای **تکمیل محصول محلی GlobalIntelligence** نوشته شده است: حفظ قابلیت‌های موجود، تکمیل بخش‌های ناقص، ساخت قابلیت‌های واقعاً غایب، یکپارچه‌سازی UI طراحی‌شده توسط مالک، تکمیل چرخهٔ داده و هوش، مدیریت امن کاربران و تنظیمات، و اثبات پایداری/بازیابی روی Windows.

این نسخه اجازهٔ بازنویسی معماری، حذف کار مالک، فعال‌سازی مخرب داده، استفادهٔ پنهانی از Provider پولی یا ادعای Production Readiness بدون شواهد را نمی‌دهد.

**معیار موفقیت، تعداد Stageهای تیک‌خورده یا درصد تخمینی نیست؛ معیار موفقیت این است که کاربر بتواند از رابط اصلی وارد سیستم شود، منابع مجاز را مدیریت کند، دادهٔ واقعی و قابل‌ردیابی دریافت کند، تحلیل‌های قابل‌توضیح و دارای provenance اجرا کند، خروجی را در UI ببیند و سیستم پس از خطا/Restart بدون از دست‌دادن یا تکرار داده بازیابی شود.**


---

# 31. Change Log نسخهٔ ۲٫۲ — اصلاح بر اساس پاسخ مالک

- Gold Set دیگر کارِ انجام‌نشدهٔ مالک نیست؛ مسیر دقیق `H:\GIRuntime\labeling` به‌عنوان منبع خارجی داده ثبت شد. مسئولیت AI: inventory، اعتبارسنجی، hash، provenance، import و evaluation؛ اصل فایل‌ها immutable می‌مانند.
- SMTP قبلاً در `.env` تنظیم و توسط مالک تست شده بود؛ این سابقه حفظ شد. به دلیل افشای App Password در گفتگو، فقط rotate کردن credential فعلی توسط مالک باقی است؛ پس از آن re-test انجام می‌شود. هیچ Secret در این سند درج نشده است.
- وجود چهار Provider credential یعنی Gemini، OpenRouter، Groq و Cloudflare در `.env` به‌عنوان گزارش مالک ثبت شد؛ اعتبار اتصال، مدل، policy و billing باید جداگانه و بدون نمایش Secret تأیید شود.
- بودجهٔ آغازین به‌صورت Free-first تعیین شد: Paid calls خاموش، سقف کل روزانه ۱ دلار و ماهانه ۱۵ دلار، سقف هر درخواست تعاملی ۰٫۱۰ دلار و هر Article background برابر ۰٫۰۵ دلار؛ افزایش سقف نیازمند تصمیم جدید مالک است.
- کشور دوم برای Country Profile به‌طور قطعی آمریکا (`US`) انتخاب شد.
- حذف Legacy UI از طرف مالک تأیید شد؛ حذف فقط پس از dependency/runtime audit، backup و hash فایل‌های قطعاً unused مجاز است. فایل‌های Shared/Protected/Unknown و Backend/DB خارج این مجوز هستند.
- سیاست Retention قبلی مالک مرجع باقی می‌ماند؛ AI باید آن را از اسناد/کد استخراج کند و سؤال تکراری نسازد. Auto-Purge default OFF و Dry-run ON می‌ماند.
- Forecast targets تثبیت شدند: XAUUSD، USD/IRR با تفکیک نرخ بازار/رسمی، Brent، WTI، CPI، BTC و ETH. افق‌های آغازین برای بازارها ۱/۷/۳۰/۹۰ روز و برای تورم next-release/۳/۶/۱۲ ماه هستند.
- سیاست ثبت‌نام عمومی و ایجاد حساب کاربری توسط Admin صریح‌تر شد.
- برای اجرای ۲۴/۷، Windows Task Scheduler به‌عنوان راهکار پیش‌فرض startup/recovery stack محلی پیشنهاد شد و یک scheduler داخلی واحد باید مالک اجرای Jobها بماند؛ n8n نباید schedule تکراری ایجاد کند.
