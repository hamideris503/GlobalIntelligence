/** هوشمندی اجتماعی: صفحهٔ رزرو. در رابط فعلی داده‌ای نمایش داده نمی‌شود. */
import { Empty, PageHeader, StateBanner } from "../ui";

export default function Society() {
  return (
    <div>
      <PageHeader title="هوشمندی اجتماعی" subtitle="سنجش روایت‌ها و فشارهای اجتماعی." />
      <StateBanner state="dev" text="Backend دارای مدل و router برای این حوزه است، اما صفحهٔ آن هنوز به رابط وصل نشده است. هیچ داده‌ٔ نمایشی هم برای آن ساخته نشده تا با دادهٔ واقعی اشتباه نشود." />
      <Empty text="پس از اتصال به API، تحلیل‌های اجتماعی و روایت‌ها اینجا نمایش داده می‌شوند." />
    </div>
  );
}
