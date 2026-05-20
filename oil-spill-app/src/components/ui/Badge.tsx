import * as React from "react";
import { cn, riskClassName } from "@/lib/utils";
import { riskLabel } from "@/lib/riskLevels";
import type { RiskLevel } from "@/types";
import { useLang } from "@/hooks/useLang";

export function Badge({
  className,
  ...props
}: React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium border",
        className
      )}
      {...props}
    />
  );
}

export function RiskPill({
  level,
  size = "md",
}: {
  level: RiskLevel;
  size?: "sm" | "md";
}) {
  const { lang } = useLang();
  const label = riskLabel(level, lang);
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border font-medium",
        riskClassName(level),
        size === "sm" ? "px-2 py-0.5 text-[10px]" : "px-2.5 py-1 text-xs"
      )}
    >
      <span
        className="w-1.5 h-1.5 rounded-full"
        style={{
          background:
            level === "High"
              ? "#dc2626"
              : level === "Medium"
              ? "#d97706"
              : level === "Low"
              ? "#059669"
              : "#94a3b8",
        }}
      />
      {label}
    </span>
  );
}
