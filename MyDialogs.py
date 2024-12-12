import tkinter as tk
import tkinter.ttk as ttk
from PIL import Image,ImageTk
from tkinter import messagebox, simpledialog,colorchooser, Toplevel
from draw_utils import get_hex_color
import numpy as np
from tkinter import font


class LabelColorSelectionDialog(simpledialog.Dialog):
    def __init__(self, parent, title, labels):
        self._title = title
        self.items = labels
        super().__init__(parent)
        
    def body(self, master):
        self.title(self._title)

        self.listbox = tk.Listbox(master, selectmode=tk.SINGLE)
        # 使用传入的items填充listbox
        if self.items and len(self.items)>0:
            for item in self.items:
                self.listbox.insert(tk.END, item)
        # 绑定选择响应事件
        self.listbox.bind("<<ListboxSelect>>", self.on_listbox_select)
        self.listbox.pack(pady=5)

        return self.entry

    def on_listbox_select(self, event):
        selection_index = self.listbox.curselection()
        if selection_index:
            self.text_var.set(self.listbox.get(selection_index))

    def colorset(self):
            setcolor = colorchooser.askcolor(color="red", title="背景色")
            root.config(bg=setcolor[1])

    def create_buttons(self):
        # 创建自定义按钮
        box = tk.Frame(self)

        ok_button = tk.Button(box, text="OK", width=10, command=self.check_and_close, default='active')
        ok_button.pack(side=tk.LEFT, padx=5, pady=5)
        cancel_button = tk.Button(box, text="Cancel", width=10, command=self.cancel)
        cancel_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.bind("<Return>", self.check_and_close)  # 绑定回车键

        box.pack()

    def check_and_close(self, event=None):
        value = self.text_var.get().strip()  # 删除前导和尾随的空白字符
        if not value:
            messagebox.showerror("Error", "Entry cannot be empty!")
            return  # 返回以跳过默认的关闭行为

        # 如果内容不为空，保存结果
        self.result = value
        self.destroy()  # 关闭对话框

    def cancel(self, event=None):
        self.result = None
        self.destroy()  # 关闭对话框

    def buttonbox(self):
        # 重写buttonbox以创建自定义按钮
        self.create_buttons()


class AddROIDialog(simpledialog.Dialog):
    def __init__(self, parent, title, label_dict:dict,  pos=[], cur_label=""):
        self._title = title
        self.cur_label = cur_label
        self.label_dict = label_dict
        self.pos = pos
        super().__init__(parent)
        
    def body(self, master):
        self.title(self._title)
        self.label = tk.Label(master, text=f"ROI position: {self.pos}")
        self.label.pack(pady=5)
        if len(self.cur_label) > 0:
            self.label = tk.Label(master, text=f"当前Label : {self.cur_label}")
            self.label.pack(pady=5)

        self.text_var = tk.StringVar()
        self.entry = tk.Entry(master, textvariable=self.text_var)
        self.entry.pack(pady=5)

        self.listbox = tk.Listbox(master, selectmode=tk.SINGLE)
        if self.label_dict and len(self.label_dict)>0:
            for key in self.label_dict:
                self.listbox.insert(tk.END, key)
        # 绑定选择响应事件
        self.listbox.bind("<<ListboxSelect>>", self.on_listbox_select)
        self.listbox.pack(pady=5)

        # return self.entry

    def on_listbox_select(self, event):
        selection_index = self.listbox.curselection()
        if selection_index:
            self.text_var.set(self.listbox.get(selection_index))

    # def apply(self):
    #     # 当用户点击默认的“OK”按钮时,获取textedit的内容
    #     value = self.text_var.get().strip()  # 删除前导和尾随的空白字符
    #     if not value:
    #         messagebox.showerror("Error", "Entry cannot be empty!")
    #         return  # 返回以跳过默认的关闭行为
    #     self.result = self.text_var.get()

    def create_buttons(self):
        # 创建自定义按钮
        box = tk.Frame(self)

        ok_button = tk.Button(box, text="OK", width=10, command=self.check_and_close, default='active')
        ok_button.pack(side=tk.LEFT, padx=5, pady=5)
        cancel_button = tk.Button(box, text="Cancel", width=10, command=self.cancel)
        cancel_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.bind("<Return>", self.check_and_close)  # 绑定回车键

        box.pack()

    def check_and_close(self, event=None):
        labelname = self.text_var.get().strip()  # 删除前导和尾随的空白字符
        if not labelname:
            messagebox.showerror("Error", "Entry cannot be empty!")
            return  # 返回以跳过默认的关闭行为

        # 如果内容不为空，判断是否为新标签, 颜色选择
        if labelname not in self.label_dict.keys():
            setcolor = colorchooser.askcolor(color="red", title="选择标签颜色")
            if not setcolor:
                color = get_hex_color()
            else:
                color = setcolor[1]
            self.label_dict[labelname] = color
        else:
            color = self.label_dict[labelname]

        self.result = labelname, color
        self.destroy()  # 关闭对话框

    def cancel(self, event=None):
        self.result = None
        self.destroy()  # 关闭对话框

    def buttonbox(self):
        # 重写buttonbox以创建自定义按钮
        self.create_buttons()


class SaveROIDialog(simpledialog.Dialog):

    def __init__(self, parent, title,  labels,  points):

        self._title = title
        self.labels = labels
        self.points = points
        super().__init__(parent)

    def body(self, master):

        self.title(self._title)
        # Two checkboxes
        self.save_points = tk.BooleanVar(value=False)
        self.save_npy = tk.BooleanVar(value=False)
        
        self.cb1 = ttk.Checkbutton(master, text="保存点的谱线", variable=self.save_points)
        self.cb1.grid(row=0, column=0, padx=5, pady=5, sticky='w')
        
        self.cb2 = ttk.Checkbutton(master, text="生成谱线npy文件", variable=self.save_npy)
        self.cb2.grid(row=0, column=1, padx=5, pady=5, sticky='w')
        
        # Frame
        self.frame = ttk.Frame(master, borderwidth=2, relief="sunken", width=200, height=100)
        self.frame.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky='ew')
        
        return 

    def buttonbox(self):
        # Clear default buttons and add custom ones
        box = ttk.Frame(self)
        
        w1 = ttk.Button(box, text="Save", width=10, command=self.save, default="active")
        w1.pack(side="left", padx=5, pady=5)
        w2 = ttk.Button(box, text="Don't Save", width=10, command=self.dont_save)
        w2.pack(side="left", padx=5, pady=5)
        w3 = ttk.Button(box, text="Cancel", width=10, command=self.cancel)
        w3.pack(side="left", padx=5, pady=5)
        
        self.bind("<Escape>", self.cancel)

        box.pack()

    def save(self):
        print("Saved!")
        self.result = 1
        self.destroy()
        
    def dont_save(self):
        print("Not saved!")
        self.result = 0
        self.destroy()

    def cancel(self, event=None):
        print("Cancelled!")
        if self.parent is not None:
            self.parent.focus_set()
        self.result = -1
        self.destroy()


class FileListFilterDialog(simpledialog.Dialog):

    def __init__(self, parent, filelistbox):
        self.filelistbox = filelistbox
        super().__init__(parent)

    def body(self, master):

        self.title("文件列表过滤")

        self.var = tk.IntVar(self)
        self.var.set(1)  # 默认选择

        # 创建Radiobutton控件
        tk.Label(self, text="过滤方式：").pack(anchor="w")
        tk.Radiobutton(self, text="保留", variable=self.var, value=0).pack(anchor="w")
        tk.Radiobutton(self, text="去掉", variable=self.var, value=1).pack(anchor="w", pady=5)

        # 创建单行文本输入控件
        tk.Label(self, text="过滤条件：").pack(anchor="w")
        self.entry = tk.Entry(self)
        self.entry.pack(pady=5)

        # # 创建确定和取消按钮
        # button_frame = tk.Frame(self)
        # button_frame.pack(pady=5)
        # ok_button = tk.Button(button_frame, text="确定", command=self.ok)
        # ok_button.pack(side="left", padx=5)
        # cancel_button = tk.Button(button_frame, text="取消", command=self.cancel)
        # cancel_button.pack(side="left")

        # self.bind("<Return>", self.ok)  # 绑定回车键到确定按钮
        # self.bind("<Escape>", self.cancel)  # 绑定Esc键到取消按钮

        # self.protocol("WM_DELETE_WINDOW", self.cancel)  # 绑定关闭窗口事件到取消按钮

        self.result = None  # 初始化result为None
        
        return 

    def buttonbox(self):
        # Clear default buttons and add custom ones
        box = ttk.Frame(self)
        
        w1 = ttk.Button(box, text="确定", width=10, command=self.ok, default="active")
        w1.pack(side="left", padx=5, pady=5)

        w3 = ttk.Button(box, text="取消", width=10, command=self.cancel)
        w3.pack(side="left", padx=5, pady=5)
        
        self.bind("<Return>", self.ok)  # 绑定回车键到确定按钮
        self.bind("<Escape>", self.cancel)  # 绑定Esc键到取消按钮

        box.pack()

    def ok(self):
        print("ok!")
        self.result = 1
        self.destroy()


    def cancel(self, event=None):
        print("Cancelled!")
        if self.parent is not None:
            self.parent.focus_set()
        self.result = -1
        self.destroy()




class DlgShowTable(tk.Toplevel):
    def __init__(self,  
                 heading_list:list,  content:np.ndarray, 
                 master=None, title="标准谱线SAM距离", row_title=False):
        super().__init__(master)
        
        self.title(title)
        self.title = title
        self.resizable(True, True)
        # self.grab_set()

        self.heading_list = heading_list
        self.content = content
        self.row_title = row_title
       
        self.init_ui()

        # 放置对话框在屏幕中央
        # print(f"{self.winfo_reqwidth()}x{self.winfo_reqheight()}+{int((self.master.winfo_screenwidth() - self.winfo_reqwidth()) / 2)}+{int((self.master.winfo_screenheight() - self.winfo_reqheight()) / 2)}")
        w = 800
        h = 600
        self.geometry(f"{w}x{h}+{int((self.master.winfo_screenwidth() - w) / 2)}+{int((self.master.winfo_screenheight() - h) / 2)}")

        return
    

    def init_ui(self):
        label_font = font.Font(family='SimHei', size=12, weight='bold')
        frame_title = tk.Label(self, text=self.title, font=label_font)
        frame_title.pack(side="top", fill='y')
        frame_content = ttk.Frame(self)
        frame_content.pack(side="top", expand=1, fill="both")
        frame_btn = ttk.Frame(self)
        frame_btn.pack(side="bottom", fill='y')

        # 创建Treeview控件
        row_num, col_num = self.content.shape
        if self.row_title:
            col_num += 1
            self.heading_list.insert(0, "")

        tree_columns = [str(i) for i in range(col_num)]
        self.tree_content = ttk.Treeview(frame_content, columns=tree_columns, show='headings', selectmode=tk.BROWSE)
        # Create scrollbars
        self.x_scroll = tk.Scrollbar(frame_content, orient="horizontal", command=self.tree_content.xview)
        self.y_scroll = tk.Scrollbar(frame_content, orient="vertical", command=self.tree_content.yview)
        # Configure the canvas to be scrollable
        self.tree_content.configure(yscrollcommand=self.y_scroll.set, xscrollcommand=self.x_scroll.set)
        self.tree_content.grid(row=0, column=0, sticky="nsew")
        self.x_scroll.grid(row=1, column=0, sticky="ew")
        self.y_scroll.grid(row=0, column=1, sticky="ns")
        frame_content.grid_rowconfigure(0, weight=10)
        frame_content.grid_columnconfigure(0, weight=10)

        btn_ok = ttk.Button(frame_btn, text="确定", command=self.on_closing)
        btn_ok.pack(side='top', padx=5)


        # 设置表格列标题
        for i in range(col_num):
            self.tree_content.heading(tree_columns[i], text=self.heading_list[i], anchor=tk.CENTER)
            self.tree_content.column(tree_columns[i],  anchor="center")

        # 表格数据
        self.tree_class_rowid = {}
        for i in range(row_num):
            row_value = []
            if self.row_title:
                row_value.append(self.heading_list[i+1])
            
            for v in self.content[i,:]:
                row_value.append(str(v))

            self.tree_content.insert("", 'end', values=tuple(row_value), iid=str(i))

        
           
        return
    

    def on_closing(self):

        # 确保关闭事件继续传播
        self.destroy()
        # self.quit()
        pass
    


if __name__ == '__main__':

    class App1(tk.Frame):
        def __init__(self, master=None):
            tk.Frame.__init__(self, master)
            self.pack()

            self.icon_image = tk.PhotoImage(file="openfolder.gif")
            imglabel = tk.Label(self, image=self.icon_image, relief='groove')
            imglabel.pack(pady=20)

            self.button = tk.Button(self, text="Open", command=self.on_button1)
            self.button.pack(pady=20)

            self.quitButton = tk.Button(self, text="Quit", command=self.quit)
            self.quitButton.pack(side=tk.BOTTOM, pady=10)
            

        def on_button1(self):
            d = AddROIDialog(self, "MyDialog")
            print(d.result)

    # import cv2

    # img = cv2.imread("Res//images//document_open.png")
    
    # cv2.imshow("ss", img)
    # cv2.waitKey()
    # cv2.destroyAllWindows()

    root = tk.Tk()
    app = App1(master=root)
    app.mainloop()