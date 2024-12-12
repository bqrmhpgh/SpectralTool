import numpy as np
import cv2
from sklearn import preprocessing
from copy import deepcopy
import pandas as pd
import os
from Img_Functions import ImgInfo, HDRInfo, save_img
# import torch
from numpy import random
import matplotlib.colors as mcolors
import random
import logging
from scipy.signal import savgol_filter
from PIL import Image
import copy
import shutil


COLOR_CONF_LIST = [
    'red', 'lime', 'aqua',  'yellow', 'fuchsia', 'deepskyblue', 
    'tomato', 'green', 'paleturquoise','gold', 'darkviolet', 'blue',
    'pink', 'palegreen', 'teal', 'orange', 'mediumslateblue', 'lightsteelblue',
    'tan', 'olive', 'darkgray', 'lightslategray'
    ]

COLOR_ALLOC_MARK_LIST = [1]*len(COLOR_CONF_LIST)  # 1: available; 0: unavailable

def rgb_tuple_2_hexstr(rgb, order_rgb=True):
    if 0<=rgb[0]<=255 and 0<=rgb[1]<=255 and 0<=rgb[2]<=255:
        if order_rgb:
            return "#{:02x}{:02x}{:02x}".format(rgb[0], rgb[1], rgb[2])
        else:
            return "#{:02x}{:02x}{:02x}".format(rgb[2], rgb[1], rgb[0])
    else:
        return "#{:02x}{:02x}{:02x}".format(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))


def random_color_hexstr():
    """Return a random color in hex format."""
    return "#{:02x}{:02x}{:02x}".format(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))

def random_color_tuple():
    """Return a random color in hex format."""
    return (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))


def mcolor_2_hexstr(color_name, rgb=True):
    rgb = mcolors.to_rgb(color_name)
    rgb_255 = [int(c*255) for c in rgb]
    if rgb:
        return "#{:02x}{:02x}{:02x}".format(rgb_255[0], rgb_255[1], rgb_255[2])
    else:
        return "#{:02x}{:02x}{:02x}".format(rgb_255[2], rgb_255[1], rgb_255[0])
    
    
def mcolor_2_tuple(color_name, rgb=True):
    rgb = mcolors.to_rgb(color_name)
    rgb_255 = [int(c*255) for c in rgb]
    if rgb:
        return (rgb_255[0], rgb_255[1], rgb_255[2])
    else:
        return (rgb_255[2], rgb_255[1], rgb_255[0])


class Label_Info:

    label_color = {
        "0": "red",
        "1": "cyan",
        "2": "fuchsia",
        "3": "orange"
    }

    def __init__(self,label="", img_w=0, img_h=0, x0=-1, y0=-1, x1=-1, y1=-1,
                 yolo_cx=-1,yolo_cy=-1,yolo_w=-1,yolo_h=-1):

        self.label = label
        self.color = Label_Info.label_color.get(label, random_color_hexstr())
        self.x0 = x0
        self.y0 = y0
        self.x1 = x1
        self.y1 = y1
        self.img_w = img_w
        self.img_h = img_h
        self.yolo_cx = yolo_cx
        self.yolo_cy = yolo_cy
        self.yolo_w = yolo_w
        self.yolo_h = yolo_h

        self.draw_id = None
        self.text_id = None
        pass


    def set_img_wh(self, w, h):
        self.img_h = h
        self.img_w = w


    def set_color(self, label):
        self.color = Label_Info.label_color.get(label, random_color_hexstr())
        pass

    def set_rect_info(self, x0, y0, x1, y1):
        self.x0 = x0
        self.y0 = y0
        self.x1 = x1
        self.y1 = y1
        pass

    def set_yolo_info(self, yolo_cx,yolo_cy,yolo_w,yolo_h):
        self.yolo_cx = yolo_cx
        self.yolo_cy = yolo_cy
        self.yolo_w = yolo_w
        self.yolo_h = yolo_h
        pass


    def to_yolo_info(self):
        if self.img_w == 0 or self.img_h == 0:
            return
        self.yolo_cx = (self.x0+self.x1)/2/self.img_w
        self.yolo_cy = (self.y0+self.y1)/2/self.img_h
        self.yolo_w = (self.x1 - self.x0)/self.img_w
        self.yolo_h = (self.y1 - self.y0)/self.img_h


    def to_rect_info(self):

        if self.img_w == 0 or self.img_h == 0:
            return

        self.x0 = round(self.yolo_cx*self.img_w - (self.yolo_w*self.img_w)/2)
        self.x1 = round(self.yolo_cx*self.img_w + (self.yolo_w*self.img_w)/2)
        self.y0 = round(self.yolo_cy*self.img_h - (self.yolo_h*self.img_h)/2)
        self.y1 = round(self.yolo_cy*self.img_h + (self.yolo_h*self.img_h)/2)


    def get_rect_xy_list(self):
        return [self.x0, self.y0, self.x1, self.y1]
    

    def set_id(self, draw_id, text_id):
        if draw_id is not None:
            self.draw_id = draw_id
        if text_id is not None:    
            self.text_id = text_id
        pass

        
    def clear_id(self):
        self.draw_id = None
        self.text_id = None
        pass

    pass


def img_stretch(img:np.ndarray, l:np.uint8, m:np.uint8, u:np.uint8):
    '''
    图像3点拉伸(l-m之间的值拉伸到0-128; m-u之间的值拉伸到128-255)
    '''
    img_f = img.astype(np.float32)

    img_mask = np.zeros(img.shape, dtype=np.uint8)
    img_mask[img>m] = 255

    img_left = (img_f - l) * 128 / (m-l)
    img_left = img_left.clip(0,255).astype(np.uint8)
    img_left = np.bitwise_and(img_left, np.bitwise_not(img_mask))

    img_right = (img_f - m) * 128 / (u-m) + 128
    img_right = np.bitwise_and(img_right.clip(0,255).astype(np.uint8), img_mask)


    # img[img<=m] = (img[img<=m] - l) * m_center / (m-l)
    # img[img>m]  = (img[img>m] - m) * m_center / (u-m) + m_center
    # img = img.clip(0,m_max)

    # return img

    return img_left + img_right



def get_index_range_of_wave_range(src_wave_list, dst_wav_start, dst_wv_end):
    '''
    在wave_list中查找wav_range范围的波段索引
    dst_wav_range: [,]
    '''
    left = -1
    right = -1

    if dst_wav_start > 0 and dst_wv_end >= dst_wav_start:
        for i, wv in enumerate(src_wave_list):
            if wv < dst_wav_start:
                continue
            elif wv <= dst_wv_end:
                if left < 0:
                    left = i
                right = i
                continue
            else:
                break
            
    return left, right


def sam_distance(X:np.ndarray, Y:np.ndarray):
    '''
    计算两组向量的SAM距离。
    输入: X:M*B; Y:N*B (M，N是向量数量，B是向量特征)
    输出: M*N 的距离

    '''
    if X.ndim == 1:
        X = X.reshape(1,-1)

    if Y.ndim == 1:
        Y = Y.reshape(1,-1)

    XX = X*X    # M*B
    YY = Y*Y    # N*B
    XY = np.matmul(X,Y.T)   # M*N
    
    X1 = np.sqrt(np.sum(XX, axis=1, keepdims=1))
    Y1 = np.sqrt(np.sum(YY, axis=1, keepdims=1))

    X = np.repeat(X1, Y1.shape[0], axis=1)

    return XY/(X*Y1.T)


def trans_none(img:np.ndarray):
    return img


def trans_diff1(img:np.ndarray):
    '''
    差分处理, 并乘以factor。 img.shape = N*C, or M*N*C 
    '''
    if img.ndim == 1:
        img = np.diff(img, n=1)
        img = np.concatenate((img, img[-2:-1]))
    elif img.ndim == 2:
        img = np.diff(img, n=1, axis=1)
        img = np.hstack((img, img[:,-1].reshape(-1,1)))
    elif img.ndim == 3:
        img = np.diff(img, n=1, axis=2)
        img = np.concatenate((img, img[:,:,-1].reshape(img.shape[0],img.shape[1],1)), axis=2)

    return img


def max_min_normalization(self, data):
        """
        最大最小归一化
        """
        data = deepcopy(data)
        # min = np.min(data, axis=0)
        # max = np.max(data, axis=0)
        # res = (data - min) / (max - min)
        if isinstance(data, pd.DataFrame):
            data = data.values
        min_max_scaler = preprocessing.MinMaxScaler()
        res = min_max_scaler.fit_transform(data.T)
        return res.T

def trans_maxmin_stretch(img:np.ndarray):
    return img



def trans_diff(img:np.ndarray, diff_times=1, diff_factor=1):
        '''
        差分处理, 并乘以factor。 img.shape = N*C, or M*N*C 
        '''
        if img.ndim == 1:
            img = (np.diff(img,n=diff_times))*diff_factor
            if diff_times == 1:
                img = np.hstack((img, img[-1]))
            elif diff_times == 2:
                img = np.hstack((img[0], img, img[-1]))
        if img.ndim == 2:
            img = (np.diff(img,n=diff_times, axis=1))*diff_factor
            if diff_times == 1:
                img = np.hstack((img, img[:,-1].reshape(-1,1)))
            elif diff_times == 2:
                img = np.hstack((img[:,0].reshape(-1,1), img, img[:,-1].reshape(-1,1)))
        elif img.ndim == 3:
            img = np.diff(img,n=diff_times, axis=2)*diff_factor
            if diff_times == 1:
                img = np.concatenate((img, img[:,:,-1].reshape(img.shape[0],img.shape[1],1)), axis=2)
            elif diff_times == 2:
                img = np.concatenate((img[:,:,0].reshape(img.shape[0],img.shape[1],1), img, img[:, :,-1].reshape(img.shape[0],img.shape[1],1)), axis=2)
 
        return img


def trans_sg(img:np.ndarray, window_size=5, polynomial_order=2):

    if img.ndim == 2:
        img = savgol_filter(img, window_length=window_size, polyorder=polynomial_order, axis=1)
    elif img.ndim == 3:
        img = savgol_filter(img, window_length=window_size, polyorder=polynomial_order, axis=2)
    else:
        img = savgol_filter(img, window_length=window_size, polyorder=polynomial_order)
    
    return img

    
def trans_diff1_enhanced(img:np.ndarray, diff_factor=1, ):



    pass

def test_sam_distance():
    '''
    answer:
        [[[0.9258201  0.9258201  0.81649658 0.68523092]]]
    '''

    data = np.ones((2,3), dtype=np.float32)

    sam = np.array([
    [1, 3, 2,],
    [1, 2, 3,],
    [1, 4, 9,],
    [1, 16, 81]
    ], dtype=np.float32)

    dist = sam_distance(data, sam)
    print(dist)

    pass


def RGB2HSV(R, G, B, base=255):
    '''
    RGB转HSV， 返回(h,s,v). 参考opencv的公式
    '''
    R = R/base
    G = G/base
    B = B/base

    v = max([R, G, B])

    s = 0
    if v!=0:
        s = (v - min([R, G, B]))/v

    if R==G and G==B:
        h = 0
    elif v == R:
        h = 0 + 60*(G-B)/(v - min(R,G,B))
    elif v == G:
        h = 120 + 60*(B-R)/(v - min(R,G,B))
    elif v == B:
        h = 240 + 60*(R-G)/(v - min(R,G,B))

    if h<0:
        h = h+360

    return h,s,v


# g_align_array = np.array(
#     [
#         [-10,0],    # jpg
#         [6,2],    # 450  w, h
#         [-13,-10],    # 550
#         [-5,-10],
#         [0,0],
#         [1,-10],
#         [-2,-24],
#         [7,-17],    # 850
#     ], dtype=np.int32
# )

'''
#define TRANSFORM_FirstDerivative   ((uint8_t)0)
#define TRANSFORM_SecondDerivative  ((uint8_t)1)
#define TRANSFORM_SavitzkyGolay     ((uint8_t)2)
#define TRANSFORM_SNV     ((uint8_t)3)
#define TRANSFORM_CubicSmooth7     ((uint8_t)4)

#define TRANSFORM_Stretch_MaxMin  ((uint8_t)20)
#define TRANSFORM_Stretch_01  ((uint8_t)21)
#define TRANSFORM_Stretch_02  ((uint8_t)22)
#define TRANSFORM_Stretch_03  ((uint8_t)23)

#define TRANSFORM_FirstDerivativeEnhanced     ((uint8_t)100)
#define TRANSFORM_Stretch_SNV_Concat     ((uint8_t)101)
'''
TRANSFORMS_DEF = {
    'None': {
        'name': "无",
        'func': trans_none,
        'id': -1
        } ,
    'Diff1': {
        'name': "一阶Diff",
        'func': trans_diff1,
        'id': 0
        } , 
    'Diff2': {
        'name': "二阶Diff",
        'func': trans_diff,
        'id': 1
        } ,
    'FirstDerivativeEnhanced':  {
        'name': "一阶导增强",
        'func': trans_diff1_enhanced,
        'id': 100
        } ,
    'SavitzkyGolay':  {
        'name': "SG平滑",
        'func': trans_sg,
        'id': 2
        } ,
    'MaxMinStretch':  {
        'name': "最值拉伸",
        'func': trans_maxmin_stretch,
        'id': 21
        } ,
}


def transform_process(trans_key, wave):
    if trans_key not in TRANSFORMS_DEF:
        return wave
    func =  TRANSFORMS_DEF[trans_key]['func']   
    return func(wave)


def get_transid_by_name(name):
    for key in TRANSFORMS_DEF:
        trans = TRANSFORMS_DEF[key]
        if name == trans['name']:
            return trans.get('id', '')
    
    return ''


def get_transid_by_key(key):
    if key in TRANSFORMS_DEF:
        trans = TRANSFORMS_DEF[key]
        return trans.get('id', '')
    
    return ''


def get_transkey_by_name(name):
    for key in TRANSFORMS_DEF:
        if TRANSFORMS_DEF[key]['name'] == name:
            return key
    return None


def get_transkey_by_id(id):
    for key in TRANSFORMS_DEF:
        if TRANSFORMS_DEF[key]['id'] == id:
            return key
    return None


def test_rgb2hsv():
    h,s,v = RGB2HSV(40, 52, 65)  # return: 211.2 0.3846153846153846 0.2549019607843137
    print(h,s,v)
    print(h/2,s*255,v*255)

    img = np.zeros((200,100,3), dtype=np.uint8)   # H, W, C
    img[:,:,0] = 65    # B
    img[:,:,1] = 52    # G
    img[:,:,2] = 40    # R

    print(img[0,0,:])
    cv2.imshow("rgb_image", img)
    cv2.waitKey()
    cv2.destroyAllWindows()

    arr = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    print(arr[0,0,:])
    #   [[106  98  65]
    #   [106  98  65]
    #   [106  98  65]]]


def test_hsv_filter():
    
    img = cv2.imread("Res/MAX_20240319_002_MAX_0002_Color_D.jpg")
    print(img.shape)

    hsv_arr = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    # print(hsv_arr)
    lowerb = (200//2, int(0*255), int(0*255))
    upperb = (250//2, int(0.7*255), int(0.5*255))

    # lowerb[0] = lowerb[0]//2
    # lowerb[1] = int(lowerb[1]*255)
    # lowerb[2] = int(lowerb[2]*255)
    # upperb[0] = upperb[0]//2
    # upperb[1] = int(upperb[1]*255)
    # upperb[2] = int(upperb[2]*255)


    hsv_filter = cv2.inRange(hsv_arr, lowerb, upperb)
    print(hsv_filter.shape)

    cv2.imshow("hsv result", hsv_filter)
    cv2.waitKey()
    cv2.destroyAllWindows()

    pass



def get_align_params(conf_path, line_count=8):
    '''
    从align.conf文件中读取img各个波段以及jpg之间的像素偏移值
    line_count等于波段数量+1（jpg）
    '''
    align_list = []

    r = 0
    with open(conf_path, "r", encoding='utf-8') as f:
        for line in f:
            line = line.replace('\t', '')
            line = line.strip()
            if line.startswith("#"):
                continue
            
            line = line.split("#")[0]
            print(line)
            v_str = line.split(',')
            if len(v_str) < 2:
                print("align config: at least 2 numbers each line!")
                return None
            try:
                v_str = v_str[:2]
                v = [int(i) for i in v_str]
                
            except:
                print("align config: should be integer numbers in each line!")
                return None
            # g_align_array[r][0] = v[0]
            # g_align_array[r][1] = v[1]

            align_list.append([v[0], v[1]])
            r += 1

            if r == line_count:
                break
            
        pass

    return np.array(align_list, dtype=np.int32)


def img_alignment(img:np.ndarray, img_align_array:np.ndarray, interleave='bsq'):
    '''
    img 对齐操作 (bsq or bip)。
    img: [c, h, w] or [h,w,c]  
    img_align_array 不包括rgb的偏移项 [channel_num, 2]
    720的左上角是(wh最大偏移正值)
    '''

    # align_offset = g_align_array[1:,:]
    align_offset = img_align_array

    pos_max_w = 0   # 也就是720的左上角坐标
    pos_max_h = 0   # 也就是720的左上角坐标
    neg_max_w = 0
    neg_max_h = 0

    for i in range(img_align_array.shape[0]):
        spec_offset = img_align_array[i]
        if spec_offset[0]>0:
            if spec_offset[0]>pos_max_w:
                pos_max_w = spec_offset[0]
        elif spec_offset[0]<0:
            if spec_offset[0] < neg_max_w:
                neg_max_w = spec_offset[0]

        if spec_offset[1]>0:
            if spec_offset[1]>pos_max_h:
                pos_max_h = spec_offset[1]
        elif spec_offset[1]<0:
            if spec_offset[1]<neg_max_h:
                neg_max_h = spec_offset[1]
        pass

    expansion_w = pos_max_w - neg_max_w
    expansion_h = pos_max_h - neg_max_h
   
    if interleave == 'bsq':
        out_img = np.zeros((img.shape[0], img.shape[1]+expansion_h, img.shape[2]+expansion_w), dtype=img.dtype)
        for i in range(img_align_array.shape[0]):
            w_start = pos_max_w - img_align_array[i][0]
            h_start = pos_max_h - img_align_array[i][1]
            out_img[i, h_start:h_start+img.shape[1], w_start:w_start+img.shape[2]] = img[i,:,:]
    
        return out_img[:, pos_max_h:pos_max_h+img.shape[1], pos_max_w:pos_max_w+img.shape[2]].copy()
    else:
        out_img = np.zeros((img.shape[0]+expansion_h, img.shape[1]+expansion_w, img.shape[2]), dtype=img.dtype)
        for i in range(img_align_array.shape[0]):
            w_start = pos_max_w - img_align_array[i][0]
            h_start = pos_max_h - img_align_array[i][1]
            out_img[h_start:h_start+img.shape[0], w_start:w_start+img.shape[1], i] = img[:, :, i]

        return out_img[pos_max_h:pos_max_h+img.shape[0], pos_max_w:pos_max_w+img.shape[1], :].copy()




def batch_process_alignment(file_dir, img_align_array:np.ndarray):

    img_list = []
    for filename in os.listdir(file_dir):
        basename, ext = os.path.splitext(filename)
        if ext != '.img':
            continue
        if 'aligned' in basename:
            continue
        
        img_path = os.path.join(file_dir, filename)
        img_list.append(img_path)

    for img_path in img_list:

        img_info = ImgInfo()
        ret, _ = img_info.create_img_info(img_path)
        if not ret:
            print(f"get_img_info error: {img_path}")
            continue

        img = img_info.img
        hdr = img_info.hdr

        filename, _ = os.path.splitext(img_path)

        out_filename = filename + "_aligned"

        out_img_path = out_filename + ".img"

        img = img_alignment(img, img_align_array)

        print(out_img_path)
        save_img(img, out_img_path, hdr)


    pass


def get_rgb_by_color_name(color:str):

    rgb = mcolors.to_rgb(color)
    rgb_255 = [int(c*255) for c in rgb]

    return tuple(rgb_255)



def on_segment(p, q, r):
    """判断点r是否在线段pq上"""
    if (q[0] <= max(p[0], r[0]) and q[0] >= min(p[0], r[0]) and
        q[1] <= max(p[1], r[1]) and q[1] >= min(p[1], r[1])):
        return True
    return False

def orientation(p, q, r):
    """计算有向面积（叉积），判断三点p, q, r的相对位置"""
    val = (q[1] - p[1]) * (r[0] - q[0]) - (q[0] - p[0]) * (r[1] - q[1])
    if val == 0: return 0  # 共线
    elif val > 0: return 1 # 左侧
    else: return 2         # 右侧

def do_intersect(p1, q1, p2, q2):
    """判断线段p1q1和p2q2是否相交"""
    o1 = orientation(p1, q1, p2)
    o2 = orientation(p1, q1, q2)
    o3 = orientation(p2, q2, p1)
    o4 = orientation(p2, q2, q1)

    # 一般情况
    if (o1 != o2 and o3 != o4):
        return True

    # 特殊情况：线段共线
    if (o1 == 0 and on_segment(p1, p2, q1)): return True
    if (o2 == 0 and on_segment(p1, q2, q1)): return True
    if (o3 == 0 and on_segment(p2, p1, q2)): return True
    if (o4 == 0 and on_segment(p2, q1, q2)): return True

    return False


def get_polygon_from_labelme(json_file_path):
    polygon_list = []
    import json
    with open(json_file_path, 'r' ,encoding='utf-8') as f:
        data = json.load(f)
        for shape in data['shapes']:
            if shape['shape_type'] == 'polygon':
                xy_list = [[int(i[0]), int(i[1])] for i in shape['points']]
                polygon_list.append(xy_list)
                # polygon_list.append(shape['points'])
            pass
    
    return polygon_list


def get_rect_from_yolo_label_file(yolo_label_path:str, img_w:int=0, img_h:int=0):
    if img_w == 0 or img_h == 0:
        return []
    
    rect_list = []
    
    with open(yolo_label_path, encoding="utf-8") as f:
        lines = f.readlines()

    for index, line in enumerate(lines):
        line_list = line.strip().replace("\n", "").split(' ')
        if len(line_list) < 5:
            continue

        label = line_list[0].strip()
        cx = float(line_list[1].strip())    
        cy = float(line_list[2].strip())
        w = float(line_list[3].strip())
        h = float(line_list[4].strip())

        x0 = round(cx*img_w - (w*img_w)/2)
        x1 = round(cx*img_w + (w*img_w)/2)
        y0 = round(cy*img_h - (h*img_h)/2)
        y1 = round(cy*img_h + (h*img_h)/2)

        rect_list.append([x0, y0, x1, y1])
        
    return rect_list


def get_random_index_for_list(list_length, item_num=6):

    ll = [i for i in range(list_length)]
    if list_length <=item_num:
        return ll
    
    random.shuffle(ll)
    return ll[:item_num]


def new_xy_validate(xy_list:np.ndarray, index, x, y):
    point_num = len(xy_list)
    if index == 0:
        index_l = point_num - 1
    else:
        index_l = index - 1

    if index == point_num - 1:
        index_r = 0
    else:
        index_r = index + 1

    for i, start_pt in enumerate(xy_list):

        if i == point_num - 1:
            i_next = 0
        else:
            i_next = i + 1
        
        p1 = xy_list[i]
        q1 = xy_list[i_next] 

        if i in [index_l, index, index_r] or i_next in [index_l, index, index_r]:
            continue
        
        p2 = xy_list[index_l]
        q2 = [x,y]
        if do_intersect(p1, q1, p2, q2):
            return False
        
        p2 = [x,y]
        q2 = xy_list[index_r]
        if do_intersect(p1, q1, p2, q2):
            return False

        pass

    return True


def get_closest_point(row, col, dst_arr, foreground=True):

    r = 1
    r_max = 100

    while r<=r_max:
        start_r = row-r if row-r>=0 else 0
        end_r = row+r+1 if row+r+1 <= dst_arr.shape[0] else dst_arr.shape[0]
        start_c = col-r if col-r>=0 else 0
        end_c = col+r+1 if col+r+1 <= dst_arr.shape[1] else dst_arr.shape[1]
        
        for ri in range(start_r, end_r, 1):
            for ci in range(start_c, end_c, 1):
                if ri == row and ci == col:
                    continue
                if foreground:    
                    if dst_arr[ri,ci] == 255:
                        return ri,ci
                else:
                    if dst_arr[ri,ci] == 0:
                        return ri,ci

        r += 1
        pass
    pass

    return -1, -1


def get_point_to_fill(row, col, dst_arr, foreground=True):


    pass

import math
def points_list_get_bbox(polygon, img_size, output=''):
    """
    :param polygon: 多边形顶点列表 [(x, y), (x, y)```]
    :param img_size: 图像尺寸：（width，height）
    :param output: 输出路径
    """
    min_x = math.floor(min(point[0] for point in polygon)) - 2 if math.floor(min(point[0] for point in polygon)) > 2 else 0   # 取整并扩展边界
    max_x = math.ceil(max(point[0] for point in polygon)) + 2 if math.ceil(max(point[0] for point in polygon)) + 2 <= img_size[0] else img_size[0]
    min_y = math.floor(min(point[1] for point in polygon)) - 2 if math.floor(min(point[1] for point in polygon)) > 2 else 0
    max_y = math.ceil(max(point[1] for point in polygon)) + 2 if math.ceil(max(point[1] for point in polygon)) + 2 <= img_size[1] else img_size[1]

    # 构建外接矩形的四个顶点坐标
    height = (max_y - min_y)/img_size[1]
    width = (max_x - min_x)/img_size[0]
    cx = ((min_x + max_x) / 2)/img_size[0]
    cy = ((min_y + max_y) / 2)/img_size[1]
    data = str(cx) + " " + str(cy) + " " + str(width) + " " + str(height)
    with open(output, 'a+') as file:
        file.writelines("2 " + data + '\n')


def rect_2_yolo_bbox( rect_xy_list:list, img_size, output=''):
    """
    :param rect_xy_list: 矩形左上角和右下角坐标 [x, y, x, y]
    :param img_size: 图像尺寸：（width，height）
    :param output: 输出路径
    """
    min_x = rect_xy_list[0]
    max_x = rect_xy_list[2]
    min_y = rect_xy_list[1]
    max_y = rect_xy_list[3]

    # 构建外接矩形的四个顶点坐标
    height = (max_y - min_y)/img_size[1]
    width = (max_x - min_x)/img_size[0]
    cx = ((min_x + max_x) / 2)/img_size[0]
    cy = ((min_y + max_y) / 2)/img_size[1]
    data = str(cx) + " " + str(cy) + " " + str(width) + " " + str(height)
    with open(output, 'a+') as file:
        file.writelines("2 " + data + '\n')


def polygon_insert_points(poly_list, dist_len_gap=10):

    pt_num = len(poly_list)
    if pt_num <= 1:
        return

    for i in range(pt_num):
        pt_i = poly_list[i]
        if i == pt_num-1 and i == 1:
            continue
        elif i == pt_num-1 and i > 1:
            pt_j = poly_list[0]
        else:
            pt_j = poly_list[i+1]
        pass
        
        d = abs(pt_i[0]-pt_j[0]) + abs(pt_i[1]-pt_j[1])
        if d>=dist_len_gap:
            min_pt_x = min(pt_i[0], pt_j[0])
            min_pt_y = min(pt_i[1], pt_j[1])
            n = dist_len_gap // 6
            for k in range(n):
                pt_x = int(min_pt_x + abs(pt_i[0]-pt_j[0])*(k+1)*6/dist_len_gap)
                pt_y = int(min_pt_y + abs(pt_i[1]-pt_j[1])*(k+1)*6/dist_len_gap)
                poly_list.append([pt_x, pt_y])
            pass
    pass


def sample_expansion(file_dir, num_per_img=10, random_pt_num=4, offset_r=5, new_pix_num_thres=0.8):

    # src_dir = os.path.dirname(file_dir)
    file_list = os.listdir(file_dir)

    dst_dir = os.path.join(file_dir, "output")
    if not os.path.exists(dst_dir):
        os.makedirs(dst_dir)

    for file_name in file_list:
        file_path = os.path.join(file_dir, file_name)
        if os.path.isdir(file_path):
            continue
        name, ext = os.path.splitext(file_path)
        if ext != '.jpg' and ext != '.png':
            continue

        labelme_path = name + ".json"
        if not os.path.exists(labelme_path):
            continue
        
        poly_list = get_polygon_from_labelme(labelme_path)
        if len(poly_list) == 0:
            continue

        from shapely.geometry import Polygon
        max_area = 0
        index = -1
        for i, pt_list in enumerate(poly_list):
            poly = Polygon(pt_list)
            print(poly.area)  # 输出多边形面积
            if poly.area > max_area:
                max_area = poly.area
                index = i

        xy_list = poly_list[index]
        point_num = len(xy_list)

        xy_arr = np.array(xy_list, dtype=np.int32)

        # image = cv2.imread(file_path)
        image = cv2.imdecode(np.fromfile(file_path, dtype=np.uint8), -1)
        
        # image_ori = image.copy()
        # cv2.namedWindow("original")
        # cv2.polylines(image_ori, [xy_arr], isClosed=True, color=(255,0,0), thickness=2)
        # cv2.imshow("original", image_ori)

        ori_mask = np.zeros((image.shape[0], image.shape[1]), np.uint8)   # H * W
        cv2.fillPoly(ori_mask, [xy_arr.reshape((-1, 1, 2))], 255)

        kernel = np.ones((9,9),np.uint8)
        ori_mask_shrink = cv2.erode(ori_mask, kernel)

        # fore_indices = np.where(ori_mask_shrink==255)
        # fore_pix_xy = list(zip(fore_indices[0], fore_indices[1]))

        basename, _ = os.path.splitext(file_name)

        for num_gen in range(num_per_img):
            print(f"gen num {num_gen+1} ......")

            out_image_path = os.path.join(dst_dir, f"{basename}_{num_gen+1}.jpg")
            out_yolo_path = os.path.join(dst_dir, f"{basename}_{num_gen+1}.txt")

            image_gen = image.copy()

            new_xy_arr = xy_arr.copy()
            new_point_list_index = get_random_index_for_list(point_num, random_pt_num)

            for index in new_point_list_index:
                cur_pt = new_xy_arr[index]
                max_fail_count = 10000
                n = 0
                new_x = cur_pt[0]
                new_y = cur_pt[1]
                while n<max_fail_count:
                    x = random.randint(cur_pt[0]-offset_r, cur_pt[0]+offset_r)
                    y = random.randint(cur_pt[1]-offset_r, cur_pt[1]+offset_r)
                    # new_x, new_y 不能与其他连线相交
                    if new_xy_validate(new_xy_arr, index, x, y):
                    # if 1:
                        new_x = x
                        new_y = y
                        break

                    n += 1
                    pass

                new_xy_arr[index,0] = new_x
                new_xy_arr[index,1] = new_y

                pass
            
            # 填充处理
            
            new_mask = np.zeros((image.shape[0], image.shape[1]), np.uint8)   # H * W
            cv2.fillPoly(new_mask, [new_xy_arr], 255)

            xor_mask = ori_mask != new_mask
            
            # 遍历变化了的像素
            changed_indices = np.where(xor_mask==True)
            changed_rc = list(zip(changed_indices[0], changed_indices[1]))

            for r,c in changed_rc:
                if ori_mask[r, c] == 0:   # 填充前景
                    dr, dc = get_closest_point(r,c, ori_mask_shrink,foreground=True)
                    if dc<0:
                        print("error!")
                        dr = r
                        dc = c
                    pass
                    image_gen[r, c, 0] = image[dr, dc, 0]
                    image_gen[r, c, 1] = image[dr, dc, 1]
                    image_gen[r, c, 2] = image[dr, dc, 2]

                else:                           # 填充背景
                    dr, dc = get_closest_point(r,c, ori_mask,foreground=False)
                    if dc<0:
                        print("error!")
                        dr = r
                        dc = c
                    pass

                    image_gen[r, c, 0] = image[dr, dc, 0]
                    image_gen[r, c, 1] = image[dr, dc, 1]
                    image_gen[r, c, 2] = image[dr, dc, 2]
     
            
            if 0:
                cv2.polylines(image_gen, [new_xy_arr], isClosed=True, color=(0,0,255), thickness=1)
                cv2.namedWindow(f"new-{num_gen+1}")
                cv2.imshow(f"new-{num_gen+1}", image_gen)
                cv2.waitKey(0)
                cv2.destroyWindow(f"new-{num_gen+1}")

            # 输出图像和轮廓
            print(out_image_path)
            # cv2.imwrite(out_image_path, image_gen)
            cv2.imencode(".jpg", image_gen)[1].tofile(out_image_path)
            print(out_yolo_path)
            points_list_get_bbox(new_xy_arr, (image.shape[1], image.shape[0]), out_yolo_path)


        pass

        # cv2.destroyWindow("original") 
    pass



def polygon_reshaping(file_path, out_path, type=0, seq=0, mask=None, n=2, method=cv2.DECOMP_LU):
    '''
    type: 0-yolo ; 1: labelme
    
    '''

    if os.path.isdir(file_path):
        return 
    
    if not os.path.exists(file_path):
        return 
    
    name, ext = os.path.splitext(file_path)
    if ext != '.jpg' and ext != '.png':
        return
    
    if type > 0: 
        label_path = name + ".json"
    else:
        label_path = name + ".txt"
    
    if not os.path.exists(label_path):
        return

    filename = os.path.basename(file_path)
    basename, _ = os.path.splitext(filename)
        
    image_ori = cv2.imdecode(np.fromfile(file_path, dtype=np.uint8), -1)   # 中文路径 HWC
    img_w = image_ori.shape[1]
    img_h = image_ori.shape[0]

    if type > 0:
        poly_list = get_polygon_from_labelme(label_path)
    else:
        poly_list = get_rect_from_yolo_label_file(label_path, img_w, img_h)

    if len(poly_list) == 0:
        return None,None
    
    for index in range(len(poly_list)):
        image = image_ori.copy()
        xy_list = poly_list[index]
        if type > 0:
            oil_x0 = math.floor(min(point[0] for point in xy_list)) - 2 if math.floor(min(point[0] for point in xy_list)) > 2 else 0   # 取整并扩展边界
            oil_x1 = math.ceil(max(point[0] for point in xy_list)) + 2 if math.ceil(max(point[0] for point in xy_list)) + 2 <= image.shape[1] else image.shape[1]
            oil_y0 = math.floor(min(point[1] for point in xy_list)) - 2 if math.floor(min(point[1] for point in xy_list)) > 2 else 0
            oil_y1 = math.ceil(max(point[1] for point in xy_list)) + 2 if math.ceil(max(point[1] for point in xy_list)) + 2 <= image.shape[0] else image.shape[0]
        else:
            oil_x0 = xy_list[0] - 2 if xy_list[0] >= 2 else 0   
            oil_x1 = xy_list[2] + 2 if xy_list[2] + 2 < image.shape[1] else image.shape[1]
            oil_y0 = xy_list[1] - 2 if xy_list[1] >= 2 else 0
            oil_y1 = xy_list[3] + 2 if xy_list[3] + 2 < image.shape[0] else image.shape[0]

        oil_w = oil_x1 - oil_x0
        oil_h = oil_y1 - oil_y0

        rect_x0 = oil_x0 - oil_w//2 if oil_x0 - oil_w//2 >=0 else 0
        rect_y0 = oil_y0 - oil_h//2 if oil_y0 - oil_h//2 >=0 else 0
        rect_x1 = oil_x1 + oil_w//2 if oil_x1 + oil_w//2 < image.shape[1] else image.shape[1] - 1
        rect_y1 = oil_y1 + oil_h//2 if oil_y1 + oil_h//2 < image.shape[0] else image.shape[0] - 1

        rect_w = rect_x1 - rect_x0 + 1
        rect_h = rect_y1 - rect_y0 + 1

        rect_img =  image[rect_y0:rect_y1+1, rect_x0:rect_x1+1, :]

        dx = oil_w//n
        dy = oil_h//n

        # oil_grid_xy = np.zeros((n+1,n+1,2), dtype=np.int32)
        # oil_grid_xy_new = np.zeros((n+1,n+1,2), dtype=np.int32)

        rect_grid_xy = np.zeros((n+1+2,n+1+2,2), dtype=np.int32)
        
        for r in range(n+1+2):
            for c in range(n+1+2):
                if r == 0:
                    y = 0
                elif r == n+1+2-1:
                    y = rect_h - 1
                else:
                    y = oil_y0-rect_y0+(r-1)*dy
                if c == 0:
                    x = 0
                elif c == n+1+2-1:
                    x = rect_w - 1
                else:
                    x = oil_x0-rect_x0+(c-1)*dx
                
                rect_grid_xy[r,c,:] = [x,y] 

        rect_grid_xy_new = rect_grid_xy.copy()

        for r in range(1, n+1+1):
            for c in range(1, n+1+1):
                x = rect_grid_xy[r,c,0]
                y = rect_grid_xy[r,c,1]
                # cv2.circle(rect_img, [x, y], 2, (255, 0, 0) , -1)
                
                # offset_start_x = rect_grid_xy[r-1,c-1,0] + (rect_grid_xy[r,c,0] - rect_grid_xy[r-1,c-1,0])//2
                # offset_start_y = rect_grid_xy[r-1,c-1,1] + (rect_grid_xy[r,c,1] - rect_grid_xy[r-1,c-1,1])//2
                # offset_end_x = rect_grid_xy[r,c,0] + (rect_grid_xy[r+1,c+1,0] - rect_grid_xy[r,c,0])//2
                # offset_end_y = rect_grid_xy[r,c,1] + (rect_grid_xy[r+1,c+1,1] - rect_grid_xy[r,c,1])//2

                offset_start_x = rect_grid_xy[r,c,0] - dx//2 + 1
                offset_start_y = rect_grid_xy[r,c,1] - dy//2 + 1
                offset_end_x = rect_grid_xy[r,c,0] + dx//2 - 1
                offset_end_y = rect_grid_xy[r,c,1] + dy//2 - 1

                rand_x = np.random.randint(offset_start_x, offset_end_x)
                rand_y = np.random.randint(offset_start_y, offset_end_y)
                # cv2.circle(rect_img, [rand_x, rand_y], 2, (0, 0, 255) , -1)
                rect_grid_xy_new[r,c,:] = [rand_x, rand_y]
        
        # cv2.namedWindow("original")
        # cv2.imshow("original", rect_img)
        # cv2.waitKey(0)
        # cv2.destroyWindow(f"original")

        # 遍历每个拉伸点, 进行4次仿射变换, mask过滤
        for r in range(1, n+1+2-1):
            for c in range(1, n+1+2-1):

                if mask is not None:
                    mr = r - 1
                    mc = c - 1
                    if mask[mr,mc] == 0:
                        continue

                x0 = rect_grid_xy[r,c,0]
                y0 = rect_grid_xy[r,c,1]
                xx0 = rect_grid_xy_new[r,c,0]
                yy0 = rect_grid_xy_new[r,c,1]
                
                seq_Affine = [
                    [[r, c], [r, c-1], [r-1,c-1], [r-1,c]],    #    （左上）
                    [[r, c], [r, c+1], [r-1,c+1], [r-1,c]],    #    （右上）
                    [[r, c], [r, c+1], [r+1,c+1], [r+1,c]],    #    （右下）
                    [[r, c], [r, c-1], [r+1,c-1], [r+1,c]],    #    （左下）
                ]

                mask_clips = np.zeros(rect_img.shape, dtype=np.uint8)
                img_clips = np.zeros(rect_img.shape, dtype=np.uint8)
                for i, affine in enumerate(seq_Affine):
                    x1 = rect_grid_xy[affine[1][0], affine[1][1], 0]
                    y1 = rect_grid_xy[affine[1][0], affine[1][1], 1]
                    x2 = rect_grid_xy[affine[2][0], affine[2][1], 0]
                    y2 = rect_grid_xy[affine[2][0], affine[2][1], 1]
                    x3 = rect_grid_xy[affine[3][0], affine[3][1], 0]
                    y3 = rect_grid_xy[affine[3][0], affine[3][1], 1]

                    xx1 = rect_grid_xy[affine[1][0], affine[1][1], 0]
                    yy1 = rect_grid_xy[affine[1][0], affine[1][1], 1]
                    xx2 = rect_grid_xy[affine[2][0], affine[2][1], 0]
                    yy2 = rect_grid_xy[affine[2][0], affine[2][1], 1]
                    xx3 = rect_grid_xy[affine[3][0], affine[3][1], 0]
                    yy3 = rect_grid_xy[affine[3][0], affine[3][1], 1]

                    mask_clip = np.zeros(rect_img.shape, dtype=np.uint8)
                    mask_clip = cv2.fillPoly(mask_clip, [np.int32([[xx0, yy0], [xx1, yy1],[xx2, yy2],[xx3, yy3]])], (255,255,255))
    
                    # 仿射变换
                    # src_pts = np.float32([[x0, y0], [x1, y1], [x3, y3]])
                    # dst_pts = np.float32([[xx0, yy0], [xx1, yy1], [xx3, yy3]])                    
                    # M = cv2.getAffineTransform(src_pts, dst_pts)
                    # dst_img = cv2.warpAffine(rect_img, M, (rect_img.shape[1], rect_img.shape[0]))

                    # 透视变换
                    src_pts = np.float32([[x0, y0], [x1, y1], [x2, y2], [x3, y3]])
                    dst_pts = np.float32([[xx0, yy0], [xx1, yy1], [xx2, yy2], [xx3, yy3]]) 
                    M = cv2.getPerspectiveTransform(src_pts, dst_pts, solveMethod=method)
                    dst_img = cv2.warpPerspective(rect_img, M, (rect_img.shape[1], rect_img.shape[0]))

                    dst_img = np.bitwise_and(dst_img, mask_clip)
                    
                    # cv2.destroyWindow(f"warpPerspective")
                    mask_clips = np.bitwise_or(mask_clips, mask_clip)
                    img_clips = np.bitwise_or(img_clips, dst_img)

                # cv2.namedWindow("warpAffine")
                # cv2.imshow("warpAffine", img_clips)
                # cv2.waitKey(0)

                rect_img = np.bitwise_or(np.bitwise_and(rect_img, np.bitwise_not(mask_clips)), img_clips)

                # cv2.namedWindow("img_trans")
                # cv2.imshow("img_trans", rect_img)
                # cv2.waitKey(0)
                pass

        # 贴回原图
        image[rect_y0:rect_y1+1, rect_x0:rect_x1+1, :] = rect_img

        # 新多边形的轮廓  rect_grid_xy_new
        box_y0 = 10000 
        for v in rect_grid_xy_new[1,:,1]:
            if v < box_y0:
                box_y0 = v
        box_y0 = box_y0 + rect_y0

        box_y1 = 0 
        for v in rect_grid_xy_new[n+1,:,1]:
            if v > box_y1:
                box_y1 = v
        box_y1 = box_y1 + rect_y0

        box_x0 = 10000 
        for v in rect_grid_xy_new[:,1,0]:
            if v < box_x0:
                box_x0 = v
        box_x0 = box_x0 + rect_x0

        box_x1 = 0 
        for v in rect_grid_xy_new[:,n+1,0]:
            if v > box_x1:
                box_x1 = v
        box_x1 = box_x1 + rect_x0

        print([box_x0, box_y0, box_x1, box_y1])
        if 0:
            cv2.namedWindow("img_trans")
            cv2.imshow("img_trans", image)
            cv2.waitKey(0)
            cv2.destroyWindow("img_trans")

        out_image_path = os.path.join(out_path, f"{basename}_{seq}_{index}.jpg")
        out_yolo_path = os.path.join(out_path, f"{basename}_{seq}_{index}.txt")
        print(out_image_path)
        # cv2.imwrite(out_image_path, image_gen)
        cv2.imencode(".jpg", image)[1].tofile(out_image_path)
        
        print(out_yolo_path)
        rect_2_yolo_bbox([box_x0, box_y0, box_x1, box_y1], (image.shape[1], image.shape[0]), out_yolo_path)

        if 1:
            out_image_path = os.path.join(out_path, f"{basename}_{seq}_{index}_show.jpg")
            cv2.rectangle(image, (box_x0, box_y0), (box_x1, box_y1), (0,0,255), 2)
            cv2.imencode(".jpg", image)[1].tofile(out_image_path)
        
    return 


def sample_augmentation(file_dir, num_per_img=10, out_dir="output", grid_n=2, mask=None, method=cv2.DECOMP_LU):

    file_list = os.listdir(file_dir)

    dst_dir = os.path.join(file_dir, out_dir)
    if not os.path.exists(dst_dir):
        os.makedirs(dst_dir)

    for file_name in file_list:
        file_path = os.path.join(file_dir, file_name)
        basename, ext = os.path.splitext(file_name)
        print(file_path)
        for num_gen in range(num_per_img):
            print(f"gen num {num_gen+1} ......")
            polygon_reshaping(file_path, dst_dir, seq=num_gen, n=grid_n, mask=mask, method=method)


    pass


def label_load(file_path, w, h):
    try:
        with open(file_path, "r", encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        # messagebox.showwarning("标签文件错误", "标签文件打开错误！")  
        return -1
    
    coord_list = []
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
        
        coord = []
        pos_value_error = False
        for i in range(0, len(pos_pairs), 2):
            if pos_pairs[i] >= w or pos_pairs[i+1] >= h:
                pos_value_error = True
                break
            coord.append([ pos_pairs[i], pos_pairs[i+1] ])
        
        if pos_value_error:
            print(f"标签第{index+1}行, 坐标值超过图像大小!") 
            continue

        coord_list.append(np.array(coord, dtype=np.int32))

    return coord_list



def test_img_alignment():

    arr_align = get_align_params(r"align.conf")
    batch_process_alignment(r"Z:\原油检测\00大庆现场测试\01数据\MAX_20240525", arr_align)
    pass



def spectral_angles(data, members):
    '''Calculates spectral angles with respect to given set of spectra.

    Arguments:

        `data` (:class:`numpy.ndarray` or :class:`spectral.Image`):

            An `MxNxB` image for which spectral angles will be calculated.

        `members` (:class:`numpy.ndarray`):

            `CxB` array of spectral endmembers.

    Returns:

        `MxNxC` array of spectral angles.


    Calculates the spectral angles between each vector in data and each of the
    endmembers.  The output of this function (angles) can be used to classify
    the data by minimum spectral angle by calling argmin(angles).
    '''
    assert members.shape[1] == data.shape[2], \
        'Matrix dimensions are not aligned.'

    m = np.array(members, np.float64)
    m /= np.sqrt(np.einsum('ij,ij->i', m, m))[:, np.newaxis]

    norms = np.sqrt(np.einsum('ijk,ijk->ij', data, data))
    dots = np.einsum('ijk,mk->ijm', data, m)
    dots = np.clip(dots / norms[:, :, np.newaxis], -1, 1)
    return dots



def get_color_rgb():
    color_name_list = ['red', 'lime', 'aqua', 'blue', 'yellow', 
                       'fuchsia', 'tomato', 'gold', 'green', 'deepskyblue', 'violet'
    ]
    for colorname in color_name_list:
        rgb = mcolors.to_rgb(colorname)
        rgb_255 = [int(c*255) for c in rgb]
        print(colorname, ' ',  rgb_255)
    pass


def get_binning_wave(wavelength:list, gap=10):

    if len(wavelength) == 0:
        return [],[]
    
    binning_wv_list = []
    binning_wv_index_list = []

    wv_int = round(wavelength[0])
    while wv_int<= wavelength[-1]:
        binning_wv_list.append(wv_int)
        wv_int += gap

    half = gap/2
    offset = 0
    for i, binning_wv in enumerate(binning_wv_list):
        index_left = -1
        index_right = -1
        for j in range(offset, len(wavelength)):
            wv = wavelength[j]
            if wv < binning_wv-half:
                continue
            elif wv < binning_wv+half:
                if index_left < 0:
                    index_left = j
                
                index_right = j
            else:
                offset = j
                break
            pass

        if index_left <0 or index_right<0:
            return [],[]
        
        binning_wv_index_list.append((index_left, index_right))
        pass

    return binning_wv_list, binning_wv_index_list


def get_binning_index(img_wv_list:list, binning_wv_list:list):
    if len(binning_wv_list) <= 2:
        return []
    
    gap = binning_wv_list[1] - binning_wv_list[0]
    if len(img_wv_list) < 2:
        return []
    
    binning_wv_index_list = []

    half = gap/2
    offset = 0
    for i, binning_wv in enumerate(binning_wv_list):
        index_left = -1
        index_right = -1
        for j in range(offset, len(img_wv_list)):
            wv = img_wv_list[j]
            if wv < binning_wv-half:
                continue
            elif wv < binning_wv+half:
                if index_left < 0:
                    index_left = j
                
                index_right = j
            else:
                offset = j
                break
            pass

        if index_left <0 or index_right<0:
            return []
        
        binning_wv_index_list.append((index_left, index_right))
        pass

    return  binning_wv_index_list


def read_tif(tif_path):
    '''
    读取单通道Tif文件到img
    '''
    # 可以读取单通道影像
    # 读取3通道16位tif影像时报错(PIL.UnidentifiedImageError: cannot identify image file),
    # 支持4通道8位影像
    tif = Image.open(tif_path)         
    mode = tif.mode     # 'I;16'
    if mode[0] == 'L':
        data_type =  0
    elif mode[0] == 'I':
        data_type =  12
    else:
        raise ValueError(f'Unsupported mode: {mode}')
    
    prefix = tif.ifd.prefix
    
    # 根据TIF文件格式标准，前两个字节应是字节顺序标记
    if prefix == b'II':
        byte_order = 0      #'little-endian'
    elif prefix == b'MM':
        byte_order = 1      #  'big-endian'
    else:
        raise ValueError("Not a valid TIFF file or unsupported endianness")
    
    lines = tif.height
    samples = tif.width
    
    arr = np.array(tif)    # white board shape: [H, B]
    
    return arr


def adjust_d_file_by_wb(d_file_path, wb_path):
    '''
    根据白板数据生成反射率数据文件
    '''
    img_info = ImgInfo()
    img_info.create_img_info(d_file_path)

    img = img_info.get_img_by_interleave('bip')
    hdr = copy.copy(img_info.hdr)
    hdr.interleave = 'bip'

    filename, _ = os.path.splitext(d_file_path)
    
    r_file_path = filename + "_wb.img"
    wb_img = read_tif(wb_path)
    out_img = img.astype(np.float32)/wb_img.reshape((hdr.lines, 1, -1)).astype(np.float32)
    out_img = np.clip(out_img, 0, 1)
    out_img = out_img*65535
    out_img = out_img.astype(np.uint16)    
    save_img(img, r_file_path, hdr)


    start_index = 276
    end_index = 360
    wb_img = wb_img[start_index:end_index+1, ]
    wb_img = np.mean(wb_img, axis=0)
    wb_img = wb_img.reshape((1, 1, -1))
    wb_img = np.repeat(wb_img, hdr.lines, axis=0)

    r_file_path = filename + "_wb_adj.img"
    out_img = img.astype(np.float32)/wb_img.astype(np.float32)
    out_img = np.clip(out_img, 0, 1)
    out_img = out_img*65535
    out_img = out_img.astype(np.uint16)    
    save_img(img, r_file_path, hdr)

    return


 
def check_endianness(file_path):
    # 打开文件并只读模式读取前两个字节
    with open(file_path, 'rb') as f:
        data = f.read(2)
    
    # 根据TIF文件格式标准，前两个字节应是字节顺序标记
    if data == b'II':
        return 0      #'little-endian'
    elif data == b'MM':
        return 1      #  'big-endian'
    else:
        raise ValueError("Not a valid TIFF file or unsupported endianness")


def get_tiff_info(image_path):

    xmp_dict = {}

    import tifffile
    import xml.etree.ElementTree as ET

    # 加载TIFF文件
    with tifffile.TiffFile(image_path) as tif:
        # 获取文件的所有页面（如果TIFF文件包含多个页面）
        pages = tif.pages
    
        # 遍历每个页面并打印标签信息
        for i, page in enumerate(pages):
            # print(f"Page number: {i}")
            # print("Tags:")

            for tag in page.tags.values():
                # print(f"  {tag.name}: {tag.value}")

                if tag.name == 'XMP':

                    # XMP标签的值是一个XML格式的字符串
                    xmp_xml_string = tag.value
                    
                    # 解析XML字符串
                    namespaces = {}

                    try:
                        root = ET.fromstring(xmp_xml_string)
                        
                        # 现在你可以使用ElementTree API来访问XML元素和属性
                        # 例如，打印根元素及其子元素的标签名
                        for elem in root.iter():

                            # 检查元素的'xmlns'属性
                            for key, value in elem.attrib.items():
                                if key.startswith('xmlns'):
                                    if ':' in key:
                                        # 命名空间前缀
                                        prefix = key.split(':')[1]
                                        namespaces[prefix] = value
                                    else:
                                        # 默认命名空间
                                        namespaces[''] = value

                            if '{' in elem.tag:
                                # 替换命名空间为标签名
                                elem.tag = elem.tag.split('}')[-1]
                            
                            # print(elem.tag, elem.attrib, elem.text)
                            xmp_dict[elem.tag] = elem.text
                            
                        # 如果你知道具体的XML结构，你可以更具体地访问元素和属性
                        # 例如，假设你有一个名为"dc:title"的元素，你可以这样获取它的值：
                        # title_elem = root.find('{http://purl.org/dc/elements/1.1/}title')
                        # if title_elem is not None:
                        #     print("Title:", title_elem.text)
                        #     pass
                            
                    except ET.ParseError as e:
                        print("XML解析错误:", e)


            # print()  # 打印一个空行以便区分不同页面

    return xmp_dict



def Tif2ImgBatchprocess(dir_path, wave_list=[450,550,650,720,750,800,850], index=1, count=-1, prefix=""):

    if not os.path.exists(dir_path):
        print(f"path error! {dir_path}")
        return 
    
    tif_list = []
    
    for file_path in os.listdir(dir_path):
        filename = os.path.basename(file_path)
        name, ext = os.path.splitext(filename)

        if ext != ".tif":
            continue

        tif_list.append(file_path)

    if count<0:
        count = math.ceil(len(tif_list) / 7)

    for i in range(index,count+index, 1):
        tif_set_list = []
        IrradianceExposureTime = []
        IrradianceGain = []

        for j in range(len(wave_list)):
            tif_file = f"MAX_{i:04d}_{wave_list[j]}nm_D.tif"
            if len(prefix) > 0:
                tif_file = prefix + "_" + tif_file
            tif_path = os.path.join(dir_path, tif_file)
            if not os.path.exists(tif_path):
                print(f"{tif_path}: not exist!")
                break
            tif_set_list.append(tif_path)
            tif_info_dict = get_tiff_info(tif_path)
            try:
                IrradianceExposureTime.append(tif_info_dict['IrradianceExposureTime'])
                IrradianceGain.append(tif_info_dict['IrradianceGain'])
            except Exception as e:
                print(f"{tif_path}: get tif info error!")
                break

        if len(tif_set_list) < len(wave_list):
            continue

        # output img
        one_img_list = []
        data_type = 0
        byte_order = 0
        lines = 0
        samples = 0
        for j in range(len(tif_set_list)):
            tif = Image.open(tif_set_list[j])         #可以读取单通道影像,读取3通道16位tif影像时报错(PIL.UnidentifiedImageError: cannot identify image file),支持4通道8位影像
            
            if j == 0:
                mode = tif.mode
                if mode[0] == 'L':
                    data_type =  0
                elif mode[0] == 'I':
                    data_type =  12
                else:
                    raise ValueError(f'Unsupported mode: {mode}')
                
                # byte_order = check_endianness(tif_set_list[j])

                prefix = tif.ifd.prefix

                # 根据TIF文件格式标准，前两个字节应是字节顺序标记
                if prefix == b'II':
                    byte_order = 0      #'little-endian'
                elif prefix == b'MM':
                    byte_order = 1      #  'big-endian'
                else:
                    raise ValueError("Not a valid TIFF file or unsupported endianness")
                
                lines = tif.height
                samples = tif.width
                
            arr = np.array(tif)
            one_img_list.append(arr)


        img = np.stack(one_img_list, axis=0)

        bands = len(wave_list)
        interleave = 'bsq'
        band_names = [str(i) for i in wave_list]

        kw_param = {}
        kw_param['IrradianceExposureTime'] = '{' + ','.join(i for i in IrradianceExposureTime) +'}'
        kw_param['IrradianceGain'] =  '{' + ','.join(i for i in IrradianceGain) +'}'

        hdrinfo = HDRInfo(bands,lines,samples, data_type, interleave, band_names, wave_list, byte_order, **kw_param)
       
        img_file = f"MAX_{i:04d}_Color_D.img"
        if len(prefix) > 0:
            img_file = prefix + "_" + img_file
        img_path = os.path.join(dir_path, img_file)
        save_img(img, img_path, hdrinfo)

        print(img_path)

        pass


def rename_files_in_dir(src_dir, filter=None, exclude=None):
    '''
    将原文件夹的文件加上父目录名称，进行重命名
    '''
    par_dir = os.path.basename(src_dir)
    for filename in os.listdir(src_dir):
        name, ext = os.path.splitext(filename)
        if filter :
            if isinstance(filter, str) and ext.lower() != filter:
                continue
            elif isinstance(filter, list) and ext.lower() not in filter:
                continue
        
        if exclude :
            if isinstance(exclude, str) and ext.lower() == exclude:
                continue
            elif isinstance(exclude, list) and ext.lower() in exclude:
                continue
        
        src_file_path = os.path.join(src_dir, filename)

        dst_filename = '_'.join([par_dir,filename])
        dest_file_path = os.path.join(src_dir, dst_filename)
        print(src_file_path+" => "+dest_file_path)
        shutil.move(src_file_path, dest_file_path)
        pass


def del_file_ext_in_dir(dir_path, ext='.tif'):

    for file_path in os.listdir(dir_path):
        filename = os.path.basename(file_path)
        name, ext = os.path.splitext(filename)

        if ext != ".tif":
            continue

        if os.path.exists(file_path):
            os.remove(file_path)
            print(f'{file_path} deleted!')

    return


def batch_process_oil_tif(dir_path):

    Tif2ImgBatchprocess(dir_path)

    del_file_ext_in_dir(dir_path)

    rename_files_in_dir(dir_path)


if __name__=='__main__':

    if 1:
        adjust_d_file_by_wb(r"Z:\塑料\海宝物料数据\1112_DATA\40um_900_2_0.6ms\D\PSB_D2024111218485.img",
                            r"Z:\塑料\海宝物料数据\1112_DATA\40um_900_2_0.6ms\D\W100_640_2_2.tif")

    if 0:
        read_tif(r"Z:\塑料\海宝物料数据\1112_DATA\40um_900_2_0.6ms\W100_640_2_2.tif")


    if 0:
        get_color_rgb()

    if 0:
        # 创建一个logger
        logger = logging.getLogger(__name__)  # 使用当前模块名作为logger名
        logger.setLevel(logging.DEBUG)  # 设置日志级别为DEBUG，这将记录DEBUG及以上级别的日志

        # 创建一个handler，用于写入日志文件
        fh = logging.FileHandler('algos.log')  # 创建一个文件处理器，将日志写入文件app.log
        fh.setLevel(logging.DEBUG)  # 设置文件处理器的日志级别为DEBUG

        # 定义handler的输出格式
        # formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        # fh.setFormatter(formatter)  # 文件处理器使用此格式

        # 给logger添加handler
        logger.addHandler(fh)  # 添加文件处理器

    # test_sam_distance()
    # test_rgb2hsv()
    # test_hsv_filter()

    if 0:
        test_img_alignment()

    # get_rgb_by_color_name("red")

    # 示例
    # p1, q1 = (1, 1), (10, 1)  # 第一条线段的两个点
    # p2, q2 = (1, 2), (10, 2)  # 第二条线段的两个点
    # print(do_intersect(p1, q1, p2, q2))  # 应输出 False，因为线段不相交

    # p1, q1 = (1, 1), (10, 10)  
    # p2, q2 = (1, 10), (10, 1)  
    # print(do_intersect(p1, q1, p2, q2))  # 应输出 True，因为线段相交

    # p1, q1 = (1, 10), (3, 3)  
    # p2, q2 = (1, 1), (2, 2)  
    # print(do_intersect(p1, q1, p2, q2))  # 应输出 True，因为线段相交
    
    # grid_n = 2
    # mask = np.zeros((grid_n+1, grid_n+1), dtype=np.uint8)
    # mask[0,0] = 1
    # mask[grid_n, grid_n] = 1
    # mask[0, grid_n] = 1
    # mask[grid_n, 0] = 1
    # mask[grid_n//2, grid_n//2] = 1

    # sample_augmentation(r"z:\原油检测\00大庆现场测试\temp", 
    #                   num_per_img=10, out_dir="output1", grid_n=3, mask=None, method=cv2.DECOMP_SVD)

    # oil_spectral_statis(r"Y:\taorui\oil\test_set_oil_since_513")

    # polygon_reshaping("Res/MAX_20240519_MAX_0076_Color_D.jpg")

    pass