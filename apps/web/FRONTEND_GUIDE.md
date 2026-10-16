# راهنمای کوتاه Frontend — GlobalIntelligence

مسیر: `apps/web` — React 18 + Vite + TypeScript، مسیریابی hash، بدون کتابخانهٔ UI اضافه.

## اجرا
```
cd apps/web
npm install
npm run dev        # http://localhost:5173  (Backend پیش‌فرض: http://localhost:8000)
npm run build
```
آدرس Backend: متغیر `VITE_API_BASE_URL` یا صفحهٔ «تنظیمات». کلید API فقط در حافظه می‌ماند.

## فایل‌های مهم
| فایل | کاربرد |
|---|---|
| `src/design/tokens.css` | رنگ‌ها، فونت، فاصله، گوشه، سایه، عرض منو، تم تیره/روشن |
| `src/styles.css` | استایل اجزا (فقط از tokens استفاده می‌کند) |
| `src/ui.tsx` | پوسته (Shell)، جدول، فرم، مودال، نمودارها، StatCard، StateBanner |
| `src/icons.tsx` | آیکون‌های SVG |
| `src/router.ts` | مسیرها و ساختار منوی کناری (`NAV_GROUPS`) |
| `src/api.ts` | تنها لایهٔ ارتباط با Backend |
| `src/pages/*` | هر صفحه یک فایل |

## تغییر رنگ اصلی
در `src/design/tokens.css` مقدار `--brand-h` (طیف رنگ، ۰–۳۶۰) و در صورت نیاز `--brand-s` را عوض کنید. دکمه‌ها، منوی فعال، نمودارها و نشان‌ها خودکار تغییر می‌کنند.

## افزودن صفحهٔ جدید
1. `src/pages/my-page.tsx` بسازید و `export default function MyPage()` بنویسید (از `PageHeader` و `Section` استفاده کنید).
2. در `src/router.ts`: نام را به `RouteName` و آرایهٔ `valid` در `parseHash` اضافه کنید، و یک آیتم در `NAV_GROUPS` بگذارید.
3. در `src/App.tsx`: `{route.name === "my-page" && <MyPage />}`.

## ساخت کامپوننت
کامپوننت مشترک را در `src/ui.tsx` (یا فایل جدید کنار آن) بنویسید و فقط از متغیرهای `var(--...)` برای رنگ و فاصله استفاده کنید؛ هرگز رنگ ثابت (`#fff`) ننویسید.

## فرم جدید
از `Field` برای برچسب/توضیح، `button` + `useToast()` برای پیام موفقیت/خطا، و `ConfirmDialog` برای عملیات حساس استفاده کنید. اعتبارسنجی را قبل از `api.post` انجام دهید و دکمه را هنگام اجرا `disabled` کنید (نمونه: `pages/sources.tsx`).

## افزودن نمودار
`LineChart`، `Donut`، `Bars`، `Sparkline` در `ui.tsx` هستند. داده را با `useApi` بگیرید و فقط وقتی داده کافی است نمودار را رسم کنید؛ در غیر این‌صورت `<Empty />`.

## اتصال API موجود به صفحه
```tsx
const list = useApi<MyType[]>("/api/some/endpoint?limit=50", [tick]);
<Section title="عنوان" error={list.error} loading={list.loading}>
  {list.data?.length ? <Table .../> : <Empty />}
</Section>
```
`useApi` وضعیت loading/error را مدیریت می‌کند. برای عملیات POST از `RunButton` یا `api.post` استفاده کنید. Endpointها را حدس نزنید؛ از `backend/api/routers/` بخوانید.

## بخش‌های غیرواقعی
اگر API وجود ندارد: `<StateBanner state="demo" | "dev" | "nc" />` بگذارید، و داده‌ٔ نمونه را هرگز با داده واقعی مخلوط نکنید.

## کلیدها و سرویس‌ها
صفحهٔ `keys` از `src/config/services.ts` ساخته می‌شود. برای افزودن سرویس یا متغیر جدید فقط یک آبجکت به `SERVICES` اضافه کنید (نام متغیر، الزامی‌بودن، پیش‌فرض، لینک دریافت کلید، و «علاوه بر کلید چه لازم است»). وضعیت «کلید ثبت شده» از `GET /api/ai/providers` می‌آید. رابط هرگز کلید را ذخیره یا ارسال نمی‌کند؛ کلیدها فقط در `.env` سرور هستند.
