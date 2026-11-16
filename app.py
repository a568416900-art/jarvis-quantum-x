# -*- coding: utf-8 -*-
import os
import re
import ssl
import ast
import json
import time
import socket
import inspect
import urllib.parse
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import requests
import gradio as gr

# ==============================================================================
# 1. PERMANENT OWNER LOCK (अपरिवर्तनीय मालिक - मास्टर अरुण कुमार)
# ==============================================================================
OWNER = "मास्टर अरुण कुमार"
SYSTEM_NAME = "J.A.R.V.I.S. QUANTUM X [SUPREME AI]"

DATA_DIR = Path("./jarvis_vault")
DATA_DIR.mkdir(parents=True, exist_ok=True)
MEM_FILE = DATA_DIR / "permanent_memory.json"
PEND_FILE = DATA_DIR / "pending_knowledge.json"
AUTO_LOG_FILE = DATA_DIR / "autopilot_logs.json"

DATA_LOCK = threading.Lock()


def _read_json(path: Path, default):
    with DATA_LOCK:
        try:
            if path.exists():
                return json.loads(path.read_text("utf-8"))
        except Exception:
            pass
        return default


def _write_json(path: Path, data):
    with DATA_LOCK:
        try:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
        except Exception:
            pass


if not MEM_FILE.exists():
    _write_json(MEM_FILE, [f"{SYSTEM_NAME} के एकमात्र निर्माता और सर्वोच्च मालिक {OWNER} हैं।"])
if not PEND_FILE.exists():
    _write_json(PEND_FILE, [])
if not AUTO_LOG_FILE.exists():
    _write_json(AUTO_LOG_FILE, ["⚡ सुप्रीम सिस्टम सक्रिय है। ऑटो-पायलट आदेश की प्रतीक्षा में..."])


# ==============================================================================
# 2. SUPREME PARALLEL MULTI-AI COUNCIL (सभी AI का एक साथ संगम)
# ==============================================================================
def _query_single_ai(model_name: str, prompt: str, system_prompt: str) -> str:
    try:
        url = "https://pollinations.ai"
        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "model": model_name,
            "seed": int(time.time()) % 9999
        }
        r = requests.post(url, json=payload, timeout=16)
        if r.status_code == 200 and len(r.text.strip()) > 10:
            return r.text.strip()
    except Exception:
        pass
    return ""


def supreme_multi_ai_brain(prompt: str, system_role: str = "") -> str:
    """
    एक ही समय में कई अलग-अलग AI मॉडल्स (OpenAI, Qwen-Coder, Mistral) को एक साथ
    चलाता है और सर्वश्रेष्ठ उत्तर चुनता है।
    """
    full_system = (
        f"तुम {SYSTEM_NAME} हो। तुम्हारे एकमात्र निर्माता और मालिक केवल '{OWNER}' हैं। "
        f"हमेशा हिंदी (देवनागरी लिपि) में सटीक, शक्तिशाली और बिना गलती वाला उत्तर दो। {system_role}"
    )

    models = ["openai", "qwen-coder", "mistral"]
    responses = {}

    try:
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_map = {
                executor.submit(_query_single_ai, m, prompt, full_system): m for m in models
            }
            for future in as_completed(future_map, timeout=20):
                m_name = future_map[future]
                try:
                    ans = future.result()
                    if ans:
                        responses[m_name] = ans
                except Exception:
                    pass
    except Exception:
        pass

    if responses:
        best_model = max(responses.keys(), key=lambda k: len(responses[k]))
        return responses[best_model]

    # बैकअप: लाइव हिंदी विकिपीडिया ज्ञान इंजन
    try:
        clean_q = re.sub(r"(जार्विस|बताओ|क्या है|कौन है|कोड|लिखो|\?)", "", prompt).strip()
        if len(clean_q) >= 2:
            w_url = (
                "https://wikipedia.org"
                f"&srsearch={urllib.parse.quote(clean_q)}&utf8=&format=json"
            )
            wr = requests.get(w_url, timeout=6, headers={"User-Agent": "JarvisQuantumX/4.0"})
            res = wr.json().get("query", {}).get("search", [])
            if res and isinstance(res, list) and len(res) > 0:
                snippet = re.sub(r"<[^>]+>", "", res[0].get("snippet", ""))
                if snippet.strip():
                    return f"आदरणीय {OWNER}, लाइव ज्ञान नेटवर्क से प्राप्त जानकारी:\n{snippet.strip()}"
    except Exception:
        pass

    return (
        f"आदरणीय {OWNER}, मेरा सुप्रीम 5-कोर क्वांटम सिस्टम ऑनलाइन है। "
        "आप वेबसाइट स्कैन ('स्कैन google.com'), कोडिंग या कोई भी शोध आदेश दे सकते हैं।"
    )


# ==============================================================================
# 3. REAL ETHICAL SECURITY AUDITOR (असली दूरस्थ वेबसाइट सुरक्षा स्कैनर)
# ==============================================================================
def real_security_audit(raw_url: str) -> str:
    target = raw_url.strip().rstrip(".,;:)")
    if not target.startswith(("http://", "https://")):
        target = "https://" + target
    parsed = urllib.parse.urlparse(target)
    host = parsed.hostname
    if not host:
        return f"क्षमा करें {OWNER}, कृपया एक मान्य वेबसाइट का नाम या लिंक दें।"

    findings = []
    fixes = []
    score = 100

    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=6) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
                ver = ssock.version()
                not_after = cert.get("notAfter", "")
                findings.append(f"✅ SSL/TLS एनक्रिप्शन सक्रिय ({ver} | वैधता: {not_after})")
    except Exception:
        score -= 35
        findings.append("🔴 SSL/TLS प्रमाणपत्र अनुपस्थित या असुरक्षित")
        fixes.append("तुरंत वैध HTTPS (SSL/TLS) प्रमाणपत्र लागू करें।")

    try:
        resp = requests.get(target, timeout=8, headers={"User-Agent": "Jarvis-Ethical-Auditor/4.0"})
        hdrs = {k.lower(): v for k, v in resp.headers.items()}
        checks = [
            ("strict-transport-security", "HSTS हेडर अनुपस्थित (MITM खतरा)", "Strict-Transport-Security हेडर जोड़ें।", 15),
            ("content-security-policy", "CSP नीति अनुपस्थित (XSS खतरा)", "Content-Security-Policy लागू करें।", 20),
            ("x-frame-options", "X-Frame-Options अनुपस्थित (Clickjacking खतरा)", "X-Frame-Options: DENY सेट करें।", 15),
            ("x-content-type-options", "nosniff सुरक्षा हेडर अनुपस्थित", "X-Content-Type-Options: nosniff जोड़ें।", 10)
        ]
        for key, warn, fix, penalty in checks:
            if key not in hdrs:
                score -= penalty
                findings.append(f"🟠 {warn}")
                fixes.append(fix)
            else:
                findings.append(f"✅ {key.upper()} सुरक्षित है।")
    except Exception as e:
        findings.append(f"⚠️ रिमोट सर्वर संपर्क सीमा: {str(e)[:70]}")

    score = max(0, score)
    fix_block = "\n  • ".join(fixes) if fixes else "सभी प्रमुख सुरक्षा कवच मजबूत पाए गए हैं!"
    return (
        f"🛡️ **[Ethical Security Auditor — वास्तविक स्कैन रिपोर्ट: `{host}`]**\n\n"
        f"**सुरक्षा स्कोर:** `{score}/100`\n\n"
        f"**जाँच परिणाम:**\n  • " + "\n  • ".join(findings) + "\n\n"
        f"**सुरक्षा कवच सुधार उपाय:**\n  • {fix_block}"
    )


# ==============================================================================
# 4. AUTONOMOUS BACKGROUND ENGINE (टेबल पर रखे-रखे खुद काम व सीखने वाला इंजन)
# ==============================================================================
AUTOPILOT_STATE = {
    "running": False,
    "mission": "आधुनिक साइबर सुरक्षा और AI कोडिंग तकनीकों पर शोध"
}


def _add_auto_log(msg: str):
    logs = _read_json(AUTO_LOG_FILE, [])
    ts = datetime.now().strftime("%H:%M:%S")
    logs.append(f"[{ts}] {msg}")
    _write_json(AUTO_LOG_FILE, logs[-15:])


def _stage_pending(fact: str):
    pend = _read_json(PEND_FILE, [])
    mem = _read_json(MEM_FILE, [])
    clean = fact.strip()[:600]
    if clean and clean not in pend and clean not in mem and len(pend) < 20:
        pend.append(clean)
        _write_json(PEND_FILE, pend)


def autopilot_worker():
    sub_tasks = [
        "वेबसाइट को XSS और SQL Injection से बचाने के सबसे आधुनिक उपाय",
        "Python में सुरक्षित और तेज़ मल्टी-एजेंट AI बनाने की तकनीक",
        "फिशिंग और साइबर धोखाधड़ी पहचानने के 3 मुख्य नियम",
        "जीरो-ट्रस्ट साइबर सिक्योरिटी आर्किटेक्चर के सिद्धांत"
    ]
    idx = 0
    while True:
        if AUTOPILOT_STATE["running"]:
            mission = AUTOPILOT_STATE["mission"]
            topic = f"{mission} — {sub_tasks[idx % len(sub_tasks)]}"
            idx += 1
            _add_auto_log(f"🧭 [Planner]: स्वायत्त शोध शुरू -> '{topic[:45]}...'")
            thought = supreme_multi_ai_brain(
                f"इस विषय पर 2-3 पंक्तियों में सबसे उपयोगी और सटीक तकनीकी ज्ञान दो: {topic}",
                "तुम एक स्वायत्त AI शोधकर्ता हो। सीधे तथ्य दो।"
            )
            if thought and len(thought) > 20 and "ऑनलाइन है" not in thought:
                _stage_pending(thought)
                _add_auto_log("🧠 [Self-Learning]: नया ज्ञान खोजा गया और मास्टर अरुण कुमार की अनुमति हेतु Pending में रखा गया।")
        time.sleep(30)


threading.Thread(target=autopilot_worker, daemon=True).start()


# ==============================================================================
# 5. 5-CORE COUNCIL & COMMAND PROCESSOR
# ==============================================================================
def get_pending_text() -> str:
    pend = _read_json(PEND_FILE, [])
    mem = _read_json(MEM_FILE, [])
    if not pend:
        return f"🟢 कोई नया ज्ञान अनुमति के लिए लंबित नहीं है। *(कुल स्थायी ज्ञान: {len(mem)})*"
    return (
        f"🧠 **{OWNER}, मैंने यह नया सीखा है, क्या मैं इसे अपने सिस्टम में जोड़ सकता हूँ?**\n\n"
        f"> {pend[0]}\n\n*(कुल लंबित: {len(pend)} • स्थायी मेमोरी: {len(mem)} • नीचे 'हाँ' या 'नहीं' दबाएं)*"
    )


def get_auto_logs() -> str:
    
