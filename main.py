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

    @pyqtSlot(str, str, str)
    def sendSecret(self, recipient, name, payload_json):
        dest_dir = self.base_dir / recipient
        if dest_dir.exists():
            with open(dest_dir / (name + ".secret"), 'w', encoding='utf-8') as f: f.write(payload_json)
        self.refreshFiles()

    @pyqtSlot(str)
    def deleteFile(self, filename):
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
                :root { --accent: #60a5fa; }
                body { 
                    background: radial-gradient(circle at center, #1e1b4b 0%, #020617 100%); 
                    height: 100vh; overflow: hidden; font-family: 'Inter', sans-serif; color: white;
                }
                
                /* Animated Background Mesh */
                .mesh {
                    position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                    background: radial-gradient(circle at 20% 30%, rgba(99, 102, 241, 0.15) 0%, transparent 40%),
                                radial-gradient(circle at 80% 70%, rgba(236, 72, 153, 0.1) 0%, transparent 40%);
                    z-index: -1; animation: meshFlow 20s infinite alternate;
                }
                @keyframes meshFlow { 0% { transform: scale(1); } 100% { transform: scale(1.2) rotate(5deg); } }

                .hide { display: none !important; }
                
                /* Orbital App Shell */
                .app-shell {
                    position: fixed; inset: 10%;
                    background: rgba(15, 23, 42, 0.6);
                    backdrop-filter: blur(40px) saturate(150%);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 4rem;
                    display: flex; flex-direction: column;
                    box-shadow: 0 0 100px rgba(0,0,0,0.5), inset 0 0 20px rgba(255,255,255,0.05);
                    z-index: 100; transform: scale(0.9); opacity: 0; pointer-events: none;
                    transition: all 0.6s cubic-bezier(0.16, 1, 0.3, 1);
                }
                .app-shell.active { transform: scale(1); opacity: 1; pointer-events: auto; }

                /* Floating Launcher Nodes */
                .orb-launcher {
                    position: fixed; bottom: 3rem; left: 50%; transform: translateX(-50%);
                    display: flex; gap: 1.5rem; padding: 1rem 2rem;
                    background: rgba(255, 255, 255, 0.05); border-radius: 3rem;
                    backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.1);
                }
                .orb {
                    width: 3.5rem; height: 3.5rem; border-radius: 50%;
                    display: flex; items-center; justify-content: center;
                    cursor: pointer; transition: all 0.3s;
                    box-shadow: 0 10px 20px rgba(0,0,0,0.2);
                }
                .orb:hover { transform: translateY(-1rem) scale(1.2); filter: brightness(1.2); }

                /* Constellation File Nodes */
                .node {
                    position: absolute; width: 6rem; height: 6rem; border-radius: 50%;
                    background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.1);
                    display: flex; flex-direction: column; align-items: center; justify-content: center;
                    cursor: pointer; transition: all 0.5s cubic-bezier(0.16, 1, 0.3, 1);
                    animation: float 10s infinite alternate ease-in-out;
                }
                .node:hover { background: rgba(255, 255, 255, 0.1); border-color: var(--accent); scale: 1.1; }
                .node span { font-size: 0.7rem; margin-top: 0.5rem; max-width: 80%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

                @keyframes float { 
                    0% { transform: translate(0, 0); } 
                    100% { transform: translate(20px, 30px); } 
                }

                input, textarea { background: transparent; border: none; outline: none; color: white; }
                .btn-primary { background: var(--accent); color: white; padding: 0.75rem 1.5rem; border-radius: 1.5rem; font-weight: 600; }
                
                canvas { background: transparent; cursor: crosshair; }
            </style>
        </head>
        <body>
            <div class="mesh"></div>

            <!-- Space for background nodes -->
            <div id="constellation" class="fixed inset-0 pointer-events-none"></div>

            <!-- Login: Centered Minimal -->
            <div id="screen-login" class="fixed inset-0 flex items-center justify-center">
                <div class="text-center space-y-8 animate-pulse">
                    <h1 class="text-5xl font-thin tracking-widest uppercase">EasyDesk</h1>
                    <div class="space-y-4">
                        <input id="u" type="text" placeholder="IDENTITY" class="text-center w-64 p-4 border-b border-white/20 text-xl focus:border-white transition-colors">
                        <input id="p" type="password" placeholder="PHASE" class="text-center w-64 p-4 block mx-auto border-b border-white/20 text-xl focus:border-white transition-colors">
                    </div>
                    <button onclick="login()" class="text-xs tracking-widest opacity-50 hover:opacity-100 transition-opacity">INITIALIZE SYSTEM</button>
                </div>
            </div>

            <!-- Spatial Launcher -->
            <div id="screen-home" class="hide">
                <div class="orb-launcher">
                    <div class="orb bg-blue-500/20 text-blue-400" onclick="openApp('diary')"><i data-lucide="edit-3"></i></div>
                    <div class="orb bg-yellow-500/20 text-yellow-400" onclick="openApp('tasks')"><i data-lucide="check-circle"></i></div>
                    <div class="orb bg-pink-500/20 text-pink-400" onclick="openApp('flashcards')"><i data-lucide="zap"></i></div>
                    <div class="orb bg-indigo-500/20 text-indigo-400" onclick="openApp('secret')"><i data-lucide="shield"></i></div>
                    <div class="orb bg-orange-500/20 text-orange-400" onclick="openApp('sketch')"><i data-lucide="palette"></i></div>
                    <div class="orb bg-white/5 text-white/40" onclick="location.reload()"><i data-lucide="power"></i></div>
                </div>
            </div>

            <!-- Unified App Shell -->
            <div id="app-shell" class="app-shell">
                <div class="p-12 flex-1 flex flex-col overflow-hidden">
                    <!-- App Headers -->
                    <div id="header-diary" class="app-header hide flex items-center gap-6 mb-8">
                        <input id="d-name" type="text" placeholder="Untitled Note" class="text-4xl font-light flex-1">
                        <button onclick="saveDiary()" class="btn-primary">Preserve</button>
                        <button onclick="closeApp()" class="opacity-30"><i data-lucide="circle-dashed"></i></button>
                    </div>
                    <div id="header-tasks" class="app-header hide flex items-center gap-6 mb-8">
                        <input id="t-name" type="text" placeholder="Objective Board" class="text-4xl font-light flex-1">
                        <button onclick="addTaskRow()" class="px-4 py-2 border border-white/10 rounded-xl">+ Task</button>
                        <button onclick="saveTasks()" class="btn-primary">Sync</button>
                        <button onclick="closeApp()" class="opacity-30"><i data-lucide="circle-dashed"></i></button>
                    </div>
                    <div id="header-sketch" class="app-header hide flex items-center gap-6 mb-8">
                        <input id="sk-name" type="text" placeholder="Visual Capture" class="text-4xl font-light flex-1">
                        <input id="sk-color" type="color" value="#60a5fa" class="w-10 h-10 bg-transparent">
                        <button onclick="saveSketch()" class="btn-primary">Snapshot</button>
                        <button onclick="closeApp()" class="opacity-30"><i data-lucide="circle-dashed"></i></button>
                    </div>

                    <!-- App Bodies -->
                    <div id="body-diary" class="app-body hide flex-1">
                        <textarea id="d-body" class="w-full h-full text-xl leading-relaxed placeholder:opacity-10" placeholder="Begin transmission..."></textarea>
                    </div>
                    <div id="body-tasks" class="app-body hide flex-1 overflow-y-auto space-y-4" id="t-container"></div>
                    <div id="body-sketch" class="app-body hide flex-1 relative rounded-3xl overflow-hidden bg-white/5">
                        <canvas id="sk-canvas" class="w-full h-full"></canvas>
                    </div>
                </div>
            </div>

            <script>
                let pybridge;
                let activeApp = null;
                const canvas = document.getElementById('sk-canvas');
                let ctx, drawing = false;

                new QWebChannel(qt.webChannelTransport, function(channel) {
                    pybridge = channel.objects.pybridge;
                    pybridge.loginSuccess.connect((u) => {
                        document.getElementById('screen-login').classList.add('hide');
                        document.getElementById('screen-home').classList.remove('hide');
                    });
                    pybridge.loadFiles.connect((json) => {
                        renderConstellation(JSON.parse(json));
                    });
                });

                function login() { pybridge.handleLogin(document.getElementById('u').value, document.getElementById('p').value); }

                function renderConstellation(files) {
                    const container = document.getElementById('constellation');
                    container.innerHTML = '';
                    files.forEach((f, i) => {
                        const node = document.createElement('div');
                        node.className = 'node pointer-events-auto';
                        // Random position in background
                        const x = 10 + Math.random() * 80;
                        const y = 10 + Math.random() * 60;
                        node.style.left = x + '%';
                        node.style.top = y + '%';
                        node.style.animationDelay = (i * -2) + 's';
                        
                        const icons = { diary: 'file-text', tasks: 'check-circle', sketch: 'image', flashcards: 'zap', secret: 'lock' };
                        node.innerHTML = `<i data-lucide="${icons[f.type] || 'circle'}"></i><span>${f.name}</span>`;
                        node.onclick = () => loadFile(f);
                        container.appendChild(node);
                    });
                    lucide.createIcons();
                }

                function openApp(appName) {
                    activeApp = appName;
                    document.getElementById('app-shell').classList.add('active');
                    document.querySelectorAll('.app-header, .app-body').forEach(el => el.classList.add('hide'));
                    document.getElementById('header-' + appName)?.classList.remove('hide');
                    document.getElementById('body-' + appName)?.classList.remove('hide');
                    
                    if(appName === 'sketch') initSketch();
                    if(appName === 'diary') { document.getElementById('d-name').value = ''; document.getElementById('d-body').value = ''; }
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
                    }
                }

                // Sketchpad Logic
                function initSketch() {
                    ctx = canvas.getContext('2d');
                    const rect = canvas.getBoundingClientRect();
                    canvas.width = rect.width; canvas.height = rect.height;
                    ctx.lineCap = 'round'; ctx.strokeStyle = document.getElementById('sk-color').value;
                    canvas.onmousedown = (e) => { drawing = true; draw(e); };
                    canvas.onmousemove = draw;
                    window.onmouseup = () => { drawing = false; ctx.beginPath(); };
                }
                function draw(e) {
                    if(!drawing) return;
                    const rect = canvas.getBoundingClientRect();
                    ctx.lineWidth = 4;
                    ctx.strokeStyle = document.getElementById('sk-color').value;
                    ctx.lineTo(e.clientX - rect.left, e.clientY - rect.top);
                    ctx.stroke(); ctx.beginPath(); ctx.moveTo(e.clientX - rect.left, e.clientY - rect.top);
                }
                function saveSketch() {
                    const data = canvas.toDataURL();
                    pybridge.saveFile(document.getElementById('sk-name').value || 'Vision', JSON.stringify({image:data}), 'sketch');
                    closeApp();
                }

                function saveDiary() {
                    pybridge.saveFile(document.getElementById('d-name').value || 'Transmission', document.getElementById('d-body').value, 'diary');
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