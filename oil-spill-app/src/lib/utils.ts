import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import type { RiskLevel } from "@/types";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function riskColor(level: RiskLevel): string {
  switch (level) {
    case "NoSpill":
      return "#94a3b8";
    case "Low":
      return "#10b981";
    case "Medium":
      return "#f59e0b";
    case "High":
      return "#ef4444";
  }
}

export function riskClassName(level: RiskLevel): string {
  switch (level) {
    case "NoSpill":
      return "risk-nospill";
    case "Low":
      return "risk-low";
    case "Medium":
      return "risk-medium";
    case "High":
      return "risk-high";
  }
}

export function formatArea(m2: number): string {
  if (m2 >= 1_000_000) return `${(m2 / 1_000_000).toFixed(2)} km²`;
  if (m2 >= 10_000) return `${(m2 / 10_000).toFixed(1)} ha`;
  return `${m2.toLocaleString()} m²`;
}

/** مساحة بالكيلومتر المربع (للخريطة والعرض التفصيلي). */
export function formatAreaKm2(m2: number): string {
  if (!Number.isFinite(m2) || m2 <= 0) return "0 km²";
  const km2 = m2 / 1_000_000;
  if (km2 >= 1) return `${km2.toFixed(3)} km²`;
  if (km2 >= 0.01) return `${km2.toFixed(4)} km²`;
  return `${km2.toFixed(6)} km²`;
}

/** إحداثيات بدون مسافة بينهما: 26.0774°,49.8764° */
export function formatCoordinates(lat: number, lon: number, decimals = 4): string {
  return `${lat.toFixed(decimals)}°,${lon.toFixed(decimals)}°`;
}

export function formatDate(iso: string, lang: "en" | "ar" = "en"): string {
  const d = new Date(iso);
  return d.toLocaleString(lang === "ar" ? "ar-SA" : "en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatRelative(iso: string, lang: "en" | "ar" = "en"): string {
  const d = new Date(iso);
  const diffMin = (Date.now() - d.getTime()) / 60000;
  if (lang === "ar") {
    if (diffMin < 60) return `قبل ${Math.round(diffMin)} دقيقة`;
    if (diffMin < 1440) return `قبل ${Math.round(diffMin / 60)} ساعة`;
    return `قبل ${Math.round(diffMin / 1440)} يوم`;
  }
  if (diffMin < 60) return `${Math.round(diffMin)}m ago`;
  if (diffMin < 1440) return `${Math.round(diffMin / 60)}h ago`;
  return `${Math.round(diffMin / 1440)}d ago`;
}
