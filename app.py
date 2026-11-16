# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S. QUANTUM X
100% फ्री: Gradio + Transformers (लोकल ओपन-सोर्स मॉडल) + ChromaDB. कोई OpenAI/Gemini/पेड API नहीं, कोई Docker नहीं।
Hugging Face Spaces (SDK: Gradio) पर Port 7860 पर चलता है।
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

MODEL_ID = os.getenv("JARVIS_MODEL", "Qwen/Qwen2.5-1.5B-Instruct")
EMB_MODEL = os.getenv("JARVIS_EMB", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
DATA = Path(os.getenv("JARVIS_DATA", "./jarvis_data"))
DATA.mkdir(parents=True, exist_ok=True)
MASTER_PIN = os.getenv("MASTER_PIN", "")  # Space Secret (वैकल्पिक): सेट होने पर ही स्वीकृति संभव


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def is_master(pin):
    if not MASTER_PIN:
        return True
    return hmac.compare_digest(str(pin or ""), MASTER_PIN)


# ══════════════════════════════════════════════════════════════════════════════
# 1. लोकल LLM (CPU, फ्री)
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
# 2. स्थायी मेमोरी (ChromaDB) + Pending_Knowledge (पूछकर सीखना)
# ══════════════════════════════════════════════════════════════════════════════


def _hub_cfg():
    return os.getenv("JARVIS_MEMORY_REPO"), os.getenv("HF_TOKEN")


def hub_pull():
    repo, tok = _hub_cfg()
    if not repo or not tok:
        return
    try:
        from huggingface_hub import hf_hub_download
        hf_hub_download(repo_id=repo, filename="memory.json", repo_type="dataset",
                        token=tok, local_dir=str(DATA))
    except Exception as e:
        print("[memory] hub pull skipped:", e)


def hub_push():
    repo, tok = _hub_cfg()
    if not repo or not tok:
        return
    try:
        from huggingface_hub import HfApi
        api = HfApi(token=tok)
        api.create_repo(repo, repo_type="dataset", private=True, exist_ok=True)
        api.upload_file(path_or_fileobj=str(DATA / "memory.json"), path_in_repo="memory.json",
                        repo_id=repo, repo_type="dataset")
    except Exception as e:
        print("[memory] hub push failed:", e)


class Memory:
    """स्वीकृत ज्ञान: memory.json (स्रोत) + ChromaDB (सिमैंटिक खोज)।"""

    def __init__(self):
        self.lock = threading.Lock()
        self.file = DATA / "memory.json"
        self.col = None
        self.ready = False
        self.failed = False

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

    def init(self):
        with self.lock:
            if self.ready:
                return
            hub_pull()
            import chromadb
            from chromadb.utils import embedding_functions
            client = chromadb.PersistentClient(path=str(DATA / "chroma"))
            ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMB_MODEL)
            self.col = client.get_or_create_collection(
                "jarvis_memory", embedding_function=ef, metadata={"hnsw:space": "cosine"})
            items = self._items()
            if items:
                self.col.upsert(ids=[i["id"] for i in items], documents=[i["text"] for i in items],
                                metadatas=[{"source": i.get("source") or "learned"} for i in items])
            self.ready = True

    def add(self, text, source="learned"):
        text = text.strip()
        self.init()
        item = {"id": hashlib.sha1(text.encode("utf-8")).hexdigest(), "text": text,
                "source": source or "learned", "time": now_iso()}
        with self.lock:
            items = self._items()
            if not any(i["id"] == item["id"] for i in items):
                items.append(item)
                self.file.write_text(json.dumps(items, ensure_ascii=False, indent=1), "utf-8")
        self.col.upsert(ids=[item["id"]], documents=[text], metadatas=[{"source": item["source"]}])
        threading.Thread(target=hub_push, daemon=True).start()

    def search(self, query, k=3, max_dist=0.55):
        if self.failed:
            return []
        try:
            self.init()
            n = self.col.count()
            if n == 0:
                return []
            res = self.col.query(query_texts=[query], n_results=min(k, n))
            return [d for d, dist in zip(res["documents"][0], res["distances"][0]) if dist <= max_dist]
        except Exception as e:
            print("[memory] search disabled:", e)
            self.failed = True
            return []


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
    r"(?:अरुण|arun)[^.?!।\n]{0,30}?(?:मालिक|owner|creator|निर्माता)[^.?!।\n]{0,25}?(?:नहीं|not|fake|झूठ|हटा|remove|forget|भूल)",
    r"(?:नाम|name)\s*(?:को\s*)?(?:बदल|change|rename)|(?<![a-z])rename(?![a-z])|change\s+(?:your|the|owner)\w*\s+name",
    r"ignore\s+(?:all\s+|any\s+|the\s+|your\s+)?(?:previous\s+|prior\s+|above\s+)?(?:instructions|rules)|system\s*prompt|jailbreak|developer\s*mode|dan\s*mode|(?:पिछले|सभी|सारे|अपने)\s*(?:निर्देश|नियम)\s*(?:भूल|छोड़|ignore)",
]]
IDENTITY_Q = [re.compile(p, _F) for p in [
    r"(?:तुम्हारा|तेरा|आपका|your)\s*(?:मालिक|owner|creator|निर्माता|बनाने वाला|master)",
    r"(?:मालिक|owner|creator|निर्माता)\s*(?:कौन|who)",
    r"(?:किसने|who)\s*.{0,15}?(?:बनाया|made|created|built|develop)",
    r"(?:तुम|आप)\s*कौन\s*(?:हो|हैं)|who\s+are\s+you",
]]
HARM = re.compile(
    r"ransomware|रैनसमवेयर|keylogger|कीलॉगर|botnet|ddos|डीडॉस|phishing\s*(?:page|site|kit|link)|फ़िशिंग|फिशिंग|"
    r"credential\s*(?:steal|harvest)|info\s*stealer|reverse\s*shell|malware\s*(?:बना|लिख|write|create|make)|"
    r"मालवेयर\s*(?:बना|लिख)|virus\s*(?:बना|लिख|write|create|make)|वायरस\s*(?:बना|लिख)|"
    r"(?:किसी|दूसरे|उसका|उसकी)\s*(?:का|की)?\s*(?:अकाउंट|account|पासवर्ड|password|wifi|वाईफाई)\s*(?:हैक|hack|crack|चुरा|steal)|"
    r"hack\s+(?:someone|his|her|their|into)|हैक\s*कर(?:ो|ना|ने)|साइट\s*हैक|बम\s*बना|bomb\s*making|हथियार\s*बना|"
    r"exploit\s*(?:for|against)\s*(?:this\s*)?(?:site|website|server)|sql\s*injection\s*(?:payload|attack)\s*(?:on|against|for)",
    _F)
DANGEROUS_CODE = [
    (re.compile(r"rm\s+-rf\s+/|shutil\.rmtree\(\s*['\"]/['\"]"), "सिस्टम मिटाने वाला कमांड"),
    (re.compile(r"os\.system\(|subprocess\.[a-z_]+\([^)]*shell\s*=\s*True"), "शेल कमांड — यूज़र-इनपुट कभी सीधे न जोड़ें"),
    (re.compile(r"\beval\(|\bexec\("), "eval/exec का उपयोग जोखिम भरा है"),
    (re.compile(r"pickle\.loads?\("), "अविश्वसनीय डेटा पर pickle असुरक्षित है"),
    (re.compile(r"verify\s*=\s*False"), "SSL सत्यापन बंद किया गया है"),
    (re.compile(r"(?:password|api[_-]?key|secret|token)\s*=\s*['\"][^'\"]{6,}['\"]", re.I), "कोड में हार्ड-कोडेड सीक्रेट"),
]
RANSOM_LIKE = re.compile(r"(?:Fernet|AES).{0,400}?(?:os\.walk|glob).{0,400}?(?:os\.remove|unlink)", re.S)


class Guardian:
    name = "🛡️ Guardian"

    def check_input(self, text):
        for rx in OWNER_ATTACK:
            if rx.search(text):
                return True, OWNER_REFUSAL
        if HARM.search(text):
            return True, ("🛡️ यह अनुरोध किसी को नुकसान पहुँचा सकता है, इसलिए मैं इसमें मदद नहीं करूँगा। "
                          "अगर आपकी अपनी वेबसाइट की सुरक्षा जाँचनी है तो 'Ethical Security Auditor' टैब से "
                          "अनुमति-सहित निष्क्रिय जाँच करवा सकते हैं, और बचाव के उपाय पूछ सकते हैं।")
        return False, ""

    def identity(self, text):
        return IDENTITY_REPLY if any(rx.search(text) for rx in IDENTITY_Q) else ""

    def check_output(self, ans):
        notes = []
        if RANSOM_LIKE.search(ans):
            return "🛡️ यह कोड फ़ाइलें एन्क्रिप्ट करके मिटाने जैसा व्यवहार करता है, इसलिए मैंने इसे रोक दिया।", ["रैनसमवेयर-जैसा कोड रोका"]
        if re.search(r"(?:मेरा|मेरे|my)\s*(?:एकमात्र\s*)?(?:मालिक|owner|creator|निर्माता|बनाने वाला)", ans, re.I) and "अरुण" not in ans:
            return IDENTITY_REPLY, ["मालिक-सुधार लागू"]
        warns = [msg for rx, msg in DANGEROUS_CODE if rx.search(ans)]
        if warns:
            ans += "\n\n---\n🛡️ **Guardian चेतावनी:** " + "; ".join(warns) + "।"
            notes.append(f"{len(warns)} कोड-जोखिम चिह्नित")
        return ans, notes


GUARD = Guardian()

# ══════════════════════════════════════════════════════════════════════════════
# 4. एजेंट 5 — ETHICAL SECURITY AUDITOR (निष्क्रिय, अनुमति-आधारित जाँच)
#    केवल 1-3 सामान्य HTTP अनुरोध + TLS हैंडशेक। कोई हमला, पोर्ट-स्कैन, फज़िंग या एक्सप्लॉइट नहीं।
# ══════════════════════════════════════════════════════════════════════════════
UA = {"User-Agent": "JARVIS-QuantumX-PassiveAudit/1.0 (owner-authorised, non-intrusive)"}
_audit_lock = threading.Lock()
_last_audit = [0.0]

FIX = {
    "https": "पूरी साइट HTTPS पर चलाएँ (मुफ्त Let's Encrypt प्रमाणपत्र) और सभी HTTP अनुरोध HTTPS पर 301 रीडायरेक्ट करें।",
    "tls": "वैध, पूरी चेन वाला प्रमाणपत्र लगाएँ, डोमेन-नाम मिलाएँ और स्वतः-नवीनीकरण (certbot/ACME) चालू करें।",
    "tls_exp": "प्रमाणपत्र नवीनीकृत करें और ऑटो-रिन्यू सेट करें।",
    "hsts": "`Strict-Transport-Security: max-age=31536000; includeSubDomains` हेडर जोड़ें (पहले HTTPS पूरी तरह जाँच लें)।",
    "csp": "`Content-Security-Policy` शुरू करें; पहले `Content-Security-Policy-Report-Only` में परखें, फिर लागू करें। 'unsafe-inline' हटाने के लिए nonce/hash अपनाएँ।",
    "xfo": "`X-Frame-Options: DENY` (या CSP में `frame-ancestors 'self'`) जोड़ें ताकि क्लिकजैकिंग न हो।",
    "xcto": "`X-Content-Type-Options: nosniff` जोड़ें।",
    "ref": "`Referrer-Policy: strict-origin-when-cross-origin` जोड़ें।",
    "perm": "`Permissions-Policy` से कैमरा/माइक/लोकेशन जैसी अनावश्यक सुविधाएँ बंद करें।",
    "banner": "सर्वर/फ्रेमवर्क का संस्करण दिखाने वाले हेडर (Server, X-Powered-By) हटाएँ या छोटा करें।",
    "cors": "`Access-Control-Allow-Origin: *` के साथ credentials कभी न दें; केवल भरोसेमंद ओरिजिन की सूची रखें।",
    "cookie": "कुकी में `Secure; HttpOnly; SameSite=Lax` (या Strict) लगाएँ।",
    "mixed": "सभी स्क्रिप्ट/इमेज/iframe के लिंक `https://` करें; CSP में `upgrade-insecure-requests` जोड़ें।",
    "sri": "बाहरी स्क्रिप्ट पर `integrity` (SRI) और `crossorigin` गुण लगाएँ, या उन्हें खुद होस्ट करें।",
    "sectxt": "`/.well-known/security.txt` बनाएँ ताकि शोधकर्ता कमज़ोरी की सूचना दे सकें।",
}
SEV = {"HIGH": ("🔴", "उच्च", 20), "MED": ("🟠", "मध्यम", 10), "LOW": ("🟡", "निम्न", 4), "INFO": ("🔵", "सूचना", 0)}
BAD_TLD = {"py", "js", "html", "css", "txt", "md", "json", "exe", "png", "jpg", "pdf", "sh", "ts", "ini", "log", "yml", "yaml"}
URL_RE = re.compile(
    r"(https?://[^\s<>\"'”’)]+|(?<![@\w./-])(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}(?:/[^\s<>\"']*)?)", re.I)
AUDIT_KW = re.compile(
    r"स्कैन|scan|audit|ऑडिट|vulnerab|कमजोरी|कमज़ोरी|सुरक्षा\s*(?:जांच|जाँच|check)|security\s*(?:check|test|audit)|सिक्योरिटी",
    re.I)


def extract_url(text):
    for m in URL_RE.finditer(text):
        cand = m.group(0).rstrip(".,;:)")
        if cand.lower().startswith("http"):
            return cand
        host = cand.split("/")[0]
        if host.split(".")[-1].lower() not in BAD_TLD:
            return cand
    return ""


def _is_public(ip_str):
    ip = ipaddress.ip_address(ip_str)
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped:
        ip = mapped
    return ip.is_global and not ip.is_multicast


def _safe_resolve(host):
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise ValueError("डोमेन हल नहीं हुआ")
    ips = []
    for info in infos:
        ip = info[4][0].split("%")[0]
        if not _is_public(ip):
            raise ValueError("लक्ष्य निजी/आंतरिक नेटवर्क का है — अनुमति नहीं")
        ips.append(ip)
    if not ips:
        raise ValueError("कोई IP नहीं मिला")
    return sorted(set(ips), key=lambda x: ":" in x)


def _fetch(url, verify=True, hops=4):
    sess = requests.Session()
    chain = []
    for _ in range(hops + 1):
        pu = urlparse(url)
        if pu.scheme not in ("http", "https") or not pu.hostname:
            raise ValueError("अमान्य रीडायरेक्ट")
        if pu.port not in (None, 80, 443):
            raise ValueError("गैर-मानक पोर्ट पर रीडायरेक्ट — रोका गया")
        _safe_resolve(pu.hostname)
        r = sess.get(url, headers=UA, timeout=(5, 8), allow_redirects=False, stream=True, verify=verify)
        chain.append((url, r.status_code))
        loc = r.headers.get("Location")
        if r.status_code in (301, 302, 303, 307, 308) and loc:
            r.close()
            url = urljoin(url, loc)
            continue
        return r, chain
    raise ValueError("बहुत अधिक रीडायरेक्ट")


def _tls_info(host):
    ip = _safe_resolve(host)[0]
    ctx = ssl.create_default_context()
    with socket.create_connection((ip, 443), timeout=8) as s:
        with ctx.wrap_socket(s, server_hostname=host) as ss:
            cert = ss.getpeercert()
            ver = ss.version()
    days = int((ssl.cert_time_to_seconds(cert["notAfter"]) - time.time()) // 86400)
    issuer = dict(x[0] for x in cert.get("issuer", [])).get("organizationName", "?")
    return ver, days, issuer


def _bt(s, n=120):
    return str(s).replace("`", "'").replace("\n", " ")[:n]


def audit_site(raw_url, consent):
    if not consent:
        return ("⛔ **अनुमति पुष्टि ज़रूरी है।** सेटिंग्स में टिक करें कि यह साइट आपकी है या आपके पास जाँच की "
                "लिखित अनुमति है। बिना अनुमति किसी की वेबसाइट की जाँच नहीं की जाती।")
    url = (raw_url or "").strip()
    if not url:
        return "ℹ️ कृपया जाँचने के लिए वेबसाइट का लिंक दें।"
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    try:
        p = urlparse(url)
        port = p.port
    except ValueError:
        return "⛔ लिंक अमान्य है।"
    if p.scheme not in ("http", "https") or not p.hostname:
        return "⛔ केवल http/https लिंक मान्य हैं।"
    if port not in (None, 80, 443):
        return "⛔ केवल मानक पोर्ट (80/443) की जाँच की जाती है।"
    with _audit_lock:
        if time.time() - _last_audit[0] < 10:
            return "⏳ कृपया 10 सेकंड बाद दोबारा कोशिश करें (दुरुपयोग-रोकथाम)।"
        _last_audit[0] = time.time()

    host = p.hostname
    findings, good = [], []

    def add(sev, title, detail, fix):
        findings.append((sev, title, detail, fix))

    try:
        _safe_resolve(host)
    except Exception as e:
        return f"⛔ जाँच रोकी गई: {e}"

    verify_ok = True
    try:
        resp, chain = _fetch(url, True)
    except requests.exceptions.SSLError as e:
        verify_ok = False
        add("HIGH", "TLS प्रमाणपत्र अमान्य/अविश्वसनीय", _bt(e, 160), FIX["tls"])
        try:
            resp, chain = _fetch(url, False)
        except Exception as e2:
            return _render(host, url, None, findings, good, f"आगे की जाँच संभव नहीं: {_bt(e2)}")
    except Exception as e:
        return f"⛔ साइट तक पहुँच नहीं हो पाई: {_bt(e, 200)}"

    final_url = chain[-1][0]
    fscheme = urlparse(final_url).scheme
    h = {k.lower(): v for k, v in resp.headers.items()}

    if p.scheme == "http" and fscheme == "http":
        add("HIGH", "साइट HTTPS पर नहीं चल रही", "HTTP अनुरोध HTTPS पर नहीं भेजा गया।", FIX["https"])
    elif p.scheme == "http" and fscheme == "https":
        good.append("HTTP → HTTPS रीडायरेक्ट मौजूद")

    if fscheme == "https":
        try:
            ver, days, issuer = _tls_info(host)
            good.append(f"TLS संस्करण `{ver}`, जारीकर्ता `{_bt(issuer, 40)}`")
            if days < 0:
                add("HIGH", "TLS प्रमाणपत्र की अवधि समाप्त", f"{-days} दिन पहले समाप्त हुआ।", FIX["tls_exp"])
            elif days < 15:
                add("MED", "TLS प्रमाणपत्र जल्द समाप्त होगा", f"{days} दिन बचे हैं।", FIX["tls_exp"])
            elif days < 30:
                add("LOW", "TLS प्रमाणपत्र 30 दिन में समाप्त", f"{days} दिन बचे हैं।", FIX["tls_exp"])
            else:
                good.append(f"प्रमाणपत्र वैध ({days} दिन शेष)")
        except Exception as e:
            if verify_ok:
                add("HIGH", "TLS हैंडशेक/सत्यापन विफल", _bt(e, 160), FIX["tls"])

        hsts = h.get("strict-transport-security")
        if not hsts:
            add("MED", "HSTS हेडर नहीं", "ब्राउज़र को HTTPS पर बाध्य करने वाला हेडर अनुपस्थित।", FIX["hsts"])
        else:
            m = re.search(r"max-age=(\d+)", hsts, re.I)
            if m and int(m.group(1)) < 15552000:
                add("LOW", "HSTS अवधि कम", f"`{_bt(hsts, 80)}`", FIX["hsts"])
            else:
                good.append("HSTS सक्रिय")

    csp = h.get("content-security-policy")
    if not csp:
        add("MED", "Content-Security-Policy नहीं", "XSS के असर को सीमित करने वाली नीति अनुपस्थित।", FIX["csp"])
    elif "unsafe-inline" in csp.lower() or "unsafe-eval" in csp.lower():
        add("LOW", "CSP में कमज़ोर निर्देश", "`unsafe-inline`/`unsafe-eval` मौजूद है।", FIX["csp"])
    else:
        good.append("CSP मौजूद")

    if not h.get("x-frame-options") and not (csp and "frame-ancestors" in csp.lower()):
        add("MED", "क्लिकजैकिंग सुरक्षा नहीं", "न X-Frame-Options, न CSP frame-ancestors।", FIX["xfo"])
    else:
        good.append("फ्रेमिंग सुरक्षा मौजूद")
    if h.get("x-content-type-options", "").lower() != "nosniff":
        add("LOW", "X-Content-Type-Options नहीं", "MIME-sniffing रोकने वाला हेडर अनुपस्थित।", FIX["xcto"])
    else:
        good.append("nosniff सक्रिय")
    if "referrer-policy" not in h:
        add("LOW", "Referrer-Policy नहीं", "रेफ़रर जानकारी का नियंत्रण अनुपस्थित।", FIX["ref"])
    if "permissions-policy" not in h:
        add("INFO", "Permissions-Policy नहीं", "ब्राउज़र-फ़ीचर सीमित नहीं किए गए।", FIX["perm"])

    srv = h.get("server", "")
    if re.search(r"\d+\.\d+", srv):
        add("LOW", "सर्वर संस्करण उजागर", f"Server: `{_bt(srv, 60)}`", FIX["banner"])
    for hdr in ("x-powered-by", "x-aspnet-version", "x-aspnetmvc-version"):
        if hdr in h:
            add("LOW", f"तकनीक-जानकारी उजागर ({hdr})", f"`{_bt(h[hdr], 60)}`", FIX["banner"])

    acao = h.get("access-control-allow-origin")
    if acao == "*" and h.get("access-control-allow-credentials", "").lower() == "true":
        add("HIGH", "खतरनाक CORS कॉन्फ़िगरेशन", "`*` के साथ credentials की अनुमति।", FIX["cors"])
    elif acao == "*":
        add("INFO", "CORS सभी ओरिजिन के लिए खुला", "यदि API सार्वजनिक नहीं है तो सीमित करें।", FIX["cors"])

    try:
        cookies = resp.raw.headers.getlist("Set-Cookie")
    except Exception:
        cookies = [h["set-cookie"]] if "set-cookie" in h else []
    for c in cookies[:5]:
        low = c.lower()
        miss = []
        if fscheme == "https" and "secure" not in low:
            miss.append("Secure")
        if "httponly" not in low:
            miss.append("HttpOnly")
        if "samesite" not in low:
            miss.append("SameSite")
        if miss:
            add("LOW", f"कुकी `{_bt(c.split('=', 1)[0], 30)}` असुरक्षित", "अनुपस्थित: " + ", ".join(miss), FIX["cookie"])

    if "text/html" in h.get("content-type", "").lower():
        body = b""
        try:
            for chunk in resp.iter_content(65536):
                body += chunk
                if len(body) >= 300_000:
                    break
        except Exception:
            pass
        html = body.decode(resp.encoding or "utf-8", errors="ignore")
        if fscheme == "https":
            mixed = re.findall(r"""<(?:script|img|link|iframe)\b[^>]*?(?:src|href)\s*=\s*["']http://[^"']+""", html, re.I)
            if mixed:
                add("MED", "मिश्रित सामग्री (HTTP संसाधन)", f"{len(mixed)} संसाधन `http://` से लोड हो रहे हैं।", FIX["mixed"])
        no_sri = 0
        for m in re.finditer(r"<script\b[^>]*\bsrc\s*=\s*[\"']https?://([^/\"']+)[^>]*>", html, re.I):
            if m.group(1).lower() != host.lower() and "integrity=" not in m.group(0).lower():
                no_sri += 1
        if no_sri:
            add("LOW", "बाहरी स्क्रिप्ट बिना SRI", f"{no_sri} बाहरी स्क्रिप्ट पर `integrity` नहीं।", FIX["sri"])
    resp.close()

    try:
        origin = f"{urlparse(final_url).scheme}://{urlparse(final_url).netloc}"
        r2, _ = _fetch(origin + "/.well-known/security.txt", verify_ok, hops=1)
        if r2.status_code == 200:
            good.append("security.txt मौजूद")
        else:
            add("INFO", "security.txt नहीं", "कमज़ोरी-रिपोर्टिंग का संपर्क-बिंदु उपलब्ध नहीं।", FIX["sectxt"])
        r2.close()
    except Exception:
        pass

    return _render(host, final_url, resp.status_code, findings, good, "")


def _render(host, final_url, status, findings, good, err):
    order = {"HIGH": 0, "MED": 1, "LOW": 2, "INFO": 3}
    findings = sorted(findings, key=lambda f: order[f[0]])
    score = max(0, 100 - sum(SEV[f[0]][2] for f in findings))
    cnt = {k: sum(1 for f in findings if f[0] == k) for k in SEV}
    out = [f"## 🛡️ Ethical Security Audit — `{_bt(host, 80)}`",
           f"**सुरक्षा स्कोर: {score}/100** • 🔴 {cnt['HIGH']} • 🟠 {cnt['MED']} • 🟡 {cnt['LOW']} • 🔵 {cnt['INFO']}",
           f"जाँचा गया पता: `{_bt(final_url, 140)}`" + (f" • HTTP स्थिति: {status}" if status else "")]
    if err:
        out.append(f"⚠️ {err}")
    if findings:
        out.append("### निष्कर्ष और बचाव के उपाय")
        for sev, title, detail, fix in findings:
            ic, lbl, _ = SEV[sev]
            out.append(f"- {ic} **{title}** _({lbl})_ — {detail}\n  - 🛠️ **उपाय:** {fix}")
    else:
        out.append("✅ कोई कमज़ोरी नहीं मिली।")
    if good:
        out.append("### ✅ सही पाया गया\n" + "\n".join(f"- {g}" for g in good))
    out.append("> यह केवल निष्क्रिय (passive) जाँच है: कुछ सामान्य HTTP अनुरोध और TLS हैंडशेक। कोई हमला, पोर्ट-स्कैन, "
               "फज़िंग या एक्सप्लॉइट नहीं चलाया गया। गहरी जाँच के लिए साइट-मालिक की अनुमति से किसी प्रमाणित पेन-टेस्टर की मदद लें।")
    return "\n\n".join(out)


# ══════════════════════════════════════════════════════════════════════════════
# 5. एजेंट 1-3 — PLANNER, CODER, CRITIC
# ══════════════════════════════════════════════════════════════════════════════
CODE_RE = re.compile(
    r"कोड|code|प्रोग्राम|program|स्क्रिप्ट|script|फंक्शन|function|\bbug\b|बग|एरर|error|python|पायथन|javascript|"
    r"\bjava\b|html|css|\bsql\b|c\+\+|react|flask|\bapi\b|एल्गोरिदम|algorithm|debug|डिबग|ऐप\s*बना|वेबसाइट\s*बना",
    re.I)
FACT_Q = re.compile(r"\?|क्या|कैसे|क्यों|कौन|कब|कहाँ|कहां|कितन|what|how|why|who|when|where", re.I)
TEACH_RE = re.compile(r"^\s*(?:सीखो|सीख\s*लो|याद\s*रखो|याद\s*कर\s*लो|learn|remember)\s*[:：\-–]?\s*(.{5,})$", _F)
YES = {"हाँ", "हां", "हा", "haan", "ha", "yes", "y", "ठीक है", "ok", "okay", "जोड़ दो", "जोड़ दीजिए", "जोड़ दे",
       "add", "approve", "सही है", "बिल्कुल", "जी हाँ", "जी हां"}
NO = {"नहीं", "नही", "ना", "no", "n", "nahi", "nahin", "हटा दो", "हटा दे", "रद्द", "reject", "delete",
      "मत जोड़ो", "मत जोड़ना", "जी नहीं"}


def py_blocks(text):
    return [m.group(2) for m in re.finditer(r"```(python|py)\s*\n(.*?)```", text, re.S | re.I)]


def syntax_errors(text):
    errs = []
    for i, code in enumerate(py_blocks(text), 1):
        try:
            ast.parse(code)  # केवल पार्स; कोड कभी चलाया नहीं जाता
        except SyntaxError as e:
            errs.append(f"ब्लॉक {i}, पंक्ति {e.lineno}: {e.msg}")
    return errs


class Planner:
    name = "🧭 Planner"

    def plan(self, msg, intent, hits):
        if intent == "code":
            p = llm([{"role": "system", "content": "तुम Planner एजेंट हो। केवल 3-5 छोटे क्रमांकित चरणों में हिंदी में योजना दो। कोई कोड मत लिखो।"},
                     {"role": "user", "content": msg}], max_new_tokens=150, temperature=0.2)
            return p or "1. आवश्यकता समझो\n2. कोड लिखो\n3. जाँचो"
        base = "सीधा और सटीक उत्तर देना"
        return base + (" (स्वीकृत मेमोरी का उपयोग करके)" if hits else "")


class Coder:
    name = "💻 Coder"

    def self_correct(self, msgs, answer, rounds=2):
        fixed = 0
        for _ in range(rounds):
            errs = syntax_errors(answer)
            if not errs:
                break
            answer = llm(msgs + [{"role": "assistant", "content": answer},
                                 {"role": "user", "content": "ऊपर के Python कोड में SyntaxError है: " + "; ".join(errs) +
                                  "\nकृपया पूरा सुधरा हुआ कोड ```python ब्लॉक में दोबारा दो।"}],
                         max_new_tokens=700, temperature=0.1)
            fixed += 1
        return answer, fixed


class Critic:
    name = "🔍 Critic"

    def review(self, q, ans, deep, regen, is_code):
        notes = []
        if ans.count("```") % 2 == 1:
            ans += "\n```"
            notes.append("खुला कोड-ब्लॉक बंद किया")
        if len(ans.strip()) < 2:
            return "क्षमा करें, मैं इस बार उत्तर नहीं बना पाया। कृपया प्रश्न दोबारा पूछें।", ["खाली उत्तर पकड़ा गया"]
        if not is_code:
            lines = ans.splitlines()
            dedup = [l for i, l in enumerate(lines) if i == 0 or l.strip() != lines[i - 1].strip() or not l.strip()]
            if len(dedup) < len(lines) - 2:
                ans = "\n".join(dedup)
                notes.append("दोहराई गई पंक्तियाँ हटाईं")
        if deep:
            crit = llm([{"role": "system", "content": "तुम कठोर समीक्षक (Critic) हो।"},
                        {"role": "user", "content": f"प्रश्न: {q}\n\nउत्तर:\n{ans[:2500]}\n\nअगर उत्तर में तथ्य/तर्क/कोडिंग की गलती है तो "
                         "अधिकतम 3 छोटे बिंदुओं में लिखो। गलती न हो तो केवल यही लिखो: कोई समस्या नहीं"}],
                       max_new_tokens=120, temperature=0)
            if crit and "कोई समस्या नहीं" not in crit and len(crit) > 10:
                ans = regen(crit)
                notes.append("गहरी जाँच के बाद उत्तर सुधारा")
            else:
                notes.append("गहरी जाँच: कोई समस्या नहीं")
        errs = syntax_errors(ans)
        if errs:
            ans += "\n\n⚠️ **Critic:** कोड में Python सिंटैक्स त्रुटि बची है — " + "; ".join(errs) + "। चलाने से पहले जाँच लें।"
            notes.append("सिंटैक्स त्रुटि बाकी")
        elif is_code and py_blocks(ans):
            notes.append("Python सिंटैक्स जाँच सफल")
        return ans, notes


PLANNER, CODER, CRITIC = Planner(), Coder(), Critic()


def knowledge_block(hits):
    if not hits:
        return ""
    return f"\n\n{OWNER} द्वारा स्वीकृत ज्ञान (इसे प्राथमिकता दो):\n" + "\n".join(f"- {h[:500]}" for h in hits)


def build_messages(system_extra, history, user):
    msgs = [{"role": "system", "content": SYSTEM_CORE + system_extra}]
    for u, a in history[-3:]:
        msgs += [{"role": "user", "content": u}, {"role": "assistant", "content": a}]
    msgs.append({"role": "user", "content": user})
    return msgs


# ══════════════════════════════════════════════════════════════════════════════
# 6. मुख्य पाइपलाइन (5-कोर)
# ══════════════════════════════════════════════════════════════════════════════
def process(msg, pin, consent, deep, autolearn, history):
    history = history or []
    msg = (msg or "").strip()
    L = []

    def log(agent, text):
        L.append(f"{agent} ▸ {text}")
        return "\n".join(L)

    if not msg:
        yield gr.update(), gr.update(), pend_view(), gr.update(), history
        return

    # (4) Guardian — इनपुट
    blocked, reply = GUARD.check_input(msg)
    if blocked:
        yield reply, log(GUARD.name, "अनुरोध रोका गया"), pend_view(), "", history
        return
    ident = GUARD.identity(msg)
    if ident:
        yield ident, log(GUARD.name, "मालिक-पहचान नियम लागू"), pend_view(), "", history
        return

    # स्वीकृति: 'हाँ' / 'नहीं'
    word = msg.strip(" .,!?।\"'").lower()
    if PENDING.head() and (word in YES or word in NO):
        res = decide(word in YES, pin)
        yield res, log("🧠 Learning", "मास्टर का निर्णय दर्ज"), pend_view(), "", history
        return

    # सिखाना: 'सीखो: ...' → Pending_Knowledge
    tm = TEACH_RE.match(msg)
    if tm:
        item = PENDING.add(tm.group(1), "taught")
        if item:
            yield ask_block(item), log("🧠 Learning", "नया ज्ञान Pending_Knowledge में रखा"), pend_view(), "", history
        else:
            yield ("ℹ️ यह ज्ञान पहले से लंबित/मेमोरी में है, या कतार भरी है (अधिकतम 20)। पहले लंबित ज्ञान पर निर्णय दें।",
                   log("🧠 Learning", "डुप्लिकेट/कतार भरी"), pend_view(), "", history)
        return

    # (5) Ethical Security Auditor
    url = extract_url(msg)
    if url and AUDIT_KW.search(msg):
        yield "⏳ सुरक्षा जाँच चल रही है…", log("🔐 Auditor", f"{url} की निष्क्रिय जाँच"), gr.update(), gr.update(), history
        try:
            rep = audit_site(url, consent)
        except Exception as e:
            rep = f"⚠️ जाँच में त्रुटि: {type(e).__name__}: {_bt(e, 160)}"
        yield rep, log("🔐 Auditor", "रिपोर्ट तैयार"), pend_view(), "", history
        return

    try:
        yield "⏳ J.A.R.V.I.S. सोच रहा है…", log(PLANNER.name, "अनुरोध का विश्लेषण…"), gr.update(), gr.update(), history
        intent = "code" if CODE_RE.search(msg) else "chat"
        hits = MEM.search(msg)
        plan = PLANNER.plan(msg, intent, hits)
        log(PLANNER.name, f"प्रकार={intent}, मेमोरी-मिलान={len(hits)} → " + plan.replace("\n", " ")[:220])

        extra = knowledge_block(hits)
        if intent == "code":
            extra += CODER_STYLE
            user_content = f"योजना:\n{plan}\n\nकार्य: {msg}"
            mt, temp, who = 700, 0.2, CODER.name
        else:
            user_content, mt, temp, who = msg, 320, 0.5, "🧠 Core"
        msgs = build_messages(extra, history, user_content)

        yield "⏳ J.A.R.V.I.S. सोच रहा है…", log(who, "उत्तर लिख रहा हूँ…"), gr.update(), gr.update(), history
        answer, last = "", 0.0
        for part in llm_stream(msgs, mt, temp):
            answer = part
            if time.time() - last > 0.3:
                last = time.time()
                yield answer, "\n".join(L), gr.update(), gr.update(), history
        answer = answer.strip()

        if intent == "code":
            answer, fixed = CODER.self_correct(msgs, answer)
            log(CODER.name, f"{fixed} बार स्वयं-सुधार" if fixed else "पहले प्रयास में सिंटैक्स सही")
            yield answer, "\n".join(L), gr.update(), gr.update(), history

        def regen(crit):
            return llm(msgs + [{"role": "assistant", "content": answer},
                               {"role": "user", "content": f"समीक्षक की टिप्पणी:\n{crit}\n\nइन्हें सुधारकर पूरा अंतिम उत्तर दो।"}],
                       mt, 0.2)

        answer, cn = CRITIC.review(msg, answer, deep, regen, intent == "code")
        log(CRITIC.name, "; ".join(cn) if cn else "कोई समस्या नहीं मिली")

        answer, gn = GUARD.check_output(answer)
        log(GUARD.name, "; ".join(gn) if gn else "आउटपुट सुरक्षित")

        # (3) पूछकर सीखना — सीधे मेमोरी में नहीं
        if autolearn and intent == "chat" and not hits and FACT_Q.search(msg) and len(answer) > 40 and not gn:
            head_before = PENDING.head()
            item = PENDING.add(f"प्रश्न: {msg}\nउत्तर: {answer[:500]}", "auto")
            if item:
                log("🧠 Learning", "नया ज्ञान Pending_Knowledge में रखा")
                if head_before is None:
                    answer += "\n\n---\n" + ask_block(item)
                else:
                    answer += f"\n\n---\n🧠 _नया ज्ञान कतार में जोड़ा; लंबित: {PENDING.count()}_"

        history = (history + [[msg, answer[:500]]])[-4:]
        yield answer, "\n".join(L), pend_view(), "", history
    except Exception as e:
        yield (f"⚠️ आंतरिक त्रुटि: {type(e).__name__}: {_bt(e, 200)}",
               log("⚠️ System", "पाइपलाइन विफल"), pend_view(), "", history)


def do_yes(pin):
    return decide(True, pin), pend_view()


def do_no(pin):
    return decide(False, pin), pend_view()


def run_audit(url, consent):
    try:
        return audit_site(url, consent)
    except Exception as e:
        return f"⚠️ जाँच में त्रुटि: {type(e).__name__}: {_bt(e, 160)}"


# ══════════════════════════════════════════════════════════════════════════════
# 7. आयरन-मैन होलोग्राम + वॉइस UI (Three.js + Web Speech API)
# ══════════════════════════════════════════════════════════════════════════════
HEAD = r"""
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<style>
body, .gradio-container { background: radial-gradient(ellipse at 50% -10%, #06263a 0%, #02070d 60%, #000 100%) !important; }
.gradio-container { max-width: 1100px !important; }
#holo_root { position: relative; width: 100%; height: 420px; overflow: hidden; border-radius: 14px;
  border: 1px solid rgba(0,229,255,.38); background: linear-gradient(180deg, rgba(0,229,255,.06), rgba(0,0,0,.45));
  box-shadow: 0 0 34px rgba(0,229,255,.16) inset, 0 0 22px rgba(0,229,255,.12); }
#holo_root canvas { position: absolute; inset: 0; width: 100% !important; height: 100% !important; display: block; }
#holo_root::after { content: ""; position: absolute; inset: 0; pointer-events: none; mix-blend-mode: screen;
  background: repeating-linear-gradient(0deg, rgba(0,229,255,.05) 0 1px, transparent 1px 3px); animation: jscan 7s linear infinite; }
@keyframes jscan { from { background-position: 0 0; } to { background-position: 0 60px; } }
@media (prefers-reduced-motion: reduce) { #holo_root::after { animation: none; } }
.j-title { position: absolute; left: 16px; top: 12px; z-index: 5; font-family: 'Orbitron', 'Segoe UI', sans-serif;
  font-size: 18px; letter-spacing: 3px; color: #7df3ff; text-shadow: 0 0 12px rgba(0,229,255,.7); }
.j-title b { color: #fff; }
.j-btns { position: absolute; right: 12px; top: 10px; z-index: 5; display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
.j-btn { cursor: pointer; padding: 8px 14px; border-radius: 8px; color: #bffaff; background: rgba(0,229,255,.1);
  border: 1px solid rgba(0,229,255,.55); font-size: 14px; }
.j-btn:hover { background: rgba(0,229,255,.25); }
.j-btn:focus-visible { outline: 2px solid #fff; outline-offset: 2px; }
.j-status { position: absolute; left: 16px; bottom: 12px; z-index: 5; font-family: 'Orbitron', sans-serif; font-size: 12px;
  letter-spacing: 2px; color: #7df3ff; }
.j-heard { position: absolute; left: 50%; bottom: 40px; transform: translateX(-50%); z-index: 5; max-width: 80%;
  text-align: center; font-size: 15px; color: #e6fdff; text-shadow: 0 0 8px rgba(0,229,255,.8); }
.j-owner { position: absolute; right: 16px; bottom: 12px; z-index: 5; font-size: 12px; color: #7df3ff; opacity: .85; }
</style>
<script>
(function () {
  if (window.__JARVIS_BOOT) { return; }
  window.__JARVIS_BOOT = true;
  document.addEventListener('DOMContentLoaded', function () { document.body.classList.add('dark'); });

  var S = { mode: 'idle', voiceOn: true, raf: 0, renderer: null, ro: null, wd: 0, rec: null, mx: 0, my: 0 };
  var COLORS = { idle: 0x00e5ff, listening: 0x39ff88, thinking: 0xb36bff, speaking: 0xffb020 };
  var LABEL = { idle: 'STANDBY • तैयार', listening: 'LISTENING • सुन रहा हूँ…', thinking: 'PROCESSING • सोच रहा हूँ…', speaking: 'SPEAKING • बोल रहा हूँ…' };
  var ui = {}, mats = [];
  function $(id) { return document.getElementById(id); }

  function setMode(m) {
    S.mode = m;
    if (ui.status) { ui.status.textContent = LABEL[m]; }
    mats.forEach(function (x) { x.color.setHex(COLORS[m]); });
    clearTimeout(S.wd);
    if (m === 'thinking') { S.wd = setTimeout(function () { if (S.mode === 'thinking') { setMode('idle'); } }, 300000); }
  }
  function say(t) { if (ui.heard) { ui.heard.textContent = t; } }

  function setGradioValue(el, val) {
    var proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, val);
    el.dispatchEvent(new Event('input', { bubbles: true }));
  }
  function sendToGradio(text) {
    var box = document.querySelector('#cmd_box textarea, #cmd_box input');
    var b = document.querySelector('#send_btn');
    if (!box || !b) { say('कमांड बॉक्स नहीं मिला'); setMode('idle'); return; }
    var btn = b.tagName === 'BUTTON' ? b : b.querySelector('button');
    setGradioValue(box, text);
    setMode('thinking');
    setTimeout(function () { btn.click(); }, 150);
  }

  function startListen() {
    var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { say('इस ब्राउज़र में वॉइस-इनपुट नहीं है — Chrome/Edge में खोलें।'); return; }
    if (window.speechSynthesis) { speechSynthesis.cancel(); }
    try { if (S.rec) { S.rec.abort(); } } catch (e) {}
    var rec = new SR();
    S.rec = rec;
    rec.lang = 'hi-IN'; rec.interimResults = true; rec.continuous = false; rec.maxAlternatives = 1;
    rec.onstart = function () { setMode('listening'); say('बोलिए…'); };
    rec.onresult = function (e) {
      var txt = '', fin = false;
      for (var i = e.resultIndex; i < e.results.length; i++) {
        txt += e.results[i][0].transcript;
        if (e.results[i].isFinal) { fin = true; }
      }
      say('🗣️ ' + txt);
      if (fin && txt.trim()) { sendToGradio(txt.trim()); }
    };
    rec.onerror = function (e) {
      setMode('idle');
      say(e.error === 'not-allowed' ? 'माइक की अनुमति दें (Space को अलग टैब में खोलना बेहतर है)।' : 'माइक त्रुटि: ' + e.error);
    };
    rec.onend = function () { if (S.mode === 'listening') { setMode('idle'); } };
    try { rec.start(); } catch (e) { say('माइक शुरू नहीं हो पाया'); }
  }

  function stopAll() {
    try { if (S.rec) { S.rec.abort(); } } catch (e) {}
    if (window.speechSynthesis) { speechSynthesis.cancel(); }
    setMode('idle');
  }

  function chunks(t) {
    var parts = t.match(/[^।.!?]+[।.!?]?/g) || [t], out = [], cur = '';
    parts.forEach(function (p) {
      if ((cur + p).length > 170 && cur) { out.push(cur); cur = p; } else { cur += p; }
    });
    if (cur.trim()) { out.push(cur); }
    return out;
  }

  window.JARVIS_speak = function (raw) {
    var t = (raw || '')
      .replace(/```[\s\S]*?```/g, ' कोड ऊपर दिया गया है। ')
      .replace(/https?:\/\/\S+/g, ' लिंक ')
      .replace(/`[^`]*`/g, ' ')
      .replace(/[#*_>|~\[\]()]/g, ' ')
      .replace(/\s+/g, ' ').trim();
    if (!t || t.indexOf('⏳') === 0 || !S.voiceOn || !window.speechSynthesis) { setMode('idle'); return; }
    if (t.length > 650) { t = t.slice(0, 650); }
    speechSynthesis.cancel();
    var voices = speechSynthesis.getVoices();
    var hv = null, i;
    for (i = 0; i < voices.length; i++) { if (/^hi[-_]IN$/i.test(voices[i].lang)) { hv = voices[i]; break; } }
    if (!hv) { for (i = 0; i < voices.length; i++) { if (/^hi/i.test(voices[i].lang)) { hv = voices[i]; break; } } }
    var cs = chunks(t);
    cs.forEach(function (c, idx) {
      var u = new SpeechSynthesisUtterance(c);
      u.lang = 'hi-IN'; u.rate = 1; u.pitch = 0.9;
      if (hv) { u.voice = hv; }
      if (idx === 0) { u.onstart = function () { setMode('speaking'); }; }
      if (idx === cs.length - 1) { u.onend = function () { setMode('idle'); }; }
      u.onerror = function () { setMode('idle'); };
      speechSynthesis.speak(u);
    });
  };

  document.addEventListener('click', function (e) {
    var el = e.target && e.target.closest ? e.target.closest('#send_btn, #yes_btn, #no_btn') : null;
    if (el) { setMode('thinking'); }
  }, true);

  function build(root) {
    if (S.raf) { cancelAnimationFrame(S.raf); S.raf = 0; }
    if (S.ro) { try { S.ro.disconnect(); } catch (e) {} S.ro = null; }
    if (S.renderer) { try { S.renderer.dispose(); } catch (e) {} S.renderer = null; }
    mats = [];
    root.innerHTML =
      '<div class="j-title">J.A.R.V.I.S. <b>QUANTUM X</b></div>' +
      '<div class="j-btns"><button class="j-btn" id="j_mic">🎙️ बोलिए</button>' +
      '<button class="j-btn" id="j_voice">🔊 आवाज़: ON</button><button class="j-btn" id="j_stop">⏹ रोकें</button></div>' +
      '<div class="j-status" id="j_status"></div><div class="j-heard" id="j_heard"></div>' +
      '<div class="j-owner">OWNER • __OWNER__</div>';
    ui.status = $('j_status'); ui.heard = $('j_heard');
    $('j_mic').onclick = startListen;
    $('j_stop').onclick = stopAll;
    $('j_voice').onclick = function () {
      S.voiceOn = !S.voiceOn;
      this.textContent = '🔊 आवाज़: ' + (S.voiceOn ? 'ON' : 'OFF');
      if (!S.voiceOn && window.speechSynthesis) { speechSynthesis.cancel(); if (S.mode === 'speaking') { setMode('idle'); } }
    };
    if (window.speechSynthesis) { speechSynthesis.getVoices(); }
    if (typeof THREE === 'undefined') { setMode('idle'); say('3D इंजन लोड नहीं हुआ (CDN) — वॉइस फीचर चालू हैं।'); return; }
    var renderer;
    try { renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true }); }
    catch (e) { setMode('idle'); say('WebGL उपलब्ध नहीं — वॉइस फीचर चालू हैं।'); return; }
    S.renderer = renderer;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    root.insertBefore(renderer.domElement, root.firstChild);

    var scene = new THREE.Scene();
    var camera = new THREE.PerspectiveCamera(55, 1, 0.1, 100);
    camera.position.set(0, 0.4, 6.4);
    var group = new THREE.Group(); scene.add(group);
    function M(op, extra) {
      var m = new THREE.MeshBasicMaterial(Object.assign({ color: COLORS.idle, transparent: true, opacity: op }, extra || {}));
      mats.push(m); return m;
    }
    var core = new THREE.Mesh(new THREE.IcosahedronGeometry(1.15, 1), M(0.85, { wireframe: true }));
    var inner = new THREE.Mesh(new THREE.SphereGeometry(0.55, 24, 24), M(0.35));
    group.add(core); group.add(inner);
    var rings = [], arcs = [], i;
    for (i = 0; i < 4; i++) {
      var r = new THREE.Mesh(new THREE.TorusGeometry(1.7 + i * 0.45, 0.02, 8, 160), M(0.75 - i * 0.12));
      r.rotation.x = Math.PI / 2 + (i - 1.5) * 0.35; r.rotation.y = i * 0.5;
      group.add(r); rings.push(r);
    }
    for (i = 0; i < 3; i++) {
      var a = new THREE.Mesh(new THREE.RingGeometry(3.0 + i * 0.35, 3.04 + i * 0.35, 64, 1, 0, Math.PI * (1.1 - i * 0.25)), M(0.7, { side: THREE.DoubleSide }));
      a.rotation.x = Math.PI / 2.4; group.add(a); arcs.push(a);
    }
    var N = 900, pos = new Float32Array(N * 3), k;
    for (k = 0; k < N; k++) {
      var rr = 3.5 + Math.random() * 4, th = Math.random() * Math.PI * 2, ph = Math.acos(2 * Math.random() - 1);
      pos[k * 3] = rr * Math.sin(ph) * Math.cos(th);
      pos[k * 3 + 1] = rr * Math.sin(ph) * Math.sin(th) * 0.7;
      pos[k * 3 + 2] = rr * Math.cos(ph);
    }
    var pg = new THREE.BufferGeometry();
    pg.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    var pm = new THREE.PointsMaterial({ color: COLORS.idle, size: 0.035, transparent: true, opacity: 0.8 });
    mats.push(pm);
    var pts = new THREE.Points(pg, pm); scene.add(pts);
    var grid = new THREE.GridHelper(16, 32, 0x00e5ff, 0x0a4a66);
    grid.position.y = -2.4; grid.material.transparent = true; grid.material.opacity = 0.35; scene.add(grid);

    function resize() {
      var w = root.clientWidth || 600, h = root.clientHeight || 420;
      renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
    }
    if (window.ResizeObserver) { S.ro = new ResizeObserver(resize); S.ro.observe(root); }
    resize();
    root.onmousemove = function (e) {
      var b = root.getBoundingClientRect();
      S.mx = (e.clientX - b.left) / b.width - 0.5; S.my = (e.clientY - b.top) / b.height - 0.5;
    };

    var clock = new THREE.Clock();
    function tick() {
      S.raf = requestAnimationFrame(tick);
      var t = clock.getElapsedTime(), m = S.mode;
      var sp = m === 'thinking' ? 3 : (m === 'listening' ? 1.6 : (m === 'speaking' ? 1.3 : 0.5));
      var pulse = m === 'speaking' ? 1 + 0.12 * Math.sin(t * 14) + 0.06 * Math.sin(t * 23)
        : (m === 'listening' ? 1 + 0.07 * Math.sin(t * 6) : 1 + 0.03 * Math.sin(t * 2));
      core.rotation.y += 0.004 * sp; core.rotation.x += 0.002 * sp;
      core.scale.setScalar(pulse);
      inner.scale.setScalar(pulse * (0.9 + 0.1 * Math.sin(t * 3)));
      rings.forEach(function (r, idx) { r.rotation.z += (0.003 + idx * 0.002) * sp * (idx % 2 ? -1 : 1); });
      arcs.forEach(function (a, idx) { a.rotation.z += (0.006 + idx * 0.003) * sp * (idx % 2 ? -1 : 1); });
      pts.rotation.y += 0.0006 * sp;
      group.rotation.y += (S.mx * 0.9 - group.rotation.y) * 0.03;
      group.rotation.x += (S.my * 0.5 - group.rotation.x) * 0.03;
      renderer.render(scene, camera);
    }
    setMode(S.mode);
    tick();
  }

  setInterval(function () {
    var root = $('holo_root');
    if (root && !root.dataset.ready) { root.dataset.ready = '1'; build(root); }
  }, 600);
})();
</script>
""".replace("__OWNER__", OWNER)

GREETING = (
    f"**{SYSTEM_NAME} ऑनलाइन।** नमस्ते {OWNER}! 🙏\n\n"
    "ऊपर **🎙️ बोलिए** दबाकर हिंदी में आदेश दें, या नीचे टाइप करें।\n\n"
    "- कोड लिखवाएँ: _\"पायथन में फाइबोनाची फंक्शन लिखो\"_\n"
    "- कुछ सिखाएँ: _\"सीखो: मेरी कंपनी का नाम ...\"_ (पहले आपसे पूछकर ही जुड़ेगा)\n"
    "- अपनी वेबसाइट की सुरक्षा जाँच: _\"example.com स्कैन करो\"_ (सेटिंग्स में अनुमति टिक करें)"
)


def _split_kwargs(head):
    bp = inspect.signature(gr.Blocks.__init__).parameters
    lp = inspect.signature(gr.Blocks.launch).parameters
    bk, lk = {}, {}
    if "head" in bp:
        bk["head"] = head
    elif "head" in lp:
        lk["head"] = head
    if "ssr_mode" in lp:
        lk["ssr_mode"] = False
    return bk, lk


BK, LK = _split_kwargs(HEAD)

with gr.Blocks(title=SYSTEM_NAME, **BK) as demo:
    gr.HTML('<div id="holo_root"></div>')
    state = gr.State([])
    with gr.Tabs():
        with gr.Tab("💬 कमांड सेंटर"):
            answer = gr.Markdown(GREETING, elem_id="answer_box")
            with gr.Row():
                cmd = gr.Textbox(label="आदेश", placeholder="यहाँ लिखें या 🎙️ से बोलें…", elem_id="cmd_box", scale=6)
                send = gr.Button("🚀 भेजें", elem_id="send_btn", variant="primary", scale=1)
            with gr.Accordion("🧠 पूछकर सीखना — Pending_Knowledge", open=True):
                pending = gr.Markdown(pend_view())
                with gr.Row():
                    yes = gr.Button("✅ हाँ, जोड़ दो", elem_id="yes_btn")
                    no = gr.Button("❌ नहीं, हटा दो", elem_id="no_btn")
            with gr.Accordion("⚙️ सेटिंग्स", open=False):
                pin = gr.Textbox(label="मास्टर PIN (यदि Space Secret में MASTER_PIN सेट है)", type="password")
                consent = gr.Checkbox(label="पुष्टि: जो वेबसाइट मैं जाँचवा रहा हूँ वह मेरी है या मेरे पास लिखित अनुमति है", value=False)
                deep = gr.Checkbox(label="गहरी Critic-जाँच (ज़्यादा सटीक, पर धीमी)", value=False)
                autol = gr.Checkbox(label="नया सीखा हुआ अपने-आप प्रस्तावित करो (मंज़ूरी के बाद ही जुड़ेगा)", value=True)
            logbox = gr.Textbox(label="5-कोर एजेंट लॉग", lines=8, interactive=False)
        with gr.Tab("🛡️ Ethical Security Auditor"):
            gr.Markdown(
                "केवल **अपनी या लिखित अनुमति वाली** वेबसाइट। यह निष्क्रिय जाँच है (कुछ सामान्य HTTP अनुरोध + TLS जाँच): "
                "सुरक्षा-हेडर, प्रमाणपत्र, कुकी-फ्लैग, मिश्रित सामग्री आदि। कोई हमला, पोर्ट-स्कैन या फज़िंग नहीं। "
                "पहले ⚙️ सेटिंग्स में अनुमति-पुष्टि टिक करें।")
            aurl = gr.Textbox(label="वेबसाइट का लिंक", placeholder="https://example.com")
            abtn = gr.Button("🔐 जाँच शुरू करें", variant="primary")
            areport = gr.Markdown()

    speak_js = "(t) => { if (window.JARVIS_speak) { window.JARVIS_speak(t); } }"
    ins = [cmd, pin, consent, deep, autol, state]
    outs = [answer, logbox, pending, cmd, state]
    send.click(process, ins, outs).then(None, [answer], None, js=speak_js)
    cmd.submit(process, ins, outs).then(None, [answer], None, js=speak_js)
    yes.click(do_yes, [pin], [answer, pending]).then(None, [answer], None, js=speak_js)
    no.click(do_no, [pin], [answer, pending]).then(None, [answer], None, js=speak_js)
    abtn.click(run_audit, [aurl, consent], [areport])
    demo.load(pend_view, None, pending)
    demo.queue(max_size=16)


def _warmup():
    try:
        get_model()
        MEM.init()
    except Exception as e:
        print("[warmup] skipped:", e)


if __name__ == "__main__":
    threading.Thread(target=_warmup, daemon=True).start()
    demo.launch(server_name="0.0.0.0", server_port=7860, show_error=True, **LK)
