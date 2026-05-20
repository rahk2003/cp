import { useMemo, useState, useEffect } from "react";
import { Link } from "react-router-dom";
import {
  Eye,
  Download,
  Bot,
  FileText,
  Search,
  Filter,
  Languages,
  Calendar,
  X,
  ChevronRight,
  Sparkles,
  Loader2,
  Trash2,
} from "lucide-react";
import { useLang } from "@/hooks/useLang";
import { useSpills, useReports } from "@/hooks/useApi";
import {
  deleteReport,
  generateReport,
  reportAssetUrl,
  reportHtmlUrl,
} from "@/lib/api";
import type { ReportRecord, ReportSolutionPayload, SpillRecord } from "@/types";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { RiskPill } from "@/components/ui/Badge";
import { riskLabel } from "@/lib/riskLevels";
import { cn, formatDate, formatArea } from "@/lib/utils";
import { chatbotPath, reportSpillKey } from "@/lib/chatContext";

export default function ReportsPage() {
  const { t, lang } = useLang();
  const { reports, loading, error, refresh } = useReports();
  const { spills } = useSpills();
  const [search, setSearch] = useState("");
  const [filterLang, setFilterLang] = useState<"all" | "EN" | "AR">("all");
  const [selected, setSelected] = useState<ReportRecord | null>(null);
  const [generating, setGenerating] = useState(false);
  const [genSpillId, setGenSpillId] = useState<string>("");
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // Auto-select first report once data arrives
  useEffect(() => {
    if (!selected && reports.length > 0) {
      setSelected(reports[0]);
    }
  }, [reports, selected]);

  // Default the generator's selected spill to the first available
  useEffect(() => {
    if (!genSpillId && spills.length > 0) {
      setGenSpillId(spills[0].id);
    }
  }, [spills, genSpillId]);

  const filtered = useMemo(() => {
    return reports.filter((r) => {
      if (filterLang !== "all" && r.language !== filterLang) return false;
      if (
        search &&
        !r.filename.toLowerCase().includes(search.toLowerCase()) &&
        !r.id.toLowerCase().includes(search.toLowerCase())
      )
        return false;
      return true;
    });
  }, [reports, search, filterLang]);

  const selectedSpill = selected
    ? spills.find(
        (s) =>
          s.id === selected.spill_id ||
          s.filename === selected.spill_id ||
          s.filename === selected.filename
      )
    : undefined;

  const onGenerate = async () => {
    if (!genSpillId) return;
    setGenerating(true);
    try {
      const r = await generateReport(genSpillId, lang);
      await refresh();
      setSelected(r);
      const src = (r as ReportRecord & { source?: string; warning?: string }).source;
      const warn = (r as ReportRecord & { warning?: string }).warning;
      if (src === "template" && warn) {
        alert(warn);
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      console.error("[generate-report] failed:", msg);
      alert(
        (lang === "ar"
          ? "تعذّر توليد تقرير Qwen. تأكدي من LLM_PYTHON في .env (نفس بايثون run_local_oil_llm.py): "
          : "Qwen report failed. Set LLM_PYTHON in .env to the Python used for run_local_oil_llm.py: ") +
          msg
      );
    } finally {
      setGenerating(false);
    }
  };

  const onDelete = async (r: ReportRecord, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm(t("deleteReportConfirm"))) return;
    setDeletingId(r.id);
    try {
      await deleteReport(r.id);
      if (selected?.id === r.id) {
        const remaining = reports.filter((x) => x.id !== r.id);
        setSelected(remaining[0] ?? null);
      }
      await refresh();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      alert(
        (lang === "ar" ? "تعذّر حذف التقرير: " : "Could not delete report: ") + msg
      );
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="px-4 lg:px-8 py-6">
      {/* Header */}
      <div className="mb-6 flex items-end justify-between flex-wrap gap-3">
        <div>
          <h1 className="display-font text-xl lg:text-2xl font-semibold text-navy-500 tracking-tight">
            {t("reportsTitle")}
          </h1>
          <p className="text-muted-foreground text-xs mt-1 max-w-2xl">
            {t("reportsDesc")}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-teal-50 border border-teal-200">
            <FileText className="w-3.5 h-3.5 text-teal-700" />
            <span className="text-xs font-semibold text-teal-700">
              {loading
                ? lang === "ar"
                  ? "جاري التحميل..."
                  : "Loading..."
                : `${reports.length} ${lang === "ar" ? "تقارير" : "reports"}`}
            </span>
          </div>
        </div>
      </div>

      {/* Generate report bar */}
      <Card className="mb-5 p-3 flex items-center gap-2 flex-wrap">
        <div className="flex items-center gap-2 text-xs font-semibold text-navy-500 me-1">
          <Sparkles className="w-3.5 h-3.5 text-teal-600" />
          {t("generateNewReport")}
        </div>
        <select
          value={genSpillId}
          onChange={(e) => setGenSpillId(e.target.value)}
          className="h-9 px-2 rounded-lg border border-ocean-100 bg-ocean-50/40 text-xs text-navy-500 focus:outline-none focus:ring-2 focus:ring-teal-400/40 focus:border-teal-300 flex-1 min-w-[200px]"
        >
          {spills.length === 0 && (
            <option value="">
              {lang === "ar" ? "لا توجد تسرّبات" : "No spills available"}
            </option>
          )}
          {spills.slice(0, 200).map((s) => (
            <option key={s.id} value={s.id}>
              {s.id.slice(0, 30)} · {s.final_risk_level}
            </option>
          ))}
        </select>
        <Button
          size="sm"
          variant="teal"
          onClick={onGenerate}
          disabled={generating || !genSpillId}
        >
          {generating ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              {t("generatingSpillReport")}
            </>
          ) : (
            <>
              <FileText className="w-4 h-4" />
              {t("reportGenerateShort")}
            </>
          )}
        </Button>
      </Card>

      {error && (
        <Card className="mb-5 p-3 border-red-200 bg-red-50/40">
          <div className="text-xs text-red-700">
            {lang === "ar"
              ? `تعذّر تحميل التقارير: ${error}`
              : `Could not load reports: ${error}`}
          </div>
        </Card>
      )}

      <div className="grid lg:grid-cols-[1fr_440px] gap-5">
        {/* TABLE */}
        <div className="bg-white rounded-2xl border border-ocean-100 overflow-hidden">
          {/* Filters bar */}
          <div className="px-4 py-3 border-b border-ocean-100 flex items-center gap-2 flex-wrap">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute start-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={lang === "ar" ? "ابحث في التقارير..." : "Search reports..."}
                className="w-full h-9 ps-9 pe-3 rounded-lg bg-ocean-50/70 border border-ocean-100 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400/40 focus:border-teal-300 transition"
              />
            </div>

            <div className="flex items-center gap-1 p-0.5 rounded-lg bg-ocean-50/70 border border-ocean-100">
              {(["all", "EN", "AR"] as const).map((l) => (
                <button
                  key={l}
                  onClick={() => setFilterLang(l)}
                  className={cn(
                    "px-3 h-8 rounded-md text-xs font-medium transition",
                    filterLang === l
                      ? "bg-white text-navy-500 shadow-sm"
                      : "text-muted-foreground hover:text-navy-500"
                  )}
                >
                  {l === "all" ? (lang === "ar" ? "الكل" : "All") : l}
                </button>
              ))}
            </div>

            <Button variant="outline" size="sm">
              <Filter className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">
                {lang === "ar" ? "مرشحات" : "Filters"}
              </span>
            </Button>
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-ocean-50/40">
                <tr className="text-[10px] uppercase tracking-wider text-muted-foreground">
                  <th className="text-start px-4 py-3 font-semibold">
                    {t("reportId")}
                  </th>
                  <th className="text-start px-4 py-3 font-semibold">
                    {t("filename")}
                  </th>
                  <th className="text-start px-4 py-3 font-semibold">
                    {t("risk")}
                  </th>
                  <th className="text-start px-4 py-3 font-semibold">
                    {t("language")}
                  </th>
                  <th className="text-start px-4 py-3 font-semibold whitespace-nowrap">
                    {t("generated")}
                  </th>
                  <th className="text-end px-4 py-3 font-semibold">
                    {t("actions")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((r) => {
                  const isSelected = selected?.id === r.id;
                  return (
                    <tr
                      key={r.id}
                      onClick={() => setSelected(r)}
                      className={cn(
                        "border-t border-ocean-100 hover:bg-ocean-50/40 cursor-pointer transition group",
                        isSelected && "bg-teal-50/50"
                      )}
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          {isSelected && (
                            <span className="w-1 h-6 rounded-full bg-teal-500" />
                          )}
                          <span className="text-xs font-mono font-semibold text-navy-500">
                            {r.id}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3 max-w-[280px]">
                        <div className="text-xs font-mono text-navy-400 truncate">
                          {r.filename}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <RiskPill level={r.risk_level} size="sm" />
                      </td>
                      <td className="px-4 py-3">
                        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-ocean-50 border border-ocean-100 text-[10px] font-mono uppercase font-semibold text-navy-500">
                          <Languages className="w-3 h-3" />
                          {r.language}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-muted-foreground whitespace-nowrap">
                        {formatDate(r.generated_at, lang)}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-1">
                          <ActionButton
                            icon={Eye}
                            label={t("view")}
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelected(r);
                            }}
                          />
                          <a
                            href={reportHtmlUrl(r.id)}
                            target="_blank"
                            rel="noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            title={t("download")}
                            className="w-8 h-8 rounded-lg hover:bg-ocean-50 hover:text-navy-500 text-muted-foreground inline-flex items-center justify-center transition"
                          >
                            <Download className="w-4 h-4" />
                          </a>
                          <Link
                            to={chatbotPath({
                              spillId: reportSpillKey(r),
                              reportId: r.id,
                            })}
                            onClick={(e) => e.stopPropagation()}
                            className="w-8 h-8 rounded-lg hover:bg-teal-50 hover:text-teal-700 text-muted-foreground inline-flex items-center justify-center transition"
                            title={t("askChat")}
                          >
                            <Bot className="w-4 h-4" />
                          </Link>
                          <button
                            type="button"
                            onClick={(e) => onDelete(r, e)}
                            disabled={deletingId === r.id}
                            title={t("deleteReport")}
                            className={cn(
                              "w-8 h-8 rounded-lg inline-flex items-center justify-center transition",
                              deletingId === r.id
                                ? "opacity-50 cursor-wait"
                                : "hover:bg-red-50 hover:text-red-600 text-muted-foreground"
                            )}
                          >
                            {deletingId === r.id ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <Trash2 className="w-4 h-4" />
                            )}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {filtered.length === 0 && !loading && (
              <div className="p-12 text-center">
                <FileText className="w-10 h-10 text-ocean-200 mx-auto mb-3" />
                <p className="text-sm text-muted-foreground">
                  {reports.length === 0
                    ? lang === "ar"
                      ? "لا توجد تقارير بعد. ولّد تقريراً جديداً من الأعلى."
                      : "No reports yet. Generate one above."
                    : lang === "ar"
                    ? "لا توجد تقارير مطابقة"
                    : "No matching reports"}
                </p>
              </div>
            )}
            {loading && filtered.length === 0 && (
              <div className="p-12 text-center text-muted-foreground text-sm">
                <Loader2 className="w-6 h-6 animate-spin mx-auto mb-3 text-teal-500" />
                {lang === "ar" ? "جاري التحميل..." : "Loading reports..."}
              </div>
            )}
          </div>
        </div>

        {/* PREVIEW PANEL */}
        <div className="lg:sticky lg:top-20 lg:self-start">
          {selected ? (
            <ReportPreview report={selected} spill={selectedSpill} />
          ) : (
            <Card className="p-10 text-center text-sm text-muted-foreground">
              <FileText className="w-10 h-10 mx-auto mb-3 text-ocean-200" />
              {lang === "ar"
                ? "اختر تقريراً لعرض معاينته"
                : "Select a report to preview"}
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

function ActionButton({
  icon: Icon,
  label,
  onClick,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  onClick?: (e: React.MouseEvent) => void;
}) {
  return (
    <button
      onClick={onClick}
      title={label}
      className="w-8 h-8 rounded-lg hover:bg-ocean-50 hover:text-navy-500 text-muted-foreground inline-flex items-center justify-center transition"
    >
      <Icon className="w-4 h-4" />
    </button>
  );
}

function ReportPreview({
  report,
  spill,
}: {
  report: ReportRecord;
  spill?: SpillRecord;
}) {
  const { t, lang } = useLang();
  const isAr = report.language === "AR";
  const payload = report.payload as ReportSolutionPayload | undefined;
  const previewImage = report.image_assets?.primary
    ? reportAssetUrl(report.image_assets.primary)
    : report.image_asset
      ? reportAssetUrl(report.image_asset)
      : null;

  return (
    <Card className="overflow-hidden">
      {/* Header */}
      <div className="relative bg-gradient-to-br from-navy-500 to-navy-700 px-5 py-5 text-white overflow-hidden">
        <div className="absolute -right-10 -top-10 w-40 h-40 bg-teal-400/20 rounded-full blur-3xl" />
        <div className="absolute -left-10 -bottom-10 w-32 h-32 bg-ocean-400/20 rounded-full blur-3xl" />
        <div className="relative">
          <div className="flex items-start justify-between mb-3">
            <div>
              <div className="text-[10px] font-mono uppercase tracking-[0.18em] text-teal-200 mb-1">
                Report · {report.id}
              </div>
              <div className="display-font text-xl font-semibold leading-tight">
                {t("spillIntelligenceReport")}
              </div>
            </div>
            <span className="px-2 py-0.5 rounded-full bg-white/20 border border-white/30 text-[10px] font-mono font-semibold backdrop-blur">
              {report.language}
            </span>
          </div>
          <div className="flex items-center gap-2 text-[11px] text-ocean-200">
            <Calendar className="w-3 h-3" />
            <span>{formatDate(report.generated_at, lang)}</span>
            <span className="mx-1 opacity-50">·</span>
            <span className="font-mono truncate">{report.filename}</span>
          </div>
        </div>
      </div>

      <div
        className={cn("p-5 space-y-5", isAr && "font-arabic")}
        dir={isAr ? "rtl" : "ltr"}
      >
        {previewImage && (
          <div className="rounded-xl overflow-hidden border border-ocean-100 bg-ocean-50/40">
            <img
              src={previewImage}
              alt={report.filename}
              className="w-full max-h-56 object-contain bg-navy-950/5"
            />
            <div className="px-3 py-1.5 text-[10px] text-muted-foreground text-center">
              {isAr ? "صورة الكشف والتسرب" : "Spill detection imagery"}
            </div>
          </div>
        )}

        {/* Risk badge */}
        <div className="flex items-center justify-between">
          <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground font-semibold">
            {isAr ? "مستوى الخطورة" : "Risk level"}
          </div>
          <RiskPill level={report.risk_level} />
        </div>

        {/* Summary */}
        <ReportSection title={isAr ? "الملخّص" : "Summary"}>
          <p className="text-sm text-navy-500 leading-relaxed whitespace-pre-wrap">
            {report.content || report.summary}
          </p>
        </ReportSection>

        {/* Spatial */}
        {spill && (
          <ReportSection title={t("spatial")}>
            <div className="grid grid-cols-2 gap-2">
              <PreviewStat
                label={isAr ? "المساحة" : "Area"}
                value={formatArea(spill.area_m2)}
              />
              <PreviewStat
                label={isAr ? "التغطية" : "Coverage"}
                value={`${Number(spill.coverage_pct).toFixed(1)}%`}
              />
              <PreviewStat
                label={isAr ? "المسافة من اليابسة" : "Distance to land"}
                value={`${Number(spill.distance_to_land_km).toFixed(1)} km`}
              />
              <PreviewStat
                label={isAr ? "المسافة من الشعاب المرجانية" : "Distance to coral reefs"}
                value={`${Number(spill.distance_to_coral_km).toFixed(1)} km`}
              />
            </div>
          </ReportSection>
        )}

        {/* Assessment */}
        <ReportSection title={isAr ? "تقييم المخاطر" : "Risk Assessment"}>
          <p className="text-sm text-navy-500 leading-relaxed">
            {isAr
              ? `استناداً إلى موقع التسرّب وقربه من العناصر الحساسة، يصنّف التحليل التلقائي هذا التسرّب على أنه ${riskLabel(report.risk_level, "ar")}. يوصى بمتابعة الانجراف ومراقبته كل ساعة.`
              : `Based on the spill's location and proximity to sensitive features, the automated analysis classifies it as ${report.risk_level}. Hourly drift monitoring is recommended until containment.`}
          </p>
        </ReportSection>

        {payload?.operational_decision && (
          <ReportSection title={isAr ? "القرار التشغيلي" : "Operational decision"}>
            <p className="text-sm font-semibold text-navy-600">{payload.operational_decision}</p>
            {payload.decision_badge && (
              <span className="inline-block mt-2 px-2 py-0.5 rounded-full bg-cyan-50 text-cyan-800 text-[10px] font-semibold">
                {payload.decision_badge}
              </span>
            )}
          </ReportSection>
        )}

        {payload?.immediate && payload.immediate.length > 0 && (
          <PayloadListSection
            title={isAr ? "إجراءات فورية" : "Immediate actions"}
            items={payload.immediate}
          />
        )}
        {payload?.short_term && payload.short_term.length > 0 && (
          <PayloadListSection
            title={isAr ? "إجراءات قصيرة المدى" : "Short-term actions"}
            items={payload.short_term}
          />
        )}
        {payload?.long_term && payload.long_term.length > 0 && (
          <PayloadListSection
            title={isAr ? "إجراءات طويلة المدى" : "Long-term actions"}
            items={payload.long_term}
          />
        )}
        {payload?.equipment && payload.equipment.length > 0 && (
          <PayloadListSection
            title={isAr ? "المعدات" : "Equipment"}
            items={payload.equipment}
          />
        )}
        {payload?.agencies && payload.agencies.length > 0 && (
          <PayloadListSection
            title={isAr ? "الجهات المعنية" : "Agencies"}
            items={payload.agencies}
          />
        )}
        {payload?.monitoring && payload.monitoring.length > 0 && (
          <PayloadListSection
            title={isAr ? "المراقبة" : "Monitoring"}
            items={payload.monitoring}
          />
        )}

        <div className="flex gap-2 pt-2">
          <Button asChild className="flex-1" size="sm">
            <a href={reportHtmlUrl(report.id)} target="_blank" rel="noreferrer">
              <Download className="w-4 h-4" />
              {isAr ? "تنزيل HTML" : "Download HTML"}
            </a>
          </Button>
          <Button asChild variant="teal" className="flex-1" size="sm">
            <Link
              to={chatbotPath({
                spillId: reportSpillKey(report),
                reportId: report.id,
              })}
            >
              <Bot className="w-4 h-4" />
              {isAr ? "اسأل الوكيل الذكي" : "Ask AI"}
            </Link>
          </Button>
        </div>
      </div>
    </Card>
  );
}

function PayloadListSection({ title, items }: { title: string; items: string[] }) {
  return (
    <ReportSection title={title}>
      <ul className="space-y-1.5">
        {items.map((item, i) => (
          <li key={i} className="flex items-start gap-2 text-sm text-navy-500">
            <span className="w-4 h-4 rounded-full bg-teal-50 text-teal-600 inline-flex items-center justify-center text-[9px] font-bold mt-0.5 shrink-0">
              {i + 1}
            </span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </ReportSection>
  );
}

function ReportSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="flex items-center gap-1.5 mb-2">
        <ChevronRight className="w-3 h-3 text-teal-600" />
        <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground font-semibold">
          {title}
        </div>
      </div>
      <div className="ps-4 border-s-2 border-ocean-100">{children}</div>
    </div>
  );
}

function PreviewStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-ocean-50/60 px-2.5 py-2">
      <div className="text-[9px] uppercase tracking-wider text-muted-foreground mb-0.5">
        {label}
      </div>
      <div className="text-xs font-semibold text-navy-500 font-mono">
        {value}
      </div>
    </div>
  );
}
