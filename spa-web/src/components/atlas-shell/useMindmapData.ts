"use client";

import { useCallback, useEffect, useState } from "react";

import { readBackendQuery, type AuthUser } from "@/lib/api";
import type { AtlasIndexNode } from "@/lib/atlas";

type SelectedNodeMeta = {
  id: number;
  type: AtlasIndexNode["type"];
} | null;

type UseMindmapDataInput = {
  user: AuthUser | null;
  selectedMeta: SelectedNodeMeta;
};

export default function useMindmapData({ user, selectedMeta }: UseMindmapDataInput) {
  const [mindmapPayload, setMindmapPayload] = useState<Record<string, unknown> | null>(null);
  const [mindmapPending, setMindmapPending] = useState(false);
  const [mindmapError, setMindmapError] = useState("");

  const loadMindmap = useCallback(
    async (activeUser: AuthUser, nodeId: number, nodeType: AtlasIndexNode["type"]): Promise<void> => {
      setMindmapPending(true);
      setMindmapError("");
      try {
        const payload = await readBackendQuery({
          actor_username: activeUser.username,
          kind: "mindmap.root",
          params: { node_id: nodeId, node_type: nodeType },
        });
        setMindmapPayload((payload as Record<string, unknown>) || null);
      } catch (error) {
        setMindmapError(String(error instanceof Error ? error.message : error));
        setMindmapPayload(null);
      } finally {
        setMindmapPending(false);
      }
    },
    [],
  );

  useEffect(() => {
    if (!user || !selectedMeta) {
      setMindmapPayload(null);
      return;
    }
    void loadMindmap(user, selectedMeta.id, selectedMeta.type);
  }, [loadMindmap, selectedMeta, user]);

  return {
    mindmapPayload,
    mindmapPending,
    mindmapError,
  };
}
