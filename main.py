import sys
import os
import json
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QHBoxLayout, QLineEdit
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal, Qt, QUrl

def get_base_path():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent

class Bridge(QObject):
    loginSuccess = pyqtSignal(str)
    loadFiles = pyqtSignal(str)
    openBrowser = pyqtSignal(str)

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
        ext_map = {'.md': 'diary', '.json': 'tasks', '.sketch': 'sketch', '.secret': 'secret', '.cards': 'flashcards'}
        for f in user_dir.glob("*"):
            ftype = ext_map.get(f.suffix)
            if not ftype: continue
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    if f.suffix in ['.json', '.sketch', '.secret', '.cards']:
                        content = json.load(file)
                    else:
                        content = file.read()
                files.append({"id": str(f.name), "name": f.name, "content": content, "type": ftype})
            except: continue
        self.loadFiles.emit(json.dumps(files))

    @pyqtSlot(str, str, str)
    def saveFile(self, name, content, ftype):
        if not self.current_user: return
        exts = {"diary": ".md", "tasks": ".json", "sketch": ".sketch", "secret": ".secret", "flashcards": ".cards"}
        ext = exts.get(ftype, ".txt")
        if not name.strip(): name = "Untitled"
        if not name.endswith(ext): name += ext
        
        path = self.base_dir / self.current_user / name
        try:
            data = json.loads(content)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f)
        except:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
        
        self.refreshFiles()

    @pyqtSlot(str)
    def deleteFile(self, filename):
        if not self.current_user: return
        path = self.base_dir / self.current_user / filename
        if path.exists(): os.remove(path)
        self.refreshFiles()

    @pyqtSlot(str)
    def launchExplorer(self, url):
        self.openBrowser.emit(url)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # 1. Setup Window properties
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.showFullScreen()
        
        # 2. Setup the Bridge and Channel
        self.bridge = Bridge(self)
        self.channel = QWebChannel()
        self.channel.registerObject('pybridge', self.bridge)

        # 3. Create Explorer UI
        self.explorer_container = QWidget(self)
        self.explorer_container.hide()
        self.explorer_layout = QVBoxLayout(self.explorer_container)
        self.explorer_layout.setContentsMargins(20, 20, 20, 20)
        
        toolbar = QHBoxLayout()
        back_btn = QPushButton("← Back to Grove")
        back_btn.setStyleSheet("background: #88B04B; color: white; border-radius: 15px; padding: 10px 20px; font-weight: bold; border: none;")
        back_btn.clicked.connect(self.hide_explorer)
        
        # Internal URL tracking (hidden address bar)
        self.url_display = QLineEdit()
        self.url_display.setReadOnly(True)
        self.url_display.hide() # Completely hidden per request "remove the address bar"
        
        toolbar.addWidget(back_btn)
        toolbar.addStretch()
        self.explorer_layout.addLayout(toolbar)

        self.explorer_view = QWebEngineView()
        self.explorer_view.setStyleSheet("border-radius: 20px; background: white;")
        # Handle page changes automatically
        self.explorer_view.urlChanged.connect(self.handle_url_change)
        self.explorer_layout.addWidget(self.explorer_view)

        # 4. Setup Main UI View
        self.main_view = QWebEngineView()
        self.main_view.page().setWebChannel(self.channel)
        self.setCentralWidget(self.main_view)

        # 5. Connect signals
        self.bridge.openBrowser.connect(self.show_explorer)

        self.html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <script src="https://cdn.tailwindcss.com"></script>
            <script src="https://unpkg.com/lucide@latest"></script>
            <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;700&family=Gaegu:wght@400;700&display=swap');
                :root { --grass: #88B04B; --bark: #6D4C41; --leaf-light: #C5E1A5; --sky: #E3F2FD; }
                * { cursor: none !important; }
                body { transition: background-color 2s ease; background-color: var(--sky); font-family: 'Nunito', sans-serif; height: 100vh; overflow: hidden; margin: 0; }
                #custom-cursor { position: fixed; width: 32px; height: 32px; pointer-events: none; z-index: 99999; transform: translate(-50%, -50%) rotate(-15deg); transition: transform 0.1s ease-out; filter: drop-shadow(2px 2px 2px rgba(0,0,0,0.1)); }
                input, textarea { cursor: text !important; }
                .bubble { background: white; border-radius: 2rem; box-shadow: 0 10px 0 rgba(0,0,0,0.05); border: 4px solid white; position: relative; }
                .leaf-card { background: white; border-radius: 1.5rem 4rem; transition: all 0.3s ease; cursor: none; border: 3px solid transparent; }
                .leaf-card:hover { transform: translateY(-5px); border-color: var(--grass); }
                .overlay { position: fixed; inset: 0; z-index: 5000; display: none; padding: 2rem; background: rgba(255, 255, 255, 0.95); backdrop-filter: blur(10px); }
                .overlay.active { display: flex; flex-direction: column; }
                .nav-pill { background: var(--grass); color: white; padding: 0.75rem 2rem; border-radius: 999px; font-weight: 700; box-shadow: 0 4px 0 #558B2F; }
                .hide { display: none !important; }
            </style>
        </head>
        <body class="flex flex-col theme-day">
            <div id="custom-cursor"><svg viewBox="0 0 24 24" fill="#88B04B"><path d="M2.00002 21.9998L3.99991 19.9999C12.5 21.9998 18.5 16 19.5 9.49983C20.5 2.99983 14.5 1.99983 14.5 1.99983C14.5 1.99983 14 8.49983 7 10.4998C2.5 11.7855 2.00002 16.4998 2.00002 21.9998Z"/></svg></div>
            
            <div id="login" class="fixed inset-0 z-[9999] bg-[#E3F2FD] flex items-center justify-center p-10">
                <div class="bubble p-12 text-center w-full max-w-sm space-y-6">
                    <h1 class="text-3xl font-bold text-bark">Nature Desk</h1>
                    <input id="u" type="text" placeholder="Your Name" class="w-full text-center p-3 rounded-xl border">
                    <input id="p" type="password" placeholder="Passkey" class="w-full text-center p-3 rounded-xl border">
                    <button onclick="login()" class="nav-pill w-full">Enter the Grove</button>
                </div>
            </div>

            <div id="dashboard" class="hide h-full flex flex-col p-8">
                <header class="flex justify-between items-center mb-12">
                    <h1 class="text-4xl font-bold text-bark" id="welcome-text">Hello!</h1>
                    <button onclick="location.reload()" class="opacity-40 font-bold">Sign Out</button>
                </header>

                <div class="flex-1 overflow-y-auto space-y-12">
                    <section>
                        <h2 class="text-xl font-bold mb-6 text-bark/60 uppercase tracking-widest text-sm">Create New</h2>
                        <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
                            <div class="leaf-card p-6 flex flex-col items-center gap-3" onclick="newFile('diary')"><i data-lucide="feather"></i><span>Note</span></div>
                            <div class="leaf-card p-6 flex flex-col items-center gap-3" onclick="newFile('tasks')"><i data-lucide="list-checks"></i><span>Tasks</span></div>
                            <div class="leaf-card p-6 flex flex-col items-center gap-3" onclick="newFile('sketch')"><i data-lucide="palette"></i><span>Sketch</span></div>
                            <div class="leaf-card p-6 flex flex-col items-center gap-3" onclick="newFile('secret')"><i data-lucide="lock"></i><span>Secret</span></div>
                            <div class="leaf-card p-6 flex flex-col items-center gap-3" onclick="newFile('flashcards')"><i data-lucide="layers"></i><span>Cards</span></div>
                            <div class="leaf-card p-6 flex flex-col items-center gap-3 text-blue-500" onclick="pybridge.launchExplorer('https://www.google.com')"><i data-lucide="globe"></i><span>Explorer</span></div>
                        </div>
                    </section>

                    <section>
                        <h2 class="text-xl font-bold mb-6 text-bark/60 uppercase tracking-widest text-sm">Collection</h2>
                        <div id="file-grid" class="grid grid-cols-2 md:grid-cols-5 gap-4"></div>
                    </section>
                </div>
            </div>

            <div id="app-overlay" class="overlay">
                <div class="flex items-center gap-4 mb-8">
                    <button onclick="closeApp()" class="w-12 h-12 rounded-full bg-white flex items-center justify-center">←</button>
                    <input id="file-title" class="text-2xl font-bold bg-transparent border-none flex-1 focus:outline-none text-bark">
                    <button onclick="discardCurrent()" class="nav-pill !bg-red-400">Discard</button>
                    <button onclick="triggerSave()" class="nav-pill">Save & Close</button>
                </div>
                <div id="ui-diary" class="flex-1 hide"><textarea id="diary-box" class="w-full h-full p-8 rounded-3xl border shadow-inner focus:outline-none"></textarea></div>
                <div id="ui-tasks" class="flex-1 hide overflow-y-auto"><div id="task-items"></div><button onclick="addTaskRow()" class="w-full p-4 mt-4 border-2 border-dashed rounded-xl">+ Task</button></div>
                <div id="ui-sketch" class="flex-1 hide bg-white rounded-3xl border-4 overflow-hidden"><canvas id="paint-canvas"></canvas></div>
                <div id="ui-secret" class="flex-1 hide flex flex-col gap-4"><textarea id="secret-plain" class="flex-1 p-4 rounded-xl border focus:outline-none" oninput="updateSecret()"></textarea><textarea id="secret-encoded" class="flex-1 p-4 rounded-xl border bg-gray-50 focus:outline-none" readonly></textarea></div>
                <div id="ui-flashcards" class="flex-1 hide flex flex-col items-center"><div class="bubble p-20 text-3xl font-bold w-full max-w-lg text-center" id="card-q"></div></div>
            </div>

            <script>
                let pybridge;
                let activeType = null;
                let currentFileName = null;
                new QWebChannel(qt.webChannelTransport, function(channel) {
                    pybridge = channel.objects.pybridge;
                    pybridge.loginSuccess.connect(user => {
                        document.getElementById('login').classList.add('hide');
                        document.getElementById('dashboard').classList.remove('hide');
                        document.getElementById('welcome-text').innerText = "Hello, " + user + "!";
                    });
                    pybridge.loadFiles.connect(json => { renderFiles(JSON.parse(json)); });
                });

                function login() { pybridge.handleLogin(u.value, p.value); }
                function renderFiles(files) {
                    const grid = document.getElementById('file-grid');
                    grid.innerHTML = '';
                    files.forEach(f => {
                        const card = document.createElement('div');
                        card.className = "bubble p-4 text-center cursor-none";
                        card.innerHTML = `<div class="font-bold text-bark">${f.name.split('.')[0]}</div><div class="text-xs text-bark/40">${f.type}</div>`;
                        card.onclick = () => openFile(f);
                        grid.appendChild(card);
                    });
                }

                function newFile(type) { openFile({name:'Untitled', type:type, content:''}); }
                function openFile(file) {
                    activeType = file.type; currentFileName = file.name;
                    document.getElementById('app-overlay').classList.add('active');
                    document.getElementById('file-title').value = file.name.split('.')[0];
                    ['ui-diary', 'ui-tasks', 'ui-sketch', 'ui-secret', 'ui-flashcards'].forEach(id => document.getElementById(id).classList.add('hide'));
                    document.getElementById('ui-' + file.type).classList.remove('hide');
                    if(file.type === 'diary') document.getElementById('diary-box').value = file.content;
                }
                function triggerSave() { pybridge.saveFile(document.getElementById('file-title').value, document.getElementById('diary-box').value, activeType); closeApp(); }
                function closeApp() { document.getElementById('app-overlay').classList.remove('active'); }
                function discardCurrent() { if(confirm("Discard?")) { pybridge.deleteFile(currentFileName); closeApp(); } }

                document.addEventListener('mousemove', e => {
                    const c = document.getElementById('custom-cursor');
                    c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px';
                });
                lucide.createIcons();
            </script>
        </body>
        </html>
        """
        self.main_view.setHtml(self.html_content)

    def handle_url_change(self, url):
        self.url_display.setText(url.toString())

    def show_explorer(self, url):
        self.url_display.setText(url)
        self.explorer_view.setUrl(QUrl(url))
        self.explorer_container.setGeometry(self.rect())
        self.explorer_container.show()
        self.explorer_container.raise_()

    def hide_explorer(self):
        self.explorer_container.hide()
        self.explorer_view.setUrl(QUrl("about:blank"))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'explorer_container') and self.explorer_container.isVisible():
            self.explorer_container.setGeometry(self.rect())

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())