#!/usr/bin/env python3
import asyncio
import sys
import re
import os
import io
import contextlib
import time
import psutil
import platform
import getpass
import aiohttp
import numpy as np
import pyfiglet
import warnings
import shutil
import ast
import itertools

# [CRITICAL FIX] Enable Arrow Keys & History Support
try:
    import readline
except ImportError:
    pass 

# [FIX] Silence specific library warnings
warnings.filterwarnings("ignore", category=RuntimeWarning)

# [OPTIMIZATION] Fast JSON
try:
    import orjson as json
    JSON_MODE_READ = 'rb'
    JSON_MODE_WRITE = 'wb'
except ImportError:
    import json
    JSON_MODE_READ = 'r'
    JSON_MODE_WRITE = 'w'

# [OPTIMIZATION] Computer Vision
try:
    import cv2
except ImportError:
    cv2 = None 

# [OPTIMIZATION] Async Libraries
from ollama import AsyncClient
from bs4 import BeautifulSoup

# [FIX] Robust Search Import
try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

# [OPTIMIZATION] High-performance Event Loop
try:
    import uvloop
except ImportError:
    uvloop = None

# [OPTIMIZATION] True Async File I/O
try:
    import aiofiles
except ImportError:
    aiofiles = None 

# ==========================================
# [GLOBAL STATE]
# ==========================================
MESSAGES = []

# Default Configuration
CONFIG = {
    "model": "llama3.2:3b",           
    "ai_name": "J.4.R.V.I.S.",           
    "prompt_user": "[USER] >> ",         
    "prompt_ai":   "[J4.RVIS] >> ",      
    "loading_phrase": "Thinking...",     
    "min_tool_display_time": 1.2,        
    "color_user": "\033[92m",            # Green 
    "color_ai":   "\033[96m",            # Cyan 
    "color_sys":  "\033[93m",            # Yellow
    "color_reset": "\033[0m",            
    "weather_api_key": "66294a9e35a864a6cc716af9f6872695", 
    "file_memory_user": "ai_memory_user.json",       
    "file_memory_convo": "ai_memory_conversations.json", 
    "ascii_width": 100,                              
    "safe_roots": ["~", "/tmp/"],
    "startup_banner": None, 
    # [HARDWARE TUNING] Radeon 5700 (8GB VRAM) Optimized Settings
    "ctx_len": 8192,
    "temp": 0.1,      # Extremely low temp to prevent hallucination
}

RUNTIME_STATE = {"emoji_mode": False}

# --- SYSTEM INSTRUCTIONS ---
SYSTEM_INSTRUCTIONS = """You are {ai_name}, a CLI assistant.
CWD: {cwd}

{user_block}
{convo_block}

=== TOOL DEFINITIONS ===
1. web_search(query): REQUIRED for stocks, news, prices, or ANY info you don't know.
2. get_system_stats(): For CPU/RAM usage.
3. list_directory(path): To see files in a folder.
4. read_file(filename): To see file content.
5. create_directory(path): To make new folders.
6. delete_directory(path): To remove folders.
7. create_file(filename, content): To make new files.
8. edit_file(filename, content): To overwrite existing files.
9. delete_file(filename): To remove files.
10. run_python_code(code): For math, logic, or data processing.
11. get_weather(city): For temperature/forecast.
12. convert_image_to_ascii(path, width={ascii_width}): For local images.
13. find_and_convert_ascii(query, width={ascii_width}): Search generic images.
14. store_user_info(info): Save facts about the user.
15. store_conversation_note(note): Save context about the chat.

=== PROTOCOL ===
1. **THINK FIRST**: You may analyze, reason, or plan before answering.
2. **TOOL USAGE**: If you need a tool, output the call alone (e.g., `web_search(...)`).
3. **FINAL ANSWER**: When you are ready to speak to the user, you MUST start your final response with `***ANSWER***`.
   - Everything before this tag will be hidden from the user.
   - Everything after this tag will be shown.

=== EXAMPLES ===
User: "What is 25 * 48?"
You: I need to calculate this.
run_python_code(code='print(25 * 48)')
System: [TOOL RESULT] 1200
You: The calculation is complete.
***ANSWER***
The answer is 1200.

User: "Find pizza in Buffalo."
You: I need to search for pizza places.
web_search(query='pizza places Buffalo NY')
System: [TOOL RESULT] Duff's, Anchor Bar...
You: I found the results.
***ANSWER***
The best pizza places in Buffalo are Duff's and Anchor Bar.

{emoji_rule}
"""

# ==========================================
# [COMPACT SPINNER CLASS]
# ==========================================
class SpinnerState:
    def __init__(self):
        self.messages = [CONFIG['loading_phrase']]
        self.running = False
        self.task = None
    def update(self, new_messages):
        if isinstance(new_messages, str): self.messages = [new_messages]
        elif isinstance(new_messages, list) and new_messages: self.messages = new_messages
        else: self.messages = [CONFIG['loading_phrase']]
    async def start(self):
        if not self.running:
            self.running = True
            self.task = asyncio.create_task(loading_animation(self))
    async def stop(self):
        self.running = False
        if self.task: 
            await self.task
            self.task = None
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()

async def loading_animation(state: SpinnerState):
    # [OPTIMIZATION] Ultra-compact spinner for small screens
    spinner_chars = itertools.cycle(['|', '/', '-', '\\'])
    idx = 0
    last_cycle = time.time()
    cycle_speed = 1.5 # Seconds per text message
    
    sys.stdout.write("\033[?25l") # Hide cursor
    try:
        while state.running:
            # Rotate text messages if list is provided
            msgs = state.messages
            if time.time() - last_cycle > cycle_speed:
                idx = (idx + 1) % len(msgs)
                last_cycle = time.time()
            if idx >= len(msgs): idx = 0
            
            # Truncate text to fit very small screens
            current_text = msgs[idx].replace("\n", " ").strip()[:40]
            char = next(spinner_chars)
            
            # Format: [ / ] Thinking...
            sys.stdout.write(f"\r\033[K{CONFIG['color_sys']}[ {char} ] {current_text}{CONFIG['color_reset']}")
            sys.stdout.flush()
            await asyncio.sleep(0.1)
    except Exception: pass
    finally:
        sys.stdout.write("\r\033[K")
        sys.stdout.write("\033[?25h") # Show cursor
        sys.stdout.flush()

SPINNER = SpinnerState()

# ==========================================
# [SAFE FILE SYSTEM TOOLS]
# ==========================================
def resolve_path(path):
    try:
        expanded = os.path.expanduser(path)
        return os.path.abspath(expanded)
    except Exception:
        return None

def is_safe_path(path):
    if ".." in path: return False
    abs_path = resolve_path(path)
    if not abs_path: return False
    
    allowed_roots = [os.path.abspath(os.path.expanduser(r)) for r in CONFIG['safe_roots']]
    if 'microsoft' in platform.uname().release.lower() or 'wsl' in platform.uname().release.lower():
        allowed_roots.append("/mnt/")
        
    return any(abs_path.startswith(root) for root in allowed_roots)

async def confirm_action(action, target):
    await SPINNER.stop()
    sys.stdout.write("\n") 
    prompt = f"{CONFIG['color_sys']}╔════════════════════════════════════════════════╗\n║  ⚠️  CONFIRMATION REQUIRED                     ║\n║  ACTION: {action:<37} ║\n║  TARGET: {target[-40:]:<37} ║\n╚════════════════════════════════════════════════╝\n[?] Proceed? (y/n) >> {CONFIG['color_reset']}"
    response = await asyncio.to_thread(input, prompt)
    return response.strip().lower() == 'y'

async def list_directory(path="."):
    safe = resolve_path(path)
    if not is_safe_path(safe): return "Denied: Unsafe path."
    if not os.path.exists(safe): return "Error: Path not found."
    return await asyncio.to_thread(lambda: ", ".join(os.listdir(safe)[:50]))

async def read_file(filename):
    safe = resolve_path(filename)
    if not is_safe_path(safe): return "Denied: Unsafe path."
    if not os.path.exists(safe): return "Error: File not found."
    
    if aiofiles:
        async with aiofiles.open(safe, 'r', encoding='utf-8', errors='replace') as f:
            content = await f.read()
            return content[:2000]
    else:
        with open(safe, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()[:2000]

async def create_directory(path):
    safe = resolve_path(path)
    if not is_safe_path(safe): return "Denied: Unsafe path."
    if os.path.exists(safe): return f"Directory already exists: {safe}"
    
    if await confirm_action("CREATE DIR", safe):
        await asyncio.to_thread(os.makedirs, safe, exist_ok=True)
        return f"Directory created: {safe}"
    return "Cancelled."

async def delete_directory(path):
    safe = resolve_path(path)
    if not is_safe_path(safe): return "Denied: Unsafe path."
    if not os.path.exists(safe): return "Error: Directory not found."
    
    if await confirm_action("DELETE DIR", safe):
        try:
            await asyncio.to_thread(shutil.rmtree, safe)
            return "Directory deleted."
        except Exception as e: return f"Error: {e}"
    return "Cancelled."

async def create_file(filename, content):
    safe = resolve_path(filename)
    if not is_safe_path(safe): return "Denied: Unsafe path."
    if os.path.exists(safe): return "Error: File exists. Use edit_file."
    
    if await confirm_action("CREATE FILE", safe):
        if aiofiles:
            async with aiofiles.open(safe, 'w', encoding='utf-8') as f: await f.write(content)
        else:
            with open(safe, 'w', encoding='utf-8') as f: f.write(content)
        return f"File created: {safe}"
    return "Cancelled."

async def edit_file(filename, content):
    safe = resolve_path(filename)
    if not is_safe_path(safe): return "Denied: Unsafe path."
    
    if await confirm_action("OVERWRITE FILE", safe):
        if aiofiles:
            async with aiofiles.open(safe, 'w', encoding='utf-8') as f: await f.write(content)
        else:
            with open(safe, 'w', encoding='utf-8') as f: f.write(content)
        return "File updated."
    return "Cancelled."

async def delete_file(filename):
    safe = resolve_path(filename)
    if not is_safe_path(safe): return "Denied: Unsafe path."
    if not os.path.exists(safe): return "Error: File not found."
    
    if await confirm_action("DELETE FILE", safe):
        await asyncio.to_thread(os.remove, safe)
        return "File deleted."
    return "Cancelled."

# ==========================================
# [OTHER TOOLS]
# ==========================================
SEARCH_SESSION = DDGS()

async def web_search(query, count=3):
    try:
        def _s():
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                res = SEARCH_SESSION.text(query, max_results=count)
                if not res: return "Search returned no results."
                formatted = []
                for r in res:
                    title = r.get('title', 'No Title')
                    body = r.get('body', 'No Content')
                    formatted.append(f"Title: {title}\nSummary: {body}\n---")
                return "\n".join(formatted)
        return await asyncio.to_thread(_s)
    except Exception as e: return f"Search Error: {e}"

async def get_system_stats():
    return await asyncio.to_thread(lambda: f"CPU: {psutil.cpu_percent()}% | RAM: {psutil.virtual_memory().percent}%")

async def run_python_code(code: str) -> str:
    def _exec():
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf): exec(code, {'__builtins__': __builtins__}, {})
        return buf.getvalue()
    try: return f"Output:\n{await asyncio.to_thread(_exec)}"
    except Exception as e: return f"Error: {e}"

async def get_weather(city):
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"q": city, "units": "imperial", "appid": CONFIG['weather_api_key']}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, params=params) as r:
                if r.status != 200: return "Location not found."
                d = await r.json()
                return f"Weather in {d['name']}: {d['weather'][0]['description']}, {d['main']['temp']}F"
    except Exception as e: return f"API Error: {e}"

async def convert_image_to_ascii(path, width=CONFIG['ascii_width']):
    path = path.strip("'\"")
    if not os.path.exists(path) or cv2 is None: return "Error: OpenCV missing or file not found."
    def _p():
        img = cv2.imread(path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        new_h = int((h/w) * width * 0.55)
        resized = cv2.resize(gray, (width, new_h), interpolation=cv2.INTER_LINEAR)
        chars = np.array(list(" .:-=+*#%@"))
        return "\n" + "\n".join("".join(r) for r in chars[(resized/255*(len(chars)-1)).astype(int)]) + "\n"
    return await asyncio.to_thread(_p)

async def find_and_convert_ascii(query, width=CONFIG['ascii_width']):
    try:
        def _get_url():
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                res = SEARCH_SESSION.images(query, max_results=1)
                r = list(res)
                return r[0]['image'] if r else None
        url = await asyncio.to_thread(_get_url)
        if not url: return "No image."
        tf = f"temp_{int(time.time())}.jpg"
        async with aiohttp.ClientSession() as s:
            async with s.get(url) as r: 
                data = await r.read()
                if aiofiles:
                    async with aiofiles.open(tf, 'wb') as f: await f.write(data)
                else:
                    with open(tf, 'wb') as f: f.write(data)
        art = await convert_image_to_ascii(tf, width)
        await asyncio.to_thread(os.remove, tf)
        return art
    except Exception as e: return f"Error: {e}"

async def generate_ascii_banner(text):
    return await asyncio.to_thread(lambda: "\n" + pyfiglet.figlet_format(text) + "\n")

# ==========================================
# [MEMORY HELPERS]
# ==========================================
async def _safe_write(path, content, mode='w'):
    if aiofiles:
        async with aiofiles.open(path, mode, encoding='utf-8' if 'b' not in mode else None) as f:
            await f.write(content)
    else:
        with open(path, mode, encoding='utf-8' if 'b' not in mode else None) as f:
            f.write(content)

async def _safe_read(path, mode='r'):
    if not os.path.exists(path): return None
    if aiofiles:
        async with aiofiles.open(path, mode, encoding='utf-8' if 'b' not in mode else None) as f:
            return await f.read()
    else:
        with open(path, mode, encoding='utf-8' if 'b' not in mode else None) as f:
            return f.read()

async def store_generic(fpath, item):
    try:
        raw = await _safe_read(fpath, mode=JSON_MODE_READ)
        data = json.loads(raw) if raw else {"facts": []}
        if item in data["facts"]: return None
        data["facts"].append(item)
        if hasattr(json, 'OPT_INDENT_2'): new_content = json.dumps(data, option=json.OPT_INDENT_2)
        else: new_content = json.dumps(data, indent=2)
        await _safe_write(fpath, new_content, mode=JSON_MODE_WRITE)
        await update_system_prompt()
        return "Saved."
    except Exception as e: return f"Error: {e}"

async def init_memory():
    initial_data = json.dumps({"facts": []})
    mode = 'wb' if isinstance(initial_data, bytes) else 'w'
    for fpath in [CONFIG['file_memory_user'], CONFIG['file_memory_convo']]:
        if not os.path.exists(fpath):
            try: await _safe_write(fpath, initial_data, mode=mode)
            except: pass

async def load_all_memories():
    u_facts, c_facts = [], []
    try:
        u_raw = await _safe_read(CONFIG['file_memory_user'], mode=JSON_MODE_READ)
        c_raw = await _safe_read(CONFIG['file_memory_convo'], mode=JSON_MODE_READ)
        if u_raw: u_facts = json.loads(u_raw).get("facts", [])
        if c_raw: c_facts = json.loads(c_raw).get("facts", [])
    except: pass
    return u_facts, c_facts

async def update_system_prompt():
    global MESSAGES
    u, c = await load_all_memories()
    ub = ("\n--- USER ---\n" + "\n".join([f"- {m}" for m in u])) if u else ""
    cb = ("\n--- MEMORY ---\n" + "\n".join([f"- {m}" for m in c])) if c else ""
    emoji_rule = "EMOJIS: You are allowed to use emojis." if RUNTIME_STATE['emoji_mode'] else "EMOJIS: STRICTLY NO emojis."
    prompt = SYSTEM_INSTRUCTIONS.format(
        ai_name=CONFIG['ai_name'], cwd=os.getcwd(), user_block=ub, convo_block=cb, 
        ascii_width=CONFIG['ascii_width'], emoji_rule=emoji_rule
    )
    if MESSAGES: 
        MESSAGES[0]['content'] = prompt
    else:
        MESSAGES.append({'role': 'system', 'content': prompt})

# ==========================================
# [CORE ENGINE]
# ==========================================
TOOLS = {
    'web_search': web_search, 'get_system_stats': get_system_stats,
    'list_directory': list_directory, 'read_file': read_file,
    'create_directory': create_directory, 'delete_directory': delete_directory,
    'create_file': create_file, 'edit_file': edit_file, 'delete_file': delete_file,
    'run_python_code': run_python_code, 'get_weather': get_weather,
    'convert_image_to_ascii': convert_image_to_ascii, 'find_and_convert_ascii': find_and_convert_ascii,
    'store_user_info': lambda i: store_generic(CONFIG['file_memory_user'], i),
    'store_conversation_note': lambda n: store_generic(CONFIG['file_memory_convo'], n),
    'generate_ascii_banner': generate_ascii_banner
}

# [CRITICAL] Balanced Parsing + Fallback
def parse_tool_calls(content):
    calls = []
    # 1. Check for Code Blocks (Llama 3.2 often puts calls in markdown)
    code_blocks = re.findall(r'
http://googleusercontent.com/immersive_entry_chip/0
