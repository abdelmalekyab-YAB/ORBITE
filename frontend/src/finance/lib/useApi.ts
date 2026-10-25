import { useCallback, useEffect, useState } from "react";

/** Petit hook de chargement avec rechargement manuel (remplacer par react-query si Orbit l'utilise). */
export function useApi<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const reload = useCallback(() => {
    setLoading(true);
    fn()
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, deps); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    reload();
  }, [reload]);
  return { data, error, loading, reload };
}
