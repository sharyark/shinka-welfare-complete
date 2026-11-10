import { useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';

/** Loads data whenever the screen comes into view; gives data, error and a reload function. */
export function useLoad<T>(load: () => Promise<T>) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(() => {
    setLoading(true);
    load()
      .then((value) => {
        setData(value);
        setError(null);
      })
      .catch(setError)
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useFocusEffect(reload);
  return { data, error, loading, reload };
}
