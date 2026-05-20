import { useEffect, useMemo, useRef, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup, ZoomControl } from "react-leaflet";
import {
  Filter,
  MapPin,
  X,
  Layers,
  Search,
  Sparkles,
  FileText,
  Bot,
  Maximize2,
  ChevronDown,
} from "lucide-react";
import { Link } from "react-router-dom";
import { useLang } from "@/hooks/useLang";
import { useSpills } from "@/hooks/useApi";
import { DISPLAY_RISK_LEVELS, riskLabel } from "@/lib/riskLevels";
import type { RiskLevel, SpillRecord } from "@/types";
import { Button } from "@/components/ui/Button";
import { RiskPill } from "@/components/ui/Badge";
import { cn, riskColor, formatAreaKm2, formatCoordinates, formatRelative } from "@/lib/utils";
import { chatbotPath, spillContextKey } from "@/lib/chatContext";
import {
  SEA_REGIONS,
  seaLabel,
  spillMatchesMapSearch,
  type SeaRegion,
} from "@/lib/seas";

const RISK_LEVELS: RiskLevel[] = DISPLAY_RISK_LEVELS;

export default function MapPage() {
  const { t, lang } = useLang();
  const { spills, count: totalSpills, loading, error } = useSpills();
  const [riskFilter, setRiskFilter] = useState<Set<RiskLevel>>(
    new Set(RISK_LEVELS)
  );
  const [selectedSea, setSelectedSea] = useState<SeaRegion | "all">("all");
  const [seaMenuOpen, setSeaMenuOpen] = useState(false);
  const seaMenuRef = useRef<HTMLDivElement>(null);
  const [maxLandDist, setMaxLandDist] = useState(100);
  const [minAreaKm2, setMinAreaKm2] = useState(0);
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    if (!seaMenuOpen) return;
    const onPointerDown = (e: MouseEvent) => {
      if (seaMenuRef.current && !seaMenuRef.current.contains(e.target as Node)) {
        setSeaMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [seaMenuOpen]);

  const uniqueSpills = useMemo(() => {
    const seen = new Set<string>();
    return spills.filter((spill) => {
      const key = spill.filename || spill.spill_id || spill.id;
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }, [spills]);

  const mappedSpills = useMemo(() => {
    return uniqueSpills.filter((s) => {
      const hasCoords =
        Number.isFinite(s.latitude) &&
        Number.isFinite(s.longitude) &&
        !(Math.abs(s.latitude) < 1e-9 && Math.abs(s.longitude) < 1e-9);
      if (!hasCoords) return false;
      if (!riskFilter.has(s.final_risk_level)) return false;
      if (selectedSea !== "all" && s.region !== selectedSea) return false;
      if (s.distance_to_land_km > maxLandDist) return false;
      if (s.area_m2 < minAreaKm2 * 1_000_000) return false;
      if (search && !spillMatchesMapSearch(s, search)) return false;
      return true;
    });
  }, [uniqueSpills, riskFilter, selectedSea, maxLandDist, minAreaKm2, search]);

  const selected =
    mappedSpills.find((s) => s.id === selectedId) ?? mappedSpills[0] ?? null;

  const toggleRisk = (r: RiskLevel) => {
    const next = new Set(riskFilter);
    if (next.has(r)) next.delete(r);
    else next.add(r);
    setRiskFilter(next);
  };

  const clearFilters = () => {
    setRiskFilter(new Set(RISK_LEVELS));
    setSelectedSea("all");
    setSeaMenuOpen(false);
    setMaxLandDist(100);
    setMinAreaKm2(0);
    setSearch("");
  };

  const seaButtonLabel =
    selectedSea === "all"
      ? t("allSeas")
      : seaLabel(selectedSea, lang);

  const seaCounts = useMemo(() => {
    const c: Record<SeaRegion, number> = {
      "Arabian Gulf": 0,
      "Red Sea": 0,
      "Open Sea": 0,
    };
    uniqueSpills.forEach((s) => {
      const sea = s.region as SeaRegion;
      if (sea in c) c[sea] += 1;
    });
    return c;
  }, [uniqueSpills]);

  /** أقصى مساحة في البيانات (كم²) + هامش بسيط — الفلتر «الحد الأدنى للمساحة» وليس حدّاً أعلى. */
  const areaSliderMaxKm2 = useMemo(() => {
    let peak = 0;
    uniqueSpills.forEach((s) => {
      const km2 = Number(s.area_m2) / 1_000_000;
      if (Number.isFinite(km2) && km2 > peak) peak = km2;
    });
    const withMargin = peak > 0 ? peak * 1.15 : 0.5;
    return Math.max(0.1, Math.ceil(withMargin * 1000) / 1000);
  }, [uniqueSpills]);

  const areaSliderStep = areaSliderMaxKm2 <= 1 ? 0.001 : 0.01;

  // Risk counts from full dataset
  const counts = Object.fromEntries(
    RISK_LEVELS.map((r) => [r, 0])
  ) as Record<RiskLevel, number>;
  uniqueSpills.forEach((s) => {
    if (counts[s.final_risk_level] !== undefined) {
      counts[s.final_risk_level]++;
    }
  });

  return (
    <div className="px-4 lg:px-8 py-6">
      <div className="mb-5 flex items-end justify-between flex-wrap gap-3">
        <div>
          <h1 className="display-font text-3xl lg:text-4xl font-semibold text-navy-500 tracking-tight">
            {t("map")}
          </h1>
          <p className="text-muted-foreground text-sm mt-1 flex items-center gap-2">
            {loading ? (
              <span className="inline-flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-ocean-400 animate-pulse" />
                {lang === "ar" ? "جاري التحميل..." : "Loading..."}
              </span>
            ) : error ? (
              <span className="inline-flex items-center gap-1.5 text-red-600">
                <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
                {lang === "ar" ? "تعذّر الاتصال بالخادم" : "Backend offline"}
              </span>
            ) : (
              <>
                {mappedSpills.length}
                {totalSpills > 0 && mappedSpills.length !== totalSpills && (
                  <span className="text-muted-foreground">
                    {" "}
                    / {totalSpills}
                  </span>
                )}{" "}
                {t("spillsShown")}
                {mappedSpills.length < uniqueSpills.length && (
                  <span className="text-[11px] text-amber-700 ms-1">
                    {lang === "ar"
                      ? `(فلتر: ${uniqueSpills.length - mappedSpills.length} مخفية)`
                      : `(${uniqueSpills.length - mappedSpills.length} hidden by filters)`}
                  </span>
                )}
              </>
            )}
          </p>
        </div>

        {/* Risk legend */}
        <div className="flex items-center gap-1.5">
          {RISK_LEVELS.map((r) => (
            <button
              key={r}
              onClick={() => toggleRisk(r)}
              className={cn(
                "flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs transition",
                riskFilter.has(r)
                  ? "bg-white border-ocean-200"
                  : "bg-transparent border-transparent opacity-40"
              )}
            >
              <span
                className="w-2.5 h-2.5 rounded-full"
                style={{ background: riskColor(r) }}
              />
              <span className="font-medium text-navy-500">
                {riskLabel(r, lang)}
              </span>
              <span className="text-muted-foreground font-mono text-[10px]">
                {counts[r]}
              </span>
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] xl:grid-cols-[280px_1fr_340px] gap-5">
        {/* LEFT: Filters */}
        <aside className="bg-white rounded-2xl border border-ocean-100 p-5 h-fit sticky top-20">
          <div className="flex items-center justify-between mb-5">
            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-teal-600" />
              <span className="font-semibold text-navy-500 text-sm">
                {t("filters")}
              </span>
            </div>
            <button
              onClick={clearFilters}
              className="text-[11px] text-teal-700 hover:text-teal-800 font-medium"
            >
              {t("clearFilters")}
            </button>
          </div>

          {/* Search */}
          <div className="relative mb-3">
            <Search className="absolute start-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={
                lang === "ar"
                  ? "ابحث بالاسم أو البحر (مثل: البحر الأحمر)…"
                  : "Search by name or sea (e.g. Red Sea)…"
              }
              className="w-full h-10 ps-9 pe-3 rounded-xl bg-ocean-50/70 border border-ocean-100 text-sm focus:outline-none focus:ring-2 focus:ring-teal-400/40 focus:border-teal-300 transition"
            />
          </div>

          <div ref={seaMenuRef} className="relative mb-5">
            <label className="mb-1.5 block text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">
              {t("seaFilter")}
            </label>
            <button
              type="button"
              onClick={() => setSeaMenuOpen((o) => !o)}
              className={cn(
                "w-full h-10 px-3 rounded-xl border text-sm flex items-center justify-between gap-2 transition",
                seaMenuOpen
                  ? "bg-teal-50 border-teal-300 text-navy-600 ring-2 ring-teal-400/30"
                  : "bg-ocean-50/70 border-ocean-100 text-navy-500 hover:border-teal-200"
              )}
              aria-expanded={seaMenuOpen}
              aria-haspopup="listbox"
            >
              <span className="truncate font-medium">{seaButtonLabel}</span>
              <ChevronDown
                className={cn(
                  "w-4 h-4 shrink-0 text-muted-foreground transition",
                  seaMenuOpen && "rotate-180"
                )}
              />
            </button>
            {seaMenuOpen && (
              <ul
                role="listbox"
                className="absolute z-50 mt-1 w-full rounded-xl border border-ocean-100 bg-white shadow-lg overflow-hidden py-1"
              >
                <li>
                  <button
                    type="button"
                    role="option"
                    aria-selected={selectedSea === "all"}
                    onClick={() => {
                      setSelectedSea("all");
                      setSeaMenuOpen(false);
                    }}
                    className={cn(
                      "w-full px-3 py-2.5 text-start text-sm flex items-center justify-between gap-2 hover:bg-teal-50 transition",
                      selectedSea === "all" && "bg-teal-50 text-navy-600 font-semibold"
                    )}
                  >
                    <span>{t("allSeas")}</span>
                    <span className="font-mono text-[10px] text-muted-foreground tabular-nums">
                      {uniqueSpills.length}
                    </span>
                  </button>
                </li>
                {SEA_REGIONS.map((sea) => (
                  <li key={sea}>
                    <button
                      type="button"
                      role="option"
                      aria-selected={selectedSea === sea}
                      onClick={() => {
                        setSelectedSea(sea);
                        setSeaMenuOpen(false);
                      }}
                      className={cn(
                        "w-full px-3 py-2.5 text-start text-sm flex items-center justify-between gap-2 hover:bg-teal-50 transition border-t border-ocean-50",
                        selectedSea === sea && "bg-teal-50 text-navy-600 font-semibold"
                      )}
                    >
                      <span>{seaLabel(sea, lang)}</span>
                      <span className="font-mono text-[10px] text-muted-foreground tabular-nums">
                        {seaCounts[sea]}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="space-y-5">
            {/* Risk levels */}
            <FilterSection title={t("riskLevel")}>
              <div className="grid grid-cols-2 gap-1.5">
                {RISK_LEVELS.map((r) => (
                  <button
                    key={r}
                    onClick={() => toggleRisk(r)}
                    className={cn(
                      "flex items-center gap-2 px-2.5 py-1.5 rounded-lg border text-xs transition",
                      riskFilter.has(r)
                        ? "bg-ocean-50 border-ocean-200 text-navy-500"
                        : "bg-white border-ocean-100 text-muted-foreground opacity-60"
                    )}
                  >
                    <span
                      className="w-2 h-2 rounded-full"
                      style={{ background: riskColor(r) }}
                    />
                    {riskLabel(r, lang)}
                  </button>
                ))}
              </div>
            </FilterSection>


            {/* Distance to land */}
            <FilterSection title={t("distanceLand")}>
              <input
                type="range"
                min={0}
                max={100}
                step={0.5}
                value={maxLandDist}
                onChange={(e) => setMaxLandDist(Number(e.target.value))}
                className="w-full accent-teal-500"
              />
              <div className="flex items-center justify-between mt-1.5 text-[11px] text-muted-foreground font-mono">
                <span>0 km</span>
                <span className="font-semibold text-navy-500">
                  ≤ {maxLandDist} km
                </span>
              </div>
            </FilterSection>

            {/* Area */}
            <FilterSection title={t("areaFilter")}>
              <input
                type="range"
                min={0}
                max={areaSliderMaxKm2}
                step={areaSliderStep}
                value={Math.min(minAreaKm2, areaSliderMaxKm2)}
                onChange={(e) => setMinAreaKm2(Number(e.target.value))}
                className="w-full accent-teal-500"
              />
              <div className="flex items-center justify-between mt-1.5 text-[11px] text-muted-foreground font-mono">
                <span>0 km²</span>
                <span className="font-semibold text-navy-500">
                  ≥ {Math.min(minAreaKm2, areaSliderMaxKm2).toFixed(
                    areaSliderMaxKm2 < 1 ? 3 : 2
                  )}{" "}
                  km²
                </span>
              </div>
              <p className="mt-1 text-[10px] leading-4 text-muted-foreground">
                {lang === "ar"
                  ? `أقصى مساحة في بياناتك ≈ ${areaSliderMaxKm2.toFixed(3)} كم² (الفلتر يخفي الأصغر من القيمة المختارة).`
                  : `Largest spill in your data ≈ ${areaSliderMaxKm2.toFixed(3)} km² (filter hides spills smaller than the selected minimum).`}
              </p>
            </FilterSection>
          </div>
        </aside>

        {/* CENTER: Map */}
        <div className="relative">
          <div className="relative rounded-2xl border border-ocean-100 overflow-hidden bg-ocean-50 shadow-lg h-[640px]">
            <MapContainer
              center={[26, 50]}
              zoom={5}
              zoomControl={false}
              className="w-full h-full"
              attributionControl={true}
            >
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
                maxZoom={19}
              />
              <ZoomControl position="bottomright" />
              {mappedSpills.map((s) => {
                const isSelected = selected?.id === s.id;
                return (
                  <CircleMarker
                    key={s.id}
                    center={[s.latitude, s.longitude]}
                    radius={isSelected ? 12 : 8}
                    pathOptions={{
                      color: riskColor(s.final_risk_level),
                      fillColor: riskColor(s.final_risk_level),
                      fillOpacity: isSelected ? 0.9 : 0.65,
                      weight: isSelected ? 3 : 2,
                    }}
                    eventHandlers={{
                      click: () => setSelectedId(s.id),
                    }}
                  >
                    <Popup>
                      <SpillPopup spill={s} />
                    </Popup>
                  </CircleMarker>
                );
              })}
            </MapContainer>

            {/* Map overlay HUD top-left */}
            <div className="absolute top-3 start-3 flex items-center gap-2 z-[400]">
              <div className="rounded-xl bg-white/95 backdrop-blur-md border border-ocean-100 px-3 py-2 shadow-lg">
                <div className="flex items-center gap-2">
                  <Layers className="w-3.5 h-3.5 text-teal-600" />
                  <span className="text-[11px] font-medium text-navy-500">
                    {lang === "ar" ? "خريطة فاتحة" : "Light basemap"}
                  </span>
                </div>
              </div>
              <div className="rounded-xl bg-white/95 backdrop-blur-md border border-ocean-100 px-3 py-2 shadow-lg flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                <span className="text-[11px] font-medium text-navy-500">
                  {mappedSpills.length}
                  {totalSpills > mappedSpills.length
                    ? ` / ${totalSpills}`
                    : ""}{" "}
                  {lang === "ar" ? "نقطة" : "points"}
                </span>
              </div>
            </div>

            {/* Risk legend overlay top-right */}
            <div className="absolute top-3 end-3 z-[400] rounded-xl bg-white/95 backdrop-blur-md border border-ocean-100 p-3 shadow-lg min-w-[160px]">
              <div className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold mb-2">
                {t("riskLevel")}
              </div>
              <div className="space-y-1.5">
                {RISK_LEVELS.map((r) => (
                  <div key={r} className="flex items-center justify-between text-[11px]">
                    <div className="flex items-center gap-2">
                      <span
                        className="w-2.5 h-2.5 rounded-full"
                        style={{ background: riskColor(r) }}
                      />
                      <span className="text-navy-500 font-medium">
                        {riskLabel(r, lang)}
                      </span>
                    </div>
                    <span className="font-mono text-muted-foreground">
                      {counts[r]}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Maximize button */}
            <button className="absolute bottom-3 start-3 z-[400] w-9 h-9 rounded-lg bg-white/95 backdrop-blur-md border border-ocean-100 shadow-lg flex items-center justify-center hover:bg-ocean-50 transition">
              <Maximize2 className="w-4 h-4 text-navy-500" />
            </button>
          </div>
        </div>

        {/* RIGHT: Detail panel */}
        <aside className="hidden xl:block">
          <div className="bg-white rounded-2xl border border-ocean-100 overflow-hidden sticky top-20">
            {selected ? (
              <SpillDetailPanel spill={selected} />
            ) : (
              <div className="p-8 text-center text-muted-foreground text-sm">
                <MapPin className="w-8 h-8 mx-auto mb-3 text-ocean-300" />
                {t("selectMarker")}
              </div>
            )}
          </div>
        </aside>
      </div>

      {/* Mobile detail card */}
      {selected && (
        <div className="xl:hidden mt-5 bg-white rounded-2xl border border-ocean-100">
          <SpillDetailPanel spill={selected} />
        </div>
      )}
    </div>
  );
}

function FilterSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold mb-2">
        {title}
      </div>
      {children}
    </div>
  );
}

function SpillPopup({ spill }: { spill: SpillRecord }) {
  const { t, lang } = useLang();
  const s = spill;
  return (
    <div className="p-3">
      <div className="flex items-center justify-between mb-2">
        <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
          {s.id}
        </div>
        <RiskPill level={s.final_risk_level} size="sm" />
      </div>
      <div className="text-sm font-semibold text-navy-500 mb-0.5">
        {s.region}
      </div>
      <div className="text-[11px] font-mono text-muted-foreground mb-3 truncate">
        {s.filename}
      </div>
      <div className="grid grid-cols-2 gap-2 mb-3 text-xs">
        <PopupStat label={t("area")} value={formatAreaKm2(s.area_m2)} />
        <PopupStat label={t("coverage")} value={`${Number(s.coverage_pct).toFixed(1)}%`} />
        <PopupStat
          label={t("distLand")}
          value={`${Number(s.distance_to_land_km).toFixed(1)} km`}
        />
        <PopupStat
          label={t("distCoral")}
          value={`${Number(s.distance_to_coral_km).toFixed(1)} km`}
        />
      </div>
      <div className="flex gap-1.5">
        <Link
          to="/reports"
          className="flex-1 inline-flex items-center justify-center gap-1 px-2.5 py-1.5 rounded-lg bg-navy-500 text-white text-[10px] font-medium hover:bg-navy-600 transition"
        >
          <FileText className="w-3 h-3" />
          {lang === "ar" ? "تقرير" : "Report"}
        </Link>
        <Link
          to={chatbotPath({ spillId: spillContextKey(s) })}
          className="flex-1 inline-flex items-center justify-center gap-1 px-2.5 py-1.5 rounded-lg bg-teal-500 text-white text-[10px] font-medium hover:bg-teal-600 transition"
        >
          <Bot className="w-3 h-3" />
          {lang === "ar" ? "اسأل" : "Ask AI"}
        </Link>
      </div>
    </div>
  );
}

function PopupStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-ocean-50 px-2 py-1.5">
      <div className="text-[9px] uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <div className="text-xs font-semibold text-navy-500 font-mono">
        {value}
      </div>
    </div>
  );
}

function SpillDetailPanel({ spill }: { spill: SpillRecord }) {
  const { t, lang } = useLang();
  const s = spill;

  return (
    <div>
      {/* Header */}
      <div className="relative h-32 bg-gradient-to-br from-navy-500 to-navy-700 overflow-hidden">
        <svg className="absolute inset-0 w-full h-full opacity-30" viewBox="0 0 400 200">
          <defs>
            <pattern id="popgrid" width="20" height="20" patternUnits="userSpaceOnUse">
              <path d="M 20 0 L 0 0 0 20" fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="0.5" />
            </pattern>
            <radialGradient id="popblob" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#000" stopOpacity="0.7" />
              <stop offset="100%" stopColor="#000" stopOpacity="0" />
            </radialGradient>
          </defs>
          <rect width="100%" height="100%" fill="url(#popgrid)" />
          <ellipse cx="200" cy="100" rx="120" ry="60" fill="url(#popblob)" />
        </svg>
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2">
          <div className="relative">
            <div className="w-6 h-6 rounded-full marker-pulse crit"
              style={{ background: riskColor(s.final_risk_level) }} />
          </div>
        </div>
        <div className="absolute top-3 left-3 right-3 flex items-start justify-between text-white">
          <div className="text-[9px] font-mono opacity-80 tracking-wider">
            {s.id}
          </div>
          <RiskPill level={s.final_risk_level} size="sm" />
        </div>
      </div>

      <div className="p-5">
        <div className="text-sm font-semibold text-navy-500 mb-0.5">
          {s.region}
        </div>
        <div className="text-[11px] font-mono text-muted-foreground mb-4 truncate">
          {s.filename}
        </div>

        <div className="grid grid-cols-2 gap-2 mb-5">
          <DetailStat label={t("area")} value={formatAreaKm2(s.area_m2)} />
          <DetailStat label={t("coverage")} value={`${Number(s.coverage_pct).toFixed(1)}%`} />
          <DetailStat
            label={t("distLand")}
            value={`${Number(s.distance_to_land_km).toFixed(1)} km`}
            sub={s.land_proximity_class}
          />
          <DetailStat
            label={t("distCoral")}
            value={`${Number(s.distance_to_coral_km).toFixed(1)} km`}
            sub={s.coral_risk_class}
          />
        </div>

        <div className="rounded-xl bg-ocean-50 px-3 py-2.5 mb-5 flex items-center justify-between">
          <div>
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
              {lang === "ar" ? "المركز" : "Centroid"}
            </div>
            <div className="text-xs font-mono text-navy-500 font-semibold">
              {formatCoordinates(s.centroid[0], s.centroid[1])}
            </div>
          </div>
          <div className="text-[10px] text-muted-foreground">
            {formatRelative(s.detected_at, lang)}
          </div>
        </div>

        <div className="space-y-2">
          <Button asChild className="w-full" variant="default" size="sm">
            <Link to="/reports">
              <FileText className="w-4 h-4" />
              {t("generateReport")}
            </Link>
          </Button>
          <Button asChild className="w-full" variant="teal" size="sm">
            <Link to={chatbotPath({ spillId: spillContextKey(s) })}>
              <Sparkles className="w-4 h-4" />
              {t("askAi")}
            </Link>
          </Button>
        </div>
      </div>
    </div>
  );
}

function DetailStat({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="rounded-xl border border-ocean-100 p-2.5">
      <div className="text-[9px] uppercase tracking-wider text-muted-foreground mb-0.5">
        {label}
      </div>
      <div className="text-sm font-semibold text-navy-500 font-mono">
        {value}
      </div>
      {sub && (
        <div className="text-[10px] text-teal-700 mt-0.5 font-medium">
          {sub}
        </div>
      )}
    </div>
  );
}
