"use client";

import { createContext, ReactNode, useContext, useEffect, useMemo, useState } from "react";

type QueryKey = readonly unknown[];

export class QueryClient {
  private listeners = new Set<() => void>();

  subscribe(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  async invalidateQueries(_: { queryKey: QueryKey }): Promise<void> {
    this.listeners.forEach((listener) => listener());
  }
}

const QueryClientContext = createContext<QueryClient | null>(null);

export function QueryClientProvider({ client, children }: { client: QueryClient; children: ReactNode }) {
  return <QueryClientContext.Provider value={client}>{children}</QueryClientContext.Provider>;
}

export function useQueryClient(): QueryClient {
  const client = useContext(QueryClientContext);
  if (!client) {
    throw new Error("useQueryClient must be used within QueryClientProvider");
  }
  return client;
}

export function useQuery<T>({ queryKey, queryFn }: { queryKey: QueryKey; queryFn: () => Promise<T> }) {
  const queryClient = useQueryClient();
  const [data, setData] = useState<T | undefined>(undefined);
  const [error, setError] = useState<Error | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [version, setVersion] = useState(0);
  const key = useMemo(() => JSON.stringify(queryKey), [queryKey]);

  useEffect(() => queryClient.subscribe(() => setVersion((current) => current + 1)), [queryClient]);

  useEffect(() => {
    let mounted = true;
    setIsLoading(true);
    setError(null);

    queryFn()
      .then((response) => {
        if (!mounted) return;
        setData(response);
      })
      .catch((queryError: unknown) => {
        if (!mounted) return;
        setError(queryError instanceof Error ? queryError : new Error("Query failed"));
      })
      .finally(() => {
        if (!mounted) return;
        setIsLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, [key, queryFn, version]);

  return {
    data,
    isLoading,
    isError: !!error,
    error,
  };
}

export function useMutation<TData, TVariables>({
  mutationFn,
  onSuccess,
  onError,
}: {
  mutationFn: (variables: TVariables) => Promise<TData>;
  onSuccess?: (data: TData) => void | Promise<void>;
  onError?: (error: Error) => void;
}) {
  const [isPending, setIsPending] = useState(false);

  const mutate = async (variables: TVariables) => {
    setIsPending(true);
    try {
      const result = await mutationFn(variables);
      await onSuccess?.(result);
    } catch (mutationError) {
      onError?.(mutationError instanceof Error ? mutationError : new Error("Mutation failed"));
    } finally {
      setIsPending(false);
    }
  };

  return {
    mutate,
    isPending,
  };
}
