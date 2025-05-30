import time
import subprocess
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

WATCHED_EXTENSIONS = ['.py', '.js', '.ts', '.json', '.env', '.sh', '.txt', '.md']
CHECK_INTERVAL = 30  # секунд
HAS_CHANGES = False

class AutoGitHandler(FileSystemEventHandler):
    def on_any_event(self, event):
        global HAS_CHANGES
        # Только если файл отслеживаемого расширения И не внутри .git/
        if (not event.is_directory and 
            Path(event.src_path).suffix in WATCHED_EXTENSIONS and 
            '.git' not in event.src_path):
            HAS_CHANGES = True
            print(f"🟡 Изменено: {event.src_path}")

def has_real_changes():
    # Проверяем реальные незакоммиченные изменения
    result = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
    return bool(result.stdout.strip())

def run_git_commit():
    try:
        if has_real_changes():
            subprocess.call(['git', 'add', '--all'])
            result = subprocess.run(['git', 'commit', '-m', 'Auto-commit every 30s'], capture_output=True, text=True)
            if result.returncode == 0:
                subprocess.call(['git', 'push'])
                print("✅ Изменения закоммичены и запушены")
            else:
                print("ℹ️ Нет новых изменений для коммита")
        else:
            print("ℹ️ Нет изменений для коммита (git status чистый)")
    except Exception as e:
        print(f"❌ Ошибка при коммите/пуше: {e}")

if __name__ == "__main__":
    print("🟢 Старт слежения. Каждые 30 секунд — коммит и пуш, если были изменения.")
    observer = Observer()
    event_handler = AutoGitHandler()
    observer.schedule(event_handler, path='.', recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(CHECK_INTERVAL)
            if HAS_CHANGES:
                run_git_commit()
                # Не нужен global в главном цикле!
                HAS_CHANGES = False
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
