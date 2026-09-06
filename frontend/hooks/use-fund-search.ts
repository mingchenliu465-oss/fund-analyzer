"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { searchFunds } from "@/services/fund";

/**
 * Shared debounced fund search. Results are cached across pages so repeated
 * searches do not keep hitting the backend on slower machines.
 */
export function useFundSearch(query: string, limit = 6) {
  const [debouncedQuery, setDebouncedQuery] = useState("");

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(query.trim()), 250);
    return () => window.clearTimeout(timer);
  }, [query]);

  const normalizedQuery = debouncedQuery.toLowerCase();
  const { data = [], isFetching } = useQuery({
    queryKey: ["fundSearch", normalizedQuery],
    queryFn: () => searchFunds(debouncedQuery),
    enabled: normalizedQuery.length > 0,
    staleTime: 10 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
    retry: 0,
  });

  const isCurrentQuery = query.trim().toLowerCase() === normalizedQuery;

  return {
    suggestions: normalizedQuery && isCurrentQuery ? data.slice(0, limit) : [],
    isSearching: query.trim().length > 0 && (!isCurrentQuery || isFetching),
  };
}
