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
                :root { --accent: #60a5fa; }
                body { 
                    background: radial-gradient(circle at center, #1e1b4b 0%, #020617 100%); 
                    height: 100vh; overflow: hidden; font-family: 'Inter', sans-serif; color: white;
                }
                
                .mesh {
                    position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                    background: radial-gradient(circle at 20% 30%, rgba(99, 102, 241, 0.15) 0%, transparent 40%),
                                radial-gradient(circle at 80% 70%, rgba(236, 72, 153, 0.1) 0%, transparent 40%);
                    z-index: -1; animation: meshFlow 20s infinite alternate;
                }
                @keyframes meshFlow { 0% { transform: scale(1); } 100% { transform: scale(1.2) rotate(5deg); } }

                .hide { display: none !important; }
                
                .app-shell {
                    position: fixed; inset: 10%;
                    background: rgba(15, 23, 42, 0.85);
                    backdrop-filter: blur(50px) saturate(160%);
                    border: 1px solid rgba(255, 255, 255, 0.15);
                    border-radius: 4rem;
                    display: flex; flex-direction: column;
                    box-shadow: 0 50px 100px rgba(0,0,0,0.6);
                    z-index: 1000; transform: scale(0.8); opacity: 0; pointer-events: none;
                    transition: all 0.5s cubic-bezier(0.16, 1, 0.3, 1);
                }
                .app-shell.active { transform: scale(1); opacity: 1; pointer-events: auto; }

                .orb-launcher {
                    position: fixed; bottom: 3rem; left: 50%; transform: translateX(-50%);
                    display: flex; gap: 1.5rem; padding: 1.2rem 2.2rem;
                    background: rgba(255, 255, 255, 0.08); border-radius: 4rem;
                    backdrop-filter: blur(20px); border: 1px solid rgba(255, 255, 255, 0.1);
                    z-index: 2000;
                }
                .orb {
                    width: 3.5rem; height: 3.5rem; border-radius: 50%;
                    display: flex; align-items: center; justify-content: center;
                    cursor: pointer; transition: all 0.3s;
                    box-shadow: 0 10px 20px rgba(0,0,0,0.2);
                }
                .orb:hover { transform: translateY(-0.8rem) scale(1.15); filter: brightness(1.2); }

                .node {
                    position: absolute; width: 7rem; height: 7rem; border-radius: 50%;
                    background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1);
                    display: flex; flex-direction: column; align-items: center; justify-content: center;
                    cursor: pointer; transition: all 0.4s;
                    animation: float 15s infinite alternate ease-in-out;
                    z-index: 10; pointer-events: auto;
                }
                .node:hover { background: rgba(255, 255, 255, 0.15); border-color: var(--accent); scale: 1.1; z-index: 20; }
                .node span { font-size: 0.75rem; margin-top: 0.5rem; max-width: 85%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; text-align: center; pointer-events: none; }
                .node i { pointer-events: none; }

                @keyframes float { 
                    0% { transform: translate(0, 0); } 
                    100% { transform: translate(40px, 40px); } 
                }

                input, textarea { background: transparent; border: none; outline: none; color: white; }
                .btn-primary { background: var(--accent); color: white; padding: 0.8rem 1.8rem; border-radius: 1.8rem; font-weight: 600; transition: transform 0.2s; }
                .btn-primary:active { transform: scale(0.95); }
                
                canvas { background: transparent; cursor: crosshair; touch-action: none; display: block; }
                
                .app-body { overflow-y: auto; flex: 1; }
                .app-body::-webkit-scrollbar { width: 6px; }
                .app-body::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 10px; }
            </style>
        </head>
        <body>
            <div class="mesh"></div>
            <div id="constellation" class="fixed inset-0 pointer-events-none"></div>

            <div id="screen-login" class="fixed inset-0 flex items-center justify-center z-[5000]">
                <div class="text-center space-y-10">
                    <h1 class="text-6xl font-thin tracking-[0.5em] uppercase opacity-80">EasyDesk</h1>
                    <div class="space-y-6">
                        <input id="u" type="text" placeholder="IDENTITY" class="text-center w-72 p-4 border-b border-white/10 text-xl focus:border-white/50 transition-all uppercase tracking-widest">
                        <input id="p" type="password" placeholder="PHASE" class="text-center w-72 p-4 block mx-auto border-b border-white/10 text-xl focus:border-white/50 transition-all uppercase tracking-widest">
                    </div>
                    <button onclick="login()" class="text-xs tracking-[0.3em] opacity-40 hover:opacity-100 hover:tracking-[0.4em] transition-all">INITIALIZE_SYSTEM</button>
                </div>
            </div>

            <div id="screen-home" class="hide">
                <div class="orb-launcher">
                    <div class="orb bg-blue-500/20 text-blue-300" onclick="openApp('diary')"><i data-lucide="edit-3"></i></div>
                    <div class="orb bg-yellow-500/20 text-yellow-300" onclick="openApp('tasks')"><i data-lucide="check-circle"></i></div>
                    <div class="orb bg-orange-500/20 text-orange-300" onclick="openApp('sketch')"><i data-lucide="palette"></i></div>
                    <div class="orb bg-white/5 text-white/30" onclick="location.reload()"><i data-lucide="power"></i></div>
                </div>
            </div>

            <div id="app-shell" class="app-shell">
                <div class="p-16 flex-1 flex flex-col overflow-hidden">
                    <div id="header-diary" class="app-header hide flex items-center gap-6 mb-10">
                        <input id="d-name" type="text" placeholder="Untitled Note" class="text-4xl font-light flex-1">
                        <button onclick="saveDiary()" class="btn-primary">Preserve</button>
                        <button onclick="closeApp()" class="opacity-30 hover:opacity-100 transition-opacity"><i data-lucide="x"></i></button>
                    </div>
                    <div id="header-tasks" class="app-header hide flex items-center gap-6 mb-10">
                        <input id="t-name" type="text" placeholder="Objective Board" class="text-4xl font-light flex-1">
                        <button onclick="addTaskRow()" class="px-5 py-2 border border-white/10 rounded-2xl hover:bg-white/5">+ Task</button>
                        <button onclick="saveTasks()" class="btn-primary">Sync</button>
                        <button onclick="closeApp()" class="opacity-30 hover:opacity-100 transition-opacity"><i data-lucide="x"></i></button>
                    </div>
                    <div id="header-sketch" class="app-header hide flex items-center gap-6 mb-10">
                        <input id="sk-name" type="text" placeholder="Visual Capture" class="text-4xl font-light flex-1">
                        <div class="flex items-center gap-3 bg-white/5 px-4 py-2 rounded-2xl">
                            <input id="sk-color" type="color" value="#60a5fa" class="w-8 h-8 bg-transparent cursor-pointer">
                            <input id="sk-size" type="range" min="1" max="50" value="5" class="w-20 accent-blue-400">
                        </div>
                        <button onclick="saveSketch()" class="btn-primary">Snapshot</button>
                        <button onclick="closeApp()" class="opacity-30 hover:opacity-100 transition-opacity"><i data-lucide="x"></i></button>
                    </div>

                    <div id="body-diary" class="app-body hide">
                        <textarea id="d-body" class="w-full h-full text-xl leading-relaxed placeholder:opacity-5 resize-none" placeholder="Begin transmission..."></textarea>
                    </div>
                    <div id="body-tasks" class="app-body hide space-y-4">
                        <div id="t-container" class="space-y-4"></div>
                    </div>
                    <div id="body-sketch" class="app-body hide relative rounded-[2.5rem] overflow-hidden bg-black/20 border border-white/5">
                        <canvas id="sk-canvas"></canvas>
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
                        node.className = 'node';
                        const x = 5 + Math.random() * 85;
                        const y = 5 + Math.random() * 75;
                        node.style.left = x + '%';
                        node.style.top = y + '%';
                        node.style.animationDelay = (i * -1.5) + 's';
                        
                        const icons = { diary: 'file-text', tasks: 'check-circle', sketch: 'image', flashcards: 'zap', secret: 'lock' };
                        node.innerHTML = `<i data-lucide="${icons[f.type] || 'circle'}"></i><span>${f.name}</span>`;
                        node.onclick = (e) => { e.stopPropagation(); loadFile(f); };
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
                    
                    if(appName === 'sketch') {
                        setTimeout(resizeCanvas, 50); // Ensure layout is computed
                        initSketch();
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
                    ctx.lineCap = 'round';
                    ctx.lineJoin = 'round';
                    
                    canvas.onmousedown = (e) => { drawing = true; startPos(e); };
                    canvas.onmousemove = draw;
                    window.onmouseup = () => { drawing = false; ctx.beginPath(); };
                    
                    canvas.ontouchstart = (e) => { e.preventDefault(); drawing = true; startPos(e.touches[0]); };
                    canvas.ontouchmove = (e) => { e.preventDefault(); draw(e.touches[0]); };
                    canvas.ontouchend = () => { drawing = false; ctx.beginPath(); };
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
                    pybridge.saveFile(document.getElementById('sk-name').value || 'Vision', JSON.stringify({image:data}), 'sketch');
                    closeApp();
                }

                function saveDiary() {
                    pybridge.saveFile(document.getElementById('d-name').value || 'Transmission', document.getElementById('d-body').value, 'diary');
                    closeApp();
                }

                function addTaskRow(text = "", done = false) {
                    const div = document.createElement('div');
                    div.className = "flex items-center gap-4 bg-white/5 p-4 rounded-3xl border border-white/5 hover:border-white/10 transition-all";
                    div.innerHTML = `
                        <input type="checkbox" ${done ? 'checked' : ''} class="w-6 h-6 rounded-full border-2 border-white/20 appearance-none checked:bg-blue-400 checked:border-transparent transition-all cursor-pointer">
                        <input type="text" value="${text}" placeholder="New objective..." class="flex-1 text-lg">
                        <button onclick="this.parentElement.remove()" class="opacity-20 hover:opacity-100 hover:text-red-400"><i data-lucide="trash-2"></i></button>
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