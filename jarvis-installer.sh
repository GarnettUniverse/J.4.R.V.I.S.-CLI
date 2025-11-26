#!/usr/bin/env bash
set -e

echo ">>> Installing JARVIS..."

INSTALL_DIR="$HOME/.local/share/jarvis"
BIN_DIR="$HOME/.local/bin"
VENV="$INSTALL_DIR/jarvis-venv"

mkdir -p "$INSTALL_DIR" "$BIN_DIR"

echo ">>> Downloading jarvis.py"
curl -s -L "https://raw.githubusercontent.com/<yourname>/<repo>/main/jarvis.py" -o "$INSTALL_DIR/jarvis.py"

echo ">>> Creating virtual environment"
python3 -m venv "$VENV"

echo ">>> Installing dependencies"
"$VENV/bin/pip" install --upgrade pip
"$VENV/bin/pip" install ollama requests ddgs psutil beautifulsoup4 pillow pyfiglet

echo ">>> Creating launcher script"
cat << 'EOF' > "$BIN_DIR/jarvis"
#!/usr/bin/env bash
APP="$HOME/.local/share/jarvis/jarvis.py"
VENV="$HOME/.local/share/jarvis/jarvis-venv"
source "$VENV/bin/activate"
python "$APP"
EOF

chmod +x "$BIN_DIR/jarvis"

if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
    echo ">>> Added ~/.local/bin to PATH (restart terminal)"
fi

echo ">>> Done! Run:  jarvis"
