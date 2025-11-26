J.A.R.V.I.S. — Local CLI AI Assistant for Linux & WSL

J.A.R.V.I.S. is a command-line AI assistant designed to run locally on Linux and Windows Subsystem for Linux (WSL). It uses your local Ollama models and provides tools such as:

• Local file reading
• Folder creation
• ASCII art and image conversion
• Weather lookup
• Web search (DuckDuckGo)
• Python execution
• Persistent memory system
• Custom 5x5 throbber animation
• Multi-threaded tool execution

The included installer automatically creates:
• A dedicated virtual environment (jarvis-venv)
• A persistent install directory (~/.local/share/jarvis)
• A global shell command: jarvis

------------------------------------------------------------
Installation (Linux & WSL)
------------------------------------------------------------

1. Clone the repository:

git clone https://github.com/<yourname>/<repo>.git
cd <repo>

2. Run the installer:

bash jarvis-installer.sh

The installer will:
• Create ~/.local/share/jarvis
• Create a virtual environment: jarvis-venv
• Install all required dependencies:
  ollama, requests, ddgs, psutil, beautifulsoup4, pillow, pyfiglet
• Copy jarvis.py into the install directory
• Create executable command ~/.local/bin/jarvis
• Add ~/.local/bin to PATH if needed

------------------------------------------------------------
Running JARVIS
------------------------------------------------------------

After installation, simply run:

jarvis

No need to activate the virtual environment manually.

------------------------------------------------------------
Restarting and Exiting
------------------------------------------------------------

Inside JARVIS:

To exit:
/bye
or press CTRL+C

To restart:
/rb

------------------------------------------------------------
Switching the Ollama Model
------------------------------------------------------------

JARVIS uses an Ollama model defined inside jarvis.py:

CONFIG = {
    "model": "granite3.1-moe",
    ...
}

To change the model:

1. Edit the installed file:
   nano ~/.local/share/jarvis/jarvis.py

2. Find the line containing:
   "model": "granite3.1-moe"

3. Replace it with any model you have installed in Ollama, for example:
   "model": "llama3.2"

4. Save the file.

5. Restart JARVIS using the command:
/rb

------------------------------------------------------------
Install Locations
------------------------------------------------------------

Main program:
~/.local/share/jarvis/jarvis.py

Virtual environment:
~/.local/share/jarvis/jarvis-venv

Launcher command:
~/.local/bin/jarvis

Memory files:
Stored inside ~/.local/share/jarvis

------------------------------------------------------------
Uninstalling
------------------------------------------------------------

rm -rf ~/.local/share/jarvis
rm ~/.local/bin/jarvis

Restart your terminal afterward.

------------------------------------------------------------
Requirements
------------------------------------------------------------

• Linux or WSL
• Python 3.8+
• Ollama installed (https://ollama.ai)

------------------------------------------------------------
Enjoy!
------------------------------------------------------------

JARVIS is built to be fast, customizable, and deeply personal.

If you want:
• A .deb package
• Auto-update functionality
• Windows installer
• A more advanced UI
• A VSCode extension version

Just ask!
