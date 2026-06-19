import { useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useWebSocket } from "./useWebSocket.js";

export function useLiveJobRefresh(jobId) {
  const queryClient = useQueryClient();

  const refreshJobs = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["jobs"] });
    queryClient.invalidateQueries({ queryKey: ["quarantined-jobs"] });
    queryClient.invalidateQueries({ queryKey: ["manager-dashboard"] });
    queryClient.invalidateQueries({ queryKey: ["agents"] });
    if (jobId) {
      queryClient.invalidateQueries({
        queryKey: ["jobs", "detail", String(jobId)],
      });
    }
  }, [jobId, queryClient]);

  const onUploadsMessage = useCallback(
    (message) => {
      const payload = message?.payload || {};
      if (!jobId || String(payload.upload_id) === String(jobId)) {
        refreshJobs();
      } else if (
        message?.event === "upload_status" ||
        String(payload.status || "").length
      ) {
        queryClient.invalidateQueries({ queryKey: ["jobs"] });
      }
    },
    [jobId, queryClient, refreshJobs],
  );

  const onManagerMessage = useCallback(() => {
    refreshJobs();
  }, [refreshJobs]);

  const onDashboardMessage = useCallback(() => {
    refreshJobs();
  }, [refreshJobs]);

  useWebSocket("uploads", onUploadsMessage);
  useWebSocket("manager", onManagerMessage);
  useWebSocket("dashboard", onDashboardMessage);
}
