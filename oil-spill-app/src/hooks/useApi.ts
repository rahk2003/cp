import { useEffect, useState, useCallback } from "react";
import type { SpillRecord, ReportRecord } from "@/types";
import { fetchSpills, fetchReports } from "@/lib/api";

/**
 * Fetches all spills from the backend once on mount.
 * Falls back to empty array and surfaces an error string for UI.
 */
export function useSpills() {
  const [spills, setSpills] = useState<SpillRecord[]>([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchSpills();
      setSpills(data.spills);
      setCount(data.count || data.spills.length || 0);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      setCount(0);
      console.error("[useSpills] failed:", msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { spills, count, loading, error, refresh };
}

export function useReports() {
  const [reports, setReports] = useState<ReportRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchReports();
      setReports(data.reports);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      console.error("[useReports] failed:", msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { reports, loading, error, refresh };
}
