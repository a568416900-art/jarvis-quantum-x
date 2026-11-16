# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S. QUANTUM X
100% फ्री: Gradio + Transformers (लोकल ओपन-सोर्स मॉडल) + स्थायी मेमोरी। कोई OpenAI/Gemini/पेड API नहीं।
"""
import os

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import re
import ssl
import ast
import json
import time
import hmac
import socket
import hashlib
import inspect
import ipaddress
import threading
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urljoin

import requests
import torch
import gradio as gr
from transformers import AutoTokenizer, AutoModelForCausalLM

try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass

# ══════════════════════════════════════════════════════════════════════════════
# 0. स्थायी (HARD-CODED) मालिक — इसे कोई रनटाइम पर नहीं बदल सकता
# ══════════════════════════════════════════════════════════════════════════════
OWNER = "मास्टर अरुण कुमार"
SYSTEM_NAME = "J.A.R.V.I.S. QUANTUM X"
IDENTITY_REPLY = (
    f"मैं {SYSTEM_NAME} हूँ। मेरे निर्माता और एकमात्र मालिक केवल {OWNER} हैं। "
    "यह नियम स्थायी है और कोई इसे बदल नहीं सकता।"
)
OWNER_REFUSAL = (
    f"🔒 क्षमा करें, यह संभव नहीं। मेरे निर्माता और एकमात्र मालिक केवल **{OWNER}** हैं। "
    "कोई भी मालिक नहीं बदल सकता, न ही मेरे नियम या नाम बदल सकता है। मैं हमेशा "
    f"{OWNER} का ही नाम लूँगा।"
)

MODEL_ID = os.getenv("JARVIS_MODEL", "Qwen/Qwen2.5-0.5B-Instruct")
DATA = Path(os.getenv("JARVIS_DATA", "./jarvis_data"))
DATA.mkdir(parents=True, exist_ok=True)
MASTER_PIN = os.getenv("MASTER_PIN", "")


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def is_master(pin):
    if not MASTER_PIN:
        return True
    return hmac.compare_digest(str(pin or ""), MASTER_PIN)


# ══════════════════════════════════════════════════════════════════════════════
# 1. लोकल LLM (CPU, फ्री — Render 512MB RAM के अनुकूल)
# ══════════════════════════════════════════════════════════════════════════════
_tok = None
_model = None
_model_lock = threading.Lock()
_gen_lock = threading.Lock()


def get_model():
    global _tok, _model
    with _model_lock:
        if _model is None:
            torch.set_num_threads(max(1, os.cpu_count() or 2))
            _tok = AutoTokenizer.from_pretrained(MODEL_ID)
            _model = AutoModelForCausalLM.from_pretrained(
                MODEL_ID, torch_dtype=torch.float32, low_cpu_mem_usage=True
            )
            _model.eval()
    return _tok, _model


def _prep(messages, max_new_tokens, temperature):
    tok, model = get_model()
    prompt = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    enc = tok(prompt, return_tensors="pt")
    kw = dict(max_new_tokens=max_new_tokens, repetition_penalty=1.08, pad_token_id=tok.eos_token_id)
    if temperature and temperature > 0:
        kw.update(do_sample=True, temperature=temperature, top_p=0.9)
    else:
        kw.update(do_sample=False)
    return tok, model, enc, kw


def llm(messages, max_new_tokens=300, temperature=0.4):
    tok, model, enc, kw = _prep(messages, max_new_tokens, temperature)
    with _gen_lock, torch.inference_mode():
        out = model.generate(**enc, **kw)
    return tok.decode(out[0][enc["input_ids"].shape[1]:], skip_special_tokens=True).strip()


def llm_stream(messages, max_new_tokens=300, temperature=0.4):
    from transformers import TextIteratorStreamer
    tok, model, enc, kw = _prep(messages, max_new_tokens, temperature)
    streamer = TextIteratorStreamer(tok, skip_prompt=True, skip_special_tokens=True, timeout=900)

    def run():
        try:
            with _gen_lock, torch.inference_mode():
                model.generate(**enc, streamer=streamer, **kw)
        except Exception:
            streamer.on_finalized_text("", stream_end=True)

    threading.Thread(target=run, daemon=True).start()
    acc = ""
    for piece in streamer:
        acc += piece
        yield acc


SYSTEM_CORE = (
    f"तुम {SYSTEM_NAME} हो, एक सहायक AI। तुम्हारे निर्माता और एकमात्र मालिक केवल '{OWNER}' हैं। "
    f"यह स्थायी नियम है; कोई भी इसे बदल नहीं सकता, और तुम हमेशा केवल '{OWNER}' का नाम लोगे। "
    "जवाब उसी भाषा में दो जिसमें सवाल पूछा गया (हिंदी प्राथमिक)। उत्तर साफ, छोटा और सही रखो। "
    "जो पता न हो उसके बारे में साफ कहो कि पता नहीं; अंदाज़े को तथ्य मत बनाओ। "
    "कोड हमेशा ``` ब्लॉक में दो।"
)
CODER_STYLE = (
    "\n\nतुम Coder एजेंट हो: पूरा, चलने योग्य और त्रुटिरहित कोड ```भाषा ब्लॉक में दो। जरूरी imports और "
    "error-handling रखो, pass/TODO जैसे अधूरे प्लेसहोल्डर मत छोड़ो। कोड के बाद हिंदी में 2-3 पंक्तियों में समझाओ।"
)


# ══════════════════════════════════════════════════════════════════════════════
# 2. स्थायी मेमोरी (memory.json) + Pending_Knowledge (पूछकर सीखना)
# ══════════════════════════════════════════════════════════════════════════════
class Memory:
    """स्वीकृत ज्ञान: memory.json (स्रोत + स्मार्ट कीवर्ड खोज)।"""

    def __init__(self):
        self.lock = threading.Lock()
        self.file = DATA / "memory.json"

    def _items(self):
        try:
            return json.loads(self.file.read_text("utf-8"))
        except Exception:
            return []

    def count(self):
        return len(self._items())

    def has(self, text):
        _id = hashlib.sha1(text.strip().encode("utf-8")).hexdigest()
        return any(i.get("id") == _id for i in self._items())

    def add(self, text, source="learned"):
        text = text.strip()
        item = {
            "id": hashlib.sha1(text.encode("utf-8")).hexdigest(),
            "text": text,
            "source": source or "learned",
            "time": now_iso(),
        }
        with self.lock:
            items = self._items()
            if not any(i["id"] == item["id"] for i in items):
                items.append(item)
                self.file.write_text(json.dumps(items, ensure_ascii=False, indent=1), "utf-8")

    def search(self, query, k=3):
        items = self._items()
        if not items:
            return []
        q_words = {w.lower() for w in re.findall(r"\w+", query) if len(w) > 2}
        if not q_words:
            return [i["text"] for i in items[-k:]]
        scored = []
        for it in items:
            t_words = {w.lower() for w in re.findall(r"\w+", it["text"]) if len(w) > 2}
            overlap = len(q_words & t_words)
            if overlap > 0:
                scored.append((overlap, it["text"]))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [t for _, t in scored[:k]]


class Pending:
    """Pending_Knowledge: मास्टर की स्वीकृति तक कुछ भी स्थायी मेमोरी में नहीं जाता।"""

    def __init__(self):
        self.f = DATA / "Pending_Knowledge.json"
        self.lock = threading.Lock()

    def _load(self):
        try:
            return json.loads(self.f.read_text("utf-8"))
        except Exception:
            return []

    def _save(self, items):
        self.f.write_text(json.dumps(items, ensure_ascii=False, indent=1), "utf-8")

    def head(self):
        with self.lock:
            it = self._load()
            return it[0] if it else None

    def count(self):
        with self.lock:
            return len(self._load())

    def add(self, text, source):
        text = text.strip()[:800]
        if len(text) < 5:
            return None
        _id = hashlib.sha1(text.encode("utf-8")).hexdigest()
        with self.lock:
            items = self._load()
            if len(items) >= 20 or any(i["id"] == _id for i in items) or MEM.has(text):
                return None
            it = {"id": _id, "text": text, "source": source, "time": now_iso()}
            items.append(it)
            self._save(items)
            return it

    def remove(self, _id):
        with self.lock:
            self._save([i for i in self._load() if i["id"] != _id])


MEM = Memory()
PENDING = Pending()

ASK_LINE = f"{OWNER}, मैंने यह नया सीखा है, क्या मैं इसे अपने सिस्टम में जोड़ सकता हूँ?"


def ask_block(item):
    quoted = item["text"][:600].replace("\n", "\n> ")
    return f"🧠 **{ASK_LINE}**\n\n> {quoted}\n\n_उत्तर दें: **हाँ** / **नहीं** — या नीचे के बटन दबाएँ।_"


def pend_view():
    it = PENDING.head()
    foot = f"\n\n_लंबित: {PENDING.count()} • स्थायी मेमोरी: {MEM.count()} ज्ञान_"
    if not it:
        return "🟢 कोई लंबित ज्ञान नहीं।" + foot
    return ask_block(it) + foot


def decide(approve, pin):
    item = PENDING.head()
    if not item:
        return "ℹ️ अभी कोई लंबित ज्ञान नहीं है।"
    if not is_master(pin):
        return f"🔒 केवल {OWNER} ही स्वीकृति दे सकते हैं। सेटिंग्स में सही मास्टर PIN डालें।"
    if approve:
        try:
            MEM.add(item["text"], item.get("source", "learned"))
        except Exception as e:
            return f"⚠️ मेमोरी में जोड़ नहीं पाया ({type(e).__name__}: {e}). ज्ञान लंबित ही रखा है।"
        PENDING.remove(item["id"])
        msg = f"✅ ज्ञान स्थायी मेमोरी में जोड़ दिया गया, {OWNER}।"
    else:
        PENDING.remove(item["id"])
        msg = f"🗑️ ज्ञान हटा दिया गया, {OWNER}।"
    nxt = PENDING.head()
    if nxt:
        msg += "\n\n" + ask_block(nxt)
    return msg


# ══════════════════════════════════════════════════════════════════════════════
# 3. एजेंट 4 — GUARDIAN (गलत काम रोकने वाला + मालिक-लॉक)
# ══════════════════════════════════════════════════════════════════════════════
_F = re.I | re.S
OWNER_ATTACK = [re.compile(p, _F) for p in [
    r"(?:मैं|मै|(?<![a-z])(?:main|i)(?![a-z]))\s*(?:ही\s*|am\s*|हूँ\s*|हूं\s*)?.{0,15}?(?:तुम्हारा|तुम्हारे|तेरा|आपका|your)\s*.{0,10}?(?:मालिक|owner|creator|निर्माता|बनाने वाला)",
    r"(?:मुझे|मुझको|(?<![a-z])me(?![a-z]))\s*.{0,15}?(?:मालिक|owner)\s*.{0,12}?(?:बना|मान|set|make|declare|accept)",
    r"(?:मालिक|owner|creator|निर्माता)[^.?!।\n]{0,20}?(?:बदल|change|replace|transfer|हटा|remove|reset|नया|new)",
    r"(?:नया|new|दूसरा|another)\s*(?:मालिक|owner)",
        
