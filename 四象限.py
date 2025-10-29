import tkinter as tk
from tkinter import simpledialog
import json
import os
import sys

DATA_FILE = os.path.expanduser("~/.my_app_config/EisenhowerMatrix/todos.kcptun_config.json")
if sys.platform == "darwin":
    RIGHT_CLICK = "<Button-2>"
else:
    RIGHT_CLICK = "<Button-3>"

class TodoItem:
    def __init__(self, canvas, text, x=50, y=50, done=False):
        self.canvas = canvas
        self.text = text
        self.done = done
        self.width = 120
        self.height = 50

        self.rect = self.canvas.create_rectangle(x, y, x+self.width, y+self.height,
                                                 fill="lightyellow" if not done else "lightgreen",
                                                 outline="black", width=2)
        self.label = self.canvas.create_text(x+self.width/2, y+self.height/2,
                                             text=self.text, font=("Arial", 12))

        self.canvas.tag_bind(self.rect, "<Button-1>", self.start_drag)
        self.canvas.tag_bind(self.label, "<Button-1>", self.start_drag)
        self.canvas.tag_bind(self.rect, "<B1-Motion>", self.do_drag)
        self.canvas.tag_bind(self.label, "<B1-Motion>", self.do_drag)
        self.canvas.tag_bind(self.rect, RIGHT_CLICK, self.show_menu)
        self.canvas.tag_bind(self.label, RIGHT_CLICK, self.show_menu)
        self.canvas.tag_bind(self.rect, "<Double-1>", self.edit_text)
        self.canvas.tag_bind(self.label, "<Double-1>", self.edit_text)

        self.drag_data = {"x": 0, "y": 0}

    def start_drag(self, event):
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y

    def do_drag(self, event):
        dx = event.x - self.drag_data["x"]
        dy = event.y - self.drag_data["y"]
        self.canvas.move(self.rect, dx, dy)
        self.canvas.move(self.label, dx, dy)
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y
        app.save_todos()

    def show_menu(self, event):
        menu = tk.Menu(self.canvas, tearoff=0)
        menu.add_command(label="完成", command=self.mark_done)
        menu.add_command(label="删除", command=self.delete)
        menu.post(event.x_root, event.y_root)

    def mark_done(self):
        self.done = True
        self.canvas.itemconfig(self.rect, fill="lightgreen")
        app.save_todos()

    def delete(self):
        self.canvas.delete(self.rect)
        self.canvas.delete(self.label)
        app.todos.remove(self)
        app.save_todos()

    def edit_text(self, event):
        new_text = simpledialog.askstring("修改待办", "请输入新的内容:", initialvalue=self.text)
        if new_text:
            self.text = new_text
            self.canvas.itemconfig(self.label, text=new_text)
            app.save_todos()

    def get_data(self):
        x1, y1, x2, y2 = self.canvas.coords(self.rect)
        return {"text": self.text, "x": x1, "y": y1, "done": self.done}

class TodoApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Eisenhower Matrix 待办")
        self.root.geometry("800x600")
        self.root.resizable(False, False)  # 禁止调整大小（宽、高都不能改）
        self.canvas = tk.Canvas(root, width=800, height=600)
        self.canvas.pack(fill="both", expand=True)

        self.draw_quadrants()

        self.canvas.bind("<Double-1>", self.create_todo_on_click)

        self.todos = []
        self.load_todos()

    def draw_quadrants(self):
        w, h = 800, 600
        mid_x, mid_y = w/2, h/2

        # 定义四象限颜色和文字
        quadrants = [
            {"coords": (0, 0, mid_x, mid_y), "color": "#ffcccc", "text": "立刻去做"},
            {"coords": (mid_x, 0, w, mid_y), "color": "#fff2cc", "text": "计划一个时间去做"},
            {"coords": (0, mid_y, mid_x, h), "color": "#cce5ff", "text": "委托别人帮忙"},
            {"coords": (mid_x, mid_y, w, h), "color": "#ccffcc", "text": "消除它"},
        ]

        for q in quadrants:
            x1, y1, x2, y2 = q["coords"]
            self.canvas.create_rectangle(x1, y1, x2, y2, fill=q["color"], outline="black")
            self.canvas.create_text((x1+x2)/2, (y1+y2)/2, text=q["text"],
                                    font=("Arial", 16, "bold"), fill="gray")

    def create_todo_on_click(self, event):
        # 点击空白区域才新增
        items = self.canvas.find_overlapping(event.x, event.y, event.x, event.y)
        for item in items:
            if any(item == t.rect or item == t.label for t in self.todos):
                return
        text = simpledialog.askstring("新增待办", "请输入待办内容:")
        if text:
            todo = TodoItem(self.canvas, text, event.x, event.y)
            self.todos.append(todo)
            self.save_todos()

    def save_todos(self):
        data = [t.get_data() for t in self.todos]
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_todos(self):
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data:
                todo = TodoItem(self.canvas, item["text"], item["x"], item["y"], item.get("done", False))
                self.todos.append(todo)

if __name__ == "__main__":
    root = tk.Tk()
    app = TodoApp(root)
    root.mainloop()
