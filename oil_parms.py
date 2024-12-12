import json
import numpy as np

class yolo_oil_param:
    def __init__(self, id) -> None:
        self.id = id
        self.spectral_id_list:list[int] = []
        self.hsv = 0
        self.confidence = 0
        self.area_ratio = 0
        self.area_pixel_count = 0


class spectral_info:
    def __init__(self, id:int, spectral:np.array, gain:float, expo_time:float, sam_threshold) -> None:
        self.id = id
        self.spectral = spectral
        self.gain = gain
        self.expo_time = expo_time
        self.sam_threshold = sam_threshold

    def get_spectral(self, use_gain=False):
        if use_gain:
            spectral = self.spectral*1024/self.gain/self.expo_time
            return np.clip(spectral, 0, 65535)
        else:
            return self.spectral
        

class oil_detector_params:
    def __init__(self) -> None:
        self.class_num = 0
        self.oil_num = 0
        
        self.amp_threshold_850 = 0
        self.amp_threshold_450 = 0
        self.paraller_num = 12                # 并行度
        self.detect_rect_min_size  = 3        # 检测区域最小尺寸
        self.detect_rect_gap  = 50            # 检测区域最大间隔
        self.rect_filter_factor_w = 1
        self.rect_filter_factor_h = 1
        self.match_algo_reletive = 1
        self.sam_match_algo = 0
        self.hsv_info = [] 
        self.yolo_enabled = 0
        self.yolo_oil_classnum = 1
        self.yolo_confidence_trust = 0.95
        self.yolo_image_preprocess_type = 1    # 0: resize  1: letterbox padding
        self.yolo_image_size = 640
        self.yolo_confidence_min = 0.5
        self.yolo_nms = 0.3
        self.yolo_sam_intersaction = 0.35
        self.sam_pixel_threshold = 100
        self.jpg_adv_img_pixel = 7
        self.use_expo_time_gain = 0
        self.base_expo_time = 3
        self.base_gain = 1024
        self.yolo_class_param:dict[int, yolo_oil_param] = {}

        self.arr_spectral = None
        self.arr_gain = None
        self.arr_expo_time = None
        self.arr_sam_thres = None

        pass


    def parse(self, json_path):
        data = ""
        try:
            with open(json_path, "r", encoding='utf-8') as f:
                data = f.read()  # 读取文件内容
        except Exception as e:
            return False, f"{json_path} open error!"
        
        parsed_data = json.loads(data)  # 将JSON字符串解析为Python数据结构
        if 'spectral_info' not in parsed_data:
            return False, "key of spectral_info NOT found!"
        
        self.amp_threshold_450 = parsed_data.get('amp_threshold_450', 0)
        self.sam_match_algo = parsed_data.get('sam_match_algo', 0)
        self.match_algo_reletive = parsed_data.get('match_algo_reletive', 1)
        self.use_expo_time_gain = parsed_data.get('use_expo_time_gain', 0)
        self.base_expo_time = parsed_data.get('base_expo_time', 0)
        self.base_gain = parsed_data.get('base_gain', 0)

        for hsv_info in parsed_data['hsv']:
            self.hsv_info.extend(hsv_info)
            break 
        
        self.yolo_enabled = parsed_data.get('yolo_enabled', 1)
        self.yolo_oil_classnum = parsed_data.get('yolo_oil_classnum', 1)
        self.yolo_image_preprocess_type = parsed_data.get('yolo_image_preprocess_type', 1)
        self.yolo_image_size = parsed_data.get('yolo_image_size', 960)
        self.yolo_confidence_min = parsed_data.get('yolo_confidence_min', 0.2)
        self.yolo_confidence_trust = parsed_data.get('yolo_confidence_trust', 0.95)
        self.yolo_nms = parsed_data.get('yolo_nms', 0.45)
        self.yolo_sam_intersaction = parsed_data.get('yolo_sam_intersaction', 0.15)
        self.sam_pixel_threshold = parsed_data.get('sam_pixel_threshold', 80)

        count = 0
        for yolo_label_info in parsed_data['yolo_label_info']:
            label = yolo_label_info['label']
            yolo_label_param = yolo_oil_param(label)
            yolo_label_param.spectral_id_list.extend(yolo_label_info['spectral_index'])
            yolo_label_param.hsv = yolo_label_info.get('hsv', 0)
            yolo_label_param.confidence = yolo_label_info.get('confidence', self.yolo_confidence_min)
            yolo_label_param.area_ratio = yolo_label_info.get('area_ratio', self.yolo_sam_intersaction)
            yolo_label_param.area_pixel_count = yolo_label_info.get('area_pixel_count', self.sam_pixel_threshold)

            self.yolo_class_param[label]= yolo_label_param

            count += 1
            pass

        self.yolo_oil_classnum = self.yolo_oil_classnum if self.yolo_oil_classnum<count else count

        
        oil_list = []
        non_oil_list = []
        oil_gain_list = []
        non_oil_gain_list = []
        oil_expo_time_list = []
        non_oil_expo_time_list = []
        oil_sam_thres = []
        non_oil_sam_thres = []

        num = 0
        for spectral_info in parsed_data['spectral_info']:
            if int(spectral_info['enabled']) > 0:
                oil_list.append(spectral_info['spectral'])
                oil_gain_list.append(spectral_info['gain'])
                oil_expo_time_list.append(spectral_info['expo_time'])
                oil_sam_thres.append(spectral_info['sam_threshold'])
                num += 1

        self.oil_num = num
        
        num = 0
        for spectral_info in parsed_data['neg_spectral_info']:
            if int(spectral_info['enabled']) > 0:
                non_oil_list.append(spectral_info['spectral'])
                non_oil_gain_list.append(spectral_info['gain'])
                non_oil_expo_time_list.append(spectral_info['expo_time'])
                non_oil_sam_thres.append(spectral_info['sam_threshold'])
                num += 1
            pass

        self.class_num = self.oil_num + num

        self.arr_spectral = np.array(oil_list+non_oil_list, dtype=np.float32)
        self.arr_gain = np.array(oil_gain_list+non_oil_gain_list, dtype=np.float32)
        self.arr_expo_time = np.array(oil_expo_time_list+non_oil_expo_time_list, dtype=np.float32)
        self.arr_sam_thres = np.array(oil_sam_thres+non_oil_sam_thres, dtype=np.float32)

        oil_num = 0
        standard_spectral_list = []
        standard_sam_thres = []
        for spectral_info in parsed_data['standard_spectral']:
            if str(spectral_info['label']).strip() == "Oil":
                for oil in spectral_info['spectral']:
                    standard_spectral_list.append(oil)
                    oil_num += 1
                for thres in spectral_info['sam_threshold']:
                    standard_sam_thres.append(thres)

            if str(spectral_info['label']).strip() == "Non_Oil":
                for oil in spectral_info['spectral']:
                    standard_spectral_list.append(oil)
                for thres in spectral_info['sam_threshold']:
                    standard_sam_thres.append(thres)

            pass

        self.standard_spectrl_arr = np.array(standard_spectral_list, dtype=np.float32)
        self.standard_sam_thres_arr = np.array(standard_sam_thres, dtype=np.float32)
        self.oil_num = oil_num
        self.class_num = self.standard_spectrl_arr.shape[0]

        return True, f"总谱线数量：{self.class_num}\n原油谱线数量：{self.oil_num}\n"
    

    def get_oil_spectral(self):

        arr_spectral = self.arr_spectral*self.base_gain/self.arr_gain/self.arr_expo_time
        arr_spectral = np.clip(arr_spectral, 0, 65535)

        return arr_spectral



if __name__ == '__main__':

    params_path = "Y:/taorui/oil/conf/params.json"

    oil_params = oil_detector_params()

    ret, info = oil_params.parse(params_path)
    if not ret: 
        print("原油配置参数读取错误", info)

    pass

