import tkinter as tk
from tkinter import ttk
from .stardict import open_dict, convert_dict
from dataclasses import dataclass
from ctypes import wintypes
from typing import Tuple
import urllib.request
import subprocess
import threading
import traceback
import ctypes
import os
import io
import re

ECDICT_URL = 'https://gitee.com/hupo510/note-serial/releases/download/ecdict.7z/ecdict.7z'
STARDICT_URL = 'https://gitee.com/hupo510/note-serial/releases/download/stardict.7z/stardict.7z'


@dataclass
class EcDictInfo:
    '英汉词典信息'
    url: str
    name: str
    ecdict = None

    @property
    def zip_name(self):
        return f'{self.name}.7z'

    @property
    def csv_name(self):
        return f'{self.name}.csv'

    @property
    def db_name(self):
        return f'{self.name}.db'


ecdict_infos = (  # 词典信息列表
    EcDictInfo(url=ECDICT_URL, name='ecdict'),
    EcDictInfo(url=STARDICT_URL, name='stardict'),
)

SC_MOVE = 0xF010
HTCAPTION = 2
GWL_EXSTYLE = (-20)
WM_SYSCOMMAND = 0x0112
LWA_COLORKEY = 0x00000001
WS_EX_LAYERED = 0x00080000

user32 = ctypes.windll.LoadLibrary('user32')
PostMessage = user32.PostMessageW
PostMessage.argtypes = [wintypes.HWND,
                        wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
PostMessage.restype = wintypes.BOOL
ReleaseCapture = user32.ReleaseCapture
ReleaseCapture.argtypes = []
ReleaseCapture.restype = wintypes.BOOL
GetParent = user32.GetParent
GetParent.argtypes = [wintypes.HWND]
GetParent.restype = wintypes.HWND
SetWindowLongPtr = user32.SetWindowLongPtrW
SetWindowLongPtr.argtypes = [wintypes.HWND, wintypes.INT, wintypes.LPVOID]
SetWindowLongPtr.restype = wintypes.LPVOID
GetWindowLongPtr = user32.GetWindowLongPtrW
GetWindowLongPtr.argtypes = [wintypes.HWND, wintypes.INT]
GetWindowLongPtr.restype = wintypes.DWORD
SetLayeredWindowAttributes = user32.SetLayeredWindowAttributes
SetLayeredWindowAttributes.argtypes = [
    wintypes.HWND, wintypes.COLORREF, wintypes.BYTE, wintypes.DWORD]
SetLayeredWindowAttributes.restype = wintypes.BOOL


class LoaderApp(tk.Tk):
    '加载界面'

    def __init__(self, cwd: str, infos: Tuple[EcDictInfo]):
        super().__init__()
        self.cwd = cwd  # 工作目录
        self.infos = infos
        self.create_layout()
        self.create_worker()

    def create_layout(self):
        '创建布局'
        self.resizable(False, False)
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        bg = tk.Frame(self, background='#366cb3')
        bg.pack(side=tk.TOP, fill=tk.BOTH, padx=0, pady=0, anchor=tk.CENTER)
        frame = tk.Frame(bg)
        frame.pack(side=tk.TOP, fill=tk.BOTH, padx=1, pady=1, anchor=tk.CENTER)
        title = tk.Label(frame, text='ECDICT词典下载安装器')
        title.pack(side=tk.TOP, fill=tk.X)
        title.bind("<ButtonPress-1>", self.on_move)
        ttk.Separator(frame).pack(side=tk.TOP, fill=tk.X)
        fix = tk.Frame(frame)
        fix.pack(side=tk.TOP, fill=tk.X, padx=3, pady=3)
        fix.grid_columnconfigure(1, weight=1)
        self.progress_vars = list()
        self.tip_vars = list()
        self.tip_labels = dict()
        for i in range(len(self.infos)):
            info = self.infos[i]
            tk.Label(fix, text=info.name).grid(
                row=i, column=0, padx=1, pady=1, sticky=tk.NSEW)
            double_var = tk.DoubleVar(value=0)
            self.progress_vars.append(double_var)
            pbar = ttk.Progressbar(
                fix, variable=double_var, maximum=100, length=200)
            pbar.grid(row=i, column=1, padx=1, pady=1, sticky=tk.NSEW)
            pbar.bind("<Configure>", self.update_pos)
            tip_var = tk.StringVar(value='')
            self.tip_vars.append(tip_var)
            self.tip_labels[pbar._name] = tk.Label(
                fix, textvariable=tip_var, bg='#fff', font=('', 9))
        cbtn = tk.Button(
            self, text='X', relief=tk.FLAT, borderwidth=2, bg='red',
            highlightthickness=1, activebackground="#f44", fg='white')
        cbtn.bind('<ButtonRelease-1>', self.on_cancel)
        self.update_idletasks()  # 确保窗口尺寸已计算
        width = self.winfo_width()
        cbtn.place(x=width-4, y=4, width=16, height=16, anchor=tk.NE)
        px, py = self.winfo_pointerxy()
        x, y = px - width // 2, py - 8  # 鼠标落在标题栏上
        self.geometry(f'+{x}+{y}')

    def create_worker(self):
        '创建工作'
        self.threads = list()
        self.cancel = threading.Event()
        self.cancel.clear()
        for i in range(len(self.infos)):
            info = self.infos[i]
            thread = threading.Thread(
                target=self.task_handle, args=(
                    info, self.progress_vars[i], self.tip_vars[i]), daemon=True)
            self.threads.append(thread)
            thread.start()

    def task_handle(self, info: EcDictInfo, pvar: tk.Variable, tvar: tk.Variable):
        '任务处理'
        try:
            zip_path = os.path.join(self.cwd, info.zip_name)
            if not os.path.exists(zip_path):
                pvar.set(0)
                tvar.set('下载文件中...')
                if not self.download_file(info.url, zip_path, pvar):
                    tvar.set('文件下载异常')
                    if os.path.exists(zip_path):
                        os.remove(zip_path)
                    return
            if self.cancel.is_set():  # 检查是否手动退出
                return
            csv_path = os.path.join(self.cwd, info.csv_name)
            if not os.path.exists(csv_path):
                pvar.set(0)
                tvar.set('解压文件中...')
                if not execute_7zdec(zip_path, self.cwd):
                    tvar.set('文件解压失败')
                    return
            if self.cancel.is_set():  # 检查是否手动退出
                return
            db_path = os.path.join(self.cwd, info.db_name)
            if not os.path.exists(db_path):
                pvar.set(0)
                tvar.set('构建数据库中...')
                if not convert_dict(db_path, csv_path, var=pvar, cancel=self.cancel):  # 转换词典
                    tvar.set('构建数据库失败')
                    if os.path.exists(db_path):
                        os.remove(db_path)
                    return
            if self.cancel.is_set():  # 检查是否手动退出
                return
            pvar.set(100)
            tvar.set('词典已就绪')
        finally:
            self.after(100, self.check_done)  # 稍后进行检查

    def download_file(self, url: str, path: str, var: tk.Variable):
        '下载文件'
        try:
            req = urllib.request.Request(url)
            response = urllib.request.urlopen(req)
            total_size = int(response.headers.get('Content-Length', 0))
            with open(path, 'wb') as f:
                downloaded = 0
                block_size = 8192  # 每次读取8KB
                while True:
                    buffer = response.read(block_size)
                    if not buffer:
                        return True
                    if self.cancel.is_set():
                        return False
                    f.write(buffer)
                    downloaded += len(buffer)
                    percent = min(100, (downloaded / total_size) * 100)
                    var.set(percent)
        except:
            return False

    def check_done(self):
        '检查全部完成'
        if any([th.is_alive() for th in self.threads]):  # 仍存在任务在运行
            return
        self.destroy()  # 销毁结束窗口

    def on_move(self, event=None):
        '移动'
        ReleaseCapture()
        hwnd = GetParent(self.winfo_id())
        PostMessage(hwnd, WM_SYSCOMMAND, SC_MOVE | HTCAPTION, 0)

    def on_cancel(self, event=None):
        '取消'
        self.cancel.set()

    def update_pos(self, event=None):
        '更新位置'
        pbar: tk.Widget = event.widget
        name = pbar._name
        label: tk.Widget = self.tip_labels.get(name)
        if label is None:
            return
        padding = 3
        x, y = pbar.winfo_x()+padding, pbar.winfo_y()+padding
        w, h = pbar.winfo_width() - 2*padding, pbar.winfo_height() - 2*padding
        label.place(x=x, y=y, width=w, height=h)
        hwnd = label.winfo_id()
        ex_style = GetWindowLongPtr(hwnd, GWL_EXSTYLE)
        SetWindowLongPtr(hwnd, GWL_EXSTYLE,  ex_style | WS_EX_LAYERED)
        SetLayeredWindowAttributes(hwnd, 0xFFFFFF, 0, LWA_COLORKEY)  # 设备背景为透明色


def execute_7zdec(file: str, cwd: str = None):
    '调用解压文件'
    commands = [f'{os.getcwd()}\\7zdec.exe', 'x', os.path.abspath(file)]
    ret_code = subprocess.call(commands, cwd=os.path.abspath(cwd))
    return ret_code == 0


def script_path():
    '获取脚本目录'
    try:
        import lua
        return lua.eval("package.spath")
    except:
        return os.path.dirname(__file__)


def split_string(text):
    '分割字符串，包括驼峰命名的分割'
    parts = re.split(r'[^a-zA-Z0-9]', text)  # 分割字符串
    pattern1 = re.compile(r'(.)([A-Z][a-z]+)')  # 插入空格在大小写字母之间
    pattern2 = re.compile(r'([a-z0-9])([A-Z])')  # 插入空格在大写字母之间（避免拆分缩写）
    words = list()
    for part in parts:
        if part:
            s1 = re.sub(pattern1, r'\1 \2', part)
            s2 = re.sub(pattern2, r'\1 \2', s1)
            ws = s2.split()  # 按空格分割
            if len(ws) > 1:
                words.append(part)  # 先追加一个原驼峰命名的词组
            words.extend(ws)
    return words


def ecdict_translate(text):
    '英汉词典翻译'
    if any([x.ecdict is None for x in ecdict_infos]):
        mpath = os.path.join(script_path(), __name__.split('.')[0])
        cwd = os.path.abspath(mpath)
        if not all([os.path.exists(os.path.join(cwd, info.db_name)) for info in ecdict_infos]):
            try:  # 尝试构建数据库
                app = LoaderApp(cwd, ecdict_infos)
                app.mainloop()
            except:
                app.destroy()
                return traceback.format_exc()
        for info in ecdict_infos:  # 逐一打开词典
            if info.ecdict is None:
                db_path = os.path.join(cwd, info.db_name)
                if os.path.exists(db_path):
                    info.ecdict = open_dict(db_path)
    result = io.StringIO()
    words = split_string(text)
    result.write('分词：')
    result.write(' '.join(words))
    if any([info.ecdict is None for info in ecdict_infos]):  # 检查词典的完整性
        names = list()
        for info in ecdict_infos:
            if info.ecdict is None:
                names.append(info.name)
        names_str = ','.join(names)
        result.write(f'\n !<{names_str}>词典缺失')
    for word in words:  # 逐个单词进行查找
        for info in ecdict_infos:
            if info.ecdict is None:
                continue
            res: list = info.ecdict.query(word)
            if res is None:
                continue
            result.write(f"\n# {res['word']}")
            tl = res['translation'].split('\n')
            for t in tl:
                result.write(f'\n  * {t}')
            break  # 查到符合结果则不查询下一个词典
    return result.getvalue()
