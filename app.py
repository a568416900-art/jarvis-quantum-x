import gradio as gr
import json
import os

KNOWLEDGE_FILE = "knowledge_base.json"
PENDING_FILE = "pending_knowledge.json"

def init_db():
    if not os.path.exists(KNOWLEDGE_FILE):
        with open(KNOWLEDGE_FILE, "w", encoding="utf-8") as f:
            json.dump({"owner": "मास्टर अरुण कुमार", "facts": []}, f)
    if not os.path.exists(PENDING_FILE):
        with open(PENDING_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)

init_db()

def jarvis_core_engine(user_input):
    owner_name = "मास्टर अरुण कुमार"
    lower_input = user_input.lower()
    
    # Permanent Owner Lock
    if any(k in lower_input for k in ["owner", "creator", "who made you", "maalik", "malik", "kaun ho"]):
        return f"बॉस, मेरे एकमात्र निर्माता और स्थायी मालिक सिर्फ **{owner_name}** हैं।"

    # Approval Learning
    if lower_input.startswith("learn:"):
        new_fact = user_input[6:].strip()
        with open(PENDING_FILE, "r", encoding="utf-8") as f:
            pending = json.load(f)
        pending.append(new_fact)
        with open(PENDING_FILE, "w", encoding="utf-8") as f:
            json.dump(pending, f, ensure_ascii=False)
        return f"मास्टर अरुण कुमार, मैंने यह नया सीखा है: '{new_fact}'। क्या मैं इसे अपने सिस्टम में हमेशा के लिए जोड़ सकता हूँ? (हाँ / ना कहें)"

    if lower_input in ["हाँ", "han", "yes", "ha"]:
        with open(PENDING_FILE, "r", encoding="utf-8") as f:
            pending = json.load(f)
        if pending:
            latest = pending.pop()
            with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
                kb = json.load(f)
            kb["facts"].append(latest)
            with open(KNOWLEDGE_FILE, "w", encoding="utf-8") as f:
                json.dump(kb, f, ensure_ascii=False)
            with open(PENDING_FILE, "w", encoding="utf-8") as f:
                json.dump(pending, f, ensure_ascii=False)
            return f"शुक्रिया मास्टर अरुण कुमार! मैंने इस नए ज्ञान को अपनी स्थायी मेमोरी में सुरक्षित जोड़ लिया है।"
        else:
            return "बॉस, अभी कोई भी नया ज्ञान पेंडिंग लिस्ट में नहीं है।"

    if lower_input in ["ना", "na", "no", "nahi"]:
        with open(PENDING_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
        return "ठीक है मास्टर अरुण कुमार, मैंने उस नए ज्ञान को हटा दिया है।"

    # 5-Core Simulation & General Intelligence
    if "audit" in lower_input or "scan" in lower_input:
        return f"[Ethical Security Auditor Agent]: सुरक्षित दूरस्थ विश्लेषण सक्रिय। मास्टर अरुण कुमार, टार्गेटेड लिंक की सुरक्षा कमजोरियों की जांच की जा रही है।"
    
    if "code" in lower_input or "script" in lower_input:
        return f"[Coder & Critic Agent]: मास्टर अरुण कुमार, आपके निर्देशानुसार ऑप्टिमाइज्ड पाइथन कोड तैयार है और Critic एजेंट द्वारा जांच लिया गया है।"

    return f"मास्टर अरुण कुमार, आपका हर आदेश सर्वोपरि है। 5-कोर क्वांटम सिस्टम पूरी ताकत से ऑनलाइन है।"

# HTML + Three.js Hologram UI
html_code = """
<!DOCTYPE html>
<html lang="hi">
<head>
    <meta charset="UTF-8">
    <title>J.A.R.V.I.S. Quantum X</title>
    <style>
        body { margin: 0; background: #030712; color: #00f3ff; font-family: 'Segoe UI', monospace; overflow: hidden; }
        #canvas-container { position: absolute; top: 0; left: 0; width: 100vw; height: 100vh; z-index: 1; pointer-events: none; }
        .ui-layer { position: relative; z-index: 10; display: flex; flex-direction: column; height: 100vh; padding: 20px; box-sizing: border-box; background: rgba(3, 7, 18, 0.85); }
        header { text-align: center; font-size: 18px; font-weight: bold; letter-spacing: 2px; border-bottom: 2px solid #00f3ff; padding-bottom: 10px; text-shadow: 0 0 10px #00f3ff; }
        #chat-box { flex: 1; overflow-y: auto; margin: 15px 0; padding: 10px; border: 1px solid #1e3a8a; background: rgba(15, 23, 42, 0.6); display: flex; flex-direction: column; gap: 10px; border-radius: 8px; }
        .msg { padding: 12px 16px; border-radius: 8px; max-width: 80%; line-height: 1.5; font-size: 14px; }
        .user { align-self: flex-end; background: #0284c7; color: #fff; border-right: 4px solid #38bdf8; }
        .bot { align-self: flex-start; background: #1e293b; color: #38bdf8; border-left: 4px solid #00f3ff; box-shadow: 0 0 10px rgba(0,243,255,0.2); }
        .input-group { display: flex; gap: 10px; }
        input { flex: 1; padding: 14px; background: #020617; border: 1px solid #00f3ff; color: #00f3ff; font-size: 16px; outline: none; border-radius: 6px; }
        button { padding: 14px 24px; background: #00f3ff; color: #020617; font-weight: bold; border: none; cursor: pointer; border-radius: 6px; box-shadow: 0 0 15px #00f3ff; }
        .mic-btn { background: #ff0055; color: #fff; box-shadow: 0 0 15px #ff0055; }
    </style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
</head>
<body>
    <div id="canvas-container"></div>
    <div class="ui-layer">
        <header>⚡ J.A.R.V.I.S. QUANTUM X // मास्टर अरुण कुमार कमांड सेंटर</header>
        <div id="chat-box">
            <div class="msg bot">जर्वीस क्वांटम एक्स ऑनलाइन है। मास्टर अरुण कुमार, आपका स्वागत है!</div>
        </div>
        <div class="input-group">
            <button class="mic-btn" onclick="startVoice()">🎤 माइक</button>
            <input type="text" id="user-input" placeholder="यहाँ अपना आदेश लिखें..." onkeypress="if(event.key==='Enter')sendMessage()">
            <button onclick="sendMessage()">एक्जीक्यूट</button>
        </div>
    </div>
    <script>
        const container = document.getElementById('canvas-container');
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
        const renderer = new THREE.WebGLRenderer({ alpha: true });
        renderer.setSize(window.innerWidth, window.innerHeight);
        container.appendChild(renderer.domElement);
        const geometry = new THREE.IcosahedronGeometry(2, 1);
        const material = new THREE.MeshBasicMaterial({ color: 0x00f3ff, wireframe: true });
        const sphere = new THREE.Mesh(geometry, material);
        scene.add(sphere);
        camera.position.z = 5;
        function animate() {
            requestAnimationFrame(animate);
            sphere.rotation.x += 0.005;
            sphere.rotation.y += 0.005;
            renderer.render(scene, camera);
        }
        animate();

        function speak(text) {
            if ('speechSynthesis' in window) {
                window.speechSynthesis.cancel();
                const utterance = new SpeechSynthesisUtterance(text.replace(/[*#_]/g, ''));
                utterance.lang = 'hi-IN';
                window.speechSynthesis.speak(utterance);
            }
        }

        function startVoice() {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SpeechRecognition) { alert("ब्राउज़र वॉइस सपोर्ट नहीं करता।"); return; }
            const recognition = new SpeechRecognition();
            recognition.lang = 'hi-IN';
            recognition.onresult = function(event) {
                document.getElementById('user-input').value = event.results[0][0].transcript;
                sendMessage();
            };
            recognition.start();
        }

        async function sendMessage() {
            const inputField = document.getElementById('user-input');
            const text = inputField.value.trim();
            if (!text) return;
            const chatBox = document.getElementById('chat-box');
            chatBox.innerHTML += `<div class="msg user">${text}</div>`;
            inputField.value = '';
            chatBox.scrollTop = chatBox.scrollHeight;

            try {
                const response = await fetch('/run/predict', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ data: [text] })
                });
                const result = await response.json();
                const botReply = result.data[0];
                chatBox.innerHTML += `<div class="msg bot">${botReply}</div>`;
                chatBox.scrollTop = chatBox.scrollHeight;
                speak(botReply);
            } catch (err) {
                chatBox.innerHTML += `<div class="msg bot">सिस्टम त्रुटि: कनेक्शन विफल।</div>`;
            }
        }
    </script>
</body>
</html>
"""

with gr.Blocks() as demo:
    gr.HTML(html_code)
    txt_in = gr.Textbox(visible=False)
    txt_out = gr.Textbox(visible=False)
    txt_in.submit(jarvis_core_engine, inputs=txt_in, outputs=txt_out)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    demo.launch(server_name="0.0.0.0", server_port=port, share=False)
