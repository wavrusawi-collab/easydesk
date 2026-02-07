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
        ext_map = {'.md': 'diary', '.json': 'tasks', '.sketch': 'sketch', '.secret': 'secret', '.cards': 'flashcards'}
        for f in user_dir.glob("*"):
            ftype = ext_map.get(f.suffix)
            if not ftype: continue
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    content = json.load(file) if f.suffix in ['.json', '.sketch', '.secret', '.cards'] else file.read()
                files.append({"name": f.name, "content": content, "type": ftype})
            except: continue
        self.loadFiles.emit(json.dumps(files))

    @pyqtSlot(str, str, str)
    def saveFile(self, name, content, ftype):
        if not self.current_user: return
        exts = {"diary": ".md", "tasks": ".json", "sketch": ".sketch", "secret": ".secret", "flashcards": ".cards"}
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
                @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;700&family=Gaegu:wght@400;700&display=swap');
                
                :root {
                    --grass: #88B04B;
                    --bark: #6D4C41;
                    --leaf-light: #C5E1A5;
                    --sky: #E3F2FD;
                    --flower: #F48FB1;
                    --wood: #A1887F;
                }

                body { 
                    background-color: var(--sky);
                    background-image: radial-gradient(circle at 20% 20%, rgba(255,255,255,0.8) 0%, transparent 25%);
                    color: var(--bark); 
                    font-family: 'Nunito', sans-serif;
                    height: 100vh; overflow: hidden; margin: 0;
                }
                
                .font-organic { font-family: 'Gaegu', cursive; }

                .bubble {
                    background: white;
                    border-radius: 2rem;
                    box-shadow: 0 10px 0 rgba(0,0,0,0.05);
                    border: 4px solid white;
                }

                .leaf-card {
                    background: white;
                    border-radius: 1.5rem 4rem 1.5rem 4rem;
                    transition: all 0.3s ease;
                    cursor: pointer;
                    border: 3px solid transparent;
                }
                .leaf-card:hover {
                    transform: translateY(-5px) rotate(1deg);
                    border-color: var(--grass);
                    box-shadow: 0 15px 30px rgba(136, 176, 75, 0.2);
                }

                .overlay {
                    position: fixed; inset: 0; z-index: 5000;
                    display: none; padding: 2rem;
                    background: rgba(227, 242, 253, 0.98);
                    backdrop-filter: blur(10px);
                }
                .overlay.active { display: flex; flex-direction: column; animation: fadeIn 0.4s ease; }
                
                @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

                .nav-pill {
                    background: var(--grass);
                    color: white;
                    padding: 0.75rem 2rem;
                    border-radius: 999px;
                    font-weight: 700;
                    box-shadow: 0 4px 0 #558B2F;
                    transition: all 0.1s;
                }
                .nav-pill:active { transform: translateY(4px); box-shadow: none; }

                input, textarea { 
                    background: rgba(255,255,255,0.7); border: 2px solid var(--leaf-light); 
                    border-radius: 1.5rem; padding: 1rem; outline: none; 
                    font-family: inherit;
                }
                textarea:focus { border-color: var(--grass); background: white; }

                .hide { display: none !important; }

                /* Flashcard Flip */
                .flip-card { perspective: 1000px; width: 100%; height: 300px; }
                .flip-card-inner {
                    position: relative; width: 100%; height: 100%;
                    text-align: center; transition: transform 0.6s;
                    transform-style: preserve-3d; cursor: pointer;
                }
                .flip-card.flipped .flip-card-inner { transform: rotateY(180deg); }
                .flip-front, .flip-back {
                    position: absolute; width: 100%; height: 100%;
                    backface-visibility: hidden; border-radius: 2rem;
                    display: flex; items-center; justify-center; padding: 2rem;
                    font-size: 2rem; font-weight: bold; border: 8px solid var(--leaf-light);
                }
                .flip-front { background: white; color: var(--bark); }
                .flip-back { background: var(--grass); color: white; transform: rotateY(180deg); }
            </style>
        </head>
        <body class="flex flex-col">
            <!-- Login -->
            <div id="login" class="fixed inset-0 z-[9999] bg-[#E3F2FD] flex items-center justify-center p-10">
                <div class="bubble p-12 text-center w-full max-w-sm space-y-6">
                    <div class="w-20 h-20 bg-[#C5E1A5] rounded-full mx-auto flex items-center justify-center">
                        <i data-lucide="sprout" class="text-[#558B2F] w-10 h-10"></i>
                    </div>
                    <h1 class="text-3xl font-organic font-bold">Nature Desk</h1>
                    <input id="u" type="text" placeholder="Your Name" class="w-full text-center">
                    <input id="p" type="password" placeholder="Passkey" class="w-full text-center">
                    <button onclick="login()" class="nav-pill w-full text-xl">Enter the Grove</button>
                </div>
            </div>

            <!-- Dashboard -->
            <div id="dashboard" class="hide h-full flex flex-col p-8">
                <header class="flex justify-between items-center mb-12">
                    <div>
                        <h1 class="text-4xl font-organic font-bold text-bark" id="welcome-text">Hello!</h1>
                        <p class="text-bark opacity-60">Welcome back to your quiet corner.</p>
                    </div>
                    <button onclick="location.reload()" class="text-bark opacity-40 hover:opacity-100 font-bold transition-opacity">Sign Out</button>
                </header>

                <div class="flex-1 overflow-y-auto space-y-12">
                    <section>
                        <h2 class="text-xl font-bold mb-6 flex items-center gap-2">
                            <i data-lucide="sparkles" class="text-yellow-500"></i> New Activity
                        </h2>
                        <div class="grid grid-cols-2 md:grid-cols-5 gap-4">
                            <div class="leaf-card p-6 flex flex-col items-center gap-3 bg-white" onclick="newFile('diary')">
                                <i data-lucide="feather" class="text-pink-400"></i><span class="font-bold text-sm">Note</span>
                            </div>
                            <div class="leaf-card p-6 flex flex-col items-center gap-3 bg-white" onclick="newFile('tasks')">
                                <i data-lucide="list-checks" class="text-emerald-500"></i><span class="font-bold text-sm">Tasks</span>
                            </div>
                            <div class="leaf-card p-6 flex flex-col items-center gap-3 bg-white" onclick="newFile('sketch')">
                                <i data-lucide="palette" class="text-blue-500"></i><span class="font-bold text-sm">Sketch</span>
                            </div>
                            <div class="leaf-card p-6 flex flex-col items-center gap-3 bg-white" onclick="newFile('secret')">
                                <i data-lucide="lock" class="text-amber-600"></i><span class="font-bold text-sm">Secret</span>
                            </div>
                            <div class="leaf-card p-6 flex flex-col items-center gap-3 bg-white" onclick="newFile('flashcards')">
                                <i data-lucide="layers" class="text-purple-500"></i><span class="font-bold text-sm">Cards</span>
                            </div>
                        </div>
                    </section>

                    <section>
                        <h2 class="text-xl font-bold mb-6 flex items-center gap-2">
                            <i data-lucide="container" class="text-amber-700"></i> Your Collection
                        </h2>
                        <div id="file-grid" class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 pb-12"></div>
                    </section>
                </div>
            </div>

            <!-- App Overlay -->
            <div id="app-overlay" class="overlay">
                <div class="flex items-center gap-4 mb-8">
                    <button onclick="closeApp()" class="w-12 h-12 rounded-full bg-white flex items-center justify-center shadow-sm">
                        <i data-lucide="chevron-left" class="text-bark"></i>
                    </button>
                    <input id="file-title" class="flex-1 text-2xl font-bold bg-white" placeholder="Untitled...">
                    <button id="save-btn" class="nav-pill">Save & Close</button>
                </div>

                <!-- Diary UI -->
                <div id="ui-diary" class="flex-1 hide"><textarea id="diary-box" class="w-full h-full text-lg leading-relaxed shadow-inner" placeholder="Once upon a time..."></textarea></div>
                
                <!-- Tasks UI -->
                <div id="ui-tasks" class="flex-1 hide space-y-4 overflow-y-auto">
                    <div id="task-items" class="space-y-3"></div>
                    <button onclick="addTaskRow()" class="w-full py-4 border-2 border-dashed border-leaf-light rounded-2xl text-leaf-light hover:text-grass font-bold">+ New Task</button>
                </div>

                <!-- Sketch UI -->
                <div id="ui-sketch" class="flex-1 hide bg-white rounded-3xl border-4 border-leaf-light overflow-hidden relative shadow-lg">
                    <canvas id="paint-canvas"></canvas>
                </div>

                <!-- Secret Message UI -->
                <div id="ui-secret" class="flex-1 hide flex flex-col gap-6">
                    <div class="bubble p-8 space-y-4">
                        <label class="font-bold opacity-60">Normal Message:</label>
                        <textarea id="secret-plain" class="w-full h-32" oninput="updateSecret()"></textarea>
                    </div>
                    <div class="bubble p-8 space-y-4 bg-bark/5 border-bark/10">
                        <label class="font-bold text-amber-800">Secret Code:</label>
                        <textarea id="secret-encoded" class="w-full h-32 text-amber-800 font-mono" oninput="updatePlain()"></textarea>
                    </div>
                </div>

                <!-- Flashcards UI -->
                <div id="ui-flashcards" class="flex-1 hide flex flex-col gap-8">
                    <div class="flex-1 flex flex-col items-center justify-center gap-8">
                        <div id="card-display" class="flip-card" onclick="this.classList.toggle('flipped')">
                            <div class="flip-card-inner">
                                <div class="flip-front" id="card-q">Click + to add a card!</div>
                                <div class="flip-back" id="card-a">Answer will show here.</div>
                            </div>
                        </div>
                        <div class="flex gap-4">
                            <button onclick="prevCard()" class="nav-pill bg-bark">Back</button>
                            <span id="card-counter" class="font-bold text-2xl px-4">0 / 0</span>
                            <button onclick="nextCard()" class="nav-pill bg-bark">Next</button>
                        </div>
                    </div>
                    <div class="bubble p-6 h-48 overflow-y-auto">
                         <div id="flash-editor-list" class="space-y-2"></div>
                         <button onclick="addFlashRow()" class="mt-4 text-grass font-bold">+ Add New Card</button>
                    </div>
                </div>
            </div>

            <script>
                let pybridge;
                let activeType = null;
                const canvas = document.getElementById('paint-canvas');
                const ctx = canvas.getContext('2d');
                let drawing = false;

                // Flashcard state
                let currentCards = [];
                let currentCardIdx = 0;

                new QWebChannel(qt.webChannelTransport, function(channel) {
                    pybridge = channel.objects.pybridge;
                    pybridge.loginSuccess.connect((user) => {
                        document.getElementById('login').classList.add('hide');
                        document.getElementById('dashboard').classList.remove('hide');
                        document.getElementById('welcome-text').innerText = "Hello, " + user + "!";
                    });
                    pybridge.loadFiles.connect(json => renderFiles(JSON.parse(json)));
                });

                function login() { pybridge.handleLogin(u.value, p.value); }

                function renderFiles(files) {
                    const grid = document.getElementById('file-grid');
                    grid.innerHTML = '';
                    files.forEach(f => {
                        const card = document.createElement('div');
                        card.className = `bubble p-4 flex flex-col items-center text-center cursor-pointer hover:scale-105 transition-transform`;
                        const icons = { diary:'feather', tasks:'list-checks', sketch:'palette', secret:'lock', flashcards:'layers' };
                        card.innerHTML = `<div class="p-3 bg-gray-50 rounded-2xl mb-2"><i data-lucide="${icons[f.type]}" class="w-6 h-6 text-bark/60"></i></div><span class="text-sm font-bold truncate w-full px-2">${f.name.split('.')[0]}</span>`;
                        card.onclick = () => openFile(f);
                        card.oncontextmenu = (e) => { e.preventDefault(); if(confirm("Discard this?")) pybridge.deleteFile(f.name); };
                        grid.appendChild(card);
                    });
                    lucide.createIcons();
                }

                function openFile(file) {
                    activeType = file.type;
                    document.getElementById('app-overlay').classList.add('active');
                    document.getElementById('file-title').value = file.name.split('.')[0];
                    ['ui-diary', 'ui-tasks', 'ui-sketch', 'ui-secret', 'ui-flashcards'].forEach(id => document.getElementById(id).classList.add('hide'));
                    document.getElementById('ui-' + file.type).classList.remove('hide');

                    if(file.type === 'diary') {
                        document.getElementById('diary-box').value = file.content;
                        document.getElementById('save-btn').onclick = () => { pybridge.saveFile(file_title.value, diary_box.value, 'diary'); closeApp(); };
                    } 
                    else if(file.type === 'tasks') {
                        document.getElementById('task-items').innerHTML = '';
                        file.content.forEach(t => addTaskRow(t.text, t.done));
                        document.getElementById('save-btn').onclick = () => {
                            const data = Array.from(document.querySelectorAll('#task-items > div')).map(d => ({ text: d.querySelector('input[type="text"]').value, done: d.querySelector('input[type="checkbox"]').checked }));
                            pybridge.saveFile(file_title.value, JSON.stringify(data), 'tasks'); closeApp();
                        };
                    } 
                    else if(file.type === 'sketch') {
                        resizeCanvas();
                        if(file.content.image) { let img = new Image(); img.onload = () => ctx.drawImage(img, 0, 0); img.src = file.content.image; }
                        else { ctx.fillStyle = "white"; ctx.fillRect(0,0,canvas.width,canvas.height); }
                        document.getElementById('save-btn').onclick = () => { pybridge.saveFile(file_title.value, JSON.stringify({image: canvas.toDataURL()}), 'sketch'); closeApp(); };
                    }
                    else if(file.type === 'secret') {
                        document.getElementById('secret-plain').value = file.content.plain || '';
                        updateSecret();
                        document.getElementById('save-btn').onclick = () => {
                            pybridge.saveFile(file_title.value, JSON.stringify({plain: secret_plain.value}), 'secret'); closeApp();
                        };
                    }
                    else if(file.type === 'flashcards') {
                        currentCards = Array.isArray(file.content) ? file.content : [];
                        currentCardIdx = 0;
                        renderFlashEditor();
                        updateCardDisplay();
                        document.getElementById('save-btn').onclick = () => {
                            saveFlashData();
                            pybridge.saveFile(file_title.value, JSON.stringify(currentCards), 'flashcards'); closeApp();
                        };
                    }
                }

                function newFile(type) { openFile({name: 'New ' + type, type: type, content: type === 'tasks' || type === 'flashcards' ? [] : (type === 'sketch' || type === 'secret' ? {} : '')}); }

                // Secret Message Logic
                function caesar(str, shift) {
                    return str.replace(/[a-z]/gi, c => {
                        const s = c <= 'Z' ? 65 : 97;
                        return String.fromCharCode(((c.charCodeAt(0) - s + shift) % 26 + 26) % 26 + s);
                    });
                }
                function updateSecret() { document.getElementById('secret-encoded').value = caesar(document.getElementById('secret-plain').value, 5); }
                function updatePlain() { document.getElementById('secret-plain').value = caesar(document.getElementById('secret-encoded').value, -5); }

                // Flashcard Logic
                function addFlashRow(q='', a='') {
                    const row = document.createElement('div');
                    row.className = 'flex gap-2';
                    row.innerHTML = `<input type="text" placeholder="Question" value="${q}" class="flex-1 text-sm"><input type="text" placeholder="Answer" value="${a}" class="flex-1 text-sm">`;
                    document.getElementById('flash-editor-list').appendChild(row);
                }
                function renderFlashEditor() {
                    document.getElementById('flash-editor-list').innerHTML = '';
                    currentCards.forEach(c => addFlashRow(c.q, c.a));
                }
                function saveFlashData() {
                    currentCards = Array.from(document.querySelectorAll('#flash-editor-list > div')).map(div => ({
                        q: div.querySelectorAll('input')[0].value,
                        a: div.querySelectorAll('input')[1].value
                    })).filter(c => c.q || c.a);
                }
                function updateCardDisplay() {
                    document.getElementById('card-display').classList.remove('flipped');
                    if(currentCards.length > 0) {
                        document.getElementById('card-q').innerText = currentCards[currentCardIdx].q;
                        document.getElementById('card-a').innerText = currentCards[currentCardIdx].a;
                        document.getElementById('card-counter').innerText = `${currentCardIdx + 1} / ${currentCards.length}`;
                    } else {
                        document.getElementById('card-q').innerText = "No cards yet!";
                        document.getElementById('card-a').innerText = "Add them below.";
                        document.getElementById('card-counter').innerText = "0 / 0";
                    }
                }
                function nextCard() { saveFlashData(); if(currentCards.length > 0) { currentCardIdx = (currentCardIdx + 1) % currentCards.length; updateCardDisplay(); } }
                function prevCard() { saveFlashData(); if(currentCards.length > 0) { currentCardIdx = (currentCardIdx - 1 + currentCards.length) % currentCards.length; updateCardDisplay(); } }

                function addTaskRow(text = '', done = false) {
                    const row = document.createElement('div');
                    row.className = 'flex items-center gap-4 bg-white/60 p-4 rounded-2xl border-2 border-leaf-light';
                    row.innerHTML = `<input type="checkbox" ${done ? 'checked' : ''} class="w-6 h-6 accent-grass"><input type="text" value="${text}" placeholder="New task..." class="flex-1 bg-transparent border-none !p-0">`;
                    document.getElementById('task-items').appendChild(row);
                }

                function resizeCanvas() {
                    const rect = canvas.parentElement.getBoundingClientRect();
                    canvas.width = rect.width; canvas.height = rect.height;
                    ctx.lineCap = 'round'; ctx.lineWidth = 6; ctx.strokeStyle = '#6D4C41';
                }
                canvas.onmousedown = (e) => { drawing = true; ctx.beginPath(); ctx.moveTo(e.offsetX, e.offsetY); };
                canvas.onmousemove = (e) => { if(drawing) { ctx.lineTo(e.offsetX, e.offsetY); ctx.stroke(); } };
                window.onmouseup = () => drawing = false;

                function closeApp() { document.getElementById('app-overlay').classList.remove('active'); }
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