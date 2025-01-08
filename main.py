import pyautogui
import requests
import openai
import os
from PIL import Image
import tkinter as tk
from tkinter import messagebox, filedialog
import base64
import json
import pytesseract
import configparser
import sys

# 配置文件路径
CONFIG_FILE = 'config.ini'


def load_config():
    """加载配置文件，如果不存在则创建默认配置"""
    config = configparser.ConfigParser()

    if not os.path.exists(CONFIG_FILE):
        config['API'] = {
            'openai_api_key': '你的OpenAI API密钥',
            'openai_api_base': 'https://api.openai.com/v1',
            'use_tesseract': 'true',
            'ocr_api_url': '你的OCR API地址',
            'ocr_api_key': '你的OCR API密钥'
        }
        config['Paths'] = {
            'screenshot_dir': os.path.join(os.path.expanduser('~'), 'Screenshots'),
            'tesseract_path': r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        }

        # 确保截图目录存在
        os.makedirs(config['Paths']['screenshot_dir'], exist_ok=True)

        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            config.write(f)
    else:
        config.read(CONFIG_FILE, encoding='utf-8')

    return config


class ScreenshotTool:
    def __init__(self, save_dir):
        self.save_dir = save_dir
        self.root = tk.Tk()
        self.root.attributes('-alpha', 0.1)
        self.root.attributes('-fullscreen', True)
        self.root.attributes('-topmost', True)

        self.canvas = tk.Canvas(self.root, cursor="cross")
        self.canvas.pack(fill="both", expand=True)

        self.start_x = None
        self.start_y = None
        self.current_rect = None

        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

        self.root.bind("<Escape>", lambda e: self.root.quit())

        self.screenshot = None
        self.selection = None

    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y

    def on_drag(self, event):
        if self.current_rect:
            self.canvas.delete(self.current_rect)
        self.current_rect = self.canvas.create_rectangle(
            self.start_x, self.start_y, event.x, event.y, outline='red'
        )

    def on_release(self, event):
        if self.start_x and self.start_y:
            x1 = min(self.start_x, event.x)
            y1 = min(self.start_y, event.y)
            x2 = max(self.start_x, event.x)
            y2 = max(self.start_y, event.y)

            self.root.withdraw()

            screenshot = pyautogui.screenshot()
            self.selection = screenshot.crop((x1, y1, x2, y2))
            self.root.quit()


def capture_screen(save_dir):
    """
    捕获屏幕区域并保存
    :param save_dir: 截图保存目录
    :return: 保存的图片路径
    """
    tool = ScreenshotTool(save_dir)
    tool.root.mainloop()

    if tool.selection:
        # 生成文件名
        filename = 'screenshot.png'
        filepath = os.path.join(save_dir, filename)
        tool.selection.save(filepath)
        return filepath
    return None


def ocr_image(image_path, config):
    """
    OCR识别函数，支持本地Tesseract和在线API两种方式
    :param image_path: 图片路径
    :param config: 配置信息
    """
    try:
        use_tesseract = config['API'].getboolean('use_tesseract')

        if use_tesseract:
            # 设置Tesseract路径
            pytesseract.pytesseract.tesseract_cmd = config['Paths']['tesseract_path']
            text = pytesseract.image_to_string(Image.open(image_path), lang='chi_sim')
            return text.strip()
        else:
            # 使用在线OCR API
            with open(image_path, 'rb') as image_file:
                img_base64 = base64.b64encode(image_file.read()).decode()

            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {config["API"]["ocr_api_key"]}'
            }

            payload = {
                'image': img_base64,
                'language': 'chi_sim'
            }

            response = requests.post(config['API']['ocr_api_url'], headers=headers, json=payload)

            if response.status_code == 200:
                result = response.json()
                return result.get('text', '')
            else:
                print(f"OCR API错误: {response.status_code}")
                return None

    except Exception as e:
        print(f"OCR识别错误: {str(e)}")
        return None


def ask_gpt(text, config):
    """
    调用GPT API获取回复
    :param text: 输入文本
    :param config: 配置信息
    """
    try:
        openai.api_key = config['API']['openai_api_key']
        openai.api_base = config['API']['openai_api_base']

        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "user", "content": text}
            ]
        )

        return response.choices[0].message.content
    except Exception as e:
        print(f"GPT API调用错误: {str(e)}")
        return None


def change_screenshot_dir():
    """更改截图保存目录"""
    config = load_config()
    new_dir = filedialog.askdirectory(title="选择截图保存目录")

    if new_dir:
        config['Paths']['screenshot_dir'] = new_dir
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            config.write(f)
        print(f"截图保存目录已更改为: {new_dir}")


def main():
    try:
        # 加载配置
        config = load_config()

        # 确保截图保存目录存在
        save_dir = config['Paths']['screenshot_dir']
        os.makedirs(save_dir, exist_ok=True)

        # 1. 区域截图
        image_path = capture_screen(save_dir)
        if not image_path:
            print("截图已取消")
            return

        print("截图已保存至:", image_path)

        # 2. OCR识别
        text = ocr_image(image_path, config)

        if text:
            print("识别到的文字:", text)

            # 3. 发送给GPT-4
            response = ask_gpt(text, config)
            if response:
                # 4. 打印结果
                print("GPT-4回复:", response)
            else:
                print("获取GPT回复失败")
        else:
            print("OCR识别失败")

    except Exception as e:
        print(f"程序执行错误: {str(e)}")


if __name__ == "__main__":
    # 添加命令行参数处理
    if len(sys.argv) > 1 and sys.argv[1] == '--config-dir':
        change_screenshot_dir()
    else:
        main()