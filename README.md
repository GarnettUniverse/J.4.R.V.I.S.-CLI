# J.A.R.V.I.S. — Local CLI AI Assistant for Linux & WSL

J.A.R.V.I.S. is a fully offline, terminal-based AI assistant designed for **Linux** and **Windows Subsystem for Linux (WSL)**.  
It uses local **Ollama** models and includes an advanced tool system, persistent memory, animated terminal visuals, and a clean interactive CLI experience.

---

## ⚡ Features

- Runs completely locally (no cloud dependencies)
- Uses any Ollama model you have installed
- Beautiful animated 5×5 terminal throbber
- Persistent memory (user profile + project notes)
- File browsing & manipulation tools
- Built-in Python execution
- Web search via DuckDuckGo (DDGS)
- Weather API integration (Needs Free OpenWeatherMap API key)
- ASCII art + image-to-ASCII converter
- Multi-threaded tool execution
- Easy installer & global command

---

## 🚀 Installation (Linux & WSL)

### 1. Clone the repository

```bash
git clone [http://github.com/GarnettUniverse/J.4.R.V.I.S.-CLI]
cd <repo>
```

### 2. Run the installer

```bash
bash jarvis-installer.sh
```

The installer will:

- Create `~/.local/share/jarvis`
- Create a virtual environment: `jarvis-venv`
- Install all required Python dependencies:
  - ollama  
  - requests  
  - ddgs  
  - psutil  
  - beautifulsoup4  
  - pillow  
  - pyfiglet  
- Copy `jarvis.py` into the install directory
- Create a global executable command: `jarvis`
- Add `~/.local/bin` to your PATH if missing

Once complete, your system will have a new global command:

```bash
jarvis
```

---

## 🧠 Running JARVIS

Just type:

```bash
jarvis
```

No need to activate the venv manually — the launcher script handles everything.

---

## 🔄 Restarting & Exiting the Program

Inside JARVIS:

### Exit:
```
/bye
```
or **CTRL + C**

### Restart:
```
/rb
```

This fully restarts the assistant without leaving the terminal.

---

## 🤖 Switching the Ollama Model

JARVIS uses the model defined in the configuration block inside `jarvis.py`:

```python
CONFIG = {
    "model": "granite3.1-moe",
    ...
}
```

### To change it:

1. Edit the installed file:

```bash
nano ~/.local/share/jarvis/jarvis.py
```

2. Find:

```python
"model": "granite3.1-moe"
```

3. Replace it with any model you have locally:

```python
"model": "llama3.2"
```

4. Save the file.

5. Restart JARVIS:

```
/rb
```

---

## 📁 Installation Paths

| Component | Location |
|----------|-----------|
| Main program | `~/.local/share/jarvis/jarvis.py` |
| Virtual environment | `~/.local/share/jarvis/jarvis-venv` |
| Launcher command | `~/.local/bin/jarvis` |
| Memory files | `~/.local/share/jarvis/` |

---

## 🧹 Uninstalling JARVIS

```bash
rm -rf ~/.local/share/jarvis
rm ~/.local/bin/jarvis
```

Restart your terminal afterward.

---

## 🛠 Requirements

- Linux or WSL
- Python 3.8 or newer
- Ollama installed locally  
  https://ollama.ai

---

## 🎉 Enjoy Your Personal CLI Assistant!

JARVIS is designed to be fast, flexible, beautiful, and completely personal.

If you want:
- A `.deb` package  
- Auto-update support  
- A Windows installer  
- Further tool integrations  
- A VSCode extension  

Just ask — I can generate all of it!
