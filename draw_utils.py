import random
from tkinter import Canvas,Listbox,Scrollbar
from tkinter.scrolledtext import ScrolledText
from tkinter.font import Font
import tkinter
from matplotlib.ticker import AutoLocator, MultipleLocator
from matplotlib import artist
from matplotlib.pyplot import Axes
import matplotlib.colors as mcolors
from PIL import Image, ImageTk, ExifTags
from typing import Literal, Union, Dict, List
import numpy as np
from Img_Functions import  ImgInfo, Img_Data_type,  get_np_dtype_from_data_type, save_img
import os
import copy
import cv2
from configparser import ConfigParser
from algos import (TRANSFORMS_DEF, sam_distance, get_index_range_of_wave_range, 
                   transform_process, img_alignment, get_binning_wave, get_align_params,
                   COLOR_CONF_LIST, COLOR_ALLOC_MARK_LIST,img_stretch,
                   random_color_hexstr, mcolor_2_hexstr, trans_diff)

from datetime import datetime
import json

class RoiType:
    OP_HAND = 'hand'
    OP_ROI_RECT = 'label_rect'
    OP_ROI_POLYGON = 'label_polygon'
    OP_ROI_POINT = 'label_point'
    OP_TRUTH_RECT = 'truth_rect'
    OP_TRUTH_POLYGON = 'truth_polygon'
    OP_CLIP_RECT = 'clip_rect'
    OP_AUTO_ROI_REGION = 'auto_roi_region'
    OP_SAMPLE_POINT = 'sample_point'
    OP_SAMPLE_RECT = 'sample_rect'
    OP_SAMPLE_POLYGON = 'sample_polygon'
    OP_AUTO_ROI_POLYGON = 'auto_roi_polygon'
    pass


def get_hex_color(r=None, g=None, b=None):
    """Return a color in hex format."""
    if isinstance(r, np.uint8) and isinstance(g, np.uint8) and isinstance(b, np.uint8):
        return "#{:02x}{:02x}{:02x}".format(r,g,b)
    else:
        return "#{:02x}{:02x}{:02x}".format(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))


COLOR_TRUTH = 'orange'


class ShapeType:
    point = 'point'
    rect =  'rect'
    polygon = 'polygon' 

    pass


class ImageReDrawType:
    
    on_creating = 0
    on_wave_chage = 1
    on_stretch = 2
    on_zooming = 3
    on_show_auto_roi_mask = 4
    on_auto_roi_transparency = 5

    pass


class Shape:

    def __init__(self, id=-1, shape=ShapeType.point, roi_type=RoiType.OP_ROI_POINT, color=None, classname="",
                 dash=None, file_path:str=None):
        '''
        当确定要绘制某个shape的时候（从鼠标release开始），初始化Shape实例
        '''
        self.id = id           # 唯一标识
        self.roi_type = roi_type
        self.shape = shape
        self.pos_list = []      # 坐标信息[x,y,x,y,...] 像素坐标
        self.canvas_id = None   # Canvas上图形对象的ID
        self.fig_obj:artist.Artist = None     # Figure上波形图形对象
        self.canvas_mode:Literal['normal', 'highlight'] = None
        self.fig_mode:Literal['normal', 'highlight', 'other'] = None
        self.temp_point_list = []   # 矩形框的四个点； 多边形框的角点

        self.selected = False

        self.classname = classname
        self.color = color

        # 绘制虚线，该选项值是一个整数元组，元组中的元素分别代表短线的长度和间隔，
        # 比如 (3, 5) 代表 3 个像素的短线和 5 个像素的间隔
        self.dash = dash

        # 对齐之后的wave数据
        
        self.ori_roi_img:np.ndarray = None
        self.transformed_wave:np.ndarray = None
        
        self.img_path = file_path

        return


    def get_pos_on_canvas(self):

        canvas_pos_list = []
        for pos in self.pos_list:
            canvas_pos_list.append(DrawingManager.get_canvas_pos(pos))
        
        return canvas_pos_list
    

    def append_position(self, x, y):
        '''
        记录当前（真实）坐标
        '''
        self.pos_list.append(x)
        self.pos_list.append(y)
        return
    

    def set_selected(self, selected=True):

        if selected:
            self.canvas_mode = 'highlight'
            self.fig_mode = 'highlight'
        else:
            self.canvas_mode = 'normal'
            
            if self.roi_type in [RoiType.OP_SAMPLE_POINT, RoiType.OP_SAMPLE_POLYGON, RoiType.OP_SAMPLE_RECT]:
                if len(ShapeManager.samples_last_id_list)>0:
                    self.fig_mode = 'other'
                else:
                    self.fig_mode = 'normal'
            elif self.roi_type in [RoiType.OP_ROI_POINT, RoiType.OP_ROI_POLYGON, RoiType.OP_ROI_RECT]:
                if ShapeManager.label_last_selected_id>=0:
                    self.fig_mode = 'other'
                else:
                    self.fig_mode = 'normal'
        return


    def drawing(self, canvas_x, canvas_y):
        '''
        矩形和多边形在绘制中，删除旧位置，渲染新位置
        样式：虚线，灰色
        '''

        if self.shape == ShapeType.point:
            return
        
        real_x, real_y = DrawingManager.get_actural_xy(canvas_x, canvas_y)
                
        if self.canvas_id is not None:
            DrawingManager.canvas.delete(self.canvas_id)

        if self.shape == ShapeType.polygon:

            self.pos_list.extend([real_x, real_y])
            canvas_pos_list = self.get_pos_on_canvas()
            self.canvas_id = DrawingManager.canvas.create_polygon(canvas_pos_list, 
                                                                  outline='yellow', 
                                                                  fill='', dash=(1,1))
            pass

        else: 

            if len(self.pos_list) < 2:  # Dragging的起始Event，坐标为空
                self.pos_list.append(real_x)
                self.pos_list.append(real_y)
                return
            elif len(self.pos_list) < 4:  # Dragging的终止Event，已经存在起点了
                self.pos_list.append(real_x)
                self.pos_list.append(real_y)
            else:                          # 实际上，不存在这种情况
                self.pos_list[2] = real_x
                self.pos_list[3] = real_y

            canvas_pos_list = self.get_pos_on_canvas()
            self.canvas_id = DrawingManager.canvas.create_rectangle(canvas_pos_list, 
                                                                    outline='yellow', 
                                                                    dash=(1,1))

        return
    

    def end_drawing(self, canvas_x, canvas_y, cancel=False):
        '''
        将绘制的最终结果图像展示在Canvas上面，清除绘制过程中产生的图像
        设置 图像的Wave数据
        '''

        real_x, real_y = DrawingManager.get_actural_xy(canvas_x, canvas_y)

        if self.canvas_id is not None:
            DrawingManager.canvas.delete(self.canvas_id)
            if cancel:
                return True    # 此处是否增加wave绘制过程

        if self.shape == ShapeType.point:
            self.pos_list.extend([real_x, real_y])
            self.draw_shape(canvas_mode='normal')
            self.ori_roi_img = ImgDataManager.get_roi_wave(self.pos_list)

        elif self.shape == ShapeType.polygon:
            if cancel or len(self.pos_list) < 6:
                return False
            
            self.pos_list.extend([real_x, real_y])
            canvas_pos_list = self.get_pos_on_canvas()
            
            if self.dash is None:
                self.canvas_id = DrawingManager.canvas.create_polygon(canvas_pos_list, outline=self.color, 
                                                                  fill='', tags=(self.classname, self.shape, self.roi_type))
            else:
                self.canvas_id = DrawingManager.canvas.create_polygon(canvas_pos_list, outline=self.color, 
                                                                  fill='', dash=self.dash, tags=(self.classname, self.shape, self.roi_type))
            
            self.canvas_mode="normal"
            self.ori_roi_img  = ImgDataManager.get_roi_wave(self.pos_list, shape=ShapeType.polygon)
            
            pass
        else: 
            # 注意：如果没有拖动的过程，则pos_list为空，因为不会走Dragging Event的代码
            if len(self.pos_list) == 0:
                return False
            # 如果矩形拖动为一条直线
            if real_x == self.pos_list[0] or real_y == self.pos_list[1]:
                return False
            
            # 下面的赋值可要可不要，因为Dragging Event的终点坐标等于释放Event的坐标
            # self.pos_list[2] = real_x
            # self.pos_list[3] = real_y
            
            canvas_pos_list = self.get_pos_on_canvas()
            if self.dash is None:
                self.canvas_id = DrawingManager.canvas.create_rectangle(canvas_pos_list, 
                                                                    outline=self.color,
                                                                    tags=(self.classname, self.shape, self.roi_type))
            else:
                self.canvas_id = DrawingManager.canvas.create_rectangle(canvas_pos_list, 
                                                                    outline=self.color, dash=self.dash,
                                                                    tags=(self.classname, self.shape, self.roi_type))
            
            self.ori_roi_img  = ImgDataManager.get_roi_wave(self.pos_list, shape=ShapeType.rect)

            pass
        
        self.canvas_mode="normal"
        self.transformed_wave = self.get_transform_wave()
        return True   
    

    def draw_shape(self, canvas_mode=None, zoomed=False):
        '''
        重绘shape的位置和模式。
        新增shape：必须绘制。 canvas_mode='normal', zoomed=True; 
        缩放图像：  必须以(self.canvas_mode)重绘。 canvas_mode=None, zoomed=True; 
        选择shape变化(选择->正常；正常->选择)： 以(canvas_mode is not None)重绘, zoomed=False
        '''

        if zoomed:
            pass
        else: 
            if self.canvas_mode == canvas_mode:  # 需要判断mode是否发生改变
                return
            self.canvas_mode = canvas_mode
                
        if self.shape == ShapeType.point:
            self.draw_point()
        
        else:
            if zoomed:
                canvas_pos_list = self.get_pos_on_canvas()   
                DrawingManager.canvas.coords(self.canvas_id, canvas_pos_list)

            if self.canvas_mode == 'normal':
                fill = ""
                outline = self.color
                pass
            else:
                fill= DrawingManager.poly_style_highligth_fill_color
                outline = self.color
                DrawingManager.canvas.tag_raise(self.canvas_id)
                pass

            DrawingManager.canvas.itemconfig(self.canvas_id, fill=fill, outline=outline)
            

        return
    

    def draw_point(self):
        '''
        重绘点的位置和模式。
        '''
                
        # 设置点的形状大小
        if self.canvas_mode == 'normal':
            point_shape = DrawingManager.pt_style_normal_shape
            point_color = self.color
        else:
            point_shape = DrawingManager.pt_style_highlight_shape
            point_color = DrawingManager.pt_style_highlight_color

        canvas_pos_list = self.get_pos_on_canvas()
        sx = canvas_pos_list[0]
        sy = canvas_pos_list[1]

        half = 1
        if DrawingManager.showing_scale>100:
            half = DrawingManager.get_canvas_pos(half, use_round=True)
        
        if self.canvas_id is not None:
            DrawingManager.canvas.delete(self.canvas_id)

        if point_shape == "diamond": #上顶点# 左顶点# 下顶点# 右顶点
            point_list =         [
                (sx, sy - half),  
                (sx - half, sy),  
                (sx, sy + half), 
                (sx + half, sy)  
            ]
            self.canvas_id = DrawingManager.canvas.create_polygon(point_list, fill=point_color, outline=point_color, 
                                                                tags=(self.classname, self.shape, self.roi_type))
        elif point_shape == "round":
            point_list = [ sx - half, sy - half, sx + half, sy + half]

            self.canvas_id = DrawingManager.canvas.create_oval(point_list, fill=point_color, outline=point_color,
                                                            tags=(self.classname, self.shape, self.roi_type))
            '''
            Ovals, mathematically, are ellipses, including circles as a special case. 
            The ellipse is fit into a rectangle defined by the coordinates (x0, y0) of the top left corner 
            and the coordinates (x1, y1) of a point just outside of the bottom right corner.

            The oval will coincide with the top and left-hand lines of this box, 
            but will fit just inside the bottom and right-hand sides.
            '''
        elif point_shape == "rect":
            point_list = [ sx - half, sy - half, sx + half, sy + half]

            self.canvas_id = DrawingManager.canvas.create_rectangle(point_list, fill=point_color, outline=point_color,
                                                                    tags=(self.classname, self.shape, self.roi_type))
    
        if self.canvas_mode != 'normal':
            DrawingManager.canvas.tag_raise(self.canvas_id)

        return


    def draw_shape_on_canvas(self):
        '''
        根据得到shape对象实体，将它绘制（创建）到Canvas上. 类似于end_drawing
        '''
        self.canvas_mode == 'normal'

        if self.shape == ShapeType.point:

            self.draw_point()

        elif self.shape == ShapeType.polygon:

            canvas_pos_list = self.get_pos_on_canvas()
            
            if self.dash is None:
                self.canvas_id = DrawingManager.canvas.create_polygon(canvas_pos_list, outline=self.color, 
                                                                  fill='', tags=(self.classname, self.shape, self.roi_type))
            else:
                self.canvas_id = DrawingManager.canvas.create_polygon(canvas_pos_list, outline=self.color, 
                                                                  fill='', dash=self.dash, tags=(self.classname, self.shape, self.roi_type))
            pass
        else: 
            
            canvas_pos_list = self.get_pos_on_canvas()
            
            if self.dash is None:
                self.canvas_id = DrawingManager.canvas.create_rectangle(canvas_pos_list, 
                                                                    outline=self.color,
                                                                    tags=(self.classname, self.shape, self.roi_type))
            else:
                self.canvas_id = DrawingManager.canvas.create_rectangle(canvas_pos_list, 
                                                                    outline=self.color, dash=self.dash,
                                                                    tags=(self.classname, self.shape, self.roi_type))
            
            pass
        
        return

    
    def draw_wave(self, fig_mode='normal', transformed=False):
        '''
        场景1： 数据变换
        场景2： Shape对象选择发生变化
        '''

        # 真值框不用绘制wave
        if self.roi_type in  [RoiType.OP_TRUTH_RECT, RoiType.OP_TRUTH_POLYGON]:
            return   

        if transformed:
            
            self.transformed_wave = self.get_transform_wave()

            if self.fig_mode == 'highlight':
                if self.fig_obj is not None:
                    self.fig_obj.remove()
                self.fig_obj, = DrawingManager.ax.plot([i for i in range(len(ImgDataManager.wave_enabled_list))],
                                        self.transformed_wave,
                                        marker=DrawingManager.high_marker, 
                                        linestyle=DrawingManager.high_linestyle, 
                                        color=DrawingManager.wave_style_highlight_color, 
                                        zorder=100, picker=True, pickradius=5)
            elif self.fig_mode == 'other':
                if self.fig_obj is not None:
                    self.fig_obj.remove()
                self.fig_obj, = DrawingManager.ax.plot( 
                                        [i for i in range(len(ImgDataManager.wave_enabled_list))],
                                        self.transformed_wave,
                                        marker=DrawingManager.other_marker, 
                                        linestyle=DrawingManager.other_linestyle, 
                                        color=DrawingManager.wave_style_other_color, 
                                        zorder=1, picker=True, pickradius=5)
            else:
                if self.fig_obj is not None:
                    self.fig_obj.remove()
                self.fig_obj, = DrawingManager.ax.plot( 
                        [i for i in range(len(ImgDataManager.wave_enabled_list))],
                                        self.transformed_wave,
                                        marker=DrawingManager.normal_marker, 
                                        linestyle=DrawingManager.normal_linestyle, 
                                        color=self.color, 
                                        zorder=1, picker=True, pickradius=5)
            
            return

        if fig_mode is None:
            self.fig_mode = fig_mode
        elif self.fig_mode == fig_mode:
            return
        else:
            self.fig_mode = fig_mode

        if self.fig_mode == 'highlight':
            if self.fig_obj is not None:
                self.fig_obj.set_color(DrawingManager.wave_style_highlight_color)
                self.fig_obj.set_zorder(100)
            else:
                # 下面赋值有个逗号，是因为plot返回的结果是list of Line2D, A list of lines representing the plotted data.
                # 这里的逗号是使得self.figid等于列表的第一个元素
                # 并且这样赋值不出错的原因是该List只有一个元素
                # Line2D继承于matplotlib.artist.Artist
                # 最终，self.figid的本质是Line2D对象
                self.fig_obj, = DrawingManager.ax.plot([i for i in range(len(ImgDataManager.wave_enabled_list))],
                                    self.transformed_wave,
                                    marker=DrawingManager.high_marker, 
                                    linestyle=DrawingManager.high_linestyle, 
                                    color=DrawingManager.wave_style_highlight_color, 
                                    zorder=100, picker=True, pickradius=5)
        elif self.fig_mode == 'other':
            if self.fig_obj is not None:
                self.fig_obj.set_color(DrawingManager.wave_style_other_color)
                self.fig_obj.set_zorder(1)
            else:
                self.fig_obj, = DrawingManager.ax.plot( 
                                    [i for i in range(len(ImgDataManager.wave_enabled_list))],
                                    self.transformed_wave,
                                    marker=DrawingManager.other_marker, 
                                    linestyle=DrawingManager.other_linestyle, 
                                    color=DrawingManager.wave_style_other_color, 
                                    zorder=1, picker=True, pickradius=5)
        else:
            if self.fig_obj is not None:
                self.fig_obj.set_color(self.color)
                self.fig_obj.set_zorder(1)
            else:
                self.fig_obj, = DrawingManager.ax.plot( 
                    [i for i in range(len(ImgDataManager.wave_enabled_list))],
                                    self.transformed_wave,
                                    marker=DrawingManager.normal_marker, 
                                    linestyle=DrawingManager.normal_linestyle, 
                                    color=self.color, 
                                    zorder=1, picker=True, pickradius=5)
                
        return
    
    
    def  get_transform_wave(self, de_gain_control=True, binning_control=True, norm_control=True, diff_control=True):
        '''
        得到数据变换之后的wave
        1. de gain
        2. mean value
        3. binning wave
        4. norm
        5. diff

        '''

        #  得到原始值
        if not de_gain_control and not binning_control and not norm_control and not diff_control:
            roi_img = self.ori_roi_img.astype(np.float32)
            wave = np.mean(roi_img, axis=0)
            return wave

        # 
        if de_gain_control and ImgDataManager.use_de_gain:
            arr_gain, arr_expo = ImgDataManager.img_file_gain_expo_dict.get(self.img_path, (None, None))
            if arr_gain is not None and arr_expo is not None:
                arr_gain = arr_gain.reshape((1, -1))
                arr_expo = arr_expo.reshape((1, -1))
                roi_img = self.ori_roi_img.astype(np.float32)*1024/arr_gain/arr_expo
                wave = np.mean(roi_img, axis=0)
            else:
                wave = np.mean(self.ori_roi_img.astype(np.float32), axis=0)
        else:
            wave = np.mean(self.ori_roi_img.astype(np.float32), axis=0)

        if binning_control and ImgDataManager.use_binning and ImgDataManager.binning_gap > 0:
            if len(ImgDataManager.binning_wv_index_list)>0:
                
                binning_wave = np.zeros((wave.shape[0], len(ImgDataManager.binning_wv_list)), dtype=np.float32)
                try:
                    for i,(l,r) in enumerate(ImgDataManager.binning_wv_index_list):
                        binning_wave[:, i] = np.mean(wave[:, l:r+1], axis=1)
                    wave = binning_wave
                except:
                    pass
        
        if norm_control and ImgDataManager.use_norm:

            pass

        if diff_control and ImgDataManager.use_diff>0:

            wave = trans_diff(wave, ImgDataManager.use_diff)

        return wave
    
    pass


class ShapeManager:

    shape_id_object_dict:Dict[int, Shape] = {}     # 全部Shape对象 {shape_id: shape object}

    shape_id_next = 0

    current_label_name = ""
    label_name_shape_id_dict:Dict[str, list[int]] = {}   # 标签名称对应的Shape id列表
    label_shape_id_list = []                             # 标签的Shape id列表
    label_last_selected_id = -1

    filepath_sample_id_list_dict:Dict[str, list[int]] = {}
    sample_shape_id_list = [] 
    samples_last_id_list = []    # 当前已经选中的sample id list

    truth_shape_id_list = []   # 为label_shape_id_list的子集

    current_file_path = None

    auto_roi_classname = None
    auto_roi_polygon_id_list = []

    sample_current_color = None
    label_style_dict= {}

    def __init__(self):
        
        pass

    
    @staticmethod
    def clear():
        '''
        当前文件切换后的清理工作
        '''
        
        # ShapeManager.shape_id_next = 0
        ShapeManager.clear_label_objects()
        ShapeManager.label_last_selected_id = -1

        ShapeManager.current_file_path = None
        ShapeManager.sample_select()

        pass


    @staticmethod
    def clear_label_objects(labelname=""):
        '''
        清除指定标签名称的标注对象
        或全部标注对象，包括对应的图像
        '''
        if labelname != "":
            if labelname in ShapeManager.label_name_shape_id_dict:

                id_list = ShapeManager.label_name_shape_id_dict.pop(labelname)
                for id in id_list:
                    if id in ShapeManager.shape_id_object_dict:
                        shape_obj = ShapeManager.shape_id_object_dict.pop(id)
                        DrawingManager.canvas.delete(shape_obj.canvas_id)
                        if shape_obj.fig_obj is not None:
                            shape_obj.fig_obj.remov()
                        shape_obj = None

                    if id == ShapeManager.label_last_selected_id:
                        ShapeManager.label_last_selected_id  = -1
                    
                    if id in ShapeManager.label_shape_id_list:
                        ShapeManager.label_shape_id_list.remove(id)

                    if id in ShapeManager.truth_shape_id_list:
                        ShapeManager.truth_shape_id_list.remove(id)

            if labelname == ShapeManager.auto_roi_classname:
                ShapeManager.auto_roi_polygon_id_list.clear()
                ShapeManager.auto_roi_classname = ""    
                

        else:  # 全部清除
            for classname, id_list in ShapeManager.label_name_shape_id_dict.items():
                for id in id_list:
                    if id in ShapeManager.shape_id_object_dict:
                        shape_obj = ShapeManager.shape_id_object_dict.pop(id)
                        DrawingManager.canvas.delete(shape_obj.canvas_id)
                        if shape_obj.fig_obj is not None:
                            shape_obj.fig_obj.remove()
                        shape_obj = None
            pass
            ShapeManager.label_shape_id_list.clear()
            ShapeManager.truth_shape_id_list.clear()
            ShapeManager.label_name_shape_id_dict.clear()

            ShapeManager.auto_roi_polygon_id_list.clear()
            ShapeManager.auto_roi_classname = ""
            ShapeManager.label_last_selected_id = -1

        return
    

    @staticmethod
    def clear_auto_roi_objects():
        '''
        清除指定标签名称的标注对象或全部标注对象，包括对应的图像
        '''

        for id in ShapeManager.auto_roi_polygon_id_list:
            if id in ShapeManager.shape_id_object_dict:
                shape = ShapeManager.shape_id_object_dict.pop(id)
                DrawingManager.canvas.delete(shape.canvas_id)
                shape = None

        if ShapeManager.auto_roi_classname in ShapeManager.label_name_shape_id_dict:
            for id in ShapeManager.auto_roi_polygon_id_list:
                ShapeManager.label_name_shape_id_dict[ShapeManager.auto_roi_classname].remove(id)

        ShapeManager.auto_roi_polygon_id_list.clear()
        ShapeManager.auto_roi_classname = ""
        return


    @staticmethod
    def alloc_shape_id(roi_type=None):
        
        if roi_type == RoiType.OP_CLIP_RECT:
            return -1

        id = ShapeManager.shape_id_next
        ShapeManager.shape_id_next += 1

        return id
    

    @staticmethod
    def allocate_labelname_color(labelname):
        '''
        根据类别名称分配颜色(hexstring)
        '''

        if labelname not in ShapeManager.label_style_dict:
            for i, color in enumerate(COLOR_CONF_LIST):
                if COLOR_ALLOC_MARK_LIST[i] > 0:
                    COLOR_ALLOC_MARK_LIST[i] = 0
                    ShapeManager.label_style_dict[labelname] = (i, mcolor_2_hexstr(color))
                    break
            else:
                # random color
                ShapeManager.label_style_dict[labelname] = (-1, random_color_hexstr())
        
        return ShapeManager.label_style_dict[labelname][1]


    @staticmethod
    def store_drawing_shape_object():
        '''
        在Canvas上绘制shape结束后，将shape对象保存
        '''
        
        if DrawingManager.drawing_mode in [RoiType.OP_ROI_POINT, RoiType.OP_ROI_RECT, RoiType.OP_ROI_POLYGON,
                                           RoiType.OP_TRUTH_RECT, RoiType.OP_TRUTH_POLYGON]:
            # 取消选中对象，所有对象都绘制为Normal
            ShapeManager.label_last_selected_id = -1
            for id in ShapeManager.label_shape_id_list:
                if id in ShapeManager.shape_id_object_dict:
                    shape_obj = ShapeManager.shape_id_object_dict[id]
                    shape_obj.draw_shape('normal')
                    shape_obj.draw_wave('normal')

            DrawingManager.drawing_shape.draw_wave('normal')
            ShapeManager.label_shape_id_list.append(DrawingManager.drawing_shape.id)
            ShapeManager.shape_id_object_dict[DrawingManager.drawing_shape.id] = DrawingManager.drawing_shape
            ShapeManager.label_name_shape_id_dict[DrawingManager.drawing_shape.classname].append(DrawingManager.drawing_shape.id)

            # for id in ShapeManager.label_shape_id_list:
            #     if id in ShapeManager.shape_id_object_dict:
            #         shape_obj = ShapeManager.shape_id_object_dict[id]
            #         shape_obj.draw_wave('normal')
            
            pass
        
        elif DrawingManager.drawing_mode in [RoiType.OP_SAMPLE_POINT, RoiType.OP_SAMPLE_RECT, RoiType.OP_SAMPLE_POLYGON]:
            
            ShapeManager.samples_last_id_list.clear()
            for id in ShapeManager.sample_shape_id_list:
                if id in ShapeManager.shape_id_object_dict:
                    shape_obj = ShapeManager.shape_id_object_dict[id]
                    shape_obj.draw_shape('normal')
                    shape_obj.draw_wave('normal')
            
            DrawingManager.drawing_shape.draw_wave('normal')
            ShapeManager.sample_shape_id_list.append(DrawingManager.drawing_shape.id)
            ShapeManager.shape_id_object_dict[ DrawingManager.drawing_shape.id] =  DrawingManager.drawing_shape
            ShapeManager.filepath_sample_id_list_dict[ShapeManager.current_file_path].append( DrawingManager.drawing_shape.id)
            
            # for id in ShapeManager.sample_shape_id_list:
            #     if id in ShapeManager.shape_id_object_dict:
            #         shape_obj = ShapeManager.shape_id_object_dict[id]
            #         shape_obj.draw_wave('normal')
            # pass

        elif DrawingManager.drawing_mode in [RoiType.OP_AUTO_ROI_REGION]:
            DrawingManager.auto_roi_region_shape =  DrawingManager.drawing_shape
            pass

        return  DrawingManager.drawing_shape.id
    

    @staticmethod
    def set_current_filepath(filepath):

        ShapeManager.current_file_path = filepath
        if ShapeManager.current_file_path not in ShapeManager.filepath_sample_id_list_dict:
            ShapeManager.filepath_sample_id_list_dict[ShapeManager.current_file_path] = []

        return    
    

    @staticmethod
    def set_current_label_name(labelname=""):

        ShapeManager.current_label_name = labelname
        if labelname == "":
            return

        if ShapeManager.current_label_name not in ShapeManager.label_name_shape_id_dict:
            ShapeManager.label_name_shape_id_dict[ShapeManager.current_label_name] = []

        return   


    @staticmethod
    def change_label_name(old:str, new:str):
        '''
        标注的标签名改变
        '''

        if old == ShapeManager.current_label_name:
            ShapeManager.current_label_name = new

        if old in ShapeManager.label_name_shape_id_dict:
            id_list = ShapeManager.label_name_shape_id_dict.pop(old)
            for id in id_list:
                shape_obj = ShapeManager.shape_id_object_dict[id]
                shape_obj.classname = new

            # 旧key改为新key
            ShapeManager.label_name_shape_id_dict[new] = id_list

        if old == ShapeManager.auto_roi_classname:
            ShapeManager.auto_roi_classname = new

        return
    

    @staticmethod
    def delete_label_name(labelname, remove_obj=True):
        '''
        remove_obj: 当删除一个标签名称时，是否要将该标签对应的标注对象全部清除
        '''
        if labelname == ShapeManager.current_label_name:
            ShapeManager.current_label_name = None

        if labelname in ShapeManager.label_name_shape_id_dict:
            id_list = ShapeManager.label_name_shape_id_dict[labelname]
            for id in id_list:
                ShapeManager.label_delete(id, on_select=False)
                

        if labelname == ShapeManager.auto_roi_classname:
            ShapeManager.auto_roi_classname = None
            ShapeManager.auto_roi_polygon_id_list.clear()
            # ShapeManager.auto_roi_polygon_id_shape_dict.clear()
            # DrawingManager.canvas.delete((RoiType.OP_AUTO_ROI_POLYGON))

        return
        
     
    @staticmethod
    def label_select(id):
        '''
        在标注中选择id的Shape, 当重复点击同一个条目，则为取消选择
        '''
        # 查找id
        iid = int(id)
        if iid not in ShapeManager.label_shape_id_list:
            print(f"label_select error. id={id}")
            return False
        
        if ShapeManager.label_last_selected_id == iid:
            ShapeManager.label_last_selected_id = -1
            for label_shape_id in ShapeManager.label_shape_id_list:
                if label_shape_id in ShapeManager.shape_id_object_dict:
                    shape_obj = ShapeManager.shape_id_object_dict[label_shape_id]
                    shape_obj.draw_shape(canvas_mode='normal')
                    shape_obj.draw_wave('normal')
            return False    # 取消选择

        ShapeManager.label_last_selected_id = iid
        for label_shape_id in ShapeManager.label_shape_id_list:
            if label_shape_id in ShapeManager.shape_id_object_dict:
                shape_obj = ShapeManager.shape_id_object_dict[label_shape_id]
                if label_shape_id == iid:
                    shape_obj.draw_shape(canvas_mode='highlight')
                    shape_obj.draw_wave('highlight')
                else:
                    shape_obj.draw_shape(canvas_mode='normal')
                    shape_obj.draw_wave('normal')

        return True
    

    @staticmethod
    def label_delete(id, on_select=True):
        '''
        在标注中删除id的Shape
        on_select: 在label listbox里面选中条目进行删除的场景
        '''
        # 查找id
        iid = int(id)
        if iid not in ShapeManager.label_shape_id_list:
            return False
        
        ShapeManager.label_shape_id_list.remove(iid)
        if iid in ShapeManager.truth_shape_id_list:
            ShapeManager.truth_shape_id_list.remove(iid)

        if iid in ShapeManager.shape_id_object_dict:
            shape_obj = ShapeManager.shape_id_object_dict.pop(iid)
            DrawingManager.canvas.delete(shape_obj.canvas_id)
            if shape_obj.fig_obj is not None:
                shape_obj.fig_obj.remove()
            
            ShapeManager.label_last_selected_id = -1
            # 如果删除的标注shape是选中模式，则要将其他标注shape wave都从other置为normal
            if shape_obj.canvas_mode == 'highlight':
                for id in ShapeManager.label_shape_id_list:
                    if id in ShapeManager.shape_id_object_dict:
                        shape_other = ShapeManager.shape_id_object_dict[id]
                        shape_other.draw_wave('normal')
            
            shape_obj = None

        return True
    

    @staticmethod
    def label_clear():
        '''
        删除全部标注
        '''
        for id in ShapeManager.label_shape_id_list:
            if id in ShapeManager.shape_id_object_dict:
                shape_obj = ShapeManager.shape_id_object_dict.pop(id)
                DrawingManager.canvas.delete(shape.canvas_id)
                if shape_obj.fig_obj is not None:   # 真值框没有fig_obj
                    shape_obj.fig_obj.remove()
                shape_obj = None

        ShapeManager.label_shape_id_list.clear()
        ShapeManager.truth_shape_id_list.clear()
        ShapeManager.label_last_selected_id = -1
        return 


    # @staticmethod
    # def truth_clear():

    #     for id in ShapeManager.truth_shape_id_list:
    #         if id in ShapeManager.shape_id_object_dict:
    #             shape = ShapeManager.shape_id_object_dict.pop(id)
    #             DrawingManager.canvas.delete(shape.canvas_id)
    #             shape.fig_obj.remove()
    #             shape = None

    #     return

    @staticmethod
    def sample_delete_by_file(file_path:str):
        '''
        删除指定文件路径file_path的样本点
        '''

        return


    @staticmethod
    def sample_delete(id_list:list):
        '''
        id_list 当前选择的id list
        '''

        for id in id_list:
            if id in ShapeManager.shape_id_object_dict:
                shape = ShapeManager.shape_id_object_dict.pop(id)      # 删除index的item
                DrawingManager.canvas.delete(shape.canvas_id)
                shape.fig_obj.remove()
                shape = None
                if id in ShapeManager.samples_last_id_list:
                    ShapeManager.samples_last_id_list.remove(id)
                ShapeManager.sample_shape_id_list.remove(id)

                cur_id_list = ShapeManager.filepath_sample_id_list_dict[ShapeManager.current_file_path]
                if id in cur_id_list:
                    cur_id_list.remove(id)
                    pass
                else:
                    for file_path, file_id_list in ShapeManager.filepath_sample_id_list_dict.items():
                        if id in file_id_list:
                            file_id_list.remove(id)
                            break
                        pass

        for id in ShapeManager.sample_shape_id_list:
            if id in ShapeManager.shape_id_object_dict:        
                shape = ShapeManager.shape_id_object_dict[id]
                # shape.draw_shape(canvas_mode='normal', zoomed=False)  # 没必要
                shape.draw_wave('normal')

        return
    

    @staticmethod
    def sample_clear():
        '''
        清除全部样本点
        '''
        for id in ShapeManager.sample_shape_id_list:
            if id in ShapeManager.shape_id_object_dict:
                shape = ShapeManager.shape_id_object_dict[id]
                DrawingManager.canvas.delete(shape.canvas_id)
                shape.fig_obj.remove()
                shape = None
        
        ShapeManager.sample_shape_id_list.clear()
        ShapeManager.samples_last_id_list.clear()
        ShapeManager.filepath_sample_id_list_dict.clear()
        return
    

    @staticmethod
    def sample_select(id_list=[]):

        if len(id_list) == 0:  # 清除全部选中对象
            for id in ShapeManager.samples_last_id_list:
                if id in ShapeManager.shape_id_object_dict:
                    shape_obj = ShapeManager.shape_id_object_dict[id]
                    shape_obj.draw_shape(canvas_mode='normal')
                    shape_obj.draw_wave('normal')
            ShapeManager.samples_last_id_list.clear()
            return
        
        for id in ShapeManager.sample_shape_id_list:
            if id in ShapeManager.shape_id_object_dict:
                shape = ShapeManager.shape_id_object_dict[id]
            
                if id in id_list:   # 如果当前选中ID
                    if id in ShapeManager.samples_last_id_list :  # 如果之前已经选中
                        continue
                    else:
                        shape.draw_shape(canvas_mode='highlight')
                        shape.draw_wave('highlight')
                else:
                    shape.draw_shape(canvas_mode='normal')
                    shape.draw_wave('other')
                    pass

        ShapeManager.samples_last_id_list.clear()
        ShapeManager.samples_last_id_list.extend(id_list)    

        return
    
    
    @staticmethod
    def get_file_path_by_id(selected_id_list):

        if len(selected_id_list)>1:
            return
        
        id = selected_id_list[0]

        for file_path, id_list in  ShapeManager.filepath_sample_id_list_dict.items():
            if id in id_list:
                return file_path
            
        return ""
    

    @staticmethod
    def draw_samples_shape_on_canvas():
        '''
        当文件切换回来后，尝试重新加载新文件之前已经保存过的Samples
        '''
        if ShapeManager.current_file_path in ShapeManager.filepath_sample_id_list_dict:
            id_list = ShapeManager.filepath_sample_id_list_dict[ShapeManager.current_file_path]
            for id in id_list:
                if id in ShapeManager.shape_id_object_dict:
                    shape_obj = ShapeManager.shape_id_object_dict[id]
                    shape_obj.draw_shape_on_canvas()
        return
    

    @staticmethod
    def get_distance_between_samples(id_list):
        '''
        计算样本点之间的SAM距离。以原始值+DeGain的数据变换进行计算的结果
        '''

        wave_list = []
        for id in id_list:
            shape_obj = ShapeManager.shape_id_object_dict[id]
            wave = shape_obj.get_transform_wave(de_gain_control=True, binning_control=False,
                                                norm_control=False, diff_control=False)
            wave_list.append(wave)
        
        stand_spectral_all = np.array(wave_list, dtype=np.float32)
        distance = sam_distance(stand_spectral_all, stand_spectral_all)

        return distance


    
    @staticmethod
    def save_samples_wave_to_file(file_path:str):
        '''
        将采样点（支持多个文件）的波形保存到文本文件中
        '''

        with open(file_path, 'w', encoding='utf-8') as f:

            for sample_file_path in ShapeManager.filepath_sample_id_list_dict:
                id_list = ShapeManager.filepath_sample_id_list_dict[sample_file_path]
                if len(id_list) == 0:
                    continue

                f.write(f"# {sample_file_path}\n\n")
                f.write(f"# --- samples original wave value ---\n")
                
                wave_list = []
                for id in id_list:
                    if id in ShapeManager.shape_id_object_dict:
                        shape_obj = ShapeManager.shape_id_object_dict[id]
                        roi_img = shape_obj.ori_roi_img
                        wave = np.mean(roi_img, axis=0)
                        line = ','.join(f"{wave[i]:5.2f}" for i in range(wave.size))
                        f.write(f"{line}\n")
                        wave_list.append(wave)
                
                pass

                f.write(f"\n# --- mean value of samples original wave ---\n\n")
                mean_wv = np.mean(np.array(wave_list, dtype=np.float32), axis=0)
                line = ','.join(f"{mean_wv[i]:5.2f}" for i in range(mean_wv.size))
                f.write(f"{line}\n")

                arr_gain, arr_expo_time = ImgDataManager.img_file_gain_expo_dict.get(sample_file_path, (None, None))
                if arr_gain is not None and arr_expo_time is not None:
                    gain_str = ','.join(str(arr_gain[i]) for i in range(arr_gain.size))
                    expo_str = ','.join(str(arr_expo_time[i]) for i in range(arr_expo_time.size))
                    f.write(f"\n# gain: {gain_str}\n")
                    f.write(f"# exposure time: {expo_str}\n")

                    wave_list.clear()
                    f.write(f"\n# --- samples DE-Gain wave value  ---\n\n")
                    for id in id_list:
                        if id in ShapeManager.shape_id_object_dict:
                            shape_obj = ShapeManager.shape_id_object_dict[id]
                            roi_img = shape_obj.ori_roi_img.astype(np.float32)
                            roi_img = roi_img*1024/arr_gain/arr_expo_time
                            wave = np.mean(roi_img, axis=0)
                            
                        line = ','.join(f"{wave[i]:5.2f}" for i in range(wave.size))
                        f.write(f"{line}\n")
                        wave_list.append(wave)
                    
                    f.write(f"\n# --- mean value of samples DE-Gain wave ---\n\n")
                    mean_wv = np.mean(np.array(wave_list, dtype=np.float32), axis=0)
                    line = ','.join(f"{mean_wv[i]:5.2f}" for i in range(mean_wv.size))
                    f.write(f"{line}\n")
        
        return
    

    @staticmethod
    def save_samples_info_to_json(saved_file_path):
        
        try:
            with open(saved_file_path, 'r' ,encoding='utf-8') as f:
                old_data = json.load(f)
        except:
            old_data = []
            pass

        json_obj = []
        new_file_list = []
        with open(saved_file_path, 'w', encoding='utf-8') as f:

            for file_path in ShapeManager.filepath_sample_id_list_dict:
                id_list = ShapeManager.filepath_sample_id_list_dict[file_path]
                if len(id_list) == 0:
                    continue
                
                new_file_list.append(file_path)

                file_sample_dict = {}
                file_sample_dict['file_path'] = file_path
                file_sample_dict['count'] =  len(id_list)
                if file_path in ImgDataManager.img_file_gain_expo_dict:
                    gain = ImgDataManager.img_file_gain_expo_dict[file_path][0]
                    expo_time = ImgDataManager.img_file_gain_expo_dict[file_path][1]
                    file_sample_dict['gain'] =  gain.tolist()
                    file_sample_dict['exposure_time'] =  expo_time.tolist()
                else:
                    file_sample_dict['gain'] =  []
                    file_sample_dict['exposure_time'] =  []

                file_sample_dict['samples'] = []
                for id in id_list:
                    if id in ShapeManager.shape_id_object_dict:
                        shape_obj = ShapeManager.shape_id_object_dict[id]
                        roi_img = shape_obj.ori_roi_img
                        wave = np.mean(roi_img, axis=0)
                        pos_list = shape_obj.pos_list
                        shape = shape_obj.shape
                        file_sample_dict['samples'].append(
                            {
                                'shape': shape,
                                'pos_list': pos_list,
                                'wave': wave.tolist()
                            }
                        ) 
                
                # json_obj['samples_info'].append(file_sample_dict)
                json_obj.append(file_sample_dict)

            # 需要保留旧json文件中的记录
            for old_file_obj in old_data:
                old_file_path = old_file_obj['file_path']
                if old_file_path not in new_file_list:
                    json_obj.append(old_file_obj) 

            json.dump(json_obj, f, ensure_ascii=False, indent=4)

        return


    @staticmethod
    def load_samples_info_from_json(json_file_path:str):

        sample_file_path_list = []
        sample_id_list = []
        with open(json_file_path, 'r' ,encoding='utf-8') as f:
            data = json.load(f)
            for file_sample_dict in data:

                file_path = file_sample_dict['file_path']

                id_list = ShapeManager.filepath_sample_id_list_dict.get(file_path, [])
                if len(id_list) > 0:    # 如果当前文件已经有新绘制的样本了，则不加载json文件中的样本
                    continue

                sample_file_path_list.append(file_path)
                sample_count = file_sample_dict['count']

                if file_path not in ImgDataManager.img_file_gain_expo_dict:
                    gain = file_sample_dict['gain']
                    expo_time = file_sample_dict['exposure_time']
                    if len(gain) == 0 or len(expo_time)==0:
                        ImgDataManager.img_file_gain_expo_dict[file_path] = (None, None)
                    else:
                        ImgDataManager.img_file_gain_expo_dict[file_path] = (
                            np.array(gain, dtype=np.float32), np.array(expo_time, dtype=np.float32)
                        )
                
                file_id_list = []
                sample_list = file_sample_dict['samples']
                for sample in sample_list:
                    shape = sample['shape']
                    pos_list = sample['pos_list']
                    wave = sample['wave']

                    if shape == ShapeType.point:
                        roi_type=RoiType.OP_SAMPLE_POINT
                    elif shape == ShapeType.rect:
                        roi_type=RoiType.OP_SAMPLE_RECT
                    else:
                        roi_type=RoiType.OP_SAMPLE_POLYGON

                    id = ShapeManager.alloc_shape_id()
                    shape_obj = Shape(id=id, shape=shape, roi_type=roi_type, classname="", dash=None, file_path=file_path,
                                      color=random_color_hexstr())
                    shape_obj.pos_list = pos_list
                    shape_obj.ori_roi_img = np.array(wave, np.float32).reshape((1,-1))
                    shape_obj.fig_mode = 'normal'
                    ShapeManager.sample_shape_id_list.append(id)
                    ShapeManager.shape_id_object_dict[id] = shape_obj

                    file_id_list.append(id)

                    sample_id_list.append((id, shape))

                ShapeManager.filepath_sample_id_list_dict[file_path] = copy.copy(file_id_list)

                pass

        return sample_file_path_list, sample_id_list
    

    @staticmethod
    def draw_shape_id_list_wave(id_list:list, fig_mode='normal'):
        '''
        将当前shape id的波段绘制到fig
        '''
        for id in id_list:
            if id in ShapeManager.shape_id_object_dict:
                shape_obj = ShapeManager.shape_id_object_dict[id]
                shape_obj.draw_wave(transformed=True)

        return


    @staticmethod
    def label_load_from_info(shape, labelname, pos_list, truth=False, auto_roi=False):
        '''
        从shape, pos_list等信息构建对象，保存并绘制到Canvas
        场景：自动标注Shape结果绘制到Canvas;  从标注文件中加载Shape
        truth=False ： 标记是否是从真值文件中加载Shape,和标注文件的区别目前仅仅在于绘制的时候用虚线，此外真值不包括点对象
        '''
        
        if shape == ShapeType.point:
            if len(pos_list) < 2:
                return -1
            id = ShapeManager.alloc_shape_id()
            color = ShapeManager.allocate_labelname_color(labelname)
            shape_obj = Shape(id, shape=shape, roi_type=RoiType.OP_ROI_POINT, 
                                color=color, classname=labelname)
            shape_obj.pos_list.extend(pos_list)
            shape_obj.draw_shape(canvas_mode='normal')

        elif shape == ShapeType.polygon:
            if len(pos_list) < 6:
                return -1
            id = ShapeManager.alloc_shape_id()
            color = ShapeManager.allocate_labelname_color(labelname)

            shape_obj = Shape(id, shape=shape, color=color, classname=labelname)
            shape_obj.canvas_mode='normal'
            
            shape_obj.pos_list.extend(pos_list)
            canvas_pos_list = shape_obj.get_pos_on_canvas()
            
            if not truth:
                shape_obj.dash = None
                shape_obj.roi_type = RoiType.OP_AUTO_ROI_POLYGON if auto_roi else RoiType.OP_ROI_POLYGON
                shape_obj.canvas_id = DrawingManager.canvas.create_polygon(canvas_pos_list, outline=shape_obj.color, 
                                                                fill='', tags=(shape_obj.classname, shape_obj.shape, shape_obj.roi_type))
            else:
                shape_obj.dash = (2,2)
                shape_obj.roi_type = RoiType.OP_TRUTH_POLYGON
                shape_obj.canvas_id = DrawingManager.canvas.create_polygon(canvas_pos_list, outline=shape_obj.color, 
                                                                fill='', dash=shape_obj.dash, tags=(shape_obj.classname, 
                                                                                                    shape_obj.shape, shape_obj.roi_type))
            pass

        else: 

            if len(pos_list) < 4:
                return -1
            id = ShapeManager.alloc_shape_id()
            color = ShapeManager.allocate_labelname_color(labelname)

            shape_obj = Shape(id, shape=shape, color=color, classname=labelname)
            shape_obj.canvas_mode='normal'
            shape_obj.pos_list.extend(pos_list)
            canvas_pos_list = shape_obj.get_pos_on_canvas()
            
            if not truth:
                shape_obj.dash = None
                shape_obj.roi_type = RoiType.OP_ROI_RECT
                shape_obj.canvas_id = DrawingManager.canvas.create_rectangle(canvas_pos_list, 
                                                                    outline=shape_obj.color,
                                                                    tags=(shape_obj.classname, shape_obj.shape, shape_obj.roi_type))
            else:
                shape_obj.dash = (2,2)
                shape_obj.roi_type = RoiType.OP_TRUTH_RECT
                shape_obj.canvas_id = DrawingManager.canvas.create_rectangle(canvas_pos_list, 
                                                                    outline=shape_obj.color, dash=shape_obj.dash,
                                                                    tags=(shape_obj.classname, shape_obj.shape, shape_obj.roi_type))
            
            pass

        ShapeManager.shape_id_object_dict[id] = shape_obj
        
        if not truth:
            ShapeManager.label_shape_id_list.append(id)
        else:
            ShapeManager.label_shape_id_list.append(id)
            ShapeManager.truth_shape_id_list.append(id)

        if labelname not in ShapeManager.label_name_shape_id_dict:
            ShapeManager.label_name_shape_id_dict[labelname] = []
        
        ShapeManager.label_name_shape_id_dict[labelname].append(id)

        return id
    

    @staticmethod
    def label_load_from_txt_file(file_path:str):
        '''
        从标注文件加载多边形和点坐标信息
        返回：
            shape_info_list：（id，classname，shape，pos_list）
            label_count_dict： {classname：count}
            total_count： 文件中总数量
        '''
        try:
            with open(file_path, "r", encoding='utf-8') as f:
                lines = f.readlines()
        except Exception as e:
            print("标签文件打开错误！")  
            return 0, 0, None, None
        
        if file_path.find('truth')>0:
            truth_file = True
        else:
            truth_file = False

        label_count_dict = {}
        shape_info_list = []

        total_count = 0
        for index, line in enumerate(lines):
            line = line.strip()
            if line.startswith("#"):
                continue
            
            total_count += 1
            line_list = line.replace("\n", "").split(',')
            if len(line_list) < 4:
                print(f"标签文件第{index+1}行错误！字段数量错误：{len(line_list)}")
                continue

            labelname = line_list[0].strip()
            shape = line_list[1].strip()   

            if shape not in [ShapeType.point, ShapeType.rect, ShapeType.polygon]:
                print(f"标签文件第{index+1}行错误！形状错误：{shape}")
                continue

            real_pos_pairs = [int(pos) for pos in line_list[2:]]
            if len(real_pos_pairs) % 2 != 0:
                print(f"标签文件第{index+1}行错误！坐标数量错误：{len(real_pos_pairs)}")
                continue
            
            for i in range(0, len(real_pos_pairs), 2):
                if real_pos_pairs[i] >= ImgDataManager.img_info.hdr.samples or real_pos_pairs[i+1] >= ImgDataManager.img_info.hdr.lines:
                    print(f"标签第{index+1}行, 坐标值超过图像大小!") 
                    break
            else:
                
                id = ShapeManager.label_load_from_info(shape, labelname, real_pos_pairs, truth=truth_file)
                if id >= 0:

                    if labelname in label_count_dict:
                        label_count_dict[labelname] += 1
                    else:
                        label_count_dict[labelname] = 1

                    shape_info_list.append((id, labelname, shape, real_pos_pairs))

            pass
  
        return shape_info_list, label_count_dict, total_count


    @staticmethod
    def label_save_to_txt_file(file_path):
        '''
        保存标注到自定义的文本文件
        '''

        with open(file_path, 'w', encoding='utf-8') as f:
            for id in ShapeManager.label_shape_id_list:
                if id in ShapeManager.shape_id_object_dict:
                    shape_obj = ShapeManager.shape_id_object_dict[id]
                    label = shape_obj.classname
                    shape = shape_obj.shape
                    pos_list = ','.join(str(int(pos)) for pos in shape_obj.pos_list)
                    f.write(f"{label},{shape},{pos_list}\n")

        pass


    @staticmethod
    def label_save_to_json_file(self, file_path):
        '''
        保存多边形和点坐标信息到标注文件（无数据集数值信息）
        '''
        with open(file_path, 'w', encoding='utf-8') as f:
            for index, poly in enumerate(self.polygon_list):
                label = poly.label
                shape = poly.shape
                pos_list = ','.join(str(int(pos)) for pos in poly.pos_list)
                f.write(f"{label},{shape},{pos_list}\n")

            for pt in self.point_list:
                f.write(f"{pt.label}, point, {pt.cx},{pt.cy}\n")

        return
    
    pass


    @staticmethod
    def label_save_as_dataset(save_dir):

        # 创建保存结果的文件夹
        now = datetime.now()
        formatted_time = now.strftime("%Y%m%d%H%M%S")
                
        label_name_list = ShapeManager.label_name_shape_id_dict.keys()

        common_hdr_info = copy.deepcopy(ImgDataManager.img_info.hdr)
            
        for label, id in ShapeManager.label_name_shape_id_dict.items():
            img_file_path = os.path.join(save_dir, f"{label}_{formatted_time}.img")
            
            label_img_pix_wave_arr = None
            if id in ShapeManager.shape_id_object_dict:
                shape_obj = ShapeManager.shape_id_object_dict[id]
                if shape_obj.shape == ShapeType.point:
                    img = shape_obj.wave.reshape((1,-1))
                else:
                    img = shape_obj.roi_img
                if label_img_pix_wave_arr is None:
                    label_img_pix_wave_arr = img
                else:
                    label_img_pix_wave_arr = np.concatenate([label_img_pix_wave_arr, img], axis=0)

            count, wv_len = label_img_pix_wave_arr.shape    
            label_img_pix_wave_arr = label_img_pix_wave_arr.reshape((count, 1, wv_len))

            common_hdr_info.samples = 1
            common_hdr_info.lines   = count
            common_hdr_info.interleave = 'bip'
            common_hdr_info.set_user_defined_param("class_name", label)

            save_img(label_img_pix_wave_arr, img_file_path, common_hdr_info)
            pass
    
        return
    

    @staticmethod
    def create_polygon_from_auto_roi(auto_roi_lablename:str):
        
        if DrawingManager.auto_roi_mask_img is None:
            return
        
        ShapeManager.current_label_name = auto_roi_lablename
        ShapeManager.auto_roi_classname = auto_roi_lablename
        ShapeManager.auto_roi_polygon_id_list.clear()

        # # 使用Canny边缘检测找到图像中的边缘
        # edges = cv2.Canny(self.mask_img, 50, 150)
        # 查找轮廓
        contours, _ = cv2.findContours(DrawingManager.auto_roi_mask_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            # 使用epsilon值来逼近轮廓，得到一个多边形
            epsilon = 0.001 * cv2.arcLength(contour, True)
            polygon = cv2.approxPolyDP(contour, epsilon, True)
            
            coord_list = polygon.reshape(-1).tolist()

            if len(coord_list) < 6:
                continue

            id = ShapeManager.label_load_from_info(shape=ShapeType.polygon, 
                                              labelname=auto_roi_lablename, 
                                              pos_list=coord_list,
                                              auto_roi=True)
            
            if id >= 0:
                ShapeManager.auto_roi_polygon_id_list.append(id)

        return 




class DrawingManager:

    canvas:Canvas = None
    ax:Axes = None
    # canvas_scroll_bar:list[Scrollbar] = None
    showing_scale = 100   # [10+10, 300+20; 500+50; 2000]
    
    # img相关信息
    # Canvas绘图使用的基本img, 更新它的操作：图像对齐操作，增益调整。
    # 它用于伪彩波段选择，单波段选择，为生成可以渲染的img提供数据
    showing_ori_img_bip = None
    showing_img = None   # 经过波段选择，亮度拉伸调整之后的到的img，用于图像显示，宽高为原始值
    img_tk_image = None  # 基于showing_img, 经过缩放操作得到tk canvas图像
    img_image_on_canvas = None  # tk canvas上的img图像ID

    img_rgb_index_list = [-1,-1,-1]
    img_wave_index_selected = -1
    strecth_enabled = False
    stretch_factor = [0, 128, 255]
    
    show_height = -1
    show_width = -1
    
    canvas_image_list = []

    # 绘图相关信息    
    drawing_mode = None     # RoiType 
    drawing = False
    drawing_shape:Shape = None
    # 用于拖动图像
    end_x = 0
    end_y = 0

    # 自动ROI的mask图层
    auto_roi_region_shape:Shape = None
    auto_roi_mask_show = False
    auto_roi_mask_img:np.ndarray = None
    auto_roi_mask_image_tk = None
    auto_roi_mask_image_on_canvas = None
    auto_roi_image_transparency = 128
    auto_roi_gray_thres = 50
    auto_roi_erosion = 1

    # Point style
    pt_style_normal_shape = 'round'
    pt_style_highlight_shape = 'diamond'
    pt_style_highlight_color = 'blue'
    poly_style_highligth_fill_color = 'blue'

    # Wave style
    wave_style_highlight_color = 'blue'
    wave_style_other_color = 'gray'
    normal_marker='.'
    normal_linestyle='-'
    normal_linewidth=1
    other_marker='.'
    other_linestyle='-'
    other_linewidth=1
    high_marker='o'
    high_linestyle='-'
    high_linewidth=2

    show_sample_mean_wave = False

    def __init__(self):

        return

    @staticmethod
    def init_canvas_figure(canvas, ax, scroll_x, scroll_y):
        DrawingManager.canvas = canvas
        DrawingManager.ax = ax
        # DrawingManager.canvas_scroll_bar = (scroll_x, scroll_y)
        return
    

    @staticmethod
    def reset():
        
        DrawingManager.canvas.delete('all')
        DrawingManager.canvas_image_list.clear()
        
        DrawingManager.showing_ori_img_bip = None
        DrawingManager.showing_img = None
        DrawingManager.img_tk_image = None 
        DrawingManager.img_image_on_canvas = None       

        # drawing_mode = None     # RoiType 
        DrawingManager.drawing = False
        DrawingManager.drawing_shape = None

        DrawingManager.img_rgb_index_list = [-1,-1,-1]
        DrawingManager.img_wave_index_selected = -1
        # DrawingManager.strecth_enabled = False
        # stretch_factor = [0, 128, 255]

        # 自动ROI的mask图层
        DrawingManager.clear_auto_roi()

        return
    
    
    @staticmethod
    def set_canvas_scale(showing_scale=100):
        DrawingManager.showing_scale = showing_scale
        return
        

    @staticmethod
    def set_drawing_mode(roi_type):
        DrawingManager.drawing_mode = roi_type
        return
    
        
    @staticmethod
    def init_showing_img():
        '''
        Canvas上的Showing img仅仅和对齐，Gain调整， 以及伪彩和波段选择有关系
        和 波段聚合，wave数据处理没有关系
        '''
        # 设置 bgr_index
        for i, wv in enumerate(ImgDataManager.img_info.hdr.wavelength):
            if abs(wv-450) < 0.0001:
                DrawingManager.img_rgb_index_list[2] = i
            elif DrawingManager.img_rgb_index_list[2] <0 and 420<=wv<=480:
                DrawingManager.img_rgb_index_list[2] = i

            if abs(wv-550) < 0.0001:
                DrawingManager.img_rgb_index_list[1] = i
            elif DrawingManager.img_rgb_index_list[1] >=0 and 520<=wv<=580:
                DrawingManager.img_rgb_index_list[1] = i

            if abs(wv-650) < 0.0001:
                DrawingManager.img_rgb_index_list[0] = i
            elif DrawingManager.img_rgb_index_list[0] >=0 and 620<=wv<=680:
                DrawingManager.img_rgb_index_list[0] = i

        if DrawingManager.img_rgb_index_list[0] < 0 or\
                DrawingManager.img_rgb_index_list[0]>=ImgDataManager.img_info.hdr.bands or\
                DrawingManager.img_rgb_index_list[1] < 0 or\
                DrawingManager.img_rgb_index_list[1]>=ImgDataManager.img_info.hdr.bands or\
                DrawingManager.img_rgb_index_list[2] < 0 or\
                DrawingManager.img_rgb_index_list[2]>=ImgDataManager.img_info.hdr.bands:

            DrawingManager.img_rgb_index_list[1] = int(ImgDataManager.img_info.hdr.bands/2)
            DrawingManager.img_rgb_index_list[2] = int(ImgDataManager.img_info.hdr.bands/2)-1
            DrawingManager.img_rgb_index_list[0] = int(ImgDataManager.img_info.hdr.bands/2) + 1

        DrawingManager.img_wave_index_selected = -1
        DrawingManager.show_height = ImgDataManager.img_info.hdr.lines
        DrawingManager.show_width = ImgDataManager.img_info.hdr.samples
        DrawingManager.showing_scale = 100

        DrawingManager.set_ori_img()

        DrawingManager.update_x_axis()
        
        return
    
    
    @staticmethod
    def set_ori_img():
        
        if ImgDataManager.img_info.hdr.data_type == Img_Data_type.type_uint8:
            DrawingManager.showing_ori_img_bip = ImgDataManager.img_bip
        if ImgDataManager.img_info.hdr.data_type == Img_Data_type.type_uint16:
            img = ImgDataManager.img_bip.astype(np.float32)*255/65535
            DrawingManager.showing_ori_img_bip = img.astype(np.uint8)
        
        return


    @staticmethod
    def validate_drawing():
        '''
        是否可以进行绘制操作
        '''
        return DrawingManager.showing_img is not None

    

    @staticmethod
    def set_bgr_index(index, bgr=0):
        if 0<=bgr<=2 and 0<=index<ImgDataManager.img_info.hdr.bands:
            DrawingManager.img_rgb_index_list[bgr] = index
        else:
            return False
        
        DrawingManager.show_img(redraw_type=ImageReDrawType.on_wave_chage)
        return


    @staticmethod
    def set_wave_selected(index=-1):
        '''
        '''
        if 0<=index<=ImgDataManager.wave_index_end:
            DrawingManager.img_wave_index_selected = index
            DrawingManager.show_img(redraw_type=ImageReDrawType.on_wave_chage)
            return True
        else:
            DrawingManager.img_wave_index_selected = -1
            DrawingManager.show_img(redraw_type=ImageReDrawType.on_wave_chage)
            return False
     

    # @staticmethod
    # def set_stretch_factor(stretch_factor_value, lmu=0):
    #     # 进行拉伸
    #     if 0<=lmu<=2:
    #         old = DrawingManager.stretch_factor[lmu]
    #         DrawingManager.stretch_factor[lmu] = int(stretch_factor_value*255/100)
    #         if 0<=DrawingManager.stretch_factor[0]<DrawingManager.stretch_factor[1]<DrawingManager.stretch_factor[2]<=255:
    #             pass
    #         else:
    #            DrawingManager.stretch_factor[lmu] = old 
    #            return False
    #     else:
    #         return False
        
    #     DrawingManager.show_img(redraw_type=ImageReDrawType.on_stretch)
    #     return
    

    @staticmethod
    def set_stretch_info(enabled, stretch_factor_list=None):
        DrawingManager.strecth_enabled = enabled
        
        if enabled and len(stretch_factor_list) == 3 and\
           0<=stretch_factor_list[0]<stretch_factor_list[1]<stretch_factor_list[2]<=255:
            DrawingManager.stretch_factor.clear()
            DrawingManager.stretch_factor.extend(stretch_factor_list)
        else:
            pass
        
        DrawingManager.show_img(redraw_type=ImageReDrawType.on_stretch)
        return


    @staticmethod
    def show_img(redraw_type=ImageReDrawType.on_creating):
        '''
        根据像素值拉伸、按缩放比例显示图像（伪彩或灰度图）到界面
        on_zoom: 因为图像缩放导致的重绘
        '''

        if redraw_type != ImageReDrawType.on_show_auto_roi_mask:
        
            if DrawingManager.img_wave_index_selected >= 0:
                DrawingManager.showing_img = DrawingManager.showing_ori_img_bip[:,:, DrawingManager.img_wave_index_selected]
                pass
            else:
                DrawingManager.showing_img = DrawingManager.showing_ori_img_bip[:,:, DrawingManager.img_rgb_index_list]
                pass

            # 进行拉伸
            if DrawingManager.strecth_enabled:
                DrawingManager.showing_img = img_stretch(DrawingManager.showing_img, 
                                            DrawingManager.stretch_factor[0], DrawingManager.stretch_factor[1], 
                                            DrawingManager.stretch_factor[2])
            
            '''
            In the case of NumPy, be aware that Pillow modes do not always correspond to NumPy dtypes. 
            Pillow modes only offer 1-bit pixels, 8-bit pixels, 32-bit signed integer pixels, 
            and 32-bit floating point pixels.
            '''
            pil_image = Image.fromarray(DrawingManager.showing_img) 
                
            if redraw_type in [ImageReDrawType.on_creating, ImageReDrawType.on_wave_chage, 
                            ImageReDrawType.on_zooming]:

                show_width, show_height = DrawingManager.get_canvas_xy(ImgDataManager.img_info.hdr.samples,
                                                                       ImgDataManager.img_info.hdr.lines)

                pil_image = pil_image.resize((show_width, show_height))

            DrawingManager.img_tk_image = ImageTk.PhotoImage(pil_image)   # 注意：image_tk必须是成员变量,不能为局部变量
            if DrawingManager.img_image_on_canvas:
                DrawingManager.canvas.delete(DrawingManager.img_image_on_canvas)
            DrawingManager.img_image_on_canvas = DrawingManager.canvas.create_image(0, 0, 
                                                                                    anchor="nw", 
                                                                                    image=DrawingManager.img_tk_image,
                                                                                    tags='img')
            '''
            id = C.create_image(x, y, option, ...)

            activeimage	- Image to be displayed when the mouse is over the item. For option values, see image below.
            anchor - The default is anchor=tk.CENTER, meaning that the image is centered on the (x, y) position. See Section 5.5, 
                    “Anchors” for the possible values of this option. 
                    For example, if you specify anchor=tk.S, the image will be positioned so that 
                    point (x, y) is located at the center of the bottom (south) edge of the image.
            disabledimage - Image to be displayed when the item is inactive. For option values, see image below.
            image -	The image to be displayed. See Section 5.9, “Images”, above, 
                    for information about how to create images that can be loaded onto canvases.
            state -	Normally, image objects are created in state tk.NORMAL. 
                    Set this value to tk.DISABLED to make it grayed-out and unresponsive to the mouse. 
                    If you set it to tk.HIDDEN, the item is invisible.
            tags - If a single string, the image is tagged with that string. 
                    Use a tuple of strings to tag the image with multiple tags.
            '''
            
            DrawingManager.canvas.tag_lower(DrawingManager.img_image_on_canvas)
            '''
            tagOrId：这是一个参数，可以是一个或多个标签（tag）的字符串，或者是一个图形项的ID（通常是一个整数）。
                    如果提供的是标签，那么所有具有该标签的图形项都会被移动。
            belowThis（可选）：这是一个参数，指定了要将图形项移动到哪个图形项的下方。
                    它可以是另一个图形项的ID或标签。如果省略此参数，图形项将被移动到堆叠顺序的最底层。
            '''
            '''
            # 使用find方法根据标签获取对象ID
            # ids = DrawingManager.canvas.find_withtag('img')
            '''
            DrawingManager.canvas_image_list.clear()
            DrawingManager.canvas_image_list.append(DrawingManager.img_image_on_canvas)
        
        
        if DrawingManager.auto_roi_mask_show and DrawingManager.auto_roi_mask_img is not None:
            
            color_array = np.zeros((DrawingManager.auto_roi_mask_img.shape[0], DrawingManager.auto_roi_mask_img.shape[1], 3), dtype=np.uint8)
            color_array[:, :, 0][DrawingManager.auto_roi_mask_img==1] = 255  # Red channel
            color_array[:, :, 1] = 0
            color_array[:, :, 2] = 0
              
            pil_image_mask = Image.fromarray(color_array)
            pil_image_mask = pil_image_mask.resize((DrawingManager.show_width, DrawingManager.show_height))

            # 创建一个与图像2相同大小的alpha图层，并填充为128（半透明）
            p = int(DrawingManager.auto_roi_image_transparency*255/100)
            alpha_layer = Image.new('L', pil_image_mask.size, p)
            # 将alpha图层添加到图像的alpha通道
            pil_image_mask.putalpha(alpha_layer)

            DrawingManager.image_tk_auto_roi_mask = ImageTk.PhotoImage(pil_image_mask)
            if DrawingManager.auto_roi_mask_image_on_canvas:
                DrawingManager.canvas.delete(DrawingManager.auto_roi_mask_image_on_canvas)
            DrawingManager.auto_roi_mask_image_on_canvas = DrawingManager.canvas.create_image(0, 0, 
                                                                                              anchor="nw", 
                                                                                              image=DrawingManager.image_tk_auto_roi_mask,
                                                                                              tags='auto_roi_img')
            DrawingManager.canvas.tag_raise(DrawingManager.auto_roi_mask_image_on_canvas)
            
            DrawingManager.canvas_image_list.clear()
            DrawingManager.canvas_image_list.append(DrawingManager.auto_roi_mask_image_on_canvas)

            pass
        
        DrawingManager.canvas.config(scrollregion=DrawingManager.canvas.bbox("all"))

        return


    @staticmethod
    def get_image_xy_on_canvas(event):
        '''
        获取事件在Canvas图像上的坐标(x,y). (-1, -1)为非法
        '''
        if DrawingManager.img_image_on_canvas is None:
            return -1,-1

         # 转换事件的坐标到Canvas坐标（当前显示的图像大小即位于此坐标系统）
        image_x = int(DrawingManager.canvas.canvasx(event.x))
        image_y = int(DrawingManager.canvas.canvasy(event.y))

        if image_x>=0 and image_y>=0 and \
            image_x < DrawingManager.show_width and image_y < DrawingManager.show_height:
                return image_x, image_y
        else:
            return -1,-1 


    @staticmethod
    def canvas_event_to_img_rc(event):
        '''
        canvas上鼠标事件转换为img图像矩阵的真实位置（row， col）
        '''
        image_x, image_y = DrawingManager.get_image_xy_on_canvas(event)

        if image_x < 0 or image_y<0:
            return -1, -1

        # Calculate the scaling factors
        scale_x = ImgDataManager.img_info.hdr.samples / DrawingManager.show_width
        scale_y = ImgDataManager.img_info.hdr.lines / DrawingManager.show_height
        
        # Adjust the mouse coordinates using the scaling factors
        img_col = int(image_x * scale_x)
        img_row = int(image_y * scale_y)
        
        return img_row, img_col
     

    @staticmethod
    def get_actural_xy(canvas_x, canvas_y, use_round=False):
        if use_round:
            row = round(canvas_y*100./DrawingManager.showing_scale)
            col = round(canvas_x*100./DrawingManager.showing_scale)
        else:
            row = int(canvas_y*100./DrawingManager.showing_scale)
            col = int(canvas_x*100./DrawingManager.showing_scale)
        return col, row
    
    @staticmethod
    def get_actural_pos(pos, use_round=False):
        if use_round:
            p = round(pos*100./DrawingManager.showing_scale)
        else:
            p = int(pos*100./DrawingManager.showing_scale)
        return p
    

    @staticmethod
    def get_canvas_xy(col, row, use_round=False):
        if use_round:
            canvas_x = round(DrawingManager.showing_scale*col/100.)
            canvas_y = round(DrawingManager.showing_scale*row/100.)
        else:
            canvas_x = int(DrawingManager.showing_scale*col/100.)
            canvas_y = int(DrawingManager.showing_scale*row/100.)
        return canvas_x, canvas_y
    
    @staticmethod
    def get_canvas_pos(pos, use_round=False):
        if use_round:
            p = round(DrawingManager.showing_scale*pos/100.)
        else:
            p = int(DrawingManager.showing_scale*pos/100.)
        return p
    
    
    @staticmethod
    def on_mouse_left_clicked(event):
        '''
        创建canvas上的Shape对象
        '''

        '''
        event.x和event.y属性给出了鼠标指针在触发事件的控件上的位置。
        这些坐标是以控件(Canvas窗口)的左上角为原点（0,0）的二维坐标系中的点
        '''
        print(f"Left click Event coordinates: ({event.x}, {event.y})")

        '''
        canvas_x, canvas_y坐标是Canvas本身的左上角为原点（0,0）的二维坐标系中的点
        当Canvas的大小超过Canvas窗口时，canvas_x, canvas_y可能会大于event.x和event.y
        '''
        canvas_x, canvas_y = DrawingManager.get_image_xy_on_canvas(event)
        if canvas_x < 0 or canvas_y<0:
            return 
        
        print(f"Left click Canvas coordinates: ({canvas_x}, {canvas_y})")
        
        if DrawingManager.drawing_mode == RoiType.OP_HAND:  # hand
            #canvas尺寸是显示出来的那部分大小
            canvas_width = DrawingManager.canvas.winfo_width()   
            canvas_height = DrawingManager.canvas.winfo_height()

            # 仅当图像大小超过canvas大小时才记录鼠标位置
            if DrawingManager.show_width > canvas_width or DrawingManager.show_height > canvas_height:
                DrawingManager.end_x = event.x
                DrawingManager.end_y = event.y

            return 

        if DrawingManager.drawing_mode not in [RoiType.OP_ROI_POINT,
                                               RoiType.OP_ROI_RECT, RoiType.OP_ROI_POLYGON,
                                               RoiType.OP_TRUTH_RECT, RoiType.OP_TRUTH_POLYGON,
                                               RoiType.OP_AUTO_ROI_REGION,
                                               RoiType.OP_CLIP_RECT,
                                               RoiType.OP_SAMPLE_POLYGON,
                                               RoiType.OP_SAMPLE_RECT, RoiType.OP_SAMPLE_POINT]:
            return
        
        
        if DrawingManager.drawing:
            return

        id = ShapeManager.alloc_shape_id(DrawingManager.drawing_mode)

        if DrawingManager.drawing_mode in [RoiType.OP_ROI_POINT, RoiType.OP_ROI_POLYGON,
                                               RoiType.OP_ROI_RECT]:
            labelname = ShapeManager.current_label_name
            color = ShapeManager.allocate_labelname_color(labelname)
            dash = None

        elif DrawingManager.drawing_mode in [RoiType.OP_TRUTH_RECT, RoiType.OP_TRUTH_POLYGON]:

            labelname = ShapeManager.current_label_name
            color = ShapeManager.allocate_labelname_color(labelname)
            # labelname = "truth"
            # color = mcolor_2_hexstr('golden')
            dash = (2,2)

        elif DrawingManager.drawing_mode in [RoiType.OP_AUTO_ROI_REGION]:
            
            labelname = DrawingManager.drawing_mode
            color = mcolor_2_hexstr('gray')
            dash = (2,2)

        elif DrawingManager.drawing_mode in [RoiType.OP_SAMPLE_RECT, RoiType.OP_SAMPLE_POINT, 
                                             RoiType.OP_SAMPLE_POLYGON]:
            
            labelname = DrawingManager.drawing_mode
            color = ShapeManager.sample_current_color
            dash = None
            pass

        if DrawingManager.drawing_mode in [RoiType.OP_ROI_POINT, RoiType.OP_SAMPLE_POINT]:

            DrawingManager.drawing_shape = Shape(id=id, classname=labelname, color=color,
                                                 shape=ShapeType.point, 
                                                 roi_type=DrawingManager.drawing_mode,
                                                 file_path=ShapeManager.current_file_path)
            
            pass
                  
        elif DrawingManager.drawing_mode  in [RoiType.OP_ROI_RECT, RoiType.OP_SAMPLE_RECT, 
                                              RoiType.OP_TRUTH_RECT, 
                            RoiType.OP_CLIP_RECT,  RoiType.OP_AUTO_ROI_REGION]:
            # 只有绘制矩形才记录起点坐标 (注意：其实不需要记录，参见 dragging Event的注释)  
            # col, row = DrawingManager.get_actural_xy(canvas_x, canvas_y)
            DrawingManager.drawing_shape = Shape(id=id, classname=labelname, color=color, 
                                                 shape=ShapeType.rect, dash=dash, 
                                                 roi_type=DrawingManager.drawing_mode,
                                                 file_path=ShapeManager.current_file_path)
            # DrawingManager.drawing_shape.append_position(col, row)

        elif DrawingManager.drawing_mode in [RoiType.OP_ROI_POLYGON,  RoiType.OP_SAMPLE_POLYGON, 
                                             RoiType.OP_TRUTH_POLYGON] :

            DrawingManager.drawing_shape = Shape(id=id, classname=labelname, color=color, 
                                                 shape=ShapeType.polygon, dash=dash, 
                                                 roi_type=DrawingManager.drawing_mode,
                                                 file_path=ShapeManager.current_file_path)

        DrawingManager.drawing = True
        return


    @staticmethod
    def on_mouse_released(event):

        if DrawingManager.drawing_mode not in [RoiType.OP_ROI_POINT,
                                               RoiType.OP_ROI_RECT, RoiType.OP_ROI_POLYGON,
                                               RoiType.OP_TRUTH_RECT, RoiType.OP_TRUTH_POLYGON,
                                               RoiType.OP_AUTO_ROI_REGION,
                                               RoiType.OP_CLIP_RECT,
                                               RoiType.OP_SAMPLE_POLYGON,
                                               RoiType.OP_SAMPLE_RECT, RoiType.OP_SAMPLE_POINT]:
            return None
        
        if DrawingManager.drawing_shape is None:
            return None
        
        canvas_x, canvas_y = DrawingManager.get_image_xy_on_canvas(event)
        if canvas_x < 0 or canvas_y<0:
            if DrawingManager.drawing:
                DrawingManager.drawing_shape.end_drawing(canvas_x, canvas_y, cancel=True)
                DrawingManager.drawing = False
                DrawingManager.drawing_shape = None
                pass
            return None
        
        print(f"Release Event coordinates: ({event.x}, {event.y})")
        print(f"Release Canvas coordinates: ({canvas_x}, {canvas_y})")
        
        if DrawingManager.drawing_mode in [RoiType.OP_ROI_POINT, RoiType.OP_SAMPLE_POINT]:
            # 记录当前点坐标, 点绘制完成
            DrawingManager.drawing_shape.end_drawing(canvas_x, canvas_y)
            id = ShapeManager.store_drawing_shape_object()
            pos_list = copy.copy(DrawingManager.drawing_shape.pos_list)
            DrawingManager.drawing = False
            DrawingManager.drawing_shape = None
            return id, pos_list
                      
        elif DrawingManager.drawing_mode  in [RoiType.OP_ROI_RECT, 
                                              RoiType.OP_SAMPLE_RECT,
                                               RoiType.OP_TRUTH_RECT, 
                                                RoiType.OP_AUTO_ROI_REGION]:
            # 矩形框结束绘制
            # 如果起点，终点坐标不同，则正常结束； 否则终止绘制
            if DrawingManager.drawing_shape.end_drawing(canvas_x, canvas_y):
                id = ShapeManager.store_drawing_shape_object()
                pos_list = copy.copy(DrawingManager.drawing_shape.pos_list)
            else:
                DrawingManager.drawing = False
                DrawingManager.drawing_shape = None
                return None
            
            if DrawingManager.drawing_mode == RoiType.OP_AUTO_ROI_REGION:
                DrawingManager.auto_roi_region_shape = DrawingManager.drawing_shape

            DrawingManager.drawing = False
            DrawingManager.drawing_shape = None

            return id, pos_list

        elif DrawingManager.drawing_mode  in [RoiType.OP_CLIP_RECT]:
            # 通知：保存矩形框图片
            # ......
            DrawingManager.drawing_shape.end_drawing(canvas_x, canvas_y, cancel=True)
            pos_list = copy.copy(DrawingManager.drawing_shape.pos_list)
            DrawingManager.drawing = False
            DrawingManager.drawing_shape = None
            print("About to save cut img!")

            return -1, pos_list

        elif DrawingManager.drawing_mode in [RoiType.OP_ROI_POLYGON,  RoiType.OP_SAMPLE_POLYGON] :
            # 多边形正在绘制
            DrawingManager.drawing_shape.drawing(canvas_x, canvas_y)

            return None
        
        return None


    @staticmethod
    def on_mouse_dragging(event):
        '''
        只有绘制矩形才会拖动鼠标;  或者拖动图像
        注意：一次鼠标拖动本质上产生了至少两个dragging Event，其中：
             第一个Event代表了拖动的起点，其坐标和鼠标左键Click Event的坐标相同
             最后一个Event代表了拖动的终点，其坐标和鼠标左键Release Event的坐标相同
        '''

        if DrawingManager.drawing_mode == RoiType.OP_HAND:  # hand
            #canvas尺寸是显示出来的那部分大小
            canvas_window_width = DrawingManager.canvas.winfo_width()   
            canvas_window_height = DrawingManager.canvas.winfo_height()

            if DrawingManager.show_width > canvas_window_width:
                
                x_diff = event.x - DrawingManager.end_x

                # x_diff_ratio_before = DrawingManager.end_x*1.0/DrawingManager.show_width
                # x_diff_ratio_now = event.x*1.0/DrawingManager.show_width
                # DrawingManager.canvas_scroll_bar[0].set(x_diff_ratio_before, x_diff_ratio_now)

                DrawingManager.canvas.xview_scroll(-x_diff, "units")
                DrawingManager.end_x = event.x

            if DrawingManager.show_height > canvas_window_height:
                
                y_diff = event.y - DrawingManager.end_y

                # y_diff_ratio_before = DrawingManager.end_y*1.0/DrawingManager.show_height
                # y_diff_ratio_now = event.y*1.0/DrawingManager.show_height
                # DrawingManager.canvas_scroll_bar[1].set(y_diff_ratio_before, y_diff_ratio_now)

                DrawingManager.canvas.yview_scroll(-y_diff, "units")    
                DrawingManager.end_y = event.y

            return 

        if DrawingManager.drawing_mode not in [
                                               RoiType.OP_ROI_RECT, RoiType.OP_SAMPLE_RECT, 
                                               RoiType.OP_TRUTH_RECT, RoiType.OP_AUTO_ROI_REGION,
                                               RoiType.OP_CLIP_RECT]:
            return
        
        if DrawingManager.drawing_shape is None:
            return
        
        canvas_x, canvas_y = DrawingManager.get_image_xy_on_canvas(event)
        if canvas_x < 0 or canvas_y<0:
            return 

        print(f"Dragging Event coordinates: ({event.x}, {event.y})")
        print(f"Dragging Canvas coordinates: ({canvas_x}, {canvas_y})")

        if DrawingManager.drawing_mode == RoiType.OP_AUTO_ROI_REGION:
            if DrawingManager.auto_roi_region_shape is not None:
                DrawingManager.canvas.delete(DrawingManager.auto_roi_region_shape.canvas_id)

        DrawingManager.drawing_shape.drawing(canvas_x, canvas_y)

        return


    @staticmethod
    def on_mouse_double_clicked(event):

        if DrawingManager.drawing_mode not in [RoiType.OP_ROI_POLYGON, 
                                               RoiType.OP_SAMPLE_POLYGON, RoiType.OP_TRUTH_POLYGON]:
            return None
        
        if DrawingManager.drawing_shape is None:
            return None
        
        canvas_x, canvas_y = DrawingManager.get_image_xy_on_canvas(event)
        if canvas_x < 0 or canvas_y<0:
            if DrawingManager.drawing:
                DrawingManager.drawing_shape.end_drawing(canvas_x, canvas_y, cancel=True)
                DrawingManager.drawing = False
                DrawingManager.drawing_shape = None
                pass
            return None
        
        print(f"D clicked Event coordinates: ({event.x}, {event.y})")
        print(f"D clicked  Canvas coordinates: ({canvas_x}, {canvas_y})")
        
        if DrawingManager.drawing_shape.end_drawing(canvas_x, canvas_y):
            id = ShapeManager.store_drawing_shape_object()
            # self.shape_dict[self.drawing_shape.id] = self.drawing_shape
        else:
            id = None
        DrawingManager.drawing = False
        DrawingManager.drawing_shape = None

        return id


    @staticmethod
    def on_mouse_right_clicked(event):
        '''
        取消绘制（多边形）过程
        '''

        if DrawingManager.drawing_mode in [RoiType.OP_ROI_POLYGON, 
                                           RoiType.OP_SAMPLE_POLYGON, RoiType.OP_TRUTH_POLYGON]:

            canvas_x, canvas_y = DrawingManager.get_image_xy_on_canvas(event)

            print(f"Right clicked Event coordinates: ({event.x}, {event.y})")
            print(f"Right clicked  Canvas coordinates: ({canvas_x}, {canvas_y})")
            
            DrawingManager.drawing_shape.end_drawing(canvas_x, canvas_y, cancel=True)
            DrawingManager.drawing = False
            DrawingManager.drawing_shape = None

        return


    @staticmethod
    def on_zooming(scale_type='restore'):

        if scale_type == 'restore':
            DrawingManager.showing_scale = 100
        elif scale_type == 'zoomin':
            if DrawingManager.showing_scale<300:
                delta = 10
            elif DrawingManager.showing_scale<500:
                delta = 20
            elif DrawingManager.showing_scale<2000:
                delta = 50
            else:
                return
            DrawingManager.showing_scale += delta
        else:
            if DrawingManager.showing_scale<=10:
                return
            elif DrawingManager.showing_scale<=300:
                delta = 10
            elif DrawingManager.showing_scale<=500:
                delta = 20
            else:
                delta = 50
            DrawingManager.showing_scale -= delta 

        if DrawingManager.showing_scale != 100:
            DrawingManager.show_width, DrawingManager.show_height = DrawingManager.get_canvas_xy(ImgDataManager.img_info.hdr.samples, 
                                                                                                 ImgDataManager.img_info.hdr.lines)
            
        else:
            DrawingManager.show_height = ImgDataManager.img_info.hdr.lines
            DrawingManager.show_width = ImgDataManager.img_info.hdr.samples

        DrawingManager.show_img(redraw_type=ImageReDrawType.on_zooming)
        # 处理采样点，标签的缩放
        
        for id in ShapeManager.label_shape_id_list:
            if id in ShapeManager.shape_id_object_dict:
                shape = ShapeManager.shape_id_object_dict[id]
                shape.draw_shape(zoomed=True)
            pass

        for id in ShapeManager.sample_shape_id_list:
            if id in ShapeManager.shape_id_object_dict:
                shape = ShapeManager.shape_id_object_dict[id]
                shape.draw_shape(zoomed=True)
            pass
        
        # 正在绘制的多边形，未完成的shape也要进行缩放
        if DrawingManager.drawing and DrawingManager.drawing_mode in [RoiType.OP_ROI_POLYGON,
                                                                      RoiType.OP_SAMPLE_POLYGON,
                                                                      RoiType.OP_TRUTH_POLYGON]:
            if DrawingManager.drawing_shape is not None:
                if DrawingManager.drawing_shape.canvas_id is not None:
                    DrawingManager.canvas.delete(DrawingManager.drawing_shape.canvas_id)

                if DrawingManager.drawing_shape.shape == ShapeType.polygon:
                    canvas_pos_list = DrawingManager.drawing_shape.get_pos_on_canvas()
                    DrawingManager.drawing_shape.canvas_id = DrawingManager.canvas.create_polygon(canvas_pos_list, 
                                                                  outline='yellow', 
                                                                  fill='', dash=(1,1))
           
        
        return
    
    
    @staticmethod
    def clear_canvas_figure():
        '''
        删除Canvas上所有对象， 删除figure对象
        '''

        DrawingManager.canvas.delete('all')


        return
    

    @staticmethod
    def remove_canvas_shape(shape_canvas_id):
        
        DrawingManager.canvas.delete(shape_canvas_id)

        # wave 的处理

        return
    

    @staticmethod
    def update_x_axis():
        '''
        根据波段选择情况，更新x轴的信息
        '''
        x_ticks = [i for i in range(len(ImgDataManager.wave_enabled_list))]
        xlabels = [f'{wv:4.2f}' for wv in ImgDataManager.wave_enabled_list]
        DrawingManager.ax.set_xticks(x_ticks, labels=xlabels, rotation=45)
        DrawingManager.ax.set_xlim(-1, len(ImgDataManager.wave_enabled_list))
        DrawingManager.ax.xaxis.set_major_locator(AutoLocator())
        # ROIManager.ax.xaxis.set_major_locator(MultipleLocator(5))

        return
   
    @staticmethod
    def set_auto_roi_params(auto_roi_show=False, auto_roi_gray_thres=None, auto_roi_erosion=None, 
                            auto_roi_image_transparency=None):

        DrawingManager.auto_roi_mask_show = auto_roi_show

        if auto_roi_gray_thres is not None:
            DrawingManager.auto_roi_gray_thres = auto_roi_gray_thres

        if auto_roi_erosion is not None:
            DrawingManager.auto_roi_erosion = auto_roi_erosion

        if auto_roi_image_transparency is not None:
            DrawingManager.auto_roi_image_transparency = auto_roi_image_transparency

        return


    @staticmethod
    def auto_roi():
        '''
        自动标注处理和显示图层的过程
        '''
        DrawingManager.auto_roi_mask_img = np.zeros(DrawingManager.showing_img.shape, dtype=np.uint8)
        DrawingManager.auto_roi_mask_img[DrawingManager.showing_img>=DrawingManager.auto_roi_gray_thres] = 1
        DrawingManager.auto_roi_mask_img[DrawingManager.showing_img>=234] = 0
        # 范围外的像素不考虑
        if DrawingManager.auto_roi_region_shape is not None:
            roi_region = np.zeros_like(DrawingManager.auto_roi_mask_img)
            coord_list = [DrawingManager.get_canvas_pos(pos) for pos in DrawingManager.auto_roi_region_shape.pos_list]
            roi_region[coord_list[1]:coord_list[3], coord_list[0]:coord_list[2]] = 1
            DrawingManager.auto_roi_mask_img = np.bitwise_and(DrawingManager.auto_roi_mask_img, roi_region)

        # # 应用高斯模糊来平滑图像，降低噪声（可选）
        # self.mask_img = cv2.GaussianBlur(self.mask_img, (5, 5), 0)

        # 腐蚀
        k = DrawingManager.auto_roi_erosion
        if k > 0:
            if k % 2 == 0:
                k -= 1
            kernel = np.ones((k,k),np.uint8)
            DrawingManager.auto_roi_mask_img = cv2.erode(DrawingManager.auto_roi_mask_img, kernel=kernel)
            pass

        DrawingManager.show_img(redraw_type=ImageReDrawType.on_show_auto_roi_mask)

    pass


    @staticmethod
    def clear_auto_roi():

        # 清理限制区域对象
        if DrawingManager.auto_roi_region_shape is not None:
            DrawingManager.canvas.delete(DrawingManager.auto_roi_region_shape.canvas_id)
            DrawingManager.auto_roi_region_shape = None
        # 清理mask图像对象
        if DrawingManager.auto_roi_mask_image_on_canvas is not None:
            DrawingManager.canvas.delete(DrawingManager.auto_roi_mask_image_on_canvas)
            DrawingManager.auto_roi_mask_image_on_canvas = None

        if DrawingManager.auto_roi_mask_img is not None:
            DrawingManager.auto_roi_mask_img = None
            DrawingManager.auto_roi_mask_image_tk = None

            # DrawingManager.canvas.delete((RoiType.OP_AUTO_ROI_POLYGON))
            
            # 重绘图像 
            DrawingManager.show_img(redraw_type=ImageReDrawType.on_show_auto_roi_mask)
        
        return
    

    @staticmethod
    def clear_auto_roi_region():

        if DrawingManager.auto_roi_region_shape is not None:
            DrawingManager.canvas.delete(DrawingManager.auto_roi_region_shape.canvas_id)
            DrawingManager.auto_roi_region_shape = None

        return
    

    @staticmethod
    def save_auto_roi_to_dataset(save_path, formatted_time):
    
        img = ImgDataManager.img_info.get_img_by_interleave('bip')
        img = img_alignment(img, ImgDataManager.arr_align_conf)
        img = img.reshape((ImgDataManager.img_info.hdr.lines*ImgDataManager.img_info.hdr.samples, -1))
        mask = DrawingManager.auto_roi_mask_img.reshape(-1)
        img = img[mask==1, :]
        img = img.reshape((img.shape[0], 1, -1))

        hdr = copy.copy(ImgDataManager.img_info.hdr)
        hdr.interleave = 'bip'
        hdr.lines = img.shape[0]
        hdr.samples = 1
        hdr.update_band_names_by_wavelength()
        hdr.set_user_defined_param('class_name', ShapeManager.auto_roi_classname)
        hdr.set_user_defined_param('time_index', formatted_time)
        hdr.set_user_defined_param('threshold_lower', '0')
        hdr.set_user_defined_param('threshold_upper', '0')
        hdr.set_user_defined_param('threshold_wave_length', '0.00')

        # 选择文件保存路径
        save_img(img, save_path, hdr)
    
        return


    
    @staticmethod
    def on_pick_figure_obj(obj:artist, event_ind):
        '''
        在figure上面选中绘图对象的处理过程
        event_ind:曲线点击点在x轴方向的数值，如果点击在两个离散点x1和x2之间，则取更为接近的那个x值
        '''
        xdata = obj.get_xdata()   # 曲线的x轴数据
        ydata = obj.get_ydata()   # 曲线的y值数据序列
        points = tuple(zip(xdata[event_ind], ydata[event_ind]))  # 拾取对象曲线上的点的数值
        print('onpick points:', points)

        for id, shape_obj in ShapeManager.shape_id_object_dict.items():
            if shape_obj.fig_obj == obj:
                print(f"found shape! id={id}")
                if id in ShapeManager.label_shape_id_list:
                    ShapeManager.label_select(id)
                    return id
                
                if id in ShapeManager.sample_shape_id_list:
                    if id not in ShapeManager.samples_last_id_list:  #如果之前未选中
                        id_list = [id]
                        id_list.extend(ShapeManager.samples_last_id_list)
                        ShapeManager.sample_select(id_list)
                        return id_list
        return None
    

    @staticmethod
    def on_data_transformed():
        '''
        数据变换之后，重绘所有采样点
        '''

        for file_path,id_list in ShapeManager.filepath_sample_id_list_dict.items():
            if len(id_list) == 0:
                continue

            for id in id_list:
                if id in ShapeManager.shape_id_object_dict:
                    shape_obj = ShapeManager.shape_id_object_dict[id]
                    shape_obj.draw_wave(transformed=True)

        DrawingManager.update_x_axis()

        return



class ImgDataManager:

    # 图像相关变量
    img_info = None
    img_bip:np.ndarray = None   # 原始bip数据矩阵，随着对齐进行更新

    # img_bip_trans:np.ndarray = None    # 1: de gain; 2: binning

    wave_start:float = 0
    wave_end:float = 0
    wave_index_start:int = 0
    wave_index_end:int = 0
    wave_range_index_mask_arr = None          # 有效波段的范围mask列表
    wave_enabled_index_mask_arr = None        # 有效波段的选择状态mask列表
    wave_enabled_index_list = []    # 选中的特征波段在原始波段中的index
    wave_enabled_list = []          # 在原始波段中，选中的特征波段


    norm_max_value = 65535

    # 原油相关
    # 注： 对齐和去增益两个操作是独立互不影响的，都施加在img_bip上
    # 对齐
    auto_align_enabled = False
    arr_align_conf:np.ndarray = None
    img_align_state = False
    
    # 去增益
    use_de_gain= False
    img_file_gain_expo_dict = {}        # 各个Img 文件的gain和曝光值
    arr_gain = None
    arr_expo_time = None
    
    # Transform
    use_binning = False     
    binning_gap = 10
    binning_wv_list = []
    binning_wv_index_list = []

    use_norm = False
    use_smooth = 0      # 0: disable; 1: sg;  2: other;
    use_diff = 0        # 0: disable; 1: first ;  2:  second
    trans_seq = []


    def __init__(self):
        pass

    
    @staticmethod
    def initial(de_gain=False, binning=False, binning_gap=10, norm=False, diff=0):

        ImgDataManager.use_de_gain = de_gain
        ImgDataManager.use_binning = binning
        ImgDataManager.binning_gap = binning_gap
        ImgDataManager.use_norm = norm
        ImgDataManager.use_diff = diff
        pass


    @staticmethod
    def read_img_info(img_file_path):
        '''
        读取img文件信息
        '''
        ImgDataManager.img_info = ImgInfo()
        
        ret, info = ImgDataManager.img_info.create_img_info(img_file_path)
        if not ret:
            return False

        # 尝试读取曝光时间和增益字段
        gain = ImgDataManager.img_info.hdr.fields_dict.get('IrradianceGain'.lower(), None)
        expo_time = ImgDataManager.img_info.hdr.fields_dict.get('IrradianceExposureTime'.lower(), None)
        try:
            if isinstance(gain, str):
                ImgDataManager.arr_gain = np.array([float(g) for g in gain.split(',')], dtype=np.float32)
            else:
                ImgDataManager.arr_gain = np.array([float(g) for g in gain], dtype=np.float32)

            if isinstance(expo_time, str):
                ImgDataManager.arr_expo_time = np.array([float(e)*1000 for e in expo_time.split(',')], dtype=np.float32)
            else:
                ImgDataManager.arr_expo_time = np.array([float(e)*1000 for e in expo_time], dtype=np.float32)
        except:
            ImgDataManager.arr_gain = None
            ImgDataManager.arr_expo_time = None

        ImgDataManager.img_file_gain_expo_dict[img_file_path] = (
            ImgDataManager.arr_gain, ImgDataManager.arr_expo_time
        )

        ImgDataManager.init_img()
        return True


    @staticmethod
    def init_img():
        '''
        img初始化：
        1. 对齐
        '''
        
        ImgDataManager.img_align_state = False
        ImgDataManager.img_bip = ImgDataManager.img_info.get_img_by_interleave('bip')

        ImgDataManager.reset_wavelength_info()

        if ImgDataManager.img_info.hdr.data_type == Img_Data_type.type_uint8:
            ImgDataManager.norm_max_value = 255
        elif ImgDataManager.img_info.hdr.data_type == Img_Data_type.type_uint16:
            ImgDataManager.norm_max_value = 65535
        else:
            ImgDataManager.norm_max_value = np.max(ImgDataManager.img_bip)
        
        if ImgDataManager.auto_align_enabled:
            ImgDataManager.align_img()

        DrawingManager.init_showing_img()
        DrawingManager.show_img()
        
        return
    

    @staticmethod
    def reset_wavelength_info():

        ImgDataManager.wave_index_start = 0
        ImgDataManager.wave_index_end = ImgDataManager.img_info.hdr.bands-1
        ImgDataManager.wave_start = ImgDataManager.img_info.hdr.wavelength[ImgDataManager.wave_index_start]
        ImgDataManager.wave_end = ImgDataManager.img_info.hdr.wavelength[ImgDataManager.wave_index_end]
        ImgDataManager.wave_range_index_mask_arr = np.array([1 for _ in range(ImgDataManager.img_info.hdr.bands)], dtype=np.uint8)
        ImgDataManager.wave_enabled_index_mask_arr = np.array([1 for _ in range(ImgDataManager.img_info.hdr.bands)], dtype=np.uint8)
        ImgDataManager.wave_enabled_index_list = [i for i in range(ImgDataManager.img_info.hdr.bands)]
        ImgDataManager.wave_enabled_list = copy.copy(ImgDataManager.img_info.hdr.wavelength)

        return


    @staticmethod
    def clear_img_info():
        '''
        当前图像非img格式的时候，进行清除
        '''
        ImgDataManager.img_info = None
        ImgDataManager.img_bip = None

        ImgDataManager.wave_start = 0
        ImgDataManager.wave_end = 0
        ImgDataManager.wave_index_start = 0
        ImgDataManager.wave_index_end = 0
        ImgDataManager.wave_range_index_mask_arr = None          
        ImgDataManager.wave_enabled_index_mask_arr = None       
        ImgDataManager.wave_enabled_index_list.clear()
        ImgDataManager.wave_enabled_list.clear()

        ImgDataManager.norm_max_value = 65535

        # 自动对齐以及对齐配置数据来自UI操作，不应该清除
        # ImgDataManager.auto_align_enabled = False
        # ImgDataManager.arr_align_conf = None
        ImgDataManager.img_align_state = False

        ImgDataManager.use_de_gain= False
        ImgDataManager.arr_gain = None
        ImgDataManager.arr_expo_time = None
        
        ImgDataManager.use_binning = False     
        ImgDataManager.binning_gap = 10
        ImgDataManager.use_smooth = 0      # 0: disable; 1: sg;  2: other;
        ImgDataManager.use_diff = 0        # 0: disable; 1: first ;  2:  second
        ImgDataManager.trans_seq.clear()


        return

    
    @staticmethod
    def set_auto_align(auto=False):
        if auto:
            if ImgDataManager.arr_align_conf is None:
                ImgDataManager.auto_align_enabled = False
                return False
        
        ImgDataManager.auto_align_enabled = auto
        return


    @staticmethod
    def set_align_config(file_path:str):

        ImgDataManager.arr_align_conf = get_align_params(file_path)
        return ImgDataManager.arr_align_conf


    @staticmethod
    def align_img(req=True):
        '''
        指定进行对齐操作的处理函数。
        img对齐是最基本的操作，如果图像进行对齐，则其他一切数据处理都将无效。
        即：img对齐是基于原始img的第一步操作
        '''
        
        # if req == ImgDataManager.img_align_state:
        #     return False, f"{'已经' if req else '未'}进行了对齐操作！"
        
        # if ImgDataManager.arr_align_conf is None:
        #     return False, "对齐配置为空"
        
        if req:
            ImgDataManager.img_bip = img_alignment(ImgDataManager.img_bip, 
                                                   ImgDataManager.arr_align_conf[1:,:],
                                                   interleave='bip')
            ImgDataManager.img_align_state = True
        else:
            ImgDataManager.img_bip = ImgDataManager.img_info.get_img_by_interleave('bip')
            ImgDataManager.img_align_state = False
        
        DrawingManager.set_ori_img()

        return True


    @staticmethod
    def save_aligned_img(file_path):

        hdrinfo = copy.copy(ImgDataManager.img_info.hdr)
        hdrinfo.interleave = 'bsq'
        img_aligned_bsq = ImgDataManager.img_info.get_img_by_interleave('bsq')
        img_aligned_bsq = img_alignment(img_aligned_bsq, ImgDataManager.arr_align_conf[1:,:])
        save_img(img_aligned_bsq, file_path, hdrinfo)

        return True
    
   
    
    @staticmethod
    def img_gain_adjust(de_gain_enabled):
        '''
        增益调整改变将无条件影响binning的结果
        '''
        ImgDataManager.use_de_gain = de_gain_enabled

        # if ImgDataManager.use_de_gain:
        #     arr_gain = ImgDataManager.arr_gain.reshape((1,1,-1))
        #     arr_expo_time = ImgDataManager.arr_expo_time.reshape((1,1,-1))
        #     ImgDataManager.img_bip_trans = ImgDataManager.img_bip.astype(np.float32)*1024/arr_gain/arr_expo_time
        # else:
        #     ImgDataManager.img_bip_trans = ImgDataManager.img_bip.astype(np.float32)

        # if ImgDataManager.use_binning and ImgDataManager.binning_gap > 0:
        #     ImgDataManager.set_binning_wave(gap=ImgDataManager.binning_gap)   # 刷新binning

        DrawingManager.on_data_transformed()

        return True


    @staticmethod
    def set_wv_range(wv_index_start=-1, wv_index_end=-1):
        '''
        img的实际波段信息
        '''
        cur_wv_index_start = wv_index_start if wv_index_start>=0 and wv_index_start<=ImgDataManager.img_info.hdr.bands-1 else ImgDataManager.wave_index_start
        cur_wv_index_end = wv_index_end if wv_index_end>=0 and wv_index_end<=ImgDataManager.img_info.hdr.bands-1 else ImgDataManager.wave_index_end
        if cur_wv_index_end >= cur_wv_index_start:

            ImgDataManager.wave_index_start = cur_wv_index_start
            ImgDataManager.wave_index_end = cur_wv_index_end
            ImgDataManager.wave_start = ImgDataManager.img_info.hdr.wavelength[ImgDataManager.wave_index_start]
            ImgDataManager.wave_end = ImgDataManager.img_info.hdr.wavelength[ImgDataManager.wave_index_end]

            ImgDataManager.wave_range_index_mask_arr[:] = 0
            ImgDataManager.wave_range_index_mask_arr[ImgDataManager.wave_index_start:ImgDataManager.wave_index_end+1] = 1

            ImgDataManager.wave_enabled_index_list.clear()
            ImgDataManager.wave_enabled_list.clear()

            mask = np.bitwise_and(ImgDataManager.wave_enabled_index_mask_arr, ImgDataManager.wave_range_index_mask_arr)
            for i in range(ImgDataManager.img_info.hdr.bands):
                if mask[i] > 0:
                    ImgDataManager.wave_enabled_index_list.append(i)
                    ImgDataManager.wave_enabled_list.append(ImgDataManager.img_info.hdr.wavelength[i])
            
        return
    

    @staticmethod
    def set_wave_enabled(wave_index_list:list, enabled=True):
        '''
        在有效范围波段列表中，对入参的wave_index_list进行使能操作
        '''
        for i in wave_index_list:
            if i <= 0 and i >=ImgDataManager.img_info.hdr.bands-1:
                ImgDataManager.wave_enabled_index_mask_arr[i] = 1 if enabled else 0

        ImgDataManager.wave_enabled_index_list.clear()
        ImgDataManager.wave_enabled_list.clear()
        mask = np.bitwise_and(ImgDataManager.wave_enabled_index_mask_arr, ImgDataManager.wave_range_index_mask_arr)
        for i in range(ImgDataManager.img_info.hdr.bands):
            if mask[i] > 0:
                ImgDataManager.wave_enabled_index_list.append(i)
                ImgDataManager.wave_enabled_list.append(ImgDataManager.img_info.hdr.wavelength[i])

        return


    @staticmethod
    def img_transform(trans=True):

        if ImgDataManager.use_binning and ImgDataManager.binning_gap > 0:
            pass



        return
    

    @staticmethod
    def set_binning_wave(enabled=True, gap=10):
        '''
        当enabled为False的时候，需要回退到de-gain的状态
        '''
        ImgDataManager.use_binning = enabled
        ImgDataManager.binning_gap = gap

        if not ImgDataManager.use_binning or ImgDataManager.binning_gap <= 0:  
            ImgDataManager.binning_wv_list.clear()
            ImgDataManager.binning_wv_index_list.clear()
            pass            
        else: 
        
            ImgDataManager.binning_wv_list, ImgDataManager.binning_wv_index_list = get_binning_wave(ImgDataManager.img_info.hdr.wavelength, gap)
            if len(ImgDataManager.binning_wv_list) == 0:
                pass
            else:
        
                # binning_img = np.zeros((ImgDataManager.img_bip_trans.shape[0], ImgDataManager.img_bip_trans.shape[1], len(ImgDataManager.binning_wv_list)), dtype=np.float32)
                # for i,(l,r) in enumerate(ImgDataManager.binning_wv_index_list):
                #     binning_img[:, :, i] = np.mean(ImgDataManager.img_bip_trans[:, :, l:r+1], axis=2)

                # ImgDataManager.img_bip_trans = binning_img
                ImgDataManager.wave_index_start = 0
                ImgDataManager.wave_index_end = len(ImgDataManager.binning_wv_list) - 1 
                ImgDataManager.wave_start = ImgDataManager.binning_wv_list[0]
                ImgDataManager.wave_end = ImgDataManager.binning_wv_list[ImgDataManager.wave_index_end]
                ImgDataManager.wave_range_index_mask_arr = np.array([1 for _ in range(len(ImgDataManager.binning_wv_list))], dtype=np.uint8)
                ImgDataManager.wave_enabled_index_mask_arr = np.array([1 for _ in range(len(ImgDataManager.binning_wv_list))], dtype=np.uint8)
                ImgDataManager.wave_enabled_index_list = [i for i in range(len(ImgDataManager.binning_wv_list))]
                ImgDataManager.wave_enabled_list = ImgDataManager.binning_wv_list

                return

        # 取消binning wave时，需要回退到de gain状态
        ImgDataManager.reset_wavelength_info()
        # ImgDataManager.img_bip_trans = ImgDataManager.img_bip.astype(np.float32).copy()
        # if ImgDataManager.use_de_gain:
        #     arr_gain = ImgDataManager.arr_gain.reshape((1,1,-1))
        #     arr_expo_time = ImgDataManager.arr_expo_time.reshape((1,1,-1))
        #     ImgDataManager.img_bip_trans = ImgDataManager.img_bip.astype(np.float32)*1024/arr_gain/arr_expo_time


        return
    

    @staticmethod
    def get_roi_wave(roi_or_xy:Union[np.ndarray, List[int]], shape=ShapeType.point, mean=True):
        '''
        计算shape对象的波形数值
        对于rect或polygon，根据mean决定是否计算平均值；如果mean=False则返回shape包含的全部像素的wave值
        '''

        if isinstance(roi_or_xy, list) and len(roi_or_xy)>=2 and shape==ShapeType.point:
            col = roi_or_xy[0]
            row = roi_or_xy[1]
            return ImgDataManager.img_bip[row, col, :].reshape(-1, 
                                                               ImgDataManager.img_info.hdr.bands)
        
        if isinstance(roi_or_xy, list) and len(roi_or_xy)>=4 and shape==ShapeType.rect:
            start_col = roi_or_xy[0]
            start_row = roi_or_xy[1]
            end_col = roi_or_xy[2]
            end_row = roi_or_xy[3]
            
            roi_img = ImgDataManager.img_bip[start_row:end_row+1, 
                                         start_col:end_col+1, :].reshape(-1, 
                                                                         ImgDataManager.img_info.hdr.bands)
            roi_wave_mean = np.mean(roi_img, axis=0)
            
            return roi_img
        
        if isinstance(roi_or_xy, list) and len(roi_or_xy)>=6 and shape==ShapeType.polygon:

            img_mask = np.zeros((ImgDataManager.img_bip.shape[0], ImgDataManager.img_bip.shape[1]), np.uint8)
            poly = np.array(roi_or_xy, dtype=np.int32).reshape(-1,2)
            cv2.fillConvexPoly(img_mask, poly, (1))
            img_mask = np.expand_dims(img_mask,2).repeat(ImgDataManager.img_bip.shape[2],axis=2)
            roi_img = ImgDataManager.img_bip[img_mask>0].reshape(-1, ImgDataManager.img_info.hdr.bands)
            roi_wave_mean = np.mean(roi_img, axis=0)

            return  roi_img
        
        return None

    
    @staticmethod
    def clip_save(file_path, pos_list):
        if len(pos_list)!=4:
            print("save_clip pos num should be 4!")
            return False

        start_x = min(pos_list[0], pos_list[2])
        start_y = min(pos_list[1], pos_list[3])
        end_x  =  max(pos_list[0], pos_list[2])
        end_y =   max(pos_list[1], pos_list[3])

        matrix = ImgDataManager.img_info.get_img_by_rect((start_y,end_y+1), (start_x,end_x+1))

        filename, ext = os.path.splitext(file_path)
        hdr_info = copy.deepcopy(ImgDataManager.img_info.hdr) 
        hdr_info.lines = end_y+1-start_y
        hdr_info.samples = end_x+1-start_x
                
        hdr_file_path = filename+".hdr"
        ImgInfo.write_hdr_file(hdr_file_path, hdr_info)

        if hdr_info.data_type == 1:
            matrix.tofile(file_path)
        elif hdr_info.data_type == 12:
            matrix.astype('<u2').tofile(file_path)

        return True


    @staticmethod
    def get_transformed_img():
        '''
        获取当前img经过数据变换之后的img
        '''

        img_bip_trans = ImgDataManager.img_bip.astype(np.float32)

        if ImgDataManager.use_de_gain:
            arr_gain = ImgDataManager.arr_gain.reshape((1,1,-1))
            arr_expo_time = ImgDataManager.arr_expo_time.reshape((1,1,-1))
            img_bip_trans = img_bip_trans*1024/arr_gain/arr_expo_time
        

        if ImgDataManager.use_binning and ImgDataManager.binning_gap > 0:
            binning_img = np.zeros((img_bip_trans.shape[0], img_bip_trans.shape[1], len(ImgDataManager.binning_wv_list)), dtype=np.float32)
            for i,(l,r) in enumerate(ImgDataManager.binning_wv_index_list):
                binning_img[:, :, i] = np.mean(img_bip_trans[:, :, l:r+1], axis=2)

            img_bip_trans = binning_img

        if ImgDataManager.use_norm:
            pass

        if ImgDataManager.use_diff>0:

            img_bip_trans = trans_diff(img_bip_trans, ImgDataManager.use_diff)

        return img_bip_trans
    
    
    @staticmethod
    def get_norm_img():

        if ImgDataManager.img_info.hdr.data_type == Img_Data_type.type_uint8:
            return ImgDataManager.img_bip.astype(np.float32)/255
        elif ImgDataManager.img_info.hdr.data_type == Img_Data_type.type_uint16:
            return ImgDataManager.img_bip.astype(np.float32)/65535
        else:
            max_value = np.max(ImgDataManager.img_bip)
            min_value = np.min(ImgDataManager.img_bip)
            if max_value - min_value == 0:
                return ImgDataManager.img_bip.astype(np.float32)/max_value
            else:
                return (ImgDataManager.img_bip.astype(np.float32)-min_value)/(max_value-min_value)
        


    @staticmethod
    def sam_result_between_samples_and_img(selected_id_list,  mean=True):
        '''
        mean: 是否计算平均值
        '''

        class_name_list = []
        wave_list = []
        for id in selected_id_list:
            shape = ShapeManager.shape_id_object_dict[id]
            class_name_list.append(str(id))
            wave_list.append(shape.get_transform_wave())
        
        stand_spectral_all = np.array(wave_list, dtype=np.float32)

        if mean:
            wave_mean = np.mean(stand_spectral_all, axis=0, keepdims=True)
            stand_spectral_all = np.concatenate([wave_mean, stand_spectral_all], axis=0)

        input_img = ImgDataManager.get_transformed_img()
        input_img = input_img.reshape((ImgDataManager.img_info.hdr.lines*ImgDataManager.img_info.hdr.samples, -1))

        distance = sam_distance(input_img, stand_spectral_all)
        distance = distance.reshape((ImgDataManager.img_info.hdr.lines, ImgDataManager.img_info.hdr.samples, -1))

        return distance           


class JpgDataManager:

    def __init__(self):
        
        pass


class TiffDataManager:

    def __init__(self):
        
        pass



if __name__ == '__main__':
    
    if 0:
        from matplotlib.font_manager import FontManager

        mpl_fonts = set(f.name for f in FontManager().ttflist)

        print('all font list get from matplotlib.font_manager:')
        for f in sorted(mpl_fonts):
            print('\t' + f)


    shape = Shape(1, ShapeType.point, 'red', 'abc')

    ll= []
    dd = {}
    ll.append(shape)
    dd['aa'] = shape

    shape = None
    print(ll[0].color)
    print(dd['aa'].color)


    import tkinter as tk

    # 初始化Tk窗口
    root = tk.Tk()

    # 创建一个Canvas控件
    canvas = tk.Canvas(root, width=200, height=200)
    canvas.pack()

    # 定义两个点的坐标
    point1 = (50, 50)
    point2 = (150, 150)

    canvas.create_polygon([30, 30], fill='blue', outline='blue')

    canvas.create_polygon([point1, point2], fill='red', outline='red')

    canvas.create_rectangle([180, 60, 150, 30], fill='green', outline='blue')

    # 运行Tk窗口的主循环
    root.mainloop()

    pass