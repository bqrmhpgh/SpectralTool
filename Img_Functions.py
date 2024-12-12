import numpy as np
import os
from typing import List, Dict, Any, Union

class Img_Data_type:
    '''
    The type of data representation:
    - 1 = Byte: 8-bit unsigned integer
    - 2 = Integer: 16-bit signed integer
    - 3 = Long: 32-bit signed integer
    - 4 = Floating-point: 32-bit single-precision
    - 5 = Double-precision: 64-bit double-precision floating-point
    - 6 = Complex: Real-imaginary pair of single-precision floating-point
    - 9 = Double-precision complex: Real-imaginary pair of double precision floating-point
    - 12 = Unsigned integer: 16-bit
    - 13 = Unsigned long integer: 32-bit
    - 14 = 64-bit long integer (signed)
    - 15 = 64-bit unsigned long integer (unsigned)
    '''
    type_uint8 = 1
    type_int16 = 2
    type_int32 = 3
    type_float32 = 4
    type_float64 = 5
    type_float32_complex = 6
    type_float64_complex = 9
    type_uint16 = 12
    type_uint32 = 13
    type_int64 = 14
    type_uint64 = 15

    pass


class Img_Byte_Order:

    Inter_LSF = 0
    IEEE_MSF  = 1
    pass


class HDRInfo:

    def __init__(self, bands:int = 0, lines:int = 0,samples:int = 0, data_type:int = -1,
                 interleave:str = '', band_names:list[str] = [], wave_length:list = [], 
                 byte_order:int = -1,
                 **kw) -> None:
        '''
        ENVI Header 必选字段：
        bands:  The number of bands per image file.
        byte order:  The order of the bytes in integer, long integer, 64-bit integer, unsigned 64-bit integer, 
                     floating point, double precision, and complex data types. Use one of the following:
                     - Byte order=0 (Host (Intel) in the Header Info dialog) is least significant byte first (LSF) 
                        data (DEC and MS-DOS systems).
                     - Byte order=1 (Network (IEEE) in the Header Info dialog) is most significant byte first (MSF) 
                        data (all other platforms).
        data type:  The type of data representation:
                    - 1 = Byte: 8-bit unsigned integer
                    - 2 = Integer: 16-bit signed integer
                    - 3 = Long: 32-bit signed integer
                    - 4 = Floating-point: 32-bit single-precision
                    - 5 = Double-precision: 64-bit double-precision floating-point
                    - 6 = Complex: Real-imaginary pair of single-precision floating-point
                    - 9 = Double-precision complex: Real-imaginary pair of double precision floating-point
                    - 12 = Unsigned integer: 16-bit
                    - 13 = Unsigned long integer: 32-bit
                    - 14 = 64-bit long integer (signed)
                    - 15 = 64-bit unsigned long integer (unsigned)
        file type:
        header offset: The number of bytes of embedded header information present in the file. 
                       ENVI skips these bytes when reading the file. The default value is 0 bytes.
        interleave: BSQ, BIL, or BIP.
                    - Band Sequential: BSQ format is the simplest format, where each line of the data is 
                      followed immediately by the next line in the same spectral band. 
                      This format is optimal for spatial (x,y) access of any part of a single spectral band. [CHW]
                    - Band-interleaved-by-pixel: BIP format stores the first pixel for all bands in sequential order, 
                      followed by the second pixel for all bands, followed by the third pixel for all bands, and so forth, 
                      interleaved up to the number of pixels. 
                      This format provides optimum performance for spectral (z) access of the image data.  [HWC]
                    - Band-interleaved-by-line: BIL format stores the first line of the first band, 
                      followed by the first line of the second band, followed by the first line of the third band, 
                      interleaved up to the number of bands. Subsequent lines for each band are interleaved in similar fashion. 
                      This format provides a compromise in performance between spatial and spectral processing and 
                      is the recommended file format for most ENVI processing tasks. [HCW]
        lines: The number of lines per image for each band.
        samples: The number of samples (pixels) per image line for each band.
        ------------------------------------------------------------------------------------
        You can add comments to the file by inserting a line with a semicolon as the first character. 
        ENVI ignores these lines when parsing the header file.

        '''
        
        self.samples = samples
        self.lines   = lines
        self.bands   = bands
        self.data_type = data_type
        self.interleave = interleave
        self.byte_order = byte_order

        self.band_names = band_names
        self.str_band_names = ",".join(name for name in self.band_names)
        self.str_band_names = "band names = {" + self.str_band_names + "}"

        if len(wave_length) > 0:
            if isinstance (wave_length[0], str):
                self.wavelength = [float(wave) for wave in wave_length]
                self.str_wavelength = ",".join(wave for wave in wave_length)
                self.str_wavelength = "wavelength = {" + self.str_wavelength + "}"            
            elif isinstance (wave_length[0], float):
                self.wavelength = wave_length
                self.str_wavelength = ",".join(str(wave) for wave in wave_length)
                self.str_wavelength = "wavelength = {" + self.str_wavelength + "}"
            elif isinstance (wave_length[0], int):
                self.wavelength = wave_length
                self.str_wavelength = ",".join(str(wave) for wave in wave_length)
                self.str_wavelength = "wavelength = {" + self.str_wavelength + "}"
            else:
                self.wavelength = wave_length
                self.str_wavelength = ""
        else:
            self.wavelength = wave_length
            self.str_wavelength = ""

        self.fields_dict = {}

        if kw:
            for k,v in kw.items():
                self.fields_dict[k] = v

        pass

    def set_sizes(self, bands:int, lines:int, samples:int):
        if bands > 0:
            self.bands = bands
        if lines > 0:
            self.lines = lines
        if samples > 0:
            self.samples = samples


    def set_band_names(self, band_names:list[str]):
        self.band_names = band_names
        self.str_band_names = ",".join(name for name in self.band_names)
        self.str_band_names = "band names = {" + self.str_band_names + "}"


    def update_band_names_by_wavelength(self):
        band_names = [str(round(wv, 2)) for wv in self.wavelength]
        self.set_band_names(band_names)


    def set_wave_length(self, wave_length:list):
        if len(wave_length) > 0:
            if isinstance (wave_length[0], str):
                self.wavelength = [float(wave) for wave in wave_length]
                self.str_wavelength = ",".join(wave for wave in wave_length)
                self.str_wavelength = "wavelength = {" + self.str_wavelength + "}"            
            elif isinstance (wave_length[0], (float, int)):
                self.wavelength = wave_length
                self.str_wavelength = ",".join(str(wave) for wave in wave_length)
                self.str_wavelength = "wavelength = {" + self.str_wavelength + "}"
            else:
                print("set_wave_length tyep error!")
        

    def parse_hdr_info_old(self, hdr_path):
        try:
            with open(hdr_path,encoding='utf-8', errors = 'ignore') as f:
                content = f.readlines()
        except Exception as e:
            return False, f"{hdr_path} open error!"

        for ll in content:
            line_element = ll.replace('\n','').split("=")
            if len(line_element)<=1:
                continue
            k = line_element[0].strip().lower()
            v = line_element[1].strip().lower()
            if k == "samples":
                self.samples = int(line_element[1].strip())
            elif k == "lines":
                self.lines = int(line_element[1].strip())
            elif k == "bands":
                self.bands = int(line_element[1].strip())
            elif k == "data type":
                self.data_type = int(line_element[1].strip())
            elif k == "interleave":
                self.interleave = line_element[1].strip()
            elif k == "byte order":
                self.byte_order = int(line_element[1].strip())
            elif k == "band names":
                self.band_names = line_element[1].strip()[1:-1].split(",")
            elif k == "wavelength":
                self.wavelength = [float(element) for element in (line_element[1].strip()[1:-1].split(","))]
            else:
                self.fields_dict[line_element[0].strip()] = line_element[1].strip()

        self.str_band_names = ",".join(name for name in self.band_names)
        self.str_band_names = "band names = {" + self.str_band_names + "}"

        self.str_wavelength = ",".join(str(wave) for wave in self.wavelength)
        self.str_wavelength = "wavelength = {" + self.str_wavelength + "}"
        
        return True, ""
    

    def parse_hdr_info(self, hdr_path):
        try:
            with open(hdr_path,encoding='utf-8', errors = 'ignore') as f:
                content = f.readlines()
        except Exception as e:
            return False, f"{hdr_path} open error!"
        
        self.fields_dict.clear()
        
        left = False
        k = ""
        list_value = ""
        for ll in content:
            line_element = ll.replace('\n','').split("=")
            if len(line_element)<=1:
                if left:
                    item = line_element[0].strip()
                    list_value += item
                    if item.endswith("}"):
                        left = False
                        self.fields_dict[k] = [item for item in list_value[1:-1].split(',')]
                        list_value = ""
                continue

            k = line_element[0].strip().lower()
            v = line_element[1].strip()

            if v.startswith("{") and v.endswith("}"):
                v_list = [item.strip() for item in v[1:-1].split(',')]
                if v_list[-1] == "":
                    v_list.pop()
                self.fields_dict[k] = v_list
            elif v.startswith("{"):
                left = True
                list_value += v
            else:
                self.fields_dict[k] = v

        # 必选字段
        try:
            self.samples = int(self.fields_dict['samples'])
            self.lines = int(self.fields_dict['lines'])
            self.bands = int(self.fields_dict['bands'])
            self.data_type = int(self.fields_dict['data type'])
            self.interleave = self.fields_dict['interleave']
            self.wavelength = [float(element) for element in self.fields_dict['wavelength']]
        except Exception as e:
            print(e)
            return False, "Key fields reading Error!"
        
        try:   # 兼容之前的错误：因为写入的hdr信息中漏了byte order字段
            self.byte_order = int(self.fields_dict.get('byte order', '0'))
        except Exception as e:
            print(e)
            

        self.band_names = self.fields_dict.get('band names', self.fields_dict['wavelength'])
        
        self.str_band_names = ",".join(item for item in self.band_names)
        self.str_band_names = "band names = {" + self.str_band_names + "}"
        self.str_wavelength = ",".join(item for item in self.fields_dict['wavelength'])
        self.str_wavelength = "wavelength = {" + self.str_wavelength + "}"

        return True, ""
    


    def set_user_defined_param(self, key:str, value:str):

        self.fields_dict[key] = value
        pass

    def get_user_defined_param(self, key:str):

        return self.fields_dict.get(key, "")
        

    def get_gain_exposure_time_info(self):
        '''
        fetch gain and expose time list from hdr info.
        '''
        expose_time_list = []
        gain_list = []
        if 'IrradianceExposureTime' in self.fields_dict and \
                'IrradianceGain' in self.fields_dict:
            expose_time_list.extend([float(v)*1000 for v in self.fields_dict['IrradianceExposureTime'].split(',')])
            gain_list.extend([float(v) for v in self.fields_dict['IrradianceGain'].split(',')])
        
            if len(expose_time_list) > 0 and len(gain_list) > 0:
                return  np.array(gain_list, dtype=np.float32), np.array(expose_time_list, dtype=np.float32)
        
        return None, None


class ImgInfo:

    def __init__(self):

        self.img = None
        self.hdr = None
        self.img_path = ""
        self.hdr_path = ""
        pass

    def empty(self):

        return self.img == None
    

    def clear(self):

        self.img = None
        self.hdr = None
        self.img_path = ""
        self.hdr_path = ""
        
        return
    

    @staticmethod
    def img_path_valid(img_path):
        '''
        判断img文件路径是否合法（包括是否存在对应的hdr文件）
        '''
        if not os.path.exists(img_path):
            return False, f'{img_path} path not exists!'
    
        name, ext = os.path.splitext(img_path)
        if ext != '.img':
            return False, f'{img_path} is not img file!'

        hdr_path = name + '.hdr'
        if not os.path.exists(hdr_path):
            return False, f'{hdr_path} not exists!'
        
        return True, hdr_path


    @staticmethod
    def img_transpose_by_interleave(img:np.ndarray, src_interleave, dst_interleave):
        '''
        静态方法.
        img: 输入的img矩阵
        已知其src_interleave。reshape为dst_interleave
        '''
        # chw -> hwc
        if src_interleave == 'bsq' and dst_interleave == 'bip':
            return np.transpose(img, (1,2,0))
        # chw -> hcw
        if src_interleave == 'bsq' and dst_interleave == 'bil':
            return np.transpose(img, (1,0,2))
        # hwc -> chw
        if src_interleave == 'bip' and dst_interleave == 'bsq':
            return np.transpose(img, (2,0,1))
        # hwc -> hcw
        if src_interleave == 'bip' and dst_interleave == 'bil':
            return np.transpose(img, (0,2,1))
        # hcw -> chw
        if src_interleave == 'bil' and dst_interleave == 'bsq':
            return np.transpose(img, (1,0,2))
        # hcw -> hwc
        if src_interleave == 'bil' and dst_interleave == 'bip':
            return np.transpose(img, (0,2,1))
        
        return img
    

    def transpose_by_interleave(self, dst_interleave):
        '''
        成员函数。将自身的img矩阵reshape为dst_interleave
        并且修改hdr中的interleave信息为成员函数dst_interleave
        '''
        
        self.img = ImgInfo.img_transpose_by_interleave(self.img, self.hdr.interleave, dst_interleave)
        self.hdr.interleave = dst_interleave    


    def get_img_by_interleave(self, dst_interleave):
        '''
        成员函数。将自身的img矩阵复制后reshape为dst_interleave
        不修改自身的img_info
        '''
        img = self.img.copy()
        img = ImgInfo.img_transpose_by_interleave(img, self.hdr.interleave, dst_interleave)
        return img    
    

    def get_img_uint8(self, dst_interleave=None):
        '''
        用于得到用于渲染显示的img
        '''
        if dst_interleave is None or self.hdr.interleave == dst_interleave:
            img = self.img
        else:
            img = ImgInfo.img_transpose_by_interleave(self.img, self.hdr.interleave, dst_interleave)

        if self.hdr.data_type == Img_Data_type.type_uint8:
            return img.copy()
        elif self.hdr.data_type == Img_Data_type.type_uint16:
            img = img.astype(np.float32)*255/65535
            img = img.astype(np.uint8)
            return img
        else:
            return None
            
          


    def create_img_info(self, img_file_path):
        '''
        img_file_path: absolute path of .img 
        .img and .hdr file should be in same file folder.
        return: img, hdr_info
        '''
        ret, info = ImgInfo.img_path_valid(img_file_path)
        if not ret:
            return ret, info

        self.hdr_path = info
        self.hdr = HDRInfo()
        ret, info = self.hdr.parse_hdr_info(self.hdr_path)
        if not ret: 
            return ret, info
        
        if self.hdr.data_type not in [Img_Data_type.type_uint8, Img_Data_type.type_uint16,
                                      Img_Data_type.type_float32] :  
            return False, 'unsupported data type!'     
        
        self.img_path = img_file_path
        
        self.byte_num = Img_Data_type.type_uint8    # uint8
        if self.hdr.data_type == Img_Data_type.type_uint16:      # uint16
            self.byte_num = 2
        elif self.hdr.data_type == Img_Data_type.type_float32:     # float32
            self.byte_num = 4

        self.little_endian = True
        if self.hdr.byte_order == 1:
            self.little_endian = False

        if self.hdr.interleave == 'bsq':
            dims_order = (self.hdr.bands, self.hdr.lines, self.hdr.samples)
        elif self.hdr.interleave == 'bip':
            dims_order = (self.hdr.lines, self.hdr.samples, self.hdr.bands)
        else:
            dims_order = (self.hdr.lines, self.hdr.bands, self.hdr.samples)
        
        if self.byte_num == 1:
            self.img = np.fromfile(img_file_path, dtype=np.uint8).reshape(dims_order)
        elif self.byte_num == 2:
            if self.little_endian:
                img = np.fromfile(img_file_path, dtype='<u2')
                self.img = img.reshape(dims_order)
            else:
                self.img = np.fromfile(img_file_path, dtype='>u2').reshape(dims_order)
        elif self.byte_num == 4:
            self.img = np.fromfile(img_file_path, dtype=np.float32).reshape(dims_order)

        return True, ""


    def get_img(self, filter_wv_list=[], interleave=None, norm=False):
        '''
        filter_wv_list: 
        return: copy of img
        '''

        if self.img is None:
            return None
        
        if 0<len(filter_wv_list)<=self.hdr.bands:
            filter_wv_index = []
            for wv in filter_wv_list:
                index, _ = get_closest_wave_in_spectral_list(self.hdr.wavelength, wv)
                if index < 0:
                    img = self.img.copy()
                    break
                filter_wv_index.append(index)
            else:
                img = self.img[:,:, filter_wv_index].copy()
                pass
            
        else:
            img = self.img.copy()

        if interleave is not None and self.hdr.interleave != interleave:
            img = ImgInfo.img_transpose_by_interleave(img, self.hdr.interleave, interleave)
            pass

        if not norm:
            return img
        
        if self.hdr.data_type == 4:
            maxnumber = img.max()
            pass
        elif self.hdr.data_type == 12:
            maxnumber = 65535
        else:
            maxnumber = 255
            pass
        
        return img.astype(np.float32)/maxnumber


    def get_img_to_show(self, interleave=None):
        '''
        return: copy of img
        '''

        if self.img is None:
            return None
        
        img = self.img.copy()
        if interleave is not None and self.hdr.interleave != interleave:
            img = ImgInfo.img_transpose_by_interleave(img, self.hdr.interleave, interleave)
            pass
        
        if self.hdr.data_type == 4:
            maxnumber = img.max()
            return (img.astype(np.float32)*255/maxnumber).astype(np.uint8)
        elif self.hdr.data_type == 12:
            maxnumber = 65535
            return (img.astype(np.float32)*255/maxnumber).astype(np.uint8)
        else:
            maxnumber = 255
            return img
        
        
    def get_img_by_channels(self, channel_index:list):
        '''
        channel_index: 
        return: img
        '''

        if self.img is None:
            return None
        
        if len(channel_index) == 0 or len(channel_index)>=self.hdr.bands:
            return self.img
        
        for idx in channel_index:
            if isinstance(idx, int) and idx >= 0 and idx < self.hdr.bands:
                pass
            else:
                return None
            
        if self.hdr.interleave == "bip":
            return self.img[:,:, channel_index]
        elif self.hdr.interleave == "bsq":
            return self.img[channel_index, :, :]
        else:
            return self.img[:, channel_index, :]
        
    
    def get_img_by_rect(self, rowrange, colrange):
        '''
        channel_index: 
        return: img
        '''

        if self.img is None:
            return None
        
        for idx in rowrange:
            if isinstance(idx, int) and idx >= 0 and idx < self.hdr.lines:
                pass
            else:
                return None
            
        for idx in colrange:
            if isinstance(idx, int) and idx >= 0 and idx < self.hdr.samples:
                pass
            else:
                return None
            
        if self.hdr.interleave == "bip":
            return self.img[rowrange[0]:rowrange[1], colrange[0]:colrange[1], :]
        elif self.hdr.interleave == "bsq":
            return self.img[:, rowrange[0]:rowrange[1], colrange[0]:colrange[1]]
        else:
            return self.img[rowrange[0]:rowrange[1], :, colrange[0]:colrange[1]]
        

    def get_img_by_roi_mask(self, mask:np.ndarray):
        '''
        mask: shape=[H, W]
        return: img
        '''

        if self.img is None:
            return None

        if self.hdr.interleave == "bip":   # [H, W, C]
            if self.img[:,:,0].shape != mask.shape:
                return None
            return self.img[mask == 255]
 
        elif self.hdr.interleave == "bsq":   # [C, H, W]
            if self.img[0, :, :].shape != mask.shape:
                return None

            return self.img[:, mask == 255].T
        
        else:         # [H, C,  W]
            if self.img[:, 0, :].shape != mask.shape:
                return None
            ch_num= self.hdr.bands
            mask_bool = mask == 255
            mask_bool_expanded = mask_bool[:, np.newaxis, :]
            mask_bool_expanded = np.repeat(mask_bool_expanded, ch_num, axis=1)

            return self.img[mask_bool_expanded].reshape((-1, ch_num))
        


    @staticmethod
    def write_hdr_file(output_hdr_file, hdr_info:HDRInfo):

        with open(output_hdr_file, "w", encoding='utf-8') as f_hdr:
            f_hdr.write("ENVI\n")
            f_hdr.write("description = { Wayho Tech }\n")
            f_hdr.write(f"samples = {hdr_info.samples}\n")
            f_hdr.write(f"lines = {hdr_info.lines}\n")
            f_hdr.write(f"bands = {hdr_info.bands}\n")
            f_hdr.write("header offset = 0\n")
            f_hdr.write(f"data type = {hdr_info.data_type}\n")
            f_hdr.write(f"interleave = {hdr_info.interleave}\n")
            f_hdr.write(f"byte order = {hdr_info.byte_order}\n")
            f_hdr.write(hdr_info.str_band_names+"\n")
            f_hdr.write(hdr_info.str_wavelength+"\n")

            for key, value in hdr_info.fields_dict.items():
                if key in ['description', 'samples', 'lines', 'bands', 'header offset',
                           'data type', 'interleave', 'byte order', 'band names', 'wavelength']:
                    continue
                # print(f"{key}: {value}")
                f_hdr.write(f"{key} = {value}\n")    




def get_np_dtype_from_data_type(data_type):
    '''
    - 1 = Byte: 8-bit unsigned integer
    - 2 = Integer: 16-bit signed integer
    - 3 = Long: 32-bit signed integer
    - 4 = Floating-point: 32-bit single-precision
    - 5 = Double-precision: 64-bit double-precision floating-point
    - 6 = Complex: Real-imaginary pair of single-precision floating-point
    - 9 = Double-precision complex: Real-imaginary pair of double precision floating-point
    - 12 = Unsigned integer: 16-bit
    - 13 = Unsigned long integer: 32-bit
    - 14 = 64-bit long integer (signed)
    - 15 = 64-bit unsigned long integer (unsigned)
    '''
    if data_type == 1:
        return np.uint8
    elif data_type == 2:
        return np.int16
    elif data_type == 3:
        return np.int32
    elif data_type == 4:
        return np.float32
    elif data_type == 5:
        return np.float64
    elif data_type == 6:
        return np.complex64
    elif data_type == 9:
        return np.complex128
    elif data_type == 12:
        return np.uint16
    elif data_type == 13:
        return np.uint32
    elif data_type == 14:
        return np.int64
    elif data_type == 15:
        return np.uint64
    else:
        return None


def save_img(img, file_path, hdr_info:HDRInfo):
    filename, ext = os.path.splitext(file_path)
    hdr_file_path = filename+".hdr"
    ImgInfo.write_hdr_file(hdr_file_path, hdr_info)


    if hdr_info.data_type == 1:
        img.tofile(file_path)
    elif hdr_info.data_type == 12:
        if hdr_info.byte_order == 0:
            img.astype('<u2').tofile(file_path)
        else:
            img.astype('>u2').tofile(file_path)
    elif hdr_info.data_type == 4:
        img.astype(np.float32).tofile(file_path)


def get_closest_wave_in_spectral_list(src_wave_list, dst_wav, dist = 5):
    '''
    在train_wave_list中查找和test_wave最接近的波段,
    返回其在train_wave_list中的序号和波段取值
    如果没有找到，则索引返回-1
    '''

    index = -1
    match_wav = -1
    for i, wav in enumerate(src_wave_list):

        if isinstance(wav, str):
            try:
                wav = float(wav)
            except Exception as e:
                return -1, -1

        delta = abs(wav-dst_wav)
        if delta < dist:
            index = i
            match_wav = wav
            dist = delta

    return index, match_wav



def get_wave_index_list_from_hdr(hdr_wave_list, wave_list):
    '''
    从HDR文件信息，查找wave_list中每个波段的索引
    '''
    
    wave_index_list = []
    for wv in wave_list:
        index = get_closest_wave_in_spectral_list(hdr_wave_list, wv)[0]
        if index<0:
            return []
        wave_index_list.append(index)
    
    return wave_index_list



def get_filter_wave_info_list(img_wave_info_list:list, filter_wave_def:list, binning_count = 1):
    '''
    从IMG文件信息列表，查找filter_wave_def中各个波段区间或波段的索引
    '''
    
    wav_list = []
    wave_index_list = []
    idx = 0
    wave_count = len(img_wave_info_list)
    for wv_item in filter_wave_def:
        if type(wv_item) == tuple:
            left = wv_item[0]
            right = wv_item[1]
            temp_list = []
            while idx < wave_count:
                if img_wave_info_list[idx] < left:
                    idx += 1
                    continue
                elif img_wave_info_list[idx] <= right:
                    temp_list.append(img_wave_info_list[idx])
                    wave_index_list.append(idx)
                    idx += 1
                    continue
                else:
                    break
        elif type(wv_item) == int:
            index = get_closest_wave_in_spectral_list(img_wave_info_list, wv_item)
            if index > 0:
                wav_list.append(img_wave_info_list[index])
                wave_index_list.append(index)
            pass

        else:
            pass
    
    return wav_list, wave_index_list


def get_filter_wave_info_from_hdr(hdr_wave_list:list, filter_wave_def:list):
    '''
    从HDR文件信息，查找filter_wave_def中各个波段区间或波段的索引
    '''
    
    wav_list = []
    wave_index_list = []
    idx = 0
    wave_count = len(hdr_wave_list)
    for wv_item in filter_wave_def:
        if type(wv_item) == tuple:
            left = wv_item[0]
            right = wv_item[1]

            while idx < wave_count:
                if hdr_wave_list[idx] < left:
                    idx += 1
                    continue
                elif hdr_wave_list[idx] <= right:
                    wav_list.append(hdr_wave_list[idx])
                    wave_index_list.append(idx)
                    idx += 1
                    continue
                else:
                    break
        elif type(wv_item) == int:
            index = get_closest_wave_in_spectral_list(hdr_wave_list, wv_item)
            if index > 0:
                wav_list.append(hdr_wave_list[index])
                wave_index_list.append(index)
            pass

        else:
            pass
    
    return wav_list, wave_index_list



def img_path_valid(img_path):

    if not os.path.exists(img_path):
        return False
    
    name, ext = os.path.splitext(img_path)
    if ext != '.img':
        return False

    hdr_path = name + '.hdr'
    if not os.path.exists(hdr_path):
        return False
    
    return True


if __name__ == '__main__':

    
    filepath = r"D:/00 Work/D_2023_01_12_15-49-59_9_channels_downsize.img"

    hdr_path = r"Z:\20241127-深圳技术大学考察Specim SWIR\数据\塑料样本\capture\spectrum_test_0222.hdr"

    hdr = HDRInfo()

    hdr.parse_hdr_info(hdr_path)

    
    img_info = ImgInfo.get_img_info(filepath)

    img = img_info[0]

    hdrinfo = img_info[1]

    hdrinfo.lines = 20
    
    # ImgInfo.write_hdr_file("test.hdr", hdrinfo)
    

    pass
