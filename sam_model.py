
import os
from Img_Functions import ImgInfo, img_path_valid, get_closest_wave_in_spectral_list
import numpy as np
from typing import Dict, List
from algos import (sam_distance, trans_diff1, get_transkey_by_id, transform_process,
                   mcolor_2_hexstr, random_color_hexstr, get_binning_index,
                   mcolor_2_tuple, random_color_tuple, rgb_tuple_2_hexstr,
                   COLOR_CONF_LIST)

from sam_dataset import SamDataset, DataInfo


class ClassInfo:

    def __init__(self, class_name):
        self.class_name = class_name
        self.sam_threshold = 1.
        self.super_class_index = -1
        self.cluster_num = 1
        self.spectral = None    # 特征波段值

        self.enabled = 1

        self.cluster_index_list = []   # 类别所包含的簇序号，长度等于cluster_num
        self.class_color = None              # 类别的颜色
        
        self.repeat_index = 1
        pass



class SamModel:

    def __init__(self):
        
        self.model_path_list = []
        self.class_info_dict:Dict[str, ClassInfo] = {}
        
        self.wavelength:List[float] = []  # 特征波段的波长列表
        self.data_type = -1
        self.bands = 0
        self.trans_list = []
        self.all_spectral = None   # [簇数量，1，特征波段数量]
        self.all_threshold = []   # 各个类别簇的门限值，用于矩阵运算，[簇数量]

        self.cluster_class_name_list = []  # 各个类别簇所对应的类别名称列表，[簇数量]
        self.cluster_color_list = []       # 各个类别簇所对应的类别颜色列表，[簇数量]

        self.use_super_class_index = True    # 根据各个类别的superclass的配置判断是否启用
        self.super_class_index_ind = -1      # superclass_index序号起点
        self.super_class_color_dict = {}     # index:color 字典

        self.trans_key = 'None'
        self.smooth = 0
        self.binning = 0
        self.binning_wv_index = []

        self.amp_thres = 0.07

        self.predict_img_height = 0       # 推理图像的高度，推理前初始化相关矩阵的大小

        # Cache process params
        self.cache_col_index = 0    # col index
        self.cache_cols = 3   # Cache Size
        self.cache_pixs = 4   # pix number threshold
        self.cache_value = None
        self.cache_value_op = None
        pass

    pass


    def clear(self):

        self.model_path_list.clear()
        self.class_info_dict.clear()

        self.wavelength.clear()
        self.data_type = -1
        self.bands = 0
        self.trans_list.clear()

        self.all_spectral = None
        self.all_threshold.clear()
        
        self.use_super_class_index = True
        self.super_class_index_ind = -1
        self.super_class_color_dict.clear()

        self.cluster_class_name_list.clear()
        self.cluster_color_list.clear()

        self.smooth = 0
        self.binning = 0
        self.binning_wv_index.clear()
        self.trans_key = 'None'
        
        pass


    def empty(self):

        return self.all_spectral is None
    

    def set_params(self, **kw):
        if kw:
            self.amp_thres = kw.get('amp_thres', -1)
            pass

        pass


    def init_cache_cols(self, height):

        self.predict_img_height = height
        if self.cache_cols > 0:
            self.cache_value = np.zeros((self.predict_img_height, self.cache_cols), dtype=np.uint8)
            self.cache_value_op = np.zeros((self.predict_img_height, self.cache_cols), dtype=np.uint8)
            self.cache_col_index = 0    # col index
        else:
            self.cache_value = None
            self.cache_value_op = None
        return


    def load_model_file(self, img_path:str):
        '''
        加载单个（类别）模型文件
        '''

        if not img_path_valid(img_path):
            return
        
        if img_path in self.model_path_list:
            return
        
        img_info = ImgInfo()
        img_info.create_img_info(img_path)
        img = img_info.img
        hdrinfo = img_info.hdr

        if hdrinfo.interleave != 'bip':  # H，W，C
            return
        
        class_name = hdrinfo.fields_dict.get('class_name', None)
        if class_name is None:
            return
        
        trans_list = []
        transform_sequence = hdrinfo.fields_dict.get('transform_sequence', None)
        if transform_sequence is not None:
            try:
                trans_list = [int(trans) for trans in transform_sequence.split(',')]
            except Exception as e:
                print("transform_sequence error!", e)

        binning_gap = hdrinfo.fields_dict.get('band_binning_gap', '0')
        try:
            binning_gap = int(binning_gap)
        except Exception as e:
            print("band_binning_gap error!", e)
            binning_gap = 0
        
        self.binning = binning_gap

        if len(self.wavelength) == 0:  # The first model

            self.wavelength = hdrinfo.wavelength
            self.data_type = hdrinfo.data_type
            self.trans_list = trans_list
            self.bands = hdrinfo.bands

            pass
        
        # 比较wavelength是否一致
        if self.wavelength != hdrinfo.wavelength:   # to do...
            return
        if self.trans_list != trans_list:   # to do...
            return
        
        if self.data_type != hdrinfo.data_type:   # to do...
            return
        
        if self.bands != hdrinfo.bands:   # to do...
            return
        

        if len(trans_list)>0:
            for id in trans_list:
                trans_key = get_transkey_by_id(id)
                if trans_key in ['Diff1', 'Diff2']:
                    self.trans_key = trans_key
                if trans_key in ['SavitzkyGolay']:
                    self.smooth = 1
            pass

        h,w,c = img.shape
        img = img.reshape((h,c))
        
        if self.all_spectral is None:
            self.all_spectral = img.copy()
        else:
            if self.all_spectral.shape[1] != img.shape[1]:
                return
            # concat img
            self.all_spectral = np.concatenate([self.all_spectral, img], axis=0)

        super_class_index = hdrinfo.fields_dict.get('super_class_index', -1)
        if super_class_index != -1:
            try:
                super_class_index = int(super_class_index)
            except Exception as e:
                print("super_class_index error!", e)
                self.use_super_class_index = False
        else:
            self.use_super_class_index = False

        sam_threshold = hdrinfo.fields_dict.get('threshold', 1)
            
        if class_name in self.class_info_dict:  # 同样类名, 则视为配置了superclass的类
            class_info = self.class_info_dict[class_name]
            super_class_index = class_info.super_class_index
            class_name = class_name + "_rep_" + str(class_info.repeat_index)
            class_info.repeat_index += 1
            pass

        class_information = ClassInfo(class_name)
        self.class_info_dict[class_name] = class_information
        
        class_information.spectral = img.copy()
        class_information.sam_threshold = float(sam_threshold)
        class_information.super_class_index = int(super_class_index)

        # Class Color
        color_index = len(self.class_info_dict) - 1
        if color_index < len(COLOR_CONF_LIST):
            class_information.class_color = mcolor_2_tuple(COLOR_CONF_LIST[color_index])
        else:
            class_information.class_color = random_color_tuple()

        # Process Cluster Infomation        
        class_information.cluster_num = hdrinfo.lines
        for i in range(hdrinfo.lines):
            self.cluster_class_name_list.append(class_name)

            class_cluster_index_ind = len(self.cluster_class_name_list) - 1
            class_information.cluster_index_list.append(class_cluster_index_ind)

            self.all_threshold.append(class_information.sam_threshold)

            # 簇颜色设置
            self.cluster_color_list.append(class_information.class_color)
            pass

        # 设置超类颜色
        if self.use_super_class_index:
            if super_class_index in self.super_class_color_dict:
                pass
            else:
                self.super_class_index_ind += 1
                if self.super_class_index_ind < len(COLOR_CONF_LIST):
                    self.super_class_color_dict[super_class_index] = mcolor_2_tuple(COLOR_CONF_LIST[self.super_class_index_ind])
                else:
                    self.super_class_color_dict[super_class_index] = random_color_tuple()


        # 保存模型文件路径信息
        self.model_path_list.append(img_path)

        pass


    def load_model_in_dir(self, model_dir:str):

        if not os.path.exists(model_dir):
            return
        
        for file_name in os.listdir(model_dir):
            file_path = os.path.join(model_dir, file_name)
            self.load_model_file(file_path)
        
        pass


    def gen_wave_index(self, img_wv_list):
        '''
        计算标准谱线波段在预测img波段列表中的索引号
        wv_list: 数据集或者预测img的波段列表
        '''
        wv_index = []
        start_i = 0

        for std_wv in self.wavelength:
            found = False
            for i  in  range(start_i, len(img_wv_list)):
                if abs(std_wv-img_wv_list[i]) < 0.5:
                    found = True
                    wv_index.append(i)
                    start_i = i+1
                    break

            if not found:
                return []

        return wv_index


    def predict_img(self, img_path):

        if not img_path_valid(img_path):
            return None
        
        img_info = ImgInfo()
        img_info.create_img_info(img_path)
        
        img = img_info.get_img()

        input_img = ImgInfo.img_transpose_by_interleave(img, img_info.hdr.interleave, 'bip')
        input_img = input_img.astype(np.float32)
        input_img = self.process_img_wave_3d(input_img, img_info.hdr.wavelength)

        h, w, c = input_img.shape
        self.init_cache_cols(h)

        result_img = None
        for i in range(w):
            input_line = input_img[:, i, :].reshape((h, c))
            result = self.predict_2d(input_line)

            if result_img is None:
                result_img = result
            else:
                result_img = np.concatenate([result_img, result], axis = 1)

        return result_img
    

    def predict_2d(self, input_img:np.ndarray):
        '''
        input_img:  [H, B]
        '''
        img_mean = np.mean(input_img, axis=1)   # (H, )

        input_line = input_img
        if self.smooth > 0:
            input_line = transform_process('SavitzkyGolay', input_line)

        input_line = transform_process(self.trans_key, input_line)

        # class_num, _, feature_num = self.all_spectral.shape
        # std_spectral = self.all_spectral.reshape((class_num, feature_num))
        dist = sam_distance(input_line, self.all_spectral)   # [H, B]

        threshold_arr = np.array(self.all_threshold, dtype=np.float32)
        delta_arr = dist - threshold_arr
        dist[delta_arr<0] = -100

        dist_max_index = np.argmax(dist, axis=1)  # (H,)
        dist_max = np.max(dist, axis=1)           # (H,)

        # 背景光强值过滤
        if self.amp_thres>0:
            dist_max[img_mean<65535*self.amp_thres] = -100
            pass

        img_result = np.zeros((dist.shape[0], 1, 3), np.uint8)
        value_result = [255]*dist.shape[0]

        for i in range(dist.shape[0]):
            if dist_max[i]>=0:
                idx = dist_max_index[i]
                img_result[i,0,0] = self.cluster_color_list[idx][0]
                img_result[i,0,1] = self.cluster_color_list[idx][1]
                img_result[i,0,2] = self.cluster_color_list[idx][2]
                
                value_result[i] = idx

        # Cache Processing
        if self.cache_cols > 0:   # Enabled

            col_cache_i = self.cache_col_index % self.cache_cols
            self.cache_value[:, col_cache_i] = np.array(value_result).copy()
            self.cache_col_index += 1

            value_result = [255]*dist.shape[0]
            img_result.fill(0)

            if self.cache_col_index < self.cache_cols: # 不足三帧
                return
            
            # 取cache的次序： 
            # col_cache_i==0:  1,2 ; 0
            # col_cache_i==1:  2 ; 0,1
            # col_cache_i==2:  0,1,2
            if col_cache_i != self.cache_cols-1:
                self.cache_value_op[:, 0:self.cache_cols-col_cache_i-1] = self.cache_value[:, col_cache_i+1:self.cache_cols]
            self.cache_value_op[:, self.cache_cols-col_cache_i-1:self.cache_cols] = self.cache_value[:, 0:col_cache_i+1]
            
            
                
            for r_i in range(1, input_img.shape[0]-1):
                value = self.cache_value_op[r_i, 1]
                if value == 255:
                    continue
                
                n = 0

                if self.cache_value_op[r_i-1, 0] == value:
                    n += 1
                if self.cache_value_op[r_i-1, 1] == value:
                    n += 1
                if self.cache_value_op[r_i-1, 2] == value:
                    n += 1
                if self.cache_value_op[r_i, 0] == value:
                    n += 1    
                if self.cache_value_op[r_i, 2] == value:
                    n += 1
                if self.cache_value_op[r_i+1, 0] == value:
                    n += 1
                if self.cache_value_op[r_i+1, 1] == value:
                    n += 1
                if self.cache_value_op[r_i+1, 2] == value:
                    n += 1  

                if n>= self.cache_pixs:
                    img_result[r_i,0,0] = self.cluster_color_list[value][0]
                    img_result[r_i,0,1] = self.cluster_color_list[value][1]
                    img_result[r_i,0,2] = self.cluster_color_list[value][2]

        return img_result


    def predict_init(self, class_enabled_status:Dict[str, ClassInfo]={}, use_super_class=True):
        '''
        始终取界面当前设置值来更新距离比较门限和超类颜色设置
        注意：本函数不会改变原有模型各个类别的实例信息。
        距离门限即成员变量all_threshold，它的原始值可以通过原模型各个类型的实例信息来恢复
        '''
        self.use_super_class_index = True
        self.super_class_index_ind = -1
        self.super_class_color_dict.clear()
        classname_superclass_index = {}

        for classname in self.class_info_dict:
            model_class_info = self.class_info_dict[classname]
            
            ui_classinfo = class_enabled_status.get(classname, None)
            if ui_classinfo is None:   # UI没有带入该类别
                if model_class_info.super_class_index < 0:
                    self.use_super_class_index = False
                else:
                    classname_superclass_index[classname] = model_class_info.super_class_index

                    if model_class_info.super_class_index in self.super_class_color_dict:
                        pass
                    else:
                        self.super_class_index_ind += 1
                        if self.super_class_index_ind < len(COLOR_CONF_LIST):
                            self.super_class_color_dict[model_class_info.super_class_index] = mcolor_2_tuple(COLOR_CONF_LIST[self.super_class_index_ind])
                        else:
                            self.super_class_color_dict[model_class_info.super_class_index] = random_color_tuple()
                
                
                continue  # UI没有带入该类别，其他参数不用更新

            # 查找模型的ClassInfo实例
            ui_superclass_index = ui_classinfo.super_class_index
            ui_thres = ui_classinfo.sam_threshold
            ui_enable = ui_classinfo.enabled
            
            if ui_superclass_index < 0:
                self.use_super_class_index = False
            else:
                classname_superclass_index[classname] = ui_superclass_index
                if ui_superclass_index in self.super_class_color_dict:
                    pass
                else:
                    self.super_class_index_ind += 1
                    if self.super_class_index_ind < len(COLOR_CONF_LIST):
                        self.super_class_color_dict[ui_superclass_index] = mcolor_2_tuple(COLOR_CONF_LIST[self.super_class_index_ind])
                    else:
                        self.super_class_color_dict[ui_superclass_index] = random_color_tuple()
                
            # 获取类别簇的index
            for cluster_index in model_class_info.cluster_index_list:
                if ui_enable:
                    self.all_threshold[cluster_index] = ui_thres
                else:
                    self.all_threshold[cluster_index] = 10

                pass
            

        # 根据超类设置簇颜色
        if use_super_class and self.use_super_class_index:
            for i, name in enumerate(self.cluster_class_name_list):
                super_class_idx = classname_superclass_index[name]

                color = self.super_class_color_dict[super_class_idx]
                self.cluster_color_list[i] = color

                pass

        # 获取

        pass
        

    def create_model_from_dataset(self, dataset:SamDataset):
        '''
        根据数据集的信息，对sam_model对象的各个信息进行填充
        self.wavelength: 标准谱线
        self.smooth
        self.trans_key
        class_num, _, feature_num = self.all_spectral.shape
        self.all_threshold
        self.amp_thres>0:
        self.cluster_color_list[idx][0]
        '''
        
        # dataset.transform_updated()
        #CLASS*B
        self.all_spectral = dataset.get_std_spectral_matrix(use_class=False)

        self.smooth = dataset.smooth
        self.binning = dataset.binning_gap
        if self.binning > 0:
            self.wavelength = dataset.binning_wv_list[dataset.start_wave_index:dataset.end_wave_index+1]
        else:
            self.wavelength = dataset.wavelength[dataset.start_wave_index:dataset.end_wave_index+1]
        
        self.bands = dataset.end_wave_index - dataset.start_wave_index + 1
        self.data_type = dataset.data_type
        self.trans_key = dataset.trans_key

        for classname, datainfo in dataset.class_info_dict.items():
            classinfo = ClassInfo(classname)
            self.class_info_dict[classname] = classinfo
            
            classinfo.super_class_index = datainfo.super_class_index
            classinfo.cluster_num = datainfo.cluster_num
            classinfo.spectral = datainfo.std_spectral
            classinfo.enabled = 1
            classinfo.class_color = datainfo.class_color

            for i in range(datainfo.cluster_num):
                self.cluster_class_name_list.append(classname)
                self.cluster_color_list.append(datainfo.class_color)
                self.all_threshold.append(datainfo.cluster_threshold[i])

        if dataset.use_super_class:
            
            self.use_super_class_index = True
            self.super_class_index_ind = -1
            self.super_class_color_dict.clear()
            classname_superclass_index = {}

            for classname in self.class_info_dict:
                model_class_info = self.class_info_dict[classname]
            
                classname_superclass_index[classname] = model_class_info.super_class_index

                if model_class_info.super_class_index in self.super_class_color_dict:
                    pass
                else:
                    self.super_class_index_ind += 1
                    if self.super_class_index_ind < len(COLOR_CONF_LIST):
                        self.super_class_color_dict[model_class_info.super_class_index] = mcolor_2_tuple(COLOR_CONF_LIST[self.super_class_index_ind])
                    else:
                        self.super_class_color_dict[model_class_info.super_class_index] = random_color_tuple()
            
                pass
                  
            for i, name in enumerate(self.cluster_class_name_list):
                super_class_idx = classname_superclass_index[name]

                color = self.super_class_color_dict[super_class_idx]
                self.cluster_color_list[i] = color

                pass

        pass


    def process_img_wave(self, img:np.ndarray, img_wv_list):
        '''
        对需要推理的img[H,B], 进行wave length匹配和binning处理，使之和标准谱线wave list一致
        '''
        if self.binning>0:
            self.binning_wv_index = get_binning_index(img_wv_list, self.wavelength)
            trans_img = np.zeros((img.shape[0], len(self.binning_wv_index)), dtype=np.float32)
            for i,(l,r) in enumerate(self.binning_wv_index):
                trans_img[:, i] = np.mean(img[:, l:r+1], axis=1)
            pass
            return trans_img
        else:
            filter_wv_index = []
            for wv in img_wv_list:
                index, _ = get_closest_wave_in_spectral_list(self.wavelength, wv)
                if index < 0:
                    return None
                
                filter_wv_index.append(index)

            return img[:, filter_wv_index].copy()
        
    
    def process_img_wave_3d(self, img:np.ndarray, img_wv_list):
        '''
        对需要推理的img[H,W,B], 进行wave length匹配和binning处理，使之和标准谱线wave list一致
        '''
        if self.binning>0:
            self.binning_wv_index = get_binning_index(img_wv_list, self.wavelength)
            trans_img = np.zeros((img.shape[0], img.shape[1], len(self.binning_wv_index)), dtype=np.float32)
            for i,(l,r) in enumerate(self.binning_wv_index):
                trans_img[:, :, i] = np.mean(img[:, :, l:r+1], axis=2)
            
            return trans_img
        else:
            filter_wv_index = []
            for wv in img_wv_list:
                index, _ = get_closest_wave_in_spectral_list(self.wavelength, wv)
                if index < 0:
                    return None
                
                filter_wv_index.append(index)

            return img[:,:, filter_wv_index].copy()


if __name__ == '__main__':

    sam = SamModel()

    model_dir = "D:/00 Work/塑料/1011/sam_model"

    sam.load_model_in_dir(model_dir)
    

    test_file_list = [
        "D:/00 Work/塑料/1011/R124911172813.img",

    ]

    for test_file in test_file_list:

        sam.predict_img(test_file)

        pass

    pass