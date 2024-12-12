import tkinter as tk
from tkinter import ttk
from tkinter import Toplevel, Canvas, Menu
from tkinter import filedialog, messagebox, simpledialog
from sam_dataset import SamDataset, DataInfo
from algos import (rgb_tuple_2_hexstr, spectral_angles, get_transkey_by_name,
                    TRANSFORMS_DEF, transform_process , sam_distance, read_tif)
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from MyFigureCanvasToolbar import FigureCanvasNavigationToolbar
import numpy as np
import datetime
import os
from PIL import Image
from sam_model import SamModel
from window_show_img import WindowShowImage
import cv2
import  win32api, win32con 
from MyDialogs import DlgShowTable

class WindowCreateModel(Toplevel):

    def __init__(self, dataset:SamDataset, master=None,  **kw):
        super().__init__(master, **kw)
        self.title("建模窗口")
        self.geometry("800x600")  # Initial size
        
        # Allow the window to be resized
        self.resizable(True, True)

        self.dataset = dataset
        self.sam_mode = None    # 用于临时推理的模型

        self.create_ui()
        self.create_ui_event_data()

        # 先计算默认的数据集标准谱线
        self.dataset.transform_updated()
        self.need_redraw_wave = True
        self.need_redraw_hist = True
        self.fig_hist = None

        self.arr_wb = None   # 白板信息矩阵


    def maximize_window(self):
        self.attributes("-zoomed", True)
        
    def minimize_window(self):
        self.iconify()


    def create_ui(self):
        
        self.center_notebook = ttk.Notebook(self)
        self.center_notebook.pack(side='top', expand=True, fill='both')

        self.process_tab = tk.Frame(self.center_notebook, bd=1) 
        self.center_notebook.add(self.process_tab, text='数据处理')

        self.spectral_panedwindow_tab = ttk.PanedWindow(self.center_notebook, orient="horizontal")
        self.center_notebook.add(self.spectral_panedwindow_tab, text='波形图')

        self.result_canvas_tab = tk.Frame(self.center_notebook) 
        self.center_notebook.add(self.result_canvas_tab, text='直方图')

        # 数据处理tab
        frame_left = ttk.Frame(self.process_tab)
        frame_left.pack(side="left", fill='y')
        frame_right = ttk.Frame(self.process_tab)
        frame_right.pack(side='left', fill='both', expand=1)
        
        lb_wv = tk.Label(frame_left, text="波段列表")
        self.listbox_wave = tk.Listbox(frame_left, selectmode=tk.SINGLE, exportselection=False)
        scrollbar_wavelist = tk.Scrollbar(frame_left, command=self.listbox_wave.yview)
        self.listbox_wave.configure(yscrollcommand=scrollbar_wavelist.set)
        lb_wv.grid(row=0, column=0, columnspan=2, sticky='W')
        self.listbox_wave.grid(row=1, column=0, sticky='NS')
        scrollbar_wavelist.grid(row=1, column=1,sticky='NS')
        frame_left.rowconfigure(0, weight=0)
        frame_left.rowconfigure(1, weight=1)


        frame_ds_operation = ttk.Frame(frame_right)
        frame_ds_operation.pack(side='top', fill='x')
        lb1 = tk.Label(frame_ds_operation, text="起始波段：")
        lb1.pack(side='left')
        self.var_start_wv = tk.DoubleVar()
        entry_start_wv = tk.Entry(frame_ds_operation, textvariable=self.var_start_wv)
        entry_start_wv.pack(side='left', padx=2)

        lb2 = tk.Label(frame_ds_operation, text="终止波段：")
        lb2.pack(side='left', padx=4)
        self.var_end_wv = tk.DoubleVar()
        entry_end_wv = tk.Entry(frame_ds_operation, textvariable=self.var_end_wv)
        entry_end_wv.pack(side='left', padx=2)
        self.var_wb_check = tk.BooleanVar(value=False)
        checkbox_wb = ttk.Checkbutton(frame_ds_operation, text='白板校正', command=None,
                variable=self.var_wb_check, onvalue=True, offvalue=False)
        checkbox_wb.pack(side='left', padx=5, anchor='w')
        btn_read_wb = ttk.Button(frame_ds_operation, text="读取白板", command=self.read_whiteboard)
        btn_read_wb.pack(side='left', padx=2)
        
        btn_clear_ds = ttk.Button(frame_ds_operation, text="清除数据集", command=self.on_clear_dataset)
        btn_clear_ds.pack(side='right', padx=5)
        btn_append_ds = ttk.Button(frame_ds_operation, text="追加数据集", command=self.on_append_dataset)
        btn_append_ds.pack(side='right', padx=5)
        
        frame_treeview = ttk.Frame(frame_right)
        frame_treeview.pack(side='top', expand=1, fill='both')
        # 创建Treeview控件
        tree_classinfo_col = [s for s in "ABCDE"]
        self.tree_classinfo = ttk.Treeview(frame_treeview, columns=tree_classinfo_col, show='headings', selectmode=tk.EXTENDED)
        self.tree_classinfo.pack(side='top', expand=1, fill='both')
        
        frame_trans = ttk.Frame(frame_right)
        frame_trans.pack(side='top', fill='both')

        frame_binning_config = ttk.Frame(frame_trans)
        frame_binning_config.pack(side='left', fill='y', padx=2)

        frame_smooth_config = ttk.Frame(frame_trans)
        frame_smooth_config.pack(side='left', fill='y', padx=2)

        frame_listbox_trans = ttk.Frame(frame_trans)
        frame_listbox_trans.pack(side='left', fill='y', padx=2)

        frame_x = ttk.Frame(frame_trans)
        frame_x.pack(side='right', expand=1, fill='y', padx=2)

        # 波段聚合配置
        self.var_binning_check = tk.BooleanVar()
        self.var_binning_check.set(False)
        checkbox = ttk.Checkbutton(frame_binning_config, text='波段聚合', command=self.on_binning_check,
                variable=self.var_binning_check, onvalue=True, offvalue=False)
        checkbox.pack(side='top', anchor='w')
        lb_binning = tk.Label(frame_binning_config, text="波段聚合间隔(nm): ")
        lb_binning.pack(side='left')
        self.var_binning_gap = tk.IntVar(value=10)
        entry_binning = tk.Entry(frame_binning_config, textvariable=self.var_binning_gap)
        entry_binning.pack(side='left', padx=2)
        btn_binning = ttk.Button(frame_binning_config, text="OK", command=self.on_binning_gap_confirmed)
        btn_binning.pack(side='left', padx=2)

        # 平滑算法列表选择
        lb_smooth = tk.Label(frame_smooth_config, text="平滑算法")
        self.listbox_smooth = tk.Listbox(frame_smooth_config, selectmode=tk.SINGLE, exportselection=False)
        scrollbar_smooth = tk.Scrollbar(frame_smooth_config, command=self.listbox_smooth.yview)
        self.listbox_smooth.configure(yscrollcommand=scrollbar_smooth.set)

        lb_smooth.grid(row=0, column=0, columnspan=2, sticky='W')
        self.listbox_smooth.grid(row=1, column=0, sticky='NS')
        scrollbar_smooth.grid(row=1, column=1,sticky='NS')
        frame_smooth_config.rowconfigure(0, weight=0)
        frame_smooth_config.rowconfigure(1, weight=1)

        # 算法列表选择
        lb_trans = tk.Label(frame_listbox_trans, text="预处理算法")
        self.listbox_trans = tk.Listbox(frame_listbox_trans, selectmode=tk.SINGLE, exportselection=False)
        scrollbar_trans = tk.Scrollbar(frame_listbox_trans, command=self.listbox_trans.yview)
        self.listbox_trans.configure(yscrollcommand=scrollbar_trans.set)

        lb_trans.grid(row=0, column=0, columnspan=2, sticky='W')
        self.listbox_trans.grid(row=1, column=0, sticky='NS')
        scrollbar_trans.grid(row=1, column=1,sticky='NS')
        frame_listbox_trans.rowconfigure(0, weight=0)
        frame_listbox_trans.rowconfigure(1, weight=1)

        # style = ttk.Style()
        # style.configure('TButton', backgound='cornsilk1', foreground='white')
        frame_btn = ttk.Frame(frame_right)
        frame_btn.pack(side='bottom', fill='x')
        btn_save = tk.Button(frame_btn, text="保存模型", command=self.on_btn_save_model, 
                             bg='darkseagreen1', fg='darkslateblue',
                             font=("heiti", "10", "bold"))
        btn_save.pack(side='right', padx=10)
        # 创建样式
        style = ttk.Style()
        # 自定义样式
        style.configure('WB.TButton', foreground='red', background='blue')
        btn_predict_dir = ttk.Button(frame_btn, text="推理文件夹", command=self.on_btn_predict_dir,
                                     style="WB.TButton")
        btn_predict_dir.pack(side='left', padx=10)
        btn_predict_imglist = tk.Button(frame_btn, text="推理文件列表", command=self.on_btn_predict_img_list)
        btn_predict_imglist.pack(side='left', padx=10)
        btn_predict_img = ttk.Button(frame_btn, text="推理单文件", command=self.on_btn_predict_img)
        btn_predict_img.pack(side='left', padx=10)



        # 波形图tab
        frame_options = tk.Frame(self.spectral_panedwindow_tab, bd=1)
        self.spectral_panedwindow_tab.add(frame_options)
        self.spectral_canvas = tk.Frame(self.spectral_panedwindow_tab) 
        self.spectral_panedwindow_tab.add(self.spectral_canvas)

        frame_labels = tk.Frame(frame_options)
        frame_labels.pack(side='top', fill='x')
        lb_classes = tk.Label(frame_labels, text="类别")
        self.listbox_classes = tk.Listbox(frame_labels, selectmode=tk.MULTIPLE, exportselection=False, height=24)
        scrollbar_classlist = tk.Scrollbar(frame_labels, command=self.listbox_classes.yview)
        self.listbox_classes.configure(yscrollcommand=scrollbar_classlist.set)
        lb_classes.grid(row=0, column=0, columnspan=2, sticky='W')
        self.listbox_classes.grid(row=1, column=0, sticky='NS')
        scrollbar_classlist.grid(row=1, column=1,sticky='NS')
        frame_labels.rowconfigure(0, weight=0)
        frame_labels.rowconfigure(1, weight=1)

        self.var_show_std_wave = tk.BooleanVar(value=True)
        checkbox_show_std = ttk.Checkbutton(frame_options, text='显示标准谱线', command=None,
                variable=self.var_show_std_wave, onvalue=True, offvalue=False)
        checkbox_show_std.pack(side='top', anchor='w')

        self.var_show_all_wave = tk.BooleanVar(value=False)
        checkbox_show_all = ttk.Checkbutton(frame_options, text='显示所有样本谱线', command=None,
                variable=self.var_show_all_wave, onvalue=True, offvalue=False)
        checkbox_show_all.pack(side='top', anchor='w')

        frame10 = tk.Frame(frame_options)
        frame10.pack(side='top', fill='x')
        lb_10 = tk.Label(frame10, text="显示样本数：")
        lb_10.pack(side='left', padx=2)
        self.var_samplenum = tk.IntVar(value=0)
        entry_samplenum = tk.Entry(frame10, textvariable=self.var_samplenum,width=8)
        entry_samplenum.pack(side='left', padx=2)
        frame_btn = tk.Frame(frame_options)
        frame_btn.pack(side='bottom', fill='x')
        btn_refresh_wave = ttk.Button(frame_btn, text="刷新", command=self.show_class_sample_spectral)
        btn_refresh_wave.pack(side='right', padx=5)
        btn_refresh_wave = ttk.Button(frame_btn, text="SAM距离", command=self.show_class_sam_distance)
        btn_refresh_wave.pack(side='right', padx=5)
        


        self.fig_wave, self.ax_wave = plt.subplots(figsize=(16, 9))
        # 将这个图表绘制到Tk的canvas上
        self.fig_wave_canvas_agg = FigureCanvasTkAgg(self.fig_wave, self.spectral_canvas)
        self.fig_wave_canvas_agg.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)
        self.nav_toolbar_wave = FigureCanvasNavigationToolbar(self.fig_wave_canvas_agg,  self.spectral_canvas)
        
        pass

    
    def create_ui_event_data(self):
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.center_notebook.bind("<<NotebookTabChanged>>", self.on_switch_tab)
        # 波段列表
        self.listbox_wave.bind('<<ListboxSelect>>', self.on_wave_select)
        self.listbox_wave.bind("<Button-3>", self.show_listbox_wave_menu) 
        self.listbox_wave_menubar = Menu(self.listbox_wave,tearoff=False)
        self.listbox_wave_menubar.add_command(label = '设置起点波段', command=self.set_start_wave)
        self.listbox_wave_menubar.add_command(label = '设置终点波段', command=self.set_end_wave)
        self.listbox_wave_menubar.add_command(label = '保留选择的波段', command=self.keep_wavelist)
        self.listbox_wave_menubar.add_command(label = '过滤选择的波段', command=self.remove_wavelist)

        # 数据集表格， TreeviewSelect不用编写逻辑
        # self.tree_classinfo.bind('<<TreeviewSelect>>', self.on_tree_classinfo_selected)
        self.tree_classinfo.bind("<Button-1>", self.on_tree_classinfo_click)
        self.tree_classinfo.bind("<Button-3>", self.show_tree_classinfo_menu) 
        self.tree_classinfo_menubar = Menu(self.listbox_wave,tearoff=False)


        self.listbox_smooth.bind('<<ListboxSelect>>', self.on_smooth_select)
        self.listbox_trans.bind('<<ListboxSelect>>', self.on_trans_select)

        # 波形图
        self.fig_wave.canvas.mpl_connect("motion_notify_event", self.fig_wave_hover)
        self.fig_wave.canvas.mpl_connect("button_press_event", self.fig_wave_button_click)
        self.fig_wave.canvas.mpl_connect('pick_event', self.fig_wave_on_pick)

        # ===================================

        for wv in self.dataset.wavelength:
            self.listbox_wave.insert(tk.END, str(wv))

        # Entry变量
        self.var_start_wv.set(self.dataset.start_wave_length)
        self.var_end_wv.set(self.dataset.end_wave_length)
        self.var_samplenum.set(-1)
        

        # 设置表格列标题
        self.tree_classinfo.heading("A", text="类别", anchor=tk.CENTER)
        self.tree_classinfo.heading("B", text="样本数量",anchor=tk.CENTER)
        self.tree_classinfo.heading("C", text="簇数量",anchor=tk.CENTER)
        self.tree_classinfo.heading("D", text="门限",anchor=tk.CENTER)
        self.tree_classinfo.heading("E", text="超类ID",anchor=tk.CENTER)
        self.tree_classinfo.column("A",  anchor="center")
        self.tree_classinfo.column("B",  anchor="center")
        self.tree_classinfo.column("C",  anchor="center")
        self.tree_classinfo.column("D",  anchor="center")
        self.tree_classinfo.column("E",  anchor="center")

        # 表格数据
        self.tree_class_rowid = {}
        for m, (label, datainfo) in enumerate(self.dataset.class_info_dict.items()):
            row_id = self.tree_classinfo.insert("", m, values=(label, str(self.dataset.class_info_dict[label].class_sample_num), 
                                                                    str(self.dataset.class_info_dict[label].cluster_num), 
                                                                    str(self.dataset.class_info_dict[label].sam_threshold),
                                                                    str(self.dataset.class_info_dict[label].super_class_index)))
            color = rgb_tuple_2_hexstr(self.dataset.class_info_dict[label].class_color)
            # 为指定的行设置样式
            self.tree_classinfo.tag_configure("tag_"+str(row_id), background=color)
            self.tree_classinfo.item(row_id, tags=("tag_"+str(row_id),))

            self.tree_class_rowid[row_id] = label

            if datainfo.cluster_num == 1:
                continue

            for n in range(datainfo.cluster_num):
                cluster_name = f"{label}-{n}"
                cluster_id = self.tree_classinfo.insert(row_id, n, values=(cluster_name, str(datainfo.cluster_sample_num[n]), 
                                                                    "1", 
                                                                    str(datainfo.cluster_threshold[n]),
                                                                    "-"))
                # self.tree_classinfo.item(cluster_id, tags=("tag_"+str(row_id),))


        # 平滑listbox数据
        self.listbox_smooth.insert(tk.END, '无')
        self.listbox_smooth.insert(tk.END, TRANSFORMS_DEF['SavitzkyGolay']['name'])
        self.listbox_smooth.select_set(0)
        
        # 算法listbox数据
        self.listbox_trans.insert(tk.END, str(TRANSFORMS_DEF['None']['name']))
        self.listbox_trans.insert(tk.END, str(TRANSFORMS_DEF['Diff1']['name']))
        self.listbox_trans.insert(tk.END, str(TRANSFORMS_DEF['Diff2']['name']))
        self.listbox_trans.insert(tk.END, str(TRANSFORMS_DEF['FirstDerivativeEnhanced']['name']))
        # for transid in TRANSFORMS_DEF:
        #     self.listbox_trans.insert(tk.END, str(TRANSFORMS_DEF[transid]['name']))
        self.listbox_trans.select_set(0)


        # 波形图tab数据
        # self.show_class_sample_spectral()

        pass


    def on_closing(self):

        # 在这里执行清理工作或保存数据
        print("建模窗口正在关闭，执行清理工作...")
        self.fig_hist.clear()
        self.fig_wave.clear()

        plt.close(self.fig_hist)
        plt.close(self.fig_wave)
        
        # 确保关闭事件继续传播
        self.destroy()
        self.quit()
        pass


    def on_tree_classinfo_click(self, event):
        '''
        treeview控件自己可以渲染选中条目和不选择条目的效果，同时保存选中条目，根本不用设置点击事件的操作逻辑
        至于获取选择的条目，通过treeview控件的selection方法即可
        而本事件的响应是仅仅是为了便于取消全部选中
        '''
        # 获取点击位置处的条目
        item = self.tree_classinfo.identify('item', event.x, event.y)
        # 检查是否点击在了空白处
        if not item:
            # print("点击了空白处")
            # self.tree_classinfo.selection_clear()   # 注意：此代码无效
            select_list = self.tree_classinfo.selection()
            for item in select_list:
                self.tree_classinfo.selection_remove(item)

        return


    def show_tree_classinfo_menu(self, event):
        selection = self.tree_classinfo.selection()
        if len(selection) == 0:
            return
        
        self.tree_classinfo_menubar.delete(0, tk.END)
        self.tree_classinfo_menubar.add_command(label = '设置SAM门限', command=self.set_class_sam_thres)
        self.tree_classinfo_menubar.add_command(label = '设置聚类簇数量', command=self.set_class_clusternum)
        self.tree_classinfo_menubar.add_command(label = '设置SuperClassIndex', command=self.set_super_class_index)
        self.tree_classinfo_menubar.post(event.x + self.tree_classinfo.winfo_rootx(), event.y + self.tree_classinfo.winfo_rooty()) 

        pass


    def refresh_tree_classinfo(self):
        '''
        当transform等参数变化后，对聚类簇的样本数量的刷新
        '''

        for itemid in self.tree_class_rowid:
            labelname = self.tree_class_rowid[itemid]
            
            row_values = self.tree_classinfo.item(itemid, 'values')
            cluster_num = int(row_values[2])

            if cluster_num < 2:
                continue

            children = self.tree_classinfo.get_children(itemid)
            for child in children:
                self.tree_classinfo.delete(child)
            
            for n in range(cluster_num):
                cluster_name = f"{labelname}-{n}"
                cluster_num = self.dataset.class_info_dict[labelname].cluster_sample_num[n]
                cluster_id = self.tree_classinfo.insert(itemid, n, 
                                                        values=(cluster_name, str(cluster_num), 
                                                                "1", 
                                                                f"{self.dataset.class_info_dict[labelname].sam_threshold}", 
                                                                "-"))


        pass


    
    def refresh_after_transform_changed(self):
        '''
        每当界面上的Transform相关的参数进行修改之后，需要进行的刷新操作
        '''
        self.need_redraw_hist = True
        self.need_redraw_wave = True
        self.refresh_tree_classinfo()
        return


    def set_class_clusternum(self):

        selection = self.tree_classinfo.selection()
        if len(selection) == 0:
            return
        
        new_value = simpledialog.askinteger(title="聚类簇数量设置", 
                                                prompt=f"设置类的聚类簇数量[1,5]", 
                                                initialvalue=1,
                                                minvalue=1, maxvalue=5)
        if not isinstance(new_value, int):
            return
        
        class_itemid_list = []
        class_name_list = []
        for itemid in selection:
            if itemid in self.tree_class_rowid:
                labelname = self.tree_class_rowid[itemid]
                row_values = self.tree_classinfo.item(itemid, 'values')
                cluster_num = int(row_values[2])
                if new_value==cluster_num:
                    continue

                row_value_list = list(row_values)
                row_value_list[2] = new_value
                new_tuple = tuple(row_value_list)
                self.tree_classinfo.item(itemid, values=new_tuple)
                
                class_itemid_list.append(itemid)
                class_name_list.append(labelname)

        if len(class_itemid_list) == 0:
            return

        self.dataset.set_class_cluster_num(class_name_list, new_value)
        
        for i, itemid in enumerate(class_itemid_list):
            labelname = class_name_list[i]
            children = self.tree_classinfo.get_children(itemid)
            for child in children:
                self.tree_classinfo.delete(child)
            
            if new_value < 2:
                continue

            for n in range(new_value):
                cluster_name = f"{labelname}-{n}"
                cluster_num = self.dataset.class_info_dict[labelname].cluster_sample_num[n]
                cluster_id = self.tree_classinfo.insert(itemid, n, 
                                                        values=(cluster_name, str(cluster_num), 
                                                                "1", 
                                                                f"{self.dataset.class_info_dict[labelname].sam_threshold}", 
                                                                "-"))

        self.need_redraw_wave = True
        self.need_redraw_hist = True       

        # Show something...

        return


    def set_class_sam_thres(self):

        selection = self.tree_classinfo.selection()
        if len(selection) == 0:
            return
        
        new_value = simpledialog.askfloat(title="SAM门限设置", 
                                                prompt=f"设置类的SAM距离门限[0~1]", 
                                                initialvalue=0.6,
                                                minvalue=0.0, maxvalue=1.0)
        if not isinstance(new_value, float):
            return
        
        for itemid in selection:
            
            row_values = self.tree_classinfo.item(itemid, 'values')
            row_value_list = list(row_values)
            sam_threshold = float(row_values[-2])
            
            if abs(new_value-sam_threshold)<1e-9:
                continue

            row_value_list[-2] = new_value
            new_tuple = tuple(row_value_list)
            self.tree_classinfo.item(itemid, values=new_tuple)

            labelname = row_values[0]
            labelname_list = labelname.split('-')
            classname = labelname_list[0]
            cluster_id = None
            if len(labelname_list) > 1:
                cluster_id = int(labelname_list[1])

            self.dataset.set_class_threshold(classname, new_value, cluster_id)

        return


    def set_super_class_index(self):

        selection = self.tree_classinfo.selection()
        if len(selection) == 0:
            return
        
        new_value = simpledialog.askinteger(title="超类ID设置", 
                                                prompt=f"设置超类ID", 
                                                initialvalue=0)
        if (not isinstance(new_value, int)):
            return

        for itemid in selection:

            if itemid not in self.tree_class_rowid:
                continue
        
            row_values = self.tree_classinfo.item(itemid, 'values')
            row_value_list = list(row_values)
            labelname = row_values[0]
            super_class_index = int(row_values[-1])
            
            if new_value==super_class_index:
                continue

            row_value_list[-1] = new_value
            new_tuple = tuple(row_value_list)
            self.tree_classinfo.item(itemid, values=new_tuple)

            self.dataset.set_class_super_index(labelname, new_value)

        return


    def on_wave_select(self, event):
        pass


    def set_start_wave(self):
        index = self.listbox_wave.curselection()[0]
        if index > self.dataset.end_wave_index:
            messagebox.showerror("错误", "起点波段索引大于终点波段索引！", parent=self)
            return
        
        if index == self.dataset.start_wave_index:
            return
        
        item = self.listbox_wave.get(index)
        self.dataset.start_wave_length = float(item)
        self.dataset.start_wave_index = index
        self.var_start_wv.set(self.dataset.start_wave_length)

        self.dataset.transform_updated()
        self.refresh_after_transform_changed()
        pass


    def set_end_wave(self):
        index = self.listbox_wave.curselection()[0]
        if index < self.dataset.start_wave_index:
            messagebox.showerror("错误", "终点波段索引小于起点波段索引！", parent=self)
            return
        if index == self.dataset.end_wave_index:
            return
        item = self.listbox_wave.get(index)
        self.dataset.end_wave_length = float(item)
        self.dataset.end_wave_index = index
        self.var_end_wv.set(self.dataset.end_wave_length)

        self.dataset.transform_updated()
        self.refresh_after_transform_changed()
        pass


    def keep_wavelist(self):
        pass


    def remove_wavelist(self):
        pass


    def show_listbox_wave_menu(self, event):

        if self.listbox_wave.size() == 0:
            return
        sel = self.listbox_wave.curselection()
        self.listbox_wave_menubar.delete(0, tk.END)
        if len(sel) >= 2:
            self.listbox_wave_menubar.add_command(label = '保留选择的波段', command=self.keep_wavelist)
            self.listbox_wave_menubar.add_command(label = '过滤选择的波段', command=self.remove_wavelist)
            self.listbox_wave_menubar.add_separator()
            self.listbox_wave_menubar.add_command(label = '全选', command=self.remove_wavelist)
            self.listbox_wave_menubar.add_command(label = '全不选', command=self.remove_wavelist)
            pass
        elif len(sel) == 1:
            self.listbox_wave_menubar.add_command(label = '设置起点波段', command=self.set_start_wave)
            self.listbox_wave_menubar.add_command(label = '设置终点波段', command=self.set_end_wave)
            self.listbox_wave_menubar.add_separator()
            self.listbox_wave_menubar.add_command(label = '保留选择的波段', command=self.keep_wavelist)
            self.listbox_wave_menubar.add_command(label = '过滤选择的波段', command=self.remove_wavelist)
            self.listbox_wave_menubar.add_separator()
            self.listbox_wave_menubar.add_command(label = '全选', command=self.remove_wavelist)
            self.listbox_wave_menubar.add_command(label = '全不选', command=self.remove_wavelist)
        else:
            self.listbox_wave_menubar.add_command(label = '全选', command=self.remove_wavelist)
            self.listbox_wave_menubar.add_command(label = '全不选', command=self.remove_wavelist)

        self.listbox_wave_menubar.post(event.x + self.listbox_wave.winfo_rootx(), event.y + self.listbox_wave.winfo_rooty()) 

        pass


    def on_binning_check(self):
        '''
        计算聚合波段列表，并更新波段列表
        '''
        gap = 0
        if self.var_binning_check.get():
            gap = self.var_binning_gap.get()
        
        # 更新波段列表
        self.update_binning_wave(gap)


    def on_binning_gap_confirmed(self):
        '''
        波段聚合操作按钮点击
        '''
        if self.var_binning_check.get():
            gap = self.var_binning_gap.get()
            self.update_binning_wave(gap)
        pass


    def update_binning_wave(self, gap):
        
        if self.dataset.binning_gap == gap:
            return
        
        self.dataset.set_binning_wave(gap)
        self.listbox_wave.delete(0, tk.END)
        if gap>0:
            for wv in self.dataset.binning_wv_list:
                self.listbox_wave.insert(tk.END, str(wv))
            self.var_start_wv.set(str(self.dataset.binning_wv_list[0]))
            self.var_end_wv.set(str(self.dataset.binning_wv_list[-1]))
        else:
            for wv in self.dataset.wavelength:
                self.listbox_wave.insert(tk.END, str(wv))
            self.var_start_wv.set(str(self.dataset.wavelength[0]))
            self.var_end_wv.set(str(self.dataset.wavelength[-1]))
        
        self.dataset.transform_updated()
        self.refresh_after_transform_changed()
        
        pass

    
    def on_smooth_select(self, event):
        index = self.listbox_smooth.curselection()[0]
        item = self.listbox_smooth.get(index)
        trans_key = get_transkey_by_name(item)

        if 'None' == trans_key:
            if self.dataset.smooth == 0:
                return
            self.dataset.set_sg_smooth(False)
        
        elif 'SavitzkyGolay' == trans_key:
            if self.dataset.smooth == 1:
                return
            self.dataset.set_sg_smooth(True)

        self.dataset.transform_updated()
        self.refresh_after_transform_changed()
        return


    def on_trans_select(self, event):
        index = self.listbox_trans.curselection()[0]
        item = self.listbox_trans.get(index)
        if self.dataset.trans_key == get_transkey_by_name(item):
            return
        self.dataset.trans_key = get_transkey_by_name(item)
        
        self.dataset.transform_updated()
        self.refresh_after_transform_changed()
        pass
    

    def on_switch_tab(self, event):
        
        # selected_tab = self.center_notebook.tab(self.center_notebook.select(), "text")
        tab_idx = self.center_notebook.index(self.center_notebook.select())
        if 0 == tab_idx:
            return
        elif 1 == tab_idx:
            if self.need_redraw_wave:
                
                self.listbox_classes.delete(0, tk.END)
                for classname, datainfo in self.dataset.class_info_dict.items():
                    self.listbox_classes.insert(tk.END, classname)
                    if datainfo.cluster_num == 1:
                        continue
                    for j in range(datainfo.cluster_num):
                        clustername = f"{classname}-{j}"
                        self.listbox_classes.insert(tk.END, clustername)

                self.listbox_classes.selection_set(0, tk.END)

                self.show_class_sample_spectral()

                self.need_redraw_wave = False

            pass

        else:
            if self.need_redraw_hist:

                self.show_fig_sam_dist_distr_hist()

                self.need_redraw_hist = False
            pass

        pass


    def fig_wave_hover(self, event):

        pass

    def fig_wave_button_click(self, event):

        pass

    def fig_wave_on_pick(self, event):

        pass

    
    def show_class_sample_spectral(self):
        '''
        显示各个类别各个样本的原始谱线以及transform变换之后的谱线
        '''
        self.ax_wave.clear()

        selections = self.listbox_classes.curselection()
        for index in selections:
            item = self.listbox_classes.get(index)
            item_list = item.split('-')
            classname = item_list[0]
            cluster_id = None
            if len(item_list) > 1:
                cluster_id = int(item_list[1])

            if classname not in self.dataset.class_info_dict:
                continue
            
            datainfo = self.dataset.class_info_dict[classname]

            x = [i for i in range(self.dataset.end_wave_index+1-self.dataset.start_wave_index)]

            # 如果标准谱线选中，则。。。            
            if self.var_show_std_wave.get():               
                if cluster_id is None:  # class
                    color = rgb_tuple_2_hexstr(self.dataset.class_info_dict[classname].class_color)
                    y = datainfo.std_spectral
                    self.ax_wave.plot(x, y, color=color, linestyle='dashed',  linewidth=2)
                    pass
                else:  # cluster
                    color = rgb_tuple_2_hexstr(self.dataset.class_info_dict[classname].class_color)
                    y = datainfo.cluster_std_spectral[cluster_id]
                    self.ax_wave.plot(x, y, color=color, linestyle='dotted',  linewidth=1)
                    pass

                pass

            # 如果全部样本谱线选中，获取随机数，渲染
            if self.var_show_all_wave.get():
                img = self.dataset.class_info_dict[classname].trans_img
                color = rgb_tuple_2_hexstr(self.dataset.class_info_dict[classname].class_color)
                
                for i in range(img.shape[0]):
                    y = img[i]
                    self.ax_wave.plot(x, y, color=color)

            x_labels = [str(wv) for wv in self.dataset.wavelength[self.dataset.start_wave_index:self.dataset.end_wave_index+1]]
            if self.dataset.binning_gap>0:
                x_labels = [str(wv) for wv in self.dataset.binning_wv_list[self.dataset.start_wave_index:self.dataset.end_wave_index+1]]
            
            self.ax_wave.set_xticks(x, labels=x_labels, rotation=45)  
            self.ax_wave

        self.fig_wave_canvas_agg.draw_idle()
        return


    def show_fig_sam_dist_distr_hist(self):
        '''
        各个类别的标准谱线(多个簇取距离最接近的)和各个类别的样本之间SAM距离的直方图分布
        '''
        # 清空画布
        if self.fig_hist:
            # for i in range(self.dataset.class_num):
            #     for j in range(self.dataset.class_num):
            #         self.axs_hist[i,j].clear()
            #         self.fig_hist.delaxes(self.axs_hist[i,j])
            self.fig_hist.clear()
            plt.close(self.fig_hist)
            self.fig_hist = None
        
        for child in self.result_canvas_tab.winfo_children():
                # 删除子控件
            child.destroy()
       
        # 直方图tab
        classnum = self.dataset.class_num
        self.fig_hist, self.axs_hist = plt.subplots(classnum, classnum, figsize=(16, 9), 
                                                    sharex='col', sharey='row', 
                                                    clear=True)
        self.fig_hist_canvas_agg = FigureCanvasTkAgg(self.fig_hist, self.result_canvas_tab)
        self.fig_hist_canvas_agg.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)
        self.nav_toolbar_hist = FigureCanvasNavigationToolbar(self.fig_hist_canvas_agg, self.result_canvas_tab)
        self.fig_hist.subplots_adjust(
            left=0.04, bottom=0.06, right=0.98, top=0.92, wspace=0.12, hspace=0.12
        )

        # 直方图数据
        for i in range(self.dataset.class_num):
            self.axs_hist[i,0].set_ylabel('%')
            for j in range(self.dataset.class_num):
                self.axs_hist[i,j].grid(True)
                self.axs_hist[i,j].label_outer()


        #CLASS*B  计算每个类的标准谱线，而不是每个簇的
        stand_spectral_all = self.dataset.get_std_spectral_matrix(use_class=False)
        print(f"all standard spectral shape: {stand_spectral_all.shape}")

        class_angles_dict = {}
        for i, classname in enumerate(self.dataset.class_info_dict):
            img = self.dataset.class_info_dict[classname].trans_img    # H * B
            
            # H * ClassNum    一个类的每个样本点和全部簇的计算结果
            class_angles = sam_distance(img, stand_spectral_all) 
            class_angles_dict[classname] = class_angles

        pass

         # 直方图 
        ang = np.arange(0., 1.01, 0.1)
        x = np.arange(ang.size)
        bin_count = ang.size-1
        x_label= ["%.1f" % i for i in ang]    
        # color=['red','tomato','peru','tan','orange','yellow','yellowgreen',
        #         'lawngreen','forestgreen','lime','lightseagreen','darkslategray','deepskyblue'][:bin_count]  
        color=['aqua','deepskyblue','aquamarine','lime','limegreen',
                'yellow','orange','lightcoral','violet','fuchsia', 'red', 'forestgreen','royalblue'][:bin_count]   
        
        self.fig_hist.suptitle('samples - class distribution')
        for i, classname in enumerate(self.dataset.class_info_dict):    # 类别
            self.axs_hist[i,0].set_ylabel(f"class:{classname}")
            for j, cls_name in enumerate(self.dataset.class_info_dict):    # 其他类簇的距离
                
                # 需要获取其他类每个簇的索引范围
                other_cluster_index_list = self.dataset.class_info_dict[cls_name].cluster_index_list

                if i == 0:
                    self.axs_hist[i,j].set_title(f"samples:{cls_name}")
                
                if i == self.dataset.class_num-1:
                    self.axs_hist[i,j].set_xticks(x, x_label, rotation=45)
                    
                angles_cluster = class_angles_dict[classname][:,other_cluster_index_list]   # H*cluster_num
                angles = np.min(angles_cluster, axis=1)
                angles = np.sort(angles)
                total_count = angles.size

                statis_value_count = []
                for n in range(bin_count):
                    left = ang[n]
                    right = ang[n+1]
                    mask = np.zeros(angles.shape, dtype=np.uint32)
                    mask[(angles>left) & (angles<=right)] = 1
                    s = np.sum(mask)
                    statis_value_count.append(s)

                statis_value_perc = [count*100/total_count for count in statis_value_count]
                
                self.axs_hist[j, i].bar(x[:-1], statis_value_perc, color = color)
                self.axs_hist[j, i].set_ylim(0,100)
                # 绘制每个柱子上的计数
                bar_count = len(x[:-1])
                y_gap = int(100/bar_count)
                for ti in x[:-1]:
                    text_x = ti 
                    text_y = 2+ti*y_gap
                    self.axs_hist[j, i].text(text_x, text_y, "%.1f" % statis_value_perc[ti], ha='center', va='bottom')
                # self.axs_hist[i,j].grid(True,linestyle=':',color='r',alpha=0.6)

                # ax.legend(handlelength=4)
        self.fig_hist_canvas_agg.draw_idle()
        return


    def show_class_sam_distance(self):
        '''
        计算标准谱线之间的距离，显示为表格
        '''

        #Cluster*B  计算每个类每个簇的标准谱线
        stand_spectral_all = self.dataset.get_std_spectral_matrix(use_class=False)
        
        distance = sam_distance(stand_spectral_all, stand_spectral_all)
        
        class_name_list = []
        for classname, classinfo in self.dataset.class_info_dict.items():
            if classinfo.cluster_num == 1:
                class_name_list.append(classname)
                continue
            for i in range(classinfo.cluster_num):
                class_name_list.append(f"{classname}-{i}")

        # UI show
        DlgShowTable(class_name_list, distance, row_title=True)
        
        # df = pd.DataFrame(class_standard_spectral_angles, index=class_name_list, columns=class_name_list)
        # df.to_excel(os.path.join(output_dir, "distance_between_standard_spectral.xlsx"), sheet_name='标准谱线距离')



        return
    

    def on_btn_save_model(self):
        # 根据控件的当前值和数据集对象进行比较
        model_dir = filedialog.askdirectory(title='选择模型文件夹')

        if model_dir:
            self.dataset.save_model_to_file(model_dir)
            messagebox.showinfo("保存", f"模型保存成功：{model_dir}")
        
        return


    def on_btn_predict_dir(self):

        dir_path = filedialog.askdirectory(title="选择推理文件夹路径")    
        if dir_path:

            # 创建保存结果的文件夹
            now = datetime.now()
            formatted_time = now.strftime("%Y%m%d%H%M%S")
            result_dir = os.path.join(dir_path, "result_" + formatted_time)
            if not os.path.exists(result_dir):
                os.makedirs(result_dir)
            
            sam_model = SamModel()
            sam_model.create_model_from_dataset(self.dataset)

            for filename in os.listdir(dir_path):
                
                filepath = os.path.join(dir_path, filename)
                result_img = sam_model.predict_img(filepath)

                if result_img is None:
                    continue

                name, ext = os.path.splitext(filename)
                result_filepath = os.path.join(result_dir, name + ".jpg")

                # 使用PIL保存图像
                img = Image.fromarray(result_img, 'RGB')
                img.save(result_filepath)

                print(f"{result_filepath} saved!")

        pass


    def on_btn_predict_img_list(self):

        pass


    def on_btn_predict_img(self):

        file_list = filedialog.askopenfilenames(title="选择推理文件", defaultextension='.img', 
                                                    filetypes=[('img file', '.img')])
        if len(file_list) == 0:
            return
        
        sam_model = SamModel()
        sam_model.create_model_from_dataset(self.dataset)

        for file_path in file_list:
            result_img = sam_model.predict_img(file_path)

            if result_img is None:
                messagebox.showinfo("错误", "当前img文件推理失败！")
                continue

            WindowShowImage(file_path=file_path, image=result_img, master=self)

            # 注意：cv imshow默认是按照bgr的次序，所以颜色和result_img相反
            # 需要进行RGB->BGR的转换
        #     cv2.namedWindow(f"{file_path}", cv2.WINDOW_NORMAL)
        #     cv2.imshow(f"{file_path}", result_img)
        #     pass
        
        # cv2.waitKey(0)
        # cv2.destroyAllWindows()
        

        pass


    def read_whiteboard(self):

        file_path = filedialog.askopenfilename(title="选择白板文件", defaultextension='.tif', 
                                                    filetypes=[('tif file', '.tif'), ('all file', '.*')])
        if file_path:
            self.arr_wb = read_tif(file_path)

            messagebox.showinfo("文件读取成功", f"读取白板信息成功！大小为{self.arr_wb.shape[0]}*{self.arr_wb.shape[1]}")

        pass


    def on_clear_dataset(self):
        
        self.dataset.clear()
        
        self.ax_wave.clear()
        self.fig_hist.clear()
        self.fig_hist_canvas_agg.draw_idle()
        self.fig_wave_canvas_agg.draw_idle()

        self.listbox_classes.delete(0, tk.END)
        self.listbox_wave.delete(0, tk.END)
        
        self.tree_class_rowid.clear()
        for itemid in self.tree_classinfo.get_children():
            for id in self.tree_classinfo.get_children(itemid):
                self.tree_classinfo.delete(id)
            self.tree_classinfo.delete(itemid)
        pass


    def on_append_dataset(self):
        

        pass


if __name__ == "__main__":
    # Create the main window
    root = tk.Tk()
    root.title("Main Window")
    root.geometry("300x200")

    dataset = SamDataset()

    # Create a button to open the new window
    open_window_button = tk.Button(root, text="Open New Window", command=lambda: WindowCreateModel(dataset, root))
    open_window_button.pack(pady=20)

    # Run the main loop
    root.mainloop()