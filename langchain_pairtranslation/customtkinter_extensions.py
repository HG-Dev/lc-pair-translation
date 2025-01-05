from typing import Any, Union, Optional, Tuple, Literal, Callable, List
from tkinter.constants import *
from customtkinter.windows.widgets.theme import ThemeManager
from customtkinter.windows.widgets.utility import check_kwargs_empty, pop_from_dict_by_set

from .chunking.base import DocumentChunk
from .rowinfo import RowCol
import customtkinter as ctk
import tkinter as tk
import re

class StaticTextbox(ctk.CTkBaseClass):

    # Overrides the original CTkTextbox constructor such that the scrollbars, and their visloop, are never created.
    def __init__(self,
                 master: Any,
                 content: Union[str, list[str]],
                 width: int = 0,
                 height: int = 0,
                 corner_radius: Optional[int] = None,
                 border_width: Optional[int] = None,
                 border_spacing: int = 3,

                 bg_color: Union[str, Tuple[str, str]] = "transparent",
                 fg_color: Optional[Union[str, Tuple[str, str]]] = None,
                 border_color: Optional[Union[str, Tuple[str, str]]] = None,
                 text_color: Optional[Union[str, str]] = None,

                 font: Optional[Union[tuple, ctk.CTkFont]] = None,
                 **kwargs):

        # transfer basic functionality (_bg_color, size, __appearance_mode, scaling) to CTkBaseClass
        super().__init__(master=master, bg_color=bg_color, width=width, height=height)

        # color
        self._fg_color = ThemeManager.theme["CTkTextbox"]["fg_color"] if fg_color is None else self._check_color_type(fg_color, transparency=True)
        self._border_color = ThemeManager.theme["CTkTextbox"]["border_color"] if border_color is None else self._check_color_type(border_color)
        self._text_color = ThemeManager.theme["CTkTextbox"]["text_color"] if text_color is None else self._check_color_type(text_color)

        # shape
        self._corner_radius = ThemeManager.theme["CTkTextbox"]["corner_radius"] if corner_radius is None else corner_radius
        self._border_width = ThemeManager.theme["CTkTextbox"]["border_width"] if border_width is None else border_width
        self._border_spacing = border_spacing

        # font
        self._font = ctk.CTkFont() if font is None else self._check_font_type(font)
        if isinstance(self._font, ctk.CTkFont):
            self._font.add_size_configure_callback(self._update_font)

        # Required for rounded edges
        self._canvas = ctk.CTkCanvas(master=self,
                                 highlightthickness=0,
                                 width=self._apply_widget_scaling(self._desired_width),
                                 height=self._apply_widget_scaling(self._desired_height))
        self._canvas.grid(row=0, column=0, sticky="nsew")
        self._canvas.configure(bg=self._apply_appearance_mode(self._bg_color))
        self._draw_engine = ctk.DrawEngine(self._canvas)

        self._textbox = tk.Text(self,
                            fg=self._apply_appearance_mode(self._text_color),
                            bg=self._apply_appearance_mode(self._border_color),
                            width=0,
                            height=0,
                            font=self._apply_font_scaling(self._font),
                            highlightthickness=0,
                            relief="flat",
                            spacing1=2,
                            #yscrollcommand=None, xscrollcommand=None, Doesn't stop scrolling!
                            insertbackground=self._apply_appearance_mode(self._text_color),
                            **pop_from_dict_by_set(kwargs, ctk.CTkTextbox._valid_tk_text_attributes))
        #print(self._textbox.bindtags())
    
        if isinstance(content, list):
            for line in content[0:-1]:
                assert('\n' not in line)
                self.insert(END, line + '\n')
        else:
            self.insert(END, content)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._textbox.grid(row=0, column=0, sticky=NSEW,
                            padx=(self._apply_widget_scaling(max(self._corner_radius, self._border_width + self._border_spacing)), 0),
                            pady=(self._apply_widget_scaling(max(self._corner_radius, self._border_width + self._border_spacing)), 0))

        check_kwargs_empty(kwargs, raise_error=True)
        self._draw()

    def count_display_lines(self, start: RowCol = RowCol.zero(), end: RowCol | Literal['end'] = END) -> int:
        """Counts the display lines, i.e. all lines including those created from text wrapping

        Args:
            start: A "row.column" string denoting where to start counting (see tkinter textbox implementation)
            end: A "row.column" string denotign where to stop counting. 'end' to stop at the very end

        Returns:
            The number of display lines found
        """
        end_str = str(end)
        if isinstance(end, RowCol):
            end_str = end.dot_str()
        result = self._textbox.count(f"{start.row}.{start.column}", end_str, "displaylines", return_ints=True) # type: ignore
        #print(f"Counting display lines in:\n{self._textbox.get(start, end).replace('\n', '&\n')}\nResult = {result}")
        assert(isinstance(result, int))
        return result

    def count_paragraphs(self, start: RowCol = RowCol.zero(), end: RowCol | Literal['end'] = END) -> int:
        """Counts the paragraph lines, i.e. instances of '\\n'

        Args:
            start: A "row.column" string denoting where to start counting (see tkinter textbox implementation)
            end: A "row.column" string denotign where to stop counting. 'end' to stop at the very end

        Returns:
            The number of paragraph lines found
        """
        end_str = str(end)
        if isinstance(end, RowCol):
            end_str = end.dot_str()
        result = self._textbox.count(f"{start.row}.{start.column}", end_str, "lines", return_ints=True) # type: ignore
        assert(isinstance(result, int))
        return result

    def _set_scaling(self, *args, **kwargs):
        super()._set_scaling(*args, **kwargs)
        self._textbox.configure(font=self._apply_font_scaling(self._font))
        self._canvas.configure(width=self._apply_widget_scaling(self._desired_width),
                               height=self._apply_widget_scaling(self._desired_height))
        self._draw(no_color_updates=True)

    def _set_dimensions(self, width=None, height=None):
        super()._set_dimensions(width, height)

        self._canvas.configure(width=self._apply_widget_scaling(self._desired_width),
                               height=self._apply_widget_scaling(self._desired_height))
        self._draw()

    def _update_font(self):
        """ pass font to tkinter widgets with applied font scaling and update grid with workaround """
        self._textbox.configure(font=self._apply_font_scaling(self._font))

        # Workaround to force grid to be resized when text changes size.
        # Otherwise grid will lag and only resizes if other mouse action occurs.
        self._canvas.grid_forget()
        self._canvas.grid(row=0, column=0, sticky="nsew")

    def destroy(self):
        if isinstance(self._font, ctk.CTkFont):
            self._font.remove_size_configure_callback(self._update_font)

        super().destroy()

    def _draw(self, no_color_updates=False):
        super()._draw(no_color_updates)

        if not self._canvas.winfo_exists():
            return

        requires_recoloring = self._draw_engine.draw_rounded_rect_with_border(self._apply_widget_scaling(self._current_width),
                                                                              self._apply_widget_scaling(self._current_height),
                                                                              self._apply_widget_scaling(self._corner_radius),
                                                                              self._apply_widget_scaling(self._border_width))

        if no_color_updates is False or requires_recoloring:
            if self._fg_color == "transparent":
                self._canvas.itemconfig("inner_parts",
                                        fill=self._apply_appearance_mode(self._bg_color),
                                        outline=self._apply_appearance_mode(self._bg_color))
                self._textbox.configure(fg=self._apply_appearance_mode(self._text_color),
                                        bg=self._apply_appearance_mode(self._bg_color),
                                        insertbackground=self._apply_appearance_mode(self._text_color))
            else:
                self._canvas.itemconfig("inner_parts",
                                        fill=self._apply_appearance_mode(self._fg_color),
                                        outline=self._apply_appearance_mode(self._fg_color))
                self._textbox.configure(fg=self._apply_appearance_mode(self._text_color),
                                        bg=self._apply_appearance_mode(self._fg_color),
                                        insertbackground=self._apply_appearance_mode(self._text_color))

            self._canvas.itemconfig("border_parts",
                                    fill=self._apply_appearance_mode(self._border_color),
                                    outline=self._apply_appearance_mode(self._border_color))
            self._canvas.configure(bg=self._apply_appearance_mode(self._bg_color))

        self._canvas.tag_lower("inner_parts")
        self._canvas.tag_lower("border_parts")

    def configure(self, require_redraw=False, **kwargs):
        if "fg_color" in kwargs:
            self._fg_color = self._check_color_type(kwargs.pop("fg_color"), transparency=True)
            require_redraw = True

            # check if CTk widgets are children of the frame and change their _bg_color to new frame fg_color
            for child in self.winfo_children():
                if isinstance(child, ctk.CTkBaseClass) and hasattr(child, "_fg_color"):
                    child.configure(bg_color=self._fg_color)

        if "border_color" in kwargs:
            self._border_color = self._check_color_type(kwargs.pop("border_color"))
            require_redraw = True

        if "text_color" in kwargs:
            self._text_color = self._check_color_type(kwargs.pop("text_color"))
            require_redraw = True

        if "corner_radius" in kwargs:
            self._corner_radius = kwargs.pop("corner_radius")
            self._create_grid_for_text_and_scrollbars(re_grid_textbox=True, re_grid_x_scrollbar=True, re_grid_y_scrollbar=True)
            require_redraw = True

        if "border_width" in kwargs:
            self._border_width = kwargs.pop("border_width")
            self._create_grid_for_text_and_scrollbars(re_grid_textbox=True, re_grid_x_scrollbar=True, re_grid_y_scrollbar=True)
            require_redraw = True

        if "border_spacing" in kwargs:
            self._border_spacing = kwargs.pop("border_spacing")
            self._create_grid_for_text_and_scrollbars(re_grid_textbox=True, re_grid_x_scrollbar=True, re_grid_y_scrollbar=True)
            require_redraw = True

        if "font" in kwargs:
            if isinstance(self._font, ctk.CTkFont):
                self._font.remove_size_configure_callback(self._update_font)
            self._font = self._check_font_type(kwargs.pop("font"))
            if isinstance(self._font, ctk.CTkFont):
                self._font.add_size_configure_callback(self._update_font)

            self._update_font()

        self._textbox.configure(**pop_from_dict_by_set(kwargs, self._valid_tk_text_attributes))
        super().configure(require_redraw=require_redraw, **kwargs)

    def cget(self, attribute_name: str) -> Any:
        if attribute_name == "corner_radius":
            return self._corner_radius
        elif attribute_name == "border_width":
            return self._border_width
        elif attribute_name == "border_spacing":
            return self._border_spacing

        elif attribute_name == "fg_color":
            return self._fg_color
        elif attribute_name == "border_color":
            return self._border_color
        elif attribute_name == "text_color":
            return self._text_color

        elif attribute_name == "font":
            return self._font

        else:
            return super().cget(attribute_name)

    def bind(self, sequence: str = "", command: Optional[Callable] = None, add: Union[str, bool] = True):
        """ called on the tkinter.Canvas """
        if not (add == "+" or add is True):
            raise ValueError("'add' argument can only be '+' or True to preserve internal callbacks")
        print(sequence)

    def unbind(self, sequence: str = "", funcid: Optional[str] = None):
        """ called on the tkinter.Label and tkinter.Canvas """
        pass

    def focus(self):
        return self._textbox.focus()

    def focus_set(self):
        return self._textbox.focus_set()

    def focus_force(self):
        return self._textbox.focus_force()

    def insert(self, index, text, tags=None):
        #self._textbox.configure(state=NORMAL) Doesn't stop scrolling!
        self._textbox.insert(index, text, tags)
        #self._textbox.configure(state=DISABLED)    

    def get(self, index1, index2=None):
        return self._textbox.get(index1, index2)

    def bbox(self, index):
        return self._textbox.bbox(index)

    def compare(self, index, op, index2):
        return self._textbox.compare(index, op, index2)

    def delete(self, index1, index2=None):
        return self._textbox.delete(index1, index2)

    def dlineinfo(self, index):
        return self._textbox.dlineinfo(index)

    def index(self, i):
        return self._textbox.index(i)

    def search(self, pattern, index, *args, **kwargs):
        return self._textbox.search(pattern, index, *args, **kwargs)

    def xview(self, *args):
        return self._textbox.xview(*args)

    def yview(self, *args):
        return self._textbox.yview(*args)
    
class ChunkFrame(ctk.CTkFrame):
    # TODO: Static lazy properties can be made with metaclass
    # https://stackoverflow.com/questions/15226721/python-class-member-lazy-initialization
    @property
    def label_font(self) -> ctk.CTkFont:
        return ctk.CTkFont('RobotoMono-Regular', 12)
    
    fontsize = ThemeManager.theme["CTkFont"]["size"]
    status_colors = ["red", "blue", "cyan", "green"]

    def __init__(self, master, chunk: Any):
        super().__init__(master)
        self.grid_columnconfigure(0, weight=0, minsize=32)
        self.grid_columnconfigure(1, weight=1, minsize=550)
        self.grid_columnconfigure(2, weight=1, minsize=550)
        self.pack(side=TOP, pady=6)

        try:
            assert(chunk.is_src_set)
        except AssertionError:
            print("Chunk recieved by ChunkFrame is missing its src link!")
            return
        
        start = chunk.start_rowcol
        total_rows = chunk.ref_paragraph_count + 2

        self.src_textbox = StaticTextbox(self, '\n'.join(chunk.src_text_substrings), height=0)
        self.edit_textbox = ctk.CTkTextbox(self, maxundo=50, height=0)
        
        start_offset_item = tk.Frame(self, width=1, height=7, bg=self._apply_appearance_mode(self._bg_color))
        start_offset_item.grid(column=0, row=0)
        
        self.row_labels: List[ctk.CTkLabel] = []
        for row, paragraph in enumerate(chunk.src_text_substrings):
            rownum_string = str(row + start.row)
            height = self._calculate_row_height(self.fontsize, paragraph.count('\n') + 1, 5)
            rownum_label = ctk.CTkLabel(self, text=rownum_string, font=self.label_font, 
                                        justify=RIGHT, anchor=NE, height=height,
                                        text_color=self._apply_appearance_mode(self._border_color))
            rownum_label.grid(column = 0, row = row+1, sticky=E)
            self.row_labels.append(rownum_label)

        end_offset_item = tk.Frame(self, width=0, height=24, bg=self._apply_appearance_mode(self._bg_color))
        end_offset_item.grid(column=0, row=total_rows-1)

        self.src_textbox.grid(column=1, row=0, rowspan=total_rows, sticky=NSEW, padx=4)
        self.edit_textbox.grid(column=2, row=0, rowspan=total_rows, sticky=NSEW, padx=8)
        self.edit_textbox.insert(END, "<initializing>")

        self.status_badge = ctk.CTkFrame(self, width=20, height=20, fg_color=self.status_colors[0])
        self.status_badge.grid(column=2, row=1, sticky=NE)
        self.after(75, self.apply_wrapping_to_height)
        self.after(100, self._reset_edit_textbox_content)

    def _reset_edit_textbox_content(self):
        self.edit_textbox.delete("0.0", END)
        self.edit_textbox.insert(END, "<untranslated>")

    @staticmethod
    def _calculate_row_height(font_size: int, display_lines: int = 1, extra_space: int = 4):
        #(f"Space calculation: {font_size} * ({display_lines} + {extra_space}) = {display_lines * (font_size + extra_space)}")
        return display_lines * (font_size + extra_space)

    def apply_wrapping_to_height(self):
        ''' Increase height where necessary by expanding each label where a line wraps '''
        #print(f"Counting wraps within:\n" + self.src_textbox.get("0.0", END))
        #(len(self.row_labels), "exist.")
        for row, label in enumerate(self.row_labels):
            wrap_returns = self.src_textbox.count_display_lines(RowCol.create(row+1, 1), RowCol.create(row+2, 1))
            if wrap_returns > 1:
                oldheight = label.cget('height')
                height = self._calculate_row_height(self.fontsize, wrap_returns) - max(0, (wrap_returns - 1) * 0.5)
                #(f"Label '{row}': '{oldheight}' grew to '{height}'")
                label.configure(require_redraw=True, height=height)

class ChunkedTranslationFrame(ctk.CTkScrollableFrame):
    
    # Chunk text, start in original document, end in original document
    # TODO: These are static! Move them into __init__
    _chunks: list[Any] = []
    _is_updating: bool = False
    _chunk_frames: list[ChunkFrame] = []            

    _addsrc_textbox_list: list[ctk.CTkTextbox] = []
    _src_textbox_list: list[ctk.CTkTextbox] = []
    _out_textbox_list: list[ctk.CTkTextbox] = []
    _out_trailing_whitespace_list: list[str] = []

    @property
    def chunk_count(self):
        return len(self._chunks)
           
    def __init__(self, master, 
                 alt_bg_color: Union[str, Tuple[str, str]] = "transparent",
                 **kwargs):
        super().__init__(master, **kwargs)
        self._alt_bg_color = alt_bg_color  
        
    # def get_source_text(self, row: int) -> str:
    #     return self._src_textbox_list[row].get('0.0', END)
    
    # def get_translation_text(self, row: int) -> str:
    #     return self._out_textbox_list[row].get('0.0', END)
    
    def _clean_chunk_text(text: str) -> str:
        # Replace line separator, paragraph separator, non-breaking space
        cleaned = re.sub(r'\u2028|\u2029|\u00A0', ' ', text)
        cleaned = cleaned.rstrip()        
        return cleaned
    
    def _add_chunk_loop_internal(self):
        next_chunk_idx = len(self._chunk_frames)
        assert(len(self._chunks) > next_chunk_idx)
        chunk = self._chunks[next_chunk_idx]
        frame = ChunkFrame(self, chunk)

        self._chunk_frames.append(frame)
        if len(self._chunks) == len(self._chunk_frames):
            return #finished
        assert(len(self._chunks) > len(self._chunk_frames))
        self.after(100, self._add_chunk_loop_internal)

    def add_chunk(self, chunk: Any):
        self._chunks.append(chunk)

        if not self._is_updating:
            self._is_updating = True
            self.after(50, self._add_chunk_loop_internal)