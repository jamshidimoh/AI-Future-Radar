import json
import os
import signal
import subprocess
import sys
from pathlib import Path

import src.dedup as dedup
from src.semantic_dedup import encode_story_signature


def _item(title, link, summary="A story summary", why="Why it matters"):
    return {"title": title, "summary": summary, "why_it_matters": why, "link": link, "source": "Example Source", "content_type": "news", "category": "ai"}


def _isolated_state(tmp_path, monkeypatch):
    state = tmp_path / "seen.json"
    feedback = tmp_path / "telegram_feedback.json"
    feedback.write_text(json.dumps({"messages": {}}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(dedup, "STATE_FILE", str(state)); monkeypatch.setattr(dedup, "FEEDBACK_FILE", str(feedback))
    return state, feedback


def test_rewritten_story_from_previous_run_is_blocked(tmp_path, monkeypatch):
    state, _ = _isolated_state(tmp_path, monkeypatch)
    published = _item("Andrew Ng launches a major new AI education initiative", "https://example.com/run-337-story", "Andrew Ng announces a new initiative focused on practical AI education and skills.", "The initiative could broaden access to AI education.")
    rewritten = _item("Andrew Ng unveils a new major initiative for practical AI learning", "https://another.example.com/rewrite-of-the-same-story", "A new Andrew Ng initiative expands practical education and skills for AI learners.", "The project could expand access to practical AI training.")
    state.write_text(json.dumps({"seen_hashes":[dedup._hash_link(published["link"])],"seen_signatures":[encode_story_signature(published)],"source_history":[]},ensure_ascii=False),encoding="utf-8")
    seen_hashes,_=dedup.load_seen(); assert dedup.filter_new_items([rewritten],seen_hashes)==[]


def test_education_without_url_survives_story_dedup(tmp_path, monkeypatch):
    state, _ = _isolated_state(tmp_path, monkeypatch)
    education = {"content_type": "education", "education_id": 31, "category": "ai", "title": "Validation و Generalization"}
    seen_hashes, _ = dedup.load_seen()
    assert dedup.filter_new_items([education], seen_hashes) == [education]

    seen_hashes, seen_signatures = dedup.load_seen()
    dedup.mark_as_seen(education, seen_hashes, seen_signatures, [])
    dedup.save_seen(seen_hashes, seen_signatures, [])
    restarted_hashes, _ = dedup.load_seen()
    assert dedup.filter_new_items([education], restarted_hashes) == []


def test_same_run_semantic_duplicate_is_blocked(tmp_path, monkeypatch):
    state,_=_isolated_state(tmp_path,monkeypatch); state.write_text(json.dumps({"seen_hashes":[],"seen_signatures":[],"source_history":[]}),encoding="utf-8")
    first=_item("MIT CSAIL researchers introduce a new AI model for physical-world interaction","https://example.com/first","Researchers at MIT CSAIL present a model designed to improve interaction with the physical world.","The work may improve AI systems operating outside purely digital environments.")
    second=_item("MIT CSAIL unveils a model that improves AI interaction with the physical world","https://example.com/second","MIT CSAIL researchers present a new model for physical-world interaction.","The model targets AI systems that operate in physical environments.")
    seen_hashes,_=dedup.load_seen(); assert len(dedup.filter_new_items([first,second],seen_hashes))==1


def test_incremental_save_survives_actual_sigterm(tmp_path):
    state=tmp_path/"seen.json"; feedback=tmp_path/"telegram_feedback.json"; feedback.write_text(json.dumps({"messages":{}},ensure_ascii=False),encoding="utf-8")
    item=_item("چالش‌های هوش مصنوعی در تعامل با دنیای فیزیکی","https://example.com/physical-world-story","MIT CSAIL researchers study AI interaction with the physical world.","The work addresses physical-world interaction.")
    signature=encode_story_signature(item)
    script=f"""
import sys,time
sys.path.insert(0,{str(Path(__file__).resolve().parents[1])!r})
import src.dedup as dedup
dedup.STATE_FILE={str(state)!r}; dedup.FEEDBACK_FILE={str(feedback)!r}
dedup.save_seen({{'durable-test-hash'}},[{signature!r}],[{{'ts':1,'source':'test'}}])
print('STATE_DURABLE',flush=True); time.sleep(30)
"""
    process=subprocess.Popen([sys.executable,"-u","-c",script],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,env=os.environ.copy())
    try:
        line=process.stdout.readline().strip(); assert line=="STATE_DURABLE",line; process.send_signal(signal.SIGTERM); process.wait(timeout=5)
    finally:
        if process.poll() is None: process.kill(); process.wait(timeout=5)
    assert state.exists(); data=json.loads(state.read_text(encoding="utf-8")); assert data.get("seen_signatures")
    old_state,old_feedback=dedup.STATE_FILE,dedup.FEEDBACK_FILE; dedup.STATE_FILE,dedup.FEEDBACK_FILE=str(state),str(feedback)
    try:
        seen_hashes,_=dedup.load_seen(); duplicate=_item("چالش‌های هوش مصنوعی در تعامل با دنیای فیزیکی — نسخه جدید","https://another.example.com/rewrite"); assert dedup.filter_new_items([duplicate],seen_hashes)==[]
    finally: dedup.STATE_FILE,dedup.FEEDBACK_FILE=old_state,old_feedback


def test_publication_ledger_is_independent_of_telegram_deletion(tmp_path, monkeypatch):
    state,_=_isolated_state(tmp_path,monkeypatch); published=_item("چالش‌های هوش مصنوعی در تعامل با دنیای فیزیکی","https://example.com/published-story"); seen_hashes,seen_signatures=dedup.load_seen(); history=[]; dedup.mark_as_seen(published,seen_hashes,seen_signatures,history); dedup.save_seen(seen_hashes,seen_signatures,history); restarted_hashes,_=dedup.load_seen(); rewritten=_item("چالش‌های هوش مصنوعی در تعامل با دنیای فیزیکی — نسخه جدید","https://another.example.com/rewrite"); assert dedup.filter_new_items([rewritten],restarted_hashes)==[]


def test_telegram_feedback_reconciles_missing_seen_state(tmp_path, monkeypatch):
    state,feedback=_isolated_state(tmp_path,monkeypatch); published=_item("چالش‌های هوش مصنوعی در تعامل با دنیای فیزیکی","https://example.com/telegram-only"); feedback.write_text(json.dumps({"messages":{"-100:1":{"message_id":1,"title":published["title"],"link":published["link"],"source":"Example Source","content_type":"news","category":"ai"}}},ensure_ascii=False),encoding="utf-8"); seen_hashes,_=dedup.load_seen(); rewritten=_item("چالش‌های هوش مصنوعی در تعامل با دنیای فیزیکی دوباره بررسی شد","https://another.example.com/telegram-only-rewrite"); assert dedup.filter_new_items([rewritten],seen_hashes)==[]
