import ollama
import sys
import re
import os
import io
import json
import contextlib
import concurrent.futures
import threading
import time

# Initialize a persistent ThreadPoolExecutor for concurrent tool execution
executor = concurrent.futures.ThreadPoolExecutor() 

# [FIX] Import readline for input history
try:
    import readline
except ImportError:
    pass 

# [WSL SETUP] Detect Windows User
try:
    win_user = os.popen('cmd.exe /c "echo %USERNAME%" 2>/dev/null').read().strip()
    if not win_user: win_user = "User"
    WIN_DOWNLOADS = f"/mnt/c/Users/{win_user}/Downloads"
except Exception:
    win_user = "User"
    WIN_DOWNLOADS = "/mnt/c/Users/User/Downloads"

# ==========================================
# [DEPENDENCIES]
# ==========================================
import requests
from ddgs import DDGS
import psutil
from bs4 import BeautifulSoup
from PIL import Image
import pyfiglet

# ==========================================
# [CONFIGURATION]
# ==========================================
FILE_USER_DATA = "ai_memory_user.json"
FILE_CONVO_DATA = "ai_memory_conversations.json"

CONFIG = {
    "model": "granite3.1-moe", 
    "prompt_user": "[USR] >> ",
    "prompt_ai":   "[J.4.R.V.I.S.] >> ", 
    "color_user": "\033[92m", "color_ai": "\033[96m", "color_sys": "\033[93m", "color_reset": "\033[0m",
    "weather_api_key": "YOUR OPENWEATHERMAP_API_KEY HERE"  # <-- REPLACE WITH YOUR KEY 
}

MESSAGES = [] 

# ==========================================
# [THROBBER]
# ==========================================

# 5x5 spinning frames (Reverted to the multi-line design)
throbber_frames = [
    ["  #####  ", "  #   #  ", "  #   #  ", "  #   #  ", "  #####  "], # Full box (Initial)
    ["  #####  ", "  >   #  ", "  #   #  ", "  #   <  ", "  #####  "], # Frame 1 (Corners)
    ["  #####  ", "  > # <  ", "  #   #  ", "  < # >  ", "  #####  "], # Frame 2 (Center)
    ["  #####  ", "  >#< #  ", "  #   #  ", "  # <#>  ", "  #####  "], # Frame 3 (Side lines)
    ["  #####  ", "  #####  ", "  #####  ", "  #####  ", "  #####  "]  # Solid (End)
]
throbber_running = threading.Event()
THROBBER_ROWS = len(throbber_frames[0]) # 5 rows for cleanup

def throbber_animation(delay_time=0.25):
    """
    Runs the multi-line 5x5 spinning throbber animation.
    Uses ANSI escape codes for cursor positioning.
    """
    time.sleep(delay_time)
    if not throbber_running.is_set():
        return # Exit if the operation was too fast (less than 0.25s)

    # Print initial blank space to occupy terminal lines
    sys.stdout.write("\n" * THROBBER_ROWS) 

    try:
        while throbber_running.is_set():
            # Define the spin sequence for visual appeal
            for frame_index in [0, 1, 2, 3, 2, 1]: 
                if not throbber_running.is_set():
                    break
                
                # Move cursor back up to the start of the occupied space
                sys.stdout.write(f"\033[{THROBBER_ROWS}A") 
                
                # Print the current frame
                for line in throbber_frames[frame_index]:
                    sys.stdout.write(f"{CONFIG['color_sys']}{line:<10}{CONFIG['color_reset']}\n")
                
                sys.stdout.flush()
                time.sleep(0.1)
    except Exception:
        pass

def loading_bar_start_stop(func, *args, **kwargs):
    """Wraps a function call with the multi-line spinning throbber."""
    throbber_running.clear()
    t = threading.Thread(target=throbber_animation, daemon=True)
    
    # 1. Start the throbber thread
    t.start()
    throbber_running.set()
    
    result = None
    try:
        # 2. Execute the wrapped function
        result = func(*args, **kwargs)
    finally:
        # 3. Stop the throbber thread
        throbber_running.clear()
        t.join(timeout=0.1) 
        
        # 4. Clean up the multi-line output if the throbber was running
        if t.is_alive() or t.ident: # Check if the thread ran or completed
            # Move cursor back up (THROBBER_ROWS lines)
            sys.stdout.write(f"\033[{THROBBER_ROWS}A") 
            # Clear all lines that were used by the throbber
            sys.stdout.write('\033[K\n' * THROBBER_ROWS) 
            # Move cursor back up to the point where the AI output will start
            sys.stdout.write(f"\033[{THROBBER_ROWS}A") 
            sys.stdout.flush()

    return result

# ==========================================
# [MEMORY SYSTEM]
# ==========================================
def init_memory():
    """Checks for both memory files on startup, creates if missing."""
    for fpath in [FILE_USER_DATA, FILE_CONVO_DATA]:
        if not os.path.exists(fpath):
            try:
                with open(fpath, 'w', encoding='utf-8') as f:
                    json.dump({"facts": []}, f) 
            except: pass

def load_all_memories():
    """Reads both JSON files to inject into the AI's brain."""
    user_facts = []
    convo_facts = []
    
    try:
        with open(FILE_USER_DATA, 'r', encoding='utf-8') as f:
            user_facts = json.load(f).get("facts", [])
    except: pass

    try:
        with open(FILE_CONVO_DATA, 'r', encoding='utf-8') as f:
            convo_facts = json.load(f).get("facts", [])
    except: pass
    
    return user_facts, convo_facts

def store_user_info(info: str) -> str:
    """Saves info SPECIFIC TO THE USER. Updates the system prompt in place."""
    try:
        with open(FILE_USER_DATA, 'r', encoding='utf-8') as f:
            data = json.load(f)
            facts = data.get("facts", [])
        
        if info in facts: return "I already know this about you."
        
        facts.append(info)
        
        with open(FILE_USER_DATA, 'w', encoding='utf-8') as f:
            json.dump({"facts": facts}, f, indent=4)
        
        update_system_prompt()
        return "Saved to User Profile."
    except Exception as e: return f"Error: {e}"

def store_conversation_note(note: str) -> str:
    """Saves GENERAL NOTES or SUMMARIES. Updates the system prompt in place."""
    try:
        with open(FILE_CONVO_DATA, 'r', encoding='utf-8') as f:
            data = json.load(f)
            facts = data.get("facts", [])
        
        if note in facts: return "This note already exists."
        
        facts.append(note)
        
        with open(FILE_CONVO_DATA, 'w', encoding='utf-8') as f:
            json.dump({"facts": facts}, f, indent=4)
        
        update_system_prompt()
        return "Saved to Conversation Log."
    except Exception as e: return f"Error: {e}"

# ==========================================
# [SYSTEM PROMPT]
# ==========================================

def build_system_prompt(user_facts, convo_facts):
    """Generates the full system prompt content."""
    user_block = ""
    if user_facts:
        user_block = "\n--- USER PROFILE (Permanent Data) ---\n" + "\n".join([f"- {m}" for m in user_facts])
        
    convo_block = ""
    if convo_facts:
        convo_block = "\n--- PAST CONVERSATION NOTES (Projects & Ideas) ---\n" + "\n".join([f"- {m}" for m in convo_facts])

    return f"""
You are "J.4.R.V.I.S.", a CLI assistant running on WSL.
Current Directory: {os.getcwd()}

{user_block}
{convo_block}

TOOLS:
1. web_search(query)
2. get_system_stats()
3. list_files(path)
4. read_local_file(filename)
5. create_folder(name)
6. save_to_file(name, content)
7. delete_file(name)
8. run_python_code(code)
9. get_weather(city)
10. convert_image_to_ascii(path, width=100)
11. generate_ascii_banner(text)
12. find_and_convert_ascii(query, width=100)

MEMORY TOOLS (USE CORRECTLY):
13. store_user_info(info)
14. store_conversation_note(note)

INSTRUCTIONS:
- If the question requires NO tool call (e.g., general knowledge), answer immediately.
- IF A TOOL IS REQUIRED, YOU MUST NOT OUTPUT ANY TEXT BEFORE THE TOOL CALL.
- If the user asks for the weather, you MUST immediately call the 'get_weather(city)' tool.
- If the user asks a question that requires external/current knowledge (e.g., locations, reviews, facts, but NOT weather), you MUST immediately call the 'web_search(query)' tool.
- If the user asks for a simple calculation or Python code execution, you MUST immediately call the 'run_python_code(code)' tool. **DO NOT use 'run_python_code' for searches, API calls, or finding external data.**
- STRICTLY DO NOT use emojis.
- STRICTLY DO NOT ask the user any questions, offer options, or request additional information.
- STRICTLY DO NOT reference the tools you used in your final answer.
- **NEVER use the phrase "I'm unable to access the web" or any variation implying a lack of capability, especially after a tool has been called.** You must use the tool results available in the history.
- Your final tone must be immediate, decisive, and fully informative.
- When returning multiple items, use numbered or bulleted list format.
"""

def update_system_prompt():
    """Updates the system message in the global MESSAGES list to reflect new memory."""
    if MESSAGES:
        user_facts, convo_facts = load_all_memories()
        MESSAGES[0]['content'] = build_system_prompt(user_facts, convo_facts)

# ==========================================
# [VISUALS]
# ==========================================
def print_banner():
    # YOUR EXACT BANNER - DO NOT TOUCH
    art_lines = [
        "      .@@@@@@@         :     o      .oo  .oPYo. o     o o .oPYo.",
        "    -@@@@@@@@@@@       :     8     .P 8  8   `8 8     8 8 8     ",
        "   .@@@@@@@@@@@@@      :     8    .P  8 o8YooP' 8     8 8 `Yooo.",
        "   -@@@@@@@@@@@@@-     :     8   oPooo8  8   `b `b   d' 8     `8",
        "   :@@   ::#  :@@:     :     8  .P    8  8    8  `b d'  8      8",
        "   '#    =@%   =@      :   oP' .P     8  8    8   `8'   8 `YooP'",
        "    @#=:*: @*+%@@      :   ...:..:::::..:..:::..:::..:::..:.....:",
        "    .  -@..=@:=:.      :   ::::::::::::::::::::::::::::::::::::::",
        "       %@@%@@#         :   ::::::::::::::::::::::::::::::::::::::"
    ]
    max_len = max(len(line) for line in art_lines)
    print(f"{CONFIG['color_ai']}")
    print(f"╔{'═'*(max_len+2)}╗")
    for line in art_lines: print(f"║ {line:<{max_len}} ║")
    print(f"╚{'═'*(max_len+2)}╝{CONFIG['color_reset']}")

def is_safe(path): 
    return not (".." in path or path.startswith("~") or (os.path.isabs(path) and not path.startswith("/mnt/")))

# ==========================================
# [TOOL EXECUTION HELPER]
# ==========================================
def execute_tool_task(tool_name, tool_args, debug_mode=False):
    """Executes a single tool function and handles logging/error visibility."""
    func = TOOLS[tool_name]
    result = None
    
    try:
        result = func(**tool_args)

        if debug_mode:
            arg_str = json.dumps(tool_args)
            res_str = str(result)
            
            print(f"\n{CONFIG['color_sys']}╔{'═'*70}╗")
            print(f"║ [DEBUG] TOOL CALL: {tool_name}")
            print(f"║ [DEBUG] ARGS: {arg_str}")
            print(f"║ [DEBUG] RESULT (Preview): {res_str[:100]}...")
            print(f"╚{'═'*70}╝{CONFIG['color_reset']}", end="", flush=True)

    except Exception as e:
        error_msg = f"Error processing args for {tool_name}: {e}"
        result = error_msg
        
        if debug_mode:
            print(f"\n{CONFIG['color_sys']}╔{'═'*70}╗")
            print(f"║ [DEBUG ERROR] TOOL: {tool_name}")
            print(f"║ [DEBUG ERROR] MESSAGE: {error_msg}")
            print(f"╚{'═'*70}╝{CONFIG['color_reset']}", end="", flush=True)

    return {'role': 'tool', 'content': str(result), 'name': tool_name}


# ==========================================
# [TOOLS]
# ==========================================
def find_and_convert_ascii(query: str, width: int = 100) -> str:
    temp_file = "auto_ascii_temp.png"
    
    try:
        image_results = DDGS().images(query, max_results=1) 
        if not image_results:
            return f"Error: Could not find an image online for the query: '{query}'."
        image_url = image_results[0]['image']
        
        response = requests.get(image_url, stream=True, timeout=5) 
        response.raise_for_status()
        
        with open(temp_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192): f.write(chunk)
        
        img = Image.open(temp_file).convert("L")
        ratio = img.height / img.width
        new_h = int(width * ratio * 0.55)
        img = img.resize((width, new_h))
        chars = ["@", "#", "S", "%", "?", "*", "+", ";", ":", ",", "."]
        pixels = img.getdata()
        new_pixels = "".join([chars[p // 25] for p in pixels])
        ascii_image = "\n" + "\n".join([new_pixels[i:i+width] for i in range(0, len(new_pixels), width)]) + "\n"
        
        return ascii_image
        
    except Exception as e:
        return f"Fatal Error during find and convert process: {e}"
        
    finally:
        if os.path.exists(temp_file): os.remove(temp_file)

def convert_image_to_ascii(image_path, width=100):
    path = image_path.strip("'\"")
    if not os.path.exists(path): return "Error: Image file not found."
    try:
        img = Image.open(path).convert("L")
        ratio = img.height / img.width
        new_h = int(width * ratio * 0.55)
        img = img.resize((width, new_h))
        chars = ["@", "#", "S", "%", "?", "*", "+", ";", ":", ",", "."]
        pixels = img.getdata()
        new_pixels = "".join([chars[p // 25] for p in pixels])
        return "\n" + "\n".join([new_pixels[i:i+width] for i in range(0, len(new_pixels), width)]) + "\n"
    except Exception as e: return f"Error: {e}"

def generate_ascii_banner(text):
    try: return "\n" + pyfiglet.figlet_format(text) + "\n"
    except Exception as e: return f"Error: {e}"

def web_search(query, count=3):
    """
    Performs a web search using DDGS with a max_results parameter determined by 'count',
    and a global timeout of 15 seconds.
    """
    try:
        # DDGS allows specifying max_results directly and supports a timeout
        res = DDGS(timeout=15).text(query, max_results=count)
        
        results_list = res[:count] if res else []

        if not results_list:
            return "No search results found."

        # Format results for the AI
        formatted_output = "\n".join([f"- {r.get('title', 'N/A')}: {r.get('body', 'N/A')}" for r in results_list])
        return formatted_output
    except Exception as e:
        return f"Error during web search: {e}"

def get_system_stats():
    cpu = psutil.cpu_percent(interval=0.0) 
    ram = psutil.virtual_memory()
    return f"CPU: {cpu}% | RAM: {ram.percent}%"

def list_files(path="."):
    if not is_safe(path): return "Denied."
    try: 
        return ", ".join(os.listdir(path)[:50]) 
    except Exception as e: return f"Error: {e}"

def read_local_file(filename):
    if not is_safe(filename) or not os.path.exists(filename): return "Error: File not found or path denied."
    f = None
    try:
        f = open(filename, 'r', encoding='utf-8')
        return f.read()[:2000]
    except Exception as e: return f"Error reading file: {e}"
    finally:
        if f: f.close()

def create_folder(folder_name):
    if not is_safe(folder_name): return "Denied."
    try:
        os.makedirs(folder_name, exist_ok=True)
        return "Created."
    except Exception as e: return f"Error creating folder: {e}"

def save_to_file(filename, content):
    if not is_safe(filename): return "Denied."
    try:
        os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else ".", exist_ok=True)
        with open(filename, 'w', encoding='utf-8') as f: f.write(content)
        return "Saved."
    except Exception as e: return f"Error saving file: {e}"

def delete_file(filename):
    if not is_safe(filename): return "Denied."
    if not os.path.exists(filename): return "Error: File not found."
    
    if input(f"{CONFIG['color_sys']}Delete {filename}? (y/n) >> {CONFIG['color_reset']}") == 'y':
        try:
            os.remove(filename)
            return "Deleted."
        except Exception as e: return f"Error deleting file: {e}"
    return "Cancelled."

def run_python_code(code: str) -> str:
    """Runs Python code in a restricted scope."""
    restricted_scope = {'__builtins__': __builtins__}
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf): 
            exec(code, restricted_scope, restricted_scope)
        return f"Code Output:\n{buf.getvalue()}"
    except Exception as e: return f"Execution Error:\n{e}"

def get_weather(city):
    key = CONFIG['weather_api_key']
    try:
        geo_params = {"q": city.strip(), "limit": 1, "appid": key}
        geo = requests.get("https://api.openweathermap.org/geo/1.0/direct", params=geo_params, timeout=5).json()
        
        if not geo and "US" not in city.upper():
            geo_params["q"] = city.strip() + ", US"
            geo = requests.get("https://api.openweathermap.org/data/2.5/weather", params=weather_params, timeout=5).json()
        
        if not geo: return "Location not found."
        
        weather_params = {"lat": geo[0]['lat'], "lon": geo[0]['lon'], "units": "imperial", "appid": key}
        w = requests.get("https://api.openweathermap.org/data/2.5/weather", params=weather_params, timeout=5).json()
        
        return (f"Weather for {geo[0]['name']}: {w['weather'][0]['description'].title()}, "
                f"{w['main']['temp']}F, Humidity: {w['main']['humidity']}%.")
    except Exception as e: return f"API Error: {e}"

TOOLS = {
    'web_search': web_search, 'get_system_stats': get_system_stats,
    'list_files': list_files, 'read_local_file': read_local_file,
    'create_folder': create_folder, 'save_to_file': save_to_file,
    'delete_file': delete_file, 'run_python_code': run_python_code,
    'get_weather': get_weather, 
    'convert_image_to_ascii': convert_image_to_ascii,
    'generate_ascii_banner': generate_ascii_banner, 
    'find_and_convert_ascii': find_and_convert_ascii, 
    'store_user_info': store_user_info, 
    'store_conversation_note': store_conversation_note
}

# ==========================================
# [MAIN LOOP]
# ==========================================
# HELPER: Strips leading/trailing JSON from model response
def strip_leading_trailing_json(text):
    text = text.strip()
    
    json_pattern = r'^\s*\{.*\}\s*|\s*\{.*\}\s*$'
    
    # Aggressive pattern to remove tool call syntax leaks and extraneous tags
    leak_pattern = r'(\[|\{)\s*["\']?(get_weather|run_python_code|web_search)\([^\)]*\)["\']?\s*(\]|\})|(\[/\]|\[END OF RESPONSE\]|P\.S\..*|Unfortunately, as a text-based AI, I\'m unable to directly access or view web content\..*)$'
    
    # 1. First, remove known conversational leaks, including the specific tool call syntax and tags
    text = re.sub(leak_pattern, '', text, flags=re.IGNORECASE | re.DOTALL).strip()
    
    # 2. Then, remove any leading/trailing raw JSON objects
    while True:
        original_text = text
        match = re.search(json_pattern, text, re.DOTALL)
        if match:
            text = text[:match.start()] + text[match.end():]
            text = text.strip()
            if not text:
                return ""
        else:
            break
            
        if original_text == text:
            break
            
    return text

def extract_image_path(text):
    m = re.search(r'([a-zA-Z0-9_\-\.\/\\:]+\.(png|jpg|jpeg|bmp|webp))', text, re.IGNORECASE)
    return m.group(1).strip("'\"") if m and os.path.exists(m.group(1).strip("'\"")) else None

def run_agent():
    global MESSAGES
    
    # Define a custom exception for clean restarts
    class RestartSignal(Exception):
        pass

    try:
        init_memory()
        print_banner()
        
        user_facts, convo_facts = load_all_memories()
        system_content = build_system_prompt(user_facts, convo_facts)
        MESSAGES = [{'role': 'system', 'content': system_content}] 
        
        while True:
            try:
                u_input = input(f"\n{CONFIG['color_user']}{CONFIG['prompt_user']}{CONFIG['color_reset']}")
            except KeyboardInterrupt: 
                print("\n[++] TERMINATING SESSION.")
                break
            
            if u_input.strip().lower() == "/bye": 
                print("\n[++] TERMINATING SESSION.")
                break
            
            # 1. RESTART COMMAND CHECK
            if u_input.strip().lower() == "/rb":
                print(f"\n{CONFIG['color_sys']}>> RESTARTING PROGRAM... <<{CONFIG['color_reset']}")
                raise RestartSignal
                
            debug_mode = False
            if u_input.strip().lower().startswith("--t"):
                debug_mode = True
                u_input = u_input[3:].strip()
                print(f"\n{CONFIG['color_sys']}>>> DEBUG MODE: ON <<< {CONFIG['color_reset']}")

            msg = {'role': 'user', 'content': u_input}
            if (path := extract_image_path(u_input)):
                msg['images'] = [path]
                print(f"{CONFIG['color_sys']}[i] Image attached.{CONFIG['color_reset']}")
            MESSAGES.append(msg)

            # 5. Main loop for AI response and tool execution (max 5 iterations)
            for i in range(5): 
                
                # --- Ollama Chat Call (Blocking/Synchronous) ---
                # Helper function for the chat call (Blocking)
                def chat_blocking(messages, tools):
                    # This function is executed inside the loading bar thread wrapper
                    return ollama.chat(model=CONFIG['model'], messages=messages, tools=tools, stream=False)

                # Execute the chat call and wait for the synchronous result
                resp = loading_bar_start_stop(chat_blocking, MESSAGES, list(TOOLS.values()))
                
                content = resp.get('message', {}).get('content', '')
                resp_message = resp.get('message', {})
                
                # 5a. Unified Tool Parser
                calls = []
                
                # 1. Native JSON tool calls (check the full response object)
                if resp_message.get('tool_calls'):
                    for t in resp_message['tool_calls']:
                        calls.append({'name': t['function']['name'], 'args': t['function']['arguments']})
                
                # 2. Raw XML tool call parser (check the content)
                elif "<tool_call>" in content:
                    match = re.search(r'<tool_call>(.*?)</tool_call>', content, re.DOTALL)
                    if match:
                        try:
                            data = json.loads(match.group(1).strip())
                            calls = data if isinstance(data, list) else [data]
                        except: pass

                # NEW DIAGNOSTIC STEP: Show raw output if debug is on and no tool call was found
                if debug_mode and not calls and content:
                     print(f"{CONFIG['color_sys']}╔{'═'*70}╗")
                     print(f"║ [DEBUG] RAW OLLAMA CONTENT (No Tool Call Found):")
                     print(f"║ {content.replace('\n', ' ').strip()}") 
                     print(f"╚{'═'*70}╝{CONFIG['color_reset']}", end="", flush=True)


                # 5b. CONCURRENT EXECUTION OF TOOLS
                executed_a_tool = False
                if calls:
                    # The message stored in history must contain the tool calls
                    MESSAGES.append({'role': 'assistant', 'content': content, 'tool_calls': resp_message.get('tool_calls')})
                    
                    future_to_call = {
                        executor.submit(execute_tool_task, c.get('name'), c.get('args', {}), debug_mode): c 
                        for c in calls if c.get('name') in TOOLS
                    }
                    
                    tool_results = []
                    # Wrap the concurrent wait process in the loading bar
                    def wait_for_tools():
                        for future in concurrent.futures.as_completed(future_to_call):
                            nonlocal executed_a_tool
                            try:
                                tool_msg = future.result()
                                tool_results.append(tool_msg)
                                executed_a_tool = True
                            except Exception as exc:
                                print(f"{CONFIG['color_sys']}!! EXCEPTION DURING TOOL EXECUTION: {exc}{CONFIG['color_reset']}")

                    loading_bar_start_stop(wait_for_tools)
                        
                    MESSAGES.extend(tool_results)

                    if executed_a_tool: 
                        continue # Loop back to get AI's next thought/answer

                # 5c. Final Answer (Only runs if no tools were executed, or all tool executions failed)
                
                # 1. Filter out the JSON leak
                final_content = strip_leading_trailing_json(content)
                
                # 2. Check for clean output
                if final_content and '<tool_call>' not in final_content:
                    # Print the final output since streaming is disabled
                    print(f"\n{CONFIG['color_ai']}{CONFIG['prompt_ai']}{final_content}{CONFIG['color_reset']}")
                    MESSAGES.append({'role': 'assistant', 'content': content}) 
                    break
                
                # 3. Last resort warning
                if i == 4 and u_input.strip():
                    print(f"{CONFIG['color_sys']}>> Warning: AI failed to generate a clean answer after multiple attempts. Skipping to next prompt. <<{CONFIG['color_reset']}")

    except RestartSignal:
        global executor
        executor.shutdown(wait=False)
        executor = concurrent.futures.ThreadPoolExecutor() 
        run_agent()

if __name__ == "__main__":
    try:
        run_agent()
    except Exception as e:
        # Final shutdown attempt only if the executor is still valid
        if executor:
            executor.shutdown(wait=False)
        # Re-raise error if it's not the benign shutdown error
        if "shutdown" not in str(e) and "NoneType" not in str(e):
             print(f"\n[!!] CRITICAL EXIT ERROR: {e}")
