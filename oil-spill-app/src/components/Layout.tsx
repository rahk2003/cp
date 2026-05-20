import { NavLink, Outlet, useLocation } from "react-router-dom";
import {
  Home,
  Map,
  Upload,
  MessageSquare,
  FileText,
  Info,
  Languages,
  Sparkles,
  Waves,
} from "lucide-react";
import { useLang } from "@/hooks/useLang";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { to: "/", icon: Home, key: "home" as const },
  { to: "/map", icon: Map, key: "map" as const },
  { to: "/analyze", icon: Upload, key: "analyze" as const },
  { to: "/chatbot", icon: MessageSquare, key: "chatbot" as const },
  { to: "/reports", icon: FileText, key: "reports" as const },
  { to: "/about", icon: Info, key: "about" as const },
];

export default function Layout() {
  const { t, lang, toggle } = useLang();
  const location = useLocation();

  return (
    <div className="min-h-screen bg-background relative overflow-x-hidden">
      {/* Decorative background */}
      <div className="fixed inset-0 -z-10 gradient-mesh opacity-60 pointer-events-none" />
      <div className="fixed inset-0 -z-10 bg-grid opacity-40 pointer-events-none" />

      <div className="flex min-h-screen">
        {/* Desktop sidebar */}
        <aside className="hidden lg:flex flex-col w-[260px] shrink-0 border-r border-ocean-100/70 bg-white/70 backdrop-blur-xl">
          <div className="px-6 pt-6 pb-8">
            <NavLink to="/" className="flex items-center gap-3 group">
              <div className="relative">
                <div className="absolute inset-0 bg-teal-400 blur-md opacity-50 group-hover:opacity-70 transition" />
                <div className="relative w-10 h-10 rounded-xl bg-gradient-to-br from-navy-500 to-teal-600 flex items-center justify-center shadow-lg">
                  <Waves className="w-5 h-5 text-white" strokeWidth={2.5} />
                </div>
              </div>
              <div>
                <div className="display-font text-xl font-bold text-navy-500 leading-none">
                  {t("brand")}
                </div>
              </div>
            </NavLink>
          </div>

          <nav className="flex-1 px-3 space-y-1">
            {NAV_ITEMS.map((item) => {
              const active = location.pathname === item.to;
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={cn(
                    "group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all",
                    active
                      ? "bg-navy-500 text-white shadow-md shadow-navy-500/20"
                      : "text-navy-400 hover:bg-ocean-50 hover:text-navy-500"
                  )}
                >
                  <Icon
                    className={cn(
                      "w-[18px] h-[18px] shrink-0 transition",
                      active ? "text-teal-300" : "text-navy-300 group-hover:text-teal-500"
                    )}
                  />
                  <span>{t(item.key)}</span>
                  {active && (
                    <span className="ms-auto w-1.5 h-1.5 rounded-full bg-teal-400 animate-pulse" />
                  )}
                </NavLink>
              );
            })}
          </nav>

          {/* Sidebar footer card */}
          <div className="px-3 pb-6">
            <div className="rounded-2xl bg-gradient-to-br from-navy-500 to-navy-700 p-4 text-white overflow-hidden relative">
              <div className="absolute -right-6 -top-6 w-24 h-24 bg-teal-400/20 rounded-full blur-2xl" />
              <Sparkles className="w-5 h-5 text-teal-300 mb-2" />
              <div className="text-sm font-semibold mb-1">
                {lang === "ar" ? "نموذج DeepLab v3+" : "DeepLab v3+ active"}
              </div>
              <div className="text-[11px] text-ocean-200 leading-relaxed">
                {lang === "ar"
                  ? "آخر تحديث: قبل 12 دقيقة"
                  : "Last sync: 12 minutes ago"}
              </div>
              <div className="mt-3 h-1.5 bg-white/10 rounded-full overflow-hidden">
                <div className="h-full w-[99%] bg-gradient-to-r from-teal-400 to-teal-300 rounded-full" />
              </div>
              <div className="mt-1.5 text-[10px] text-ocean-200">
                {lang === "ar" ? "دقة التحقّق 99%" : "Val. accuracy 99%"}
              </div>
            </div>
          </div>
        </aside>

        {/* Main */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Top bar */}
          <header className="sticky top-0 z-30 backdrop-blur-xl bg-white/70 border-b border-ocean-100/70">
            <div className="flex items-center gap-3 px-4 lg:px-8 h-16">
              {/* Mobile logo */}
              <NavLink to="/" className="lg:hidden flex items-center gap-2">
                <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-navy-500 to-teal-600 flex items-center justify-center">
                  <Waves className="w-4 h-4 text-white" strokeWidth={2.5} />
                </div>
                <span className="display-font text-lg font-bold text-navy-500">
                  {t("brand")}
                </span>
              </NavLink>

              <div className="hidden lg:flex items-center gap-2 text-sm">
                <span className="text-muted-foreground">
                  {lang === "ar" ? "أنت في" : "You are in"}
                </span>
                <span className="font-medium text-navy-500">
                  {t(
                    (NAV_ITEMS.find((i) => i.to === location.pathname)?.key ??
                      "home") as never
                  )}
                </span>
              </div>

              <div className="ms-auto flex items-center gap-2">
                <div className="hidden md:flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-emerald-50 border border-emerald-200">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  <span className="text-[11px] font-medium text-emerald-700">
                    {lang === "ar" ? "النظام يعمل" : "System online"}
                  </span>
                </div>

                <button
                  onClick={toggle}
                  className="inline-flex items-center gap-1.5 h-9 px-3 rounded-full border border-ocean-200 bg-white hover:bg-ocean-50 text-sm font-medium text-navy-500 transition"
                  aria-label="Toggle language"
                >
                  <Languages className="w-4 h-4 text-teal-600" />
                  <span className="font-mono text-xs">
                    {lang === "en" ? "AR" : "EN"}
                  </span>
                </button>
              </div>
            </div>
          </header>

          <main className="flex-1 pb-24 lg:pb-8">
            <Outlet />
          </main>

          {/* Mobile bottom nav */}
          <nav className="lg:hidden fixed bottom-0 inset-x-0 z-40 bg-white/90 backdrop-blur-xl border-t border-ocean-100">
            <div className="grid grid-cols-5 px-1 py-1.5">
              {NAV_ITEMS.map((item) => {
                const active = location.pathname === item.to;
                const Icon = item.icon;
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    className={cn(
                      "flex flex-col items-center justify-center gap-0.5 py-2 rounded-lg transition",
                      active ? "text-teal-600" : "text-navy-300"
                    )}
                  >
                    <Icon className="w-5 h-5" />
                    <span className="text-[9px] font-medium truncate max-w-full px-1">
                      {t(item.key)}
                    </span>
                  </NavLink>
                );
              })}
            </div>
          </nav>
        </div>
      </div>
    </div>
  );
}
