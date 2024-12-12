import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import threading
# import time
# from sam_model import SamModel
import os
from PIL import Image
import numpy as np
from Img_Functions import HDRInfo, save_img
import shutil

class PredictProgressDialog(tk.Toplevel):
    def __init__(self, app, result_dir, 
                 sam_model,  file_path_list = [],  
                 master=None, title="运算任务进度", message="正在执行..."):
        super().__init__(master)
        self.title(title)
        self.app = app
        self.grab_set()
        
        self.result_dir = result_dir
        self.sam_model = sam_model
        self.file_path_list = file_path_list

        self.task_amount = len(self.file_path_list)
        self.sub_task_name = self.file_path_list[0]

        self.progress_var = tk.DoubleVar()
        self.progress_var.set(0.0)
        self.count = 0

        # 创建进度条
        frame = tk.Frame(self)
        frame.pack(side='top', expand=1, fill='both')
        text = f"[1 / {self.task_amount}]  {self.sub_task_name}"
        self.label = tk.Label(frame, text=text)
        self.label.pack(side='top', pady=5, expand=1, fill='x')
        self.progressbar = ttk.Progressbar(frame, orient="horizontal", length=200, mode="determinate")
        self.progressbar.pack(side='top',pady=5, expand=1, fill='x')
        self.progressbar.config(variable=self.progress_var)
        
        self.cancel_button = tk.Button(frame, text="取  消", command=self.cancel_click)
        self.cancel_button.pack(side='bottom', pady=10)
        self.bind("<Escape>", self.cancel_click)
        self.protocol("WM_DELTE_WINDOW", self.cancel_click)
        
        # 初始化进度为0
        self.progress_var.set(0)
        
        # 标志对话框是否已被取消
        self.cancelled = False
        
        # 放置对话框在屏幕中央
        print(f"{self.winfo_reqwidth()}x{self.winfo_reqheight()}+{int((self.master.winfo_screenwidth() - self.winfo_reqwidth()) / 2)}+{int((self.master.winfo_screenheight() - self.winfo_reqheight()) / 2)}")
        self.geometry(f"400x{self.winfo_reqheight()}+{int((self.master.winfo_screenwidth() - self.winfo_reqwidth()) / 2)}+{int((self.master.winfo_screenheight() - self.winfo_reqheight()) / 2)}")
        # self.geometry("400x300")  # 设置宽度和高度


        # 在新线程中运行任务
        self.task_thread = threading.Thread(target=self.run_task)
        self.task_thread.daemon = True
        self.task_thread.start()

    
    def update_progress(self, task_index):
        '''
        每个任务结束后更新
        '''
        if not self.cancelled:
            next_index = task_index + 1
            value = next_index*100/self.task_amount
            self.progress_var.set(value)
            
            if next_index < self.task_amount:   # 如果不是最后一个任务
                task_count = next_index + 1 
                self.sub_task_name = self.file_path_list[next_index]
                text = f"[{task_count} / {self.task_amount}] : {self.sub_task_name}"
                self.label.config(text=text)   # self.label1["text"] = text1


    def cancel_click(self):
        if self.cancel_button['text'] == '取  消':
            self.cancelled = True

        self.app.count = self.count
        self.destroy()

    
    def run_task(self):

        self.count = 0
        for i, file_path in enumerate(self.file_path_list):

            result_img = self.sam_model.predict_img(file_path)

            if result_img is None:
                continue

            basename = os.path.basename(file_path)
            name, ext = os.path.splitext(basename)
            result_filepath = os.path.join(self.result_dir, name + ".jpg")

            # 使用PIL保存图像
            img = Image.fromarray(result_img, 'RGB')
            img.save(result_filepath)

            print(f"{result_filepath} saved!")
            self.count += 1

            self.update_progress(i)
            if self.cancelled:
                break

        # 任务完成后关闭对话框
        # if not self.cancelled:
        #     self.destroy()
        if not self.cancelled:
            self.cancel_button['text'] = '完  成'



class PredictOneImgProgressDialog(tk.Toplevel):
    def __init__(self, app, 
                 sam_model,  input_img:str,  file_path, 
                 master=None, title="Img推理进度", message="正在执行..."):
        super().__init__(master)
        self.title(title)
        self.app = app
        self.grab_set()
        
        self.sam_model = sam_model
        self.input_img = input_img

        self.task_amount = input_img.shape[1]
        self.sub_task_name = file_path

        self.progress_var = tk.DoubleVar()
        self.progress_var.set(0.0)
        self.count = 0

        # 创建进度条
        frame = tk.Frame(self)
        frame.pack(side='top', expand=1, fill='both')
        text = f"[1 / {self.task_amount}]\n{self.sub_task_name}"
        self.label = tk.Label(frame, text=text)
        self.label.pack(side='top', pady=5, expand=1, fill='x')
        self.progressbar = ttk.Progressbar(frame, orient="horizontal", length=240, mode="determinate")
        self.progressbar.pack(side='top',pady=5, expand=1, fill='x')
        self.progressbar.config(variable=self.progress_var)
        
        self.cancel_button = tk.Button(frame, text="取  消", command=self.cancel_click)
        self.cancel_button.pack(side='bottom', pady=10)
        self.bind("<Escape>", self.cancel_click)
        self.protocol("WM_DELTE_WINDOW", self.cancel_click)
        
        # 初始化进度为0
        self.progress_var.set(0)
        
        # 标志对话框是否已被取消
        self.cancelled = False
        
        # 放置对话框在屏幕中央
        print(f"{self.winfo_reqwidth()}x{self.winfo_reqheight()}+{int((self.master.winfo_screenwidth() - self.winfo_reqwidth()) / 2)}+{int((self.master.winfo_screenheight() - self.winfo_reqheight()) / 2)}")
        self.geometry(f"400x{self.winfo_reqheight()}+{int((self.master.winfo_screenwidth() - self.winfo_reqwidth()) / 2)}+{int((self.master.winfo_screenheight() - self.winfo_reqheight()) / 2)}")
        # self.geometry("400x300")  # 设置宽度和高度

        # 在新线程中运行任务
        self.task_thread = threading.Thread(target=self.run_task)
        self.task_thread.daemon = True
        self.task_thread.start()

    
    def update_progress(self, task_index):
        '''
        每个任务结束后更新
        '''
        if not self.cancelled:
            next_index = task_index + 1
            value = next_index*100/self.task_amount
            self.progress_var.set(value)
            
            if next_index < self.task_amount:   # 如果不是最后一个任务
                task_count = next_index + 1 
                text = f"[{task_count} / {self.task_amount}]\n{self.sub_task_name}"
                self.label.config(text=text)   # self.label1["text"] = text1


    def cancel_click(self):
        if self.cancel_button['text'] == '取  消':
            self.cancelled = True
        self.destroy()

    
    def run_task(self):
        
        h, w, c = self.input_img.shape

        count = 0
        for i in range(w):
            input_line = self.input_img[:, i, :].reshape((h, c))
            
            result = self.sam_model.predict_2d(input_line)

            if self.app.result_img is None:
                self.app.result_img = result
            else:
                self.app.result_img = np.concatenate([self.app.result_img, result], axis = 1)

            count += 1
            self.update_progress(i)
            if self.cancelled:
                break
        
        if count == w:
            self.app.finish = True
        # 任务完成后关闭对话框
        # if not self.cancelled:
        #     self.destroy()
        if not self.cancelled:
            self.cancel_button['text'] = '完  成'

        return
    
    pass


class Tifs2ImgProgressDialog(tk.Toplevel):
    def __init__(self, app, wv_list=[], img_dir_path = "",
                 img_filename_rule="",  index_filepath_dict:dict = {}, 
                 master=None, title="Tif组合Img任务进度"):
        super().__init__(master)
        self.title(title)
        self.app = app
        self.grab_set()
        
        self.img_dir_path = img_dir_path
        self.img_filename_rule = img_filename_rule
        self.index_filepath_dict = index_filepath_dict
        self.wv_list = wv_list
        self.tifs_count = len(wv_list)

        self.task_amount = len(index_filepath_dict)
        self.sub_task_name = ""

        self.progress_var = tk.DoubleVar()
        self.progress_var.set(0.0)
        self.count = 0

        # 创建进度条
        frame = tk.Frame(self)
        frame.pack(side='top', expand=1, fill='both')
        text = f"[0 / {self.task_amount}] "
        self.label = tk.Label(frame, text=text)
        self.label.pack(side='top', pady=5, expand=1, fill='x')
        self.progressbar = ttk.Progressbar(frame, orient="horizontal", length=200, mode="determinate")
        self.progressbar.pack(side='top',pady=5, expand=1, fill='x')
        self.progressbar.config(variable=self.progress_var)
        
        self.cancel_button = tk.Button(frame, text="取  消", command=self.cancel_click)
        self.cancel_button.pack(side='bottom', pady=10)
        self.bind("<Escape>", self.cancel_click)
        self.protocol("WM_DELTE_WINDOW", self.cancel_click)
        
        # 初始化进度为0
        self.progress_var.set(0)
        
        # 标志对话框是否已被取消
        self.cancelled = False
        
        # 放置对话框在屏幕中央
        print(f"{self.winfo_reqwidth()}x{self.winfo_reqheight()}+{int((self.master.winfo_screenwidth() - self.winfo_reqwidth()) / 2)}+{int((self.master.winfo_screenheight() - self.winfo_reqheight()) / 2)}")
        self.geometry(f"800x{self.winfo_reqheight()}+{int((self.master.winfo_screenwidth() - self.winfo_reqwidth()) / 2)}+{int((self.master.winfo_screenheight() - self.winfo_reqheight()) / 2)}")
        # self.geometry("400x300")  # 设置宽度和高度


        # 在新线程中运行任务
        self.task_thread = threading.Thread(target=self.run_task)
        self.task_thread.daemon = True
        self.task_thread.start()

    
    def update_progress(self, task_finish_count, info, step_info=""):
        '''
        每个任务结束后更新
        '''
        if not self.cancelled:
            value = task_finish_count*100/self.task_amount
            self.progress_var.set(value)
            
            text = f"[{step_info}{task_finish_count} / {self.task_amount}] : {info}!"
            self.label.config(text=text)   # self.label1["text"] = text1
                

    def cancel_click(self):
        
        if self.cancel_button['text'] == '取  消':
            answer = messagebox.askyesno("确认？" , "确定要停止吗？", default=messagebox.NO)
            if not answer:
                return
            self.cancelled = True

        self.app.count = self.count
        self.destroy()

    
    def run_task(self):
        '''
        
        '''

        # Step 1:    tif->img ....

        if self.tifs_count <= 0:
            return
        
        tif_file_num = 0

        import re
        def replace_last_occurrence(s, old, new):
            # 使用正则表达式，替换最后一次出现的旧字符串
            pattern = re.compile(re.escape(old))
            return pattern.sub(new, s, count=1) if pattern.search(s) else s
        
        self.count = 0
        for i, (str_index, file_path_list) in enumerate(self.index_filepath_dict.items()):
            
            tif_file_num += len(file_path_list)

            wv_len = len(file_path_list)
            if wv_len != self.tifs_count:
                self.count += 1
                self.update_progress(i+1, f"index {str_index} skipped!", step_info="[step: 1/3]  ")
                continue

            img_file = replace_last_occurrence(self.img_filename_rule, "[nnnn]", str_index)
            one_img_list = []
            data_type = 0
            byte_order = 0
            lines = 0
            samples = 0

            IrradianceExposureTime = []
            IrradianceGain = []
            for j, file_path in enumerate(file_path_list):
                from algos import get_tiff_info
                tif_info_dict = get_tiff_info(file_path)
                
                if 'IrradianceExposureTime' in tif_info_dict and \
                    'IrradianceGain' in tif_info_dict:
                    IrradianceExposureTime.append(tif_info_dict['IrradianceExposureTime'])
                    IrradianceGain.append(tif_info_dict['IrradianceGain'])
                else: 
                    print(f"{file_path}: not gain info!")

                tif = Image.open(file_path)         #可以读取单通道影像,读取3通道16位tif影像时报错(PIL.UnidentifiedImageError: cannot identify image file),支持4通道8位影像
                
                if j == 0:   # 从第一个文件读取即可
                    mode = tif.mode
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

                arr = np.array(tif)
                one_img_list.append(arr)

                tif.close()

                pass


            img = np.stack(one_img_list, axis=0)

            bands = self.tifs_count
            interleave = 'bsq'
            band_names = [str(wv) for wv in self.wv_list]

            kw_param = {}
            if len(IrradianceExposureTime) == self.tifs_count and\
                len(IrradianceGain) == self.tifs_count:

                kw_param['IrradianceExposureTime'] = ','.join(i for i in IrradianceExposureTime)
                kw_param['IrradianceGain'] = ','.join(i for i in IrradianceGain)

            hdrinfo = HDRInfo(bands,lines,samples, data_type, interleave, band_names, self.wv_list, byte_order, **kw_param)
        
            img_path = os.path.join(self.img_dir_path, img_file)
            save_img(img, img_path, hdrinfo)

            print(f"{img_file} saved!")

            self.update_progress(i+1, f"{img_file} saved!", step_info="[step: 1/3]  ")
            if self.cancelled:
                break

        if self.cancelled:
            return
        
        # Step 2: ....
        self.task_amount = tif_file_num
        self.update_progress(0, "deleting tif file", step_info="[step: 2/3]  ")
        self.count = 0
        for i, (str_index, file_path_list) in enumerate(self.index_filepath_dict.items()):
            for j, file_path in enumerate(file_path_list):
                self.count += 1
                os.remove(file_path)
                print(f"{file_path} deleted!")
                self.update_progress(self.count, f"{file_path} deleted!", step_info="[step: 2/3]  ")
                if self.cancelled:
                    break
            else:
                continue
            break

        if self.cancelled:
            return

        # Step 3: ....
        self.task_amount = len(os.listdir(self.img_dir_path))
        self.update_progress(0, "rename files", step_info="[step: 3/3]  ")
        self.count = 0
        
        par_dir = os.path.basename(self.img_dir_path)
        for filename in os.listdir(self.img_dir_path):
            name, ext = os.path.splitext(filename)
            
            src_file_path = os.path.join(self.img_dir_path, filename)

            dst_filename = '_'.join([par_dir, filename])
            dest_file_path = os.path.join(self.img_dir_path, dst_filename)
            print(src_file_path+" => "+dest_file_path)
            shutil.move(src_file_path, dest_file_path)
            self.count += 1
            self.update_progress(self.count, f"{src_file_path} renamed!", step_info="[step: 3/3]  ")
            if self.cancelled:
                break

            pass

        if self.cancelled:
            return

        # 任务完成后关闭对话框
        # if not self.cancelled:
        #     self.destroy()
        if not self.cancelled:
            self.cancel_button['text'] = '完  成'



if __name__ == "__main__":

    # 创建主窗口
    root = tk.Tk()
    root.title("主窗口")

    # 定义一个函数来启动进度对话框和任务
    def start_task():
        progress_dialog = PredictProgressDialog(root)
        # 在新线程中运行任务
        task_thread = threading.Thread(target=progress_dialog.run_task, args=())
        task_thread.daemon = True
        task_thread.start()

    # 添加启动按钮
    start_button = tk.Button(root, text="开始运算", command=start_task)
    start_button.pack(pady=20)

    # 运行主循环
    root.mainloop()
