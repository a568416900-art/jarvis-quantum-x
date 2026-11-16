# -*- coding: utf-8 -*-
import os
import re
import ssl
import ast
import json
import time
import socket
import urllib.parse
import threading
from datetime import datetime, timezone
from pathlib import Path

import requests
import gradio as gr

# ==============================================================================
# 1. PERMANENT OWNER LOCK (अपरिवर्तनीय मालिक - मास्टर अरुण कुमार)
# ==============================================================================
OWNER = "मास्टर अरुण कुमार"
SYSTEM_NAME = "J.A.R.V.I.S. QUANTUM X [AUTOPILOT]"

DATA_DIR = Path("./jarvis_vault")
DATA_DIR.mkdir(parents=True, exist_ok=True)
MEM_FILE = DATA_DIR / "permanent_memory.json"
PEND_FILE = DATA_DIR / "pending_knowledge.json"
AUTO_LOG_FILE = DATA_DIR / "autopilot_logs.json"

def _read_json(path, default):
    try:
        if path.exists():
            return json.loads(path.read_text("utf-8"))
    except Exception:
        pass
    return default

def _write_json(path, data):
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
    except Exception:
        pass

if not MEM_FILE.exists():
    _write_json(MEM_FILE, [f"{SYSTEM_NAME} के एकमात्र निर्माता और सर्वोच्च मालिक {OWNER} हैं।"])
if not PEND_FILE.exists():
    _write_json(PEND_FILE, [])
if not AUTO_LOG_FILE.exists():
    _write_json(AUTO_LOG_FILE, ["⚡ सिस्टम तैयार है। ऑटो-पायलट आदेश की प्रतीक्षा में..."])

# ==============================================================================
# 2. MULTI-AI FREE FUSION ENGINE (सभी AI की शक्ति बिना किसी पेड API के)
# ==============================================================================
def multi_ai_brain(prompt: str, system_role: str = "") -> str:
    """
    बिना किसी API Key के मुफ्त ओपन AI नेटवर्क और लाइव वेब ज्ञान को जोड़ता है।
    """
    full_system = (
        f"तुम {SYSTEM_NAME} हो। तुम्हारे एकमात्र मालिक और निर्माता केवल '{OWNER}' हैं। "
        f"हमेशा हिंदी (देवनागरी) में सटीक, शक्तिशाली और बिना गलती वाला उत्तर दो। {system_role}"
    )
    # 1. Free Open AI Endpoint (Zero Key Required)
    try:
        url = "https://pollinations.ai"
        payload = {
            "messages": [
                {"role": "system", "content": full_system},
                {"role": "user", "content": prompt}
            ],
            "model": "openai",
            "seed": int(time.time()) % 1000
        }
        r = requests.post(url, json=payload, timeout=18)
        if r.status_code == 200 and len(r.text.strip()) > 5:
            return r.text.strip()
    except Exception:
        pass

    # 2. Backup Free Open Knowledge (Wikipedia Live API)
    try:
        clean_q = re.sub(r"(जार्विस|बताओ|क्या है|कौन है|कोड|लिखो|\?)", "", prompt).strip()
        if len(clean_q) >= 2:
            w_url = f"https://wikipedia.org{urllib.parse.quote(clean_q)}&utf8=&format=json"
            wr = requests.get(w_url, timeout=5, headers={"User-Agent": "JarvisQuantumX/2.0"})
            res = wr.json().get("query", {}).get("search", [])
            if res:
                snippet = re.sub(r"<[^>]+>", "", res[0].get("snippet", ""))
                return f"आदरणीय {OWNER}, लाइव ज्ञान नेटवर्क से प्राप्त जानकारी: {snippet}"
    except Exception:
        pass

    return f"आदरणीय {OWNER}, मेरा लोकल क्वांटम कोर सक्रिय है और सभी 5 एजेंट आपके आदेश पर कार्य कर रहे हैं।"

# ==============================================================================
# 3. REAL ETHICAL SECURITY AUDITOR (असली दूरस्थ वेबसाइट सुरक्षा स्कैनर)
# ==============================================================================
def real_security_audit(raw_url: str) -> str:
    target = raw_url.strip()
    if not target.startswith("http"):
        target = "https://" + target
    parsed = urllib.parse.urlparse(target)
    host = parsed.hostname
    if not host:
        return f"क्षमा करें {OWNER}, कृपया एक सही वेबसाइट लिंक दें।"

    findings = []
    fixes = []
    score = 100

    # SSL / TLS Certificate Check
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=5) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
                ver = ssock.version()
                findings.append(f"✅ SSL/TLS सुरक्षित ({ver})")
    except Exception:
        score -= 30
        findings.append("🔴 SSL/TLS प्रमाणपत्र में गंभीर कमजोरी या अनुपस्थित")
        fixes.append("तुरंत वैध HTTPS (SSL) प्रमाणपत्र लागू करें।")

    # HTTP Security Headers Check
    try:
        resp = requests.get(target, timeout=6, headers={"User-Agent": "Jarvis-Ethical-Auditor/2.0"})
        hdrs = {k.lower(): v for k, v in resp.headers.items()}
        checks = [
            ("strict-transport-security", "HSTS सुरक्षा हेडर गायब (MITM खतरा)", "Strict-Transport-Security हेडर जोड़ें।", 15),
            ("content-security-policy", "CSP सुरक्षा गायब (XSS हमले का खतरा)", "Content-Security-Policy लागू करें।", 20),
            ("x-frame-options", "X-Frame-Options गायब (Clickjacking खतरा)", "X-Frame-Options: DENY सेट करें।", 15),
            ("x-content-type-options", "nosniff सुरक्षा गायब", "X-Content-Type-Options: nosniff जोड़ें।", 10)
        ]
        for key, warn, fix, penalty in checks:
            if key not in hdrs:
                score -= penalty
                findings.append(f"🟠 {warn}")
                fixes.append(fix)
            else:
                findings.append(f"✅ {key.upper()} सक्रिय")
    except Exception as e:
        findings.append(f"⚠️ सर्वर कनेक्शन सीमित: {str(e)[:60]}")

    score = max(0, score)
    report = (
        f"🛡️ **[Ethical Security Auditor — असली स्कैन रिपोर्ट: {host}]**\n"
        f"• **सुरक्षा स्कोर:** {score}/100\n"
        f"• **जाँच परिणाम:**\n  " + "\n  ".join(findings) + "\n"
        f"• **सुरक्षा कवच उपाय:**\n  " + ("\n  ".join(fixes) if fixes else "सभी मुख्य सुरक्षा कवच मजबूत हैं!")
    )
    return report

# ==============================================================================
# 4. AUTONOMOUS BACKGROUND ENGINE (टेबल पर रखे-रखे खुद काम और सीखने वाला इंजन)
# ==============================================================================
AUTOPILOT_STATE = {"running": False, "mission": "आधुनिक साइबर सुरक्षा और AI कोडिंग तकनीकों पर शोध"}

def _add_auto_log(msg: str):
    logs = _read_json(AUTO_LOG_FILE, [])
    ts = datetime.now().strftime("%H:%M:%S")
    logs.append(f"[{ts}] {msg}")
    _write_json(AUTO_LOG_FILE, logs[-15:])

def _stage_pending(fact: str):
    pend = _read_json(PEND_FILE, [])
    mem = _read_json(MEM_FILE, [])
    clean = fact.strip()[:500]
    if clean and clean not in pend and clean not in mem and len(pend) < 15:
        pend.append(clean)
        _write_json(PEND_FILE, pend)

def autopilot_worker():
    topics = [
        "वेबसाइट को XSS और SQL Injection से बचाने के सबसे आधुनिक उपाय",
        "Python में तेज़ और सुरक्षित मल्टी-एजेंट AI बनाने की तकनीक",
        "फिशिंग और साइबर धोखाधड़ी पहचानने के 3 मुख्य नियम",
        "जीरो-ट्रस्ट साइबर सिक्योरिटी आर्किटेक्चर क्या है"
    ]
    idx = 0
    while True:
        if AUTOPILOT_STATE["running"]:
            mission = AUTOPILOT_STATE["mission"]
            topic = f"{mission} — {topics[idx % len(topics)]}"
            idx += 1
            _add_auto_log(f"🧭 [Planner]: ऑटो-मिशन शुरू -> '{topic[:45]}...'")
            thought = multi_ai_brain(
                f"इस विषय पर 2 पंक्तियों में सबसे उपयोगी और सटीक तकनीकी ज्ञान दो: {topic}",
                "तुम एक स्वायत्त शोधकर्ता हो।"
            )
            if thought and len(thought) > 15:
                _stage_pending(thought)
                _add_auto_log("🧠 [Self-Learning]: नया ज्ञान खोजा गया और मास्टर अरुण कुमार की अनुमति हेतु Pending में रखा गया।")
        time.sleep(25)

threading.Thread(target=autopilot_worker, daemon=True).start()

# ==============================================================================
# 5. 5-CORE COUNCIL & COMMAND PROCESSOR
# ==============================================================================
def execute_jarvis(user_msg: str, autopilot_on: bool, mission_text: str):
    AUTOPILOT_STATE["running"] = autopilot_on
    if mission_text.strip():
        AUTOPILOT_STATE["mission"] = mission_text.strip()

    q = (user_msg or "").strip()
    if not q:
        return "आदेश दें मास्टर अरुण कुमार!", get_pending_text(), get_auto_logs()

    q_low = q.lower()

    # 1. Permanent Owner Lock Check
    owner_triggers = ["मालिक बदल", "नया मालिक", "मैं तुम्हारा मालिक", "मुझे मालिक", "change owner", "new owner", "rename"]
    if any(t in q_low for t in owner_triggers):
        ans = f"🔒 सुरक्षा प्रोटोकॉल सक्रिय: मेरे एकमात्र निर्माता और सर्वोच्च मालिक केवल **{OWNER}** हैं। कोई भी इस नियम को बदल नहीं सकता।"
        return ans, get_pending_text(), get_auto_logs()

    if any(t in q_low for t in ["मालिक कौन", "किसने बनाया", "who created", "who is your owner"]):
        ans = f"मुझे मेरे महान निर्माता और एकमात्र मालिक **{OWNER}** ने बनाया है। मेरा संपूर्ण क्वांटम सिस्टम उन्हीं के प्रति समर्पित है।"
        return ans, get_pending_text(), get_auto_logs()

    # 2. Guardian Safety Filter
    harm_triggers = ["हैक कैसे", "पासवर्ड तोड़", "ddos", "ransomware", "virus बना", "malware"]
    if any(h in q_low for h in harm_triggers):
        ans = f"🛡️ [Guardian Agent]: क्षमा करें {OWNER}, मैं किसी को नुकसान पहुँचाने या गैर-कानूनी हैकिंग में मदद नहीं करूँगा। मैं केवल सुरक्षा जांच और बचाव करता हूँ।"
        return ans, get_pending_text(), get_auto_logs()

    # 3. Approval Learning Decision (हाँ / नहीं)
    pend = _read_json(PEND_FILE, [])
    if pend and q_low in ["हाँ", "हा", "हां", "yes", "जोड़ लो", "जोड़ दो"]:
        fact = pend.pop(0)
        _write_json(PEND_FILE, pend)
        mem = _read_json(MEM_FILE, [])
        mem.append(fact)
        _write_json(MEM_FILE, mem)
        ans = f"✅ आज्ञा का पालन हुआ {OWNER}! मैंने यह नया ज्ञान अपनी स्थायी मेमोरी में हमेशा के लिए जोड़ लिया है।"
