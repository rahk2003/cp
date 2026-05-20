import { Link } from "react-router-dom";
import { useLang } from "@/hooks/useLang";
import { Card, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import {
  Upload,
  ScanSearch,
  Map,
  Bot,
  FileText,
  Globe2,
  ArrowLeft,
  ArrowRight,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";

const WORKFLOW = [
  {
    icon: Upload,
    color: "from-navy-500 to-navy-700",
    link: "/analyze",
    ctaAr: "تحليل صورة",
    ctaEn: "Analyze image",
  },
  {
    icon: ScanSearch,
    color: "from-teal-500 to-ocean-600",
    link: "/analyze",
    ctaAr: "ابدأ التحليل",
    ctaEn: "Run analysis",
  },
  {
    icon: Map,
    color: "from-ocean-500 to-teal-600",
    link: "/map",
    ctaAr: "افتح الخريطة",
    ctaEn: "Open map",
  },
  {
    icon: Bot,
    color: "from-cyan-500 to-teal-600",
    link: "/chatbot",
    ctaAr: "الوكيل الذكي",
    ctaEn: "AI agent",
  },
  {
    icon: FileText,
    color: "from-amber-500 to-orange-600",
    link: "/reports",
    ctaAr: "التقارير",
    ctaEn: "Reports",
  },
] as const;

const COPY = {
  ar: {
    eyebrow: "كيف يعمل النظام",
    workflowTitle: "من الصورة إلى القرار في خطوات بسيطة",
    steps: [
      {
        title: "رفع صورة الأقمار الصناعية",
        summary:
          "ارفع صورة من Sentinel أو Landsat أو أي مصدر مدعوم (.tif, .png, .jpg). النظام يقرأ الإحداثيات من الملف إن وُجدت.",
      },
      {
        title: "الكشف والتحليل",
        summary:
          "نموذج DeepLab يحدّد منطقة التسرّب، ثم يُحسب المساحة، نسبة التغطية، القرب من اليابسة والشعاب المرجانية، ومستوى الخطورة.",
      },
      {
        title: "عرض على الخريطة التفاعلية",
        summary:
          "تظهر الحالة كنقطة ملوّنة حسب الخطورة. يمكنك التصفية حسب البحر، المساحة، والمسافة من الساحل، ومشاهدة تفاصيل كل حالة.",
      },
      {
        title: "السؤال عبر الوكيل الذكي",
        summary:
          "اسأل عن عدد الحالات، قارن بين تسربين، أو اطلب شرحاً لحالة محددة. الوكيل يجيب من قاعدة البيانات والتقارير السابقة.",
      },
      {
        title: "إصدار تقرير التقييم والاستجابة",
        summary:
          "تقرير HTML واحد يجمع صورة الكشف، التقييم، المقاييس جيو المكانية، وخطة استجابة مرتّبة — جاهز للعرض أو التنزيل.",
      },
    ],
    inOne: "باختصار",
    inOneText:
      "تحميل → تحليل → خريطة → (وكيل ذكي اختياري) → تقرير. كل حالة محفوظة في قاعدة البيانات وتُحدَّث عند إضافة تحليلات جديدة.",
    datasetTitle: "مصدر البيانات",
    datasetText:
      "التدريب والاختبار اعتمدا على صور رادارية Sentinel-1 مع أقنعة تميّز النفط عن المياه النظيفة.",
    tryCta: "جرّب النظام الآن",
  },
  en: {
    eyebrow: "How it works",
    workflowTitle: "From image to decision in simple steps",
    steps: [
      {
        title: "Upload satellite imagery",
        summary:
          "Upload from Sentinel, Landsat, or other supported sources (.tif, .png, .jpg). Coordinates are read from the file when available.",
      },
      {
        title: "Detect & analyze",
        summary:
          "DeepLab segments the spill, then the system computes area, coverage, distance to land and coral reefs, and a final risk level.",
      },
      {
        title: "View on the interactive map",
        summary:
          "Each case appears as a color-coded marker. Filter by sea, area, and distance to shore, and open details for any spill.",
      },
      {
        title: "Ask the AI agent",
        summary:
          "Query counts by region, compare two cases, or get explanations for a selected spill — grounded in your database and past reports.",
      },
      {
        title: "Generate assessment & response report",
        summary:
          "One HTML report with detection imagery, assessment, geospatial metrics, and a prioritized response plan — ready to view or download.",
      },
    ],
    inOne: "In short",
    inOneText:
      "Upload → analyze → map → (optional AI agent) → report. Every case is stored in the database and updates when you add new analyses.",
    datasetTitle: "Data source",
    datasetText:
      "Model training and validation used Sentinel-1 SAR imagery with masks separating oil from clean water.",
    tryCta: "Try the system",
  },
} as const;

export default function About() {
  const { lang, t, dir } = useLang();
  const c = COPY[lang];
  const Arrow = dir === "rtl" ? ArrowLeft : ArrowRight;

  return (
    <div className="px-4 lg:px-8 py-6 lg:py-10 space-y-12">
      {/* Hero */}
      <section className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-navy-900 via-navy-800 to-navy-900 p-8 md:p-12 text-white">
        <div className="absolute inset-0 bg-grid opacity-[0.08]" />
        <div className="absolute -top-24 -end-24 w-80 h-80 rounded-full bg-teal-500/20 blur-3xl" />
        <div className="absolute -bottom-24 -start-24 w-80 h-80 rounded-full bg-ocean-500/15 blur-3xl" />

        <div className="relative max-w-3xl">
          <div className="inline-flex items-center gap-2 rounded-full bg-white/10 backdrop-blur-sm border border-white/20 px-4 py-1.5 text-xs font-medium tracking-wider uppercase">
            <Globe2 className="w-3.5 h-3.5" />
            {lang === "ar" ? "عن المشروع" : "About the Project"}
          </div>
          <h1 className="mt-5 display-font text-3xl md:text-4xl font-semibold leading-tight tracking-tight">
            {t("aboutTitle")}
          </h1>
          <p className="mt-4 text-base md:text-lg text-white/80 leading-relaxed max-w-2xl">
            {t("aboutDesc")}
          </p>
        </div>
      </section>

      {/* Workflow summary */}
      <section>
        <div className="mb-8 max-w-2xl">
          <div className="text-[11px] uppercase tracking-[0.18em] text-teal-700 font-semibold mb-2">
            {c.eyebrow}
          </div>
          <h2 className="display-font text-2xl md:text-3xl font-semibold text-navy-500 tracking-tight">
            {c.workflowTitle}
          </h2>
        </div>

        <div className="space-y-4">
          {WORKFLOW.map((step, i) => {
            const Icon = step.icon;
            const copy = c.steps[i];
            return (
              <div key={i} className="relative">
                <Card className="overflow-hidden border-ocean-100 hover:shadow-lg transition-shadow">
                  <CardContent className="p-0">
                    <div className="flex flex-col sm:flex-row">
                      <div
                        className={cn(
                          "flex sm:flex-col items-center justify-center gap-3 sm:w-28 p-5 bg-gradient-to-br text-white shrink-0",
                          step.color
                        )}
                      >
                        <span className="display-font text-3xl font-bold opacity-40">
                          {String(i + 1).padStart(2, "0")}
                        </span>
                        <Icon className="w-8 h-8" strokeWidth={1.5} />
                      </div>
                      <div className="flex-1 p-5 sm:p-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                        <div>
                          <h3 className="font-semibold text-navy-500 text-lg mb-2">
                            {copy.title}
                          </h3>
                          <p className="text-sm text-muted-foreground leading-relaxed max-w-xl">
                            {copy.summary}
                          </p>
                        </div>
                        <Button asChild variant="outline" size="sm" className="shrink-0">
                          <Link to={step.link}>
                            {lang === "ar" ? step.ctaAr : step.ctaEn}
                            <Arrow className="w-4 h-4" />
                          </Link>
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {i < WORKFLOW.length - 1 && (
                  <div className="flex justify-center py-1 sm:hidden">
                    <div className="w-0.5 h-4 bg-teal-200 rounded-full" />
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* In short */}
        <Card className="mt-8 border-teal-100 bg-gradient-to-br from-teal-50/80 to-white">
          <CardContent className="p-6 md:p-8 flex flex-col md:flex-row gap-4 md:items-center">
            <div className="w-12 h-12 rounded-2xl bg-teal-100 flex items-center justify-center shrink-0">
              <Sparkles className="w-6 h-6 text-teal-700" />
            </div>
            <div className="flex-1">
              <div className="text-xs font-semibold uppercase tracking-wider text-teal-800 mb-1">
                {c.inOne}
              </div>
              <p className="text-sm md:text-base text-navy-600 leading-relaxed font-medium">
                {c.inOneText}
              </p>
            </div>
            <Button asChild variant="teal" className="shrink-0">
              <Link to="/analyze">
                <Upload className="w-4 h-4" />
                {c.tryCta}
              </Link>
            </Button>
          </CardContent>
        </Card>
      </section>

      {/* Dataset note — brief */}
      <section>
        <Card className="border-ocean-100">
          <CardContent className="p-6">
            <h3 className="font-semibold text-navy-500 mb-2">{c.datasetTitle}</h3>
            <p className="text-sm text-muted-foreground leading-relaxed">{c.datasetText}</p>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
