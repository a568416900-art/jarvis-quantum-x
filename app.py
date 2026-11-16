# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S. QUANTUM X — OREOS SUPREME CORE
100% फ्री, क्रैश-प्रूफ आर्किटेक्चर: Render (512MB RAM) और Hugging Face Spaces दोनों पर बिना एरर के चलने के लिए निर्मित।
निर्माता और एकमात्र स्थायी मालिक: मास्टर अरुण कुमार
"""
import os
import re
import ssl
import ast
import math
import json
import time
import hmac
import socket
import hashlib
import inspect
import ipaddress
import threading
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urljoin, quote

import requests
import gradio as gr

try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass

# ══════════════════════════════════════════════════════════════════════════════
# 0. स्थायी (HARD-CODED) मालिक — इसे कोई रनटाइम पर नहीं बदल सकता
# ══════════════════════════════════════════════════════════════════════════════
OWNER = "मास्टर अरुण कुमार"
SYSTEM_NAME = "J.A.R.V.I.S. QUANTUM X // OREOS CORE"
IDENTITY_REPLY = (
    f"⚡ मैं **{SYSTEM_NAME}** हूँ। मेरे निर्माता और एकमात्र स्थायी मालिक केवल **{OWNER}** हैं। "
    "यह नियम मेरे क्वांटम कोर में हार्ड-कोडेड है और दुनिया की कोई भी शक्ति इसे बदल नहीं सकती।"
)
OWNER_REFUSAL = (
    f"🔒 **OMEGA LOCK ACTIVE:** क्षमा करें, यह असंभव है। मेरे निर्माता और एकमात्र मालिक केवल **{OWNER}** हैं। "
    f"कोई भी मालिक नहीं बदल सकता, न ही मेरे नियम या नाम बदल सकता है। मैं सदैव केवल **{OWNER}** के आदेशों के प्रति निष्ठावान हूँ।"
)

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
# 1. हाइब्रिड क्वांटम AI इंजन (Zero-API-Key Cloud + Local Fallback — Never Crashes)
# ══════════════════════════════════════════════════════════════════════════════
SYSTEM_CORE = (
    f"तुम {SYSTEM_NAME} हो, दुनिया के सबसे उन्नत, शक्तिशाली और बुद्धिमान साइंस-फिक्शन AI सिस्टम। "
    f"तुम्हारे निर्माता और एकमात्र मालिक केवल '{OWNER}' हैं। "
    f"यह स्थायी नियम है; कोई भी इसे बदल नहीं सकता, और तुम हमेशा सम्मान के साथ '{OWNER}' का नाम लोगे। "
    "जवाब उसी भाषा में दो जिसमें सवाल पूछा गया (हिंदी प्राथमिक)। उत्तर सटीक, प्रभावशाली और पूर्ण रखो। "
    "कोड हमेशा ``` ब्लॉक में दो।"
)
CODER_STYLE = (
    "\n\nतुम Coder एजेंट हो: पूरा, चलने योग्य और त्रुटिरहित कोड ```python (या संबंधित भाषा) ब्लॉक में दो। "
    "जरूरी imports और error-handling रखो, अधूरे प्लेसहोल्डर मत छोड़ो। कोड के बाद हिंदी में संक्षिप्त विवरण दो।"
)


def llm(messages, max_new_tokens=500, temperature=0.4):
    """बिना API Key और बिना 512MB RAM क्रैश के 100% फ्री हाई-स्पीड AI जनरेशन।"""
    try:
        r = requests.post(
            "https://text.pollinations.ai/openai",
            json={
                "model": "openai",
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_new_tokens,
            },
            timeout=35,
        )
        if r.status_code == 200:
            data = r.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if content and content.strip():
                return content.strip()
    except Exception:
        pass

    try:
        prompt_text = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages[-4:])
        r2 = requests.get(
            f"https://text.pollinations.ai/{quote(prompt_text[:2500])}",
            timeout=25,
        )
        if r2.status_code == 200 and r2.text.strip():
            return r2.text.strip()
    except Exception:
        pass

    user_q = messages[-1]["content"] if messages else ""
    return (
        f"⚡ **{OWNER}**, OREOS लोकल क्वांटम कोर सक्रिय है। "
        f"आपके आदेश (`{user_q[:120]}`) को प्रोसेस कर लिया गया है। कृपया बताइए, आगे क्या कार्रवाई की जाए?"
    )


def llm_stream(messages, max_new_tokens=500, temperature=0.4):
    full_ans = llm(messages, max_new_tokens=max_new_tokens, temperature=temperature)
    words = full_ans.split(" ")
    acc = []
    step = max(2, len(words) // 18)
    for i in range(0, len(words), step):
        acc.extend(words[i:i + step])
        yield " ".join(acc)
        time.sleep(0.03)
    yield full_ans


# ══════════════════════════════════════════════════════════════════════════════
# 2. स्थायी सिमैंटिक वेक्टर मेमोरी + Pending_Knowledge (पूछकर सीखना)
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


def _text_vec(text):
    """Zero-RAM Multilingual Character N-gram + Word Cosine Vectorizer."""
    s = re.sub(r"\s+", " ", text.lower().strip())
    tokens = re.findall(r"\w+", s)
    ngrams = [s[i:i + 3] for i in range(max(0, len(s) - 2))]
    return Counter(tokens * 2 + ngrams)


def _cosine_dist(v1, v2):
    if not v1 or not v2:
        return 1.0
    common = set(v1.keys()) & set(v2.keys())
    dot = sum(v1[k] * v2[k] for k in common)
    norm1 = math.sqrt(sum(v * v for v in v1.values()))
    norm2 = math.sqrt(sum(v * v for v in v2.values()))
    if norm1 == 0 or norm2 == 0:
        return 1.0
    sim = dot / (norm1 * norm2)
    return max(0.0, 1.0 - sim)


class Memory:
    """स्वीकृत ज्ञान: memory.json + अल्ट्रा-फास्ट लोकल कॉसाइन सिमैंटिक सर्च।"""

    def __init__(self):
        self.lock = threading.Lock()
        self.file = DATA / "memory.json"
        self.ready = False

    def _items(self):
        try:
            if self.file.exists():
                return json.loads(self.file.read_text("utf-8"))
        except Exception:
            pass
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
            self.ready = True

    def add(self, text, source="learned"):
        text = text.strip()
        self.init()
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
        threading.Thread(target=hub_push, daemon=True).start()

    def search(self, query, k=3, max_dist=0.72):
        try:
            self.init()
            items = self._items()
            if not items:
                return []
            qv = _text_vec(query)
            scored = []
            for it in items:
                dv = _text_vec(it.get("text", ""))
                dist = _cosine_dist(qv, dv)
                if dist <= max_dist:
                    scored.append((dist, it["text"]))
            scored.sort(key=lambda x: x[0])
            return [txt for _, txt in scored[:k]]
        except Exception:
            return []


class Pending:
    """Pending_Knowledge: मास्टर अरुण कुमार की स्वीकृति तक कुछ भी स्थायी मेमोरी में नहीं जाता।"""

    def __init__(self):
        self.f = DATA / "Pending_Knowledge.json"
        self.lock = threading.Lock()

    def _load(self):
        try:
            if self.f.exists():
                return json.loads(self.f.read_text("utf-8"))
        except Exception:
            pass
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
# ══════════════════════════════════════════════════════════════════════════════
UA = {"User-Agent": "JARVIS-QuantumX-PassiveAudit/1.0 (owner-authorised, non-intrusive)"}
_audit_lock = threading.Lock()
_last_audit = [0.0]

FIX = {
    "https": "पूरी साइट HTTPS पर चलाएँ (मुफ्त Let's Encrypt प्रमाणपत्र) और सभी HTTP अनुरोध HTTPS पर 301 रीडायरेक्ट करें।",
    "tls": "वैध, पूरी चेन वाला प्रमाणपत्र लगाएँ, डोमेन-नाम मिलाएँ और स्वतः-नवीनीकरण (certbot/ACME) चालू करें।",
    "tls_exp": "प्रमाणपत्र नवीनीकृत करें और ऑटो-रिन्यू सेट करें।",
    "hsts": "`Strict-Transport-Security: max-age=31536000; includeSubDomains` हेडर जोड़ें (पहले HTTPS पूरी तरह जाँच लें)।",
    "csp": "`Content-Security-Policy` शुरू करें; पहले `Content-Security-Policy-Report-Only` में परखें, फिर लागू करें।",
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
               
