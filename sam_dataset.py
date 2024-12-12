import spectral
import json
import os
from Img_Functions import ImgInfo, HDRInfo, img_path_valid, get_closest_wave_in_spectral_list
import numpy as np
from typing import Dict, List
from algos import (sam_distance, trans_diff1, TRANSFORMS_DEF, transform_process,
                   mcolor_2_hexstr, random_color_hexstr, save_img, get_transid_by_key,
                   mcolor_2_tuple, random_color_tuple, rgb_tuple_2_hexstr, 
                   get_binning_wave, COLOR_CONF_LIST)
import cv2
import copy
from scipy.signal import savgol_filter
from datetime import datetime

class DataInfo:

    def __init__(self, class_name):
        
        self.class_index = -1            # 类别索引编号
        self.class_name = class_name     # 类别名称（key）
        self.super_class_index = -1      # 类别归属的超类索引
        self.class_color = None          # 类别颜色
        self.ori_img:np.ndarray = None   # 原始谱线数据
        self.trans_img = None    # 更新变换算法后的样本谱线数据

        self.std_spectral = None           # 类别的标准谱线，只有一条

        self.class_sample_num = 0        # 类别总样本数量
        self.file_path_list = []
        self.sam_threshold = 0.5         # 类别的距离门限

        self.latest_cluster_num = 1       # 最近一次设置的簇数量
        self.cluster_num = 1              # 最新设置的簇数量
        self.cluster_color = []           # 每个簇的颜色[cluster_num]
        self.cluster_threshold = [0.5]      # 每个簇的距离门限
        self.cluster_sample_num = []      # 每个簇的样本数量
        self.cluster_std_spectral = []    # 多簇形成的标准谱线 [cluster_num, band num]
        self.cluster_index_list = []       # 本类别中的每个簇的索引（该索引为全部标准谱线的索引，是参与距离计算的标准谱线矩阵类别大小）        
        pass



class SamDataset:

    def __init__(self):
        
        self.file_path_list = []
        self.class_info_dict:Dict[str, DataInfo] = {}
        self.class_num = 0
        self.total_sample_num = 0
        self.wavelength = []                     #数据集的原始波长列表，必须一致
        self.start_wave_length = -1
        self.end_wave_length = -1
        self.start_wave_index = 0
        self.end_wave_index = len(self.wavelength) - 1

        self.data_type = -1
        self.bands = 0
        
        self.trans_list = []
        self.trans_key = 'None'
        self.smooth = 0
        self.binning_gap = 0
        self.binning_wv_list = []                #数据集的binning波长列表
        self.binning_wv_index_list  = []

        self.all_spectral = []     # 各个类别（簇）的标准谱线列表，用于矩阵运算
        self.all_threshold = []    # 各个类别（簇）的门限列表，用于矩阵运算

        self.hdrinfo:HDRInfo = None
        
        self.samplenum_show = -1                # 用于UI显示的样本数量

        self.use_super_class = False
        self.super_class_ind = -1               # 用于超类的索引分配
        self.super_class_dict = {}              # 超类索引到类别名称的映射

        self.cluster_index_classname_dict = {}   # 簇索引到类别名称的映射
        self.cluster_index_alloc = -1           # 用于簇的索引分配
        self.class_index_alloc = -1             # 用于类的索引分配

        pass

    pass


    def clear(self):

        self.file_path_list.clear()
        self.class_info_dict.clear()
        self.class_num = 0
        self.total_sample_num = 0

        self.wavelength.clear()
        self.start_wave_length = -1
        self.end_wave_length = -1
        self.start_wave_index = 0
        self.end_wave_index = 0

        self.data_type = -1
        self.bands = 0
        self.trans_list.clear()
        self.trans_key = 'None'
        self.smooth = 0
        self.binning_gap = 0
        self.binning_wv_list.clear()
        self.binning_wv_index_list.clear()

        self.all_spectral.clear()
        self.all_threshold.clear()
        
        self.hdrinfo:HDRInfo = None
        self.samplenum_show = -1
        self.use_super_class = False
        self.super_class_ind = -1
        self.super_class_dict.clear()

        self.cluster_index_classname_dict.clear()
        self.cluster_index_alloc = -1
        self.class_index_alloc = -1

        pass


    def empty(self):
        '''
        数据集是否为空
        '''

        return len(self.wavelength) == 0
    
    
    def set_wavelength_range(self, start_wave, end_wave):

        # 在hdrinfo中查找start_wave, end_wave的最接近index
        start_index = get_closest_wave_in_spectral_list(self.wavelength, start_wave)
        end_index = get_closest_wave_in_spectral_list(self.wavelength, end_wave)
        if start_index < 0 or end_index < 0:
            pass
        
        self.start_wave_index = start_index
        self.end_wave_index = end_index
        pass


    def transform_updated(self):
        '''
        根据更新后的transform预处理过程，更新每个class的trans_img，以及标准谱线信息
        '''
        self.all_spectral.clear()
        self.cluster_index_classname_dict.clear()
        self.cluster_index_alloc = -1
        
        for label in self.class_info_dict:
            class_info = self.class_info_dict[label]
            if self.binning_gap>0:
                trans_img = np.zeros((class_info.ori_img.shape[0], len(self.binning_wv_list)), dtype=np.float32)
                for i,(l,r) in enumerate(self.binning_wv_index_list):
                    trans_img[:, i] = np.mean(class_info.ori_img[:, l:r+1], axis=1)
            else:
                trans_img = class_info.ori_img.astype(np.float32).copy()

            if self.smooth > 0:
                trans_img = transform_process('SavitzkyGolay', trans_img)

            trans_img = transform_process(self.trans_key, trans_img)

            class_info.trans_img =  trans_img[:, self.start_wave_index:self.end_wave_index+1]
            
            img_mean = np.mean(class_info.trans_img, axis=0)
            class_info.std_spectral = img_mean

            class_info.cluster_sample_num.clear()
            class_info.cluster_std_spectral.clear()
            class_info.cluster_color.clear()
            class_info.cluster_threshold.clear()
            class_info.cluster_index_list.clear()
            
            if class_info.cluster_num>1:
                transimg = class_info.trans_img.reshape((class_info.trans_img.shape[0], 1, -1))
                class_map, centers = spectral.kmeans(transimg, class_info.cluster_num)
                unique_elements, counts = np.unique(class_map, return_counts=True)
                result_cluster_num = len(unique_elements)
                for i in range(result_cluster_num):

                    self.cluster_index_alloc += 1
                    class_info.cluster_index_list.append(self.cluster_index_alloc)
                    self.cluster_index_classname_dict[self.cluster_index_alloc] = class_info.class_name

                    id = unique_elements[i]
                    cnt = counts[i]
                    class_info.cluster_sample_num.append(cnt)
                    class_info.cluster_std_spectral.append(centers[id])
                    class_info.cluster_color.append(class_info.class_color)
                    class_info.cluster_threshold.append(class_info.sam_threshold)
                    self.all_spectral.append(centers[id])
                
                class_info.cluster_num = result_cluster_num

            else:
                self.cluster_index_alloc += 1
                class_info.cluster_index_list.append(self.cluster_index_alloc)
                self.cluster_index_classname_dict[self.cluster_index_alloc] = class_info.class_name
                
                class_info.cluster_num = 1
                class_info.cluster_sample_num.append(class_info.class_sample_num)
                class_info.cluster_std_spectral.append(class_info.std_spectral)
                class_info.cluster_color.append(class_info.class_color)
                class_info.cluster_threshold.append(class_info.sam_threshold)
                
                self.all_spectral.append(class_info.std_spectral)

        return
    

    def set_class_super_index(self, class_name, super_index=-1):
        '''
        仅更新某个类别的超类编号，以及判断是否使用超类；
        整个超类的颜色统一生成是在推理之前
        '''
        if class_name in self.class_info_dict:
            datainfo = self.class_info_dict[class_name]
            datainfo.super_class_index = super_index            
            if super_index < 0:
                self.use_super_class = False

        for datainfo in self.class_info_dict.values():
            if datainfo.super_class_index < 0:
                self.use_super_class = False
                break
            pass
        else:
            self.use_super_class = True
        
        return


    def set_class_cluster_num(self, class_name_list, cluster_num=2):
        '''
        更新某个类别的簇数量的处理
        1. 聚类
        2. 更新谱线及数量
        3. 门限，颜色
        4. 全部类别谱线列表
        class_name_list : 元素已经是需要更新的class
        '''
        
        self.all_spectral.clear()
        self.cluster_index_classname_dict.clear()
        self.cluster_index_alloc = -1

        # 需要重新根据每个类来更新all_spectral
        for class_name in self.class_info_dict:
            
            datainfo = self.class_info_dict[class_name]
            
            if class_name in class_name_list:  # 簇数量发生了变化的情况
                datainfo.cluster_sample_num.clear()
                datainfo.cluster_std_spectral.clear()
                datainfo.cluster_color.clear()
                datainfo.cluster_threshold.clear()
                datainfo.cluster_index_list.clear()

                if cluster_num>1:
                    transimg = datainfo.trans_img.reshape((datainfo.trans_img.shape[0], 1, -1))
                    class_map, centers = spectral.kmeans(transimg, cluster_num)
                    unique_elements, counts = np.unique(class_map, return_counts=True)
                    result_cluster_num = len(unique_elements)
                    if result_cluster_num != cluster_num:
                        print(f"spectral.kmeans result {result_cluster_num} is different from request {cluster_num}!")

                    for i in range(result_cluster_num):
                    
                        self.cluster_index_alloc += 1
                        datainfo.cluster_index_list.append(self.cluster_index_alloc)
                        self.cluster_index_classname_dict[self.cluster_index_alloc] = datainfo.class_name

                        id = unique_elements[i]
                        cnt = counts[i]
                        datainfo.cluster_sample_num.append(cnt)
                        datainfo.cluster_std_spectral.append(centers[id])
                        datainfo.cluster_color.append(datainfo.class_color)
                        datainfo.cluster_threshold.append(datainfo.sam_threshold)

                        self.all_spectral.append(centers[id])

                    datainfo.cluster_num = result_cluster_num

                else:
                    self.cluster_index_alloc += 1
                    datainfo.cluster_index_list.append(self.cluster_index_alloc)
                    self.cluster_index_classname_dict[self.cluster_index_alloc] = datainfo.class_name

                    datainfo.cluster_num = 1
                    datainfo.cluster_sample_num.append(datainfo.class_sample_num)
                    datainfo.cluster_std_spectral.append(datainfo.std_spectral)
                    datainfo.cluster_color.append(datainfo.class_color)
                    datainfo.cluster_threshold.append(datainfo.sam_threshold)
                    
                    self.all_spectral.append(datainfo.std_spectral)

            else:  # 填充旧值
                if datainfo.cluster_num>1:
                    self.all_spectral.extend(datainfo.cluster_std_spectral)

                    for i in range(datainfo.cluster_num):
                        self.cluster_index_alloc += 1
                        datainfo.cluster_index_list.append(self.cluster_index_alloc)
                        self.cluster_index_classname_dict[self.cluster_index_alloc] = datainfo.class_name
                    pass
                else:
                    self.all_spectral.append(datainfo.std_spectral)

                    self.cluster_index_alloc += 1
                    datainfo.cluster_index_list.append(self.cluster_index_alloc)
                    self.cluster_index_classname_dict[self.cluster_index_alloc] = datainfo.class_name
                    pass

        return 


    def set_class_threshold(self, class_name, sam_thres=1.1, cluster_index=None):

        if class_name in self.class_info_dict:
            datainfo = self.class_info_dict[class_name]

            if cluster_index is None:
                datainfo.sam_threshold = sam_thres
                datainfo.cluster_threshold = [sam_thres]*datainfo.cluster_num        
            else:
                if cluster_index < datainfo.cluster_num:
                    datainfo.cluster_threshold[cluster_index] = sam_thres

        return


    def load_ds_img_file(self, img_path:str):
        '''
        读取img文件信息，加载到数据集。
        参数为img文件和hdr文件，其中img文件是数据集波形数据
        '''

        if not img_path_valid(img_path):
            return
        
        if img_path in self.file_path_list:
            return
        
        img_info = ImgInfo()
        img_info.create_img_info(img_path)
        img = img_info.img.reshape((img_info.hdr.lines, -1))
        hdrinfo = img_info.hdr

        if hdrinfo.interleave != 'bip':  # H，W，C
            return
        
        class_name = hdrinfo.fields_dict.get('class_name', None)
        if class_name is None:
            return
        
        if len(self.wavelength) == 0:  # The first dataset

            self.wavelength = hdrinfo.wavelength
            self.start_wave_index = 0
            self.end_wave_index = len(self.wavelength) - 1
            self.start_wave_length = self.wavelength[0]
            self.end_wave_length = self.wavelength[-1]
            self.data_type = hdrinfo.data_type
            self.bands = hdrinfo.bands

            self.hdrinfo = copy.copy(hdrinfo)

            pass
        
        # 比较wavelength是否一致
        if self.wavelength != hdrinfo.wavelength:  
            return
        if self.data_type != hdrinfo.data_type:  
            return
        if self.bands != hdrinfo.bands:   
            return
            
        if class_name in self.class_info_dict: 
            class_info = self.class_info_dict[class_name]
            class_info.ori_img = np.concatenate((class_info.ori_img, img), axis=0)
            class_info.file_path_list.append(img_path)
            pass
        else:
            class_information = DataInfo(class_name)
            self.class_info_dict[class_name] = class_information
            self.class_num += 1
            class_information.ori_img = img
            class_information.file_path_list.append(img_path)

            self.class_index_alloc += 1
            self.cluster_index_alloc += 1
            class_information.class_index = self.class_index_alloc
            class_information.cluster_index_list.append(self.cluster_index_alloc)
            self.cluster_index_classname_dict[self.cluster_index_alloc] = class_information.class_name
            # Class Color
            color_index = len(self.class_info_dict) - 1

            if color_index < len(COLOR_CONF_LIST):
                class_information.class_color = mcolor_2_tuple(COLOR_CONF_LIST[color_index])
            else:
                class_information.class_color = random_color_tuple()
           
            self.class_info_dict[class_name].cluster_color.append(class_information.class_color)

        self.class_info_dict[class_name].class_sample_num = self.class_info_dict[class_name].ori_img.shape[0]

        self.class_info_dict[class_name].cluster_sample_num.clear()
        self.class_info_dict[class_name].cluster_sample_num.append(self.class_info_dict[class_name].ori_img.shape[0])

        self.total_sample_num += img.shape[0]
        pass


    def load_dataset_in_dir(self, dataset_dir:str):
        '''
        兼容官方的加载数据集方法(img文件+hdr文件，其中img文件是经过手动标注或其他方法得到的样本)
        注意：数据集文件已经和原始img数据文件没有关系了
        '''

        if not os.path.exists(dataset_dir):
            return
        
        file_path_list = []   
        
        for cur_dir, sub_dir, cur_dir_files in os.walk(dataset_dir):
            for filename in cur_dir_files:
                file_path = os.path.join(cur_dir, filename)
                if not ImgInfo.img_path_valid(file_path):
                    continue
                file_path_list.append(file_path)

        
        for filepath in file_path_list:
            self.load_ds_img_file(filepath)

        pass


    def create_dataset_from_json_labels(self, roi_path_list, hdr_info:HDRInfo):
        '''
        roi_path_list: img,hdr,roi
        在label文件的文件，读取label信息, 根据roi从img文件中提取样本
        保存为标签名相关的img和hdr文件
        '''

        self.class_info_dict.clear()
        for img_path, hdr_path, json_path in roi_path_list:

            imginfo = ImgInfo()
            imginfo.create_img_info(img_path)
            
            try:
                with open(json_path, "r", encoding='utf-8') as f:
                    data = f.read()  # 读取文件内容
                    parsed_data = json.loads(data)  
                    shapes = parsed_data.get('shapes', [])
                    if len(shapes) == 0:
                        print(f"{json_path}. no shapes in json file!")
                        return 
                    
                    for shape in shapes:
                        label = shape.get('label', '')
                        shape_type = shape.get('shape_type', '')
                        points = shape.get('points', [])
                        if label == '' or shape_type == '' or len(points) == 0:
                            continue
                        
                        pts = np.array(points, np.int32)
                        pts = pts.reshape((-1,1,2))   # fillPoly期望的是一个形状为(-1, 1, 2)的数组
                        mask = np.zeros((imginfo.hdr.lines, imginfo.hdr.samples), np.uint8)
                        cv2.fillPoly(mask, [pts], color=255)
                        roi_img = imginfo.get_img_by_roi_mask(mask)

                        if label in self.class_info_dict:
                            self.class_info_dict[label].img = np.concatenate((roi_img, self.class_info_dict[label].img), axis=0)
                            pass
                        else:
                            self.bands = hdr_info.bands
                            self.wavelength = hdr_info.wavelength
                            self.start_wave_index = 0
                            self.start_wave_length = hdr_info.wavelength[0]
                            self.end_wave_index = hdr_info.bands - 1
                            self.end_wave_length = hdr_info.wavelength[self.end_wave_index]
                            self.data_type = hdr_info.data_type
                            self.class_info_dict[label].class_sample_num = roi_img.shape[0]
                            self.class_info_dict[label].img = roi_img
                            pass

            except Exception as e:
                print(f"{json_path}. read json file error!")
                pass 
  

    


    def gen_wave_index(self, wv_list):
        '''
        计算标准谱线波段在预测img波段列表中的索引号
        wv_list: 数据集或者预测img的波段列表
        '''

        pass



    def save_model_to_file(self, model_dir):
        '''
        根据当前模型数据和参数，生成可以用于推理的model, 保存到文件
        '''

        hdr = copy.copy(self.hdrinfo)
        hdr.data_type = 4
        hdr.interleave = 'bip'

        hdr.fields_dict.clear()

        hdr.bands = self.end_wave_index - self.start_wave_index + 1
        if self.binning_gap>0:
            
            str_band_names = [str(wv) for wv in self.binning_wv_list[self.start_wave_index:self.end_wave_index+1]]
            hdr.set_band_names(str_band_names)
            str_wv_length = self.binning_wv_list[self.start_wave_index:self.end_wave_index+1]
            hdr.set_wave_length(str_wv_length)
            hdr.set_user_defined_param('band_binning_gap', f'{self.binning_gap}')
            all_wv_str = ','.join([str(wv) for wv in self.binning_wv_list])
            hdr.set_user_defined_param('all_wave_length', all_wv_str)
            hdr.set_user_defined_param('binning_wave_length', all_wv_str)

        else:

            str_band_names = [str(wv) for wv in self.wavelength[self.start_wave_index:self.end_wave_index+1]]
            hdr.set_band_names(str_band_names)
            str_wv_length = self.wavelength[self.start_wave_index:self.end_wave_index+1]
            hdr.set_wave_length(str_wv_length)
            hdr.set_user_defined_param('band_binning_gap', '0')
            hdr.set_user_defined_param('all_wave_length', '')
            hdr.set_user_defined_param('binning_wave_length', '')
        
        str_trans_seq = ""
        if self.smooth:
            str_trans_seq = str_trans_seq + "2,"

        trans_id = get_transid_by_key(self.trans_key)
        str_trans_seq = f"{str_trans_seq}{trans_id}"
        hdr.set_user_defined_param('transform_sequence', str_trans_seq)
        
        now = datetime.now()
        formatted_time = now.strftime('%y%m%d-%H%M%S')
        hdr.set_user_defined_param('time_index', formatted_time)
        hdr.set_user_defined_param('sg_window_size', '3')
        hdr.set_user_defined_param('sg_polynomial_order', '2')
        hdr.set_user_defined_param('diff1_enhanced_factor', '10')

        # self.transform_updated()

        for label in self.class_info_dict:

            class_info = self.class_info_dict[label]
            
            if class_info.cluster_num > 1:
                hdr.lines = class_info.cluster_num
                std_spectral = np.array(class_info.cluster_std_spectral,dtype=np.float32)
                r , c = std_spectral.shape
                std_spectral = std_spectral.reshape((r, 1, c))
            else:
                hdr.lines = 1
                std_spectral = np.array(class_info.std_spectral,dtype=np.float32)
                std_spectral = std_spectral.reshape((1, 1, hdr.bands))

            hdr.samples = 1
            hdr.set_user_defined_param('class_name', class_info.class_name)
            hdr.set_user_defined_param('threshold', class_info.sam_threshold)
            hdr.set_user_defined_param('super_class_index', class_info.super_class_index) 

            save_path = os.path.join(model_dir, f"{class_info.class_name}_{formatted_time}.img")
            save_img(std_spectral, save_path, hdr)
            pass
        pass


    def set_binning_wave(self, gap=0):

        self.binning_gap = gap
        if gap <= 0:
            self.binning_wv_list.clear()
            self.binning_wv_index_list.clear()
            self.start_wave_length = self.wavelength[0]
            self.end_wave_length = self.wavelength[-1]
            self.start_wave_index = 0
            self.end_wave_index = len(self.wavelength) - 1
            return
        
        self.binning_wv_list, self.binning_wv_index_list = get_binning_wave(self.wavelength, gap)

        self.start_wave_length = self.binning_wv_list[0]
        self.end_wave_length = self.binning_wv_list[-1]
        self.start_wave_index = 0
        self.end_wave_index = len(self.binning_wv_list) - 1

        pass


    def set_sg_smooth(self, enabled=False):

        if not enabled:
            self.smooth = 0

        else:
            self.smooth = 1

        pass

    
    def get_std_spectral_matrix(self, use_class=True):
        '''
        返回每个类的标准谱线形成的计算矩阵[all class num, band num]
        或者每个类的簇标准谱线形成的计算矩阵[all cluster num,  band num]
        '''
        spectral_list = []
        for classname, datainfo in self.class_info_dict.items():
            if use_class:
                spectral_list.append(datainfo.std_spectral)
            else:
                if datainfo.cluster_num>1:
                    spectral_list.extend(datainfo.cluster_std_spectral)
                else:
                    spectral_list.append(datainfo.std_spectral)

        
        arr_all_spectral = np.vstack(spectral_list, dtype=np.float32)
        return arr_all_spectral


if __name__ == '__main__':

    sam = SamDataset()

    model_dir = "D:/00 Work/塑料/1011/sam_model"

    sam.load_model_in_dir(model_dir)
    

    test_file_list = [
        "D:/00 Work/塑料/1011/R124911172813.img",

    ]

    for test_file in test_file_list:

        sam.predict_img(test_file)

        pass

    pass