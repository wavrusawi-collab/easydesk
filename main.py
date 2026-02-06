import sys
import os
import json
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal, Qt

class Bridge(QObject):
    loginSuccess = pyqtSignal(str)
    loadFiles = pyqtSignal(str)
    allUsers = pyqtSignal(str)

    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.base_dir = Path("data")
        self.base_dir.mkdir(exist_ok=True)
        self.users_file = Path("users.json")
        self.current_user = None

    @pyqtSlot(str, str)
    def handleLogin(self, username, password):
        users = {}
        if self.users_file.exists():
            with open(self.users_file, 'r') as f:
                try: users = json.load(f)
                except: users = {}
        if username in users:
            if users[username] == password: self.start_session(username)
        else:
            users[username] = password
            with open(self.users_file, 'w') as f: json.dump(users, f)
            self.start_session(username)

    def start_session(self, username):
        self.current_user = username
        (self.base_dir / username).mkdir(exist_ok=True)
        self.loginSuccess.emit(username)
        self.refreshFiles()
        self.getOtherUsers()

    def getOtherUsers(self):
        if self.users_file.exists():
            with open(self.users_file, 'r') as f:
                users = json.load(f)
                others = [u for u in users.keys() if u != self.current_user]
                self.allUsers.emit(json.dumps(others))

    @pyqtSlot()
    def refreshFiles(self):
        if not self.current_user: return
        user_dir = self.base_dir / self.current_user
        files = []
        ext_map = {'.md': 'diary', '.json': 'tasks', '.deck': 'flashcards', '.secret': 'secret', '.sketch': 'sketch'}
        for f in user_dir.glob("*"):
            ftype = ext_map.get(f.suffix)
            if not ftype: continue
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    content = json.load(file) if f.suffix in ['.json', '.deck', '.secret', '.sketch'] else file.read()
                files.append({"name": f.name, "content": content, "type": ftype})
            except: continue
        self.loadFiles.emit(json.dumps(files))

    @pyqtSlot(str, str, str)
    def saveFile(self, name, content, ftype):
        if not self.current_user: return
        exts = {"diary": ".md", "tasks": ".json", "flashcards": ".deck", "secret": ".secret", "sketch": ".sketch"}
        ext = exts.get(ftype, ".txt")
        if not name.endswith(ext): name += ext
        path = self.base_dir / self.current_user / name
        try:
            data = json.loads(content)
            with open(path, 'w', encoding='utf-8') as f: json.dump(data, f)
        except:
            with open(path, 'w', encoding='utf-8') as f: f.write(content)
        self.refreshFiles()

    @pyqtSlot(str)
    def deleteFile(self, filename):
        if not self.current_user: return
        path = self.base_dir / self.current_user / filename
        if path.exists(): os.remove(path)
        self.refreshFiles()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.showFullScreen()
        self.browser = QWebEngineView()
        self.channel = QWebChannel()
        self.bridge = Bridge(self)
        self.channel.registerObject('pybridge', self.bridge)
        self.browser.page().setWebChannel(self.channel)

        self.html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <script src="https://cdn.tailwindcss.com"></script>
            <script src="https://unpkg.com/lucide@latest"></script>
            <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
            <style>
                :root { --accent: #60a5fa; --glass: rgba(15, 23, 42, 0.85); }
                body { 
                    background: #020617; 
                    height: 100vh; overflow: hidden; font-family: 'Inter', sans-serif; color: white;
                }
                
                .mesh-container {
                    position: fixed; inset: -10%; width: 120%; height: 120%;
                    background: radial-gradient(circle at center, #1e1b4b 0%, #020617 100%);
                    z-index: -1; transition: transform 0.2s ease-out;
                }
                .mesh-glow {
                    position: absolute; width: 40%; height: 40%;
                    background: radial-gradient(circle, rgba(99, 102, 241, 0.2) 0%, transparent 70%);
                    filter: blur(80px);
                }

                .hide { display: none !important; }
                
                .app-shell {
                    position: fixed; inset: 8%;
                    background: var(--glass);
                    backdrop-filter: blur(60px) saturate(180%);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 5rem;
                    display: flex; flex-direction: column;
                    box-shadow: 0 50px 100px rgba(0,0,0,0.9);
                    z-index: 1000; transform: scale(0.7) translateY(50px); opacity: 0; pointer-events: none;
                    transition: all 0.6s cubic-bezier(0.16, 1, 0.3, 1);
                }
                .app-shell.active { transform: scale(1) translateY(0); opacity: 1; pointer-events: auto; }

                .orb-launcher {
                    position: fixed; bottom: 3rem; left: 50%; transform: translateX(-50%);
                    display: flex; gap: 1.5rem; padding: 1.2rem;
                    background: rgba(255, 255, 255, 0.05); border-radius: 5rem;
                    backdrop-filter: blur(20px); border: 1px solid rgba(255, 255, 255, 0.1);
                    z-index: 2000; transition: transform 0.4s;
                }

                .orb {
                    width: 4rem; height: 4rem; border-radius: 50%;
                    display: flex; align-items: center; justify-content: center;
                    cursor: pointer; transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
                }
                .orb:hover { transform: translateY(-1.5rem) scale(1.2); filter: brightness(1.3); }

                /* Physics Nodes Container */
                .node-wrapper {
                    position: absolute; width: 8rem; height: 8rem;
                    z-index: 10; pointer-events: auto;
                    will-change: transform;
                }
                
                .node {
                    width: 100%; height: 100%; border-radius: 50%;
                    background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.08);
                    display: flex; flex-direction: column; align-items: center; justify-content: center;
                    cursor: pointer;
                    transition: background 0.4s, border-color 0.4s, transform 0.6s cubic-bezier(0.16, 1, 0.3, 1);
                }
                
                /* Applying scale to the inner element ONLY */
                .node-wrapper:hover .node { 
                    background: rgba(255, 255, 255, 0.12); 
                    border-color: var(--accent); 
                    transform: scale(1.15); 
                }
                .node-wrapper:hover { z-index: 20; }
                
                .node span { font-size: 0.7rem; margin-top: 0.6rem; max-width: 80%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; opacity: 0.6; }

                input, textarea { background: transparent; border: none; outline: none; color: white; }
                .btn-primary { background: var(--accent); color: white; padding: 1rem 2rem; border-radius: 2rem; font-weight: 700; transition: all 0.3s; }
                
                canvas { background: transparent; cursor: crosshair; touch-action: none; display: block; }
                .app-body { overflow-y: auto; flex: 1; padding: 2rem; }
            </style>
        </head>
        <body>
            <div id="bg" class="mesh-container">
                <div class="mesh-glow" style="top: 20%; left: 20%;"></div>
                <div class="mesh-glow" style="bottom: 10%; right: 10%; background: radial-gradient(circle, rgba(236, 72, 153, 0.15) 0%, transparent 70%);"></div>
            </div>
            
            <div id="constellation" class="fixed inset-0 pointer-events-none"></div>

            <div id="screen-login" class="fixed inset-0 flex items-center justify-center z-[5000]">
                <div class="text-center space-y-12">
                    <h1 class="text-7xl font-thin tracking-[0.6em] uppercase opacity-90">EasyDesk</h1>
                    <div class="space-y-4">
                        <input id="u" type="text" placeholder="IDENTITY" class="text-center w-80 p-5 border-b border-white/5 text-2xl focus:border-white/40 transition-all uppercase tracking-widest">
                        <input id="p" type="password" placeholder="PHASE" class="text-center w-80 p-5 block mx-auto border-b border-white/5 text-2xl focus:border-white/40 transition-all uppercase tracking-widest">
                    </div>
                    <button onclick="login()" class="text-xs tracking-[0.5em] opacity-30 hover:opacity-100 transition-all cursor-pointer">START_SEQUENCE</button>
                </div>
            </div>

            <div id="screen-home" class="hide">
                <div class="orb-launcher">
                    <div class="orb bg-blue-500/20 text-blue-300" onclick="openApp('diary')"><i data-lucide="edit-3"></i></div>
                    <div class="orb bg-yellow-500/20 text-yellow-300" onclick="openApp('tasks')"><i data-lucide="check-circle"></i></div>
                    <div class="orb bg-orange-500/20 text-orange-300" onclick="openApp('sketch')"><i data-lucide="palette"></i></div>
                    <div class="orb bg-red-950/40 text-red-400" onclick="signOut()"><i data-lucide="power"></i></div>
                </div>
            </div>

            <div id="app-shell" class="app-shell">
                <div class="p-16 flex-1 flex flex-col overflow-hidden">
                    <div id="header-diary" class="app-header hide flex items-center gap-8 mb-12">
                        <input id="d-name" type="text" placeholder="New Thought" class="text-5xl font-light flex-1">
                        <button onclick="saveDiary()" class="btn-primary">Preserve</button>
                        <button onclick="closeApp()" class="w-12 h-12 flex items-center justify-center rounded-full bg-white/5 hover:bg-white/10"><i data-lucide="x"></i></button>
                    </div>
                    <div id="header-tasks" class="app-header hide flex items-center gap-8 mb-12">
                        <input id="t-name" type="text" placeholder="Objectives" class="text-5xl font-light flex-1">
                        <button onclick="addTaskRow()" class="px-6 py-3 border border-white/10 rounded-full hover:bg-white/5">+ Task</button>
                        <button onclick="saveTasks()" class="btn-primary">Sync</button>
                        <button onclick="closeApp()" class="w-12 h-12 flex items-center justify-center rounded-full bg-white/5 hover:bg-white/10"><i data-lucide="x"></i></button>
                    </div>
                    <div id="header-sketch" class="app-header hide flex items-center gap-8 mb-12">
                        <input id="sk-name" type="text" placeholder="Visual Capture" class="text-5xl font-light flex-1">
                        <div class="flex items-center gap-6 bg-white/5 px-6 py-3 rounded-full">
                            <input id="sk-color" type="color" value="#60a5fa" class="w-8 h-8 bg-transparent cursor-pointer">
                            <input id="sk-size" type="range" min="1" max="100" value="5" class="w-32 accent-blue-400">
                        </div>
                        <button onclick="saveSketch()" class="btn-primary">Capture</button>
                        <button onclick="closeApp()" class="w-12 h-12 flex items-center justify-center rounded-full bg-white/5 hover:bg-white/10"><i data-lucide="x"></i></button>
                    </div>

                    <div id="body-diary" class="app-body hide">
                        <textarea id="d-body" class="w-full h-full text-2xl leading-relaxed placeholder:opacity-5 resize-none" placeholder="Empty space..."></textarea>
                    </div>
                    <div id="body-tasks" class="app-body hide space-y-4">
                        <div id="t-container" class="space-y-4"></div>
                    </div>
                    <div id="body-sketch" class="app-body hide relative rounded-[3rem] overflow-hidden bg-black/40 border border-white/10">
                        <canvas id="sk-canvas"></canvas>
                    </div>
                </div>
            </div>

            <script>
                let pybridge;
                let activeApp = null;
                const canvas = document.getElementById('sk-canvas');
                let ctx, drawing = false;
                
                let nodes = [];
                let animationFrameId = null;

                // Parallax Background Effect
                window.addEventListener('mousemove', (e) => {
                    if (activeApp) return;
                    const x = (e.clientX / window.innerWidth - 0.5) * 30;
                    const y = (e.clientY / window.innerHeight - 0.5) * 30;
                    document.getElementById('bg').style.transform = `translate(${x}px, ${y}px)`;
                });

                new QWebChannel(qt.webChannelTransport, function(channel) {
                    pybridge = channel.objects.pybridge;
                    pybridge.loginSuccess.connect((u) => {
                        document.getElementById('screen-login').classList.add('hide');
                        document.getElementById('screen-home').classList.remove('hide');
                        startDrift(); // Restored drift loop start
                    });
                    pybridge.loadFiles.connect((json) => {
                        renderConstellation(JSON.parse(json));
                    });
                });

                function login() { pybridge.handleLogin(document.getElementById('u').value, document.getElementById('p').value); }

                function signOut() {
                    document.getElementById('screen-login').classList.remove('hide');
                    document.getElementById('screen-home').classList.add('hide');
                    document.getElementById('constellation').innerHTML = '';
                    nodes = [];
                    if (animationFrameId) cancelAnimationFrame(animationFrameId);
                    document.getElementById('u').value = '';
                    document.getElementById('p').value = '';
                }

                function renderConstellation(files) {
                    const container = document.getElementById('constellation');
                    container.innerHTML = '';
                    nodes = [];
                    
                    files.forEach((f, i) => {
                        const wrapper = document.createElement('div');
                        wrapper.className = 'node-wrapper';
                        
                        const inner = document.createElement('div');
                        inner.className = 'node';
                        
                        const nodeData = {
                            el: wrapper,
                            x: Math.random() * (window.innerWidth - 200) + 50,
                            y: Math.random() * (window.innerHeight - 200) + 50,
                            vx: (Math.random() - 0.5) * 0.5,
                            vy: (Math.random() - 0.5) * 0.5,
                            width: 128,
                            height: 128
                        };
                        
                        const icons = { diary: 'file-text', tasks: 'check-circle', sketch: 'image' };
                        inner.innerHTML = `<i data-lucide="${icons[f.type] || 'circle'}"></i><span>${f.name}</span>`;
                        wrapper.onclick = (e) => { e.stopPropagation(); loadFile(f); };
                        
                        wrapper.appendChild(inner);
                        container.appendChild(wrapper);
                        nodes.push(nodeData);
                    });
                    lucide.createIcons();
                }

                function startDrift() {
                    if (animationFrameId) cancelAnimationFrame(animationFrameId);
                    function update() {
                        if (activeApp === null) {
                            nodes.forEach(n => {
                                n.x += n.vx; n.y += n.vy;
                                // Bounce off edges
                                if (n.x <= 0 || n.x >= window.innerWidth - n.width) n.vx *= -1;
                                if (n.y <= 0 || n.y >= window.innerHeight - n.height) n.vy *= -1;
                                // Apply position to wrapper to avoid hover fight
                                n.el.style.transform = `translate3d(${n.x}px, ${n.y}px, 0)`;
                            });
                        }
                        animationFrameId = requestAnimationFrame(update);
                    }
                    update();
                }

                function openApp(appName) {
                    activeApp = appName;
                    document.getElementById('app-shell').classList.add('active');
                    document.querySelectorAll('.app-header, .app-body').forEach(el => el.classList.add('hide'));
                    document.getElementById('header-' + appName)?.classList.remove('hide');
                    document.getElementById('body-' + appName)?.classList.remove('hide');
                    if(appName === 'sketch') {
                        setTimeout(() => { resizeCanvas(); initSketch(); }, 100);
                    }
                }

                function closeApp() {
                    document.getElementById('app-shell').classList.remove('active');
                    activeApp = null;
                }

                function loadFile(file) {
                    openApp(file.type);
                    if(file.type === 'diary') {
                        document.getElementById('d-name').value = file.name.replace('.md','');
                        document.getElementById('d-body').value = file.content;
                    } else if(file.type === 'sketch') {
                        document.getElementById('sk-name').value = file.name.replace('.sketch','');
                        const img = new Image();
                        img.onload = () => ctx.drawImage(img, 0, 0);
                        img.src = file.content.image;
                    } else if(file.type === 'tasks') {
                        document.getElementById('t-name').value = file.name.replace('.json','');
                        document.getElementById('t-container').innerHTML = '';
                        file.content.forEach(t => addTaskRow(t.text, t.done));
                    }
                }

                function resizeCanvas() {
                    const parent = canvas.parentElement;
                    canvas.width = parent.clientWidth;
                    canvas.height = parent.clientHeight;
                }

                function initSketch() {
                    ctx = canvas.getContext('2d');
                    ctx.lineCap = 'round'; ctx.lineJoin = 'round';
                    canvas.onmousedown = (e) => { drawing = true; startPos(e); };
                    canvas.onmousemove = draw;
                    window.onmouseup = () => { drawing = false; ctx.beginPath(); };
                }

                function startPos(e) {
                    const rect = canvas.getBoundingClientRect();
                    ctx.beginPath();
                    ctx.moveTo(e.clientX - rect.left, e.clientY - rect.top);
                }

                function draw(e) {
                    if(!drawing) return;
                    const rect = canvas.getBoundingClientRect();
                    ctx.lineWidth = document.getElementById('sk-size').value;
                    ctx.strokeStyle = document.getElementById('sk-color').value;
                    ctx.lineTo(e.clientX - rect.left, e.clientY - rect.top);
                    ctx.stroke();
                }

                function saveSketch() {
                    const data = canvas.toDataURL();
                    pybridge.saveFile(document.getElementById('sk-name').value || 'Snapshot', JSON.stringify({image:data}), 'sketch');
                    closeApp();
                }

                function saveDiary() {
                    pybridge.saveFile(document.getElementById('d-name').value || 'Thought', document.getElementById('d-body').value, 'diary');
                    closeApp();
                }

                function addTaskRow(text = "", done = false) {
                    const div = document.createElement('div');
                    div.className = "flex items-center gap-6 bg-white/5 p-6 rounded-[2rem] border border-white/5 hover:border-white/20 transition-all group";
                    div.innerHTML = `
                        <input type="checkbox" ${done ? 'checked' : ''} class="w-8 h-8 rounded-full border-2 border-white/10 appearance-none checked:bg-blue-400 checked:border-transparent transition-all cursor-pointer">
                        <input type="text" value="${text}" placeholder="Identity task..." class="flex-1 text-2xl font-light">
                        <button onclick="this.parentElement.remove()" class="opacity-0 group-hover:opacity-100 text-red-400 transition-opacity"><i data-lucide="trash-2"></i></button>
                    `;
                    document.getElementById('t-container').appendChild(div);
                    lucide.createIcons();
                }

                function saveTasks() {
                    const tasks = Array.from(document.querySelectorAll('#t-container > div')).map(div => ({
                        text: div.querySelector('input[type="text"]').value,
                        done: div.querySelector('input[type="checkbox"]').checked
                    }));
                    pybridge.saveFile(document.getElementById('t-name').value || 'Objectives', JSON.stringify(tasks), 'tasks');
                    closeApp();
                }

                lucide.createIcons();
            </script>
        </body>
        </html>
        """
        self.browser.setHtml(self.html_content)
        self.setCentralWidget(self.browser)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())