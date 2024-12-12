import tkinter as tk
from tkinter import ttk
from tkinter import Toplevel, Canvas, Menu
from tkinter import filedialog, messagebox, simpledialog
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import os
from PIL import Image, ImageTk
import win32file, win32api, win32con     # pip install pywin32
from draw_utils import ImgDataManager, ShapeManager


class WindowShowImage(Toplevel):

    def __init__(self, file_path:str, image:np.ndarray, master=None, **kw):
        super().__init__(master, **kw)

        # 绑定窗口关闭事件
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.title(f"推理结果-{file_path}")
        self.state("zoomed")
        # self.geometry("800x600")  # Initial size
        
        # Allow the window to be resized
        self.resizable(True, True)
        self.init_ui()
        self.load_image(image)
        self.image = image
        self.file_path = file_path

        self.image_bg_on_canvas = None
        self.truth_polygon_list = []
        self.truth_pos_list = []

        return
      

    def on_closing(self):

        self.destroy()
        return

    
    def maximize_window(self):
        self.attributes("-zoomed", True)
        
    def minimize_window(self):
        self.iconify()


    def init_ui(self):
        
        self.canvas_frame = ttk.Frame(self)
        self.canvas_frame.pack(side='top', fill="both", expand=True)
        self.button_frame = ttk.Frame(self)
        self.button_frame.pack(side='bottom', fill="x")

        self.canvas = Canvas(self.canvas_frame, cursor="cross", bd=0)
        self.canvas.bind("<ButtonPress-1>", self.mouse_clicked)
        self.canvas.bind("<B1-Motion>", self.mouse_dragging)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)

        # Create scrollbars
        self.x_scroll = tk.Scrollbar(self.canvas_frame, orient="horizontal", command=self.canvas.xview)
        self.y_scroll = tk.Scrollbar(self.canvas_frame, orient="vertical", command=self.canvas.yview)

        # Configure the canvas to be scrollable
        self.canvas.configure(yscrollcommand=self.y_scroll.set, xscrollcommand=self.x_scroll.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.x_scroll.grid(row=1, column=0, sticky="ew")
        self.y_scroll.grid(row=0, column=1, sticky="ns")
        # # Position the scrollbars relative to the canvas
        self.canvas_frame.grid_rowconfigure(0, weight=1)
        self.canvas_frame.grid_rowconfigure(1, weight=0)
        self.canvas_frame.grid_columnconfigure(0, weight=1)
        self.canvas_frame.grid_columnconfigure(1, weight=0)

        self.var_show_orig = tk.BooleanVar(value=False)
        checkbox = ttk.Checkbutton(self.button_frame, text='显示真值', command=self.update_image,
                variable=self.var_show_orig, onvalue=True, offvalue=False)
        checkbox.pack(side='left', anchor='w')
        # self.var_transparency = tk.IntVar(value=50) 
        # self.entry_transparency = tk.Entry(self.button_frame, textvariable=self.var_transparency, width=3)
        # self.scale_transparency = tk.Scale(self.button_frame, from_=0, to=100, orient="horizontal", 
        #                     variable=self.var_transparency,showvalue=0,
        #                   command=self.on_transparent_change, resolution=1, troughcolor="lightgray")
        # self.entry_transparency.pack(side='left', padx=2)
        # self.scale_transparency.pack(side='left', padx=2, expand=1, fill='x')
        save_button = tk.Button(self.button_frame, text="保存图片", command=self.save_as_file)
        save_button.pack(side='right', padx=5, pady=5)

        pass


    def load_image(self, image:np.ndarray):
        '''
        To do: 增加原img单通道灰度图作为底图，便于进行真值比对
        '''
        if image is None:
            return
        
        self.image = image
        self.image_height = image.shape[0]
        self.image_width = image.shape[1]
        self.show_height = image.shape[0]
        self.show_width = image.shape[1] 
        self.showing_scale = 1.0

        pil_image = Image.fromarray(self.image)
        self.image_tk = ImageTk.PhotoImage(pil_image)   # 注意：image_tk必须是成员变量,不能为局部变量
        self.image_on_canvas = self.canvas.create_image(0, 0, anchor="nw", image=self.image_tk)
        # self.canvas.tag_lower(self.image_on_canvas)
        
        self.canvas.config(scrollregion=self.canvas.bbox("all"))

        
    def on_transparent_change(self, event):

        self.update_image()
        return


    def update_image(self):
        if self.image is None:
            return
        
        pil_image = Image.fromarray(self.image)
        pil_image = pil_image.resize((self.show_width, self.show_height))

        self.image_tk = ImageTk.PhotoImage(pil_image)   # 注意：image_tk必须是成员变量,不能为局部变量
        if self.image_on_canvas:
            self.canvas.delete(self.image_on_canvas)
        self.image_on_canvas = self.canvas.create_image(0, 0, anchor="nw", image=self.image_tk)
        self.canvas.tag_lower(self.image_on_canvas)
        self.canvas.config(scrollregion=self.canvas.bbox("all"))

        if self.image_bg_on_canvas:
            self.canvas.delete(self.image_bg_on_canvas)


        for id in self.truth_polygon_list:
            self.canvas.delete(id)

        if self.var_show_orig.get():
        
            # img_info = ImgInfo()
            # img_info.create_img_info(self.file_path)
            # ch_show = img_info.hdr.bands // 2
            # img = img_info.get_img_by_channels([ch_show])
            # img = img.reshape((img_info.hdr.lines, -1))
            # img = img*255/65535
            # pil_image_gray = Image.fromarray(img)
            # pil_image_gray = pil_image_gray.resize((self.show_width, self.show_height))
            # pil_image_color = pil_image_gray.convert('RGBA')

            # # 创建一个alpha图层，并填充为128（半透明）
            # p = int(self.var_transparency.get()*255/100)
            # alpha_layer = Image.new('L', pil_image_color.size, p)
            # # 将alpha图层添加到图像的alpha通道
            # pil_image_color.putalpha(alpha_layer)

            # self.image_tk_bg = ImageTk.PhotoImage(pil_image_color)   # 注意：image_tk必须是成员变量,不能为局部变量
            
            # self.image_bg_on_canvas = self.canvas.create_image(0, 0, anchor="nw", image=self.image_tk_bg)
            # self.canvas.tag_raise(self.image_bg_on_canvas)
            scale = self.show_height / self.image.shape[0]

            if len(self.truth_pos_list) == 0:

                filename, ext = os.path.splitext(self.file_path)
                truth_filename = filename+"_truth.txt"
                if os.path.exists(truth_filename):
                    try:
                        lines = None
                        with open(truth_filename, "r", encoding='utf-8') as f:
                            lines = f.readlines()
                    except Exception as e:
                        # messagebox.showwarning("标签文件错误", "标签文件打开错误！")  
                        pass

                    if lines is not None and len(lines) > 0:

                        for index, line in enumerate(lines):
                            line_list = line.strip().replace("\n", "").split(',')
                            if len(line_list) < 6:
                                # messagebox.showwarning("标签文件错误", f"标签文件第{index+1}行格式错误！")
                                continue

                            label = line_list[0].strip()
                            shape = line_list[1].strip()     
                            pos_pairs = [int(pos) for pos in line_list[2:]]
                            if len(pos_pairs) % 2 != 0:
                                print(f"标签文件第{index+1}行错误！坐标数量错误：{len(pos_pairs)}")
                                continue
                            
                            pos_value_error = False
                            for i in range(0, len(pos_pairs), 2):
                                if pos_pairs[i] >= self.image.shape[1] or pos_pairs[i+1] >= self.image.shape[0]:
                                    pos_value_error = True
                                    break
                            if pos_value_error:
                                print(f"标签第{index+1}行, 坐标值超过图像大小!") 
                                continue

                            color = 'yellow'

                            coord_list = [round(pos*scale) for pos in pos_pairs]
                            id = self.canvas.create_polygon(coord_list, outline=color, dash=True, width=2)
                            self.truth_polygon_list.append(id)
                            self.truth_pos_list.append(pos_pairs)
                            
                
            else:

                for pos_pair in self.truth_pos_list:
                    color = 'yellow'

                    coord_list = [round(pos*scale) for pos in pos_pair]
                    id = self.canvas.create_polygon(coord_list, outline=color, dash=True, width=2)
                    self.truth_polygon_list.append(id)

                pass    

            pass

        pass


    # event.x,event.y 是相对于绑定事件的控件的左上角的坐标
    # event.x_root, event.y_root 是相对于屏幕的左上角的坐标（注意：不是应用程序窗口左上角）
    # canvas上的绘制需要基于event的xy坐标进行
    def mouse_clicked(self, event):
        if self.image_on_canvas is None:
            return
        
        # 转换到图像坐标
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)

        print(f"mouse click event x={event.x}; y={event.y}")
        print(f"mouse click canvas x={canvas_x}; y={canvas_y}")

        # 如果图像坐标超过当前zoom图像的大小，则返回
        if canvas_x > self.show_width or canvas_y> self.show_height or canvas_x<0 or canvas_y<0 :
            return 

        #canvas尺寸是显示出来的那部分大小
        canvas_width = self.canvas.winfo_width()   
        canvas_height = self.canvas.winfo_height()

        # 仅当图像大小超过canvas大小时才记录鼠标位置
        # 图像在canvas范围内的时候，不用拖动
        if self.show_width > canvas_width or self.show_height > canvas_height:
            self.end_x = event.x
            self.end_y = event.y

        return 
        

    def mouse_dragging(self, event):
        if self.image_on_canvas is None:
            return
        
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        # 仅当图像大小超过canvas大小时才记录鼠标位置
        if self.show_width > canvas_width:
            x_diff = event.x - self.end_x
            # 使用canvas的xview_scroll和yview_scroll方法来移动内容
            self.canvas.xview_scroll(-x_diff, "units")
            self.end_x = event.x
        if self.show_height > canvas_height:
            y_diff = event.y - self.end_y
            self.canvas.yview_scroll(-y_diff, "units")    
            self.end_y = event.y

        return 


    def on_mouse_wheel(self, event):
        if not self.image_on_canvas:
            return
        
        #  检查Ctrl键是否按下
        if win32api.GetKeyState(win32con.VK_CONTROL) < 0:
            # Ctrl键按下，处理事件
            # print("Ctrl + 鼠标滚轮事件被触发")
            # Adjust the scale factor based on the OS and event details
            if event.num == 4 or event.delta > 0:  # For Linux or Windows/Mac scroll up
                # if self.img_info.hdr.lines*self.showing_scale > 4000 or \
                # self.img_info.hdr.samples*self.showing_scale > 4000 or \
                #     self.showing_scale >= 20:
                #     return
                scale_factor = 1.1
            elif event.num == 5 or event.delta < 0:  # For Linux or Windows/Mac scroll down
                # if self.img_info.hdr.lines*self.showing_scale < 100 or \
                # self.img_info.hdr.samples*self.showing_scale < 100:
                #     return
                scale_factor = 0.9
            else:
                return
            self.on_zoom(scale_factor=scale_factor)

    
    def on_zoom(self, scale_factor=1.1):
        
        cur_scale_factor = self.showing_scale*scale_factor
        if cur_scale_factor > 10 or cur_scale_factor<0.5:
            return

        # Resize the displayed image using the current displayed image
        self.showing_scale *= scale_factor
        self.show_width = int(self.showing_scale * self.image_width)
        self.show_height = int(self.showing_scale * self.image_height)
        
        self.update_image()
        print(f"zoom sx: {self.show_width/self.image_width}; sy:{self.show_height/self.image_height}")



    def save_as_file(self):

        dir_path = os.path.dirname(self.file_path)
        filename = os.path.basename(self.file_path)
        name, ext = os.path.splitext(filename)
        result_name = name + "_result.jpg"

        result_filepath = filedialog.asksaveasfilename(title="保存结果图片", confirmoverwrite=True, defaultextension='.jpg', 
                                                    filetypes=[('JPEG file', '.jpg')],
                                                    initialdir=dir_path, initialfile=result_name)

        if result_filepath:
            # 使用PIL保存图像
            pil_image = Image.fromarray(self.image, 'RGB')
            pil_image.save(result_filepath)

            print(f"{result_filepath} saved!")
        
        pass



class WindowShowSamDistanceImage(Toplevel):

    def __init__(self, classname_list:list, distance:np.ndarray, master=None):
        super().__init__(master)

        # 绑定窗口关闭事件
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.title(f"SAM距离")
        self.state("zoomed")
        # self.geometry("800x600")  # Initial size
        
        # Allow the window to be resized
        self.resizable(True, True)
        self.distance = distance
        self.classname_list = classname_list
        
        self.image_height, self.image_width, self.classnum = distance.shape
        self.current_index = 0
        
        self.image_on_canvas = None

        self.truth_rect_list = []
        self.truth_canvas_id_list = []

        for id in ShapeManager.truth_shape_id_list:
            shape_obj = ShapeManager.shape_id_object_dict[id]
            pos_list = shape_obj.pos_list
            self.truth_rect_list.append(pos_list)
        
        
        self.wv_list = ImgDataManager.wave_enabled_list
        self.img = ImgDataManager.get_norm_img()

        self.gain_enabled = ImgDataManager.use_de_gain
        self.truth_canvas_id_list = []
        self.str_gain = "de-gain" if self.gain_enabled else "with gain"

        self.show_height = self.image_height
        self.show_width = self.image_width
        self.showing_scale = 1.0
        self.init_ui()
        self.load_image(self.current_index)
        
        # self.image_bg_on_canvas = None


        return
      

    def on_closing(self):

        self.destroy()
        return

    
    def maximize_window(self):
        self.attributes("-zoomed", True)
        
    def minimize_window(self):
        self.iconify()


    def init_ui(self):
        
        self.bind('<Left>', self.on_browse_prev_img)
        self.bind('<Right>', self.on_browse_next_img)
        
        self.title_label = tk.Label(self, text=f"{ShapeManager.current_file_path} - {self.classname_list[self.current_index]} - {self.str_gain}", anchor='center')
        self.title_label.pack(side='top', fill="x")
        self.center_frame = ttk.PanedWindow(self, orient="horizontal")   # orient: Literal['vertical', 'horizontal'] = "vertical"
        self.center_frame.pack(side='top', fill="both", expand=True)
        self.button_frame = ttk.Frame(self)
        self.button_frame.pack(side='bottom', fill="x")


        self.canvas_frame = tk.Frame(self.center_frame)
        self.operation_frame = tk.Frame(self.center_frame)
        self.center_frame.add(self.canvas_frame, weight=8)
        self.center_frame.add(self.operation_frame, weight=2)
  
        self.canvas = Canvas(self.canvas_frame, cursor="cross", bd=0)
        self.canvas.pack(side='top', fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self.mouse_clicked)
        self.canvas.bind("<B1-Motion>", self.mouse_dragging)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)

        # Create scrollbars
        self.x_scroll = tk.Scrollbar(self.canvas_frame, orient="horizontal", command=self.canvas.xview)
        self.y_scroll = tk.Scrollbar(self.canvas_frame, orient="vertical", command=self.canvas.yview)

        # Configure the canvas to be scrollable
        self.canvas.configure(yscrollcommand=self.y_scroll.set, xscrollcommand=self.x_scroll.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.x_scroll.grid(row=1, column=0, sticky="ew")
        self.y_scroll.grid(row=0, column=1, sticky="ns")
        # # Position the scrollbars relative to the canvas
        self.canvas_frame.grid_rowconfigure(0, weight=1)
        self.canvas_frame.grid_rowconfigure(1, weight=0)
        self.canvas_frame.grid_columnconfigure(0, weight=1)
        self.canvas_frame.grid_columnconfigure(1, weight=0)

        self.prev_button = ttk.Button(self.button_frame, text="上一幅", command=self.prev_image)
        self.prev_button.grid(row=0, column=0, sticky="w", ipadx=10)
        self.var_show_truth = tk.BooleanVar(value=False)
        checkbox = ttk.Checkbutton(self.button_frame, text='显示真值', command=self.show_truth,
                variable=self.var_show_truth, onvalue=True, offvalue=False)
        checkbox.grid(row=0, column=1, sticky="e", ipadx=10)

        if len(self.truth_rect_list) == 0:
            checkbox.config(state='disabled')

        wave_list = ['禁用']
        wave_list.extend(self.wv_list)
        wave_list.append('波段均值')
        self.wave_combox = ttk.Combobox(self.button_frame, values=wave_list)
        self.wave_combox.grid(row=0, column=2, sticky="we", ipadx=2)
        self.var_amp_limit = tk.DoubleVar(value=0.1) 
        self.scale_amp = tk.Scale(self.button_frame, from_=0, to=1, orient="horizontal", 
                            variable=self.var_amp_limit, showvalue=1,
                            command=None, resolution=0.01, troughcolor="lightgray")
        self.scale_amp.grid(row=0, column=3, sticky="we", ipadx=2)

        self.var_threshold = tk.DoubleVar(value=0.9) 
        self.scale_thres = tk.Scale(self.button_frame, from_=0, to=1, orient="horizontal", 
                            variable=self.var_threshold, showvalue=1,
                            command=None, resolution=0.01, troughcolor="lightgray")
        self.scale_thres.grid(row=0, column=4, sticky="we", ipadx=2)
        self.update_thres_button = ttk.Button(self.button_frame, text="刷新", command=lambda:self.load_image(self.current_index))
        self.update_thres_button.grid(row=0, column=5, sticky="w", ipadx=2)
        self.ok_button = ttk.Button(self.button_frame, text="关闭窗口", command=self.on_closing)
        self.ok_button.grid(row=0, column=6, sticky="w", ipadx=10)
        self.next_button = ttk.Button(self.button_frame, text="下一幅", command=self.next_image)
        self.next_button.grid(row=0, column=7, sticky="e", ipadx=10)

        self.update_browse_button_status()

        self.button_frame.grid_columnconfigure(0, weight=1)
        self.button_frame.grid_columnconfigure(1, weight=1)
        self.button_frame.grid_columnconfigure(2, weight=0)
        self.button_frame.grid_columnconfigure(3, weight=1)
        self.button_frame.grid_columnconfigure(4, weight=1)
        self.button_frame.grid_columnconfigure(5, weight=0)
        self.button_frame.grid_columnconfigure(6, weight=0)
        self.button_frame.grid_columnconfigure(7, weight=1)

        return


    def load_image(self, index):
        '''
        self.distance: [H,W,Class]
        '''
        if 0 <= index < self.classnum:
            
            wv_index = self.wave_combox.current()
            distance = self.distance[:,:,index]
            
            image = np.zeros_like(distance, dtype=np.uint8)
            image[distance>=self.var_threshold.get()] = 255

            if wv_index > 0:
                if wv_index == len(self.wv_list) + 1: # 波段均值
                    img = np.mean(self.img, axis=2)
                    pass
                else:
                    img = self.img[:,:, wv_index-1]
                    pass
                mask = np.zeros_like(img, dtype=np.uint8)
                mask[img<self.var_amp_limit.get()] = 255
                image = np.bitwise_and(image, mask)

            if self.image_on_canvas is not None:
                self.canvas.delete(self.image_on_canvas)
            
            pil_image = Image.fromarray(image)
            if self.show_height != self.show_width or self.show_width != self.W:
                pil_image = pil_image.resize((self.show_width, self.show_height))

            self.image_tk = ImageTk.PhotoImage(pil_image)   # 注意：image_tk必须是成员变量,不能为局部变量
            self.image_on_canvas = self.canvas.create_image(0, 0, anchor="nw", image=self.image_tk)
            self.canvas.tag_lower(self.image_on_canvas)
            
            self.canvas.config(scrollregion=self.canvas.bbox("all"))

        return
    

    def show_truth(self):
        if self.image_on_canvas is None:
            return

        for id in self.truth_canvas_id_list:
            self.canvas.delete(id)

        scale = self.show_height / self.image_height
        if self.var_show_truth.get():
            
            for pos_list in self.truth_rect_list:
                color = 'red'
                coord_list = [round(pos*scale) for pos in pos_list]
                canvas_id = self.canvas.create_rectangle(coord_list, outline=color, dash=True, width=2)
                self.truth_canvas_id_list.append(canvas_id)

        return


    # event.x,event.y 是相对于绑定事件的控件的左上角的坐标
    # event.x_root, event.y_root 是相对于屏幕的左上角的坐标（注意：不是应用程序窗口左上角）
    # canvas上的绘制需要基于event的xy坐标进行
    def mouse_clicked(self, event):
        if self.image_on_canvas is None:
            return
        
        # 转换到图像坐标
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)

        print(f"mouse click event x={event.x}; y={event.y}")
        print(f"mouse click canvas x={canvas_x}; y={canvas_y}")

        # 如果图像坐标超过当前zoom图像的大小，则返回
        if canvas_x > self.show_width or canvas_y> self.show_height or canvas_x<0 or canvas_y<0 :
            return 

        #canvas尺寸是显示出来的那部分大小
        canvas_width = self.canvas.winfo_width()   
        canvas_height = self.canvas.winfo_height()

        # 仅当图像大小超过canvas大小时才记录鼠标位置
        # 图像在canvas范围内的时候，不用拖动
        if self.show_width > canvas_width or self.show_height > canvas_height:
            self.end_x = event.x
            self.end_y = event.y

        return 
        

    def mouse_dragging(self, event):
        if self.image_on_canvas is None:
            return
        
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        # 仅当图像大小超过canvas大小时才记录鼠标位置
        if self.show_width > canvas_width:
            x_diff = event.x - self.end_x
            # 使用canvas的xview_scroll和yview_scroll方法来移动内容
            self.canvas.xview_scroll(-x_diff, "units")
            self.end_x = event.x
        if self.show_height > canvas_height:
            y_diff = event.y - self.end_y
            self.canvas.yview_scroll(-y_diff, "units")    
            self.end_y = event.y

        return 


    def on_mouse_wheel(self, event):
        if not self.image_on_canvas:
            return
        
        #  检查Ctrl键是否按下
        if win32api.GetKeyState(win32con.VK_CONTROL) < 0:
            # Ctrl键按下，处理事件
            # print("Ctrl + 鼠标滚轮事件被触发")
            # Adjust the scale factor based on the OS and event details
            if event.num == 4 or event.delta > 0:  # For Linux or Windows/Mac scroll up
                # if self.img_info.hdr.lines*self.showing_scale > 4000 or \
                # self.img_info.hdr.samples*self.showing_scale > 4000 or \
                #     self.showing_scale >= 20:
                #     return
                scale_factor = 1.1
            elif event.num == 5 or event.delta < 0:  # For Linux or Windows/Mac scroll down
                # if self.img_info.hdr.lines*self.showing_scale < 100 or \
                # self.img_info.hdr.samples*self.showing_scale < 100:
                #     return
                scale_factor = 0.9
            else:
                return
            self.on_zoom(scale_factor=scale_factor)

    
    def on_zoom(self, scale_factor=1.1):
        
        cur_scale_factor = self.showing_scale*scale_factor
        if cur_scale_factor > 10 or cur_scale_factor<0.5:
            return

        # Resize the displayed image using the current displayed image
        self.showing_scale *= scale_factor
        self.show_width = int(self.showing_scale * self.image_width)
        self.show_height = int(self.showing_scale * self.image_height)
        
        self.load_image(self.current_index)
        self.show_truth()
        print(f"zoom sx: {self.show_width/self.image_width}; sy:{self.show_height/self.image_height}")
    
        return
    
   
    def update_browse_button_status(self):

        if self.current_index >= self.classnum-1:
            self.next_button.config(state='disabled')
            pass
        else:
            self.next_button.config(state='normal')
            pass

        if self.current_index <= 0:
            self.prev_button.config(state='disabled')
            pass
        else:
            self.prev_button.config(state='normal')
            pass

        return
    
    
    def prev_image(self):

        if self.current_index == 0:
            return
        
        self.current_index -= 1
        self.load_image(self.current_index)
        self.title_label['text'] = f"{ShapeManager.current_file_path} - {self.classname_list[self.current_index]} - {self.str_gain}"
        self.update_browse_button_status()
        return


    def next_image(self):

        if self.current_index == self.classnum - 1:
            return
        
        self.current_index += 1
        self.load_image(self.current_index)
        self.title_label['text'] = f"{ShapeManager.current_file_path} - {self.classname_list[self.current_index]} - {self.str_gain}"
        self.update_browse_button_status()
        return
    

    def on_browse_next_img(self, event):
        self.next_image()
        return
    
    def on_browse_prev_img(self, event):
        self.prev_image()
        return


if __name__ == "__main__":
    # Create the main window
    root = tk.Tk()
    root.title("Main Window")
    root.geometry("300x200")

    # Create a button to open the new window
    open_window_button = tk.Button(root, text="Open New Window", command=lambda: WindowShowSamDistanceImage(["abc"], np.zeros((2,3,4),dtype=np.uint8), root))
    open_window_button.pack(pady=20)

    # Run the main loop
    root.mainloop()