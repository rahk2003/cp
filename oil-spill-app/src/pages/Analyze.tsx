import { useCallback, useRef, useState } from "react";
import {
  Upload,
  FileImage,
  X,
  Play,
  Save,
  FileText,
  Send,
  CheckCircle2,
  Loader2,
  Sparkles,
  MapPin,
  TrendingUp,
  Waves,
  Activity,
  AlertCircle,
} from "lucide-react";
import { Link } from "react-router-dom";
import { useLang } from "@/hooks/useLang";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { RiskPill } from "@/components/ui/Badge";
import { cn, formatArea, formatCoordinates } from "@/lib/utils";
import {
  analyzeImage,
  generateReport,
  saveAnalyzedSpill,
  type AnalyzeResult,
} from "@/lib/api";
import {
  chatbotPath,
  spillContextKey,
  stashPendingSpillForChat,
} from "@/lib/chatContext";

type Status = "idle" | "uploaded" | "analyzing" | "done";

function formatFileSize(bytes: number, lang: "ar" | "en"): string {
  if (bytes < 1024) {
    return lang === "ar" ? `${bytes} بايت` : `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    const kb = (bytes / 1024).toFixed(1);
    return lang === "ar" ? `${kb} ك.ب` : `${kb} KB`;
  }
  const mb = (bytes / (1024 * 1024)).toFixed(1);
  return lang === "ar" ? `${mb} م.ب` : `${mb} MB`;
}

function fileTypeLabel(name: string, lang: "ar" | "en"): string {
  const ext = (name.split(".").pop() || "").toLowerCase();
  if (ext === "tif" || ext === "tiff") {
    return lang === "ar" ? "GeoTIFF" : "GeoTIFF";
  }
  if (ext === "png") return "PNG";
  if (ext === "jpg" || ext === "jpeg") return "JPEG";
  return ext ? ext.toUpperCase() : lang === "ar" ? "صورة" : "Image";
}

function uploadedFileSubtitle(
  file: File | null,
  filename: string | null,
  lang: "ar" | "en"
): string {
  const name = file?.name || filename || "";
  if (!name) return "";
  const type = fileTypeLabel(name, lang);
  if (file?.size) {
    return `${type} · ${formatFileSize(file.size, lang)}`;
  }
  return type;
}

export default function AnalyzePage() {
  const { t, lang } = useLang();
  const inputRef = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [filename, setFilename] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [progress, setProgress] = useState(0);
  const [savedToast, setSavedToast] = useState<string | null>(null);
  const [analyzeResult, setAnalyzeResult] = useState<AnalyzeResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [generatingReport, setGeneratingReport] = useState(false);
  const [savingDb, setSavingDb] = useState(false);

  const onFile = useCallback((f: File) => {
    setFile(f);
    setFilename(f.name);
    setStatus("uploaded");
    setAnalyzeResult(null);
    setErrorMsg(null);
  }, []);

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files[0]) onFile(e.dataTransfer.files[0]);
  };

  const runAnalysis = async () => {
    if (!file) {
      // "Use sample" path — no real file, simulate (backend has no demo file).
      setStatus("analyzing");
      setProgress(0);
      const interval = setInterval(() => {
        setProgress((p) => {
          if (p >= 100) {
            clearInterval(interval);
            setStatus("done");
            // Synthetic demo metrics matching backend shape
            setAnalyzeResult({
              id: `DEMO-${Date.now()}`,
              filename: filename || "sample.tif",
              latitude: 26.4521,
              longitude: 50.1023,
              area_m2: 184500,
              coverage_pct: 12.4,
              distance_to_land_km: 3.2,
              distance_to_coral_km: 8.7,
              final_risk_level: "Critical",
              processed_at: new Date().toISOString(),
            });
            return 100;
          }
          return p + 3;
        });
      }, 60);
      return;
    }

    setStatus("analyzing");
    setProgress(0);
    setErrorMsg(null);

    // Animate progress while waiting for the backend
    const interval = setInterval(() => {
      setProgress((p) => (p >= 92 ? 92 : p + 4));
    }, 80);

    try {
      const result = await analyzeImage(file);
      clearInterval(interval);
      setProgress(100);
      setAnalyzeResult(result);
      setStatus("done");
      if (result.db_saved) {
        showToast(
          lang === "ar"
            ? result.db_action === "updated"
              ? "تم التحليل وتحديث الحالة في قاعدة البيانات تلقائياً"
              : "تم التحليل وحفظ الحالة في قاعدة البيانات تلقائياً"
            : result.db_action === "updated"
              ? "Analysis complete — spill updated in the database"
              : "Analysis complete — spill saved to the database"
        );
      }
    } catch (e: unknown) {
      clearInterval(interval);
      setProgress(0);
      setStatus("uploaded");
      const msg = e instanceof Error ? e.message : String(e);
      setErrorMsg(msg);
      console.error("[analyze] failed:", msg);
    }
  };

  const reset = () => {
    setStatus("idle");
    setFilename(null);
    setFile(null);
    setProgress(0);
    setAnalyzeResult(null);
    setErrorMsg(null);
  };

  const showToast = (msg: string) => {
    setSavedToast(msg);
    setTimeout(() => setSavedToast(null), 3000);
  };

  const onGenerateSpillReport = async () => {
    if (!analyzeResult) return;
    const spillId =
      analyzeResult.filename || (analyzeResult as { id?: string }).id;
    if (!spillId) {
      setErrorMsg(
        lang === "ar"
          ? "لا يوجد معرّف للحالة لتوليد التقرير."
          : "No spill ID available to generate a report."
      );
      return;
    }
    setGeneratingReport(true);
    setErrorMsg(null);
    try {
      await generateReport(spillId, lang);
      showToast(
        lang === "ar"
          ? "تم إصدار التقرير. يمكنك فتحه من صفحة التقارير."
          : "Report generated. You can open it from Reports."
      );
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setErrorMsg(
        (lang === "ar"
          ? "تعذّر إصدار تقرير التقييم والاستجابة: "
          : "Could not generate assessment report: ") + msg
      );
    } finally {
      setGeneratingReport(false);
    }
  };

  const onSaveToDatabase = async () => {
    if (!analyzeResult) return;
    if (
      Math.abs(analyzeResult.latitude ?? 0) < 1e-9 &&
      Math.abs(analyzeResult.longitude ?? 0) < 1e-9
    ) {
      setErrorMsg(
        lang === "ar"
          ? "هذه الصورة لا تحتوي حالياً على إحداثيات صالحة، لذلك لا يمكن إنشاء نقطة لها على الخريطة عند الحفظ."
          : "This image does not currently have valid coordinates, so it cannot create a map point when saved."
      );
      return;
    }
    setSavingDb(true);
    setErrorMsg(null);
    try {
      const res = await saveAnalyzedSpill(analyzeResult);
      showToast(
        lang === "ar"
          ? res.action === "updated"
            ? "تم تحديث الحالة في قاعدة البيانات بدون تكرار نقطة جديدة"
            : "تم حفظ الحالة في قاعدة البيانات وإظهارها على الخريطة"
          : res.action === "updated"
            ? "Spill updated in database without duplicating the map point"
            : "Spill saved to database and added to the map"
      );
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setErrorMsg(
        (lang === "ar"
          ? "تعذّر الحفظ في قاعدة البيانات: "
          : "Could not save to database: ") + msg
      );
    } finally {
      setSavingDb(false);
    }
  };

  // metrics derived from backend response (or fallback while loading)
  const metrics = {
    area: analyzeResult?.area_m2 ?? 0,
    coverage: analyzeResult?.coverage_pct ?? 0,
    centroid: [
      analyzeResult?.latitude ?? 0,
      analyzeResult?.longitude ?? 0,
    ] as [number, number],
    distLand: analyzeResult?.distance_to_land_km ?? 0,
    distCoral: analyzeResult?.distance_to_coral_km ?? 0,
    risk: analyzeResult?.final_risk_level ?? "Medium",
  };

  return (
    <div className="px-4 lg:px-8 py-6">
      <div className="mb-6 flex items-end justify-between flex-wrap gap-3">
        <div>
          <h1 className="display-font text-3xl lg:text-4xl font-semibold text-navy-500 tracking-tight">
            {t("analyzeTitle")}
          </h1>
          {t("analyzeDesc") ? (
            <p className="text-muted-foreground text-sm mt-1.5 max-w-2xl">
              {t("analyzeDesc")}
            </p>
          ) : null}
        </div>
        {status !== "idle" && (
          <Button variant="ghost" size="sm" onClick={reset}>
            <X className="w-4 h-4" />
            {lang === "ar" ? "إعادة" : "Reset"}
          </Button>
        )}
      </div>

      {/* Stepper */}
      <div className="mb-6 flex items-center gap-2 text-[11px] font-medium overflow-x-auto no-scrollbar">
        {[
          { label: lang === "ar" ? "رفع" : "Upload", done: status !== "idle" },
          {
            label: lang === "ar" ? "تحليل" : "Analyze",
            done: status === "done",
          },
          { label: lang === "ar" ? "نتائج" : "Results", done: status === "done" },
          {
            label: lang === "ar" ? "إجراءات" : "Actions",
            done: status === "done",
          },
        ].map((s, i, arr) => (
          <div key={s.label} className="flex items-center gap-2 shrink-0">
            <div
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-full transition",
                s.done
                  ? "bg-teal-50 text-teal-700 border border-teal-200"
                  : "bg-white text-muted-foreground border border-ocean-100"
              )}
            >
              <span
                className={cn(
                  "w-4 h-4 rounded-full inline-flex items-center justify-center text-[9px] font-bold",
                  s.done ? "bg-teal-500 text-white" : "bg-ocean-100 text-muted-foreground"
                )}
              >
                {s.done ? <CheckCircle2 className="w-3 h-3" /> : i + 1}
              </span>
              {s.label}
            </div>
            {i < arr.length - 1 && (
              <div className="w-6 h-px bg-ocean-200" />
            )}
          </div>
        ))}
      </div>

      <div className="grid lg:grid-cols-3 gap-5">
        {/* LEFT: Upload + previews */}
        <div className="lg:col-span-2 space-y-5">
          {/* Upload zone */}
          {status === "idle" && (
            <Card
              className={cn(
                "border-2 border-dashed transition-all relative overflow-hidden",
                dragOver
                  ? "border-teal-400 bg-teal-50/40"
                  : "border-ocean-200 hover:border-teal-300 hover:bg-ocean-50/40"
              )}
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={onDrop}
            >
              <div className="absolute inset-0 bg-grid-dense opacity-40 pointer-events-none" />
              <div className="relative p-12 flex flex-col items-center text-center">
                <div className="relative w-20 h-20 mb-5">
                  <div className="absolute inset-0 bg-teal-400/20 rounded-3xl blur-2xl" />
                  <div className="relative w-full h-full rounded-3xl bg-gradient-to-br from-navy-500 to-teal-600 flex items-center justify-center">
                    <Upload className="w-8 h-8 text-white" strokeWidth={2} />
                  </div>
                </div>
                <h3 className="display-font text-2xl font-semibold text-navy-500 mb-1">
                  {t("dragDrop")}
                </h3>
                <p className="text-muted-foreground text-sm mb-5">
                  {t("accepted")}
                </p>
                <input
                  ref={inputRef}
                  type="file"
                  accept=".tif,.tiff,.png,.jpg,.jpeg"
                  className="hidden"
                  onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])}
                />
                <div className="flex items-center gap-3">
                  <Button onClick={() => inputRef.current?.click()}>
                    <FileImage className="w-4 h-4" />
                    {t("browse")}
                  </Button>
                  <span className="text-muted-foreground text-sm">
                    {t("or")}
                  </span>
                  <Button
                    variant="outline"
                    onClick={() => {
                      setFile(null);
                      setFilename("sentinel2_demo_sample.tif");
                      setStatus("uploaded");
                      setAnalyzeResult(null);
                      setErrorMsg(null);
                    }}
                  >
                    <Sparkles className="w-4 h-4" />
                    {lang === "ar" ? "استخدم عيّنة" : "Use sample"}
                  </Button>
                </div>

              </div>
            </Card>
          )}

          {/* After upload */}
          {status !== "idle" && (
            <>
              {/* File card */}
              <Card className="p-4 flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-teal-50 flex items-center justify-center shrink-0">
                  <FileImage className="w-5 h-5 text-teal-600" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-semibold text-navy-500 truncate">
                    {filename}
                  </div>
                  <div className="text-[11px] text-muted-foreground font-mono">
                    {uploadedFileSubtitle(file, filename, lang)}
                  </div>
                </div>
                {status === "analyzing" && (
                  <div className="flex items-center gap-2 text-xs text-teal-700">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span className="font-medium">
                      {progress}%
                    </span>
                  </div>
                )}
                {status === "done" && (
                  <div className="flex items-center gap-1.5 text-xs text-emerald-700 font-medium">
                    <CheckCircle2 className="w-4 h-4" />
                    {t("analysisDone")}
                  </div>
                )}
              </Card>

              {errorMsg && (
                <Card className="p-4 border-red-200 bg-red-50/50">
                  <div className="flex items-start gap-3">
                    <AlertCircle className="w-5 h-5 text-red-500 shrink-0 mt-0.5" />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-semibold text-red-900">
                        {lang === "ar" ? "تعذّر التحليل" : "Analysis failed"}
                      </div>
                      <div className="text-xs text-red-700 mt-0.5 font-mono break-words">
                        {errorMsg}
                      </div>
                      <div className="text-[11px] text-red-600 mt-1.5">
                        {lang === "ar"
                          ? "تأكد من تشغيل الباك اند على المنفذ 8000."
                          : "Make sure the backend is running on port 8000."}
                      </div>
                    </div>
                    <button
                      onClick={() => setErrorMsg(null)}
                      className="text-red-400 hover:text-red-600"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                </Card>
              )}

              {/* Analyzing progress */}
              {status === "analyzing" && (
                <Card className="p-5">
                  <div className="flex items-center justify-between mb-3">
                    <div className="text-sm font-medium text-navy-500">
                      {t("analyzing")}
                    </div>
                    <div className="text-xs font-mono text-teal-700">
                      DeepLab v3+ · {progress}%
                    </div>
                  </div>
                  <div className="h-2 bg-ocean-100 rounded-full overflow-hidden mb-3">
                    <div
                      className="h-full bg-gradient-to-r from-teal-400 to-teal-600 transition-all rounded-full shimmer-bg"
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[10px]">
                    {[
                      { label: lang === "ar" ? "معالجة" : "Preprocess", done: progress > 25 },
                      { label: lang === "ar" ? "نموذج" : "Inference", done: progress > 55 },
                      { label: lang === "ar" ? "خصائص" : "Features", done: progress > 80 },
                      { label: lang === "ar" ? "تحليل" : "Risk score", done: progress >= 100 },
                    ].map((step) => (
                      <div
                        key={step.label}
                        className={cn(
                          "flex items-center gap-1.5 px-2 py-1.5 rounded-md",
                          step.done
                            ? "bg-teal-50 text-teal-700"
                            : "bg-ocean-50 text-muted-foreground"
                        )}
                      >
                        <span
                          className={cn(
                            "w-1.5 h-1.5 rounded-full",
                            step.done ? "bg-teal-500" : "bg-ocean-300 animate-pulse"
                          )}
                        />
                        <span className="font-medium">{step.label}</span>
                      </div>
                    ))}
                  </div>
                </Card>
              )}

              {/* Preview grid */}
              {status === "done" && (
                <div className="grid sm:grid-cols-3 gap-4 animate-fade-in">
                  <PreviewTile
                    label={t("original")}
                    variant="original"
                    imageUrl={analyzeResult?.original_preview_url}
                    cacheKey={analyzeResult?.processed_at}
                  />
                  <PreviewTile
                    label={t("mask")}
                    variant="mask"
                    imageUrl={analyzeResult?.mask_preview_url}
                    cacheKey={analyzeResult?.processed_at}
                  />
                  <PreviewTile
                    label={t("overlay")}
                    variant="overlay"
                    imageUrl={analyzeResult?.overlay_preview_url}
                    cacheKey={analyzeResult?.processed_at}
                  />
                </div>
              )}

              {status === "uploaded" && (
                <Card className="p-8 text-center bg-ocean-50/40 border-dashed">
                  <Play className="w-10 h-10 text-teal-600 mx-auto mb-3" />
                  <p className="text-sm text-muted-foreground mb-4">
                    {lang === "ar"
                      ? "اضغط زرّ تشغيل التحليل لبدء عمل النموذج"
                      : "Hit Run Analysis to launch the segmentation model"}
                  </p>
                  <Button variant="teal" onClick={runAnalysis}>
                    <Play className="w-4 h-4" />
                    {t("runAnalysis")}
                  </Button>
                </Card>
              )}
            </>
          )}
        </div>

        {/* RIGHT: Metrics + actions */}
        <div className="space-y-5">
          {/* Metrics panel */}
          <Card className="overflow-hidden">
            <div className="relative bg-gradient-to-br from-navy-500 to-navy-700 p-5 text-white">
              <div className="absolute -right-8 -top-8 w-32 h-32 bg-teal-400/20 rounded-full blur-3xl" />
              <div className="relative flex items-center justify-between">
                <div>
                  <div className="text-[10px] uppercase tracking-[0.2em] text-teal-200 font-semibold mb-1">
                    {t("metrics")}
                  </div>
                  <div className="text-lg font-semibold">
                    {status === "done"
                      ? lang === "ar"
                        ? "نتائج التحليل"
                        : "Detection Results"
                      : lang === "ar"
                      ? "بانتظار التحليل"
                      : "Awaiting analysis"}
                  </div>
                </div>
                {status === "done" && (
                  <RiskPill level={metrics.risk} />
                )}
              </div>
            </div>

            <div className="p-5 space-y-3">
              {status !== "done" ? (
                <div className="space-y-3">
                  {[1, 2, 3, 4].map((i) => (
                    <div key={i} className="h-12 rounded-lg bg-ocean-50/70 animate-pulse" />
                  ))}
                </div>
              ) : (
                <>
                  <MetricRow
                    icon={Waves}
                    label={lang === "ar" ? "مساحة التسرّب" : "Spill area"}
                    value={formatArea(metrics.area)}
                  />
                  <MetricRow
                    icon={TrendingUp}
                    label={lang === "ar" ? "نسبة التغطية" : "Coverage"}
                    value={`${Number(metrics.coverage).toFixed(1)}%`}
                  />
                  <MetricRow
                    icon={MapPin}
                    label={t("centroid")}
                    value={formatCoordinates(metrics.centroid[0], metrics.centroid[1])}
                    mono
                  />
                  <MetricRow
                    icon={Activity}
                    label={t("distLand")}
                    value={`${Number(metrics.distLand).toFixed(1)} km`}
                  />
                  <MetricRow
                    icon={Activity}
                    label={t("distCoral")}
                    value={`${Number(metrics.distCoral).toFixed(1)} km`}
                  />
                </>
              )}
            </div>
          </Card>

          {/* Actions */}
          <Card className="p-5 space-y-2">
            <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground font-semibold mb-2">
              {lang === "ar" ? "إجراءات" : "Actions"}
            </div>
            <Button
              className="w-full justify-start"
              variant={status === "uploaded" ? "teal" : "outline"}
              disabled={status !== "uploaded"}
              onClick={runAnalysis}
            >
              <Play className="w-4 h-4" />
              {t("runAnalysis")}
            </Button>
            <Button
              className="w-full justify-start"
              variant="outline"
              disabled={status !== "done" || savingDb}
              onClick={onSaveToDatabase}
            >
              {savingDb ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  {lang === "ar" ? "جاري الحفظ..." : "Saving..."}
                </>
              ) : (
                <>
                  <Save className="w-4 h-4" />
                  {t("saveDb")}
                </>
              )}
            </Button>
            <Button
              className="w-full justify-start"
              variant={status === "done" ? "default" : "outline"}
              disabled={status !== "done" || generatingReport}
              onClick={onGenerateSpillReport}
            >
              {generatingReport ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  {t("generatingSpillReport")}
                </>
              ) : (
                <>
                  <FileText className="w-4 h-4" />
                  {t("generateSpillReport")}
                </>
              )}
            </Button>
            <Button
              asChild
              className="w-full justify-start"
              variant="outline"
              disabled={status !== "done" || !analyzeResult}
            >
              <Link
                to={
                  analyzeResult
                    ? chatbotPath({
                        spillId: spillContextKey({
                          filename: analyzeResult.filename,
                          id: analyzeResult.id,
                        }),
                      })
                    : "#"
                }
                onClick={() => {
                  if (!analyzeResult) return;
                  const spillId = spillContextKey({
                    filename: analyzeResult.filename,
                    id: analyzeResult.id,
                  });
                  stashPendingSpillForChat({
                    spill_id: spillId,
                    filename: analyzeResult.filename || spillId,
                    area_m2: analyzeResult.area_m2,
                    coverage_pct: analyzeResult.coverage_pct,
                    final_risk_level: analyzeResult.final_risk_level,
                    latitude: analyzeResult.latitude,
                    longitude: analyzeResult.longitude,
                    distance_to_land_km: analyzeResult.distance_to_land_km,
                    distance_to_coral_km: analyzeResult.distance_to_coral_km,
                  });
                }}
              >
                <Send className="w-4 h-4" />
                {t("sendChat")}
              </Link>
            </Button>
          </Card>
        </div>
      </div>

      {/* Toast */}
      {savedToast && (
        <div className="fixed bottom-6 end-6 z-50 animate-fade-in">
          <div className="rounded-xl bg-navy-500 text-white shadow-2xl px-4 py-3 flex items-center gap-2.5">
            <CheckCircle2 className="w-4 h-4 text-teal-300" />
            <span className="text-sm font-medium">{savedToast}</span>
          </div>
        </div>
      )}
    </div>
  );
}

function previewImageSrc(path?: string | null, cacheKey?: string): string | undefined {
  if (!path) return undefined;
  const bust = cacheKey ? encodeURIComponent(cacheKey) : String(Date.now());
  return path.includes("?") ? `${path}&v=${bust}` : `${path}?v=${bust}`;
}

function PreviewTile({
  label,
  variant,
  imageUrl,
  cacheKey,
}: {
  label: string;
  variant: "original" | "mask" | "overlay";
  imageUrl?: string | null;
  cacheKey?: string;
}) {
  const src = previewImageSrc(imageUrl, cacheKey);
  return (
    <div className="rounded-2xl border border-ocean-100 overflow-hidden bg-white">
      <div className="aspect-square relative overflow-hidden bg-navy-700">
        {src ? (
          <img
            src={src}
            alt={label}
            className="w-full h-full object-cover"
          />
        ) : (
          <>
            {variant === "original" && <OriginalSVG />}
            {variant === "mask" && <MaskSVG />}
            {variant === "overlay" && <OverlaySVG />}
          </>
        )}
      </div>
      <div className="px-3 py-2 flex items-center justify-between">
        <div className="text-xs font-medium text-navy-500">{label}</div>
        <div className="text-[9px] font-mono uppercase text-muted-foreground">
          512×512
        </div>
      </div>
    </div>
  );
}

function OriginalSVG() {
  return (
    <svg className="w-full h-full" viewBox="0 0 200 200" preserveAspectRatio="none">
      <defs>
        <radialGradient id="origGrad" cx="50%" cy="50%" r="80%">
          <stop offset="0%" stopColor="#1e3a5f" />
          <stop offset="100%" stopColor="#0a1832" />
        </radialGradient>
        <radialGradient id="origSpill" cx="55%" cy="55%" r="25%">
          <stop offset="0%" stopColor="#000" stopOpacity="0.8" />
          <stop offset="100%" stopColor="#000" stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect width="200" height="200" fill="url(#origGrad)" />
      {/* Waves */}
      {[40, 70, 100, 130, 160].map((y) => (
        <path
          key={y}
          d={`M 0 ${y} Q 50 ${y - 5} 100 ${y} T 200 ${y}`}
          stroke="rgba(255,255,255,0.05)"
          strokeWidth="1"
          fill="none"
        />
      ))}
      {/* Spill */}
      <ellipse cx="110" cy="115" rx="55" ry="38" fill="url(#origSpill)" />
      <path
        d="M 70 110 Q 90 90 120 95 Q 155 100 165 125 Q 155 145 120 145 Q 80 145 70 125 Z"
        fill="rgba(0,0,0,0.4)"
      />
    </svg>
  );
}

function MaskSVG() {
  return (
    <svg className="w-full h-full" viewBox="0 0 200 200" preserveAspectRatio="none">
      <rect width="200" height="200" fill="#0a1832" />
      <path
        d="M 70 110 Q 90 90 120 95 Q 155 100 165 125 Q 155 145 120 145 Q 80 145 70 125 Z"
        fill="#0FA4A4"
      />
      <path
        d="M 85 115 Q 100 105 120 108 Q 145 113 150 128 Q 145 138 120 138 Q 95 138 85 128 Z"
        fill="#fff"
        opacity="0.4"
      />
      {/* Grid overlay */}
      <defs>
        <pattern id="mgrid" width="20" height="20" patternUnits="userSpaceOnUse">
          <path d="M 20 0 L 0 0 0 20" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="0.5" />
        </pattern>
      </defs>
      <rect width="200" height="200" fill="url(#mgrid)" />
    </svg>
  );
}

function OverlaySVG() {
  return (
    <svg className="w-full h-full" viewBox="0 0 200 200" preserveAspectRatio="none">
      <defs>
        <radialGradient id="ovGrad" cx="50%" cy="50%" r="80%">
          <stop offset="0%" stopColor="#1e3a5f" />
          <stop offset="100%" stopColor="#0a1832" />
        </radialGradient>
      </defs>
      <rect width="200" height="200" fill="url(#ovGrad)" />
      {[40, 70, 100, 130, 160].map((y) => (
        <path
          key={y}
          d={`M 0 ${y} Q 50 ${y - 5} 100 ${y} T 200 ${y}`}
          stroke="rgba(255,255,255,0.05)"
          strokeWidth="1"
          fill="none"
        />
      ))}
      {/* Outlined spill */}
      <path
        d="M 70 110 Q 90 90 120 95 Q 155 100 165 125 Q 155 145 120 145 Q 80 145 70 125 Z"
        fill="rgba(15,164,164,0.5)"
        stroke="#0FA4A4"
        strokeWidth="1.5"
        strokeDasharray="3 3"
      />
      {/* Centroid pin */}
      <g transform="translate(118 118)">
        <circle r="10" fill="rgba(239,68,68,0.3)" />
        <circle r="5" fill="#ef4444" />
        <circle r="2" fill="#fff" />
      </g>
    </svg>
  );
}

function MetricRow({
  icon: Icon,
  label,
  value,
  sub,
  mono,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  sub?: string;
  mono?: boolean;
}) {
  return (
    <div className="flex items-center gap-3">
      <div className="w-9 h-9 rounded-lg bg-ocean-50 flex items-center justify-center shrink-0">
        <Icon className="w-4 h-4 text-teal-600" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
          {label}
        </div>
        <div
          className={cn(
            "text-sm font-semibold text-navy-500",
            mono && "font-mono text-xs"
          )}
        >
          {value}
        </div>
      </div>
      {sub && (
        <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 font-medium">
          {sub}
        </span>
      )}
    </div>
  );
}
