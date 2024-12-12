import tkinter as tk
import tkinter.font
from pathlib import Path
import numpy as np
from PIL import Image, ImageTk
from algos import random_color_hexstr, COLOR_CONF_LIST, mcolor_2_hexstr

def add_tooltip(widget, text):
    tipwindow = None

    def showtip(event):
        """Display text in tooltip window."""
        nonlocal tipwindow
        if tipwindow or not text:
            return
        x, y, _, _ = widget.bbox("insert")
        x = x + widget.winfo_rootx() + widget.winfo_width()
        y = y + widget.winfo_rooty()
        tipwindow = tk.Toplevel(widget)
        tipwindow.overrideredirect(1)
        tipwindow.geometry(f"+{x}+{y}")
        try:  # For Mac OS
            tipwindow.tk.call("::tk::unsupported::MacWindowStyle",
                              "style", tipwindow._w,
                              "help", "noActivates")
        except tk.TclError:
            pass
        label = tk.Label(tipwindow, text=text, justify=tk.LEFT,
                         relief=tk.SOLID, borderwidth=1)
        label.pack(ipadx=1)

    def hidetip(event):
        nonlocal tipwindow
        if tipwindow:
            tipwindow.destroy()
        tipwindow = None

    widget.bind("<Enter>", showtip)
    widget.bind("<Leave>", hidetip)

    return


class MyBaseToolbar(tk.Frame):

    def __init__(self, window, app=None, toolitems=()):
        """
        Parameters
        ----------
        app :  MainWindowApp
        window : tk.Window
            The tk.Window which owns this toolbar.
        """

        tk.Frame.__init__(self, master=window, borderwidth=2, height=50)

        self.app = app
        self._buttons = {}
        self.read_btn_config(toolitems)

        self._label_font = tkinter.font.Font(root=window, size=10)


    def read_btn_config(self, toolitems):

        for text, tooltip_text, image_file, callback, type, variable, bg_color in toolitems:
            if text is None:
                # Add a spacer; return value is unused.
                self._Spacer()
            else:
                self._buttons[text] = button = self._Button(
                    text,
                    image_file,
                    toggle=type,
                    command=getattr(self, callback),
                    var=getattr(self, variable),
                    bg_color=bg_color
                )
                if tooltip_text is not None:
                    add_tooltip(button, tooltip_text)



    def _update_buttons_checked(self, check_btn_text):
        # sync button checkstates to match active mode
        for text, btn in self._buttons.items():
            if isinstance(btn , tk.Checkbutton):
                if text == check_btn_text:
                    btn.select()  # NOT .invoke()
                else:
                    btn.deselect()
        return

    
    def _set_image_for_button(self, button):
        """
        Set the image for a button based on its pixel size.

        The pixel size is determined by the DPI scaling of the window.
        """
        if button._image_file is None:
            return

        # Allow _image_file to be relative to Matplotlib's "images" data
        # directory.
        path_regular = Path(button._image_file)
        path_large = path_regular.with_name(
            path_regular.name.replace('.png', '_large.png'))
        size = button.winfo_pixels('18p')

        # Nested functions because ToolbarTk calls  _Button.
        def _get_color(color_name):
            # `winfo_rgb` returns an (r, g, b) tuple in the range 0-65535
            return button.winfo_rgb(button.cget(color_name))

        def _is_dark(color):
            if isinstance(color, str):
                color = _get_color(color)
            return max(color) < 65535 / 2

        def _recolor_icon(image, color):
            image_data = np.asarray(image).copy()
            black_mask = (image_data[..., :3] == 0).all(axis=-1)
            image_data[black_mask, :3] = color
            return Image.fromarray(image_data, mode="RGBA")

        # Use the high-resolution (48x48 px) icon if it exists and is needed
        with Image.open(path_large if (size > 24 and path_large.exists())
                        else path_regular) as im:
            # assure a RGBA image as foreground color is RGB
            im = im.convert("RGBA")
            image = ImageTk.PhotoImage(im.resize((size, size)), master=self)
            button._ntimage = image

            # create a version of the icon with the button's text color
            foreground = (255 / 65535) * np.array(
                button.winfo_rgb(button.cget("foreground")))
            im_alt = _recolor_icon(im, foreground)
            image_alt = ImageTk.PhotoImage(
                im_alt.resize((size, size)), master=self)
            button._ntimage_alt = image_alt

        if _is_dark("background"):
            # For Checkbuttons, we need to set `image` and `selectimage` at
            # the same time. Otherwise, when updating the `image` option
            # (such as when changing DPI), if the old `selectimage` has
            # just been overwritten, Tk will throw an error.
            image_kwargs = {"image": image_alt}
        else:
            image_kwargs = {"image": image}
        # Checkbuttons may switch the background to `selectcolor` in the
        # checked state, so check separately which image it needs to use in
        # that state to still ensure enough contrast with the background.
        if (
            isinstance(button, tk.Checkbutton)
            and button.cget("selectcolor") != ""
        ):
            if self._windowingsystem != "x11":
                selectcolor = "selectcolor"
            else:
                # On X11, selectcolor isn't used directly for indicator-less
                # buttons. See `::tk::CheckEnter` in the Tk button.tcl source
                # code for details.
                r1, g1, b1 = _get_color("selectcolor")
                r2, g2, b2 = _get_color("activebackground")
                selectcolor = ((r1+r2)/2, (g1+g2)/2, (b1+b2)/2)
            if _is_dark(selectcolor):
                image_kwargs["selectimage"] = image_alt
            else:
                image_kwargs["selectimage"] = image

        button.configure(**image_kwargs, height='18p', width='18p')


    def _Button(self, text, image_file, toggle, command, var, bg_color):
        if not toggle:
            b = tk.Button(
                master=self, text=text, command=command, bg=bg_color,
                relief="flat", overrelief="groove", borderwidth=1,
            )
        else:
            # There is a bug in tkinter included in some python 3.6 versions
            # that without this variable, produces a "visual" toggling of
            # other near checkbuttons
            # https://bugs.python.org/issue29402
            # https://bugs.python.org/issue25684
            
            b = tk.Checkbutton(
                master=self, text=text, command=command, indicatoron=False, bg=bg_color,
                variable=var, offrelief="flat", overrelief="groove",
                borderwidth=1
            )
            
        b._image_file = image_file
        if image_file is not None:
            self._set_image_for_button(self, b)
        else:
            b.configure(font=self._label_font)
        b.pack(side=tk.LEFT)
        return b

    def _Spacer(self):
        # Buttons are also 18pt high.
        s = tk.Frame(master=self, height='18p', relief=tk.RIDGE, bg='DarkGray')
        s.pack(side=tk.LEFT, padx='3p')
        return s


    # Callback Functions...
     
    
    def set_history_buttons(self):
        state_map = {True: tk.NORMAL, False: tk.DISABLED}
        can_back = True
        can_forward = True
        if "Back" in self._buttons:
            self._buttons['Back']['state'] = state_map[can_back]
        if "Forward" in self._buttons:
            self._buttons['Forward']['state'] = state_map[can_forward]




class MyColorSelectorToolbar(tk.Frame):
    def __init__(self, window, app=None):
        
        tk.Frame.__init__(self, master=window, borderwidth=2, height=50)

        # self.btn_dict = {}
        self.var_list = []
        self.btn_name_list = []
        # self.cur_color_name = 'random'
        var_color = tkinter.IntVar(value=1)
        self.var_list.append(var_color)
        self.var_check_index = 0
        b = tk.Checkbutton(
                master=self, text='', command=self.switch_color, indicatoron=False, 
                variable=var_color, offrelief="ridge", overrelief="sunken",
                # onvalue='random', offvalue='random',
                borderwidth=1, width=2
            )
        add_tooltip(b, 'random color')
        self.btn_name_list.append('random')
        # self.btn_dict['random'] = b

        b.pack(side=tk.LEFT)

        for i in range(10):
            color_name = COLOR_CONF_LIST[i]
            bg_color = mcolor_2_hexstr(COLOR_CONF_LIST[i])
            var_color = tkinter.IntVar(value=0)
            self.var_list.append(var_color)
            b = tk.Checkbutton(
                master=self, text='', command=self.switch_color, indicatoron=False, bg=bg_color,
                variable=var_color, offrelief="ridge", overrelief="sunken", activebackground=bg_color,
                # onvalue=f'1{color_name}', offvalue=f'0{color_name}',
                borderwidth=1, width=2, selectcolor=bg_color
            )
            b.pack(side=tk.LEFT)
            add_tooltip(b, color_name)
            self.btn_name_list.append(color_name)
            # self.btn_dict[color_name] = b
            pass
        
    
    def switch_color(self):
        '''
        点击颜色按钮的响应事件
        '''
        for i, var in enumerate(self.var_list):
            v_check = var.get()
            if v_check == 1 and i != self.var_check_index:
                # 判断是否是之前check的那个
                self.var_check_index = i
                
                for j, var_j in enumerate(self.var_list):
                    if self.var_check_index != j:
                        var_j.set(0)

                break
        else:
            var = self.var_list[self.var_check_index]  # 1->0
            var.set(1)

        print("color selected index is : ", self.var_check_index)
        
        return
    

    def set_next_specified_color(self):
        '''
        设置下一个配置的颜色
        '''
        if self.var_check_index == 10:
            self.var_check_index = 1
        else:
            self.var_check_index += 1

        for i, var in enumerate(self.var_list):
            if i == self.var_check_index:
                var.set(1)
            else:
                var.set(0)
        
        return
    

    def get_current_color_hex(self):
        '''
        获取当前选定的颜色
        '''

        if self.var_check_index == 0:
            return random_color_hexstr()
        else:
            return mcolor_2_hexstr(self.btn_name_list[self.var_check_index])
        
    
    def get_next_color_hex(self):
        '''
        获取下一个配置的颜色
        '''
        self.set_next_specified_color()

        return self.get_current_color_hex()

                


transform_toolitems = (
        ('Home', 'Reset original view', 'home', 'home'),
        ('Back', 'Back to previous view', 'back', 'back'),
        ('Forward', 'Forward to next view', 'forward', 'forward'),
        (None, None, None, None),
        ('Pan',
         'Left button pans, Right button zooms\n'
         'x/y fixes axis, CTRL fixes aspect',
         'move', 'pan'),
        ('Zoom', 'Zoom to rectangle\nx/y fixes axis', 'zoom_to_rect', 'zoom'),
        ('Subplots', 'Configure subplots', 'subplots', 'configure_subplots'),
        (None, None, None, None),
        ('Save', 'Save the figure', 'filesave', 'save_figure'),
      )

class TransformerSelectorToolbar(tk.Frame):
    def __init__(self, window, app=None):
        
        tk.Frame.__init__(self, master=window, borderwidth=2, height=50)

        # self.btn_dict = {}
        self.var_list = []
        self.btn_name_list = []
        # self.cur_color_name = 'random'
        var_color = tkinter.IntVar(value=1)
        self.var_list.append(var_color)
        self.var_check_index = 0
        b = tk.Checkbutton(
                master=self, text='', command=self.switch_color, indicatoron=False, 
                variable=var_color, offrelief="ridge", overrelief="sunken",
                # onvalue='random', offvalue='random',
                borderwidth=1, width=2
            )
        add_tooltip(b, 'random color')
        self.btn_name_list.append('random')
        # self.btn_dict['random'] = b

        b.pack(side=tk.LEFT)

        for i in range(10):
            color_name = COLOR_CONF_LIST[i]
            bg_color = mcolor_2_hexstr(COLOR_CONF_LIST[i])
            var_color = tkinter.IntVar(value=0)
            self.var_list.append(var_color)
            b = tk.Checkbutton(
                master=self, text='', command=self.switch_color, indicatoron=False, bg=bg_color,
                variable=var_color, offrelief="ridge", overrelief="sunken", activebackground=bg_color,
                # onvalue=f'1{color_name}', offvalue=f'0{color_name}',
                borderwidth=1, width=2, selectcolor=bg_color
            )
            b.pack(side=tk.LEFT)
            add_tooltip(b, color_name)
            self.btn_name_list.append(color_name)
            # self.btn_dict[color_name] = b
            pass
        
    
    def switch_color(self):
        '''
        点击颜色按钮的响应事件
        '''
        for i, var in enumerate(self.var_list):
            v_check = var.get()
            if v_check == 1 and i != self.var_check_index:
                # 判断是否是之前check的那个
                self.var_check_index = i
                
                for j, var_j in enumerate(self.var_list):
                    if self.var_check_index != j:
                        var_j.set(0)

                break
        else:
            var = self.var_list[self.var_check_index]  # 1->0
            var.set(1)

        print("color selected index is : ", self.var_check_index)
        
        return
    

    def set_next_specified_color(self):
        '''
        设置下一个配置的颜色
        '''
        if self.var_check_index == 10:
            self.var_check_index = 1
        else:
            self.var_check_index += 1

        for i, var in enumerate(self.var_list):
            if i == self.var_check_index:
                var.set(1)
            else:
                var.set(0)
        
        return
    

    def get_current_color_hex(self):
        '''
        获取当前选定的颜色
        '''

        if self.var_check_index == 0:
            return random_color_hexstr()
        else:
            return mcolor_2_hexstr(self.btn_name_list[self.var_check_index])
        
    
    def get_next_color_hex(self):
        '''
        获取下一个配置的颜色
        '''
        self.set_next_specified_color()

        return self.get_current_color_hex()

                
           