import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Send,
  Sparkles,
  Bot,
  User,
  Globe2,
  MapPin,
  TrendingUp,
  AlertCircle,
  X,
  RotateCcw,
  ExternalLink,
} from "lucide-react";
import { useLang } from "@/hooks/useLang";
import { Card } from "@/components/ui/Card";
import { RiskPill } from "@/components/ui/Badge";
import { useSpills } from "@/hooks/useApi";
import { sendChat } from "@/lib/api";
import {
  readPendingSpillForChat,
  type PendingSpillContext,
} from "@/lib/chatContext";
import { normalizeArabicUiTerms } from "@/lib/terminology";
import { cn, formatArea, formatCoordinates } from "@/lib/utils";
import type { ChatMessage, SpillRecord } from "@/types";

const initialMessages = (lang: "en" | "ar"): ChatMessage[] => [
  {
    id: "m1",
    role: "assistant",
    content:
      lang === "ar"
        ? "أهلاً بك. أنا وكيلك الذكي لكشف التسرّبات النفطية. يمكنني الإجابة عن أسئلتك المتعلقة بالاكتشافات، وتوليد تقارير بالعربية والإنجليزية، وشرح مستويات الخطورة. يمكنك اختيار حالة محددة كسياق إضافي أو تركها فارغة وسأحدد المصدر المناسب حسب سؤالك."
        : "Welcome. I'm your oil spill detection assistant. I can answer questions about detections, generate bilingual reports, and explain risk levels. You can optionally select a spill as context, or leave it empty and I'll choose the best source based on your question.",
    timestamp: new Date().toISOString(),
  },
];

const SUGGEST = ["sp1", "sp2", "sp3", "sp4", "sp5"] as const;
const CHAT_STORAGE_KEY = "naftscan_chatbot_state_v2";

function normalizeContextValue(value: string): string {
  return value.trim().toLowerCase();
}

function spillMatchesContext(
  spill: {
    id?: string;
    filename?: string;
  },
  value: string
): boolean {
  const wanted = normalizeContextValue(value);
  if (!wanted) return false;
  return [spill.id, spill.filename].some((candidate) => normalizeContextValue(String(candidate || "")) === wanted);
}

function spillContextValue(spill: {
  id?: string;
  filename?: string;
}): string {
  return String(spill.filename || spill.id || "").trim();
}

function compactSearchValue(value: string): string {
  return normalizeContextValue(value).replace(/[^a-z0-9]/g, "");
}

function digitsOnly(value: string): string {
  return value.replace(/\D/g, "");
}

function scoreSpillSearch(
  spill: SpillRecord,
  query: string
): number {
  const rawQuery = normalizeContextValue(query);
  if (!rawQuery) return Number.POSITIVE_INFINITY;

  const compactQuery = compactSearchValue(query);
  const digitQuery = digitsOnly(query);
  const fields = [
    String(spill.filename || ""),
    String(spill.id || ""),
    String(spill.region || ""),
  ];

  let best = Number.POSITIVE_INFINITY;

  for (const field of fields) {
    const normalized = normalizeContextValue(field);
    const compact = compactSearchValue(field);
    const digits = digitsOnly(field);

    if (normalized === rawQuery || compact === compactQuery) {
      best = Math.min(best, 0);
    } else if (normalized.startsWith(rawQuery) || compact.startsWith(compactQuery)) {
      best = Math.min(best, 1);
    } else if (normalized.includes(rawQuery) || compact.includes(compactQuery)) {
      best = Math.min(best, 2);
    }

    if (digitQuery) {
      if (digits === digitQuery) {
        best = Math.min(best, 0);
      } else if (digits.startsWith(digitQuery)) {
        best = Math.min(best, 1 + Math.max(0, digits.length - digitQuery.length) / 100);
      } else if (digits.includes(digitQuery)) {
        best = Math.min(best, 2 + Math.max(0, digits.indexOf(digitQuery)) / 100);
      }
    }
  }

  return best;
}

function getSpillSuggestions(spills: SpillRecord[], query: string, limit = 12): SpillRecord[] {
  const trimmed = query.trim();
  if (!trimmed) {
    return spills.slice(0, 80);
  }

  return [...spills]
    .map((spill) => ({
      spill,
      score: scoreSpillSearch(spill, trimmed),
    }))
    .filter((entry) => Number.isFinite(entry.score))
    .sort((a, b) => {
      if (a.score !== b.score) return a.score - b.score;
      return spillContextValue(a.spill).localeCompare(spillContextValue(b.spill));
    })
    .slice(0, limit)
    .map((entry) => entry.spill);
}

function loadStoredChatState(lang: "en" | "ar"): {
  messages: ChatMessage[];
  contextSpillId: string;
  compareSpillLeft: string;
  compareSpillRight: string;
} {
  if (typeof window === "undefined") {
    return { messages: initialMessages(lang), contextSpillId: "", compareSpillLeft: "", compareSpillRight: "" };
  }
  try {
    const raw = window.localStorage.getItem(CHAT_STORAGE_KEY);
    if (!raw) return { messages: initialMessages(lang), contextSpillId: "", compareSpillLeft: "", compareSpillRight: "" };
    const parsed = JSON.parse(raw) as {
      messages?: ChatMessage[];
      contextSpillId?: string;
      compareSpillLeft?: string;
      compareSpillRight?: string;
    };
    const messages = Array.isArray(parsed.messages) && parsed.messages.length
      ? parsed.messages
      : initialMessages(lang);
    return {
      messages,
      contextSpillId: typeof parsed.contextSpillId === "string" ? parsed.contextSpillId : "",
      compareSpillLeft: typeof parsed.compareSpillLeft === "string" ? parsed.compareSpillLeft : "",
      compareSpillRight: typeof parsed.compareSpillRight === "string" ? parsed.compareSpillRight : "",
    };
  } catch {
    return { messages: initialMessages(lang), contextSpillId: "", compareSpillLeft: "", compareSpillRight: "" };
  }
}

function spillIdFromUrl(): string {
  if (typeof window === "undefined") return "";
  return (new URLSearchParams(window.location.search).get("spill_id") || "").trim();
}

function pendingMatchesContext(
  pending: PendingSpillContext,
  contextId: string
): boolean {
  const wanted = normalizeContextValue(contextId);
  if (!wanted) return false;
  return [pending.spill_id, pending.filename].some(
    (v) => normalizeContextValue(String(v || "")) === wanted
  );
}

function pendingToSpillRecord(pending: PendingSpillContext): SpillRecord {
  const lat = Number(pending.latitude) || 0;
  const lon = Number(pending.longitude) || 0;
  return {
    id: pending.spill_id || pending.filename,
    filename: pending.filename || pending.spill_id,
    latitude: lat,
    longitude: lon,
    area_m2: Number(pending.area_m2) || 0,
    coverage_pct: Number(pending.coverage_pct) || 0,
    distance_to_land_km: Number(pending.distance_to_land_km) || 0,
    distance_to_coral_km: Number(pending.distance_to_coral_km) || 0,
    land_proximity_class: "Unknown",
    coral_risk_class: "Unknown",
    final_risk_level:
      (pending.final_risk_level as SpillRecord["final_risk_level"]) || "Medium",
    detected_at: new Date().toISOString(),
    centroid: [lat, lon],
    region: lat !== 0 || lon !== 0 ? "Open Sea" : "—",
  };
}

export default function ChatbotPage() {
  const { t, lang } = useLang();
  const { spills, refresh: refreshSpills } = useSpills();
  const [searchParams] = useSearchParams();
  const urlContextAppliedRef = useRef(spillIdFromUrl());
  const persistedRef = useRef(loadStoredChatState(lang));
  const [messages, setMessages] = useState<ChatMessage[]>(() => persistedRef.current.messages);
  const [input, setInput] = useState("");
  const [typing, setTyping] = useState(false);
  const [contextSpillId, setContextSpillId] = useState<string>(() => {
    const fromUrl = spillIdFromUrl();
    return fromUrl || persistedRef.current.contextSpillId;
  });
  const [compareSpillLeft, setCompareSpillLeft] = useState<string>(() => persistedRef.current.compareSpillLeft);
  const [compareSpillRight, setCompareSpillRight] = useState<string>(() => persistedRef.current.compareSpillRight);
  const [pendingSpill, setPendingSpill] = useState<PendingSpillContext | null>(() =>
    readPendingSpillForChat()
  );
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, typing]);

  // من التحليل / الخريطة / التقارير: ?spill_id=... يحدّث سياق الوكيل مباشرة
  useEffect(() => {
    const fromUrl = (searchParams.get("spill_id") || "").trim();
    if (!fromUrl) return;
    urlContextAppliedRef.current = fromUrl;
    setContextSpillId(fromUrl);
    const pending = readPendingSpillForChat();
    if (pending && pendingMatchesContext(pending, fromUrl)) {
      setPendingSpill(pending);
    }
    void refreshSpills();
  }, [searchParams, refreshSpills]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(
      CHAT_STORAGE_KEY,
      JSON.stringify({ messages, contextSpillId, compareSpillLeft, compareSpillRight })
    );
  }, [messages, contextSpillId, compareSpillLeft, compareSpillRight]);

  const startNewChat = () => {
    setMessages(initialMessages(lang));
    setContextSpillId("");
    setCompareSpillLeft("");
    setCompareSpillRight("");
    setInput("");
    urlContextAppliedRef.current = "";
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(CHAT_STORAGE_KEY);
    }
  };

  const send = async (text?: string) => {
    const content = (text ?? input).trim();
    if (!content) return;
    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      content,
      timestamp: new Date().toISOString(),
      context_spill_id: contextSpillId || undefined,
    };
    const nextHistory = [...messages, userMsg]
      .slice(-8)
      .map(({ role, content, context_spill_id, intent, source_used, resolved_spill_id }) => ({
        role,
        content,
        context_spill_id,
        intent,
        source_used,
        resolved_spill_id,
      }));
    setMessages((m) => [...m, userMsg]);
    setInput("");
    setTyping(true);

    const compareSpillIds = [compareSpillLeft.trim(), compareSpillRight.trim()].filter(Boolean);
    try {
      const res = await sendChat({
        message: content,
        spill_id: contextSpillId || undefined,
        compare_spill_ids: compareSpillIds.length >= 2 ? compareSpillIds : undefined,
        language: lang,
        history: nextHistory,
      });
      if (res.resolved_spill_id) {
        setContextSpillId(res.resolved_spill_id);
      }
      const sourceTag = res.source_used
        ? `\n\n_${sourceLabel(res.source_used, lang)}_`
        : "";
      setMessages((m) => [
        ...m,
        {
          id: `a-${Date.now()}`,
          role: "assistant",
          content: (res.reply || "—") + sourceTag,
          timestamp: new Date().toISOString(),
          source_used: res.source_used,
          intent: res.intent,
          used_search: res.used_search,
          needs_clarification: res.needs_clarification,
          clarification_options: res.clarification_options,
          sources: res.sources,
          resolved_spill_id: res.resolved_spill_id,
        },
      ]);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setMessages((m) => [
        ...m,
        {
          id: `err-${Date.now()}`,
          role: "assistant",
          content:
            (lang === "ar"
              ? "تعذّر الوصول للخادم. تأكد من تشغيل الباك اند على المنفذ 8000.\n"
              : "Could not reach the backend. Make sure it is running on port 8000.\n") +
            "`" + msg + "`",
          timestamp: new Date().toISOString(),
          source_used: "chat_fallback",
        },
      ]);
    } finally {
      setTyping(false);
    }
  };

  const trimmedContextSpillId = contextSpillId.trim();
  const trimmedCompareSpillLeft = compareSpillLeft.trim();
  const trimmedCompareSpillRight = compareSpillRight.trim();
  const contextSpill = spills.find((s) => spillMatchesContext(s, trimmedContextSpillId));
  const contextFromPending =
    !contextSpill &&
    pendingSpill &&
    pendingMatchesContext(pendingSpill, trimmedContextSpillId)
      ? pendingToSpillRecord(pendingSpill)
      : null;
  const activeContextSpill = contextSpill || contextFromPending;
  const compareSpillLeftRecord = spills.find((s) => spillMatchesContext(s, trimmedCompareSpillLeft));
  const compareSpillRightRecord = spills.find((s) => spillMatchesContext(s, trimmedCompareSpillRight));
  const hasContext = Boolean(trimmedContextSpillId);
  const selectedContextOption = activeContextSpill
    ? spillContextValue(activeContextSpill)
    : trimmedContextSpillId &&
        spills.some((s) => spillMatchesContext(s, trimmedContextSpillId))
      ? trimmedContextSpillId
      : "";
  const contextSuggestions = useMemo(() => getSpillSuggestions(spills, trimmedContextSpillId), [spills, trimmedContextSpillId]);
  const compareLeftSuggestions = useMemo(() => getSpillSuggestions(spills, trimmedCompareSpillLeft), [spills, trimmedCompareSpillLeft]);
  const compareRightSuggestions = useMemo(() => getSpillSuggestions(spills, trimmedCompareSpillRight), [spills, trimmedCompareSpillRight]);
  const compareReady = Boolean(trimmedCompareSpillLeft && trimmedCompareSpillRight);
  const triggerComparison = () => {
    if (!compareReady || typing) return;
    send(
      lang === "ar"
        ? "قارن بين الحالتين من حيث الخطورة، والقرب من اليابسة، والحاجة إلى التدخل السريع."
        : "Compare the two selected cases by risk, proximity to land, and urgency of intervention."
    );
  };

  return (
    <div className="px-4 lg:px-8 py-6 h-[calc(100vh-4rem)] lg:h-[calc(100vh-4rem)]">
      <div className="h-full grid lg:grid-cols-[1fr_320px] gap-5">
        {/* CHAT */}
        <div className="flex flex-col bg-white rounded-2xl border border-ocean-100 overflow-hidden">
          {/* Header */}
          <div className="px-5 py-4 border-b border-ocean-100 flex items-center gap-3">
            <div className="relative">
              <div className="absolute inset-0 bg-teal-400 blur-md opacity-50" />
              <div className="relative w-10 h-10 rounded-xl bg-gradient-to-br from-navy-500 to-teal-600 flex items-center justify-center">
                <Bot className="w-5 h-5 text-white" />
              </div>
            </div>
            <div className="flex-1">
              <div className="display-font font-semibold text-navy-500 text-lg leading-tight">
                {t("chatTitle")}
              </div>
              <div className="text-[11px] text-muted-foreground flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                {t("chatSubtitle")}
              </div>
            </div>
            <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-teal-50 border border-teal-200">
              <Globe2 className="w-3 h-3 text-teal-700" />
              <span className="text-[10px] font-mono uppercase tracking-wider text-teal-700">
                {lang === "ar" ? "AR" : "EN"}
              </span>
            </div>
            <button
              type="button"
              onClick={startNewChat}
              className="inline-flex items-center gap-1.5 rounded-xl border border-ocean-100 px-3 py-2 text-xs font-semibold text-muted-foreground transition hover:border-teal-200 hover:bg-teal-50 hover:text-teal-700"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              <span>{lang === "ar" ? "محادثة جديدة" : "New chat"}</span>
            </button>
          </div>

          {/* Messages */}
          <div
            ref={scrollRef}
            className="flex-1 overflow-y-auto px-4 sm:px-6 py-5 space-y-4 scrollbar-thin"
          >
            {messages.map((m) => (
              <MessageBubble
                key={m.id}
                message={m}
                onChooseSpill={(spillId, label) => {
                  setContextSpillId(spillId);
                  setMessages((prev) => [
                    ...prev,
                    {
                      id: `sys-${Date.now()}`,
                      role: "system",
                      content:
                        lang === "ar"
                          ? `تم تحديد الحالة: ${label}. الآن يمكنك إعادة سؤالك وسأربطه بهذه الحالة.`
                          : `Selected spill: ${label}. You can now resend your question and I will answer using this spill.`,
                      timestamp: new Date().toISOString(),
                      context_spill_id: spillId,
                    },
                  ]);
                }}
              />
            ))}
            {typing && (
              <div className="flex gap-3">
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-navy-500 to-teal-600 flex items-center justify-center shrink-0">
                  <Bot className="w-4 h-4 text-white" />
                </div>
                <div className="rounded-2xl rounded-ss-sm bg-ocean-50 px-4 py-3">
                  <div className="typing-dots">
                    <span /><span /><span />
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Suggested prompts */}
          {messages.length <= 1 && (
            <div className="px-4 sm:px-6 py-3 border-t border-ocean-100">
              <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground font-semibold mb-2 flex items-center gap-1.5">
                <Sparkles className="w-3 h-3 text-teal-600" />
                {t("suggested")}
              </div>
              <div className="flex flex-wrap gap-2">
                {SUGGEST.map((k) => (
                  <button
                    key={k}
                    onClick={() => send(t(k))}
                    className="text-xs px-3 py-1.5 rounded-full bg-ocean-50 hover:bg-teal-50 hover:text-teal-700 border border-ocean-100 hover:border-teal-200 text-navy-400 transition"
                  >
                    {t(k)}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Input */}
          <div className="px-4 sm:px-6 py-4 border-t border-ocean-100">
            <div className="relative">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") send();
                }}
                placeholder={t("typeMessage")}
                className="w-full h-12 ps-4 pe-24 rounded-2xl bg-ocean-50/70 border border-ocean-100 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400/40 focus:border-teal-300 transition"
              />
              <div className="absolute end-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
                <button
                  onClick={() => send()}
                  disabled={!input.trim()}
                  className="h-9 px-4 rounded-xl bg-teal-500 hover:bg-teal-600 text-white text-sm font-medium transition flex items-center gap-1.5 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <Send className="w-4 h-4 rtl:scale-x-[-1]" />
                  <span className="hidden sm:inline">{t("send")}</span>
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* CONTEXT PANEL */}
        <aside className="hidden lg:flex flex-col bg-white rounded-2xl border border-ocean-100 overflow-hidden">
          <div className="px-5 py-4 border-b border-ocean-100">
            <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground font-semibold mb-0.5">
              {t("contextTitle")}
            </div>
            <div className="text-sm font-semibold text-navy-500">
              {lang === "ar" ? "حالة اختيارية" : "Optional spill context"}
            </div>
          </div>

          {/* Selector */}
          <div className="px-5 py-3 border-b border-ocean-100">
            <div className="mb-1.5 flex items-center justify-between gap-2">
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold block">
                {t("selectSpill")}
              </label>
              {hasContext && (
                <button
                  type="button"
                  onClick={() => {
                    setContextSpillId("");
                    urlContextAppliedRef.current = "";
                  }}
                  className="inline-flex items-center gap-1 rounded-full border border-ocean-100 px-2 py-1 text-[10px] font-semibold text-muted-foreground transition hover:border-red-200 hover:bg-red-50 hover:text-red-600"
                  aria-label={lang === "ar" ? "إزالة الحالة المختارة" : "Clear selected spill"}
                >
                  <X className="w-3 h-3" />
                  <span>{lang === "ar" ? "إزالة" : "Clear"}</span>
                </button>
              )}
            </div>
            <select
              value={selectedContextOption}
              onChange={(e) => setContextSpillId(e.target.value)}
              className="w-full h-9 px-2 rounded-lg border border-ocean-100 bg-ocean-50/40 text-xs text-navy-500 focus:outline-none focus:ring-2 focus:ring-teal-400/40 focus:border-teal-300"
            >
              <option value="">
                {lang === "ar" ? "بدون حالة محددة" : "No fixed spill context"}
              </option>
              {spills.length === 0 && (
                <option value="" disabled>
                  {lang === "ar" ? "لا توجد بيانات" : "No spills loaded"}
                </option>
              )}
              {spills.slice(0, 200).map((s) => (
                <option key={s.id} value={spillContextValue(s)}>
                  {spillContextValue(s).slice(0, 24)} · {s.region}
                </option>
              ))}
            </select>
            <div className="mt-2">
              <input
                value={contextSpillId}
                onChange={(e) => setContextSpillId(e.target.value)}
                placeholder={lang === "ar" ? "أدخل اسم الصورة أو رقم الحالة، مثال: 00525.tif" : "Enter image name or spill ID, e.g. 00525.tif"}
                className="w-full h-9 px-3 rounded-lg border border-ocean-100 bg-white text-xs text-navy-500 placeholder:text-muted-foreground/80 focus:outline-none focus:ring-2 focus:ring-teal-400/40 focus:border-teal-300"
              />
              <p className="mt-1 text-[11px] leading-5 text-muted-foreground">
                {lang === "ar"
                  ? "يمكنك كتابة اسم الصورة مباشرة إذا لم ترد اختيار الحالة من القائمة."
                  : "You can type the image name directly instead of choosing from the list."}
              </p>
              {trimmedContextSpillId && (
                <div className="mt-2 rounded-xl border border-ocean-100 bg-white shadow-sm overflow-hidden">
                  <div className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground border-b border-ocean-100 bg-ocean-50/60">
                    {lang === "ar" ? "نتائج البحث" : "Search results"}
                  </div>
                  {contextSuggestions.length > 0 ? (
                    <div className="max-h-56 overflow-y-auto">
                      {contextSuggestions.map((spill) => {
                        const value = spillContextValue(spill);
                        const isActive = spillMatchesContext(spill, trimmedContextSpillId);
                        return (
                          <button
                            key={`${spill.id}-${value}`}
                            type="button"
                            onClick={() => setContextSpillId(value)}
                            className={cn(
                              "w-full px-3 py-2.5 text-start transition border-b border-ocean-100 last:border-b-0 hover:bg-teal-50",
                              isActive && "bg-teal-50"
                            )}
                          >
                            <div className="text-xs font-semibold text-navy-500 font-mono">
                              {value}
                            </div>
                            <div className="mt-0.5 text-[11px] text-muted-foreground">
                              {spill.region}
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="px-3 py-3 text-xs text-muted-foreground">
                      {lang === "ar"
                        ? "لا توجد نتائج مطابقة حاليًا. أكمل الرقم أو اكتب اسم الصورة الكامل."
                        : "No matching results yet. Keep typing or enter the full image name."}
                    </div>
                  )}
                </div>
              )}
            </div>
            <div className="mt-4 rounded-2xl border border-ocean-100 bg-ocean-50/40 p-3">
              <div className="mb-2 text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">
                {lang === "ar" ? "مقارنة حالتين" : "Compare two spills"}
              </div>
              <div className="space-y-3">
                <SearchableSpillInput
                  lang={lang}
                  label={lang === "ar" ? "الصورة الأولى" : "First image"}
                  value={compareSpillLeft}
                  onChange={setCompareSpillLeft}
                  suggestions={compareLeftSuggestions}
                />
                <SearchableSpillInput
                  lang={lang}
                  label={lang === "ar" ? "الصورة الثانية" : "Second image"}
                  value={compareSpillRight}
                  onChange={setCompareSpillRight}
                  suggestions={compareRightSuggestions}
                />
              </div>
              <p className="mt-2 text-[11px] leading-5 text-muted-foreground">
                {lang === "ar"
                  ? "اختر صورتين أو اكتب اسميهما، ثم اسأل مثل: أيهما أخطر؟ أيهما أقرب لليابسة؟ أيهما يحتاج تدخل أسرع؟"
                  : "Pick two images or type their names, then ask: which is riskier? which is closer to land? which needs faster intervention?"}
              </p>
              <button
                type="button"
                onClick={triggerComparison}
                disabled={!compareReady || typing}
                className="mt-3 w-full h-10 rounded-xl bg-navy-500 text-white text-sm font-semibold transition hover:bg-navy-600 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {lang === "ar" ? "مقارنة" : "Compare"}
              </button>
            </div>
          </div>

          {/* Spill details */}
          <div className="flex-1 overflow-y-auto px-5 py-4 scrollbar-thin">
            {compareReady ? (
              <div className="space-y-4">
                <div className="rounded-2xl border border-teal-100 bg-teal-50/70 px-4 py-3">
                  <div className="text-sm font-semibold text-navy-500">
                    {lang === "ar" ? "المقارنة جاهزة" : "Comparison ready"}
                  </div>
                  <p className="mt-1 text-xs leading-6 text-muted-foreground">
                    {lang === "ar"
                      ? "اسأل الوكيل الذكي الآن عن أي فرق بين الحالتين، وسيقارن بينهما مباشرة من البيانات."
                      : "Ask the assistant about any difference between the two cases, and it will compare them directly from the data."}
                  </p>
                </div>
                <CompareSpillCard
                  lang={lang}
                  title={lang === "ar" ? "الحالة الأولى" : "First case"}
                  value={trimmedCompareSpillLeft}
                  spill={compareSpillLeftRecord}
                  onClear={() => setCompareSpillLeft("")}
                />
                <CompareSpillCard
                  lang={lang}
                  title={lang === "ar" ? "الحالة الثانية" : "Second case"}
                  value={trimmedCompareSpillRight}
                  spill={compareSpillRightRecord}
                  onClear={() => setCompareSpillRight("")}
                />
              </div>
            ) : activeContextSpill ? (
              <div className="space-y-4">
                {contextFromPending && !contextSpill && (
                  <div className="rounded-xl border border-teal-200 bg-teal-50/80 px-3 py-2 text-[11px] text-teal-800">
                    {lang === "ar"
                      ? "تم نقل نتيجة التحليل الأخيرة مباشرة من صفحة التحليل."
                      : "Latest analysis result was transferred from the Analyze page."}
                  </div>
                )}
                <div className="flex items-center justify-between gap-3">
                  <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
                    {activeContextSpill.id}
                  </div>
                  <div className="flex items-center gap-2">
                    <RiskPill level={activeContextSpill.final_risk_level} size="sm" />
                    <button
                      type="button"
                      onClick={() => {
                        setContextSpillId("");
                        urlContextAppliedRef.current = "";
                        setPendingSpill(null);
                      }}
                      className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-ocean-100 text-muted-foreground transition hover:border-red-200 hover:bg-red-50 hover:text-red-600"
                      aria-label={lang === "ar" ? "إزالة الحالة المختارة" : "Clear selected spill"}
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                <div>
                  <div className="text-sm font-semibold text-navy-500 mb-0.5">
                    {activeContextSpill.region}
                  </div>
                  <div className="text-[11px] font-mono text-muted-foreground truncate">
                    {activeContextSpill.filename}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <CtxStat
                    icon={TrendingUp}
                    label={t("area")}
                    value={formatArea(activeContextSpill.area_m2)}
                  />
                  <CtxStat
                    icon={TrendingUp}
                    label={t("coverage")}
                    value={`${Number(activeContextSpill.coverage_pct).toFixed(1)}%`}
                  />
                  <CtxStat
                    icon={MapPin}
                    label={t("distLand")}
                    value={`${Number(activeContextSpill.distance_to_land_km).toFixed(1)} km`}
                  />
                  <CtxStat
                    icon={MapPin}
                    label={t("distCoral")}
                    value={`${Number(activeContextSpill.distance_to_coral_km).toFixed(1)} km`}
                  />
                </div>

                <div className="rounded-xl bg-ocean-50 px-3 py-2.5">
                  <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
                    {t("centroid")}
                  </div>
                  <div className="text-xs font-mono text-navy-500 font-semibold">
                    {formatCoordinates(
                      activeContextSpill.centroid[0],
                      activeContextSpill.centroid[1]
                    )}
                  </div>
                </div>
              </div>
            ) : hasContext ? (
              <div className="flex h-full items-center">
                <div className="w-full rounded-2xl border border-dashed border-ocean-100 bg-ocean-50/50 px-4 py-5 text-center">
                  <div className="mb-2 inline-flex h-10 w-10 items-center justify-center rounded-full bg-white text-teal-600 shadow-sm">
                    <AlertCircle className="w-5 h-5" />
                  </div>
                  <div className="text-sm font-semibold text-navy-500">
                    {lang === "ar" ? "تم إدخال حالة يدويًا" : "Manual spill context entered"}
                  </div>
                  <div className="mt-1 text-xs font-mono text-navy-500 break-all">
                    {trimmedContextSpillId}
                  </div>
                  <p className="mt-2 text-xs leading-6 text-muted-foreground">
                    {lang === "ar"
                      ? "سيتم إرسال هذه القيمة كسياق مع سؤالك التالي حتى لو لم تظهر ضمن الحالات المحمّلة في القائمة."
                      : "This value will be sent as context with your next question even if it is not listed in the loaded spills."}
                  </p>
                </div>
              </div>
            ) : (
              <div className="flex h-full items-center">
                <div className="w-full rounded-2xl border border-dashed border-ocean-100 bg-ocean-50/50 px-4 py-5 text-center">
                  <div className="mb-2 inline-flex h-10 w-10 items-center justify-center rounded-full bg-white text-teal-600 shadow-sm">
                    <AlertCircle className="w-5 h-5" />
                  </div>
                  <div className="text-sm font-semibold text-navy-500">
                    {lang === "ar" ? "لا توجد حالة مثبّتة" : "No pinned spill"}
                  </div>
                  <p className="mt-1 text-xs leading-6 text-muted-foreground">
                    {lang === "ar"
                      ? "عند ترك هذا القسم فارغاً، سيحدد الوكيل تلقائياً أفضل مصدر للإجابة بناءً على صياغة سؤالك."
                      : "When this panel is empty, the assistant will automatically choose the best source based on your question."}
                  </p>
                </div>
              </div>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}

function MessageBubble({
  message,
  onChooseSpill,
}: {
  message: ChatMessage;
  onChooseSpill?: (spillId: string, label: string) => void;
}) {
  const { lang } = useLang();
  const isUser = message.role === "user";
  const displayContent =
    lang === "ar" && !isUser
      ? normalizeArabicUiTerms(message.content)
      : message.content;
  return (
    <div className={cn("flex gap-3", isUser && "flex-row-reverse")}>
      <div
        className={cn(
          "w-8 h-8 rounded-full shrink-0 flex items-center justify-center",
          isUser
            ? "bg-navy-500 text-white"
            : "bg-gradient-to-br from-navy-500 to-teal-600 text-white"
        )}
      >
        {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
      </div>
      <div
        className={cn(
          "max-w-[80%] sm:max-w-[70%] rounded-2xl px-4 py-2.5 text-sm",
          isUser
            ? "bg-navy-500 text-white rounded-se-sm"
            : "bg-ocean-50 text-navy-500 rounded-ss-sm"
        )}
      >
        <div className="whitespace-pre-wrap leading-relaxed">
          {displayContent}
        </div>
        {!isUser && Boolean(message.sources?.length) && (
          <div className="mt-3 rounded-xl border border-ocean-100 bg-white/70 p-3">
            <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              {lang === "ar" ? "المصادر الموثوقة" : "Trusted sources"}
            </div>
            <div className="space-y-2">
              {message.sources?.map((source, index) => (
                <a
                  key={`${source.url || source.title || "src"}-${index}`}
                  href={String(source.url || "#")}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-start justify-between gap-3 rounded-lg border border-ocean-100 bg-ocean-50/70 px-3 py-2 text-xs transition hover:border-teal-200 hover:bg-teal-50"
                >
                  <div className="min-w-0">
                    <div className="font-semibold text-navy-500">
                      {String(source.title || source.domain || source.url || "Source")}
                    </div>
                    {source.domain && (
                      <div className="mt-0.5 font-mono text-[10px] text-muted-foreground">
                        {String(source.domain)}
                      </div>
                    )}
                  </div>
                  <ExternalLink className="mt-0.5 h-3.5 w-3.5 shrink-0 text-teal-700" />
                </a>
              ))}
            </div>
          </div>
        )}
        {!isUser && message.needs_clarification && Boolean(message.clarification_options?.length) && (
          <div className="mt-3 flex flex-wrap gap-2">
            {message.clarification_options?.map((option) => (
              <button
                key={option.id}
                type="button"
                onClick={() => onChooseSpill?.(option.id, option.label)}
                className="rounded-full border border-teal-200 bg-white px-3 py-1.5 text-xs font-semibold text-teal-700 transition hover:bg-teal-50"
              >
                {option.label}
              </button>
            ))}
          </div>
        )}
        <div
          className={cn(
            "mt-1.5 text-[9px] font-mono uppercase tracking-wider",
            isUser ? "text-ocean-200" : "text-muted-foreground"
          )}
        >
          {new Date(message.timestamp).toLocaleTimeString(
            lang === "ar" ? "ar-SA" : "en-US",
            { hour: "2-digit", minute: "2-digit" }
          )}
        </div>
      </div>
    </div>
  );
}

function SearchableSpillInput({
  lang,
  label,
  value,
  onChange,
  suggestions,
}: {
  lang: "en" | "ar";
  label: string;
  value: string;
  onChange: (value: string) => void;
  suggestions: SpillRecord[];
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const trimmedValue = value.trim();

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [open]);

  const pick = (contextValue: string) => {
    onChange(contextValue);
    setOpen(false);
  };

  return (
    <div ref={rootRef} className="relative">
      <label className="mb-1 block text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">
        {label}
      </label>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "w-full h-9 px-3 rounded-lg border text-xs text-start transition flex items-center justify-between gap-2",
          open
            ? "border-teal-300 bg-teal-50 text-navy-600 ring-2 ring-teal-400/30"
            : "border-ocean-100 bg-white text-navy-500 hover:border-teal-200"
        )}
      >
        <span className={cn("truncate font-mono", !trimmedValue && "text-muted-foreground")}>
          {trimmedValue ||
            (lang === "ar" ? "اضغط لاختيار حالة…" : "Click to choose a case…")}
        </span>
        <span className="text-[10px] text-muted-foreground shrink-0">{open ? "▲" : "▼"}</span>
      </button>
      <input
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        placeholder={lang === "ar" ? "أو ابحث بالاسم…" : "Or search by name…"}
        className="mt-1.5 w-full h-8 px-3 rounded-lg border border-ocean-100 bg-ocean-50/40 text-xs text-navy-500 placeholder:text-muted-foreground/80 focus:outline-none focus:ring-2 focus:ring-teal-400/40 focus:border-teal-300"
      />
      {open && (
        <div className="absolute z-50 mt-1 w-full rounded-xl border border-ocean-100 bg-white shadow-lg overflow-hidden">
          {suggestions.length > 0 ? (
            <div className="max-h-52 overflow-y-auto">
              {suggestions.map((spill) => {
                const contextValue = spillContextValue(spill);
                const isActive = spillMatchesContext(spill, trimmedValue);
                return (
                  <button
                    key={`${spill.id}-${contextValue}`}
                    type="button"
                    onClick={() => pick(contextValue)}
                    className={cn(
                      "w-full px-3 py-2.5 text-start transition border-b border-ocean-100 last:border-b-0 hover:bg-teal-50",
                      isActive && "bg-teal-50"
                    )}
                  >
                    <div className="text-xs font-semibold text-navy-500 font-mono">
                      {contextValue}
                    </div>
                    <div className="mt-0.5 text-[11px] text-muted-foreground">
                      {spill.region}
                    </div>
                  </button>
                );
              })}
            </div>
          ) : (
            <div className="px-3 py-3 text-xs text-muted-foreground">
              {lang === "ar"
                ? "لا توجد نتائج. جرّب جزءاً من اسم الصورة."
                : "No matches. Try part of the image name."}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function CompareSpillCard({
  lang,
  title,
  value,
  spill,
  onClear,
}: {
  lang: "en" | "ar";
  title: string;
  value: string;
  spill?: SpillRecord;
  onClear: () => void;
}) {
  return (
    <div className="rounded-2xl border border-ocean-100 bg-white p-4">
      <div className="mb-2 flex items-center justify-between gap-3">
        <div className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">
          {title}
        </div>
        <button
          type="button"
          onClick={onClear}
          className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-ocean-100 text-muted-foreground transition hover:border-red-200 hover:bg-red-50 hover:text-red-600"
          aria-label={lang === "ar" ? "إزالة الحالة" : "Clear spill"}
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
      {spill ? (
        <div className="space-y-3">
          <div>
            <div className="text-xs font-mono text-navy-500 font-semibold">
              {spillContextValue(spill)}
            </div>
            <div className="mt-0.5 text-[11px] text-muted-foreground">
              {spill.region}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <CtxStat
              icon={TrendingUp}
              label={lang === "ar" ? "الخطورة" : "Risk"}
              value={spill.final_risk_level}
            />
            <CtxStat
              icon={TrendingUp}
              label={lang === "ar" ? "المساحة" : "Area"}
              value={formatArea(spill.area_m2)}
            />
            <CtxStat
              icon={MapPin}
              label={lang === "ar" ? "اليابسة" : "Land"}
              value={`${Number(spill.distance_to_land_km).toFixed(1)} km`}
            />
            <CtxStat
              icon={MapPin}
              label={lang === "ar" ? "الشعاب المرجانية" : "Coral reefs"}
              value={`${Number(spill.distance_to_coral_km).toFixed(1)} km`}
            />
          </div>
        </div>
      ) : (
        <div>
          <div className="text-xs font-mono text-navy-500 break-all">
            {value}
          </div>
          <p className="mt-2 text-xs leading-6 text-muted-foreground">
            {lang === "ar"
              ? "سيتم إرسال هذه القيمة للمقارنة حتى لو لم تظهر ضمن القائمة الحالية."
              : "This value will still be sent for comparison even if it is not in the current list."}
          </p>
        </div>
      )}
    </div>
  );
}

function CtxStat({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-lg border border-ocean-100 p-2">
      <div className="flex items-center gap-1.5 mb-0.5">
        <Icon className="w-3 h-3 text-teal-600" />
        <div className="text-[9px] uppercase tracking-wider text-muted-foreground">
          {label}
        </div>
      </div>
      <div className="text-xs font-semibold text-navy-500 font-mono">
        {value}
      </div>
    </div>
  );
}

function sourceLabel(source: string, lang: "en" | "ar"): string {
  const map: Record<string, { ar: string; en: string }> = {
    database: { ar: "المصدر: قاعدة البيانات", en: "Source: database" },
    unified_assistant: { ar: "المصدر: الوكيل الذكي الموحّد", en: "Source: unified assistant" },
    rag: { ar: "المصدر: RAG (تقارير ومستندات)", en: "Source: RAG (reports & docs)" },
    rag_default: { ar: "المصدر: RAG", en: "Source: RAG" },
    response_guide: { ar: "المصدر: دليل الاستجابة البيئية", en: "Source: environmental response guide" },
    fallback_csv_environment: { ar: "المصدر: التحليل المحلي للحالة", en: "Source: local case analysis" },
    fallback_csv_database: { ar: "المصدر: قاعدة البيانات المحلية", en: "Source: local database" },
    fallback_response_guide: { ar: "المصدر: دليل الاستجابة المحلي", en: "Source: local response guide" },
    selected_spill_local: { ar: "المصدر: تحليل الحالة المحددة", en: "Source: selected spill analysis" },
    trusted_solution_search: { ar: "المصدر: بحث موثوق للحلول", en: "Source: trusted solution search" },
    local_response_guide: { ar: "المصدر: الخطة التشغيلية المحلية", en: "Source: local operational plan" },
    database_agent: { ar: "المصدر: وكيل قاعدة البيانات", en: "Source: database agent" },
    spill_compare: { ar: "المصدر: مقارنة مباشرة بين الحالات", en: "Source: direct spill comparison" },
    clarification: { ar: "المصدر: طلب توضيح", en: "Source: clarification prompt" },
    followup_explanation: { ar: "المصدر: شرح تابع للمحادثة", en: "Source: conversational follow-up" },
    agent_meta: { ar: "المصدر: شرح داخلي للوكيل", en: "Source: agent self-explanation" },
    guardrail: { ar: "المصدر: حارس النطاق", en: "Source: scope guardrail" },
    chat_fallback: { ar: "المصدر: بديل المحادثة", en: "Source: chat fallback" },
    database_error: { ar: "خطأ في قاعدة البيانات", en: "Database error" },
    none: { ar: "—", en: "—" },
  };
  const entry = map[source];
  if (!entry) return source;
  return lang === "ar" ? entry.ar : entry.en;
}
