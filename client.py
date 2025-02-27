import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox
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

# 设置默认主题
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class ChatClient:
    def __init__(self, root):
        self.root = root
        self.username = None
        self.websocket = None
        self.loop = None
        self.is_receiving_history = False
        self.last_sent_message = None
        
        # CTk颜色主题
        self.colors = {
            'primary': ["#3B8ED0", "#1F6AA5"],
            'success': ["#2FA572", "#2A8C61"],
            'warning': ["#E65100", "#CC4700"],
            'text': ["#DCE4EE", "#DCE4EE"],
            'entry': ["#343638", "#1D1E1E"]
        }
        
        if TrustUserMode:
            self.username = os.getlogin() # 获取用户名
            self.create_chat_window() # 创建聊天窗口
            threading.Thread(target=self.run_event_loop).start() # 启动事件循环
        else:
            self.create_login_window()  # 创建登录窗口

    def create_login_window(self):
        self.login_window = ctk.CTkToplevel(self.root)
        self.login_window.title("登录")
        self.login_window.geometry("400x300")

        # 创建Frame
        login_frame = ctk.CTkFrame(self.login_window)
        login_frame.pack(expand=True, padx=20, pady=20)

        # 标题
        title_label = ctk.CTkLabel(
            login_frame,
            text="DLChatting",
            font=("Helvetica", 24, "bold")
        )
        title_label.pack(pady=20)

        # 用户名输入框
        username_frame = ctk.CTkFrame(login_frame)
        username_frame.pack(fill=tk.X, pady=10)
        
        ctk.CTkLabel(
            username_frame,
            text="用户名"
        ).pack(anchor=tk.W)
        
        self.username_entry = ctk.CTkEntry(
            username_frame,
            width=250,
            placeholder_text="请输入用户名"
        )
        self.username_entry.pack(fill=tk.X, pady=5)

        # 登录按钮
        login_button = ctk.CTkButton(
            login_frame,
            text="登录",
            command=lambda: self.on_login(),
            width=200
        )
        login_button.pack(pady=20)
        
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
        self.root.geometry("800x600")

        # 主容器
        main_container = ctk.CTkFrame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # 聊天显示区域
        self.chat_text = ctk.CTkTextbox(
            main_container,
            wrap=tk.WORD,
            height=400
        )
        self.chat_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # 配置标签样式
        self.chat_text.tag_config("green", foreground=self.colors['success'][0])
        self.chat_text.tag_config("orange", foreground=self.colors['warning'][0])

        # 底部输入区域
        input_container = ctk.CTkFrame(main_container)
        input_container.pack(fill=tk.X, pady=(10, 0))

        # 消息输入框
        self.message_entry = ctk.CTkTextbox(
            input_container,
            height=80,
            wrap=tk.WORD
        )
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 发送按钮
        send_button = ctk.CTkButton(
            input_container,
            text="发送",
            command=lambda: self.on_send_message(None),
            width=100
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
        # 使用try-finally确保文本操作完成
        try:
            # ScrolledText没有state属性，直接insert即可
            if color:
                self.chat_text.insert(tk.END, message + "\n", (color,))
            else:
                self.chat_text.insert(tk.END, message + "\n")
            
            self.chat_text.see(tk.END)  # 滚动到末尾

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
                
        except Exception as e:
            print(f"插入消息时出错: {e}")

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
        reconnect_message = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [√] 系统: 掉线了，是否重新连接？"
        self.insert_message(reconnect_message, "orange", notify=False)
        
        def ask_reconnect():
            answer = messagebox.askquestion(
                title="连接错误",
                message="掉线了，是否重新连接？"
            )
            if answer == "yes":
                try:
                    self.chat_text.delete('1.0', tk.END)
                    threading.Thread(target=self.run_event_loop).start()
                except Exception as e:
                    print(f"重连时出错: {e}")
            else:
                self.root.quit()
        
        self.root.after(0, ask_reconnect)

if __name__ == "__main__":
    root = ctk.CTk()
    app = ChatClient(root)
    root.mainloop()