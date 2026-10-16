/** Tiny hash router (zero deps). Routes map 1:1 to sidebar sections. */
import { useEffect, useState } from "react";

export type RouteName =
  | "dashboard"
  | "news"
  | "sources"
  | "ai"
  | "chat"
  | "connections"
  | "keys"
  | "world"
  | "macro"
  | "geo"
  | "society"
  | "iran"
  | "markets"
  | "forecast"
  | "debate"
  | "scenarios"
  | "decisions"
  | "portfolio"
  | "evaluation"
  | "history"
  | "ops"
  | "settings"
  | "help"
  | "search";

export interface Route {
  name: RouteName;
  /** e.g. {id} for detail sub-views */
  param?: string;
}

export function parseHash(): Route {
  const raw = window.location.hash.replace(/^#\/?/, "");
  const [name, param] = raw.split("/");
  const valid: RouteName[] = [
    "dashboard", "news", "sources", "ai", "chat", "connections", "keys", "world", "macro", "geo", "society",
    "iran", "markets", "forecast", "debate", "scenarios", "decisions", "portfolio",
    "evaluation", "history", "ops", "settings", "help", "search",
  ];
  if ((valid as string[]).includes(name)) {
    return { name: name as RouteName, param: param || undefined };
  }
  return { name: "dashboard" };
}

export function nav(name: RouteName, param?: string): void {
  window.location.hash = `#/${name}${param ? `/${param}` : ""}`;
}

export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(parseHash);
  useEffect(() => {
    const onChange = () => setRoute(parseHash());
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}

/** وضعیت هر بخش منو: live = به API واقعی وصل است؛ dev = در دست توسعه؛ nc = نیازمند اتصال */
export type NavStatus = "live" | "dev" | "nc";

export interface NavItem { name: RouteName; label: string; icon: string; status?: NavStatus }
export interface NavGroup { title: string; items: NavItem[] }

/** برای افزودن صفحهٔ جدید: یک آیتم به گروه مناسب اضافه کنید (راهنما: FRONTEND_GUIDE.md). */
export const NAV_GROUPS: NavGroup[] = [
  { title: "نمای کلی", items: [
    { name: "dashboard", label: "داشبورد", icon: "dashboard" },
    { name: "news", label: "اخبار و رویدادها", icon: "news" },
  ] },
  { title: "داده و هوش مصنوعی", items: [
    { name: "sources", label: "منابع اطلاعاتی", icon: "sources" },
    { name: "ai", label: "هوش مصنوعی و مدل‌ها", icon: "ai" },
    { name: "chat", label: "گفت‌وگو", icon: "chat" },
    { name: "connections", label: "اتصالات و APIها", icon: "plug" },
    { name: "keys", label: "کلیدها و سرویس‌ها", icon: "key" },
  ] },
  { title: "تحلیل جهان", items: [
    { name: "world", label: "وضعیت جهان", icon: "world" },
    { name: "macro", label: "اقتصاد کلان", icon: "macro" },
    { name: "geo", label: "ژئوپلیتیک و سیاست", icon: "geo" },
    { name: "society", label: "هوشمندی اجتماعی", icon: "society", status: "dev" },
    { name: "iran", label: "ایران", icon: "iran" },
  ] },
  { title: "بازار و تصمیم", items: [
    { name: "markets", label: "بازارهای مالی", icon: "markets" },
    { name: "forecast", label: "پیش‌بینی‌ها", icon: "forecast" },
    { name: "debate", label: "بحث مدل‌ها", icon: "debate" },
    { name: "scenarios", label: "سناریوها و ریسک", icon: "scenarios" },
    { name: "decisions", label: "تصمیم‌ها و پیشنهادها", icon: "decisions" },
    { name: "portfolio", label: "سبد دارایی", icon: "portfolio" },
    { name: "evaluation", label: "ارزیابی عملکرد", icon: "evaluation" },
  ] },
  { title: "سیستم", items: [
    { name: "history", label: "تاریخچه و گزارش‌ها", icon: "history" },
    { name: "ops", label: "پردازش‌ها و وظایف", icon: "ops" },
    { name: "settings", label: "تنظیمات", icon: "settings" },
    { name: "help", label: "راهنما", icon: "help" },
  ] },
];

export const MENU = NAV_GROUPS.flatMap((g) => g.items);
