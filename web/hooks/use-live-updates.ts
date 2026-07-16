"use client";

import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { API_BASE_URL, apiFetch } from "@/lib/api-client";

const RECONNECT_DELAY_MS = 3000;

/**
 * Mount once for the whole authenticated app. Opens an SSE connection so any
 * domain event (a CSV/OFX import, a connector sync) refreshes the dashboard
 * without a manual reload, elsewhere in the same session or from another
 * tab/device. Pass `enabled: false` while auth status is still resolving --
 * hooks can't be called conditionally, so the on/off switch lives inside
 * the effect instead of around the hook call.
 */
export function useLiveUpdates(enabled: boolean): void {
  const queryClient = useQueryClient();
  const sourceRef = useRef<EventSource | null>(null);
  const stoppedRef = useRef(false);

  useEffect(() => {
    if (!enabled) return;
    stoppedRef.current = false;

    const connect = async () => {
      if (stoppedRef.current) return;
      try {
        const { ticket } = await apiFetch<{ ticket: string }>("/api/v1/events/ticket", {
          method: "POST",
        });
        if (stoppedRef.current) return;

        const source = new EventSource(`${API_BASE_URL}/api/v1/events/stream?ticket=${ticket}`);
        sourceRef.current = source;

        source.onmessage = () => {
          // Coarse invalidation: any domain event can change numbers on
          // nearly every panel, so there's little value yet in maintaining
          // a fine-grained event-type -> query-key map.
          void queryClient.invalidateQueries();
        };

        source.onerror = () => {
          // The ticket is single-use, so EventSource's own built-in
          // reconnect (which would replay the same URL/ticket) can't
          // succeed here -- close it and mint a fresh ticket instead.
          source.close();
          sourceRef.current = null;
          if (!stoppedRef.current) {
            setTimeout(() => void connect(), RECONNECT_DELAY_MS);
          }
        };
      } catch {
        if (!stoppedRef.current) {
          setTimeout(() => void connect(), RECONNECT_DELAY_MS);
        }
      }
    };

    void connect();

    return () => {
      stoppedRef.current = true;
      sourceRef.current?.close();
      sourceRef.current = null;
    };
  }, [queryClient, enabled]);
}
