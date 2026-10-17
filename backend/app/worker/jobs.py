"""Tek worker döngüsü. Model çağrıları API isteği içinde değil burada yapılır.

Her aşamadan sonra durum ve ara sonuç (`job.state`) kalıcı yazılır; tekrar denemede biten
aşamalar atlanır, böylece ses yeniden yüklenmez ve aynı cevap iki kez üretilmez.
"""

import logging
import re
import time
from pathlib import Path

from sqlalchemy import update
from sqlalchemy.orm import Session

from app import schemas
from app.core.config import Settings, get_settings
from app.core.ids import iso, utcnow
from app.db import get_sessionmaker
from app.models import Evaluation, Job, PracticeSession, Training, TrainingDraft, Turn
from app.services import drafts as draftsvc
from app.services import evaluation as evalsvc
from app.services import prompts, tts
from app.services.model_client import ModelClient, ModelUnavailable, get_model_client

log = logging.getLogger("provamusteri.worker")


class JobFailed(Exception):
    def __init__(self, code: str, message: str, retryable: bool):
        super().__init__(message)
        self.code, self.message, self.retryable = code, message, retryable


def _stage(db: Session, job: Job, status: str) -> None:
    job.status = status
    db.commit()


def _media(settings: Settings, rel: str | Path) -> Path:
    return settings.media_dir / rel


def _ready_history(db: Session, session_id: str, before_index: int) -> list[Turn]:
    return (db.query(Turn).filter(Turn.session_id == session_id, Turn.index < before_index,
                                  Turn.status == "ready", Turn.text.is_not(None))
            .order_by(Turn.index).all())


_ROLE_PREFIX = re.compile(r"^\s*(müşteri|musteri|customer|ayşe hanım|assistant)\s*:\s*", re.I)


def _drop_unbalanced(text: str, *pair: str) -> str:
    # Model bazen tırnağın yalnız birini yazıyor ('Hemen" sizin için...'); eşleşmeyen tırnak ekranda ve
    # seslendirmede anlamsız. Dengeli tırnaklar (gerçek alıntı) korunur.
    count = sum(text.count(ch) for ch in pair)
    balanced = count % 2 == 0 if len(pair) == 1 else text.count(pair[0]) == text.count(pair[1])
    return text if balanced else "".join(ch for ch in text if ch not in pair)


def clean_reply(text: str) -> tuple[str, bool]:
    ended = prompts.END_MARKER in text
    text = text.replace(prompts.END_MARKER, "")
    text = _ROLE_PREFIX.sub("", text.strip()).strip()
    if len(text) > 1 and text[0] == text[-1] == '"':  # yalnız cümleyi saran tırnak çifti
        text = text[1:-1].strip()
    text = _drop_unbalanced(_drop_unbalanced(text, '"'), "“", "”")
    return " ".join(text.split()), ended


# Anlatıcı/koç gibi konuşan cevaplar (gerçek mikrofon denemesinde görüldü:
# "Ayşe Hanım'ın bu yanıtı ile karşılaştığı durumu... Yeni bir diyalog başlatabilirsin.")
_META = re.compile(r"diyalog|senaryo|\brol(ü|ün|de|den|e)?\b|yapay zek|asistan|müşteri olarak|çalışanın", re.I)
MAX_REPLY_CHARS = 350
MIN_TURNS_BEFORE_END = 2  # model ilk cevaptan sonra görüşmeyi bitirebiliyordu
FALLBACK_REPLY = "Pardon, tam anlayamadım. Bu durumda ne yapabiliriz?"


def is_hint_echo(text: str, hints: list[str]) -> bool:
    """Model sesi anlayamayınca ASR prompt'undaki ipucu listesini aynen geri okuyabiliyor."""
    words = re.findall(r"\w+", text.lower())
    hint_words = {w for h in hints for w in re.findall(r"\w+", h.lower())}
    return bool(words) and len(words) >= 3 and sum(w in hint_words for w in words) / len(words) >= 0.8


def looks_out_of_role(text: str, customer_name: str) -> bool:
    first = customer_name.split()[0]
    third_person = re.search(rf"{re.escape(first)}[^\s]*\s*(hanım|bey)?['’](ın|in|un|ün|nın|nin)\b", text, re.I)
    return bool(_META.search(text) or third_person or "\n\n" in text.strip() or len(text) > MAX_REPLY_CHARS)


def _synthesize_turn(settings: Settings, turn: Turn) -> None:
    rel = Path("sessions") / turn.session_id / turn.id
    res = tts.synthesize(settings, turn.text or "", _media(settings, rel))
    if res is not None:
        turn.audio_path = str(rel.with_suffix(res.path.suffix))
        turn.audio_mime, turn.duration_ms = res.mime, res.duration_ms
    turn.status = "ready"


def process_opening(db: Session, job: Job, settings: Settings, model: ModelClient) -> dict:
    turn = db.get(Turn, job.turn_id)
    _stage(db, job, "synthesizing")
    _synthesize_turn(settings, turn)
    return {"kind": "opening", "customer_turn": schemas.turn_json(turn)}


def process_turn(db: Session, job: Job, settings: Settings, model: ModelClient) -> dict:
    turn = db.get(Turn, job.turn_id)
    s = db.get(PracticeSession, job.session_id)
    t = db.get(Training, s.training_id)
    state = dict(job.state or {})

    if "asr_text" not in state and turn.text and not turn.audio_path:
        state["asr_text"] = turn.text
        job.state = dict(state)
        db.commit()

    if "asr_text" not in state:
        _stage(db, job, "transcribing")
        wav = _media(settings, Path(turn.audio_path).parent / f"{turn.id}.16k.wav").read_bytes()
        hints = t.scenario.get("asr_hints", [])
        text = model.transcribe(wav, prompts.asr_prompt(hints)).strip()
        if not text or is_hint_echo(text, hints):
            raise JobFailed("no_speech", "Konuşmanız anlaşılamadı. Lütfen tekrar kaydedin.", False)
        state["asr_text"] = text
        turn.text = text
        job.state = dict(state)
        db.commit()

    if "reply_text" not in state:
        _stage(db, job, "generating")
        history = [(x.speaker, x.text) for x in _ready_history(db, s.id, turn.index)]
        adaptive = ""
        if s.practice_mode == "adaptive":
            adaptive = prompts.adaptive_instructions(t.rubric, s.practice_focus or [])
        messages = prompts.customer_messages(t.scenario, t.policies, [*history, ("employee", turn.text)], adaptive)
        stub_ctx = {"scenario": t.scenario, "employee_text": turn.text or "", "history": history}
        reply, ended = clean_reply(model.chat(
            messages, max_new_tokens=120, temperature=1.0, purpose="customer_reply", stub_context=stub_ctx))
        if not reply or looks_out_of_role(reply, t.scenario["customer"]["name"]):
            log.warning("müşteri cevabı rol dışı, tekrar üretiliyor: %r", reply[:120])
            state["out_of_role"] = [reply]
            retry = [{**messages[0], "content": messages[0]["content"] + "\n\n" + prompts.ROLE_REMINDER}, *messages[1:]]
            reply, ended = clean_reply(model.chat(
                retry, max_new_tokens=120, temperature=1.0, purpose="customer_reply", stub_context=stub_ctx))
            if not reply or looks_out_of_role(reply, t.scenario["customer"]["name"]):
                state["out_of_role"].append(reply)
                reply, ended = FALLBACK_REPLY, False  # sabit, rolde kalan cümle; job.state'te iz bırakır
        state.update(reply_text=reply, customer_ended=ended)
        job.state = dict(state)
        db.commit()

    _stage(db, job, "synthesizing")
    customer = db.get(Turn, state["customer_turn_id"]) if "customer_turn_id" in state else None
    if customer is None:
        customer = Turn(session_id=s.id, index=turn.index + 1, speaker="customer", text=state["reply_text"])
        db.add(customer)
        db.flush()
        state["customer_turn_id"] = customer.id
        job.state = dict(state)
        db.commit()
    customer.status = "processing"
    # Yazılı çalışan cevabı da yönetici tarafından tur bazında dinlenebilir.
    # Yüklenen özgün ses varsa onu koruruz.
    if turn.text and not turn.audio_path:
        _synthesize_turn(settings, turn)
    _synthesize_turn(settings, customer)
    turn.status = "ready"
    db.flush()

    done = db.query(Turn).filter_by(session_id=s.id, speaker="employee", status="ready").count()
    return {
        "kind": "turn",
        "employee_turn": schemas.turn_json(turn),
        "customer_turn": schemas.turn_json(customer),
        "session_should_end": (bool(state.get("customer_ended")) and done >= MIN_TURNS_BEFORE_END)
        or done >= t.max_turns,
    }


def process_evaluation(db: Session, job: Job, settings: Settings, model: ModelClient) -> dict:
    s = db.get(PracticeSession, job.session_id)
    t = db.get(Training, s.training_id)
    ev = db.get(Evaluation, s.id)
    _stage(db, job, "evaluating")

    turns = (db.query(Turn).filter(Turn.session_id == s.id, Turn.status == "ready", Turn.text.is_not(None))
             .order_by(Turn.index).all())
    by_label = {f"t{x.index}": evalsvc.LabeledTurn(x.id, x.speaker, x.text) for x in turns}
    labeled = [(f"t{x.index}", x.speaker, x.text) for x in turns]
    dim_ids = [d["id"] for d in t.rubric["dimensions"]]
    stub_ctx = {"dimension_ids": dim_ids,
                "employee_turns": [(f"t{x.index}", x.text) for x in turns if x.speaker == "employee"]}

    messages = prompts.evaluation_messages(t.scenario, t.policies, t.rubric, labeled, s.practice_focus or [])
    raw = model.chat(messages, max_new_tokens=1400, temperature=settings.eval_temperature,
                     purpose="evaluation", stub_context=stub_ctx)
    repaired = False
    try:
        data = evalsvc.parse_json_output(raw)
        evalsvc.check_shape(data, dim_ids)
    except evalsvc.EvaluationShapeError as first:
        repaired = True  # yalnızca bir onarım denemesi
        raw = model.chat(prompts.repair_messages(raw, str(first)), max_new_tokens=1400, temperature=0.2,
                         purpose="evaluation_repair", stub_context=stub_ctx)
        try:
            data = evalsvc.parse_json_output(raw)
            evalsvc.check_shape(data, dim_ids)
        except evalsvc.EvaluationShapeError as second:
            log.warning("değerlendirme şeması onarılamadı: %s", second)
            raise JobFailed("internal_error", "Değerlendirme üretilemedi. Tekrar deneyebilirsiniz.", True) from second

    model_run = {"model": model.model_name, "runtime": model.runtime, "prompt_version": prompts.EVALUATOR_VERSION,
                 "generated_at": iso(utcnow()), "repaired": repaired}
    report, status = evalsvc.build_report(
        data, rubric=t.rubric, rubric_version=t.rubric_version, policies=t.policies, turns_by_label=by_label,
        model_run=model_run, employee_turn_count=sum(1 for x in turns if x.speaker == "employee"),
        focus_ids=s.practice_focus or [])
    ev.report, ev.status, ev.error = report, status, None
    return {"kind": "evaluation", "session_id": s.id, "evaluation_status": status}


def process_draft(db: Session, job: Job, settings: Settings, model: ModelClient) -> dict:
    draft = db.get(TrainingDraft, job.state["draft_id"])
    _stage(db, job, "generating")
    policies = draftsvc.form_policies(draft.form)
    ctx = {"form": draft.form, "policies": policies}
    requested = draft.form["scenario_count"]

    def parse(text: str):
        # Biçim onarımı (anahtar, seviye, sızan kimlik, fazla senaryo) kodda; eksik senaryo ise modelden
        # bir kez daha istenir (onarım çağrısı), çünkü eksik senaryoyu kod tamamlayamaz.
        fixed, notes = draftsvc.repair_generated(evalsvc.parse_json_output(text), policies, requested)
        part = draftsvc.GeneratedPart.model_validate(fixed)
        if len(part.scenarios) < requested:
            raise evalsvc.EvaluationShapeError(
                f"scenarios: Tam olarak {requested} senaryo üretmelisin; "
                f"{len(part.scenarios)} senaryo üretildi. Eksik senaryoları tamamla.")
        return part, notes

    raw = model.chat(prompts.draft_messages(draft.form, policies), max_new_tokens=2000, temperature=1.0,
                     purpose="draft", stub_context=ctx)
    try:
        part, notes = parse(raw)
    except (evalsvc.EvaluationShapeError, draftsvc.ValidationError) as first:
        problem = draftsvc.validation_problem(first) if isinstance(first, draftsvc.ValidationError) else str(first)
        raw = model.chat(prompts.repair_messages(raw, problem), max_new_tokens=2000, temperature=0.2,
                         purpose="draft_repair", stub_context=ctx)
        try:
            part, notes = parse(raw)
        except (evalsvc.EvaluationShapeError, draftsvc.ValidationError) as second:
            log.warning("taslak şeması onarılamadı: %s", second)
            raise JobFailed("internal_error", "Taslak üretilemedi. Tekrar deneyebilirsiniz.", True) from second
    content = {"scenarios": [s.model_dump() for s in part.scenarios], "policies": policies,
               "rubric": part.rubric.model_dump()}
    draft.content, draft.status = content, "ready"
    draft.warnings = notes + draftsvc.warnings_for(content)
    return {"kind": "draft_generation", "draft_id": draft.id}


HANDLERS = {"opening": process_opening, "turn": process_turn, "evaluation": process_evaluation,
            "draft_generation": process_draft}
FIRST_STAGE = {"opening": "synthesizing", "turn": "transcribing", "evaluation": "evaluating",
               "draft_generation": "generating"}


def _fail(db: Session, job: Job, exc: JobFailed) -> None:
    failed_stage = job.status if job.status not in ("queued", "ready", "error") else None
    job.status = "error"
    job.error = {"code": exc.code, "message": exc.message, "retryable": exc.retryable, "failed_stage": failed_stage}
    if job.turn_id:
        db.query(Turn).filter(Turn.id == job.turn_id).update({"status": "error"})
    if job.kind == "turn" and "customer_turn_id" in (job.state or {}):
        db.query(Turn).filter(Turn.id == job.state["customer_turn_id"]).update({"status": "error"})
    if job.kind == "evaluation":
        ev = db.get(Evaluation, job.session_id)
        ev.status, ev.error = "error", job.error
    if job.kind == "draft_generation":
        db.get(TrainingDraft, job.state["draft_id"]).status = "error"
    db.commit()


def run_job(db: Session, job: Job, settings: Settings, model: ModelClient) -> None:
    try:
        job.result = HANDLERS[job.kind](db, job, settings, model)
        job.status = "ready"
        db.commit()
    except JobFailed as exc:
        db.rollback()
        _fail(db, db.get(Job, job.id), exc)
    except ModelUnavailable as exc:
        db.rollback()
        log.warning("model servisine ulaşılamadı: %s", exc)
        _fail(db, db.get(Job, job.id), JobFailed(
            "model_unavailable", "Model şu an yanıt veremiyor. Kaydınız saklandı, tekrar deneyebilirsiniz.", True))
    except tts.TtsError as exc:
        db.rollback()
        log.warning("TTS hatası: %s", exc)
        _fail(db, db.get(Job, job.id), JobFailed("internal_error", "Müşteri sesi üretilemedi. Tekrar deneyin.", True))
    except Exception:
        db.rollback()
        log.exception("iş başarısız: %s", job.id)
        _fail(db, db.get(Job, job.id), JobFailed("internal_error", "Beklenmeyen bir hata oluştu.", True))


def first_stage(db: Session, job: Job) -> str:
    """Yazılı turda (ses yok) veya ASR'si önceden bitmiş tekrar denemede `transcribing` gösterilmez."""
    if job.kind == "turn":
        turn = db.get(Turn, job.turn_id)
        if "asr_text" in (job.state or {}) or (turn is not None and turn.audio_path is None):
            return "generating"
    return FIRST_STAGE[job.kind]


def claim_next(db: Session) -> Job | None:
    job = (db.query(Job).filter(Job.status == "queued", Job.kind.in_(HANDLERS))
           .order_by(Job.priority, Job.id).first())
    if job is None:
        return None
    # Koşullu güncelleme: başka bir süreç aynı işi aldıysa satır sayısı 0 olur.
    claimed = db.execute(update(Job).where(Job.id == job.id, Job.status == "queued")
                         .values(status=first_stage(db, job), updated_at=utcnow())).rowcount
    db.commit()
    if not claimed:
        return None
    db.refresh(job)
    return job


def recover_stale(db: Session) -> int:
    """Worker çökmüşse yarıda kalan işleri tekrar kuyruğa alır; ara sonuçlar korunur."""
    n = db.query(Job).filter(Job.status.in_(schemas.ACTIVE_JOB_STATES[1:])).update(
        {"status": "queued"}, synchronize_session=False)
    db.commit()
    return n


def run_once(settings: Settings | None = None, model: ModelClient | None = None) -> bool:
    settings = settings or get_settings()
    model = model or get_model_client(settings)
    with get_sessionmaker()() as db:
        job = claim_next(db)
        if job is None:
            return False
        log.info("iş başladı %s %s", job.kind, job.id)
        run_job(db, job, settings, model)
        log.info("iş bitti %s %s -> %s", job.kind, job.id, job.status)
        return True


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = get_settings()
    model = get_model_client(settings)
    with get_sessionmaker()() as db:
        if n := recover_stale(db):
            log.info("%d yarım iş kuyruğa geri alındı", n)
    log.info("worker başladı (model=%s, tts=%s)", settings.model_mode, settings.tts_provider)
    while True:
        if not run_once(settings, model):
            time.sleep(settings.worker_poll_s)
