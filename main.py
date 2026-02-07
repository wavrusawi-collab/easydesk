import sys
import os
import json
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal, Qt

def get_base_path():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent

class Bridge(QObject):
    loginSuccess = pyqtSignal(str)
    loadFiles = pyqtSignal(str)

    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.root_dir = get_base_path()
        self.base_dir = self.root_dir / "data"
        self.base_dir.mkdir(exist_ok=True)
        self.users_file = self.root_dir / "users.json"
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

    @pyqtSlot()
    def refreshFiles(self):
        if not self.current_user: return
        user_dir = self.base_dir / self.current_user
        files = []
        ext_map = {'.md': 'diary', '.json': 'tasks', '.sketch': 'sketch'}
        for f in user_dir.glob("*"):
            ftype = ext_map.get(f.suffix)
            if not ftype: continue
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    content = json.load(file) if f.suffix in ['.json', '.sketch'] else file.read()
                files.append({"name": f.name, "content": content, "type": ftype})
            except: continue
        self.loadFiles.emit(json.dumps(files))

    @pyqtSlot(str, str, str)
    def saveFile(self, name, content, ftype):
        if not self.current_user: return
        exts = {"diary": ".md", "tasks": ".json", "sketch": ".sketch"}
        ext = exts.get(ftype, ".txt")
        if not name.endswith(ext): name += ext
        path = self.base_dir / self.current_user / name
        try:
            data = json.loads(content)
            with open(path, 'w', encoding='utf-8') as f: json.dump(data, f)
        except:
            with open(path, 'w', encoding='utf-8') as f: f.write(content)
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
                @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;600&display=swap');
                :root { --accent: #818cf8; --bg: #030712; }
                body { 
                    background: var(--bg); color: white;
                    font-family: 'Plus Jakarta Sans', sans-serif;
                    height: 100vh; overflow: hidden;
                    perspective: 1000px;
                }
                
                .glass {
                    background: rgba(255, 255, 255, 0.03);
                    backdrop-filter: blur(20px);
                    border: 1px solid rgba(255, 255, 255, 0.08);
                }

                /* Sidebar */
                .sidebar {
                    width: 300px; height: 100vh;
                    padding: 3rem 2rem; border-right: 1px solid rgba(255,255,255,0.05);
                }

                /* Main Grid */
                .main-view {
                    flex: 1; padding: 4rem; overflow-y: auto;
                    display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
                    gap: 2rem; align-content: start;
                }

                .file-card {
                    padding: 2rem; border-radius: 2rem;
                    transition: all 0.5s cubic-bezier(0.23, 1, 0.32, 1);
                    cursor: pointer; position: relative;
                    transform-style: preserve-3d;
                }
                .file-card:hover {
                    background: rgba(255, 255, 255, 0.07);
                    transform: translateY(-10px) rotateX(5deg) rotateY(5deg);
                    border-color: var(--accent);
                }
                .file-card i { color: var(--accent); margin-bottom: 1.5rem; }

                /* Fullscreen Apps */
                .app-overlay {
                    position: fixed; inset: 0; z-index: 5000;
                    background: var(--bg); display: none;
                    padding: 5rem; flex-direction: column;
                }
                .app-overlay.active { display: flex; animation: fadeIn 0.4s ease; }

                @keyframes fadeIn { from { opacity: 0; transform: scale(1.05); } to { opacity: 1; transform: scale(1); } }

                input, textarea { background: transparent; border: none; outline: none; color: white; width: 100%; }
                .action-btn {
                    padding: 0.8rem 1.5rem; border-radius: 1rem;
                    background: var(--accent); font-weight: 600;
                    transition: 0.3s;
                }
                .action-btn:hover { filter: brightness(1.2); transform: scale(1.05); }
                
                .hide { display: none !important; }
            </style>
        </head>
        <body class="flex">
            <!-- Login Screen -->
            <div id="login-screen" class="fixed inset-0 z-[9000] bg-[#030712] flex items-center justify-center">
                <div class="w-96 space-y-8 text-center">
                    <div class="w-20 h-20 bg-indigo-500/20 rounded-3xl mx-auto flex items-center justify-center mb-10">
                        <i data-lucide="layers" class="text-indigo-400 w-10 h-10"></i>
                    </div>
                    <h2 class="text-3xl font-semibold tracking-tight">Welcome back</h2>
                    <input id="u" type="text" placeholder="Identity" class="glass p-4 rounded-2xl text-center">
                    <input id="p" type="password" placeholder="Passkey" class="glass p-4 rounded-2xl text-center">
                    <button onclick="login()" class="action-btn w-full py-4 mt-4">Initialize Session</button>
                </div>
            </div>

            <!-- Dashboard -->
            <div id="sidebar" class="sidebar flex flex-col hide">
                <div class="flex items-center gap-3 mb-12">
                    <div class="w-8 h-8 bg-indigo-500 rounded-lg"></div>
                    <span class="font-bold text-xl tracking-tighter">EasyDesk</span>
                </div>
                
                <nav class="space-y-2 flex-1">
                    <button onclick="newFile('diary')" class="w-full text-left p-4 rounded-xl hover:bg-white/5 flex items-center gap-3">
                        <i data-lucide="plus" class="w-4 h-4"></i> New Journal
                    </button>
                    <button onclick="newFile('tasks')" class="w-full text-left p-4 rounded-xl hover:bg-white/5 flex items-center gap-3">
                        <i data-lucide="plus" class="w-4 h-4"></i> New Task List
                    </button>
                    <button onclick="newFile('sketch')" class="w-full text-left p-4 rounded-xl hover:bg-white/5 flex items-center gap-3">
                        <i data-lucide="plus" class="w-4 h-4"></i> New Sketch
                    </button>
                </nav>

                <button onclick="location.reload()" class="p-4 rounded-xl text-red-400 hover:bg-red-400/10 flex items-center gap-3">
                    <i data-lucide="log-out" class="w-4 h-4"></i> Terminate
                </button>
            </div>

            <main id="main-grid" class="main-view hide"></main>

            <!-- App Overlays -->
            <div id="app-wrap" class="app-overlay">
                <div class="flex items-center justify-between mb-12">
                    <input id="app-title" class="text-4xl font-bold max-w-2xl" placeholder="Untitled Document">
                    <div class="flex gap-4">
                        <button id="save-trigger" class="action-btn">Save Changes</button>
                        <button onclick="closeApp()" class="glass p-3 rounded-xl hover:bg-white/10"><i data-lucide="x"></i></button>
                    </div>
                </div>

                <div id="diary-ui" class="flex-1 hide">
                    <textarea id="diary-content" class="h-full text-xl leading-relaxed opacity-80" placeholder="Start writing..."></textarea>
                </div>

                <div id="tasks-ui" class="flex-1 hide overflow-y-auto space-y-4">
                    <div id="task-list" class="space-y-3"></div>
                    <button onclick="addTaskRow()" class="text-indigo-400 p-2">+ Add Objective</button>
                </div>

                <div id="sketch-ui" class="flex-1 hide bg-black/20 rounded-3xl overflow-hidden border border-white/5">
                    <canvas id="sketch-pad" class="w-full h-full"></canvas>
                </div>
            </div>

            <script>
                let pybridge;
                let activeType = null;
                const canvas = document.getElementById('sketch-pad');
                const ctx = canvas.getContext('2d');
                let drawing = false;

                new QWebChannel(qt.webChannelTransport, function(channel) {
                    pybridge = channel.objects.pybridge;
                    pybridge.loginSuccess.connect(() => {
                        document.getElementById('login-screen').classList.add('hide');
                        document.getElementById('sidebar').classList.remove('hide');
                        document.getElementById('main-grid').classList.remove('hide');
                    });
                    pybridge.loadFiles.connect((json) => renderFiles(JSON.parse(json)));
                });

                function login() { pybridge.handleLogin(u.value, p.value); }

                function renderFiles(files) {
                    const grid = document.getElementById('main-grid');
                    grid.innerHTML = '';
                    files.forEach(f => {
                        const card = document.createElement('div');
                        card.className = 'file-card glass';
                        const icon = f.type === 'diary' ? 'file-text' : (f.type === 'tasks' ? 'list-checks' : 'palette');
                        card.innerHTML = `
                            <i data-lucide="${icon}" class="w-10 h-10"></i>
                            <h3 class="text-lg font-semibold">${f.name}</h3>
                            <p class="text-white/40 text-sm mt-1 uppercase tracking-widest">${f.type}</p>
                        `;
                        card.onclick = () => openFile(f);
                        grid.appendChild(card);
                    });
                    lucide.createIcons();
                }

                function openFile(file) {
                    activeType = file.type;
                    document.getElementById('app-wrap').classList.add('active');
                    document.getElementById('app-title').value = file.name.split('.')[0];
                    
                    document.getElementById('diary-ui').classList.add('hide');
                    document.getElementById('tasks-ui').classList.add('hide');
                    document.getElementById('sketch-ui').classList.add('hide');

                    if(file.type === 'diary') {
                        document.getElementById('diary-ui').classList.remove('hide');
                        document.getElementById('diary-content').value = file.content;
                        document.getElementById('save-trigger').onclick = () => {
                            pybridge.saveFile(document.getElementById('app-title').value, document.getElementById('diary-content').value, 'diary');
                            closeApp();
                        };
                    } else if(file.type === 'tasks') {
                        document.getElementById('tasks-ui').classList.remove('hide');
                        document.getElementById('task-list').innerHTML = '';
                        file.content.forEach(t => addTaskRow(t.text, t.done));
                        document.getElementById('save-trigger').onclick = () => {
                            const data = Array.from(document.querySelectorAll('#task-list > div')).map(d => ({
                                text: d.querySelector('input[type="text"]').value,
                                done: d.querySelector('input[type="checkbox"]').checked
                            }));
                            pybridge.saveFile(document.getElementById('app-title').value, JSON.stringify(data), 'tasks');
                            closeApp();
                        };
                    } else if(file.type === 'sketch') {
                        document.getElementById('sketch-ui').classList.remove('hide');
                        resizeCanvas();
                        const img = new Image();
                        img.onload = () => ctx.drawImage(img, 0, 0);
                        img.src = file.content.image;
                        document.getElementById('save-trigger').onclick = () => {
                            pybridge.saveFile(document.getElementById('app-title').value, JSON.stringify({image: canvas.toDataURL()}), 'sketch');
                            closeApp();
                        };
                    }
                }

                function newFile(type) {
                    openFile({name: 'New ' + type, type: type, content: type === 'tasks' ? [] : (type === 'sketch' ? {image:''} : '')});
                }

                function closeApp() { document.getElementById('app-wrap').classList.remove('active'); }

                function addTaskRow(text = '', done = false) {
                    const row = document.createElement('div');
                    row.className = 'flex items-center gap-4 glass p-4 rounded-2xl';
                    row.innerHTML = `
                        <input type="checkbox" ${done ? 'checked' : ''} class="w-6 h-6 accent-indigo-500">
                        <input type="text" value="${text}" placeholder="Objective description..." class="flex-1">
                    `;
                    document.getElementById('task-list').appendChild(row);
                }

                // Sketch Logic
                function resizeCanvas() {
                    canvas.width = canvas.parentElement.clientWidth;
                    canvas.height = canvas.parentElement.clientHeight;
                    ctx.lineCap = 'round'; ctx.lineWidth = 3; ctx.strokeStyle = '#818cf8';
                }
                canvas.onmousedown = (e) => { drawing = true; ctx.beginPath(); ctx.moveTo(e.offsetX, e.offsetY); };
                canvas.onmousemove = (e) => { if(drawing) { ctx.lineTo(e.offsetX, e.offsetY); ctx.stroke(); } };
                window.onmouseup = () => drawing = false;

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