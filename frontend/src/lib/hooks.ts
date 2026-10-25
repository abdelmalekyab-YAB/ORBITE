import { useCallback, useContext, useEffect, useState } from "react";
import { api } from "./api";
import { UIVersionContext } from "./version";

/** Charge `path` ; recharge après chaque mutation signalée (version UI) ou via `reload`. */
export function useApi<T>(path: string | null) {
  const version = useContext(UIVersionContext);
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const reload = useCallback(() => setTick((n) => n + 1), []);

  useEffect(() => {
    if (!path) return;
    let alive = true;
    api<T>(path)
      .then((d) => {
        if (alive) {
          setData(d);
          setError(null);
        }
      })
      .catch((e: Error) => alive && setError(e.message));
    return () => {
      alive = false;
    };
  }, [path, tick, version]);

  return { data, error, reload, setData };
}
