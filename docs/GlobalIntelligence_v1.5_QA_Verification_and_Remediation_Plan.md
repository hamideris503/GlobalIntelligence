# GlobalIntelligence v1.5 — نقشه‌راه جامع تست، ارزیابی، عیب‌یابی و اصلاح پروژه

**شناسه سند:** `GI-1.5-QA-PLAN`  
**نسخه سند:** ۱٫۰  
**نوع سند:** Quality Engineering / Verification / Defect Remediation Plan  
**مبنای فنی:** نقشه‌راه کامل و مهندسی GlobalIntelligence v1.5  
**هدف اجرا:** بررسی و اصلاح checkout محلی Windows؛ بدون استقرار یا انتقال به VPS  
**مخاطب اجرایی:** AI کدنویس در نقش Senior/Staff Software Engineer، QA Architect و Security-minded Reviewer  
**قاعده شروع:** ابتدا ممیزی فقط‌خواندنی `QA-00`؛ سپس اجرای تست و اصلاح فقط بر اساس شواهد  

---

## 0. هدف این سند و تفاوت آن با نقشه‌راه توسعه

این سند مکمل نقشه‌راه توسعه v1.5 است و جایگزین آن نیست. نقشه‌راه توسعه می‌گوید چه قابلیت‌هایی باید وجود داشته باشند و چگونه ساخته شوند؛ این سند مشخص می‌کند چگونه ثابت کنیم قابلیت‌های موجود واقعاً درست، امن، پایدار، قابل‌بازیابی و قابل‌استفاده‌اند و در صورت مشاهده نقص، چگونه آن نقص را با کمترین ریسک اصلاح کنیم.

**مأموریت اصلی:** وضعیت واقعی پروژه را در برابر الزام‌های v1.5 اندازه‌گیری کن؛ قابلیت‌های کامل را دوباره نساز؛ قابلیت‌های ناقص را با تست مشخص کن؛ خطاها را بازتولید کن؛ علت ریشه‌ای را پیدا کن؛ اصلاح کوچک و قابل بازبینی انجام بده؛ سپس تست‌های هدفمند و رگرسیون را اجرا کن.

این کار یک «سبزکردن ظاهری تست‌ها» نیست. معیار موفقیت، صحت رفتار و حفظ داده است؛ نه صرفاً تعداد تست‌های پاس‌شده.

### 0.1 تفاوت خروجی مورد انتظار

| نقشه‌راه توسعه v1.5 | این نقشه‌راه QA v1.5 |
|---|---|
| قابلیت‌ها را طراحی و پیاده‌سازی می‌کند | وجود، کیفیت و رفتار واقعی قابلیت‌ها را اثبات می‌کند |
| کد، API، مدل و UI اضافه می‌کند | کد و قرارداد موجود را بررسی و فقط نقص اثبات‌شده را اصلاح می‌کند |
| مسیر ساخت Feature را تعریف می‌کند | مسیر Test → Reproduce → Diagnose → Fix → Regression را تعریف می‌کند |
| تعریف می‌کند چه چیزی باید تحویل شود | تعریف می‌کند با چه شواهدی می‌توان تحویل را پذیرفت |
| Feature ممکن است هنوز وجود نداشته باشد | Feature غایب را `MISSING` ثبت می‌کند؛ فقط با اجازه و scope روشن وارد توسعه می‌شود |

### 0.2 خارج از محدوده

- ساخت دوبارهٔ سیستم یا بازنویسی معماری سالم.
- اجرای مجدد کورکورانهٔ همهٔ مراحل توسعه v1.3/v1.5.
- حذف تست برای رفع خطای CI، افزودن skip بی‌دلیل یا تغییر assertion برای تطبیق با رفتار معیوب.
- ساخت Provider، adapter یا مسیر ingestion موازی.
- تغییر سیاست‌های امنیتی، دورزدن Free Policy یا فعال‌سازی Provider بدون تأیید.
- حذف دادهٔ واقعی، پاک‌کردن PostgreSQL volume، reset دیتابیس یا اجرای purge واقعی.
- commit، push، merge، PR یا تغییر مخرب Git؛ مالک پروژه GitHub را دستی مدیریت می‌کند.
- VPS، deployment، production server یا cloud rollout.

---

# 1. قوانین حاکم بر تست و اصلاح

## 1.1 اصل اول: شواهد قبل از نتیجه‌گیری

برای هر ادعا باید یکی از این شواهد وجود داشته باشد: خروجی فرمان، log امن، تست قابل بازتولید، query فقط‌خواندنی، screenshot، trace، اندازه‌گیری یا گزارش ابزار. عبارت‌هایی مانند «به نظر درست است»، «فایلش وجود دارد»، «CI سبز است» یا «Mock جواب داد» به‌تنهایی مدرک کافی نیستند.

## 1.2 اصل دوم: تست نباید داده یا سیستم را خراب کند

- تست‌های مخرب فقط روی دیتابیس آزمایشی resettable اجرا شوند.
- روی دیتابیس دارای دادهٔ واقعی فقط تست read-only یا تستی اجرا شود که اثر آن صریحاً قابل پیش‌بینی و برگشت‌پذیر است.
- قبل از migration، archive restore، bulk operation و تغییر schema، مقصد دیتابیس و backup معتبر را تأیید کن.
- `docker compose down -v`، حذف volume، `git clean -fd` و `git reset --hard` ممنوع است.
- هیچ‌وقت برای تست آرشیو، purge یا restore از Telegram واقعی و دادهٔ واقعی بدون مجوز صریح استفاده نکن.

## 1.3 اصل سوم: محیط‌ها از هم جدا باشند

حداقل این محیط‌های منطقی را تفکیک کن؛ نام و ابزار واقعی را از repository بخوان:

| محیط | کاربرد | اجازهٔ دسترسی بیرونی | اجازهٔ تغییر داده |
|---|---|---|---|
| `local-readonly-audit` | بررسی checkout، config و داده | خیر، مگر استعلام عمومی read-only لازم باشد | خیر |
| `test-postgres` | integration، migration، concurrency | خیر | فقط دادهٔ تست |
| `mock-network` | timeout، 401/403/404/429/5xx، redirect، DNS و قطع اتصال | شبکهٔ کنترل‌شده/شبیه‌سازی‌شده | فقط دادهٔ تست |
| `local-e2e` | سناریوهای واقعی UI تا Backend | فقط سرویس‌های محلی | فقط دادهٔ تست |
| `optional-live-provider` | اتصال کنترل‌شده به Provider واقعی | فقط با opt-in و credential آزمایشی | بدون تغییر غیرمجاز؛ هزینه/سهمیه کنترل شود |
| `telegram-test` | upload، download و metadata آرشیو | فقط با opt-in و مقصد خصوصی آزمایشی | فقط آرشیو آزمایشی؛ purge واقعی ممنوع |

هیچ تستی نباید به‌طور پنهان از `test-postgres` به دیتابیس توسعه/واقعی وصل شود. اتصال هدف را قبل از اجرای suite چاپ نکن؛ فقط host/environment امن و نام database غیرحساس را گزارش کن.

## 1.4 اصل چهارم: حفظ تغییرات مالک

قبل از اولین تست یا اصلاح:

1. branch، HEAD، staged، unstaged و untracked را ثبت کن.
2. فایل‌های تغییرکرده را فهرست کن؛ محتوا ممکن است secret داشته باشد، پس گزارش نباید dump کامل `.env` یا فایل‌های حساس باشد.
3. وضعیت DB و حجم/وجود volumeها را بدون حذف بررسی کن.
4. snapshot یا patch قابل‌بازیابی از تغییرات موجود تهیه کن، اما روی فایل‌های حاوی secret نسخهٔ ناامن نساز.
5. در صورت ناتوانی در حفاظت از تغییرات، پیش از اصلاح متوقف شو.

## 1.5 اصل پنجم: اصلاح کمینه و علت‌محور

برای هر defect:

- ابتدا با test یا script کنترل‌شده بازتولید کن.
- علت ریشه‌ای را از symptom جدا کن.
- حداقل یک تست regression بنویس که پیش از fix شکست بخورد و پس از fix پاس شود.
- کوچک‌ترین patch سازگار را اعمال کن.
- تست هدفمند، suite همان حوزه و سپس regression وسیع‌تر را اجرا کن.
- اگر رفتار مورد انتظار مبهم است، آن را `SPEC_GAP` علامت بزن و تصمیم مالک را درخواست کن؛ رفتار را از خودت اختراع نکن.

## 1.6 ممنوعیت‌های صریح برای AI کدنویس

- حذف test، کاهش assertion، افزایش بی‌دلیل timeout، اضافه کردن `xfail/skip` برای پوشاندن failure ممنوع.
- Mock کردن dependencyای که هدف تست واقعی آن است ممنوع؛ Mock فقط در test مربوط به boundary یا خطای کنترل‌شده مجاز است.
- استفاده از SQLite برای اعلام صحت رفتار PostgreSQL ممنوع.
- دست‌کاری ساعت، network resolver یا environment سراسری بدون fixture محدود و cleanup قطعی ممنوع.
- خاموش‌کردن TLS verification، SSRF protections، auth، permission check یا Free Policy برای پاس شدن تست ممنوع.
- تغییر migration قدیمی ممنوع؛ فقط migration جدید و کوچک در صورت نیاز واقعی.
- تغییر snapshot بصری بدون مقایسه و review ممنوع.
- پاک‌کردن داده یا فایل ناشناخته برای مرتب‌کردن workspace ممنوع.
- هیچ secret، token، URL حاوی credential یا متن کامل response حساس در گزارش چاپ نشود.

---

# 2. مدل وضعیت، درجه اطمینان و معیار شواهد

## 2.1 وضعیت هر قابلیت

| وضعیت | معنی دقیق | شرط استفاده |
|---|---|---|
| `VERIFIED` | رفتار در محیط هدف با تست مناسب اثبات شده | فرمان، محیط، نتیجه و شاهد ثبت شده باشد |
| `PARTIALLY_VERIFIED` | فقط بخشی از رفتار/سناریو اثبات شده | بخش اثبات‌شده و gap دقیق ذکر شود |
| `NOT_VERIFIED` | شواهد کافی وجود ندارد یا تست اجرا نشده | وجود کد یا تست به‌تنهایی کافی نیست |
| `BLOCKED` | اجرای تست به credential، دادهٔ انسانی، تصمیم یا سرویس بیرونی وابسته است | blocker و مسئول رفع آن ثبت شود |
| `FAILED` | تست معتبر اجرا شده و رفتار مورد انتظار رخ نداده | failure و reproduction ثبت شود |
| `MISSING` | قابلیت/قرارداد موردنیاز در کد واقعی وجود ندارد | به‌عنوان gap توسعه ثبت شود، نه bug در کد موجود |
| `SPEC_GAP` | الزام یا رفتار مورد انتظار دوپهلو/متناقض است | تا تصمیم مالک، پیاده‌سازی حدسی ممنوع |
| `NOT_APPLICABLE` | الزام با معماری/قابلیت فعلی ارتباط ندارد | دلیل فنی لازم است |

## 2.2 سطح اطمینان شواهد

- `E0 — Assertion`: توضیح شفاهی یا فرضیه بدون شاهد.
- `E1 — Static`: کد، config، schema یا تست موجود خوانده شده.
- `E2 — Executed`: فرمان یا تست اجرا و خروجی ثبت شده.
- `E3 — Reproduced`: failure یا behavior مستقل و قابل تکرار بازتولید شده.
- `E4 — Regression-Proven`: test پیش از fix fail و پس از fix pass شده و regression مرتبط پاس است.
- `E5 — Operationally-Verified`: اجرای انتهابه‌انتها در محیط محلی واقعی/کنترل‌شده، همراه شواهد داده، recovery و security تأیید شده.

`VERIFIED` برای Featureهای حساس داده/امنیت/آرشیو معمولاً به E4 یا E5 نیاز دارد. تست unit به تنهایی برای E5 کافی نیست.

## 2.3 قالب ثبت هر تست

هر Test Case باید این اطلاعات را داشته باشد:

| فیلد | توضیح |
|---|---|
| Test ID | شناسهٔ پایدار مانند `QA-F02-PG-001` |
| Requirement IDs | الزام‌های v1.5 که تست پوشش می‌دهد |
| Level | unit / integration / contract / E2E / security / performance / manual |
| Preconditions | وضعیت DB، config، permission، داده و سرویس موردنیاز |
| Steps | مراحل دقیق و قابل تکرار |
| Expected | نتیجهٔ مورد انتظار و invariantهای داده |
| Actual | نتیجهٔ واقعی |
| Environment | OS، Python/Node، PostgreSQL، branch/HEAD، config profile |
| Evidence | مسیر log امن، screenshot، query result یا test output |
| Result | PASS / FAIL / BLOCKED / NOT RUN |
| Defect ID | شناسهٔ نقص مرتبط در صورت failure |

---

# 3. سطح‌بندی تست‌ها و استراتژی پوشش

## 3.1 Test Pyramid

1. **Static checks:** lint، typecheck، format check، dependency audit در صورت وجود، migration check و بررسی secret.
2. **Unit tests:** توابع deterministic، state transition، validators، normalizer، priority engine، eligibility rules.
3. **Contract tests:** API schema، adapter registry، ingestion contract، Provider descriptors، archive manifest و error contract.
4. **Integration tests:** PostgreSQL، worker، scheduler، queue، AI Gateway mock boundary، file storage و Telegram adapter mock.
5. **End-to-End tests:** جریان واقعی Browser → API → DB/Worker → نتیجهٔ قابل‌مشاهده در UI.
6. **Non-functional tests:** security، performance، reliability، recovery، accessibility و usability.
7. **Operational acceptance:** backup/restore، restart، local run و سناریوی کامل پروژه.

تست‌های پایین هرم باید سریع و پرتعداد باشند؛ تست E2E فقط برای workflowهای با ارزش بالا و contractهای بین اجزا استفاده شود.

## 3.2 تفکیک تست Mock و Real

برای هر تستی که Provider، Laya/Kev، Telegram، network یا model را درگیر می‌کند صریحاً ثبت کن:

- `MOCK`: فقط contract و handling خطا را تست می‌کند.
- `LOCAL_REAL`: کد و مدل local واقعی اجرا شده است.
- `EXTERNAL_REAL`: سرویس خارجی واقعی پاسخ داده است.

این سه نتیجه قابل جایگزینی با یکدیگر نیستند. Mock موفق، کیفیت مدل واقعی یا دسترس‌پذیری سرویس بیرونی را ثابت نمی‌کند.

## 3.3 Test Data Governance

- fixtureها deterministic، کوچک، نسخه‌دار و فاقد secret باشند.
- دادهٔ تست باید موارد فارسی/انگلیسی، encoding، timezone، متن ناقص، تاریخ نامعتبر، URL canonical و source provenance را پوشش دهد.
- نمونهٔ خبری نباید حاوی دادهٔ شخصی حساس غیرضروری باشد.
- دادهٔ واقعی در تست فقط با مجوز، sanitization و policy مشخص استفاده شود.
- test database قبل و بعد از سناریوی مخرب قابل تشخیص باشد.
- test IDs و external IDs باید ثابت و یکتا باشند تا test repeatable بماند.

## 3.4 پوشش و کیفیت تست

- coverage درصدی را به‌تنهایی معیار کیفیت ندان.
- coverage باید با branch/critical-path coverage و requirement traceability تکمیل شود.
- برای security، purge، dedup و job concurrency، تست‌های boundary و negative لازم‌اند.
- کدهای حساس باید حداقل یک تست برای success، invalid input، authorization failure، transient failure و retry/idempotency داشته باشند.
- test flaky باید به‌عنوان defect جداگانه ثبت شود؛ retry خودکار نامحدود آن را پنهان نمی‌کند.

---

# 4. QA-00 — ممیزی وضعیت، حفاظت و تعیین خط مبنا (فقط خواندنی)

## هدف

قبل از اجرای هر تست تغییردهنده یا patch، وضعیت واقعی checkout، سرویس‌ها، DB، migration، test suite و گزارش‌های قبلی را ثبت کن. این مرحله هیچ اصلاح کدی انجام نمی‌دهد.

## 4.1 اقلام بررسی

- Git branch، HEAD، آخرین commitها، staged/unstaged/untracked و diff summary.
- مسیر واقعی repository و working directory موردنیاز backend/frontend.
- Python، Node، package manager، Docker/Compose و PostgreSQL version.
- فایل‌های project config مانند `pyproject.toml`, lockfiles، `package.json`, workflows، pytest config و migration config.
- وضعیت DB: reachable، current revision، head revisions، تعداد تقریبی جدول‌های کلیدی فقط با query read-only و بدون نمایش محتوای حساس.
- وضعیت docker containerها/volumeها بدون stop/remove.
- test reports و `docs/STAGE_STATUS.md` و گزارش‌های Stage.
- env vars فقط از نظر وجود/عدم وجود و نام کلیدهای موردنیاز؛ هرگز مقدارشان را چاپ نکن.
- مسیر فعلی log و temp files و حجم آن‌ها؛ هیچ فایل ناشناخته را حذف نکن.

## 4.2 reconciliation مراحل v1.5

برای هر Stage از F00 تا F16 یک سطر در `docs/qa/QA_STAGE_MATRIX.md` ایجاد کن:

| Stage | Code present | Tests present | Tests executed | External dependency | Evidence | Status | Gap |
|---|---|---|---|---|---|---|---|

دادهٔ گزارش‌های قبلی را با وضعیت فعلی یکی فرض نکن. تعداد تست‌ها، زمان اجرا و نتیجه فقط از run جدید ثبت شود.

## 4.3 خروجی‌های الزامی

- `docs/qa/QA_BASELINE.md`
- `docs/qa/QA_STAGE_MATRIX.md`
- `docs/qa/TEST_ENVIRONMENT.md`
- `docs/qa/DEFECT_REGISTER.md` (ابتدا خالی یا با defectهای بازتأییدشده)
- `docs/qa/evidence/` یا محل معادل امن و gitignored برای خروجی‌ها

Evidence نباید حاوی `.env`، secret، دادهٔ شخصی یا archive واقعی باشد.

## معیار عبور QA-00

- تمام تغییرات کاربر شناسایی و محافظت شده‌اند.
- test DB از DB توسعه/دادهٔ واقعی تفکیک شده است.
- روش اجرای تست‌های موجود از خود repository استخراج شده است.
- Stageها و defectهای تاریخی status تازه دارند.
- baseline بدون اصلاح کد ثبت شده است.

پس از گزارش QA-00 توقف کن. تا دستور مجزا، هیچ test suite سنگین، migration، cleanup یا patch اجرا نکن.

---

# 5. QA-01 — آزمون پایهٔ Build، Static Analysis و وابستگی‌ها

## هدف

اثبات اینکه پروژه از checkout فعلی قابل نصب/ساخت/بررسی است و ابزارهای کیفیت واقعی اجرا می‌شوند.

## تست‌ها

- dependency lock consistency و نصب repeatable طبق package manager واقعی.
- Python lint/format/type checks فقط ابزارهای واقعاً پیکربندی‌شده.
- Frontend lint/typecheck/test/build مطابق scriptهای `package.json` موجود.
- Docker build فقط در صورت وجود Dockerfile/Compose واقعی و در محیط local.
- migration configuration load و تشخیص چند head ناخواسته.
- بررسی secretهای ناخواسته در tracked/untracked files با ابزار موجود یا scan محدود.
- بررسی dependencyهای آسیب‌پذیر با ابزار مناسب، بدون upgrade خودکار کور.

## کنترل‌های مهم

- نصب dependency نباید lockfile را ناخواسته تغییر دهد.
- خروجی command و exit code ثبت شود.
- اگر script مورد انتظار وجود ندارد، `MISSING_CHECK` ثبت کن؛ اسکریپت صوری نساز.
- build موفق به معنی درست‌بودن runtime یا integration نیست.

## معیار عبور

همهٔ checks تعریف‌شده در repository قابل اجرا باشند؛ failureها به defect مستقل تبدیل شوند؛ هیچ تغییر بی‌دلیل در dependency/lockfile رخ نداده باشد.

---

# 6. QA-02 — PostgreSQL، Migration، Transaction و CI

## هدف

اثبات رفتار دیتابیس هدف، مخصوصاً هم‌زمانی، atomicity، FK، rollback، isolation و اجرای تست در CI. SQLite جایگزین PostgreSQL نیست.

## 6.1 Migration integrity

- وضعیت `alembic heads/current` یا سازوکار migration واقعی را ثبت کن.
- migration تازه فقط روی DB آزمایشی خالی و DB آزمایشی دارای schema قبلی اجرا شود.
- مسیر upgrade تا head بررسی شود.
- downgrade فقط در دیتابیس throwaway و فقط اگر migration reversible طراحی شده باشد.
- بعد از downgrade/upgrade، schema و دادهٔ seed مورد انتظار را مقایسه کن.
- duplicate head، missing revision، غیرقابل اجرا بودن migration یا schema drift defect است.

## 6.2 Atomic dispatch و race conditions

سناریوها:

1. دو worker هم‌زمان برای یک batch از Jobهای eligible claim انجام دهند.
2. هر Job در یک لحظه فقط به یک worker واگذار شود.
3. claim transaction کوتاه و atomic باشد.
4. failure وسط claim هیچ Job نیمه‌claim‌شده باقی نگذارد.
5. lease منقضی‌شده طبق policy قابل بازیابی باشد.
6. worker قدیمی پس از از دست‌دادن lease نتواند نتیجهٔ worker جدید را overwrite کند.
7. unique constraints و idempotency در برابر درخواست تکراری حفظ شوند.

برای concurrency از barrier/latch تستی استفاده کن؛ sleepهای تصادفی جایگزین synchronization درست نیستند.

## 6.3 Connection و FK

- pool exhaustion و connection timeout با بار محدود تست شوند.
- session/transaction در success و exception آزاد شود.
- FK برای article/job/dispatch relationships در DB واقعی بررسی شود.
- helperهای تست نباید FK را دور بزنند یا rowهای orphan تولید کنند.
- تستی که به ترتیب اجرای فایل‌های دیگر وابسته است باید با اجرای مستقل و اجرای کل suite بررسی شود.

## 6.4 CI completeness

laneهای منطقی پیشنهادی:

- static/lint/typecheck؛
- unit tests؛
- PostgreSQL integration tests؛
- migration tests؛
- frontend build/unit؛
- E2E smoke؛
- security/dependency checks در صورت ابزار موجود.

هر lane باید test selection و exclusions خود را مستند کند. موفقیت lane ناقص را موفقیت کل suite ننام.

## معیار عبور QA-02

- suite PostgreSQL بدون deadlock/flake غیرقابل‌توضیح پاس شود.
- هر failure تاریخی یا رفع شده باشد یا blocker مستند داشته باشد.
- migrations در DB آزمایشی از صفر و upgrade مسیر پشتیبانی‌شده را طی کنند.
- CI همان test commands کلیدی را اجرا کند یا اختلافش صریح ثبت شود.

---

# 7. QA-03 — UI/UX، Dashboard و Design System

## هدف

ارزیابی اینکه رابط GlobalIntelligence فقط زیبا نیست، بلکه کارهای اصلی را واضح، سریع، قابل‌فهم و دسترس‌پذیر می‌کند.

## 7.1 ممیزی route و component

برای هر route ثبت کن:
- URL و permission؛
- page title و primary action؛
- APIهای مورد استفاده؛
- loading / empty / error / stale / success states؛
- responsive layout؛
- RTL/LTR؛
- keyboard/focus؛
- خطاهای visual و functional؛
- screenshot baseline و نسخهٔ اصلاح‌شده.

## 7.2 سناریوهای کاربردپذیری اجباری

| Test ID | کار کاربر | معیار موفقیت |
|---|---|---|
| QA-UX-001 | پیدا کردن مقاله P0/P1 | با جست‌وجو/فیلتر به رکورد درست برسد و اولویت را اشتباه نگیرد |
| QA-UX-002 | فهم علت Priority | reason/confidence/source قابل‌تشخیص باشد؛ مقدار ناموجود جعل نشود |
| QA-UX-003 | تشخیص Source خراب | خطا، آخرین موفقیت، زمان اجرای بعدی و اقدام بعدی واضح باشد |
| QA-UX-004 | افزودن و Test یک Source | draft، validation، test و preview با stateهای مجزا کار کنند |
| QA-UX-005 | تشخیص Job failure | کاربر بتواند job، علت safe، retry policy و run history را پیدا کند |
| QA-UX-006 | مدیریت Provider | connectivity، model availability، policy و enablement با هم اشتباه نشوند |
| QA-UX-007 | بررسی Archive | وضعیت archive، remote verification و purge eligibility واضح باشد |
| QA-UX-008 | بازگشت از جزئیات | filter/sort/page قبلی از دست نرود |

زمان task یا تعداد کلیک را فقط وقتی ثبت کن که واقعاً اندازه‌گیری شده باشد. بدون کاربر انسانی نتیجه را `SIMULATED_REVIEW` بنویس، نه usability study.

## 7.3 Dashboard data correctness

برای هر KPI:
- تعریف دقیق count/rate؛
- بازهٔ زمانی و timezone؛
- API/query source؛
- `last_updated_at`؛
- behavior در null، empty، stale یا endpoint failure؛
- deep link به لیست فیلترشده.

موارد زیر خطای جدی هستند:
- mock یا hard-coded value در runtime؛
- نمایش صفر به‌جای unknown؛
- نشان‌دادن دادهٔ stale به‌عنوان live؛
- success رنگی برای وضعیت نامشخص؛
- کلیک KPI که به filter متفاوت می‌رود.

## 7.4 Responsive و accessibility

حداقل viewportهای قابل بررسی با توجه به app:
- desktop wide؛
- desktop معمولی؛
- tablet portrait/landscape؛
- mobile narrow.

آزمون‌ها:
- keyboard-only navigation؛
- visible focus و ترتیب منطقی؛
- label و accessible name برای controlها؛
- dialog focus trap و بازگشت focus؛
- 200% zoom و text scaling؛
- reduced motion؛
- contrast در light/dark؛
- RTL فارسی و متن ترکیبی فارسی/انگلیسی/عدد/URL؛
- عدم overflow و clipped action مهم.

هدف انطباق WCAG 2.2 AA است؛ automation به‌تنهایی اثبات انطباق کامل نیست. محدودیت تست دستی را ثبت کن.

## 7.5 Visual regression

- baseline در شرایط ثابت (viewport، font، theme، seed data) ثبت شود.
- dynamic timestamps و شناسه‌ها فقط با روش test-safe کنترل شوند؛ اطلاعات واقعی را از تصویر حذف/پوشش بده.
- snapshot update باید review شود.
- visual diff بزرگ بدون دلیل طراحی/مستند، failure تلقی شود.

## معیار عبور QA-03

تمام workflowهای حیاتی سناریوهای بالا را بگذرانند؛ دادهٔ داشبورد واقعی باشد؛ RTL و responsive تست شده باشد؛ blockerهای keyboard/accessibility بسته شوند؛ screenshot و report قبل/بعد ذخیره شود.

---

# 8. QA-04 — Configuration Control Plane و Settings

## هدف

تأیید مدیریت امن و قابل‌بازگشت تنظیمات از UI، بدون تغییر کد برای تغییر مقادیر پشتیبانی‌شده.

## سناریوهای Backend و API

- دریافت descriptorهای معتبر از registry واقعی.
- رد schema version ناشناخته یا payload ناسازگار.
- ایجاد draft و revision جدید.
- optimistic locking: دو editor هم‌زمان، دومی 409 دریافت کند.
- test result فقط برای همان revision معتبر باشد.
- هر تغییر بعدی test قبلی را invalidate کند.
- transition نامعتبر به ACTIVE رد شود.
- apply failure، active revision قبلی را حفظ کند.
- rollback تاریخچه را پاک نکند و revision جدید بسازد.
- audit event ساخته شود؛ secret و payload حساس وارد audit نشود.
- worker/job revision دقیق مورد استفاده را ثبت کند.
- restart برنامه active revision معتبر را بازیابی کند.

## سناریوهای Secret

- POST/PATCH مقدار secret را دریافت کند اما GET هیچ‌گاه secret را پس ندهد.
- مقدار secret در response، DOM، browser storage، URL، logs، audit، trace، export و exception دیده نشود.
- تغییر setting غیرsecret، secret قبلی را ناخواسته خالی نکند.
- حذف secret action صریح و audit‌شده باشد.
- credential rotation در صورت پشتیبانی، شکست را بدون حذف credential فعال قبلی مدیریت کند.
- master key از UI قابل دریافت یا تغییر نباشد.

## سناریوهای UI

- unsaved changes مشخص باشند.
- خروج از فرم با draft تغییرکرده هشدار مناسب بدهد.
- form validation field-level و backend-level هماهنگ باشد.
- save draft با activate اشتباه نشود.
- revision history و rollback واضح باشد.
- permission کاربر در API enforce شود، نه فقط مخفی‌شدن button.

## معیار عبور QA-04

تمام lifecycle و secret tests پاس شوند؛ config فعال بعد از restart درست مصرف شود؛ هیچ secret leakage مشاهده نشود؛ و conflictهای هم‌زمان بی‌صدا overwrite نشوند.

---

# 9. QA-05 — Provider Catalog، AI Gateway و Free Policy

## هدف

اثبات جداسازی Provider، Model، Connectivity، Model Availability، Gateway، Policy و Routing.

## آزمون‌های تفکیکی

1. Registry catalog: Providerهای واقعاً پیاده‌سازی‌شده را فهرست کند.
2. Provider discovery: مورد شناخته‌شده را فقط به‌صورت draft/discovered ثبت کند؛ auto-enable نکند.
3. Credential test: نبود/نامعتبر بودن credential با خطای safe گزارش شود.
4. Connectivity: پاسخ endpoint و status واقعی از model check جدا باشد.
5. Model verification: شناسهٔ دقیق مدل و قابلیت‌های واقعاً تأییدشده ثبت شود.
6. Policy: Free Policy، quota و محدودیت مدل اعمال شود.
7. Gateway: همهٔ درخواست‌های واقعی از مسیر مجاز AI Gateway عبور کنند.
8. Routing: provider غیرفعال یا policy-blocked انتخاب نشود.
9. Fallback: fallback پنهان، paid یا خارج از policy رخ ندهد.
10. Usage: token/usage/cost فقط از پاسخ/دادهٔ معتبر ثبت شود؛ مقدار حدسی نباشد.
11. Secret: credential در error/trace/log ظاهر نشود.

## Failure injection

با provider mock یا transport قابل‌تزریق، موارد زیر را تست کن:
- timeout؛
- DNS/connect failure؛
- TLS failure؛
- 401/403؛
- 404 model not found؛
- 429 و Retry-After؛
- 5xx؛
- malformed JSON؛
- empty/invalid model response؛
- rate limit/usage metadata missing.

## Live test

فقط در `optional-live-provider` و با opt-in مالک. قبل از اجرا نام Provider و مدل و احتمال هزینه/محدودیت را safe گزارش کن. تست live باید حداقل درخواست و token مجاز داشته باشد و هیچ fallback پنهانی انجام ندهد.

## معیار عبور QA-05

هیچ state با state دیگر یکی گرفته نشود؛ Provider جدید خودکار enable نشود؛ Free Policy در تمام مسیرها enforce شود؛ testهای خطا و secret leakage پاس شوند.

---

# 10. QA-06 — ارزیابی انسانی Kev، Laya، Rules و Screening

## هدف

ارزیابی اینکه screening چه میزان محتوای مرتبط را تشخیص می‌دهد، چه میزان خبر نامرتبط را عبور می‌دهد و آیا انتخاب مدل/قواعد بر اساس دادهٔ انسانی است.

## 10.1 Dataset governance

- مجموعهٔ طلایی با نمونه‌های فارسی و انگلیسی، منابع گوناگون و موارد ambiguous ساخته شود.
- هدف اولیه می‌تواند ۱۰۰ تا ۲۰۰ نمونه باشد؛ کفایت نهایی با تنوع و بازهٔ اطمینان سنجیده شود.
- دو برچسب‌زن مستقل برای برچسب relevance ترجیحاً استفاده شوند؛ اختلاف‌ها adjudicate و ثبت شوند.
- label guide، version، تاریخ، برچسب‌زن و دلیل اختلاف نگه داشته شوند.
- train/dev/test split با جلوگیری از leakage منبع، نسخه‌های duplicate و خبرهای یک رویداد مرتبط ساخته شود.
- test set تا زمان evaluation در routing tuning مصرف نشود.

## 10.2 مدل‌های مورد ارزیابی

حداقل مقایسه:
- deterministic rules baseline؛
- Kev local integration؛
- Laya local integration؛
- hybrid policy که فقط بر اساس معیارهای از پیش تعیین‌شده مجاز است؛
- AI Gateway fallback فقط در جایی که معماری و policy فعلی اجازه می‌دهند.

Kev و Laya جایگزین Priority P0–P4، event/claim extraction، graph یا تحلیل موجود نیستند؛ فقط نقش screening مورد توافق را ارزیابی کن.

## 10.3 سنجه‌ها

- precision؛
- recall؛
- F1؛
- false-positive rate؛
- false-negative rate؛
- confusion matrix؛
- latency p50/p95؛
- memory footprint؛
- CPU usage و زمان اجرای هر نمونه؛
- میزان `uncertain/abstain`؛
- اختلاف عملکرد فارسی/انگلیسی و دسته‌های موضوعی.

معیار پذیرش را پیش از مشاهدهٔ نتیجه با مالک تعریف کن. یک مدل با F1 بهتر ممکن است برای P0/P1 false negative نامناسب داشته باشد؛ بنابراین metric کل به‌تنهایی کافی نیست.

## 10.4 Hardware compatibility

محیط هدف اعلام‌شده Windows و CPU خانوادهٔ i5 است؛ GPU و RAM هنوز مشخص نیستند. قبل از نصب/اجرای مدل:
- مدل/نسخه/مجوز/حجم artifact را بررسی کن؛
- CPU/RAM/GPU موجود را فقط با ابزار محلی ثبت کن؛
- dependency و runtime را pin/verify کن؛
- مصرف حافظه، startup time و latency را اندازه بگیر؛
- نصب package یا دانلود وزن سنگین بدون تأیید و بررسی فضای دیسک انجام نده.

## 10.5 Routing decision

- هیچ مدل محلی صرفاً به دلیل اجرای موفق انتخاب production-like نمی‌شود.
- مدل منتخب باید روی held-out set و محدودیت سخت‌افزار قابل قبول باشد.
- آستانه و نسخهٔ مدل ثبت شود.
- موارد uncertain باید مسیر موجود و مجاز را طی کنند.
- خروجی مدل untrusted data است؛ هرگز instruction یا code قابل اجرا تلقی نشود.

## معیار عبور QA-06

Gold set و label guide موجود؛ evaluation repeatable؛ metrics تفکیک‌شده؛ hardware report؛ routing recommendation با trade-off؛ و هیچ ادعای کیفیت بدون held-out evidence وجود نداشته باشد.

اگر دادهٔ انسانی/ماشین لازم موجود نیست، نتیجه `BLOCKED` است، نه `VERIFIED`.

---

# 11. QA-07 — Source Bot، Ingestion و Raw Data Contract

## هدف

تأیید اینکه فقط یک مسیر ingestion مالک دریافت و ایجاد RawItem است و Source Bot مسیر موازی یا تحلیل موازی نمی‌سازد.

## سناریوهای اصلی

- RSS/Atom source معتبر با چند item جدید.
- JSON/API با pagination.
- CSV با encoding/delimiter/mapping متفاوت.
- XML معتبر و XML دارای DTD/XXE.
- HTML از مسیر Scrapy موجود؛ parsing با Trafilatura روی HTML دریافت‌شده، بدون fetch دوم.
- Source با 401/403/404/429/5xx.
- timeout، connection reset و response ناقص.
- ETag/Last-Modified و unchanged response.
- تکرار fetch و restart runner.
- Source خراب در کنار Source سالم؛ failure isolation.

## Invariants

- هر item خام از قرارداد مرکزی ingestion وارد شود.
- raw source payload برای audit نگه داشته شود، بدون mutate شدن توسط normalizer.
- provenance شامل source، external ID، URL و timestamps طبق قرارداد موجود باشد.
- adapter مستقیماً SQL domain یا مسیر analysis را اجرا نکند.
- preview/test-fetch با ingest واقعی یکی نباشد.
- source-specific error یک source دیگر را متوقف نکند.
- retry محدود و backoff قابل مشاهده باشد.

## معیار عبور QA-07

تمام adapterهای موجود contract tests داشته باشند؛ مسیر واحد ingestion اثبات شود؛ دادهٔ خام و provenance حفظ شود؛ restart و failure isolation کار کند.

---

# 12. QA-08 — SSRF، DNS، Redirect و امنیت Adapterها

## هدف

اثبات اینکه دریافت URL منبع نمی‌تواند به شبکهٔ داخلی، metadata endpoint یا مقصد غیرمجاز دسترسی پیدا کند.

## Test matrix امنیت URL

| مورد | Expected |
|---|---|
| scheme غیر از HTTP/HTTPS | reject |
| URL دارای userinfo | reject |
| localhost و loopback IPv4 | block |
| loopback IPv6 | block |
| private IPv4 و IPv6 | block |
| link-local و metadata IP | block |
| multicast/reserved/unspecified | block |
| hostname با A/AAAA عمومی و خصوصی mixed | block یا policy fail-closed |
| DNS rebinding بین validation و connect | block |
| redirect از public به private | block |
| چند redirect یا loop | bounded/reject |
| پاسخ بسیار بزرگ یا slow body | size/time limit |
| header CRLF/injection | reject/sanitize |
| TLS certificate invalid | fail closed |
| proxy environment ناخواسته | نباید کنترل امنیتی را دور بزند |

## تست DNS و Redirect

از fake resolver و fake transport قابل تزریق استفاده کن. تست باید زمان resolve، IP اعتبارسنجی‌شده و IP مقصد واقعی socket را مقایسه کند یا مکانیزم معادل امن موجود را ثابت کند. صرفاً تست تابع URL parser کافی نیست.

## تست secrets و errors

- headerهای authorization در logs ثبت نشوند.
- query token در exception/URL کامل چاپ نشود.
- response body ناشناس به‌صورت کامل در UI نمایش داده نشود.
- redirect location حاوی secret sanitize شود.

## معیار عبور QA-08

تمام testهای negative پاس شوند؛ هر unknown network condition به fail-closed یا behavior امن و مستند منجر شود؛ هیچ راه bypass از proxy، redirect یا IPv6 وجود نداشته باشد.

---

# 13. QA-09 — Exact Dedup، Near-Duplicate و Cluster

## هدف

تأیید تشخیص duplicate بدون حذف فیزیکی داده یا از دست‌دادن provenance.

## سناریوهای exact duplicate

- external/source ID یکسان.
- canonical URL یکسان با تفاوت query tracking.
- normalized content hash یکسان.
- whitespace/Unicode normalization در فارسی (ی/ک و فاصله‌ها) فقط روی normalized copy.
- دو source مختلف با یک محتوا؛ دو observation/provenance حفظ شود.
- دو worker هم‌زمان یک article را وارد کنند؛ atomic upsert/unique constraint duplicate row ناخواسته نسازد.

## سناریوهای near duplicate

- عنوان مشابه ولی body متفاوت؛ نباید فقط با title یکی فرض شود.
- خبرهای یک رویداد با جزئیات/زمان متفاوت؛ cluster relation مجاز است، merge محتوا خودکار نیست.
- ترجمهٔ فارسی/انگلیسی یک خبر.
- متن کوتاه که MinHash/LSH قابل اعتماد نیست؛ uncertain نگه داشته شود.
- similarity threshold نزدیک مرز؛ score و algorithm version ثبت شود.

## Time-series

کلید duplicate باید dataset/indicator/period را لحاظ کند. دو مقدار برای دورهٔ متفاوت duplicate نیستند؛ دو رکورد یک indicator و period با source متفاوت باید semantics موجود را رعایت کنند.

## Invariants

- Dedup هیچ hard delete انجام ندهد.
- canonical record و cluster relation قابل ردیابی باشند.
- source observations/provenance حفظ شوند.
- حذف/ادغام article، Event، Claim، Evidence، Forecast، Entity و Memory را به‌طور ضمنی تغییر ندهد.

## معیار عبور QA-09

نتیجهٔ exact/near/uncertain قابل تشخیص باشد؛ race test پاس شود؛ provenance همهٔ sourceها حفظ شود؛ هیچ delete رخ ندهد.

---

# 14. QA-10 — Priority P0–P4 و Relevance Screening

## هدف

اثبات جدایی Priority از Relevance و Analysis، و اطمینان از deterministic fallback.

## Priority tests

- boundary scoreها در مرز 25، 50، 75 و 90.
- P0/P1/P2/P3/P4 طبق rule/config version واقعی.
- reason codes و توضیح تصمیم با score سازگار باشند.
- confidence و rule score جدا ثبت شوند.
- config threshold version برای هر تصمیم قابل شناسایی باشد.
- دادهٔ ناقص، unknown source/type و conflict rule.
- AI fallback فقط در شرط عدم اطمینان/مرز/conflict مجاز فعال شود.
- در دسترس نبودن AI، extraction و ingest متوقف نشود؛ fallback/pending code مستند ثبت شود.
- AI output به عنوان instruction اجرا نشود.

## Relevance tests

- مرتبط، نامرتبط، ambiguous، زبان دوم، خبر کپی‌شده، متن کوتاه، headline-only.
- screening نباید priority را بی‌دلیل تغییر دهد.
- P0/P1 policyهای حساس در false-negative test جداگانه بررسی شوند.
- Mock screening و real screening در UI/API قابل تفکیک باشند.

## معیار عبور QA-10

مرزها و reason codes با test پوشش داده شده باشند؛ Priority/Relevance/Analysis جدا بمانند؛ AI down behavior امن باشد؛ thresholdهای تجربی بدون gold set calibrated اعلام نشوند.

---

# 15. QA-11 — Durable Jobs، Dispatch، Retry، Lease و Resume

## هدف

تأیید اجرای بادوام Jobها، عدم اجرای تکراری، بازیابی پس از crash و قابلیت ردیابی.

## State machine tests

- queued → running → succeeded.
- queued → running → retryable failure → queued/retry state.
- permanent failure → terminal failure.
- pause/cancel طبق semantics واقعی.
- lease expiry و reclaim.
- worker crash پس از claim و پیش از completion.
- worker crash پس از side effect و پیش از ack؛ idempotency باید از duplicate effect جلوگیری کند.
- restart backend/worker و resume.
- maximum attempts و dead-letter/terminal behavior.

## Concurrency tests

- دو worker claim هم‌زمان.
- worker A lease را از دست بدهد؛ worker B claim کند؛ A دیرهنگام برگردد.
- duplicate enqueue با idempotency key.
- scheduler overlap در چند process.
- JobRun unique partial index/constraint در صورت وجود.

## ETag و checkpoint

- ETag/Last-Modified cache بین runها در process lifecycle مورد انتظار پایدار باشد.
- بعد از restart رفتار cache طبق persistence/scope واقعی باشد.
- resume نباید item سالم را از دست بدهد یا دوباره side effect ایجاد کند.
- config revision به job pin شود.

## معیار عبور QA-11

هیچ job گم، دو بار اجرا یا بدون owner نماند؛ restart و lease tests پاس شوند؛ metrics/trace و terminal reason موجود باشند.

---

# 16. QA-12 — Pending/Mock Recovery و Pipeline تحلیل

## QA-12A: Pending و Mock

- pending قدیمی شناسایی شود؛ خودکار به موفقیت تبدیل نشود.
- mock result با flag واضح از real result جدا باشد.
- retry real فقط طبق policy و idempotency باشد.
- result قدیمی‌تر نتواند نتیجهٔ جدیدتر را overwrite کند.
- موارد غیرقابل‌تعیین `PENDING/INSUFFICIENT_EVIDENCE/BLOCKED` باقی بمانند.

## QA-12B: Analysis pipeline

برای هر مرحلهٔ واقعاً موجود، ورودی، خروجی، lineage، status و retry بررسی شود:

- classification؛
- event extraction؛
- claim extraction؛
- evidence linking؛
- entity resolution/analysis؛
- GraphRAG/graph relation در صورت وجود؛
- domain analysis؛
- forecast در مراحل مربوط.

## Invariants

- هر خروجی به article/source/job و version منطق/مدل قابل ردیابی باشد.
- مرحله‌ای که failed است downstream را به‌صورت جعلی completed نشان ندهد.
- retry یک مرحله side effect تکراری نسازد.
- رابطهٔ Event/Claim/Evidence/Entity/Forecast با article حفظ شود.
- تغییر config وسط pipeline بدون checkpoint و revision trace اتفاق نیفتد.

## معیار عبور QA-12

یک article آزمایشی از ingest تا خروجی‌های تحلیل قابل‌ردیابی باشد؛ خطا و retry هر stage جدا ثبت شود؛ دادهٔ ناقص به عنوان خروجی معتبر جعل نشود.

---

# 17. QA-13 — API، Operations، Monitoring و Alert Delivery

## API

- schema validation و typed response.
- authorization روی هر endpoint و object.
- pagination/filter/sort deterministic.
- error envelope دارای code پایدار و correlation ID.
- rate limiting و request size.
- عدم افشای internal stack trace یا secret.

## Monitoring

- counts با query واقعی و unit مشخص.
- stale/unknown از zero جدا.
- metrics worker/queue/ingestion/Provider/archive.
- labels کم‌کاردینالیتی؛ article ID/token به‌عنوان label متریک ممنوع.
- timestamp و timezone واضح.

## Telegram/Email Alert Delivery

- delivery status مستقل از alert evaluation.
- idempotency برای پیام تکراری.
- timeout، 429، 5xx، invalid destination و permission failure.
- retry/backoff و terminal state.
- ack/resolve و delivery event با هم اشتباه نشوند.
- credential در log و response ظاهر نشود.

## Source/Integration UI

- CRUD/validation/test/preview/enable/disable با revision.
- preview بدون ingestion.
- `NEEDS_ADAPTER` غیرفعال و غیرقابل schedule باشد.
- last success/error/next run و source health به دادهٔ واقعی متصل باشند.

## معیار عبور QA-13

API security و contract tests پاس شوند؛ monitoring از دادهٔ واقعی باشد؛ delivery idempotent باشد؛ integration UI هیچ adapter ناشناخته‌ای را اجرا نکند.

---

# 18. QA-14 — Telegram Smart Archive، Recovery و Purge Safety

## هدف

تأیید بسته‌بندی کامل، upload، re-download، صحت‌سنجی، restore و سپس eligibility حذف؛ با فرض اینکه purge واقعی پیش‌فرض خاموش است.

## 18.1 Archive eligibility

- فقط articleهایی که تمام processing/analysis وابسته آن‌ها terminal-success و کامل است eligible باشند.
- failed، pending، ambiguous و job دارای retry فعال حذف/آرشیو قطعی نشوند.
- shared Event/Claim/Evidence/Forecast/Entity/Memory و relationshipها محافظت شوند.
- نسخهٔ article هنگام snapshot با نسخهٔ فعلی مقایسه شود.
- تغییر article بین eligibility و package باعث abort/re-evaluate شود.

## 18.2 Package integrity

- `manifest.json` با schema version و archive ID.
- payloadهای article و analysis و provenance طبق قرارداد v1.5.
- record counts و IDs.
- SHA-256 برای هر فایل و checksum manifest.
- ZIP traversal، symlink و path injection رد شوند.
- archive دارای secret، token، credential یا دادهٔ خارج از scope نباشد.
- ZIP قابل بازشدن، قابل validate و قابل test-restore باشد.

## 18.3 Telegram upload/download

- ابتدا transport mock و test destination.
- file size و multipart split بدون شکستن atomicity مقاله.
- metadata شامل chat/message/file IDs طبق قرارداد موجود.
- پس از upload، فایل از remote دوباره download شود.
- hash/size/count/manifest و content validate شوند.
- صرف upload یا وجود message ID به معنی `REMOTE_VERIFIED` نیست.

## 18.4 Restore

- ابتدا restore به DB آزمایشی خالی/namespace جدا.
- یک article و یک archive کامل.
- عدم duplicate هنگام restore تکراری.
- عدم overwrite نسخهٔ جدیدتر.
- idempotent restore و audit.
- relationshipها و provenance حفظ شوند.

## 18.5 Purge negative tests

این موارد باید حتماً ثابت کنند چیزی حذف نمی‌شود:
- `ARCHIVE_AUTO_PURGE_ENABLED=false`.
- archive upload شده ولی re-download نشده.
- hash mismatch.
- manifest ناقص/خراب.
- restore test fail.
- article در حین archive تغییر کرده.
- active job/dependency وجود دارد.
- eligibility نامشخص است.
- shared relationship کشف‌نشده یا unresolved وجود دارد.
- kill/restart وسط deletion batch.
- toggle خاموش‌شده وسط batch.

## 18.6 Purge positive test — فقط در DB آزمایشی

فقط پس از تست‌های منفی و با policy/approval آزمایشی:
- موارد eligible دقیقاً انتخاب شوند.
- dry-run count و IDs با delete plan یکسان باشد.
- حذف فقط فیلدهای مجاز bulky انجام شود.
- identifier، hash، priority، provenance، archive ref، audit و tombstone لازم باقی بمانند.
- اجرای دوباره delete batch هیچ side effect جدیدی نسازد.
- toggle OFF فوراً شروع batch جدید را متوقف کند و in-flight را طبق checkpoint امن pause کند.

## معیار عبور QA-14

تا پیش از remote re-download + validation + test restore، هیچ purge eligibility قطعی نیست. تمام negative tests پاس شوند. در تست local، auto purge پیش‌فرض OFF و dry-run ON بماند. هرگونه تست destructive فقط روی DB آزمایشی و با evidence کامل مجاز است.

---

# 19. QA-15 — Defect Register، Performance و Repository Hygiene

## 19.1 Defect lifecycle

`OPEN → TRIAGED → REPRODUCED → FIX_IN_PROGRESS → FIXED → REGRESSION_VERIFIED → CLOSED`

حالت‌های فرعی:
- `BLOCKED`: dependency/credential/decision ندارد.
- `WONT_FIX`: فقط با تأیید مالک و دلیل.
- `DUPLICATE`: لینک به defect canonical.
- `SPEC_GAP`: نیازمند تصمیم دربارهٔ requirement.

## 19.2 شدت و اولویت

| Severity | تعریف | نمونه |
|---|---|---|
| `S0 Critical` | داده‌ریزی، افشای secret، حذف غیرمجاز، bypass امنیتی یا فساد داده | purge ناخواسته، SSRF داخلی، credential leak |
| `S1 High` | مسیر اصلی کار نمی‌کند یا نتیجهٔ حیاتی اشتباه است | dispatch duplicate، analysis گم‌شده، P0 misclassified گسترده |
| `S2 Medium` | بخشی از قابلیت یا تجربهٔ کاربری با workaround قابل استفاده است | filter خراب، dashboard widget ناقص |
| `S3 Low` | مشکل ظاهری/مستنداتی با ریسک کم | فاصله، متن یا alignment |

اولویت remediation علاوه بر severity باید frequency، scope، exploitability، data impact و وجود workaround را لحاظ کند.

## 19.3 قالب Defect

- `Defect ID` مثل `GI-BUG-0001`؛
- عنوان و severity؛
- Stage/Requirement IDs؛
- environment و commit؛
- preconditions؛
- reproduction steps؛
- expected vs actual؛
- logs/evidence امن؛
- root cause؛
- affected files/components؛
- proposed minimal fix؛
- regression tests؛
- data/security impact؛
- status و owner/decision required.

## 19.4 Performance

قبل از بهینه‌سازی baseline بگیر:
- query count و زمان query؛
- p50/p95 latency؛
- memory/CPU؛
- N+1 evidence؛
- payload size؛
- frontend bundle/route load؛
- worker throughput و queue wait.

بهینه‌سازی بدون اندازه‌گیری ممنوع. cache، index، concurrency یا batching جدید باید با correctness test و rollback plan همراه باشد.

## 19.5 Repository hygiene

- log/temp/cache files را شناسایی کن، محتوا را بررسی کن، secret scan انجام بده.
- فقط فایل‌های واضح و disposable را بعد از حفاظت پاک کن.
- `.gitignore` را narrow و هدفمند اصلاح کن.
- فایل مستند قدیمی را حذف نکن؛ status/date/scope را مشخص کن.
- test count ثابت در docs ننویس؛ از output واقعی همان run استفاده کن.

## معیار عبور QA-15

همهٔ S0/S1 رفع یا به‌صورت blocker مورد تأیید مالک ثبت شوند؛ هر patch تست regression داشته باشد؛ performance improvement با baseline مقایسه شود؛ پاک‌سازی فایل بدون خطر انجام شود.

---

# 20. QA-16 — Backup، Restore، Migration و Local Acceptance

## Backup/Restore

- backup از DB آزمایشی/محلی با دستور رسمی project تهیه شود.
- وجود فایل، size، checksum و timestamp ثبت شود.
- restore به DB جدا انجام شود؛ هرگز روی DB اصلی overwrite نکن.
- row counts و referential integrity بررسی شوند.
- app پس از restore بتواند read pathها و workflowهای منتخب را اجرا کند.
- secrets خارج از backup عمومی و با روش مجاز نگهداری شوند.
- backup corrupt/incomplete test شود.

## Local acceptance scenario

یک سناریوی end-to-end کنترل‌شده:

1. ایجاد Source آزمایشی پشتیبانی‌شده.
2. validate، test fetch و preview.
3. enable در محیط تست.
4. ingestion یک مجموعهٔ کوچک داده.
5. بررسی raw payload و provenance.
6. اجرای normalize/dedup.
7. بررسی priority و reason codes.
8. screening با Rules/مدل local یا Mock کاملاً برچسب‌خورده.
9. enqueue و dispatch Job.
10. تحلیل با مسیر موجود و ثبت lineage.
11. نمایش نتیجه در UI.
12. ایجاد alert آزمایشی و بررسی delivery mock یا live مجاز.
13. archive dry-run و ساخت ZIP آزمایشی.
14. verify و restore به DB آزمایشی.
15. restart سرویس‌ها و بررسی resume/consistency.

## معیار عبور QA-16

سناریو از ابتدا تا انتها با دادهٔ تست، PostgreSQL، شواهد provenance و UI قابل تکرار باشد؛ restore موفق باشد؛ هیچ purge واقعی یا side effect بیرونی ناخواسته رخ نداده باشد.

---

# 21. QA-17 — Forecast Evaluation و Calibration

## هدف

ارزیابی forecastها با outcome واقعی و جلوگیری از leakage یا ادعای دقت بدون دادهٔ کافی.

## تست‌های فنی

- forecast ID، target، horizon، as-of time و model/rule version ثبت شود.
- featureها فقط از داده‌ای استفاده کنند که در as-of time در دسترس بوده است.
- temporal split رعایت شود؛ random split برای سری زمانی به‌تنهایی کافی نیست.
- outcome resolution و source آن ثبت شود.
- forecastهای unresolved از denominator metric حذف/تفکیک شوند، نه اینکه شکست فرض شوند.
- calibration، Brier/log loss یا metric متناسب با نوع خروجی ارزیابی شود.
- confidence band و base rate بررسی شود.
- performance بر اساس horizon/topic/region تفکیک شود.
- baseline ساده برای مقایسه وجود داشته باشد.

## Governance

- threshold/metric قبل از evaluation تعریف شود.
- version model و data snapshot ثبت شود.
- metric بد نباید با حذف cohort یا تغییر label پنهان شود.
- اگر sample کافی نیست، وضعیت `INSUFFICIENT_SAMPLE` باشد.

## معیار عبور QA-17

forecast evaluation repeatable و temporal باشد؛ leakage بررسی شده باشد؛ outcome source معتبر باشد؛ confidence/calibration با metric مناسب گزارش شود.

---

# 22. ممیزی امنیتی سراسری v1.5

این فصل cross-cutting است و در هر Stage تکرار/اعمال می‌شود.

## 22.1 Authentication و Authorization

- عدم احراز هویت، token منقضی، role ناکافی، object-level access و privilege escalation تست شوند.
- UI visibility کنترل امنیتی نیست؛ هر endpoint جدا enforce کند.
- account/session secrets در log ثبت نشوند.
- تغییر credential، activation، rollback، restore و purge audit شوند.

## 22.2 SSRF و Network

از QA-08 استفاده کن و هر مسیر fetch را پیدا کن: source adapters، provider custom base URL، preview/test fetch، webhook/notification در صورت وجود. هیچ مسیر URLدار نباید بدون guard باشد.

## 22.3 Injection و Untrusted Content

- HTML articleها به‌صورت safe text/sanitized render شوند.
- prompt injection داخل source/article/model response اختیار اجرایی ایجاد نکند.
- SQL parameters و filter expressions امن باشند.
- CSV/Excel formula injection در export در صورت پشتیبانی بررسی شود.
- path traversal در archive و file download رد شود.

## 22.4 Secrets و PII

- secret scanning برای Git tracked/untracked.
- redaction در application logs، test reports، telemetry و error traces.
- data minimization در archive/export.
- fixtureها فاقد credential و PII غیرضروری باشند.

## 22.5 Dependency/Supply Chain

- lockfile و integrity بررسی شود.
- license/runtime compatibility مدل Laya/Kev بررسی شود.
- package install فقط با review مجوز و سازگاری.
- هیچ auto-install plugin/package در runtime وجود نداشته باشد.

## معیار عبور امنیت

هیچ S0 باز نماند. S1 امنیتی باید بسته یا با تصمیم صریح مالک و mitigation قابل‌قبول کنترل شود. تست‌هایی که به دسترسی/credential نیاز دارند `BLOCKED` ثبت شوند.

---

# 23. Master Traceability Matrix — اتصال نیاز تا تست و نقص

در `docs/qa/TRACEABILITY_MATRIX.csv` یا ساختار معادل، این ستون‌ها را نگه دار:

```text
requirement_id,stage_id,component,api_or_route,test_id,test_level,
precondition,expected_invariant,latest_result,evidence_ref,defect_id,
code_ref,test_ref,owner_decision,status,last_verified_commit
```

## گروه‌های الزامی Requirement ID

| گروه | محدوده |
|---|---|
| `REQ-BASE-*` | حفاظت، build، environment و DB |
| `REQ-UX-*` | Design System، navigation، dashboard، responsive، accessibility |
| `REQ-CONFIG-*` | descriptor، revision، approval، secret، rollback |
| `REQ-AI-*` | registry، Gateway، model، policy، usage |
| `REQ-EVAL-*` | gold set، Laya/Kev، metrics، routing |
| `REQ-INGEST-*` | Source Bot، RawItem، provenance، adapter |
| `REQ-SEC-*` | SSRF، DNS، auth، secrets، injection |
| `REQ-DEDUP-*` | exact، near، time-series، cluster، no-delete |
| `REQ-PRIORITY-*` | P0–P4، reason codes، fallback |
| `REQ-JOB-*` | dispatch، lease، retry، resume، idempotency |
| `REQ-ANALYSIS-*` | pipeline، lineage، result status |
| `REQ-OPS-*` | UI/API، monitoring، alert delivery |
| `REQ-ARCHIVE-*` | eligibility، ZIP، Telegram، verify، restore، purge |
| `REQ-PERF-*` | performance، scalability، responsiveness |
| `REQ-FORECAST-*` | outcome، temporal evaluation، calibration |

هر الزام باید حداقل به یک تست وصل شود؛ هر defect باید به الزام و test مربوطه وصل شود. الزام بدون test `UNTESTED` می‌ماند، نه PASS.

---

# 24. برنامهٔ ترتیب اجرا و توقف‌های اجباری

| مرحله | کار | نوع اجرا | توقف/گیت |
|---|---|---|---|
| `QA-00` | ممیزی checkout و baseline | فقط خواندنی | گزارش و توقف |
| `QA-01` | build/static/dependency checks | read/build | defect register و توقف در S0/S1 |
| `QA-02` | PostgreSQL/migration/CI | test DB | گیت اصلی DB و توقف |
| `QA-03` | UI/UX audit و tests | local E2E/manual | UX blockerها و گزارش |
| `QA-04` | config control plane | test DB + local UI | secret/revision/security gate |
| `QA-05` | Provider/Gateway/Policy | Mock، سپس live opt-in | عدم fallback/افشای secret |
| `QA-06` | Kev/Laya evaluation | local benchmark | Gold set + hardware gate |
| `QA-07` | ingestion | mock network + local PG | single-ingest contract |
| `QA-08` | SSRF/security | isolated network | هیچ bypass باز نماند |
| `QA-09` | dedup | seeded PG + concurrency | no-delete/provenance gate |
| `QA-10` | Priority/relevance | deterministic + evaluation data | semantics gate |
| `QA-11` | Jobs/resume | PG concurrency/crash simulation | no-loss/no-duplicate gate |
| `QA-12` | analysis pipeline | local test data | lineage gate |
| `QA-13` | UI/API/monitoring/alerts | E2E + mock/live opt-in | delivery/authorization gate |
| `QA-14` | Archive/restore/purge | test DB + mock Telegram | remote verify + restore gate؛ purge آخرین گیت |
| `QA-15` | defects/performance/hygiene | measured | S0/S1 gate |
| `QA-16` | backup/restore/local acceptance | local controlled | پذیرش کامل محلی |
| `QA-17` | forecast evaluation | data-dependent | continuous/blocked if insufficient data |

هر بار فقط یک مرحلهٔ اصلی فعال باشد. اگر S0 پیدا شد، اجرای مراحل وابسته متوقف شود تا ریسک مهار شود.

---

# 25. قالب گزارش روزانه/مرحله‌ای QA

هر گزارش باید در `docs/qa/reports/` با نام شامل Stage ID و تاریخ/شناسهٔ اجرا ذخیره شود. قالب:

```markdown
# QA Stage Report

- Stage ID:
- Date/time/timezone:
- Branch / HEAD:
- OS / Python / Node / PostgreSQL:
- Environment profile:
- Scope:
- Out of scope:

## Executive status
- VERIFIED / PARTIALLY_VERIFIED / NOT_VERIFIED / BLOCKED / FAILED
- S0/S1/S2/S3 counts:

## Baseline
- Working tree preserved:
- DB target verified:
- Backup/test data:

## Tests executed
| Test ID | Command/steps | Environment | Result | Duration | Evidence |

## Defects found
| Defect ID | Severity | Reproduced | Root cause | Status |

## Changes made
| File | Change | Reason | Risk | Rollback |

## Regression
- Focused tests:
- Domain suite:
- Full suite:
- Frontend lint/typecheck/build/E2E:
- PostgreSQL/migration:

## Security and data integrity
- Secret leakage:
- Authorization:
- SSRF:
- Data mutation/deletion:

## Remaining gaps / blockers

## Acceptance decision
- PASS / CONDITIONAL PASS / FAIL / BLOCKED
- Evidence supporting the decision:

## Next single stage recommended
```

گزارش باید فرمان دقیق اجراشده و نتیجه را ثبت کند؛ secret یا output حساس را در آن کپی نکن.

---

# 26. Definition of Done برای هر Fix و برای کل QA

## 26.1 Definition of Done برای Fix

- [ ] failure پیش از اصلاح بازتولید شده یا علت با شواهد کافی مشخص است.
- [ ] root cause مستند است.
- [ ] تست regression قبل از fix شکست می‌خورد (در مواردی که امکان‌پذیر است).
- [ ] patch کوچک و هم‌راستا با معماری موجود است.
- [ ] تست هدفمند بعد از fix پاس است.
- [ ] تست‌های همسایه و regression مرتبط پاس هستند.
- [ ] authorization/security/data invariants حفظ شده‌اند.
- [ ] migration/rollback در صورت نیاز بررسی شده است.
- [ ] docs و defect register به‌روز شده‌اند.
- [ ] هیچ تغییر کاربر یا دادهٔ ناخواسته از بین نرفته است.

## 26.2 Definition of Done برای کل QA v1.5

- [ ] همهٔ requirementهای v1.5 در traceability matrix ثبت شده‌اند.
- [ ] هیچ S0 باز نیست.
- [ ] S1ها بسته یا با تصمیم و mitigation روشن مالک ثبت شده‌اند.
- [ ] PostgreSQL suite و migration gates پاس شده‌اند.
- [ ] Frontend lint/typecheck/build و E2Eهای حیاتی پاس شده‌اند.
- [ ] UI/UX workflowهای حیاتی، RTL، responsive و keyboard بررسی شده‌اند.
- [ ] Provider/Model/Policy/Gateway به‌صورت تفکیک‌شده تست شده‌اند.
- [ ] Gold set و ارزیابی Kev/Laya یا blocker دقیق آن گزارش شده است.
- [ ] ingestion، provenance، security، dedup و priority تست شده‌اند.
- [ ] Job dispatch، retry، idempotency و restart recovery تست شده‌اند.
- [ ] analysis pipeline lineage اثبات شده است.
- [ ] archive ZIP، remote verification و restore تست شده‌اند.
- [ ] auto-purge به‌صورت پیش‌فرض خاموش و negative tests آن پاس شده‌اند.
- [ ] backup از DB آزمایشی restore شده است.
- [ ] local acceptance end-to-end تکرارپذیر است.
- [ ] همهٔ evidenceها بدون secret و با commit/reference مشخص نگهداری می‌شوند.

اگر دادهٔ انسانی، credential یا سرویس خارجی لازم در دسترس نیست، آن بخش `BLOCKED` می‌ماند؛ کل نسخه را به‌دلیل تست‌نشدن آن `VERIFIED` اعلام نکن.

---

# 27. پرامپت اجرایی نهایی برای AI کدنویس و QA Engineer

تو در این مأموریت نقش Senior/Staff Software Engineer، QA Architect و Security-minded Reviewer پروژهٔ GlobalIntelligence را داری.

## مأموریت

نقشه‌راه کامل GlobalIntelligence v1.5 را به‌عنوان specification محصول/فنی بخوان و این سند QA را به‌عنوان برنامهٔ تست، ارزیابی و remediation اجرا کن. پروژه از قبل بخش عمده‌ای پیاده‌سازی شده است؛ بنابراین هدف تو ساخت مجدد قابلیت‌ها نیست. باید وضعیت واقعی را کشف کنی، تست کنی، نقص‌های قابل‌بازتولید را پیدا کنی و فقط همان‌ها را اصلاح کنی.

## گام اول: فقط QA-00

- checkout و working tree را بررسی کن.
- تغییرات مالک را حفاظت کن.
- محیط local و DB هدف را شناسایی کن.
- گزارش‌های قبلی را بخوان ولی ادعاهای آن‌ها را مستقل فرض نکن.
- Stage Matrix، Baseline و Defect Register ایجاد/به‌روزرسانی کن.
- در این گام هیچ کد اجرایی یا migration را تغییر نده.
- گزارش QA-00 را تحویل بده و متوقف شو.

## پس از تأیید هر مرحله

فقط Stage بعدی که مالک اجازه داده اجرا کن. برای هر failure:
1. reproduce؛
2. collect evidence؛
3. root-cause analysis؛
4. propose minimal fix؛
5. add regression test؛
6. implement؛
7. focused verification؛
8. domain regression؛
9. update traceability and report.

## قواعد مطلق

- هیچ test را برای سبزشدن حذف/skip/تضعیف نکن.
- SQLite را به‌جای PostgreSQL معیار صحت ندان.
- هیچ دادهٔ واقعی را پاک یا reset نکن.
- purge واقعی ممنوع؛ فقط test DB و dry-run، مگر مالک جداگانه اجازهٔ صریح و محدودهٔ دقیق بدهد.
- Provider/Telegram live test فقط با opt-in و credential آزمایشی.
- secret را در هیچ خروجی یا artifact چاپ نکن.
- هیچ migration قدیمی را rewrite نکن.
- هیچ commit/push/PR/merge انجام نده.
- `git reset --hard`, `git clean -fd`, `docker compose down -v` یا حذف volume ممنوع.
- معماری سالم را بازنویسی نکن؛ مسیر ingestion، AI Gateway، dedup، priority و pipeline موازی نساز.
- VPS و deployment خارج از scope هستند.
- وقتی تستی اجرا نشده، `NOT RUN` بنویس؛ وقتی به credential نیاز دارد، `BLOCKED` بنویس؛ وقتی فقط Mock بوده، آن را `MOCK` گزارش کن.
- اگر requirement مبهم است، `SPEC_GAP` بنویس؛ رفتار جدید حدس نزن.

## خروجی هر Stage

گزارش مطابق فصل 25، defect register به‌روز، traceability matrix به‌روز و فقط یک پیشنهاد مرحلهٔ بعد بده. هیچ Stage را بدون تمام معیارهایش VERIFIED اعلام نکن و پس از گزارش متوقف شو.

## نخستین اقدام

فقط `QA-00` را اجرا کن. هیچ Fix یا تست مخرب را شروع نکن. ابتدا گزارش خواندنی و شواهد پایه را آماده کن.

---

# 28. یادداشت نهایی برای مالک پروژه

برای استفادهٔ صحیح، این سند را همراه **GlobalIntelligence v1.5 Full Engineering Specification** به AI بده. سند اصلی مشخص می‌کند محصول چه باید باشد؛ این سند مشخص می‌کند چطور آن را بیازماید و با چه شواهدی اصلاح/تأیید کند.

ترتیب پیشنهادی استفاده:

1. ابتدا QA-00 فقط‌خواندنی.
2. بررسی گزارش و تأیید مالک.
3. اجرای QA-01 و QA-02 برای زیرساخت و PostgreSQL.
4. ادامهٔ مرحله‌ای طبق QA-03 تا QA-17.
5. اصلاح هر defect با چرخهٔ reproduce → fix → regression.
6. پذیرش محلی فقط بعد از backup/restore و end-to-end واقعی.

**اصل نهایی:** هدف، گزارش زیبا یا عدد بزرگ تست نیست؛ هدف پروژه‌ای است که داده‌اش سالم بماند، در برابر شکست قابل‌بازیابی باشد، خروجی قابل اعتماد بدهد، در UI واقعاً قابل استفاده باشد و هر ادعای سلامت آن با شواهد مستقل پشتیبانی شود.
