import webbrowser
import threading
import time
import uvicorn
import sys
import os

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def open_browser():
    time.sleep(1.5)
    print("Atidaroma vartotojo sąsaja naršyklėje: http://localhost:8000")
    webbrowser.open("http://localhost:8000")

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 Barbora Pirkinių Krepšelio AI Asistentas")
    print("Sistema paleidžiama adresu: http://localhost:8000")
    print("Dokumentacija AI agentams: http://localhost:8000/docs")
    print("=" * 60)
    
    # Naršyklės atidarymas fone
    threading.Thread(target=open_browser, daemon=True).start()
    
    # FastAPI serverio paleidimas
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False, log_level="info")
