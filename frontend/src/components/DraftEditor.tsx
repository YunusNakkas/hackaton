import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, isApiError } from "../api/client";
import type { TrainingDraft } from "../api/types";
import { ModalFrame } from "./ModalFrame";

type Content = NonNullable<TrainingDraft["content"]>;
const input = "mt-1 w-full rounded-xl border border-line bg-card-subtle px-3 py-2 text-sm text-ink";

function Field({ title, value, onChange, multiline = false }: {
  title: string; value: string; onChange: (value: string) => void; multiline?: boolean;
}) {
  return <label className="block text-sm text-muted">{title}{multiline
    ? <textarea required rows={3} className={input} value={value} onChange={e => onChange(e.target.value)} />
    : <input required className={input} value={value} onChange={e => onChange(e.target.value)} />}</label>;
}

export function DraftEditor({ draftId, onClose }: { draftId: string; onClose: () => void }) {
  const client = useQueryClient();
  const draft = useQuery({ queryKey: ["admin-draft", draftId], queryFn: () => api<TrainingDraft>(`/admin/training-drafts/${draftId}`) });
  const [content, setContent] = useState<Content | null>(null);
  const [version, setVersion] = useState<number | null>(null);
  const [message, setMessage] = useState("");
  const data = content ?? draft.data?.content;
  const editable = draft.data?.status === "ready";
  function change(update: (next: Content) => void) {
    if (!data) return;
    const next = structuredClone(data);
    update(next);
    setVersion(version ?? draft.data!.version);
    setContent(next);
    setMessage("");
  }
  const save = useMutation({
    mutationFn: () => api<TrainingDraft>(`/admin/training-drafts/${draftId}`, {
      method: "PATCH", body: JSON.stringify({ version: version ?? draft.data?.version, content: data }),
    }),
    onSuccess: updated => {
      client.setQueryData(["admin-draft", draftId], updated);
      void client.invalidateQueries({ queryKey: ["admin-drafts"] });
      setContent(null); setVersion(null); setMessage("Değişiklikler kaydedildi.");
    },
  });
  return <ModalFrame label="Taslağı incele ve düzenle">
    <section className="max-h-[90dvh] w-full max-w-3xl overflow-y-auto rounded-3xl border border-line bg-card p-6">
      <header className="mb-6 flex items-center justify-between gap-4"><h2 id="draft-title" className="font-serif text-2xl">Taslağı incele ve düzenle</h2><button aria-label="Kapat" onClick={onClose}>✕</button></header>
      {draft.isLoading && <p>Yükleniyor…</p>}
      {draft.error && <p role="alert" className="text-accent">{draft.error.message}</p>}
      {!!draft.data?.warnings.length && <aside className="mb-4 rounded-xl bg-warn-soft p-4 text-sm text-warn"><h3 className="font-semibold">Yayımlamadan önce kontrol edin</h3><ul className="mt-2 list-inside list-disc">{draft.data.warnings.map((warning, i) => <li key={i}>{warning}</li>)}</ul></aside>}
      {data && <form onSubmit={e => { e.preventDefault(); save.mutate(); }} className="space-y-6">
        <fieldset disabled={!editable || save.isPending} className="space-y-6 disabled:opacity-80">
          {data.scenarios.map((scenario, i) => <section key={scenario.key} className="space-y-3 rounded-2xl border border-line p-4">
            <h3 className="font-semibold">Senaryo {i + 1}</h3>
            <Field title="Başlık" value={scenario.title} onChange={v => change(c => { c.scenarios[i].title = v; })} />
            <Field title="Özet" multiline value={scenario.summary} onChange={v => change(c => { c.scenarios[i].summary = v; })} />
            <div className="grid gap-3 sm:grid-cols-2">
              <label>Zorluk<select className={input} value={scenario.difficulty} onChange={e => change(c => { c.scenarios[i].difficulty = e.target.value as typeof scenario.difficulty; })}><option value="easy">Kolay</option><option value="medium">Orta</option><option value="hard">Zor</option></select></label>
              <label>En fazla cevap<input type="number" min={2} max={20} required className={input} value={scenario.max_turns} onChange={e => change(c => { c.scenarios[i].max_turns = Number(e.target.value); })} /></label>
            </div>
            {([['name', 'Müşteri adı'], ['context', 'Müşterinin durumu'], ['mood', 'Ruh hali'], ['hidden_goal', 'Müşterinin amacı']] as const).map(([key, title]) => <Field key={key} title={title} value={scenario.customer[key]} onChange={v => change(c => { c.scenarios[i].customer[key] = v; })} />)}
            <Field title="İlk müşteri mesajı" multiline value={scenario.opening_line} onChange={v => change(c => { c.scenarios[i].opening_line = v; })} />
            <Field title="Başarı ölçütleri (her satıra bir ölçüt)" multiline value={scenario.success_criteria.join('\n')} onChange={v => change(c => { c.scenarios[i].success_criteria = v.split('\n'); })} />
            <div className="space-y-2 text-sm"><p className="text-muted">Çalışana gösterilecek politikalar</p>{data.policies.map(p => <label key={p.id} className="flex items-center gap-2"><input type="checkbox" checked={scenario.visible_policy_ids.includes(p.id)} onChange={e => change(c => { c.scenarios[i].visible_policy_ids = e.target.checked ? [...scenario.visible_policy_ids, p.id] : scenario.visible_policy_ids.filter(id => id !== p.id); })} />{p.title}</label>)}</div>
          </section>)}
          <section className="space-y-4"><h3 className="font-semibold">İşletme politikaları</h3>{data.policies.map((p, i) => <div key={p.id} className="space-y-2"><Field title="Politika başlığı" value={p.title} onChange={v => change(c => { c.policies[i].title = v; })} /><Field title="Kural" multiline value={p.body} onChange={v => change(c => { c.policies[i].body = v; })} /></div>)}</section>
          <section className="space-y-4"><h3 className="font-semibold">Değerlendirme ölçütleri</h3>{data.rubric.dimensions.map((d, i) => <div key={d.id} className="space-y-3 rounded-2xl border border-line p-4"><Field title="Ölçüt adı" value={d.name} onChange={v => change(c => { c.rubric.dimensions[i].name = v; })} /><Field title="Açıklama" value={d.description} onChange={v => change(c => { c.rubric.dimensions[i].description = v; })} /><label>Ağırlık<input required type="number" min={0.01} step={0.01} className={input} value={d.weight} onChange={e => change(c => { c.rubric.dimensions[i].weight = Number(e.target.value); })} /></label>{d.levels.map((level, j) => <Field key={j} title={`${j} puan açıklaması`} value={level} onChange={v => change(c => { c.rubric.dimensions[i].levels[j] = v; })} />)}</div>)}</section>
        </fieldset>
        {save.error && <p role="alert" className="text-accent">{save.error.message} {isApiError(save.error) && save.error.status === 409 && <button type="button" className="underline" onClick={() => { setContent(null); setVersion(null); save.reset(); void draft.refetch(); }}>Güncel taslağı yükle (yerel düzenlemeleri bırak)</button>}</p>}
        {message && <p role="status" className="text-pine">{message}</p>}
        {editable && <button disabled={!content || save.isPending} className="rounded-full bg-primary px-5 py-2 text-white disabled:opacity-50">{save.isPending ? "Kaydediliyor…" : "Değişiklikleri Kaydet"}</button>}
      </form>}
    </section>
  </ModalFrame>;
}
