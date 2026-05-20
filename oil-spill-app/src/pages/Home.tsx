import { Link } from "react-router-dom";
import {
  ArrowRight,
  Upload,
  Map,
  MessageSquare,
  FileText,
  Sparkles,
  Eye,
} from "lucide-react";
import { useLang } from "@/hooks/useLang";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { useSpills, useReports } from "@/hooks/useApi";
import { RiskPill } from "@/components/ui/Badge";
import { formatRelative, formatDate } from "@/lib/utils";
import { seaLabel, SEA_REGIONS, type SeaRegion } from "@/lib/seas";
import { reportHtmlUrl } from "@/lib/api";

function displayRegion(region: string, lang: "ar" | "en"): string {
  if (SEA_REGIONS.includes(region as SeaRegion)) {
    return seaLabel(region as SeaRegion, lang);
  }
  return region;
}

export default function HomePage() {
  const { t, lang } = useLang();
  const { spills, count, loading, error } = useSpills();
  const {
    reports,
    loading: reportsLoading,
    error: reportsError,
  } = useReports();

  const totalCoverageKm2 = spills.reduce((acc, s) => acc + (s.area_m2 || 0), 0) / 1_000_000;
  const stats = [
    {
      value: count ? count.toLocaleString() : loading ? "…" : "0",
      labelKey: "detected" as const,
    },
    {
      value: totalCoverageKm2 > 0 ? totalCoverageKm2.toFixed(1) : loading ? "…" : "0",
      labelKey: "coverage" as const,
    },
    { value: "99%", labelKey: "accuracy" as const },
    { value: "AR · EN", labelKey: "languages" as const },
  ];

  const latestSpills = [...spills]
    .sort(
      (a, b) =>
        new Date(b.detected_at).getTime() - new Date(a.detected_at).getTime()
    )
    .slice(0, 4);

  const latestReports = [...reports]
    .sort(
      (a, b) =>
        new Date(b.generated_at).getTime() - new Date(a.generated_at).getTime()
    )
    .slice(0, 4);

  return (
    <div className="px-4 lg:px-8 py-6 lg:py-10">
      {/* HERO */}
      <section className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-ocean-50 via-white to-teal-50/40 border border-ocean-100 px-6 py-10 lg:px-10 lg:py-14">
        <SeaWaves />

        <div className="relative max-w-4xl">
          <div className="relative">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-teal-50 border border-teal-200 text-teal-700 text-[11px] font-medium uppercase tracking-wider mb-6 animate-fade-in">
              <Sparkles className="w-3.5 h-3.5" />
              {t("heroEyebrow")}
            </div>

            <h1 className="display-font text-3xl sm:text-4xl lg:text-5xl xl:text-[56px] font-bold text-navy-500 leading-[1.28] tracking-normal text-balance animate-fade-in">
              {t("heroTitle").split(" ").slice(0, -3).join(" ")}{" "}
              <span className="text-teal-600">
                {t("heroTitle").split(" ").slice(-3).join(" ")}
              </span>
            </h1>

            <p
              className="mt-6 text-base lg:text-lg text-muted-foreground leading-relaxed max-w-2xl animate-fade-in"
              style={{ animationDelay: "0.1s" }}
            >
              {t("heroDesc")}
            </p>

            <div
              className="mt-8 flex flex-wrap gap-3 animate-fade-in"
              style={{ animationDelay: "0.2s" }}
            >
              <Button asChild size="lg" variant="default">
                <Link to="/analyze">
                  <Upload className="w-4 h-4" />
                  {t("ctaAnalyze")}
                  <ArrowRight className="w-4 h-4 rtl:rotate-180" />
                </Link>
              </Button>
              <Button asChild size="lg" variant="teal">
                <Link to="/map">
                  <Map className="w-4 h-4" />
                  {t("ctaMap")}
                </Link>
              </Button>
              <Button asChild size="lg" variant="outline">
                <Link to="/chatbot">
                  <MessageSquare className="w-4 h-4" />
                  {t("ctaAsk")}
                </Link>
              </Button>
            </div>

            <div
              className="mt-10 grid grid-cols-2 sm:grid-cols-4 gap-4 animate-fade-in"
              style={{ animationDelay: "0.3s" }}
            >
              {stats.map((s) => (
                <div
                  key={s.labelKey}
                  className="border-s-2 border-teal-400 ps-3"
                >
                  <div className="display-font text-2xl lg:text-3xl font-bold text-navy-500 tracking-tight">
                    {s.value}
                  </div>
                  <div className="text-[11px] uppercase tracking-wider text-muted-foreground mt-0.5">
                    {(
                      {
                        en: {
                          detected: "Spills detected",
                          coverage: "km² monitored",
                          accuracy: "Model accuracy",
                          languages: "Languages",
                        },
                        ar: {
                          detected: "تسرّب مكتشف",
                          coverage: "كم² تحت الرصد",
                          accuracy: "دقة النموذج",
                          languages: "لغة",
                        },
                      } as const
                    )[lang][s.labelKey]}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* أحدث الاكتشافات */}
      <section className="mt-16 lg:mt-20">
        <div className="flex items-end justify-between mb-6 flex-wrap gap-4">
          <div>
            <h2 className="display-font text-2xl lg:text-3xl font-semibold text-navy-500 tracking-tight">
              {lang === "ar" ? "أحدث الاكتشافات" : "Latest detections"}
            </h2>
            <p className="text-muted-foreground text-sm mt-1">
              {lang === "ar"
                ? "تسرّبات تم رصدها خلال الأيام الماضية"
                : "Spills detected in the last few days"}
            </p>
          </div>
          <Button asChild variant="outline" size="sm">
            <Link to="/map">
              <Map className="w-4 h-4" />
              {lang === "ar" ? "كل التسرّبات" : "View all on map"}
            </Link>
          </Button>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {loading && latestSpills.length === 0 ? (
            Array.from({ length: 4 }).map((_, i) => (
              <Card key={i} className="p-5 animate-pulse">
                <div className="h-3 w-16 bg-gray-200 rounded mb-3" />
                <div className="h-4 w-3/4 bg-gray-200 rounded mb-2" />
                <div className="h-3 w-1/2 bg-gray-100 rounded mb-4" />
                <div className="h-6 w-full bg-gray-100 rounded" />
              </Card>
            ))
          ) : latestSpills.length === 0 ? (
            <Card className="col-span-full p-6 text-center">
              <div className="text-sm text-muted-foreground">
                {error
                  ? lang === "ar"
                    ? `تعذّر الاتصال بالخادم: ${error}`
                    : `Backend connection failed: ${error}`
                  : lang === "ar"
                    ? "لا توجد بيانات حالياً. تأكدي من تشغيل الـ backend على المنفذ 8000."
                    : "No data yet. Make sure the backend is running on port 8000."}
              </div>
            </Card>
          ) : (
            latestSpills.map((s, i) => (
              <Card
                key={s.id}
                className="p-5 hover:shadow-lg hover:-translate-y-1 transition-all animate-fade-in"
                style={{ animationDelay: `${i * 60}ms` }}
              >
                <div className="flex items-start justify-between gap-2 mb-3">
                  <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground truncate max-w-[60%]">
                    {s.filename || s.id}
                  </div>
                  <RiskPill level={s.final_risk_level} size="sm" />
                </div>
                <div className="text-sm font-medium text-navy-500 truncate mb-1">
                  {displayRegion(s.region, lang)}
                </div>
                <div className="text-[11px] font-mono text-muted-foreground mb-3 truncate">
                  {s.filename}
                </div>
                <div className="flex items-center justify-between text-xs">
                  <div>
                    <div className="text-[10px] text-muted-foreground uppercase tracking-wide">
                      {lang === "ar" ? "التغطية" : "Coverage"}
                    </div>
                    <div className="font-semibold text-navy-500">
                      {Number(s.coverage_pct).toFixed(1)}%
                    </div>
                  </div>
                  <div className="text-[10px] text-muted-foreground">
                    {formatRelative(s.detected_at, lang)}
                  </div>
                </div>
              </Card>
            ))
          )}
        </div>
      </section>

      {/* أحدث التقارير */}
      <section className="mt-14 lg:mt-16">
        <div className="flex items-end justify-between mb-6 flex-wrap gap-4">
          <div>
            <h2 className="display-font text-2xl lg:text-3xl font-semibold text-navy-500 tracking-tight">
              {lang === "ar" ? "أحدث التقارير" : "Latest reports"}
            </h2>
            <p className="text-muted-foreground text-sm mt-1">
              {lang === "ar"
                ? "تقارير التقييم والاستجابة التي تم إصدارها مؤخراً"
                : "Recently generated assessment & response reports"}
            </p>
          </div>
          <Button asChild variant="outline" size="sm">
            <Link to="/reports">
              <FileText className="w-4 h-4" />
              {lang === "ar" ? "كل التقارير" : "All reports"}
            </Link>
          </Button>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {reportsLoading && latestReports.length === 0 ? (
            Array.from({ length: 4 }).map((_, i) => (
              <Card key={i} className="p-5 animate-pulse">
                <div className="h-3 w-20 bg-gray-200 rounded mb-3" />
                <div className="h-4 w-3/4 bg-gray-200 rounded mb-2" />
                <div className="h-3 w-1/2 bg-gray-100 rounded mb-4" />
                <div className="h-8 w-full bg-gray-100 rounded" />
              </Card>
            ))
          ) : latestReports.length === 0 ? (
            <Card className="col-span-full p-6 text-center">
              <div className="text-sm text-muted-foreground space-y-2">
                <p>
                  {reportsError
                    ? lang === "ar"
                      ? `تعذّر تحميل التقارير: ${reportsError}`
                      : `Could not load reports: ${reportsError}`
                    : lang === "ar"
                      ? "لا توجد تقارير بعد. يمكنك إصدار تقرير من صفحة التقارير أو من الخريطة."
                      : "No reports yet. Generate one from the Reports page or the map."}
                </p>
                <Button asChild variant="teal" size="sm">
                  <Link to="/reports">
                    <FileText className="w-4 h-4" />
                    {lang === "ar" ? "إصدار تقرير" : "Generate a report"}
                  </Link>
                </Button>
              </div>
            </Card>
          ) : (
            latestReports.map((r, i) => (
              <Card
                key={r.id}
                className="p-5 hover:shadow-lg hover:-translate-y-1 transition-all animate-fade-in flex flex-col"
                style={{ animationDelay: `${i * 60}ms` }}
              >
                <div className="flex items-start justify-between gap-2 mb-3">
                  <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground truncate max-w-[55%]">
                    {r.id}
                  </div>
                  <RiskPill level={r.risk_level} size="sm" />
                </div>
                <div className="text-sm font-medium text-navy-500 truncate mb-1">
                  {lang === "ar"
                    ? "تقرير التقييم والاستجابة"
                    : "Assessment & response"}
                </div>
                <div className="text-[11px] font-mono text-muted-foreground mb-3 truncate">
                  {r.filename || r.spill_id}
                </div>
                {r.summary ? (
                  <p className="text-[11px] text-muted-foreground line-clamp-2 mb-3 flex-1 leading-relaxed">
                    {r.summary}
                  </p>
                ) : (
                  <div className="flex-1" />
                )}
                <div className="flex items-center justify-between gap-2 text-xs border-t border-ocean-100 pt-3 mt-auto">
                  <div className="text-[10px] text-muted-foreground">
                    {formatRelative(r.generated_at, lang)}
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-[10px] font-medium text-teal-700">
                      {r.language === "AR"
                        ? lang === "ar"
                          ? "عربي"
                          : "AR"
                        : "EN"}
                    </span>
                    <a
                      href={reportHtmlUrl(r.id)}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-navy-500 text-white text-[10px] font-medium hover:bg-navy-600 transition"
                    >
                      <Eye className="w-3 h-3" />
                      {lang === "ar" ? "عرض" : "View"}
                    </a>
                  </div>
                </div>
                <div className="text-[9px] text-muted-foreground mt-1.5 font-mono">
                  {formatDate(r.generated_at, lang)}
                </div>
              </Card>
            ))
          )}
        </div>
      </section>
    </div>
  );
}

function SeaWaves() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      <div className="absolute -top-32 -end-32 w-[420px] h-[420px] rounded-full bg-teal-300/20 blur-3xl" />
      <div className="absolute -bottom-40 -start-40 w-[480px] h-[480px] rounded-full bg-ocean-300/20 blur-3xl" />

      <svg
        className="absolute bottom-0 left-0 w-[200%] h-44 lg:h-56 wave-slide-1"
        viewBox="0 0 1440 200"
        preserveAspectRatio="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          d="M0,120 C240,60 480,180 720,120 C960,60 1200,180 1440,120 L1440,200 L0,200 Z"
          fill="rgba(15,164,164,0.12)"
        />
      </svg>
      <svg
        className="absolute bottom-0 left-0 w-[200%] h-40 lg:h-52 wave-slide-2"
        viewBox="0 0 1440 200"
        preserveAspectRatio="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          d="M0,140 C200,90 400,180 720,140 C1040,100 1240,180 1440,140 L1440,200 L0,200 Z"
          fill="rgba(64,151,190,0.14)"
        />
      </svg>
      <svg
        className="absolute bottom-0 left-0 w-[200%] h-36 lg:h-44 wave-slide-3"
        viewBox="0 0 1440 200"
        preserveAspectRatio="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          d="M0,160 C320,120 640,200 960,160 C1200,130 1320,180 1440,160 L1440,200 L0,200 Z"
          fill="rgba(11,30,63,0.06)"
        />
      </svg>
    </div>
  );
}
