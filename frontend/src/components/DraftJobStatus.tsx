import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Job } from "../api/types";
import { jobLabel } from "../lib/labels";

export function DraftJobStatus({ jobId }: { jobId: string }) {
  const job = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => api<Job>(`/jobs/${jobId}`),
    refetchInterval: query => !query.state.data || !["ready", "error"].includes(query.state.data.status) ? 1500 : false,
  });
  return <p role="status" className={`text-xs ${job.data?.error || job.error ? "text-accent" : "text-muted"}`}>{job.error?.message ?? job.data?.error?.message ?? (job.data ? jobLabel[job.data.status] : "İş durumu yükleniyor…")}</p>;
}
