import type { AssignmentStatus, Difficulty, EvaluationStatus, JobStatus, PracticeChannel, SessionSummary, Speaker } from "../api/types";

export const difficultyLabel: Record<Difficulty, string> = {
  easy: "Kolay",
  medium: "Orta",
  hard: "Zor",
};

export const sectorLabel = (sector: string) =>
  sector === "retail" ? "Mağaza" : sector === "hotel" ? "Otel" : sector;

export const assignmentLabel: Record<AssignmentStatus, string> = {
  assigned: "Atandı",
  in_progress: "Sürüyor",
  completed: "Tamamlandı",
};

export const jobLabel: Record<JobStatus, string> = {
  queued: "Sırada",
  transcribing: "Konuşman yazıya dökülüyor",
  generating: "Müşteri yazıyor",
  synthesizing: "Cevap hazırlanıyor",
  evaluating: "Değerlendiriliyor",
  ready: "Hazır",
  error: "Hata",
};

export const evaluationLabel: Record<EvaluationStatus, string> = {
  pending: "Hazırlanıyor",
  ready: "Hazır",
  needs_review: "Yönetici incelemesi bekliyor",
  error: "Değerlendirme tamamlanamadı",
};

export const speakerLabel: Record<Speaker, string> = {
  customer: "Müşteri",
  employee: "Sen",
};

const flags: Record<string, string> = {
  unverified_evidence: "Bazı alıntılar transkriptte doğrulanamadı",
  short_session: "Görüşme puanlama için kısa kaldı",
  schema_repaired: "Rapor bir onarım adımından geçti",
  dropped_evidence: "Bazı kanıtlar konuşmayla eşleştirilemediği için rapordan çıkarıldı",
  score_without_verified_evidence: "Bazı puanlar için doğrulanmış konuşma kanıtı bulunamadı",
  unknown_policy_ref: "Raporda işletme kurallarıyla eşleştirilemeyen bir politika atfı var",
};

export function flagLabel(flag: string) {
  return flags[flag] ?? flag;
}

export function formatWhen(iso: string | null | undefined) {
  if (!iso) return "";
  return new Intl.DateTimeFormat("tr-TR", {
    day: "numeric",
    month: "long",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}

export function formatDue(iso: string | null) {
  if (!iso) return null;
  return new Intl.DateTimeFormat("tr-TR", { day: "numeric", month: "long" }).format(new Date(iso));
}

export function channelLabel(channel: PracticeChannel) {
  return channel === "phone" ? "Telefon" : "Mesaj";
}

export function summaryOutcome(item: Pick<SessionSummary, "model_runtime" | "status" | "evaluation_status" | "total">) {
  if (item.model_runtime === "stub") return "Sahte puan";
  if (item.status === "finished" && item.evaluation_status == null) return "Bırakıldı";
  if (item.total?.complete && item.total.score != null) return `${item.total.score} / ${item.total.max_score}`;
  if (item.status === "finished") return "Puan yok";
  return "Sürüyor";
}

export function formatClock(ms: number) {
  const total = Math.min(30, Math.floor(ms / 1000));
  return `0:${String(total).padStart(2, "0")}`;
}
