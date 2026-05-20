/** ثلاثة بحار رئيسية للفلترة والخريطة والشات (نفس منطق الباك إند). */
export type SeaRegion = "Arabian Gulf" | "Red Sea" | "Open Sea";

export const SEA_REGIONS: SeaRegion[] = ["Arabian Gulf", "Red Sea", "Open Sea"];

export const SEA_LABELS: Record<SeaRegion, { en: string; ar: string }> = {
  "Arabian Gulf": { en: "Arabian Gulf", ar: "الخليج العربي" },
  "Red Sea": { en: "Red Sea", ar: "البحر الأحمر" },
  "Open Sea": { en: "Open Sea", ar: "البحر المفتوح" },
};

/** يصنّف النقطة حسب الإحداثيات (متطابق مع backend _infer_sea_region). */
export function inferSeaRegion(lat: number, lon: number): SeaRegion | null {
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
  if (Math.abs(lat) < 1e-9 && Math.abs(lon) < 1e-9) return null;
  if (lat >= 12 && lat <= 28 && lon >= 33 && lon <= 44) return "Red Sea";
  if (lat >= 20 && lat <= 30 && lon >= 47 && lon <= 60) return "Arabian Gulf";
  return "Open Sea";
}

export function seaLabel(region: SeaRegion, lang: "ar" | "en"): string {
  return SEA_LABELS[region][lang];
}

/** كلمات بحث إضافية (عربي/إنجليزي) للفلترة والبحث في الخريطة. */
export const SEA_SEARCH_ALIASES: Record<SeaRegion, string[]> = {
  "Red Sea": [
    "red sea",
    "red",
    "البحر الأحمر",
    "البحر الاحمر",
    "بحر أحمر",
    "بحر احمر",
    "أحمر",
    "احمر",
  ],
  "Arabian Gulf": [
    "arabian gulf",
    "persian gulf",
    "gulf",
    "الخليج العربي",
    "الخليج",
    "خليج",
    "عمان",
  ],
  "Open Sea": [
    "open sea",
    "open",
    "offshore",
    "البحر المفتوح",
    "بحر مفتوح",
    "مفتوح",
    "عرض البحر",
  ],
};

export function seaSearchText(region: SeaRegion): string {
  return [region, SEA_LABELS[region].en, SEA_LABELS[region].ar, ...SEA_SEARCH_ALIASES[region]]
    .join(" ")
    .toLowerCase();
}

/** هل النص يطابق بحراً معيّناً (للبحث أو الفلترة). */
export function queryMatchesSea(query: string, sea: SeaRegion): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return false;
  return seaSearchText(sea).includes(q);
}

/** بحث حالة على الخريطة: اسم الملف، المعرف، البحر (عربي وإنجليزي). */
export function spillMatchesMapSearch(
  spill: { filename: string; id: string; region: string },
  query: string
): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  const base = [spill.filename, spill.id, spill.region].join(" ").toLowerCase();
  if (base.includes(q)) return true;

  const region = spill.region as SeaRegion;
  if (!SEA_REGIONS.includes(region)) return false;
  if (seaSearchText(region).includes(q)) return true;

  const matchingSeas = SEA_REGIONS.filter((sea) => seaSearchText(sea).includes(q));
  if (matchingSeas.length > 0) return matchingSeas.includes(region);
  return false;
}
