import tkinter as tk
from tkinter import scrolledtext, messagebox
import asyncio
import websockets
import threading
import time
import os
import re
from datetime import datetime
from plyer import notification

NotifyOnMessage = True  # 默认开启消息通知
TrustUserMode = False  # 不要开启这个，自用

class ChatClient:
    def __init__(self, root):
        self.root = root # 窗口
        self.username = None # 用户名
        self.websocket = None # websocket
        self.loop = None # 事件循环
        self.is_receiving_history = False # 是否正在接收历史消息
        self.last_sent_message = None  # 用于存储最后发送的消息
        
        # 添加颜色主题
        self.colors = {
            'bg': '#f0f0f0',
            'chat_bg': '#ffffff',
            'entry_bg': '#ffffff',
            'button_bg': '#4CAF50',
            'button_fg': 'white',
            'text_fg': '#333333'
        }
        self.root.configure(bg=self.colors['bg'])

        if TrustUserMode:
            self.username = os.getlogin() # 获取用户名
            self.create_chat_window() # 创建聊天窗口
            threading.Thread(target=self.run_event_loop).start() # 启动事件循环
        else:
            self.create_login_window()  # 创建登录窗口

    def create_login_window(self):
        self.login_window = tk.Toplevel(self.root) # 创建登录窗口
        self.login_window.title("登录") # 设置窗口标题
        self.login_window.geometry("300x200") # 设置窗口大小
        self.login_window.configure(bg=self.colors['bg'])

        # 创建Frame来容纳登录组件
        login_frame = tk.Frame(self.login_window, bg=self.colors['bg'])
        login_frame.place(relx=0.5, rely=0.5, anchor='center')
        
        title_label = tk.Label(login_frame, text="DLChatting", 
                             font=('Arial', 16, 'bold'),
                             bg=self.colors['bg'],
                             fg=self.colors['text_fg'])
        title_label.pack(pady=10)
        
        tk.Label(login_frame, text="请输入用户名:",
                bg=self.colors['bg'],
                fg=self.colors['text_fg']).pack(pady=5)
        
        self.username_entry = tk.Entry(login_frame, width=25,
                                     font=('Arial', 10),
                                     bg=self.colors['entry_bg'])
        self.username_entry.pack(pady=5)
        
        login_button = tk.Button(login_frame, text="登录",
                               command=lambda: self.on_login(),
                               bg=self.colors['button_bg'],
                               fg=self.colors['button_fg'],
                               width=10)
        login_button.pack(pady=10)
        self.username_entry.bind("<Return>", self.on_login)

    def on_login(self, event=None):
        self.username = self.username_entry.get() # 获取输入的用户名
        if self.username:
            # 用户名是否符合要求
            if not re.match(r'^[a-zA-Z0-9_]{3,20}$', self.username): 
                messagebox.showerror("用户名错误", "用户名只能包含26字母、数字及下划线（_），且长度必须为3~20") # 弹窗提示
                return
            self.login_window.destroy() # 销毁登录窗口
            self.create_chat_window() # 创建聊天窗口
            threading.Thread(target=self.run_event_loop).start() # 启动事件循环

    def create_chat_window(self):
        self.root.title(f"DLChatting - {self.username}")
        self.root.geometry("600x800")
        self.root.configure(bg=self.colors['bg'])

        # 创建主Frame
        main_frame = tk.Frame(self.root, bg=self.colors['bg'])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # 聊天显示区域
        self.chat_text = scrolledtext.ScrolledText(
            main_frame,
            state='disabled',
            font=('Arial', 10),
            bg=self.colors['chat_bg'],
            fg=self.colors['text_fg']
        )
        self.chat_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # 配置标签样式
        self.chat_text.tag_configure("green", foreground="#2E7D32")
        self.chat_text.tag_configure("orange", foreground="#ED6C02")

        # 创建输入区域frame
        input_frame = tk.Frame(main_frame, bg=self.colors['bg'])
        input_frame.pack(fill=tk.X, pady=(0, 10))

        # 消息输入框
        self.message_entry = tk.Text(
            input_frame,
            height=3,
            font=('Arial', 10),
            bg=self.colors['entry_bg'],
            fg=self.colors['text_fg']
        )
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 发送按钮
        send_button = tk.Button(
            input_frame,
            text="发送",
            command=lambda: self.on_send_message(None),
            bg=self.colors['button_bg'],
            fg=self.colors['button_fg'],
            width=10
        )
        send_button.pack(side=tk.RIGHT, padx=(10, 0))

        # 绑定事件
        self.message_entry.bind("<Return>", self.on_send_message)
        self.message_entry.bind("<Shift-Return>", self.on_newline)

    def on_send_message(self, event):
        message = self.message_entry.get("1.0", tk.END).strip() # 获取文本框内容
        if message:
            asyncio.run_coroutine_threadsafe(self.send_message(message), self.loop) # 发送消息
            self.message_entry.delete("1.0", tk.END) # 清空文本框
        return "break"

    def on_newline(self, event):
        self.message_entry.insert(tk.INSERT, "\n") # 插入换行
        return "break" # 返回

    async def send_message(self, message):  # 发送消息
        self.last_sent_message = message  # 记录最后发送的消息
        await self.websocket.send(message) # 发送消息

    def insert_message(self, message, color=None, notify=True):  # 插入消息
        self.chat_text.config(state='normal')  # 设置文本框为可编辑状态
        if color:
            self.chat_text.insert(tk.END, message + "\n", color)  # 在文本框末尾插入消息
        else:
            self.chat_text.insert(tk.END, message + "\n")  # 在文本框末尾插入消息
        self.chat_text.config(state='disabled')  # 设置文本框为不可编辑状态
        self.chat_text.yview(tk.END)  # 滚动到文本框末尾

        # 判断是否为自己发送的消息
        is_own_message = False 
        if self.last_sent_message: 
            # 提取消息内容（去除时间戳和用户名）
            message_content = re.search(r'\] .*?: (.+)$', message) 
            if message_content:
                message_content = message_content.group(1) # 提取消息内容
                is_own_message = message_content == self.last_sent_message

        # 历史记录不弹窗，自己发的消息不弹窗，且不弹窗消息为“---以上是历史记录---”
        if NotifyOnMessage and notify and not self.is_receiving_history and not is_own_message and message != "---以上是历史记录---":
            self.show_notification(message)

        # 重置最后发送的消息
        if is_own_message:
            self.last_sent_message = None

    def show_notification(self, message):
        notification.notify(
            title="新消息",
            message=message,
            timeout=2
        )

    async def receive_messages(self):
        try:
            self.is_receiving_history = True
            async for message in self.websocket:
                color = None
                if message.startswith("\033[32m") and message.endswith("\033[0m"):
                    message = message[5:-4]
                    color = "green"
                elif message.startswith("\033[33m") and message.endswith("\033[0m"):
                    message = message[5:-4]
                    color = "orange"
                
                # 检查是否是历史记录的结束标志
                if "---以上是历史记录---" in message:
                    self.is_receiving_history = False

                notify = not self.is_receiving_history # 是否需要弹窗
                self.insert_message(message, color, notify) # 插入消息
        except websockets.ConnectionClosed:
            self.handle_disconnection() # 处理断开连接

    async def connect(self):
        uri = f"ws://localhost:8765/{self.username}" # WebSocket URI
        self.websocket = await websockets.connect(uri) # 连接服务器
        await self.receive_messages()

    def run_event_loop(self):
        self.loop = asyncio.new_event_loop() # 创建事件循环
        asyncio.set_event_loop(self.loop) # 设置事件循环
        self.loop.run_until_complete(self.connect()) # 运行事件循环

    def handle_disconnection(self):
        reconnect_message = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [√] 系统: 掉线了，是否重新连接？（y/n）"
        self.insert_message(reconnect_message, "orange", notify=False)
        
        def ask_reconnect():
            answer = messagebox.askquestion("连接错误", "掉线了，是否重新连接？")
            if answer == 'yes':
                self.chat_text.config(state='normal')
                self.chat_text.delete(1.0, tk.END)
                self.chat_text.config(state='disabled')
                threading.Thread(target=self.run_event_loop).start()
            else:
                self.root.quit()
        
        self.root.after(0, ask_reconnect)

if __name__ == "__main__":
    root = tk.Tk()
    app = ChatClient(root)
    root.mainloop()