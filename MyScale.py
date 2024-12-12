import tkinter as tk
from tkinter import Scale, IntVar
from algos import img_stretch

class MyScale():
    def __init__(self, parent:tk.Widget):
        
        self.entry1_latest_value = IntVar(value=0) 
        self.entry1 = tk.Entry(parent, textvariable=self.entry1_latest_value, width=3)
        self.entry1.bind('<Return>', self.update_scale_from_entry)
        # self.entry1.bind("<KeyPress>", self.validate_input1)
        self.scale1_latest_value = IntVar(value=0) 
        self.scale1 = Scale(parent, from_=0, to=100, orient="horizontal", 
                            variable=self.scale1_latest_value,showvalue=0,
                          command=self.command1, resolution=1, troughcolor="lightgray")
        self.entry1.grid(row=0, column=0, padx=5)
        self.scale1.grid(row=0, column=1, padx=5, sticky='EW')
        self.last_value1 = 0

        self.entry2_latest_value = IntVar(value=50) 
        self.entry2 = tk.Entry(parent, textvariable=self.entry2_latest_value, width=3)
        self.entry2.bind('<Return>', self.update_scale_from_entry)
        self.scale2_latest_value = IntVar(value=50) 
        self.scale2 = Scale(parent, from_=0, to=100, orient="horizontal", 
                            variable=self.scale2_latest_value,showvalue=0,
                          command=self.command2, resolution=1, troughcolor="lightgray")
        self.entry2.grid(row=1, column=0, padx=5)
        self.scale2.grid(row=1, column=1, padx=5, sticky='EW')
        # self.scale2.set(50)
        self.last_value2 = 50

        self.entry3_latest_value = IntVar(value=100) 
        self.entry3 = tk.Entry(parent, textvariable=self.entry3_latest_value, width=3)
        self.entry3.bind('<Return>', self.update_scale_from_entry)
        self.scale3_latest_value = IntVar(value=100) 
        self.scale3 = Scale(parent, from_=0, to=100, orient="horizontal", 
                            variable=self.scale3_latest_value,showvalue=0,
                          command=self.command3, resolution=1, troughcolor="lightgray")
        self.entry3.grid(row=2, column=0, padx=5)
        self.scale3.grid(row=2, column=1, padx=5, sticky='EW')

        self.last_value3 = 100

        parent.columnconfigure(0, weight=0)
        parent.columnconfigure(1, weight=1)

        self.set_status(False)

    def get_values(self):
        return (self.scale1_latest_value.get(), self.scale2_latest_value.get(), self.scale3_latest_value.get())
    

    def set_status(self, enabled= False):
        if enabled:
            self.scale1["state"] = tk.NORMAL
            self.scale2["state"] = tk.NORMAL
            self.scale3["state"] = tk.NORMAL
        else:
            self.scale1["state"] = tk.DISABLED
            self.scale2["state"] = tk.DISABLED
            self.scale3["state"] = tk.DISABLED
        

    def command1(self, text):
        
        right_v = self.scale2_latest_value.get()
        if self.scale1_latest_value.get() >= right_v:
            print(f"Command1 called, value exceeds!")
            self.scale1_latest_value.set(self.last_value1)
            self.entry1_latest_value.set(self.last_value1)
            return
        self.last_value1 = self.scale1_latest_value.get()
        self.scale1.event_generate('<<IMGStretchEvent>>')
        self.entry1_latest_value.set(self.last_value1)
        

    def command2(self, text):
        right_v = self.scale3_latest_value.get()
        if self.scale2_latest_value.get() >= right_v:
            self.scale2_latest_value.set(self.last_value2)
            self.entry2_latest_value.set(self.last_value2)
            return
        left_v = self.scale1_latest_value.get()
        if self.scale2_latest_value.get() <= left_v:
            print(f"Command2 called, value left exceeds!")
            self.scale2_latest_value.set(self.last_value2)
            self.entry2_latest_value.set(self.last_value2)
            return
        self.last_value2 = self.scale2_latest_value.get()
        self.scale2.event_generate('<<IMGStretchEvent>>')
        self.entry2_latest_value.set(self.last_value2)


    def command3(self, text):
        left_v = self.scale2_latest_value.get()
        if self.scale3_latest_value.get() <= left_v:
            self.scale3_latest_value.set(self.last_value3)
            self.entry3_latest_value.set(self.last_value3)
            return
        self.last_value3 = self.scale3_latest_value.get()
        self.scale3.event_generate('<<IMGStretchEvent>>')
        self.entry3_latest_value.set(self.last_value3)


    def update_scale_from_entry(self, event):

        if event.widget == self.entry1:
            self.scale1_latest_value.set(self.entry1_latest_value.get())
            self.command1(0)
        elif event.widget == self.entry2:
            self.scale2_latest_value.set(self.entry2_latest_value.get())
            self.command2(0)
        else:
            self.scale3_latest_value.set(self.entry3_latest_value.get())
            self.command3(0)
        pass

    # def validate_input1(self, event):
    #     # 获取Entry控件的内容
    #     input_text = self.entry1.get()
    #     # 检查最后一个字符是否为数字（考虑到可能删除字符的情况，也检查整个字符串）
    #     if not input_text.isdigit() and input_text != "":  # 这里允许空字符串，即允许删除所有字符
    #         # 如果不是数字，显示错误消息，并恢复为之前的合法内容
    #         messagebox.showerror("输入错误", "请输入数字！")
    #         # 这里可以选择清除非法输入，或者恢复为之前的合法值
    #         # 例如，清除最后一个非法字符：
    #         entry.delete(len(input_text)-1, tk.END)  # 删除最后一个字符
    #         # 或者，恢复为之前的某个合法值（需要额外逻辑来存储合法值）


        
        
        
