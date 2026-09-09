"""Two lightweight native windows, with blocking work kept off Tk's main thread."""
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from .core import Hub, prepare, device_id, dictionary_candidates


def launch(role, home):
    root = tk.Tk()
    root.title('SMT2 준비·관리' if role == 'prep' else 'SMT2 AI 허브')
    root.geometry('920x680')
    panel = ttk.Frame(root, padding=16)
    panel.pack(fill='both', expand=True)
    events = queue.Queue()
    status = tk.StringVar(value='준비됨')
    busy = False

    def work(task, done):
        nonlocal busy
        if busy:
            messagebox.showinfo('작업 중', '현재 작업이 끝난 후 다시 시도하세요.')
            return
        busy = True
        status.set('처리 중…')
        def worker():
            try:
                events.put((done, task(), None))
            except Exception as exc:
                events.put((done, None, str(exc)))
        threading.Thread(target=worker, daemon=False).start()

    def poll():
        nonlocal busy
        try:
            done, value, error = events.get_nowait()
        except queue.Empty:
            pass
        else:
            busy = False
            if error:
                status.set('실패: ' + error)
                messagebox.showerror('처리 실패', error)
            else:
                status.set('완료')
                done(value)
        root.after(150, poll)

    def close():
        if busy:
            messagebox.showinfo('작업 중', '입력·결과 보존을 위해 작업 완료 후 닫아 주세요.')
        else:
            root.destroy()

    def entry(label, initial='', chooser=None):
        row = ttk.Frame(panel)
        row.pack(fill='x', pady=4)
        ttk.Label(row, text=label, width=16).pack(side='left')
        value = tk.StringVar(value=initial)
        ttk.Entry(row, textvariable=value).pack(side='left', fill='x', expand=True)
        if chooser:
            def select():
                chosen = chooser()
                if chosen:
                    value.set(chosen)
            ttk.Button(row, text='선택', command=select).pack(side='right')
        return value

    exchange = entry('교환 폴더', str(home / 'exchange'), filedialog.askdirectory)
    ttk.Label(panel, text='NAS 설정 전에는 일반 로컬 폴더를 사용합니다. 두 앱에서 같은 교환 폴더를 선택하세요.').pack(anchor='w')
    if role == 'prep':
        ttk.Label(panel, text='강의 수집이 끝난 오디오를 등록합니다. 이 앱은 AI를 호출하지 않습니다.').pack(anchor='w', pady=8)
        audio = entry('오디오', chooser=lambda: filedialog.askopenfilename(filetypes=[('오디오', '*.mp3 *.wav *.m4a')]))
        title = entry('강의 제목')
        ttk.Label(panel, text='사용자 사전 힌트 (이 작업에 고정 / MLX 미리보기 최대 2000자)').pack(anchor='w')
        dictionary = tk.Text(panel, height=12, wrap='word')
        dictionary.pack(fill='both', expand=True)
        row = ttk.Frame(panel)
        row.pack(fill='x', pady=8)
        def extract():
            path = filedialog.askopenfilename(filetypes=[('자료', '*.txt *.md *.pdf')])
            if path:
                def display(value):
                    dictionary.delete('1.0', 'end')
                    dictionary.insert('1.0', value)
                work(lambda: dictionary_candidates(Path(path)), display)
        ttk.Button(row, text='자료에서 용어 후보 추출', command=extract).pack(side='left')
        def submit():
            values = (Path(audio.get()), Path(exchange.get()) / 'outbox', device_id(home), title.get(), dictionary.get('1.0', 'end-1c'))
            if len(values[-1]) > 2000:
                messagebox.showerror('사전 길이', '현재 전사 미리보기는 사전 힌트 2000자 이내를 지원합니다.')
                return
            work(lambda: prepare(*values), lambda result: messagebox.showinfo('전달 준비 완료',
                f'{result}\n\n아직 맥 인수 완료가 아닙니다. 인수 확인 후 미니를 종료하세요.'))
        ttk.Button(row, text='전달 준비', command=submit).pack(side='right')
        def check_receipts():
            folder = Path(exchange.get()) / 'receipts' / device_id(home)
            work(lambda: receipts_data(folder), show_receipts)
        ttk.Button(panel, text='맥 인수·처리 상태 확인', command=check_receipts).pack(anchor='w')
        def receipts_data(folder):
            from .core import read_json
            return [read_json(path) for path in sorted(folder.glob('*/status.json'))] if folder.exists() else []
        # Read the StringVar on the UI thread before starting any worker.
        def show_receipts(items):
            messagebox.showinfo('인수·처리 상태', '\n'.join(f"{d['request_id']} : {d['state']}" for d in items) or '인수 확인이 아직 없습니다.')
    else:
        hub = Hub(home / 'hub')
        model = entry('맥 전사 모델', 'mlx-community/whisper-turbo')
        ttk.Label(panel, text='첫 전사 시 모델 다운로드가 발생할 수 있습니다. Apple Silicon·MLX Whisper·FFmpeg가 필요합니다.').pack(anchor='w', pady=8)
        table = ttk.Treeview(panel, columns=('title', 'state', 'attempt'), show='headings', selectmode='browse')
        for name, label in [('title', '강의'), ('state', '상태'), ('attempt', '시도')]:
            table.heading(name, text=label)
        table.pack(fill='both', expand=True)
        def refresh(_=None):
            table.delete(*table.get_children())
            for job in hub.jobs():
                table.insert('', 'end', iid=job['id'], values=(job['title'], job['state'], job['attempt']))
        row = ttk.Frame(panel)
        row.pack(fill='x', pady=8)
        def ingest():
            folder, chosen_model = Path(exchange.get()), model.get().strip()
            if not chosen_model:
                messagebox.showerror('모델', '모델을 지정하세요.')
                return
            def task():
                for path in sorted((folder / 'outbox').glob('*/*/request.json')):
                    if not path.parent.name.startswith('.'):
                        hub.ingest(path.parent, chosen_model)
                hub.export(folder)
            work(task, refresh)
        def run():
            folder = Path(exchange.get())
            def task():
                try:
                    hub.run_one()
                finally:
                    hub.export(folder)
            work(task, refresh)
        def change(action):
            chosen = table.selection()
            folder = Path(exchange.get())
            if chosen:
                def task():
                    hub.change(chosen[0], action)
                    hub.export(folder)
                work(task, refresh)
        ttk.Button(row, text='준비된 작업 인수', command=ingest).pack(side='left')
        ttk.Button(row, text='다음 1건 전사', command=run).pack(side='left')
        ttk.Button(row, text='선택 작업 재시도', command=lambda: change('retry')).pack(side='left')
        ttk.Button(row, text='대기 작업 취소', command=lambda: change('cancel')).pack(side='left')
        ttk.Button(row, text='새로고침', command=refresh).pack(side='right')
        ttk.Label(panel, text=f'맥 로컬 작업·결과: {hub.home}\n진행 중 취소·자동 감시·전역 사전 병합은 다음 개발 단계입니다.').pack(anchor='w')
        refresh()
    def view_result():
        filename = filedialog.askopenfilename(title='완료 결과의 raw.txt 선택', filetypes=[('전사 결과', 'raw.txt')])
        if not filename:
            return
        from .core import read_json, digest
        path = Path(filename)
        def read():
            marker = read_json(path.parent / 'complete.json')
            if path.name != 'raw.txt' or digest(path) != marker['raw_txt_sha256']:
                raise ValueError('완료 결과 해시가 일치하지 않습니다.')
            return path.read_text(encoding='utf-8')
        def show(text):
            window = tk.Toplevel(root)
            window.title('전사 원본 — ' + str(path))
            window.geometry('800x550')
            content = tk.Text(window, wrap='word')
            content.pack(fill='both', expand=True)
            content.insert('1.0', text)
            content.configure(state='disabled')
        work(read, show)
    ttk.Button(panel, text='완료 전사 결과 열기', command=view_result).pack(anchor='w', pady=4)
    ttk.Label(panel, textvariable=status, wraplength=860).pack(anchor='w', pady=8)
    root.protocol('WM_DELETE_WINDOW', close)
    root.after(150, poll)
    root.mainloop()
