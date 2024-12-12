import tkinter as tk
from tkinter import filedialog, messagebox, Menu, Canvas, simpledialog, colorchooser
from tkinter import ttk, EventType, IntVar
from tkinter.scrolledtext import ScrolledText
from tkinter.font import Font
from PIL import Image, ImageTk, ExifTags
import numpy as np
import os
from Img_Functions import HDRInfo, ImgInfo,save_img
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from MyFigureCanvasToolbar import FigureCanvasNavigationToolbar
from MyToolBar import MyColorSelectorToolbar

import win32file, win32api, win32con     # pip install pywin32

from algos import (img_stretch, rgb_tuple_2_hexstr, read_tif, img_alignment, 
                   COLOR_CONF_LIST, mcolor_2_hexstr, sam_distance)
from window_create_model import WindowCreateModel
from window_show_img import WindowShowImage, WindowShowSamDistanceImage
from MyDialogs import DlgShowTable

from datetime import datetime
import copy

from MyDialogs import  FileListFilterDialog
from draw_utils import RoiType, ShapeType
from draw_utils import DrawingManager, ImgDataManager, ShapeManager

from MyScale import MyScale

from sam_model import SamModel, ClassInfo
from sam_dataset import SamDataset
from DlgProgress import PredictProgressDialog, PredictOneImgProgressDialog, Tifs2ImgProgressDialog

ToolBar_Res = {
    '打开图像文件': {
        'image_path': 'Res/images/view-image.png',
        'tips': '打开图像文件'
    },
    '打开文件夹': {
        'image_path': 'Res/images/openfolder.png',
        'tips': '打开图像文件夹'
    },
    '放大': {
        'image_path': 'Res/images/zoomin.png',
        'tips': '放大图像查看(Ctrl+鼠标上滚)'
    },
    '缩小': {
        'image_path': 'Res/images/zoomout.png',
        'tips': '缩小图像查看(Ctrl+鼠标下滚)'
    },
    '原始大小': {
        'image_path': 'Res/images/resize.png',
        'tips': '图像恢复原始大小查看'
    },
    'None': {
        'image_path': 'Res/images/folder_saved_search.png',
        'tips': '打开图像文件夹'
    }
}

class AutoLoadLabelType:
    LOAD_NON = 0
    LOAD_LABEL_TXT = 1
    LOAD_LABEL_JSON = 2
    LOAD_TRUTH_TXT = 3
    pass

class Tooltip:
    def __init__(self, widget:tk.Widget, text='tooltip'):
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.tipwindow = None

    def enter(self, event=None):
        x = y = 0
        x, y, cx, cy = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(1)
        tw.wm_geometry("+%d+%d" % (x, y))
        try:
            # For Mac OS
            tw.tk.call("::tk::unsupported::MacWindowStyle", "style", tw._w, "help", "normal")
        except tk.TclError:
            pass
        label = tk.Label(tw, text=self.text, background="#f9f9f9", relief=tk.SOLID, borderwidth=1,
                        font=("tahoma", "8", "normal"))
        label.pack(ipadx=1)

    def leave(self, event=None):
        if self.tipwindow:
            self.tipwindow.destroy()



def delete_all_children_recursively(parent:tk.Widget):
    for child in parent.winfo_children():
        # 如果子控件还有子控件，则递归调用
        if hasattr(child, 'winfo_children'):
            delete_all_children_recursively(child)
        # 删除子控件
        child.destroy()


class App:
    def __init__(self, root:tk.Tk):
        self.root = root
        self.root.title("光谱分析工具")
        # 绑定窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        # print(self.root.winfo_height(), self.root.winfo_width())  # 1,1 : 此时窗口还没有初始化
        # print(self.root.winfo_screenwidth(), self.root.winfo_screenheight()) # 屏幕大小

        self.init_menu()
        self.init_toolbar()
        self.init_ui()
        self.init_statusbar()

        self.current_file_path = None
        self.cur_file_selected_index = -1
        self.file_path_list = []          # img文件路径列表
        self.file_path_dict = {}          # 文件路径列表

        self.history_saving_dir = None
        self.history_open_dir = None

        self.sam_model = SamModel()
        self.model_ui_dict = {}
        self.class_checkbtn_enabled = {}

        self.dataset = SamDataset()
        self.dataset_ui_dict = {}

        self.wnd_create_model = None
        self.history_model_dir = None
        self.history_predict_dir = None

        self.arr_wb = None     # 白板数据
        self.arr_align_conf = None   # 对齐数据

        # tif 文件 合并 img文件
        self.tif_wv_list = [450,550,650,720,750,800,850]
        self.tif2img_filename_rule = "MAX_[nnnn]_Color_D.img"

        DrawingManager.init_canvas_figure(self.canvas, self.ax, self.x_scroll, self.y_scroll)
        DrawingManager.set_drawing_mode(RoiType.OP_HAND)

        self.set_ui_state_with_img()

        return
    

    def init_menu(self):

        # Menu
        menubar = Menu(self.root)
        filemenu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="文件", menu=filemenu)
        filemenu.add_command(label="打开图像文件", command=self.on_open_image)
        filemenu.add_command(label="打开文件夹", command=self.on_open_folder)
        filemenu.add_separator()
        filemenu.add_command(label="保存标注文件", command=self.on_save_label_file)        
        filemenu.add_command(label="加载标注文件", command=self.on_load_label_file)
        filemenu.add_separator()
        self.var_auto_save_label = tk.BooleanVar(value=False)
        filemenu.add_checkbutton(label="自动保存标注文件", variable=self.var_auto_save_label, onvalue=True, 
                                 offvalue=False, command=None)
        filemenu.add_separator()
        self.var_auto_load_label_type = tk.IntVar(value=AutoLoadLabelType.LOAD_LABEL_TXT)  
        filemenu.add_radiobutton(label="不自动加载标注文件", variable=self.var_auto_load_label_type, 
                                 value=AutoLoadLabelType.LOAD_NON, command=self.toggle_auto_load_label_type)
        filemenu.add_radiobutton(label="自动加载txt标注文件", 
                                            value=AutoLoadLabelType.LOAD_LABEL_TXT, 
                                            variable=self.var_auto_load_label_type, 
                                            command= self.toggle_auto_load_label_type)
        filemenu.add_radiobutton(label="自动加载json标注文件", 
                                            value=AutoLoadLabelType.LOAD_LABEL_JSON, 
                                            variable=self.var_auto_load_label_type, 
                                            command= self.toggle_auto_load_label_type)
        filemenu.add_radiobutton(label="自动加载真值文件", 
                                            value=AutoLoadLabelType.LOAD_TRUTH_TXT, 
                                            variable=self.var_auto_load_label_type, 
                                            command= self.toggle_auto_load_label_type)  
        filemenu.add_separator()
        filemenu.add_command(label="退出", command=self.on_closing)

        self.viewmenu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="视图", menu=self.viewmenu)
        self.viewmenu.add_command(label="放大", command=lambda:self.on_zoom(scale_type='zoomin'))
        self.viewmenu.add_command(label="缩小", command=lambda:self.on_zoom(scale_type='zoomout'))
        self.viewmenu.add_command(label="原始大小", command=lambda:self.on_zoom(scale_type='restore'))
        self.viewmenu.add_separator()
        # self.viewmenu.add_command(label="最值拉伸", command=self.display_maxmin_strech)
        self.scale_enabled = tk.BooleanVar(value=False)
        self.viewmenu.add_checkbutton(label="亮度调节", variable=self.scale_enabled, onvalue=True, 
                                 offvalue=False, command=self.toggle_scale_enabled)
        self.viewmenu.add_separator()
        self.viewmenu.add_command(label="查看波形大图", command=self.show_spectral_figure)
        self.viewmenu.add_separator()
        self.var_split_canvas = tk.BooleanVar(value=False)
        self.viewmenu.add_checkbutton(label="切分窗口", variable=self.var_split_canvas, onvalue=True, 
                                 offvalue=False, command=self.toggle_split_canvas)


        self.opmenu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="ROI操作", menu=self.opmenu)
        # self.opmenu.add_command(label="显示全部点谱线", command=self.show_img_all_points_wave)
        # self.opmenu.add_separator()
        self.op_selection = tk.StringVar(value=RoiType.OP_HAND)
        self.opmenu.add_radiobutton(label="移动工具", 
                                            value=RoiType.OP_HAND, variable=self.op_selection, 
                                            command= self.on_operation_select)
        self.opmenu.add_separator()
        self.opmenu.add_radiobutton(label="绘制点样本", 
                                            value=RoiType.OP_SAMPLE_POINT, 
                                            variable=self.op_selection, 
                                            command= self.on_operation_select)
        self.opmenu.add_radiobutton(label="绘制矩形样本", 
                                            value=RoiType.OP_SAMPLE_RECT, 
                                            variable=self.op_selection, 
                                            command= self.on_operation_select)
        self.opmenu.add_radiobutton(label="绘制多边形样本", 
                                            value=RoiType.OP_SAMPLE_POLYGON, 
                                            variable=self.op_selection, 
                                            command= self.on_operation_select)
        self.opmenu.add_separator()
        self.opmenu.add_radiobutton(label="绘制点标签", 
                                value=RoiType.OP_ROI_POINT, 
                                variable=self.op_selection, 
                                command= self.on_operation_select)
        self.opmenu.add_radiobutton(label="绘制矩形标签", 
                                            value=RoiType.OP_ROI_RECT, 
                                            variable=self.op_selection, 
                                            command= self.on_operation_select)
        self.opmenu.add_radiobutton(label="绘制多边形标签", 
                                            value=RoiType.OP_ROI_POLYGON, 
                                            variable=self.op_selection, 
                                            command= self.on_operation_select)
        # self.opmenu.add_separator()
        # self.opmenu.add_radiobutton(label="矩形真值", 
        #                             value=RoiType.OP_TRUTH_RECT, 
        #                             variable=self.op_selection, 
        #                             command= self.on_operation_select)
        self.opmenu.add_separator()
        self.opmenu.add_radiobutton(label="截图保存", 
                                        value=RoiType.OP_CLIP_RECT, 
                                        variable=self.op_selection, 
                                        command= self.on_operation_select)
        self.opmenu.add_separator()
        self.opmenu.add_radiobutton(label="绘制自动ROI有效范围", value=RoiType.OP_AUTO_ROI_REGION, variable=self.op_selection, command= self.on_operation_select)
        self.opmenu.add_command(label="清除自动ROI有效范围", command=self.on_clear_auto_roi_region)
        

        self.autolabel_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="自动标注", menu=self.autolabel_menu)
        self.autolabel_menu.add_command(label="自动生成ROI", command=self.on_auto_roi)
        self.autolabel_menu.add_command(label="创建多边形标签", command=self.on_auto_label_polygon)        
        self.autolabel_menu.add_command(label="清除自动ROI", command=self.on_clear_auto_roi)
        # self.autolabel_menu.add_separator()
        # self.autolabel_menu.add_command(label="生成点标签", command=self.on_auto_label_point)
        self.autolabel_menu.add_separator()
        self.autolabel_menu.add_command(label="保存为真值配置文件", command=self.on_save_auto_label_to_truth)
        self.autolabel_menu.add_command(label="保存为数据集", command=self.on_save_auto_label_to_ds)
        self.autolabel_menu.add_separator()
        self.var_show_mask = tk.BooleanVar(value=True)
        self.autolabel_menu.add_checkbutton(label="显示标签图层", variable=self.var_show_mask, onvalue=True, 
                                 offvalue=False, command=self.toggle_show_mask)
        

        dataset_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="数据集", menu=dataset_menu)
        dataset_menu.add_command(label="加载数据集", command=self.on_load_ds_from_dir)   
        # dataset_menu.add_command(label="清除数据集", command=self.on_clear_dataset)     
        dataset_menu.add_separator()
        dataset_menu.add_command(label="当前文件标签保存到数据集", command=self.on_create_dataset_from_current_labels_points)
        dataset_menu.add_command(label="列表文件标签创建数据集", command=self.on_create_dataset_from_filelist)
        # dataset_menu.add_command(label="加载数据集", command=self.on_load_dataset)


        modelmenu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="模型", menu=modelmenu)
        modelmenu.add_command(label="加载模型", command=self.on_load_model)
        modelmenu.add_command(label="查看模型", command=self.show_model_info)    
        modelmenu.add_command(label="清除模型", command=self.on_clear_model)
        # modelmenu.add_command(label="读取参数", command=self.on_read_oil_params)
        modelmenu.add_separator()
        modelmenu.add_command(label="推理当前图片", command=self.on_detect_current_image)
        modelmenu.add_command(label="推理列表文件", command=self.on_detect_image_list)
        modelmenu.add_command(label="推理文件夹...", command=self.on_detect_image_dir)
        modelmenu.add_command(label="推理文件...", command=self.on_detect_image_file)
        self.var_use_default_model_params = tk.BooleanVar()
        self.var_use_default_model_params.set(False)
        modelmenu.add_checkbutton(label="使用模型文件参数推理", variable=self.var_use_default_model_params, onvalue=True, 
                                 offvalue=False, command=None)
        modelmenu.add_separator()
        modelmenu.add_command(label="重置为模型文件参数", command=self.reset_default_model_params)
        modelmenu.add_command(label="保存到模型文件", command=self.save_as_model_params)

        # 创建设置菜单
        toolmenu = Menu(menubar, tearoff=0)
        toolmenu.add_command(label="读取白板文件信息", command=self.read_whiteboard)
        toolmenu.add_separator()
        self.var_auto_align = tk.BooleanVar(value=False)
        toolmenu.add_checkbutton(label="启用自动对齐", variable=self.var_auto_align, onvalue=True, 
                                 offvalue=False, command=self.toggle_auto_align)
        toolmenu.add_command(label="读取对齐文件", command=self.read_alignment_conf)
        toolmenu.add_command(label="对齐img", command=lambda:self.on_align_current_img())
        toolmenu.add_command(label="对齐img另存为...", command=self.on_save_current_align_img)
        toolmenu.add_command(label="取消对齐img", command=lambda:self.on_align_current_img(False))
        toolmenu.add_separator()
        toolmenu.add_command(label="设置tif合并img规则", command=self.set_tifs2img_rules)
        toolmenu.add_command(label="tif合并img", command=self.on_tifs2img)
        toolmenu.add_separator()
        self.var_gain_enabled = tk.BooleanVar(value=False)
        toolmenu.add_checkbutton(label="去曝光增益", variable=self.var_gain_enabled, onvalue=True, 
                                 offvalue=False, command=self.toggle_gain_expo_time)
        toolmenu.add_command(label="保存样本点波段数值到文件", command=self.on_save_samples_wave)
        toolmenu.add_command(label="保存样本信息到文件", command=self.on_save_samples_info_to_json)
        toolmenu.add_command(label="载入样本信息文件", command=self.on_load_samples_info_from_json)
        menubar.add_cascade(label="工具", menu=toolmenu)


        # 创建about菜单
        aboutmenu = Menu(menubar, tearoff=0)
        aboutmenu.add_command(label="选项", command=self.help)
        aboutmenu.add_command(label="帮助", command=self.help)
        menubar.add_cascade(label="关于", menu=aboutmenu)


        self.root.config(menu=menubar)  # OR： self.root['menu'] = menubar

        return


    def init_ui(self):

        self.paned_window = ttk.PanedWindow(self.root, orient="horizontal")
        self.paned_window.pack(side='top', fill="both", expand=True, padx=5, pady=5)

        # ----- Left frame -----
        self.left_frame = ttk.PanedWindow(self.paned_window, orient="vertical")
        self.paned_window.add(self.left_frame, weight=2)

        self.file_frame = ttk.Frame(self.left_frame, relief='groove', borderwidth=2, width=50)
        self.left_frame.add(self.file_frame, weight=5)
        # self.file_frame.pack(side="top", fill="both", expand=1)  # 这里不用pack，添加到PanedWindow中的控件的布局是由PanedWindow管理的

        # 文件列表
        self.img_list_label = tk.Label(self.file_frame, text="文件列表")
        self.img_list_label.pack(side="top", anchor=tk.NW)
        frame_image_list = ttk.Frame(self.file_frame)
        frame_image_list.pack(side="top",expand=1, fill='both')
        self.image_listbox = tk.Listbox(frame_image_list, selectmode=tk.SINGLE, exportselection=False)
        self.image_listbox.pack(side="left", fill="both", expand=1)
        self.image_listbox.bind('<<ListboxSelect>>', self.on_file_select)
        self.image_list_menubar = Menu(self.image_listbox,tearoff=False)
        self.image_list_menubar.add_command(label = '删除选中文件', command=self.remove_file)
        self.image_list_menubar.add_command(label = '删除全部文件', command=self.remove_all_files)
        self.image_list_menubar.add_command(label = '过滤文件', command=self.filelist_filter)
        self.image_list_menubar.add_command(label = '保存文件列表', command=self.save_file_list)
        self.image_list_menubar.add_command(label = '加载文件列表', command=self.load_file_list)
        self.image_listbox.bind("<Button-3>", self.image_listbox_menu) 
        # 滚动条设置
        scrollbar_filelist = tk.Scrollbar(frame_image_list, command=self.image_listbox.yview)
        scrollbar_filelist.pack(side=tk.RIGHT, fill=tk.Y)
        self.image_listbox.configure(yscrollcommand=scrollbar_filelist.set)
        # 设置悬停提示事件
        self.img_list_hover_tip = None
        self.image_listbox.bind("<Motion>", self.show_or_move_image_list_hover_tip)
        self.image_listbox.bind("<Leave>", self.hide_image_list_hover_tip)
        self.image_listbox.bind('<Up>', self.image_listbox_moveup)
        self.image_listbox.bind('<Down>', self.image_listbox_movedown)

        # 标签名称 
        label_name_frame = ttk.Frame(self.left_frame)
        self.left_frame.add(label_name_frame, weight=1)

        lb_0 = tk.Label(label_name_frame, text="标签列表")
        lb_0.pack(side="top", anchor=tk.NW)
        frame_label_list = ttk.Frame(label_name_frame)
        frame_label_list.pack(side="top", expand=1, fill='both')
        self.label_name_listbox = tk.Listbox(frame_label_list, selectmode=tk.SINGLE, exportselection=False, height=5)
        self.label_name_listbox.pack(side="left", fill="both", expand=1)
        # 滚动条设置
        scrollbar_label_name_listbox = tk.Scrollbar(frame_label_list, command=self.label_name_listbox.yview)
        scrollbar_label_name_listbox.pack(side=tk.RIGHT, fill=tk.Y)
        self.label_name_listbox.configure(yscrollcommand=scrollbar_label_name_listbox.set)

        # self.label_name_listbox.bind("<Button-1>", self.on_labelname_listbox_click)
        self.label_name_listbox.bind('<<ListboxSelect>>', self.on_label_name_listbox_selected)
        self.label_name_list_menubar = Menu(self.label_name_listbox,tearoff=False)
        self.label_name_list_menubar.add_command(label = '新建标签名', command=self.label_name_listbox_add_item)
        self.label_name_list_menubar.add_command(label = '编辑标签名', command=self.edit_label_name)
        self.label_name_list_menubar.add_command(label = '删除标签名', command=self.remove_label_name)
        self.label_name_list_menubar.add_command(label = '删除全部标签名', command=self.remove_all_label_name)
        self.label_name_listbox.bind("<Button-3>", self.show_label_name_list_menubar) 
        # self.label_name_listbox.insert(tk.END, "0")

        # 标签面板
        self.roi_notebook = ttk.Notebook(self.left_frame)
        self.left_frame.add(self.roi_notebook, weight=4)
        # 创建多个frame作为每个tab的内容
        frame1 = ttk.Frame(self.roi_notebook)
        # frame2 = ttk.Frame(self.roi_notebook)
        frame2 = ttk.Frame(self.roi_notebook)
        # 向notebook中添加tab
        self.roi_notebook.add(frame1, text='标注列表')
        # self.roi_notebook.add(frame2, text=' 点 ')
        self.roi_notebook.add(frame2, text='图层列表')
        # notebook.pack(expand=True, fill="both") # 这里千万不能pack，否则会导致filelist frame被遮挡
        # 换句话说，添加到PanedWindow中的控件的布局是由PanedWindow管理的
        self.roi_notebook.select(0)

        # 标注列表
        self.label_listbox = tk.Listbox(frame1, selectmode=tk.SINGLE, exportselection=False)
        self.label_listbox.pack(side="left", fill="both", expand=True)
        self.label_listbox.bind('<<ListboxSelect>>', self.on_label_select)
        self.label_listbox.bind("<Button-3>", self.label_list_menu) 
        self.label_list_menubar = Menu(self.label_listbox,tearoff=False)
        scrollbar_label_listbox = tk.Scrollbar(frame1, command=self.label_listbox.yview)
        scrollbar_label_listbox.pack(side=tk.RIGHT, fill=tk.Y)
        self.label_listbox.configure(yscrollcommand=scrollbar_label_listbox.set)

        # 真值列表
        # self.truth_listbox = tk.Listbox(frame2, selectmode=tk.SINGLE, exportselection=False)
        # self.truth_listbox.pack(side="left", fill="both", expand=True)
        # self.truth_listbox.bind('<<ListboxSelect>>', self.on_truth_select)
        # self.truth_listbox.bind("<Button-3>", self.truth_list_menu) 
        # self.truth_list_menubar = Menu(self.truth_listbox,tearoff=False)
        # scrollbar_truth_listbox = tk.Scrollbar(frame2, command=self.truth_listbox.yview)
        # scrollbar_truth_listbox.pack(side=tk.RIGHT, fill=tk.Y)
        # self.truth_listbox.configure(yscrollcommand=scrollbar_truth_listbox.set)

        # #########################
        # --- Center Frame ----
        # #########################

        w = int(self.root.winfo_screenwidth()*0.6)
        self.center_panedwindows = ttk.PanedWindow(self.paned_window, orient="horizontal")
        self.paned_window.add(self.center_panedwindows, weight=5)
        self.center_frame = ttk.Frame(self.center_panedwindows, relief='groove', borderwidth=0, width=w)
        self.center_panedwindows.add(self.center_frame, weight=5)
        # self.center_frame.pack(side="left", fill="both", expand=1)

        self.canvas = Canvas(self.center_frame, cursor="cross", bd=0, width=w)
        # self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_clicked)
        self.canvas.bind("<B1-Motion>", self.on_mouse_dragging)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_released)
        self.canvas.bind("<Double-Button-1>", self.on_mouse_double_clicked)
        self.canvas.bind("<Button-3>", self.on_mouse_right_clicked)
        self.canvas.bind("<Motion>", self.on_mouse_move)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)

        # Create scrollbars
        self.x_scroll = tk.Scrollbar(self.center_frame, orient="horizontal", command=self.canvas.xview)
        self.y_scroll = tk.Scrollbar(self.center_frame, orient="vertical", command=self.canvas.yview)

        # Configure the canvas to be scrollable
        self.canvas.configure(yscrollcommand=self.y_scroll.set, xscrollcommand=self.x_scroll.set)

        # # Position the scrollbars relative to the canvas
        self.center_frame.grid_rowconfigure(0, weight=1)
        self.center_frame.grid_columnconfigure(0, weight=1)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.x_scroll.grid(row=1, column=0, sticky="ew")
        self.y_scroll.grid(row=0, column=1, sticky="ns")

        # #########################
        # ---- Right Frame -------
        # #########################

        self.right_frame = ttk.PanedWindow(self.paned_window, orient="vertical")
        # self.right_frame = ttk.Frame(self.paned_window, width=150, relief='groove', borderwidth=2)
        self.paned_window.add(self.right_frame, weight=3)

         # 标签面板（matplot，info）
        self.info_notebook = ttk.Notebook(self.right_frame)
        self.right_frame.add(self.info_notebook, weight=2)

        self.frame_spectral_figure = tk.Frame(self.info_notebook) 
        self.info_notebook.add(self.frame_spectral_figure, text=' 波形图 ')

        model_info_tab = tk.Frame(self.info_notebook) 
        self.info_notebook.add(model_info_tab, text='模型信息')

        self.panel_model_info = tk.Frame(model_info_tab, bd=1) 
        self.panel_model_info.pack(side='top', expand=1, fill='both')
        lb_class = tk.Label(self.panel_model_info, text="类名", width=10)
        lb_thres = tk.Label(self.panel_model_info, text="门限", width=10)
        lb_superclass = tk.Label(self.panel_model_info, text="超类", width=10)
        lb_cluster = tk.Label(self.panel_model_info, text="簇数量", width=10)
        lb_enable = tk.Label(self.panel_model_info, text="启用", width=10)
        lb_class.grid(row=0, column=0, padx=2)
        lb_thres.grid(row=0, column=1, padx=2)
        lb_superclass.grid(row=0, column=2, padx=2)
        lb_cluster.grid(row=0, column=3, padx=2)
        lb_enable.grid(row=0, column=4, padx=2)
        model_info_options = tk.Frame(model_info_tab, bd=1) 
        model_info_options.pack(side='top', expand=1, fill='both')
        self.var_amp_check = tk.BooleanVar(value=True)
        checkbox = ttk.Checkbutton(model_info_options, text='光强过滤', command=None,
                variable=self.var_amp_check, onvalue=True, offvalue=False)
        self.var_amp_thres = tk.DoubleVar(value=0.07)
        entry_amp = tk.Entry(model_info_options, textvariable=self.var_amp_thres, width=5)
        scale_amp = tk.Scale(model_info_options, from_=0.01, to=0.5, orient="horizontal", 
                            variable=self.var_amp_thres,showvalue=0,
                          command=None, resolution=0.01, troughcolor="lightgray")
        self.var_enable_cache = tk.BooleanVar(value=True)
        checkbox_1 = ttk.Checkbutton(model_info_options, text='开启多帧推理', command=self.toggle_cache_enabled,
                variable=self.var_enable_cache, onvalue=True, offvalue=False)
        lb_cache_cols = tk.Label(model_info_options, text="缓存列数", width=12)
        self.var_cache_cols = tk.DoubleVar(value=3)
        entry_cache_cols = tk.Entry(model_info_options, textvariable=self.var_cache_cols, width=5)
        lb_cache_pixs = tk.Label(model_info_options, text="像素数量门限", width=16)
        self.var_cache_pixs = tk.DoubleVar(value=3)
        entry_cache_pixs = tk.Entry(model_info_options, textvariable=self.var_cache_pixs, width=5)
        checkbox.grid(row=0, column=0, padx=2, sticky="W")
        entry_amp.grid(row=0, column=1, padx=2, sticky="W")
        scale_amp.grid(row=0, column=2, columnspan=4, padx=2, sticky='EW')
        checkbox_1.grid(row=1, column=0, padx=2, sticky="W")
        lb_cache_cols.grid(row=1, column=1, padx=2, sticky="W")
        entry_cache_cols.grid(row=1, column=2, padx=2, sticky="W")
        lb_cache_pixs.grid(row=1, column=3, padx=2, sticky="W")
        entry_cache_pixs.grid(row=1, column=4, padx=2, sticky="W")
        model_info_options.columnconfigure(0, weight=0)
        model_info_options.columnconfigure(1, weight=0)
        model_info_options.columnconfigure(2, weight=0)   
        model_info_options.columnconfigure(3, weight=0)
        model_info_options.columnconfigure(4, weight=0)
        model_info_options.columnconfigure(5, weight=1)     # Scale控件水平扩展到最大

        # self.dataset_info_tab = tk.Frame(self.info_notebook, bd=1) 
        # self.info_notebook.add(self.dataset_info_tab, text='数据集信息')
        # lb_class = tk.Label(self.dataset_info_tab, text="类名")
        # lb_samples = tk.Label(self.dataset_info_tab, text="样本数量")
        # lb_class.grid(row=0, column=0)
        # lb_samples.grid(row=0, column=1)

        color_value = '#%02x%02x%02x' % (220, 20, 60)
        self.info_text_widget = ScrolledText(self.info_notebook, relief='flat', foreground=color_value,
                                             font=Font(family="Helvetica", size=14, weight="bold"))
        self.info_notebook.add(self.info_text_widget, text=' 信息 ')

        self.info_notebook.select(0)

        self.op_notebook = ttk.Notebook(self.right_frame)
        self.right_frame.add(self.op_notebook, weight=2)

        self.scale_panel = tk.Frame(self.op_notebook)
        self.op_notebook.add(self.scale_panel, text='亮度调节')
        # self.scale_panel.pack(side="top", fill="x", expand=1)
        self.my_scale = MyScale(self.scale_panel)
        self.root.bind("<<IMGStretchEvent>>", self.on_img_stretch)

        self.auto_roi_panel = tk.Frame(self.op_notebook)
        self.op_notebook.add(self.auto_roi_panel, text='自动ROI操作')

        label_gray_thres = tk.Label(self.auto_roi_panel, text="灰度阈值(20,220):", width=16,
                                    anchor="w", justify="left")
        self.var_gray_thres = IntVar(value=50) 
        self.entry_gray_thres = tk.Entry(self.auto_roi_panel, textvariable=self.var_gray_thres, width=3)
        self.scale_gray_thres = tk.Scale(self.auto_roi_panel, from_=20, to=220, orient="horizontal", 
                            variable=self.var_gray_thres,showvalue=0,
                          command=self.on_gray_thres_changed, resolution=1, troughcolor="lightgray")
        label_gray_thres.grid(row=0, column=0, padx=2)
        self.entry_gray_thres.grid(row=0, column=1, padx=5)
        self.scale_gray_thres.grid(row=0, column=2, padx=5, sticky='EW')

        label_transparency = tk.Label(self.auto_roi_panel, text="透明度(0,100):", width=16,
                                      anchor="w", justify="left")
        self.var_transparency = IntVar(value=50) 
        self.entry_transparency = tk.Entry(self.auto_roi_panel, textvariable=self.var_transparency, width=3)
        self.scale_transparency = tk.Scale(self.auto_roi_panel, from_=0, to=100, orient="horizontal", 
                            variable=self.var_transparency,showvalue=0,
                          command=None, resolution=1, troughcolor="lightgray")
        label_transparency.grid(row=1, column=0, padx=2)
        self.entry_transparency.grid(row=1, column=1, padx=5)
        self.scale_transparency.grid(row=1, column=2, padx=5, sticky='EW')

        label_erosion = tk.Label(self.auto_roi_panel, text="腐蚀(1,5):", width=16,
                                 anchor="w", justify="left")
        self.var_erosion = IntVar(value=1) 
        self.entry_erosion = tk.Entry(self.auto_roi_panel, textvariable=self.var_erosion, width=3)
        label_erosion.grid(row=2, column=0, padx=2)
        self.entry_erosion.grid(row=2, column=1, padx=5)

        btn_auto_roi = ttk.Button(self.auto_roi_panel, text="自动ROI", command=self.on_auto_roi)
        btn_auto_roi.grid(row=3, column=0, sticky='EW')

        self.auto_roi_panel.columnconfigure(0, weight=0)
        self.auto_roi_panel.columnconfigure(1, weight=0)
        self.auto_roi_panel.columnconfigure(2, weight=1)

        self.data_transform_panel = tk.Frame(self.op_notebook)
        self.op_notebook.add(self.data_transform_panel, text='wave数据处理')
        self.var_trans_binning_enabled = tk.BooleanVar(value=False)
        checkbox_binning = ttk.Checkbutton(self.data_transform_panel, text='波段聚合', command=self.on_trans_binning,
                variable=self.var_trans_binning_enabled, onvalue=True, offvalue=False)
        self.var_trans_binning_value = tk.IntVar(value=10)
        entry_binning = tk.Entry(self.data_transform_panel, textvariable=self.var_trans_binning_value, width=3)
        lb1 = tk.Label(self.data_transform_panel, text="起始波段：")
        self.combo_start_wv = ttk.Combobox(self.data_transform_panel, width=10)
        self.combo_start_wv.bind("<<ComboboxSelected>>", self.on_set_start_wv)
        self.combo_start_wv.configure(state='readonly')
        lb2 = tk.Label(self.data_transform_panel, text="终止波段：")
        self.combo_end_wv = ttk.Combobox(self.data_transform_panel, width=10)
        self.combo_end_wv.bind("<<ComboboxSelected>>", self.on_set_end_wv)
        self.combo_end_wv.configure(state='readonly')
        checkbox_binning.grid(row=0, column=0, padx=2, sticky="W")
        entry_binning.grid(row=0, column=1, padx=2, sticky="E")
        lb1.grid(row=0, column=2, padx=2, sticky='EW')
        self.combo_start_wv.grid(row=0, column=3, padx=2, sticky="EW")
        lb2.grid(row=0, column=4, padx=2, sticky="W")
        self.combo_end_wv.grid(row=0, column=5, padx=2, sticky="EW")
        self.var_trans_norm = tk.BooleanVar(value=False)
        checkbox_norm = ttk.Checkbutton(self.data_transform_panel, text='归一化', command=None,
                variable=self.var_trans_norm, onvalue=True, offvalue=False)
        checkbox_norm.grid(row=1, column=0, padx=2, sticky="W")
        lb3 = tk.Label(self.data_transform_panel, text="数据变换：")
        self.combo_transform = ttk.Combobox(self.data_transform_panel, width=12)
        self.combo_transform['values'] = ['无', '一阶导', '二阶导']
        self.combo_transform.configure(state='readonly')
        self.combo_transform.current(0)
        self.combo_transform.bind("<<ComboboxSelected>>", self.on_transform_select)
        lb3.grid(row=1, column=2, padx=2, sticky='EW')
        self.combo_transform.grid(row=1, column=3, padx=2, sticky="EW")
        
        # self.data_transform_panel.columnconfigure(0, weight=0)
        # self.data_transform_panel.columnconfigure(1, weight=0)
        # self.data_transform_panel.columnconfigure(2, weight=0)   
        # self.data_transform_panel.columnconfigure(3, weight=0)

        self.op_notebook.select(0)

        ##### 波段列表
        self.spectral_notebook = ttk.Notebook(self.right_frame)
        self.right_frame.add(self.spectral_notebook, weight=4)
        frame_spectral = ttk.Frame(self.spectral_notebook)
        self.spectral_notebook.add(frame_spectral, text='波段列表')
        # tk.Label(self.right_frame, text="Spectral List:").pack(side="top", fill="x")
        self.spectral_listbox = tk.Listbox(frame_spectral, selectmode=tk.SINGLE, bd=2, exportselection=False)
        self.spectral_listbox.pack(side="left", fill="both", expand=1)
        scrollbar_spectral_listbox = tk.Scrollbar(frame_spectral, command=self.spectral_listbox.yview)
        scrollbar_spectral_listbox.pack(side=tk.RIGHT, fill=tk.Y)
        self.spectral_listbox.configure(yscrollcommand=scrollbar_spectral_listbox.set)
        self.spectral_listbox.bind('<<ListboxSelect>>', self.on_wave_select)
        self.spectral_listbox.bind("<Button-3>", self.spectral_list_menu) 
        self.spectral_list_menubar = Menu(self.spectral_listbox,tearoff=False)
        self.spectral_list_menubar.add_command(label = '设置为起点波段', command=lambda:self.set_wv_range(True))
        self.spectral_list_menubar.add_command(label = '设置为终点波段', command=lambda:self.set_wv_range(False))
        self.spectral_list_menubar.add_command(label = '启用波段', command=lambda:self.set_wv_status(True))
        self.spectral_list_menubar.add_command(label = '禁用波段', command=lambda:self.set_wv_status(False))

        # 分析采样点列表
        frame_sampleslist = ttk.Frame(self.spectral_notebook)
        self.spectral_notebook.add(frame_sampleslist, text='样本点列表')
        self.samples_listbox = tk.Listbox(frame_sampleslist, selectmode=tk.MULTIPLE, exportselection=False)
        self.samples_listbox.pack(side="left", fill="both", expand=True)
        self.samples_listbox.bind('<<ListboxSelect>>', self.on_sample_select)
        self.samples_listbox.bind("<Button-3>", self.sample_list_menu) 
        scrollbar_samples_listbox = tk.Scrollbar(frame_sampleslist, command=self.samples_listbox.yview)
        scrollbar_samples_listbox.pack(side=tk.RIGHT, fill=tk.Y)
        self.samples_listbox.configure(yscrollcommand=scrollbar_samples_listbox.set)

        # 使用matplotlib创建一个简单的图表
        self.fig, self.ax = plt.subplots(figsize=(5, 4))


       
        # 将这个图表绘制到Tk的canvas上
        self.fig_canvas = FigureCanvasTkAgg(self.fig, self.frame_spectral_figure)
        self.fig_canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)
        # Add navigation toolbar
        frame_toolbar = tk.Frame(self.frame_spectral_figure)
        frame_toolbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.nav_toolbar = FigureCanvasNavigationToolbar(self.fig_canvas,  frame_toolbar, pack_toolbar=False)
        self.nav_toolbar.pack(side=tk.LEFT, fill=tk.X, padx=5)
        self.color_toolbar = MyColorSelectorToolbar(frame_toolbar)
        self.color_toolbar.pack(side=tk.RIGHT, fill=tk.X, padx=5)

        # self.cid_list.append(self.fig_canvas.mpl_connect("motion_notify_event", self.fig_hover))
        # self.cid_list.append(self.fig_canvas.mpl_connect("button_press_event", self.fig_mouse_click))
        self.fig_canvas.mpl_connect('pick_event', self.fig_on_pick)

        self.fig_max_window = None
    
        return


    def create_button(self, parent, text, command_function):

        res = ToolBar_Res.get(text, None)
        tip_info = text
        if res:
            img_path = res.get('image_path', "")
            tip_info = res.get('tips', text)
            if len(img_path)>0 and os.path.exists(img_path):
                image = Image.open(img_path)
                if image:
                    image = image.resize((24,24))
                    icon = ImageTk.PhotoImage(image)
                    btn = tk.Button(parent, image=icon, text=text, command=command_function)
                    btn.image = icon
                    self.toolbar_tip = Tooltip(btn, text=tip_info)
                    return btn
                
        button = tk.Button(parent, text=text, command=command_function)
        self.toolbar_tip = Tooltip(button, text=tip_info)
        return button
    

    def init_toolbar(self):

        # Toolbar
        toolbar = tk.Frame(self.root, bd=1, relief='groove', borderwidth=1, bg='lightgray')
        toolbar.pack(side="top", fill="x")

        frame1 = ttk.Frame(toolbar)
        frame1.pack(side='left', padx=2)
        frame2 = ttk.Frame(toolbar)
        frame2.pack(side='left', padx=2)
        
        open_btn = self.create_button(frame1, text="打开图像文件", command_function=self.on_open_image)
        open_btn.pack(side="left", padx=2, pady=2)
        open_dir_btn = self.create_button(frame1, text="打开文件夹", command_function=self.on_open_folder)
        open_dir_btn.pack(side="left", padx=2, pady=2)        

        zoomin_btn = self.create_button(frame2, text="放大", command_function=lambda:self.on_zoom(scale_type='zoomin'))
        zoomin_btn.pack(side="left", padx=2, pady=2)
        zoomout_btn = self.create_button(frame2, text="缩小", command_function=lambda:self.on_zoom(scale_type='zoomout'))
        zoomout_btn.pack(side="left", padx=2, pady=2)
        zoom_btn = self.create_button(frame2, text="原始大小", command_function=lambda:self.on_zoom(scale_type='restore'))
        zoom_btn.pack(side="left", padx=2, pady=2)
        
        pass


    def init_statusbar(self):
        # Status bar
        statusbar = ttk.Frame(self.root, relief='groove')
        statusbar.pack(side="bottom", fill="x")
        self.status_labels = []
        sections=5
        for _ in range(sections):
            label = tk.Label(statusbar, text="", bd=1, relief='sunken', anchor='w')
            label.pack(side='left', fill='x', expand=True)
            self.status_labels.append(label)     
        pass


    def statusbar_set_filepath(self):
        self.status_labels[0].config(text=f"{self.current_file_path}")


    def statusbar_set_image_size(self):
        
        self.status_labels[1].config(text=f"图像大小: {DrawingManager.show_width}x{DrawingManager.show_width}  " 
                                     f"显示比例：{DrawingManager.showing_scale}%")

    
    def statusbar_set_position(self, x=-1, y=-1):
        if x>=0 and y>=0:
            self.status_labels[2].config(text=f"位置: x={x}, y={y}")
        else:
            self.status_labels[2].config(text="")

    
    def statusbar_set_tip(self, tip:str=""):
        self.status_labels[3].config(text=tip)
        return

    def statusbar_set_info(self, info:str):
        self.status_labels[4].config(text=info)
        return
    

    def statusbar_clear(self):
        for i in range(len(self.status_labels)):
            self.status_labels[i].config(text="")



    def redraw_fig_canvas(self):

        self.fig_canvas.draw_idle()

        if self.fig_max_window is not None:
            self.fig_canvas_max.draw_idle()
        return
    

    def show_spectral_figure(self):

        if self.fig_max_window is not None:
            return
        
        # self.dpi = self.fig.get_dpi()
        self.fig_w_inch, self.fig_h_inch = self.fig.get_size_inches()
        
        # 创建一个新的 Toplevel 窗口
        self.fig_max_window = tk.Toplevel()
        self.fig_max_window.title("Maximized Figure")
        self.fig_max_window.protocol("WM_DELETE_WINDOW", self.on_fig_max_wnd_closing)
        
        # 设置窗口最大化
        self.fig_max_window.state('zoomed')

        self.fig_canvas_max = FigureCanvasTkAgg(self.fig, self.fig_max_window)
        self.fig_canvas_max.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)
        self.nav_toolbar_max = FigureCanvasNavigationToolbar(self.fig_canvas_max,  self.fig_max_window, pack_toolbar=False)
        self.nav_toolbar_max.pack(side=tk.BOTTOM, fill=tk.X)

        self.fig_canvas_max.draw()

        return
    

    def toggle_split_canvas(self):

        if self.var_split_canvas.get():

            self.center_frame_extra = ttk.Frame(self.center_panedwindows, relief='sunken', borderwidth=0, width=100)
            self.center_panedwindows.add(self.center_frame_extra, weight=5)

            self.canvas_extra = Canvas(self.center_frame_extra, cursor="cross", bd=0, width=100)
            self.canvas_extra.bind("<ButtonPress-1>", self.on_mouse_clicked)
            self.canvas_extra.bind("<B1-Motion>", self.on_mouse_dragging)
            self.canvas_extra.bind("<Motion>", self.on_mouse_move)
            self.canvas_extra.bind("<MouseWheel>", self.on_mouse_wheel)
            self.x_scroll_extra = tk.Scrollbar(self.center_frame_extra, orient="horizontal", command=self.canvas_extra.xview)
            self.y_scroll_extra = tk.Scrollbar(self.center_frame_extra, orient="vertical", command=self.canvas_extra.yview)
            self.canvas_extra.configure(yscrollcommand=self.y_scroll_extra.set, xscrollcommand=self.x_scroll_extra.set)

            self.center_frame_extra.grid_rowconfigure(0, weight=1)
            self.center_frame_extra.grid_columnconfigure(0, weight=1)
            self.canvas_extra.grid(row=0, column=0, sticky="nsew")
            self.x_scroll_extra.grid(row=1, column=0, sticky="ew")
            self.y_scroll_extra.grid(row=0, column=1, sticky="ns")
            pass
        else:
            self.center_panedwindows.remove(self.center_frame_extra)
            delete_all_children_recursively(self.center_frame_extra)
            self.center_frame_extra.destroy()
            pass

        return
    

    def on_fig_max_wnd_closing(self):

        # delete_all_children_recursively(self.fig_max_window)

        # for widget in self.fig_max_window.winfo_children():
        #     # 删除子控件
        #     widget.destroy()
        
        self.nav_toolbar_max.destroy()
        self.fig_canvas_max.get_tk_widget().destroy()
        del self.fig_canvas_max
        del self.nav_toolbar_max

        self.fig_max_window.destroy()
        self.fig_max_window = None

        self.fig.set_size_inches(self.fig_w_inch, self.fig_h_inch)
        self.fig_canvas.draw_idle()
        
        return


    def fig_hover(self, event):
        '''
        鼠标在fig上移动时，在FigureCanvasNavigationToolbar右侧的message label上显示鼠标位置
        注意：如果不执行set_message，则会交由FigureCanvasNavigationToolbar进行默认处理，即：
        在message label上显示鼠标位置（而这个位置坐标时根据x,y limit的设置得到的，往往不是真实的数据坐标）
        因此，当条件不满足的时候，一定要调用set_message("")，强制显示空字符串，而非交由FigureCanvasNavigationToolbar进行默认处理
        '''
        
        if ImgDataManager.img_info is None:
            # self.nav_toolbar.set_message("")
            return
        
        if event.xdata is None or event.ydata is None:
            # self.nav_toolbar.set_message("")
            return
        
        n = round(event.xdata)
        if 0<=n<len(ImgDataManager.wave_enabled_list):
            xdata = ImgDataManager.wave_enabled_list[n]
            ydata = event.ydata
            self.nav_toolbar.set_message(f"(x, y) = ({xdata:4.2f}, {ydata:5.2f})")
        else:
            # self.nav_toolbar.set_message("")
            pass
        return
    

    def fig_mouse_click(self, event):
        '''
        在canvas上点击的响应事件
        event.button：左键1中键2右键3
        x,y: canvas的坐标
        event.xdata, ydata: 在fig坐标区域内才有效（基于坐标轴的取值）
        '''

        if ImgDataManager.img_info is None:
            return
        
        if event.xdata is None or event.ydata is None:
            return
        
        n = round(event.xdata)
        if 0<=n<len(ImgDataManager.wave_enabled_list):
            xdata = ImgDataManager.wave_enabled_list[n]
            ydata = event.ydata
        
            # print(f"{'double' if event.dblclick else 'single'} click:"
            #       f"button={event.button}, x={event.x}, y={event.y},"
            #       f"xdata={event.xdata}, ydata={event.ydata}. ")
            
            print(f"{'double' if event.dblclick else 'single'} click:"
                f"button={event.button}, x={event.x}, y={event.y},"
                f"xdata={xdata}, ydata={ydata}. ")
        return
    

    def fig_on_pick(self, event):
        '''
        在创建图形元素时，可以通过设置 picker 属性来指定对象是否可拾取。
        例如，line, = ax.plot(x, y, picker=True) 将线条设置为可拾取。
        '''
        thisline = event.artist    # 拾取到的绘制对象
        ind = event.ind           # 曲线点击点在x轴方向的数值，如果点击在两个离散点x1和x2之间，则取更为接近的那个x值
        ret = DrawingManager.on_pick_figure_obj(thisline, ind)
        if ret is None:
            return
        elif isinstance(ret, int):
            index = self.get_label_listbox_index_from_id(ret)
            if index >=0:
                self.label_listbox.selection_clear(0, tk.END)
                self.label_listbox.selection_set(index)
        elif isinstance(ret, list):
            index_list = self.get_sample_listbox_index_from_id(ret)
            if len(index_list) > 0:
                self.samples_listbox.selection_clear(0, tk.END)
                for index in index_list:
                    self.samples_listbox.selection_set(index)
        
        self.redraw_fig_canvas()
        return
    

    def toggle_scale_enabled(self):

        print(self.scale_enabled.get())
        self.my_scale.set_status(self.scale_enabled.get()) 
        if self.scale_enabled.get():
            self.on_img_stretch(None)
        else:
            DrawingManager.set_stretch_info(False)


    def on_clear_auto_roi_region(self):

        DrawingManager.clear_auto_roi_region()
        return


    def on_auto_roi(self):
        '''
        当显示单波段图像时，设置显示像素值的下限，即像素值低于该门限的像素不显示
        '''
        if ImgDataManager.img_info is None:
            return
        
        if DrawingManager.img_wave_index_selected < 0:
            messagebox.showwarning("提示", "请先选择某个波段的灰度图进行操作！")
            return
        
        if self.label_listbox.size()>0:
            answer = messagebox.askyesno("数据清除警告", "已经存在点标签或多边形标签，是否清空已有标签后继续？",
                                            default=messagebox.NO)
            if answer:
               self.delete_all_label()
        
        self.op_notebook.select(1)

        self.showimg_status_auto_roi = True
        self.var_show_mask.set(True)
        
        DrawingManager.set_auto_roi_params(auto_roi_show=self.var_show_mask.get(),
                                           auto_roi_gray_thres=self.var_gray_thres.get(),
                                           auto_roi_erosion=self.var_erosion.get(),
                                           auto_roi_image_transparency=self.var_transparency.get())
        DrawingManager.auto_roi()

        pass


    def on_clear_auto_roi(self):
        '''
        清除自动标注的结果，包括界面
        '''

        DrawingManager.clear_auto_roi()
        
        for id in ShapeManager.auto_roi_polygon_id_list:
             for index in range(self.label_listbox.size()):
                 id_in_item = self.get_id_from_label_listbox(index) 
                 if id == id_in_item:
                     self.label_listbox.delete(index)
                     break
                
        # 标签对象清理
        ShapeManager.clear_auto_roi_objects()
        return
    
    
    def on_auto_label_polygon(self):
        '''
        根据自动生成的ROI, 产生polygon，绘制到界面
        设置Label，记录到LabelList中
        '''
        if not self.showimg_status_auto_roi:
            return

        # 选择LabelName
        if self.label_name_listbox.size() > 0 and len(self.label_name_listbox.curselection()) > 0:
            index = self.label_name_listbox.curselection()[0]
            labelname = self.label_name_listbox.get(index)
        else:
            labelname = simpledialog.askstring("新标签名", "请输入新标签名称")
            labelname = labelname.strip()
            if (not isinstance(labelname, str)) or len(labelname) == 0:
                messagebox.showerror("错误", "未指定标签名称")
                return
            
            index = self.label_name_add_to_listbox(labelname)
            self.label_name_listbox.selection_set(index)

        ShapeManager.create_polygon_from_auto_roi(labelname)

        for id in ShapeManager.auto_roi_polygon_id_list:
            item = self.set_label_listbox_item(ShapeManager.current_label_name, id, ShapeType.polygon)
            self.label_listbox.insert(tk.END,  item)

        messagebox.showinfo("自动标注", f"自动标注成功生成{len(ShapeManager.auto_roi_polygon_id_list)}个多边形")

        self.redraw_fig_canvas()
        return



    def on_save_auto_label_to_truth(self):
        '''
        将自动标注的多边形保存为真值，便于测试用真值框进行统计
        '''

        if self.current_file_path and self.label_listbox.size()>0:
            cur_dir, cur_filename = os.path.split(self.current_file_path)
            filename, ext = os.path.splitext(cur_filename)
            truth_filename = filename+"_truth.txt"

            if self.history_saving_dir:
                initialdir = self.history_saving_dir
            else:
                initialdir=cur_dir

            file_path = filedialog.asksaveasfilename(title="保存真值框", confirmoverwrite=True, defaultextension='.txt', 
                                                    filetypes=[('txt file', '.txt')],
                                                    initialdir=initialdir, initialfile=truth_filename)
       
            if file_path:
                self.history_saving_dir = os.path.dirname(file_path)

                # self.roi_manager.truth_save(file_path)

                messagebox.showinfo("保存完成", "保存自动ROI到真值文件成功！")
        
        return



    def on_save_auto_label_to_ds(self):
        '''
        将界面的自动标注标签保存为数据集文件（img+hdr）
        '''

        if DrawingManager.auto_roi_mask_img is None:
            return
        
        if ShapeManager.auto_roi_classname is None:
            # 选择LabelName
            if self.label_name_listbox.size() > 0 and len(self.label_name_listbox.curselection()):
                index = self.label_name_listbox.curselection()[0]
                labelname = self.label_name_listbox.get(index)
            else:
                labelname = simpledialog.askstring("新标签名", "请输入新标签名称")
                if (not isinstance(labelname, str)) or len(labelname.strip()) == 0:
                    messagebox.showerror("错误", "未指定标签名称")
                    return
                labelname = labelname.strip()
                self.label_name_listbox.insert(tk.END, labelname)

            ShapeManager.auto_roi_classname = labelname
        
        now = datetime.now()
        formatted_time = now.strftime('%y%m%d-%H%M%S')
        default_file_name = f"{labelname}-{formatted_time}"
        
        save_path = filedialog.asksaveasfilename(title="保存数据集文件", confirmoverwrite=True, defaultextension='.img', 
                                                    filetypes=[('img file', '.img')],
                                                    initialdir=self.history_saving_dir, initialfile=default_file_name)
        if save_path is None:
            return 
        
        self.history_saving_dir = os.path.dirname(save_path)
        
        DrawingManager.save_auto_roi_to_dataset(save_path, formatted_time)

        messagebox.showinfo("保存成功", f"标签{labelname}数据集文件保存到{save_path}")


        pass

    
    def toggle_show_mask(self):

        if self.mask_img is None:
            return

        if self.var_show_mask.get():
            
            color_array = np.zeros((self.mask_img.shape[0], self.mask_img.shape[1], 3), dtype=np.uint8)
            color_array[:, :, 0][self.mask_img==1] = 255  # Red channel
            color_array[:, :, 1] = 0
            color_array[:, :, 2] = 0
              
            pil_image_mask = Image.fromarray(color_array)
            pil_image_mask = pil_image_mask.resize((self.show_width, self.show_height))

            # 创建一个与图像2相同大小的alpha图层，并填充为128（半透明）
            p = int(self.var_transparency.get()*255/100)
            alpha_layer = Image.new('L', pil_image_mask.size, p)
            # 将alpha图层添加到图像的alpha通道
            pil_image_mask.putalpha(alpha_layer)

            self.image_tk_mask = ImageTk.PhotoImage(pil_image_mask)
            if self.mask_on_canvas is not None:
                self.canvas.delete(self.mask_on_canvas)
            self.mask_on_canvas = self.canvas.create_image(0, 0, anchor="nw", image=self.image_tk_mask)
            self.canvas.tag_raise(self.mask_on_canvas)
            pass

        else:
            self.canvas.delete(self.mask_on_canvas)
            self.mask_on_canvas = None

        pass

    
    def on_gray_thres_changed(self, text):
        '''
        text为拖动滑块时的当前值，只要拖动滑块，该事件将会一直产生
        '''
        
        pass


    def on_operation_select(self):
        
        # To Do 如果多边形正在绘制，则需要取消
        
        DrawingManager.set_drawing_mode(self.op_selection.get())
        
        if self.op_selection.get() in [RoiType.OP_ROI_POINT, RoiType.OP_ROI_POLYGON, RoiType.OP_ROI_RECT]:
            self.roi_notebook.select(0)
            if ShapeManager.current_label_name == "":
                messagebox.showwarning("提示", "进行标注之前请选择标签！")
            pass
        elif self.op_selection.get() == RoiType.OP_TRUTH_RECT:
            self.roi_notebook.select(1)
        elif self.op_selection.get() in [RoiType.OP_SAMPLE_POINT, RoiType.OP_SAMPLE_POLYGON, RoiType.OP_SAMPLE_RECT]:
            self.spectral_notebook.select(1)
            pass
        
        return


    def on_label_name_listbox_selected(self, event):
        '''
        选择标签的触发动作：
        标签图形的高亮
        光谱曲线的选择或高亮
        '''
        if self.label_name_listbox.size() == 0:
            return
        
        index = self.label_name_listbox.curselection()[0]
        item = self.label_name_listbox.get(index)
        
        # 下面这段代码是为了取消选中的条目
        if item != ShapeManager.current_label_name:
            ShapeManager.set_current_label_name(item)
        else:
            self.label_name_listbox.selection_clear(0, tk.END)
            ShapeManager.set_current_label_name()

    
    def on_labelname_listbox_click(self, event):
        '''
        判断是否点击在空白处，从而取消全部选中的条目
        <Button-1>事件要早于<ListboxSelect>事件
        !!! 废代码 留着参考用 ！！！
        '''
        return
        if self.label_name_listbox.size() == 0:
            return

        selected_index = self.label_name_listbox.curselection()
        if len(selected_index) == 0:
            return

        # 使用nearest方法获取点击位置最近的条目索引,这个最近没有门限限制，所以怎么都会选中一个条目！！！
        nearest_index = self.label_name_listbox.nearest(event.y)
        # 如果没有选中任何条目
        if nearest_index != selected_index[0]:
            # 取消选中
            self.label_name_listbox.selection_clear(0, tk.END)
        pass

    
    def label_name_add_to_listbox(self, labelname:str):
        '''
        新增一个标签名称
        '''
        labelname = labelname.strip()
        if len(labelname) > 0:
            for index in range(self.label_name_listbox.size()):
                item = self.label_name_listbox.get(index)
                if item.lower() == labelname.lower():
                    return index
            else:
                self.label_name_listbox.insert(tk.END, labelname)
                return self.label_name_listbox.size() - 1
        return -1
    

    def label_name_listbox_add_item(self):
        labelname = simpledialog.askstring("新增标签", "请输入标签名称", initialvalue="0")
        if isinstance(labelname, str) and len(labelname.strip()) > 0:
            self.label_name_add_to_listbox(labelname)
        return


    def edit_label_name(self):
        index = self.label_name_listbox.curselection()[0]
        if index is None:
            return
        
        old_classname = self.label_name_listbox.get(index)
        
        new_classname = simpledialog.askstring("编辑标签", "请输入标签新名称", initialvalue="0")
        
        if isinstance(new_classname, str) and len(new_classname.strip()) > 0 and new_classname!=old_classname:
            self.label_name_listbox.delete(index)
            self.label_name_listbox.insert(index, new_classname)

        # 将该标签对应的全部对象的标签名都做相应修改
        ShapeManager.change_label_name(old_classname, new_classname)

        for index in range(self.label_listbox.size()):
            item = self.label_listbox.get(index)
            id, classname = self.get_id_from_label_listbox(index, ret_classname=True)
            if classname == old_classname:
                self.label_listbox.delete(index)
                item = item.replace(old_classname, new_classname)
                self.label_listbox.insert(index, item)

        return

    
    def remove_label_name(self):
        '''
        额外操作：
        需要删除当前文件已经绘制的标签对象，清除label listbox中对应标签对象
        '''
        index = self.label_name_listbox.curselection()[0]
        if index is None:
            return
        
        answer = messagebox.askyesno("删除标签", "是否确定要删除标签？该标签对应的所有标注对象都将被清除！", 
                                     default=messagebox.NO)
        if not answer:
            return 
        
        item = self.label_name_listbox.get(index)
        self.label_name_listbox.delete(index)

        ShapeManager.delete_label_name(item)
        
        index_to_del = []
        for index in range(self.label_listbox.size()):

            id, classname = self.get_id_from_label_listbox(index, ret_classname=True)
            if classname == item:
                index_to_del.append(index)

        if len(index_to_del)>0:
            index_to_del.sort(reverse=True)
            for i in index_to_del:
                self.label_listbox.delete(i)
        
        return


    def remove_all_label_name(self):
        if self.label_name_listbox.size() <= 0:
            return
        
        answer = messagebox.askyesno("删除全部标签", "是否确定要删除全部标签？所有标注对象都将被清除！", default=messagebox.NO)
        if not answer:
            return 
        
        for index in range(self.label_name_listbox.size()):
            item = self.label_name_listbox.get(index)
            ShapeManager.delete_label_name(item)
        
        self.label_name_listbox.delete(0, tk.END)
        self.label_listbox.delete(0, tk.END)
        return


    def show_img_all_points_wave(self, n=-1):
        '''
        将当前img文件的所有像素点的波形全部显示
        '''

        self.redraw_fig_canvas()

        return
    
        
    def help(self):
        messagebox.showinfo("光谱分析工具", "Author: TR\nV 2.0.0")


    def exit_program(self):
        self.root.quit()


    def load_wavlength(self):
        
        self.spectral_listbox.delete(0, tk.END)
        for wv in ImgDataManager.img_info.hdr.wavelength:
            self.spectral_listbox.insert(tk.END, wv)
        
        self.combo_start_wv['values'] = ImgDataManager.img_info.hdr.wavelength
        # self.combo_start_wv.configure(state='readonly')
        self.combo_start_wv.current(0)
        self.combo_end_wv['values'] = ImgDataManager.img_info.hdr.wavelength
        # self.combo_end_wv.configure(state='readonly')
        self.combo_end_wv.current(ImgDataManager.img_info.hdr.bands-1)

        return


    def load_label_from_file(self, label_file_path:str):
        '''
        为当前文件加载标注（点和多边形）
        selected_file：为当前打开的img文件选择的标签文件
        如果不指定，则标签文件的格式默认为：*.txt
        '''
        
        if self.current_file_path is None:
            return
        if not os.path.exists(label_file_path):   
            return

        _, ext = os.path.splitext(label_file_path)

        if ext == '.txt':

            shape_info_list, label_count_dict, total_count = ShapeManager.label_load_from_txt_file(label_file_path)
            if len(shape_info_list) > 0:
                for label in label_count_dict:
                    self.label_name_add_to_listbox(label)
                
                for shape_info in shape_info_list:
                    id = shape_info[0]
                    classname = shape_info[1]
                    shape = shape_info[2]
                    item = self.set_label_listbox_item(classname=classname, id=id, shape=shape)
                    self.label_listbox.insert(tk.END, item)
                
                messagebox.showinfo("标签文件加载",f"成功加载{len(shape_info_list)}条标注记录, 共{len(label_count_dict)}个类别")
            
            else:
                messagebox.showwarning("标签文件加载", f"加载标签文件{label_file_path}失败！")
        
        elif ext == '.json':   # To do
            messagebox.showinfo("json标签文件加载","To do")
            pass

        self.redraw_fig_canvas()
        return
   

    def on_wave_select(self, event):
        '''
        选择波段，变灰度图
        '''
        if self.spectral_listbox.size() == 0:
            return
        
        # self.showimg_status_auto_roi = False
        wave_selected = self.spectral_listbox.curselection()[0]

        DrawingManager.set_wave_selected(wave_selected)
        
        return
        


    def spectral_list_menu(self, event):
        if self.spectral_listbox.size() == 0:
            return
        self.spectral_list_menubar.post(event.x + self.spectral_listbox.winfo_rootx(), event.y + self.spectral_listbox.winfo_rooty()) 

        return
    

    def set_wv_range(self , start=True):

        index = self.spectral_listbox.curselection()[0]
        if index:
            if start:
                if index > ImgDataManager.wave_index_end:
                    answer = messagebox.askokcancel("设置警告", 
                                           f"设置的起点波段索引{index}大于终点波段索引{ImgDataManager.wave_index_end}\n继续则将调整终点波段索引",
                                             default=messagebox.YES)
                    if not answer:
                        return
                    
                    ImgDataManager.set_wv_range(wv_index_start=index, wv_index_end=index)
                else:
                    ImgDataManager.set_wv_range(wv_index_start=index)

            else:

                if index < ImgDataManager.wave_index_start:
                    answer = messagebox.askokcancel("设置警告", 
                                           f"设置的终点波段索引{index}小于终点波段索引{ImgDataManager.wave_index_start}\n继续则将调整起点波段索引",
                                             default=messagebox.YES)
                    if not answer:
                        return
                    
                    ImgDataManager.set_wv_range(wv_index_start=index, wv_index_end=index)
                else:
                    ImgDataManager.set_wv_range(wv_index_end=index)

            DrawingManager.update_x_axis()
            self.redraw_fig_canvas()
        return
    

    def set_wv_status(self, enable=True):

    
        return
        

    def label_list_menu(self, event):
        if self.label_listbox.size() == 0:
            return
        
        self.label_list_menubar.delete(0, tk.END)
        if self.label_listbox.curselection():
            self.label_list_menubar.add_command(label = '删除标注', command=self.delete_label)
            self.label_list_menubar.add_command(label = '删除全部标注', command=self.delete_all_label)
            self.label_list_menubar.add_separator()
            self.label_list_menubar.add_command(label = '保存标签为真值文件', command=self.save_to_truth_file)
            # self.label_list_menubar.add_command(label="选择为距离比较基准", command=self.point_select_for_sam_base)
            # self.label_list_menubar.add_command(label="清除距离比较基准", command=self.clear_point_select_for_sam_base)
            # self.polygon_listbox.update()
        else:
            self.label_list_menubar.add_command(label = '删除全部标注', command=self.delete_all_label)
            self.label_list_menubar.add_command(label = '保存标签为真值文件', command=self.save_to_truth_file)
        self.label_list_menubar.add_separator()
        self.label_list_menubar.add_command(label="编辑标签名", command=self.edit_label_labelname)
        self.label_list_menubar.post(event.x + self.label_listbox.winfo_rootx(), event.y + self.label_listbox.winfo_rooty()) 

        pass


    def on_label_select(self, event):
        '''
        选择某个标注项(class-id-shape)
        '''
        if self.label_listbox.size() == 0:
            return
        index = self.label_listbox.curselection()[0]
        id = self.get_id_from_label_listbox(index)
        if not ShapeManager.label_select(id):
            self.label_listbox.selection_clear(0, tk.END)
        
        self.redraw_fig_canvas() 
        return


    
    def delete_all_label(self):
        if not messagebox.askokcancel("确认", message="确定删除全部标签？"):
            return

        ShapeManager.label_clear()
        self.label_listbox.delete(0, tk.END)
        self.redraw_fig_canvas()  

        return


    def delete_label(self):
        
        if self.label_listbox.curselection():
            index = self.label_listbox.curselection()[0]
            id = self.get_id_from_label_listbox(index)
            ShapeManager.label_delete(id)

            self.label_listbox.delete(index)
            self.redraw_fig_canvas()

        return



    def edit_label_labelname(self):
        '''
        修改某个特定标注的标签名称
        '''

        
        return
    

    
    def on_sample_select(self, event):

        selection = self.samples_listbox.curselection()

        if len(selection) == 0:
            id_list = []
        else:
            id_list = [self.get_id_from_sample_listbox(index) for index in selection]

        ShapeManager.sample_select(id_list)
        
        if len(id_list) == 1:
            sample_file_path = ShapeManager.get_file_path_by_id(id_list)
            self.statusbar_set_tip(sample_file_path)
        
        self.redraw_fig_canvas()

        return
    

    def sample_list_menu(self, event):

        if self.samples_listbox.size() == 0:
            return
        
        samples_list_menubar = Menu(self.samples_listbox,tearoff=False)
        selection = self.samples_listbox.curselection()
        if len(selection) == 0:
            return
        
        samples_list_menubar.add_command(label = '全选', command=self.select_all_samples)
        samples_list_menubar.add_command(label = '全不选', command=self.unselect_all_samples)
        samples_list_menubar.add_separator()
        samples_list_menubar.add_command(label = '删除样本', command=self.remove_sample)
        samples_list_menubar.add_command(label = '删除全部样本', command=self.remove_all_samples)
        samples_list_menubar.add_separator()
        # samples_list_menubar.add_command(label = '设为参照', command=self.set_as_reference)
        samples_list_menubar.add_command(label = '样本之间的SAM距离', command=self.on_sam_between_samples)
        samples_list_menubar.add_command(label = '当前img和样本间的SAM距离', command=self.on_sample_sam_in_current_img)

        samples_list_menubar.post(event.x + self.samples_listbox.winfo_rootx(), 
                                             event.y + self.samples_listbox.winfo_rooty()) 


        return
        

    
    def remove_sample(self):

        selection = self.samples_listbox.curselection()
        if len(selection) == 0:
            return

        id_list = [self.get_id_from_sample_listbox(index) for index in selection]
        ShapeManager.sample_delete(id_list)
        
        self.redraw_fig_canvas()

        index_list = list(selection)
        index_list.sort(reverse=True)
        for idx in index_list:
            self.samples_listbox.delete(idx)

        return
    

    def remove_all_samples(self):

        ShapeManager.sample_clear()
        self.samples_listbox.delete(0, tk.END)
        self.redraw_fig_canvas()
        return
    

    def unselect_all_samples(self):

        ShapeManager.sample_select()
        self.samples_listbox.selection_clear(0, tk.END)

        self.redraw_fig_canvas()
        return
    
    
    def select_all_samples(self):

        self.samples_listbox.selection_set(0, tk.END)
        selection = self.samples_listbox.curselection()

        id_list = [self.get_id_from_sample_listbox(index) for index in selection]

        ShapeManager.sample_select(id_list)

        self.redraw_fig_canvas()
        return
    

    def on_sam_between_samples(self):

        #Cluster*B  计算每个类每个簇的标准谱线

        selection = self.samples_listbox.curselection()
        if len(selection) < 2:
            return 

        class_name_list = []
        id_list = []
        for index in selection:
            iid = self.get_id_from_sample_listbox(index)
            id_list.append(iid)
            class_name_list.append(str(iid))
        
        distance = ShapeManager.get_distance_between_samples(id_list)

        # UI show
        DlgShowTable(class_name_list, distance, row_title=True, title="样本点之间的SAM距离")

        return
    

    def on_sample_sam_in_current_img(self):

        selection = self.samples_listbox.curselection()
        if len(selection) == 0 :
            return 
        
        if len(selection) > 10:
            messagebox.showwarning("警告", "To do:样本数超过10个，将进行平均或（聚类）处理？？？")
            return
        
        id_list = [self.get_id_from_sample_listbox(index) for index in selection]
        mean = True
        distance = ImgDataManager.sam_result_between_samples_and_img(id_list, mean)
        if mean:
            id_list.append('mean')

        WindowShowSamDistanceImage(classname_list=id_list,
                                   distance=distance, master=self.root)
    
        return

    
    # def load_truth_from_file(self):
    #     '''
    #     加载真值配置文件，读取真值框
    #     '''
    #     if self.current_file_path:
    #         cur_dir, cur_filename = os.path.split(self.current_file_path)

    #         filename, ext = os.path.splitext(self.current_file_path)
    #         truth_filename = filename+"_truth.txt"
    #         if not os.path.exists(truth_filename):
    #             return
    #         ShapeManager.truth_clear()
    #         ret = ShapeManager.label_load_from_txt_file(truth_filename)

    #     else:
    #         messagebox.showinfo("打开真值文件错误", message="请先打开img文件!")


    def save_to_truth_file(self):

        if self.current_file_path and self.label_listbox.size()>0:
            cur_dir, cur_filename = os.path.split(self.current_file_path)
            filename, ext = os.path.splitext(cur_filename)
            truth_filename = filename+"_truth.txt"

            if self.history_saving_dir:
                initialdir = self.history_saving_dir
            else:
                initialdir=cur_dir

            file_path = filedialog.asksaveasfilename(title="保存真值", confirmoverwrite=True, defaultextension='.txt', 
                                                    filetypes=[('txt file', '.txt')],
                                                    initialdir=initialdir, initialfile=truth_filename)
       
            if file_path:
                self.history_saving_dir = os.path.dirname(file_path)
                ShapeManager.label_save_to_txt_file(file_path)
                messagebox.showinfo("保存成功", f"标签信息保存到真值文件{file_path}")
                return


    def update_imglist_label(self):
        if self.image_listbox.size()>0:
            text = f"文件列表 ({self.cur_file_selected_index+1}/{self.image_listbox.size()})"
        else:
            text = "文件列表"
        self.img_list_label.config(text=text)
        self.statusbar_set_filepath()
        return


    def close_current_file(self):
        '''
        关闭当前文件的清理工作
        '''
        if self.current_file_path is None:
            return
        
        _, ext = os.path.splitext(self.current_file_path)
        if ext == '.img':

            pass

        elif ext == '.tif':

            pass

        elif ext == '.jgp':

            pass

        self.current_file_path = None
        return


    def load_current_file(self, new_file_path=None):
        '''
        new_file_path: 当前准备加载的文件路径
        self.current_file_path: 已经加载的文件路径
        比较两者文件类型，决定如何清理和初始化
        '''

        if self.current_file_path is None:
            # 无须进行旧文件的清理
            pass
        else:
            # 旧文件的清理
            pass

        self.reset_transform()

        ImgDataManager.clear_img_info()
        DrawingManager.reset()   # 先清Canvas
        ShapeManager.clear()
        
        self.label_listbox.delete(0, tk.END)
        # 当前sample_listbox 选中状态清除
        self.samples_listbox.selection_clear(0, tk.END)

        # 读取img info
        if not ImgDataManager.read_img_info(self.current_file_path):
            messagebox.showerror("img文件读取错误", f"{self.current_file_path}")
            return 
        
        ShapeManager.set_current_filepath(self.current_file_path)
        ShapeManager.draw_samples_shape_on_canvas()

        # UI菜单项使能        
        self.set_ui_state_with_img()
        # 加载img文件的波段到列表框
        self.load_wavlength()

        # 提供img信息到nav_toolbar
        self.nav_toolbar.set_img_path(self.current_file_path)
        
        # 自动加载标签文件
        if self.var_auto_load_label_type.get() != AutoLoadLabelType.LOAD_NON:
            filename, ext = os.path.splitext(self.current_file_path)
            if self.var_auto_load_label_type.get() == AutoLoadLabelType.LOAD_LABEL_TXT:
                label_filename = filename+".txt"
            elif self.var_auto_load_label_type.get() == AutoLoadLabelType.LOAD_LABEL_JSON:
                label_filename = filename+".json"
            else:
                label_filename = filename+"_truth.txt"
            
            self.load_label_from_file(label_filename)

            pass

        self.redraw_fig_canvas()

        pass
    

    def on_open_image(self):
        '''
        打开多个图像文件文件（img，tif，jpg）
        '''
        # filedialog.askopenfilenames返回文件绝对路径列表。点击取消时，返回''
        file_selected_list = filedialog.askopenfilenames(title="打开图像文件", defaultextension='.img', 
                                               initialdir=self.history_open_dir,
                                               filetypes=[('img file', '.img'), ('tif file', '.tif'), ('all file', '.*')])
        if len(file_selected_list) == 0:
            return
        
        if len(file_selected_list) == 1 and self.current_file_path:
            if os.path.normpath(self.current_file_path) == os.path.normpath(file_selected_list[0]):
                messagebox.showinfo("提示", f"文件{file_selected_list[0]}已经打开了！")
                return
        
        index = -1   # 第一个找到的文件索引
        for file_path in file_selected_list:
            # 如果文件已经处于列表中,则选择该文件即可
            for i, item in enumerate(self.file_path_list):
                if os.path.normpath(file_path) == os.path.normpath(item):
                    if index == -1:
                        index = i
                    break
            else:
                self.image_listbox.insert(tk.END, os.path.basename(file_path))
                self.file_path_list.append(file_path)
                self.file_path_dict[file_path] = '.img'
                if index == -1:    # 保存第一个的索引，准备打开它
                    index = self.image_listbox.size()-1

        # 选择的文件中存在当前已经打开的文件，则不改变当前打开的文件
        if self.file_path_list[index] == self.current_file_path:
            return
        
        # 选择打开index对应的文件
        self.image_listbox.selection_clear(0, self.image_listbox.size()-1)
        self.image_listbox.selection_set(index)

        self.cur_file_selected_index = index
        self.current_file_path = self.file_path_list[index]

        self.load_current_file()
        
        self.history_open_dir = os.path.dirname(self.current_file_path)
        # 更新img列表标题
        self.update_imglist_label()

        return


    def on_open_folder(self):
        folder_path = filedialog.askdirectory(title="打开文件夹中img文件", initialdir=self.history_open_dir)
        if folder_path:
            # items = self.image_listbox.get(0, tk.END)
            add_num = 0
            file_list = os.listdir(folder_path)
            file_list.sort()
            for file_name in file_list:
                name, ext = os.path.splitext(file_name)
                if file_name.lower().endswith(('.jpg')) or \
                    file_name.lower().endswith(('.png')) or \
                        file_name.lower().endswith(('.tif')) or\
                            file_name.lower().endswith(('.img')):
                    file_path = os.path.join(folder_path, file_name)
                    if file_path:
                        # 如果文件已经处于列表中
                        for item in self.file_path_list:
                            if os.path.normpath(file_path) == os.path.normpath(item):
                                break
                        else:
                            self.image_listbox.insert(tk.END, os.path.basename(file_path))
                            self.file_path_list.append(file_path)
                            self.file_path_dict[file_path] = ext
                            add_num += 1
            
            total_num = self.image_listbox.size()

            self.statusbar_set_info(f"新加载了{add_num}个文件")

            self.history_open_dir = folder_path

            if self.current_file_path:  # 已经存在打开的文件
                pass
            else:     # 打开第一个文件
                if self.image_listbox.size()>0:

                    self.image_listbox.select_set(0)
                    self.current_file_path = self.file_path_list[0]
                    self.cur_file_selected_index = 0
                    
                    self.load_current_file()
                    
            self.update_imglist_label()

        return


    def on_file_select(self, event):
        
        if self.image_listbox.size() == 0:
            return
        index = self.image_listbox.curselection()[0]
        
        if self.cur_file_selected_index == index:  # 点击相同文件
            self.spectral_listbox.selection_clear(0, tk.END)
            # self.current_file_path = self.image_listbox.get(index)
            self.current_file_path = self.file_path_list[index]

            self.wave_selected = -1
            # self.showimg_status_auto_roi = True
            DrawingManager.set_wave_selected()
            
            return

        else:   # 切换文件
            answer = True
            if self.label_listbox.size() > 0:
            
                answer = messagebox.askyesno("确认","存在标注，是否要切换文件？")

            if answer:
                self.current_file_path = self.file_path_list[index]  
                self.cur_file_selected_index = index                
                
                self.load_current_file()

                self.update_imglist_label()

            else:
                self.image_listbox.selection_clear(0, tk.END)
                self.image_listbox.selection_set(self.cur_file_selected_index)
                return


    def image_listbox_menu(self, event):
        # if self.image_listbox.size() == 0:
        #     return
        # if self.current_file_path:
        self.image_list_menubar.post(event.x + self.image_listbox.winfo_rootx(), event.y + self.image_listbox.winfo_rooty()) 



    def remove_file(self):
        if self.image_listbox.size() == 0:
            return

        if self.image_listbox.curselection():   # 需要删除的文件
            # 删除当前文件
            index = self.image_listbox.curselection()[0]
            self.image_listbox.delete(index)
            self.image_listbox.selection_clear(0, tk.END)
            self.file_path_list.pop(index)

            ShapeManager.sample_delete_by_file(self.current_file_path)
            ShapeManager.label_clear()
            
            # 如果还有其他文件， 则打开它
            if self.image_listbox.size() > 0:   
                if index > 0:
                    index -= 1
                self.current_file_path = self.file_path_list[index]  
                self.cur_file_selected_index = index

                self.load_current_file()

                self.cur_file_selected_index = 0
                self.image_listbox.selection_set(0)
                self.image_listbox.yview_moveto(float(self.cur_file_selected_index)/self.image_listbox.size())
            else:
                DrawingManager.reset()
                ImgDataManager.clear_img_info()
                pass

            
            self.label_listbox.delete(0, tk.END)

            # 更新文件列表信息
            self.update_imglist_label()
        
        return


    def remove_all_files(self):

        if self.image_listbox.size() == 0:
            return

        self.image_listbox.delete(0, tk.END)
        self.file_path_list.clear()

        DrawingManager.reset()
        ShapeManager.clear()
        ImgDataManager.clear_img_info()
        self.samples_listbox.delete(0, tk.END)
        self.label_listbox.delete(0, tk.END)

        self.update_imglist_label()
        pass


    def filelist_filter(self):
        if self.image_listbox.size() == 0:
            return
        
        dlg = FileListFilterDialog(self.root, self.image_listbox)

        print(dlg.result)

        pass


    def save_file_list(self):
        if self.image_listbox.size() == 0:
            return

        file_path = filedialog.asksaveasfilename(title="保存文件列表", confirmoverwrite=True, defaultextension='.txt', 
                                                    filetypes=[('txt file', '.txt')])
       
        if file_path:
            # items = self.image_listbox.get(0, tk.END)
            with open(file_path, "w", encoding='utf-8') as f:
                for item in self.file_path_list:
                    f.write(item+"\n")
            
        
        pass

    
    def load_file_list(self):
        file_list_path = filedialog.askopenfile(title="加载文件列表", defaultextension='.txt', 
                                                    filetypes=[('txt file', '.txt')])
       
        if file_list_path:
            # items = self.image_listbox.get(0, tk.END)
            with open(file_list_path.name, "r", encoding='utf-8') as f:
                for file_path in f:
                    file_path = file_path.replace("\n", "")
                    if file_path.lower().endswith(('.img')):
                        # 如果文件已经处于列表中
                        for item in self.file_path_list:
                            if os.path.normpath(file_path) == os.path.normpath(item):
                                break
                        else:
                            self.image_listbox.insert(tk.END, os.path.basename(file_path))
                            self.file_path_list.append(file_path)
                            self.file_path_dict[file_path] = '.img'

            if self.current_file_path:
                pass
            else:
                if self.image_listbox.size()>0:
                    self.image_listbox.select_set(0)
                    self.current_file_path = self.file_path_list[0]
                    self.cur_file_selected_index = 0
                    
                    self.wave_selected = -1
                    
                    self.load_current_file()


        pass


    def show_or_move_image_list_hover_tip(self, event):
        item_index = self.image_listbox.nearest(event.y)

        bbox = self.image_listbox.bbox(item_index)  # 获取条目的边界框
        if not bbox:  # 如果没有边界框，可能没有条目
            self.hide_image_list_hover_tip(None)
            return

        if bbox[1] <= event.y <= bbox[1] + bbox[3]:  # 鼠标位于条目内
            # 获取当前鼠标位置的条目文本
            # item_text = self.image_listbox.get(item_index)
            item_text = self.file_path_list[item_index]

            if not self.img_list_hover_tip:
                self.img_list_hover_tip = tk.Toplevel(self.root)
                self.img_list_hover_tip.wm_overrideredirect(True)  # remove title bar
                self.hover_label = tk.Label(self.img_list_hover_tip, bg="yellow", padx=10, pady=2)
                self.hover_label.pack()

            # 更新标签文本并移动位置
            self.hover_label.config(text=item_text)
            abs_x = self.image_listbox.winfo_rootx() + bbox[0]  # 使用bbox的x坐标
            abs_y = self.image_listbox.winfo_rooty() + bbox[1] + 20  # 使用bbox的y坐标并稍微下移
            self.img_list_hover_tip.geometry(f"+{abs_x}+{abs_y}")
        else:
            # 如果鼠标不在任何条目上，隐藏提示
            self.hide_image_list_hover_tip(None)

        return
    

    # 隐藏悬停提示
    def hide_image_list_hover_tip(self, _):
        if self.img_list_hover_tip:
            self.img_list_hover_tip.destroy()
            self.img_list_hover_tip = None

        return

    
    def image_listbox_moveup(self, event):

        index = self.image_listbox.curselection()[0]
        if index <=0:
            return
        
        self.image_listbox.selection_clear(0, self.image_listbox.size()-1)
        self.image_listbox.selection_set(index-1)
        self.image_listbox.yview_moveto((index-1)/self.image_listbox.size())
        self.on_file_select(event)
        return
    

    def image_listbox_movedown(self, event):

        index = self.image_listbox.curselection()[0]
        if index >=self.image_listbox.size()-1:
            return
        
        self.image_listbox.selection_clear(0, self.image_listbox.size()-1)
        self.image_listbox.selection_set(index+1)
        self.image_listbox.yview_moveto((index+1)/self.image_listbox.size())
        self.on_file_select(event)

        return


    def rotate_image_according_to_exif(self, img):
        try:
            for orientation in ExifTags.TAGS.keys():
                if ExifTags.TAGS[orientation] == 'Orientation':
                    break
            exif = img._getexif()
            if exif[orientation] == 2:
                img = img.transpose(Image.FLIP_LEFT_RIGHT)
            elif exif[orientation] == 3:
                img = img.rotate(180)
            elif exif[orientation] == 4:
                img = img.rotate(180).transpose(Image.FLIP_LEFT_RIGHT)
            elif exif[orientation] == 5:
                img = img.rotate(-90, expand=True).transpose(Image.FLIP_LEFT_RIGHT)
            elif exif[orientation] == 6:
                img = img.rotate(-90, expand=True)
            elif exif[orientation] == 7:
                img = img.rotate(90, expand=True).transpose(Image.FLIP_LEFT_RIGHT)
            elif exif[orientation] == 8:
                img = img.rotate(90, expand=True)
        except (AttributeError, KeyError, IndexError):
            # cases: image doesn't have getexif method or no exif data
            pass
        return img


    def on_img_stretch(self, event):
        '''
        MyScale控件数值改变的响应事件
        '''

        if not DrawingManager.validate_drawing():
            return

        if self.scale_enabled.get():
            l, m, u = self.my_scale.get_values()
            l = int(l*255/100)
            m = int(m*255/100)
            u = int(u*255/100)

            DrawingManager.set_stretch_info(True, [l,m,u])

        return
    

    def display_maxmin_strech(self):
        '''
        to do...
        '''
        if 0 and  self.image_on_canvas is not None:
            self.canvas.delete(self.image_on_canvas)

            max_wv_value = np.repeat(np.max(self.showing_img, axis=0, keepdims=True),repeats=self.img_info.hdr.bands,axis=0)
            min_wv_value = np.repeat(np.min(self.showing_img, axis=0, keepdims=True),repeats=self.img_info.hdr.bands,axis=0)

            self.showing_img = (self.showing_img-min_wv_value).astype(np.float32)*255
            delta = max_wv_value-min_wv_value

            self.showing_img[self.showing_img>0] = self.showing_img[self.showing_img>0]/delta[self.showing_img>0]
            self.showing_img = np.clip(self.showing_img, 0, 255)
            self.showing_img = self.showing_img.astype(np.uint8)

            
            if self.wave_selected >=0:
                pil_image = Image.fromarray(self.showing_img[self.wave_selected,:,:])
            else:
                pil_image = Image.fromarray(self.showing_img[[self.r_index, self.g_index, self.b_index],:,:].transpose(1,2,0))
        
            self.image_tk = ImageTk.PhotoImage(pil_image)
            self.image_on_canvas = self.canvas.create_image(0, 0, anchor="nw", image=self.image_tk)
            self.canvas.tag_lower(self.image_on_canvas)
            self.canvas.config(scrollregion=self.canvas.bbox("all"))
        pass

    


    # event.x,event.y 是相对于绑定事件的控件的左上角的坐标
    # event.x_root, event.y_root 是相对于屏幕的左上角的坐标（注意：不是应用程序窗口左上角）
    # canvas上的绘制需要基于event的xy坐标进行
    def on_mouse_clicked(self, event):

        if not DrawingManager.validate_drawing():
            return

        if self.op_selection.get() in [RoiType.OP_ROI_POINT, RoiType.OP_ROI_POLYGON, RoiType.OP_ROI_RECT]:
            if len(self.label_name_listbox.curselection()) == 0:
                messagebox.showwarning("提示", "标注之前请先选择标签！")
                return
            
        if self.op_selection.get() in [RoiType.OP_SAMPLE_POINT, RoiType.OP_SAMPLE_RECT, RoiType.OP_SAMPLE_POLYGON]:  
            # 判断是否按住Ctrl键
            if win32api.GetKeyState(win32con.VK_CONTROL) < 0:
                color = self.color_toolbar.get_next_color_hex()
                pass
            else:
                color = self.color_toolbar.get_current_color_hex()
            pass

            ShapeManager.sample_current_color = color
        
        DrawingManager.on_mouse_left_clicked(event)

        return


    def on_mouse_dragging(self, event):
        '''
        矩形绘制过程
        或者手动拖动图片的动作
        '''
        if not DrawingManager.validate_drawing():
            return
        
        if self.op_selection.get() not in [RoiType.OP_HAND, 
                                           RoiType.OP_ROI_RECT, RoiType.OP_TRUTH_RECT, RoiType.OP_SAMPLE_RECT,
                                           RoiType.OP_CLIP_RECT, RoiType.OP_AUTO_ROI_REGION]:
            return

        DrawingManager.on_mouse_dragging(event)
        
        return
     

    def on_mouse_released(self, event):
        '''
        
        '''

        ret = DrawingManager.on_mouse_released(event)
        if ret is not None:
            id = ret[0]
            pos_list = ret[1]
            if self.op_selection.get() == RoiType.OP_ROI_POINT:
                item = self.set_label_listbox_item(ShapeManager.current_label_name, id, ShapeType.point)
                self.label_listbox.insert(tk.END,  item)
            elif self.op_selection.get() in [RoiType.OP_ROI_RECT]:
                item = self.set_label_listbox_item(ShapeManager.current_label_name, id, ShapeType.rect)
                self.label_listbox.insert(tk.END,  item)
            # elif self.op_selection.get() == RoiType.OP_TRUTH_RECT:
            #     self.truth_listbox.insert(tk.END,  f"{ShapeManager.current_label_name}-{str(ret)}-Rect")
            elif self.op_selection.get() == RoiType.OP_SAMPLE_POINT:
                item = self.set_sample_listbox_item('', id, ShapeType.point)
                self.samples_listbox.insert(tk.END,  item)
            elif self.op_selection.get() == RoiType.OP_SAMPLE_RECT:
                item = self.set_sample_listbox_item('', id, ShapeType.rect)
                self.samples_listbox.insert(tk.END, item)
            elif self.op_selection.get() == RoiType.OP_AUTO_ROI_REGION:
                pass
            elif self.op_selection.get() == RoiType.OP_CLIP_RECT:
                cur_dir, cur_filename = os.path.split(self.current_file_path)
                filename, ext = os.path.splitext(cur_filename)
                clip_filename = filename+"_clip.img"

                if self.history_saving_dir:
                    initialdir = self.history_saving_dir
                else:
                    initialdir=cur_dir
                file_path = filedialog.asksaveasfilename(title="保存截图", confirmoverwrite=True, defaultextension='.img', 
                                                    filetypes=[('img file', '.img')],
                                                    initialdir=initialdir, initialfile=clip_filename)
    
                if file_path:
                    self.history_saving_dir = os.path.dirname(file_path)
                    if ImgDataManager.clip_save(file_path, ret[1]):
                        messagebox.showinfo('保存成功', f"截取img成功保存到{file_path}")
                    else:
                        messagebox.showerror('保存失败', "截取img保存失败")

            self.redraw_fig_canvas()
        return

    
    def on_mouse_double_clicked(self, event):
        '''
        绘制多边形的结束动作
        '''

        id = DrawingManager.on_mouse_double_clicked(event)
        if id is not None:
            if self.op_selection.get() in [RoiType.OP_ROI_POLYGON]:
                item = self.set_label_listbox_item(ShapeManager.current_label_name, id, ShapeType.polygon)
                self.label_listbox.insert(tk.END,  item)
            elif self.op_selection.get() == RoiType.OP_SAMPLE_POLYGON:
                item = self.set_sample_listbox_item('', id, ShapeType.polygon)
                self.samples_listbox.insert(tk.END,  item)
        
            self.redraw_fig_canvas()
        return
    

    def on_mouse_right_clicked(self, event):
        '''
        绘制多边形的取消动作
        '''
        if not DrawingManager.validate_drawing():
            return
        
        DrawingManager.on_mouse_right_clicked(event)
        return
    

    def on_zoom(self, scale_type='restore'):
        '''
        scale_type: 'restore', 'zoomin', 'zoomout
        '''
        
        if not DrawingManager.validate_drawing():
            return
               
        DrawingManager.on_zooming(scale_type)
        self.statusbar_set_image_size()
        
        return
    

    def on_mouse_wheel(self, event):
        if not DrawingManager.validate_drawing():
            return
        
        #  检查Ctrl键是否按下
        if win32api.GetKeyState(win32con.VK_CONTROL) < 0:
            # Ctrl键按下，处理事件
            # print("Ctrl + 鼠标滚轮事件被触发")
            # Adjust the scale factor based on the OS and event details
            if event.num == 4 or event.delta > 0:  # For Linux or Windows/Mac scroll up
                self.on_zoom(scale_type='zoomin')
            elif event.num == 5 or event.delta < 0:  # For Linux or Windows/Mac scroll down
                self.on_zoom(scale_type='zoomout')
            else:
                pass
            
        return
    

    def on_mouse_move(self, event):
        '''
        在状态栏显示鼠标位置的图像真实坐标，以及单通道像素灰度值
        '''

        if not DrawingManager.validate_drawing():
            return

        r,c = DrawingManager.canvas_event_to_img_rc(event)
        if r>=0 and c>=0 :
            self.statusbar_set_position(c, r)

            # 在状态栏显示单波段像素值
            wave_selected = self.get_selected_index_of_listbox(self.spectral_listbox)
            if wave_selected >= 0:
                gray = ImgDataManager.img_info.get_img_by_channels([wave_selected])
                gray = gray.reshape((ImgDataManager.img_info.hdr.lines, -1))
                v = gray[r,c]
                self.statusbar_set_tip(f"{v}")
            else:
                self.statusbar_set_tip()

        else:
            self.statusbar_set_position()
            self.statusbar_set_tip()
        
        return

    
    def on_save_label_file(self):
        '''
        保存当前标注信息到标注文件
        '''
        
        if self.current_file_path is None:
            return
        
        if self.label_listbox.size()==0:
            return
        
        cur_dir, cur_filename = os.path.split(self.current_file_path)
        filename, ext = os.path.splitext(cur_filename)
        label_filename = filename+".txt"

        if self.history_saving_dir:
            initialdir = self.history_saving_dir
        else:
            initialdir=cur_dir

        file_path = filedialog.asksaveasfilename(title="保存标注", confirmoverwrite=True, defaultextension='.txt', 
                                                filetypes=[('txt file', '.txt'), ('json file', '.json')],
                                                initialdir=initialdir, initialfile=label_filename)
    
        if file_path:
            
            self.history_saving_dir = os.path.dirname(file_path)
            _, ext = os.path.splitext(file_path)
            
            if ext == '.txt':            
                ShapeManager.label_save_to_txt_file(file_path)
                messagebox.showinfo("保存标签到文本文件", f"标签成功保存到文本文件{file_path}！")
            elif ext == '.json':
                ShapeManager.label_save_to_json_file(file_path)
                messagebox.showinfo("保存标签到json文件", f"标签成功保存到json文件{file_path}！")
        
        return


    def on_load_label_file(self):
        '''
        加载标注文件，绘制图形到canvas
        '''
        if self.current_file_path:
            cur_dir, cur_filename = os.path.split(self.current_file_path)

            file_path = filedialog.askopenfilename(defaultextension='.txt', 
                                                    filetypes=[('txt file', '.txt'), ('json file', '.json')],
                                                    initialdir=cur_dir)
            if file_path:
                print(file_path)
                self.load_label_from_file(file_path)  

        else:
            messagebox.showinfo("打开标签文件错误", message="请先打开图片文件!")


    def save_points_to_img(self):
        '''
        将样本点保存为img文件（待处理）
        '''

        if self.current_file_path and self.label_listbox.size()>0:
            cur_dir, cur_filename = os.path.split(self.current_file_path)
            filename, ext = os.path.splitext(cur_filename)
            label_filename = filename+"_label.img"

            if self.history_saving_dir:
                initialdir = self.history_saving_dir
            else:
                initialdir=cur_dir

            file_path = filedialog.asksaveasfilename(title="保存样本点", confirmoverwrite=True, defaultextension='.img', 
                                                    filetypes=[('img file', '.img')],
                                                    initialdir=initialdir, initialfile=label_filename)
       
            if file_path:
                self.history_saving_dir = os.path.dirname(file_path)
                return

    

    def on_create_dataset_from_filelist(self):
        '''
        在文件列表中，对于存在label文件的文件，读取信息后，提取roi样本
        保存为标签名相关的img和hdr文件
        '''
        roi_path_list = []   
        
        common_hdr_info = HDRInfo()
        for imgfile in self.file_path_list:
            name, ext = os.path.splitext(imgfile)
            hdr_path = name + ".hdr"
            json_path = name + ".json"
            if not os.path.exists(json_path):
                continue
            
            # 判断各个img的兼容性
            if len(roi_path_list) == 0:
                common_hdr_info.parse_hdr_info(hdr_path)
                pass
            else:
                this_hdr_info = HDRInfo()
                this_hdr_info.parse_hdr_info(hdr_path)
                if this_hdr_info.bands != common_hdr_info.bands:
                    messagebox.showwarning("创建数据集错误", message="img文件bands数量不一致")
                    return
                if this_hdr_info.wavelength != common_hdr_info.wavelength:
                    messagebox.showwarning("创建数据集错误", message="波段不一致")
                    return
                pass

            roi_path_list.append((imgfile, hdr_path, json_path))

        if len(roi_path_list) == 0:
            messagebox.showwarning("创建数据集错误", message="roi配置文件不存在！")
            return

        self.dataset.create_dataset_from_json_labels(roi_path_list, common_hdr_info)

        if len(self.dataset.class_info_dict) > 0 :

            dir_path = filedialog.askdirectory(title="保存数据集")
            for label in self.dataset.class_info_dict:

                img_file_name = label + ".img"
                img_path = os.path.join(dir_path, img_file_name)

                img = self.dataset.class_info_dict[label].img
                shp = img.shape
                img = img.reshape((shp[0], 1, shp[1]))

                thishdr = copy.deepcopy(common_hdr_info)
                thishdr.samples = 1
                thishdr.lines   = shp[0]
                thishdr.interleave = 'bip'
                thishdr.set_user_defined_param("class_name", label)

                save_img(img, img_path, thishdr)

                pass

        messagebox.showwarning("创建数据集成功", message=f"创建数据集成功！{len(self.dataset.class_info_dict)}个类别")
        pass


    def on_create_dataset_from_current_labels_points(self):
        '''
        对于当前打开的img所加载的label和point，提取谱线数据，
        根据标签，保存为不同的数据集
        '''

        if self.current_file_path is None:
            return
        
        dir_path = filedialog.askdirectory(title="选择数据集文件夹路径", initialdir=os.path.dirname(self.current_file_path))
       
        if dir_path:

            ShapeManager.label_save_as_dataset(dir_path)

            messagebox.showwarning("创建数据集成功", message=f"创建数据集成功！")

        pass



    def on_load_dataset(self):


        pass


    def on_load_ds_from_dir(self):
        '''
        兼容官方的加载数据集接口。递归读取文件夹中的img和hdr文件加载
        '''

        if self.wnd_create_model is not None:
            messagebox.showwarning("建模", message=f"建模窗口已经打开！")
            return
        
        dir_path = filedialog.askdirectory(title="选择数据集文件夹路径") 
        if dir_path:
            
            if  not self.dataset.empty():
                self.dataset.clear()

            self.dataset.load_dataset_in_dir(dir_path)

            # self.update_dataset_info_ui()

            self.wnd_create_model = WindowCreateModel(self.dataset, self.root)
            self.wnd_create_model.protocol("WM_DELETE_WINDOW", self.on_wnd_createmodel_closing)

        pass


    def on_wnd_createmodel_closing(self):
        self.wnd_create_model.destroy()
        self.wnd_create_model = None
        pass


    def update_dataset_info_ui(self):

        for ui in self.dataset_ui_dict.values():
            for ui_item in ui:
                ui_item.destroy()
        
        self.model_ui_dict.clear()
        self.class_checkbtn_enabled.clear()

        for i, classname in enumerate(self.dataset.class_info_dict):

            color = rgb_tuple_2_hexstr(self.dataset.class_info_dict[classname].color)
            lb_class = tk.Label(self.dataset_info_tab, text=classname, bg=color)
            samplenum = self.dataset.class_info_dict[classname].img.shape[0]
            lb_samplenum = tk.Label(self.dataset_info_tab, text=str(samplenum))
            # entry_thres = tk.Entry(self.dataset_info_tab)
            # entry_thres.insert(0, str(thres))
            # entry_superclass = tk.Entry(self.panel_model_info)
            # entry_superclass.insert(0, str(superclassidx))
            # lb_cluster = tk.Label(self.panel_model_info, text=str(clusternum))
            # self.class_checkbtn_enabled[classname] = tk.IntVar()
            # ck_enabled = tk.Checkbutton(self.panel_model_info, text="", variable=self.class_checkbtn_enabled[classname])
            # ck_enabled.select()
            # ck_enabled.getvar()
            lb_class.grid(row=i+1, column=0)
            lb_samplenum.grid(row=i+1, column=1)
            # entry_superclass.grid(row=i+1, column=2)
            # lb_cluster.grid(row=i+1, column=3)
            # ck_enabled.grid(row=i+1, column=4)

            self.dataset_ui_dict[classname] = (lb_class, lb_samplenum)

        self.info_notebook.select(2)

        pass


    # def on_clear_dataset(self):
    #     '''
        
    #     '''
    #     pass


    def on_load_model(self):
        '''
        加载sam模型
        '''
        if not self.sam_model.empty():
            answer = messagebox.askyesno("模型加载确认", "已经存在加载的模型，是否先清空模型？",
                                         default=messagebox.YES)
            if answer:
                self.on_clear_model()

        # init_dir = self.history_model_dir if self.history_model_dir else os.path.curdir
        file_path = filedialog.askdirectory(title="选择模型路径",)    
        if file_path:
            print(file_path)
            self.history_model_dir = file_path
            self.sam_model.load_model_in_dir(file_path)
            self.update_model_info_ui()
            self.statusbar_set_info(f"模型加载成功！{file_path}")

        pass


    def update_model_info_ui(self):
        '''
        将模型信息渲染到界面上
        '''

        for model_ui in self.model_ui_dict.values():
            for model_ui_item in model_ui:
                model_ui_item.destroy()
        
        self.model_ui_dict.clear()
        self.class_checkbtn_enabled.clear()

        for i, classname in enumerate(self.sam_model.class_info_dict):

            color = rgb_tuple_2_hexstr(self.sam_model.class_info_dict[classname].class_color)
            thres = self.sam_model.class_info_dict[classname].sam_threshold
            superclassidx = self.sam_model.class_info_dict[classname].super_class_index
            clusternum = self.sam_model.class_info_dict[classname].cluster_num
            enabled = self.sam_model.class_info_dict[classname].enabled
            
            lb_class = tk.Label(self.panel_model_info, text=classname, bg=color, width=10)
            entry_thres = tk.Entry(self.panel_model_info, width=10)
            entry_thres.insert(0, str(thres))
            entry_superclass = tk.Entry(self.panel_model_info, width=10)
            entry_superclass.insert(0, str(superclassidx))
            lb_cluster = tk.Label(self.panel_model_info, text=str(clusternum), width=10)
            self.class_checkbtn_enabled[classname] = tk.IntVar()
            ck_enabled = tk.Checkbutton(self.panel_model_info, text="", variable=self.class_checkbtn_enabled[classname], width=10)
            if enabled:
                ck_enabled.select()
            # ck_enabled.getvar()
            lb_class.grid(row=i+1, column=0, padx=2)
            entry_thres.grid(row=i+1, column=1, padx=2)
            entry_superclass.grid(row=i+1, column=2, padx=2)
            lb_cluster.grid(row=i+1, column=3, padx=2)
            ck_enabled.grid(row=i+1, column=4, padx=2)

            self.model_ui_dict[classname] = (lb_class, entry_thres, entry_superclass, lb_cluster, ck_enabled)

        self.info_notebook.select(1)

        pass


    def preprocess_before_predict(self):
        '''
        从界面获取各个类别的使能状态，门限设置和超类设置；
        以及光强门限
        '''
        class_info_setting = {}

        if self.var_amp_check.get():
            self.sam_model.set_params(amp_thres=self.var_amp_thres.get())
        else:
            self.sam_model.set_params(amp_thres=-1)

        if not self.var_use_default_model_params.get():
            for classname in self.model_ui_dict:
                clsinfo = ClassInfo(classname)
                clsinfo.enabled = self.class_checkbtn_enabled[classname].get()
                clsinfo.sam_threshold = float(self.model_ui_dict[classname][1].get())
                clsinfo.super_class_index = int(self.model_ui_dict[classname][2].get())

                class_info_setting[classname] = clsinfo

        self.sam_model.predict_init(class_info_setting)

        pass


    def on_clear_model(self):

        self.sam_model.clear()

        for model_ui in self.model_ui_dict.values():
            for model_ui_item in model_ui:
                model_ui_item.destroy()

        self.model_ui_dict.clear()
        self.class_checkbtn_enabled.clear()
        pass

    
    def show_model_info(self):
        '''
        显示模型信息
        '''


        pass      


    def on_detect_image_list(self):
        if self.image_listbox.size() == 0:
            return

        dir_path = filedialog.askdirectory(title="保存推理结果", 
                                            initialdir=os.path.dirname(self.current_file_path))
       
        if dir_path:

            # 创建保存结果的文件夹
            now = datetime.now()
            formatted_time = now.strftime("%Y%m%d%H%M%S")
            result_dir = os.path.join(dir_path, "result_" + formatted_time)
            if not os.path.exists(result_dir):
                os.makedirs(result_dir)

            self.preprocess_before_predict()

            if 0:
            
                for filepath in self.file_path_list:

                    result_img = self.sam_model.predict_img(filepath)

                    if result_img is None:
                        continue

                    basename = os.path.basename(filepath)
                    name, ext = os.path.splitext(basename)
                    result_filepath = os.path.join(result_dir, name + ".jpg")
                    
                    # 使用PIL保存图像
                    img = Image.fromarray(result_img, 'RGB')
                    img.save(result_filepath)

                    print(f"{result_filepath} saved!")

            else:
                self.count = 0
                progress_dialog = PredictProgressDialog(self, result_dir=result_dir, sam_model=self.sam_model,
                                                        file_path_list=self.file_path_list, master=root,
                                                        title="推理进度")

                self.root.wait_window(progress_dialog)
                print("done! ", self.count)

                pass    
            
            pass

        pass


    def on_detect_current_image(self):
        if self.current_file_path is None:
            return
        
        self.preprocess_before_predict()

        if 0:    
            self.result_img = self.sam_model.predict_img(self.current_file_path)

            
        else:
            ret, _ = ImgInfo.img_path_valid(self.current_file_path)
            if not ret:
                messagebox.showerror("错误", f"img文件{self.current_file_path}非法！")
                return
        
            img_info = ImgInfo()
            img_info.create_img_info(self.current_file_path)
            
            img = img_info.get_img()

            input_img = ImgInfo.img_transpose_by_interleave(img, img_info.hdr.interleave, 'bip')
            input_img = input_img.astype(np.float32)
            input_img = self.sam_model.process_img_wave_3d(input_img, img_info.hdr.wavelength)

            self.sam_model.init_cache_cols(img_info.hdr.lines)

            self.finish = False
            self.result_img = None
            progress_dialog = PredictOneImgProgressDialog(self, sam_model=self.sam_model,
                                                        input_img=input_img, file_path=self.current_file_path,
                                                        master=self.root,
                                                        title="推理进度")

            self.root.wait_window(progress_dialog)

            if not self.finish:
                messagebox.showinfo("错误", "当前img文件推理中断！")
                
        
        WindowShowImage(file_path=self.current_file_path, image= self.result_img, master=self.root)

        return
    

    def on_detect_image_dir(self):

        dir_path = filedialog.askdirectory(title="选择推理文件夹路径")    
        
        img_file_list = []

        if dir_path:
            for filename in os.listdir(dir_path):
                filepath = os.path.join(dir_path, filename)
                if os.path.isdir(filepath):
                    continue
                
                ret, _ = ImgInfo.img_path_valid(filepath)
                if not ret:
                    continue

                img_file_list.append(filepath)

        if len(img_file_list) == 0:
            messagebox.showwarning("警告", "文件夹没有可推理的img文件")
            return
        
        # 创建保存结果的文件夹
        now = datetime.now()
        formatted_time = now.strftime("%Y%m%d%H%M%S")
        result_dir = os.path.join(dir_path, "result_" + formatted_time)
        if not os.path.exists(result_dir):
            os.makedirs(result_dir)

        self.preprocess_before_predict()

        if 0:        
            count = 0        
            for file_path in img_file_list:

                result_img = self.sam_model.predict_img(file_path)

                if result_img is None:
                    continue
                
                basename = os.path.basename(file_path)
                name, ext = os.path.splitext(basename)
                result_filepath = os.path.join(result_dir, name + ".jpg")

                # 使用PIL保存图像
                img = Image.fromarray(result_img, 'RGB')
                img.save(result_filepath)

                print(f"{result_filepath} saved!")
                count += 1

            messagebox.showinfo("文件夹推理", f"完成推理，一共推理{count}个img文件！")
        
        else:
            self.count = 0
            progress_dialog = PredictProgressDialog(self, result_dir=result_dir, sam_model=self.sam_model,
                                                    file_path_list=img_file_list, master=self.root,
                                                    title="推理进度")

            self.root.wait_window(progress_dialog)
            print("done! ", self.count)

            pass

        pass  


    def on_detect_image_file(self):
        '''
        选择一个文件夹中的1或多个img文件进行推理
        '''

        file_choose_list = filedialog.askopenfilenames(title="选择img文件", defaultextension='.img', 
                                               initialdir=self.history_open_dir,
                                               filetypes=[('img file', '.img')])    
        # 点取消：file_path_list为''， 否则返回一个元组，其中文件路径为绝对全路径
        if file_choose_list == '':
            return
        
        img_file_list = []
        for file_path in file_choose_list:
            ret, _ = ImgInfo.img_path_valid(file_path)
            if not ret:
                continue
            img_file_list.append(file_path)
        
        if len(img_file_list) == 0:
            messagebox.showwarning("警告", "没有选择可推理的img文件")
            return

        self.preprocess_before_predict()
        
        if len(img_file_list)  == 1:
            
            ret, _ = ImgInfo.img_path_valid(img_file_list[0])
            if not ret:
                messagebox.showerror("错误", f"img文件{img_file_list[0]}非法！")
                return
        
            img_info = ImgInfo()
            img_info.create_img_info(img_file_list[0])
            
            img = img_info.get_img()

            input_img = ImgInfo.img_transpose_by_interleave(img, img_info.hdr.interleave, 'bip')
            input_img = input_img.astype(np.float32)
            input_img = self.sam_model.process_img_wave_3d(input_img, img_info.hdr.wavelength)

            self.sam_model.init_cache_cols(img_info.hdr.lines)

            self.finish = False
            self.result_img = None
            progress_dialog = PredictOneImgProgressDialog(self, sam_model=self.sam_model,
                                                        input_img=input_img, file_path=img_file_list[0],
                                                        master=self.root,
                                                        title="推理进度")

            self.root.wait_window(progress_dialog)

            if not self.finish:
                messagebox.showinfo("错误", "当前img文件推理中断！")
                return

            WindowShowImage(file_path=self.current_file_path, image= self.result_img, master=self.root)

            return
        
         # 创建保存结果的文件夹
        dir_path = os.path.dirname(file_choose_list[0])
        now = datetime.now()
        formatted_time = now.strftime("%Y%m%d%H%M%S")
        result_dir = os.path.join(dir_path, "result_" + formatted_time)
        if not os.path.exists(result_dir):
            os.makedirs(result_dir)

        if 0:
            count = 0
            for i, file_path in enumerate(img_file_list):

                result_img = self.sam_model.predict_img(file_path)

                if result_img is None:
                    continue

                basename = os.path.basename(file_path)
                name, ext = os.path.splitext(basename)
                result_filepath = os.path.join(result_dir, name + ".jpg")

                # 使用PIL保存图像
                img = Image.fromarray(result_img, 'RGB')
                img.save(result_filepath)

                print(f"{result_filepath} saved!")
                count += 1

            messagebox.showinfo("文件推理结果", f"完成推理，一共推理{count}个img文件！")

        else:

            self.count = 0
            progress_dialog = PredictProgressDialog(self, result_dir=result_dir, sam_model=self.sam_model,
                                                    file_path_list=img_file_list, master=self.root,
                                                    title="img文件推理进度")
            
            self.root.wait_window(progress_dialog)
            print("done! ", self.count)
            pass


        pass


    def reset_default_model_params(self):

        pass


    def save_as_model_params(self):

        pass


    def on_read_oil_params(self):

        file_path = filedialog.askopenfilename(defaultextension='.json', 
                                                    filetypes=[('json file', '.json')],
                                                    initialdir=os.path.curdir)
        if file_path:
            ret, info = ImgDataManager.read_oil_params(file_path)
            if not ret: 
                messagebox.showerror("原油配置参数读取错误", info)
                return
            
            messagebox.showinfo("原油配置参数", info)

        pass



    
    def toggle_auto_align(self):

        if self.var_auto_align.get() and ImgDataManager.arr_align_conf is None:
            if self.read_alignment_conf():
                ImgDataManager.set_auto_align(True)
            else:
                ImgDataManager.set_auto_align(False)
            return
        
        ImgDataManager.set_auto_align(self.var_auto_align.get())
        return


    def read_alignment_conf(self):
        file_path = filedialog.askopenfilename(title="选择对齐配置文件", defaultextension='.conf', 
                                                    filetypes=[('conf file', '.conf'), ('all file', '.*')])
        if file_path:
            print(file_path)
            ret = ImgDataManager.set_align_config(file_path)
            if ret is not None: 
                messagebox.showinfo("读取成功", f"对齐配置读取成功！\n{ImgDataManager.arr_align_conf}")
                return True
            else:
                messagebox.showerror("读取错误", f"对齐配置读取错误! {file_path}")
        
        return False


    def on_align_current_img(self, align_req=True):
        '''
        对当前img进行对齐操作
        '''

        if ImgDataManager.arr_align_conf is None:
            messagebox.showwarning("警告", message="当前不存在对齐配置信息！")
            return
        
        if align_req == ImgDataManager.img_align_state:
            messagebox.showwarning("警告", message= f"{'已经' if align_req else '未'}进行了对齐操作！")
            return

        if not messagebox.askyesno(title="确认", message=f"确定要进行{'' if align_req else '取消'}对齐操作？操作将清除当前文件的样本点！",
                                   default=messagebox.YES):
            return
        
        # 清除当前文件采样点
        if ShapeManager.current_file_path in ShapeManager.filepath_sample_id_list_dict:
            id_list = copy.copy(ShapeManager.filepath_sample_id_list_dict[ShapeManager.current_file_path])
            if len(id_list) > 0:
                ShapeManager.sample_delete(id_list)

                index_list = self.get_sample_listbox_index_from_id(id_list)
                index_list.sort(reverse=True)
                for index in index_list:
                    self.samples_listbox.delete(index)
        
        self.reset_transform()
        ImgDataManager.reset_wavelength_info()
        self.load_wavlength()
        
        ImgDataManager.align_img(align_req)
        
        DrawingManager.show_img()
        self.redraw_fig_canvas()
        
        return
    

    # def reset_align_current_img(self):
    #     '''
    #     取消对齐操作
    #     '''
    #     if not ImgDataManager.img_align_state:
    #         messagebox.showwarning("警告", message="当前img并未进行过对齐操作！")
    #         return

    #     if not messagebox.askyesno(title="确认", message="确定要取消对齐操作？操作将清除当前文件的样本点！",
    #                                default=messagebox.YES):
    #         return
        
    #     # 清除当前文件采样点
    #     if ShapeManager.current_file_path in ShapeManager.filepath_sample_id_list_dict:
    #         id_list = ShapeManager.filepath_sample_id_list_dict[ShapeManager.current_file_path]
    #         if len(id_list) > 0:
    #             ShapeManager.sample_delete(id_list)

    #     self.reset_transform()
    #     ImgDataManager.reset_wavelength_info()
    #     self.load_wavlength()
        
    #     ImgDataManager.align_img(False)
        
    #     DrawingManager.show_img()
    #     self.redraw_fig_canvas()
        
    #     return
    

    def reset_transform(self):

        self.var_trans_binning_enabled.set(value=False)
        self.var_trans_norm.set(value=False)
        self.combo_transform.current(0)
        self.var_gain_enabled.set(value=False)

        return



    def on_save_current_align_img(self):

        if ImgDataManager.arr_align_conf is None:
            messagebox.showerror("错误", "未读取对齐配置！")
            return

        cur_parent_dir = os.path.dirname(self.current_file_path)
        basename = os.path.basename(self.current_file_path)
        name, _ = os.path.splitext(basename)
        save_file_name = name + "_aligned.img"
        
        file_path = filedialog.asksaveasfilename(title="保存img文件", confirmoverwrite=True, defaultextension='.img', 
                                                    filetypes=[('img file', '.img')],
                                                    initialdir=cur_parent_dir, initialfile=save_file_name)
       
        if file_path:
            self.history_saving_dir = os.path.dirname(file_path)
            
            ImgDataManager.save_aligned_img(file_path)

            messagebox.showinfo("保存完成", f"对齐img文件保存到{file_path}！")

        return
    

    def toggle_gain_expo_time(self):
        '''
        启动增益曝光时间校正，重绘样本点wave
        '''
        if self.current_file_path is None:
            return
        
        if self.var_gain_enabled.get():
            if ImgDataManager.arr_gain is None or ImgDataManager.arr_expo_time is None:
                messagebox.showerror("错误", "当前img文件不存在曝光和增益相关字段！")
                return
        
        ImgDataManager.img_gain_adjust(self.var_gain_enabled.get())
        
        self.redraw_fig_canvas()
        return
    

    def on_save_samples_wave(self):
        '''
        保存当前文件的样本点波形数据到文本文件
        '''

        if self.current_file_path is None:
            return

        if self.current_file_path in ShapeManager.filepath_sample_id_list_dict:
            if len(ShapeManager.filepath_sample_id_list_dict[self.current_file_path]) == 0:
                messagebox.showwarning("保存波形数据", f"当前文件未绘制样本点。{self.current_file_path}")   
                return
        
        if ImgDataManager.arr_align_conf is not None and not ImgDataManager.img_align_state:
            answer = messagebox.askyesno("图像对齐", "当前图像未进行对齐操作，是否继续？")   
            if not answer:
                return

        if self.samples_listbox.size()>0:
            cur_parent_dir = os.path.dirname(self.current_file_path)
            basename = os.path.basename(self.current_file_path)
            name, _ = os.path.splitext(basename)

            save_file_name = name + "_samples_wave.txt"
            
            file_path = filedialog.asksaveasfilename(title="保存文件路径", confirmoverwrite=True, defaultextension='.txt', 
                                                        filetypes=[('txt file', '.txt')],
                                                        initialdir=cur_parent_dir, initialfile=save_file_name)
       
            if file_path:
                
                ShapeManager.save_samples_wave_to_file(file_path)

                messagebox.showinfo("保存文件", f"样本点波形数值成功保存到{file_path}")           
                pass

        return


    def on_save_samples_info_to_json(self):

        if self.samples_listbox.size() == 0:
            return

        file_path = filedialog.asksaveasfilename(title="保存为json文件", confirmoverwrite=True, defaultextension='.json', 
                                                    filetypes=[('json file', '.json')])
        if file_path:
            
            ShapeManager.save_samples_info_to_json(file_path)

            messagebox.showinfo("保存文件", f"样本点信息成功保存到{file_path}")           
            pass

        return
    

    def on_load_samples_info_from_json(self):

        file_path = filedialog.askopenfilename(title="选择样本点信息文件", defaultextension='.json', 
                                                    filetypes=[('json file', '.json')])
        if file_path:
           
            with open(file_path, 'r' ,encoding='utf-8') as f:
                sample_file_path_list, sample_id_list = ShapeManager.load_samples_info_from_json(file_path)

            if len(sample_file_path_list) == 0 or len(sample_id_list) == 0:
                messagebox.showerror("载入样本失败", f"读取样本信息失败！")
                return
            
            for sample_file_path in sample_file_path_list:
                if sample_file_path not in self.file_path_list:
                    self.image_listbox.insert(tk.END, sample_file_path)
                    self.file_path_list.append(sample_file_path)
                    self.file_path_dict[sample_file_path] = '.img'
            
            cur_file_path = sample_file_path_list[0]
            for index in range(self.image_listbox.size()): 
                item = self.image_listbox.get(index)
                if item == cur_file_path:
                    self.cur_file_selected_index = index
                    break
            
            self.image_listbox.selection_set(self.cur_file_selected_index)
            self.current_file_path = cur_file_path
            ImgDataManager.initial()
            self.load_current_file()
            
            id_list = []
            for id, shape in sample_id_list:
                item = self.set_sample_listbox_item("", id, shape)
                self.samples_listbox.insert(tk.END, item)
                id_list.append(id)

            ShapeManager.draw_shape_id_list_wave(id_list)
            messagebox.showinfo("载入成功", f"读取样本信息成功！载入{len(sample_file_path_list)}个文件")
        return


    def toggle_auto_load_label_type(self):
        '''
        切换自动加载标注文件的类型的响应函数
        '''

        pass



    def toggle_point_sam_dist(self):
        # ROIManager.g_show_point_sam_dist = self.point_sam_dist_enabled.get()
        pass


    def on_closing(self):
        # 在这里执行清理工作或保存数据
        print("窗口正在关闭，执行清理工作...")
        # 确保关闭事件继续传播
        self.root.destroy()
        self.root.quit()

    
    def show_label_name_list_menubar(self, event):

        self.label_name_list_menubar.post(event.x + self.label_name_listbox.winfo_rootx(), event.y + self.label_name_listbox.winfo_rooty()) 

        pass

    
    def toggle_cache_enabled(self):

        if self.var_enable_cache.get():
            self.sam_model.cache_cols = self.var_cache_cols
            self.sam_model.cache_pixs = self.var_cache_pixs
        else:
            self.sam_model.cache_cols = 0

    
    def read_whiteboard(self):

        file_path = filedialog.askopenfilename(title="选择白板文件", defaultextension='.tif', 
                                                    filetypes=[('tif file', '.tif'), ('all file', '.*')])
        if file_path:
            self.arr_wb = read_tif(file_path)

            messagebox.showinfo("文件读取成功", f"读取白板信息成功！大小为{self.arr_wb.shape[0]}*{self.arr_wb.shape[1]}")

        return

    

    def show_img_distance_to_reference(self):
        '''
        弹出窗口显示图片上每个像素点和参考点之间的距离
        距离分为从0-1之间的十个区间，设置为不同的颜色
        '''

        return
    


    def set_tifs2img_rules(self):
        '''
        设置tif文件组合成img的文件名规则
        '''
        messagebox.showinfo("To do", "暂时写死即可")

        return


    def on_tifs2img(self):
        '''
        用于S800,将单波段TIF组合成img文件，并增加文件夹的名称到img文件名，删除tif文件
        '''
        
        folder_path = filedialog.askdirectory(title="选择tif文件夹", initialdir=self.history_open_dir)
        if folder_path:
            import re
            # tif_file = f"MAX_{i:04d}_{wave_list[j]}nm_D.tif"
            re_tif_file = r"MAX_(\d{4})_(\d{3})nm_D.tif"
            
            # def extract_four_digit_strings(input_string):
            #     # 使用正则表达式匹配连续4位的数字
            #     pattern = r'\d{' + f'{self.tif_index_digit_num}'+ '}'
            #     matches = re.findall(pattern, input_string)
            #     return matches

            index_tif_dict = {}
            for filename in os.listdir(folder_path):
                '''  
                ret = re.search(re_tif_file, filename)
                首先必须要搜索到整个pattern，然后才可以获取各组的信息
                None: 整个pattern未搜索到
                ret[0]: 'MAX_0001_450nm_D.tif'
                ret[1]:  '0001'
                ret[2]:  '450'
                ret.span(0):  (17, 37)
                ret.span(1):  (21, 25)
                ret.span(2):  (26, 29)
                ret.group(0):  'MAX_0001_450nm_D.tif'
                ret.group(1):  '0001'
                ret.group(2):'450'
                ret.groups(): ('0001', '450')
                '''
                ret = re.match(re_tif_file, filename)
                if ret:
                    if int(ret.group(2)) in self.tif_wv_list:
                        str_index = ret.group(1)
                        file_path = os.path.join(folder_path, filename)
                        if str_index in index_tif_dict:
                            index_tif_dict[str_index].append(file_path)
                        else:
                            index_tif_dict[str_index] = [file_path]

            pass

            tif2imgdlg = Tifs2ImgProgressDialog(self, self.tif_wv_list, folder_path,
                                                self.tif2img_filename_rule, index_tif_dict, self.root)
            self.root.wait_window(tif2imgdlg)

        return

    



    def on_read_oil_params(self):
        '''
        读取官方原油配置参数文件的信息
        '''

        file_path = filedialog.askopenfilename(defaultextension='.json', 
                                                    filetypes=[('json file', '.json')],
                                                    initialdir=os.path.curdir)
        if file_path:
            ret, info = self.label_manager.read_oil_params(file_path)
            if not ret: 
                messagebox.showerror("原油配置参数读取错误", info)
                return
            
            messagebox.showinfo("原油配置参数", info)

        pass


    def set_ui_state_with_img(self):

        if DrawingManager.validate_drawing():
            state_str = 'normal'

        else:
            state_str = 'disabled'
            pass

        self.viewmenu.entryconfig("放大", state=state_str)
        self.viewmenu.entryconfig("缩小", state=state_str)
        self.viewmenu.entryconfig("原始大小", state=state_str)
        self.viewmenu.entryconfig("亮度调节", state=state_str)
        self.viewmenu.entryconfig("查看波形大图", state=state_str)

        self.opmenu.entryconfig("移动工具", state=state_str)
        self.opmenu.entryconfig("绘制点样本", state=state_str)
        self.opmenu.entryconfig("绘制多边形样本", state=state_str)
        self.opmenu.entryconfig("绘制矩形标签", state=state_str)
        self.opmenu.entryconfig("绘制多边形标签", state=state_str)
        self.opmenu.entryconfig("绘制点标签", state=state_str)
        self.opmenu.entryconfig("截图保存", state=state_str)
        # self.opmenu.entryconfig("矩形真值", state=state_str)
        self.opmenu.entryconfig("绘制自动ROI有效范围", state=state_str)
        self.opmenu.entryconfig("清除自动ROI有效范围", state=state_str)

        self.autolabel_menu.entryconfig("自动生成ROI", state=state_str)
        self.autolabel_menu.entryconfig("创建多边形标签", state=state_str)
        self.autolabel_menu.entryconfig("清除自动ROI", state=state_str)
        self.autolabel_menu.entryconfig("保存为真值配置文件", state=state_str)
        self.autolabel_menu.entryconfig("保存为数据集", state=state_str)
        self.autolabel_menu.entryconfig("显示标签图层", state=state_str)

        return
    

    def set_label_listbox_item(self, classname:str, id:int, shape:str):

        return f"{classname.lower()}-{str(id)}-{shape.lower()}"
    

    def get_id_from_label_listbox(self, indexoritem, ret_classname=False):

        if isinstance(indexoritem, int):
            if 0<=indexoritem<self.label_listbox.size():
                item = self.label_listbox.get(indexoritem)
            else:
                if ret_classname:
                    return -1, ''
                return -1
        elif isinstance(indexoritem, str):
            item = indexoritem
        else:
            if ret_classname:
                return -1, ''
            return -1

        ll = item.split('-')
        if len(ll)>2:
            if ret_classname:
                return int(ll[1]), ll[0]
            return int(ll[1])
        
        return -1, ''
    

    def get_label_listbox_index_from_id(self, id):
        
        for index in range(self.label_listbox.size()):
            iid = self.get_id_from_label_listbox(index)
            if iid == id:
                return index
        else:
            return -1
        

    def set_sample_listbox_item(self, classname:str, id:int, shape:str):

        return f"{classname.lower()}-{str(id)}-{shape.lower()}"
    

    def get_id_from_sample_listbox(self, indexoritem):

        if isinstance(indexoritem, int):
            if 0<=indexoritem<self.samples_listbox.size():
                item = self.samples_listbox.get(indexoritem)
            else:
                return -1
        elif isinstance(indexoritem, str):
            item = indexoritem
        else:
            return -1

        ll = item.split('-')
        if len(ll)>2:
            return int(ll[1])
        
        return -1


    def get_sample_listbox_index_from_id(self, id_list):

        index_list = []
        for id in id_list:
            for index in range(self.samples_listbox.size()):
                iid = self.get_id_from_sample_listbox(index)
                if iid == id:
                    index_list.append(index)
        
        return index_list 


    def on_trans_binning(self):
        '''
        样本点波段聚合
        '''

        gap = self.var_trans_binning_value.get()
        self.spectral_listbox.delete(0, tk.END)

        ImgDataManager.set_binning_wave(enabled=self.var_trans_binning_enabled.get(), gap=gap)

        for wv in ImgDataManager.wave_enabled_list:
            self.spectral_listbox.insert(tk.END, wv)

        DrawingManager.on_data_transformed()
        
        self.redraw_fig_canvas()
        return


    def on_set_start_wv(self, event):


        ImgDataManager.set_wv_range()
        return


    def on_set_end_wv(self, event):

        ImgDataManager.set_wv_range()
        return
    

    def on_transform_select(self, event):
        
        index = self.combo_transform.current()
        if index == 0:
            ImgDataManager.use_diff = 0
        elif index == 1:
            ImgDataManager.use_diff = 1
        else:
            ImgDataManager.use_diff = 2

        DrawingManager.on_data_transformed()

        self.redraw_fig_canvas()
        
        return
    

    def get_selected_index_of_listbox(self, listbox:tk.Listbox, multi=False):
        '''
        Listbox没有条目选中的时候，curselection()返回结果为空元组()
        '''
        if multi:
            index = []
        else:
            index = -1

        if listbox.size() == 0:
            return index
        
        selection = listbox.curselection()
        if len(selection) == 0:
            return index
        
        if multi:
            return list(selection)
        else:
            return selection[0]
    


root = tk.Tk()
# root.geometry("800x600")
root.state("zoomed")
app = App(root)

# print(root.winfo_height(), root.winfo_width()) # 注：1,1 : 此时主窗口仍没有初始化
root.mainloop()
