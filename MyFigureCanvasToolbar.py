import matplotlib.pyplot as plt
import tkinter as tk
import tkinter.filedialog
from tkinter.font import Font
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg, NavigationToolbar2Tk)

from matplotlib.textpath import TextPath
from matplotlib.patches import PathPatch

from draw_utils import ImgDataManager

class FigureCanvasNavigationToolbar(NavigationToolbar2Tk):

    # def plot_axes(self):
    #     # This function currently makes it so that the 'original view' is lost
    #     # TODO Fix the above bug
    #     self.canvas.figure.axes[0].set_xlim([10,60])
    #     self.canvas.draw()

    def __init__(self, canvas, parent=None, pack_toolbar=True):
        self.toolitems = (
            ('Home', 'Reset original view', 'home', 'home'),
            ('Back', 'Back to previous view', 'back', 'back'),
            ('Forward', 'Forward to next view', 'forward', 'forward'),
            ('Pan', 'Pan axes with left mouse, zoom with right', 'move', 'pan'),
            ('Zoom', 'Zoom to rectangle', 'zoom_to_rect', 'zoom'),
            ('Subplots', 'Configure subplots', 'subplots', 'configure_subplots'),
            ('Save', 'Save the figure', 'filesave', 'save_figure'),
             # TODO Get this poor thing a nice gif（name, tip, icon, command）
            ('SaveWave', 'Save wave mean value', 'filesave', 'save_wav_avg'),
            )
        NavigationToolbar2Tk.__init__(self,canvas, window=parent, pack_toolbar=pack_toolbar)
        self.wav_sample_count = 0
        self.wav_avg = []

        # self.canvas.mpl_disconnect(self._id_drag)


    def set_img_path(self, img_path):
        self.img_path = img_path


    def add_text_to_plot(self):
        # x, y = 0.5, 0.5  # 文本的位置（坐标中心）
        self.custom_text = self.canvas.figure.gca().set_title(self.wav_avg)

        
        # 重新绘制canvas
        self.canvas.draw()

    def show_wav_avg(self, arr_wav_avg=None):
        self.wav_avg = arr_wav_avg
        if arr_wav_avg is not None:
            self.custom_text = self.canvas.figure.gca().set_title(', '.join(f"{i:.2f}" for i in arr_wav_avg))
        else:
            self.canvas.figure.gca().set_title("")
        # self.canvas.draw()
        

    def save_wav_avg(self):

        return

        tk_filetypes = [
            ('All Files', "*.* *.conf")
        ]
        fname = tkinter.filedialog.asksaveasfilename(
            master=self.canvas.get_tk_widget().master,
            title='Save wave mean value',
            filetypes=tk_filetypes,
            defaultextension="*.*",
            # # initialdir=initialdir,
            # initialfile=initialfile,
            # typevariable=filetype_variable
            )

        if fname in ["", ()]:
            return

        wave = ','.join(f"{i:.2f}" for i in self.wav_avg)

        with open(fname, "a", encoding='utf-8') as f:
            f.write(f"# {self.img_path}\n")
            f.write(str(self.wav_sample_count)+",")
            f.write(wave+"\n")
            pass


        pass


    '''
        self._id_press = self.canvas.mpl_connect(
            'button_press_event', self._zoom_pan_handler)
        self._id_release = self.canvas.mpl_connect(
            'button_release_event', self._zoom_pan_handler)
        self._id_drag = self.canvas.mpl_connect(
            'motion_notify_event', self.mouse_move)
    '''

    def mouse_move(self, event):
        '''
        mpl_connect("motion_notify_event"的默认响应事件
        '''
        if ImgDataManager.img_info is None:
            return
        
        if event.xdata is None or event.ydata is None:
            return
        
        n = round(event.xdata)
        if 0<=n<len(ImgDataManager.wave_enabled_list):
            xdata = ImgDataManager.wave_enabled_list[n]
            ydata = event.ydata
            self.set_message(f"(x, y) = ({xdata:4.2f}, {ydata:5.2f})")

        return
    
