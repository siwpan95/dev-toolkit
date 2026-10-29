"""
人机验证 - View 层 (Canvas)
使用 tkinter Canvas 绘制各类验证码界面
"""
import math
import random
import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional, Tuple

from model.captcha_model import CaptchaState, CaptchaResult
from viewmodel.captcha_viewmodel import (
    BaseCaptchaViewModel, TextCaptchaViewModel, SliderCaptchaViewModel,
    PuzzleCaptchaViewModel, ClickCaptchaViewModel, RotateCaptchaViewModel,
    DragSortCaptchaViewModel,
    WordOrderCaptchaViewModel, DifferenceClickCaptchaViewModel, NineGridCaptchaViewModel,
    SMSCaptchaViewModel, ScratchCardCaptchaViewModel, AreaClickCaptchaViewModel,
    VoiceCaptchaViewModel, FontRecognizeCaptchaViewModel, BehaviorMockCaptchaViewModel
)


class BaseCaptchaView:
    """验证码视图基类"""
    
    def __init__(self, parent: tk.Widget, viewmodel: BaseCaptchaViewModel, width: int = 400, height: int = 300):
        self.parent = parent
        self.viewmodel = viewmodel
        self.width = width
        self.height = height
        self.canvas: Optional[tk.Canvas] = None
        self.result_label: Optional[tk.Label] = None
        self._build_ui()
    
    def _build_ui(self):
        """构建UI - 子类可重写"""
        self.frame = ttk.Frame(self.parent)
        
        # Canvas 区域
        self.canvas = tk.Canvas(
            self.frame, width=self.width, height=self.height,
            bg='#ffffff', highlightthickness=1, highlightbackground='#ddd'
        )
        self.canvas.pack(pady=10)
        
        # 结果提示
        self.result_label = tk.Label(
            self.frame, text="", font=('微软雅黑', 12),
            fg='#666'
        )
        self.result_label.pack(pady=5)
        
        # 绑定回调
        self.viewmodel.set_callbacks(self._on_state_change, self._on_result)
    
    def _on_state_change(self):
        self.draw()
    
    def _on_result(self, result: CaptchaResult):
        if result.success:
            self.result_label.config(text=result.message, fg='#4CAF50')
        else:
            self.result_label.config(text=result.message, fg='#f44336')
    
    def draw(self):
        """绘制验证码 - 子类必须实现"""
        raise NotImplementedError
    
    def reset(self):
        """重置"""
        self.viewmodel.reset()
        self.result_label.config(text="", fg='#666')
    
    def pack(self, **kwargs):
        self.frame.pack(**kwargs)
    
    def grid(self, **kwargs):
        self.frame.grid(**kwargs)


class TextCaptchaView(BaseCaptchaView):
    """文字验证码视图"""
    
    def __init__(self, parent: tk.Widget, viewmodel: TextCaptchaViewModel, width: int = 320, height: int = 120):
        self.vm: TextCaptchaViewModel = viewmodel
        super().__init__(parent, viewmodel, width, height)
    
    def _build_ui(self):
        super()._build_ui()
        
        # 输入框
        input_frame = ttk.Frame(self.frame)
        input_frame.pack(pady=5)
        
        tk.Label(input_frame, text="请输入验证码:", font=('微软雅黑', 11)).pack(side=tk.LEFT, padx=5)
        self.entry = tk.Entry(input_frame, font=('微软雅黑', 14), width=12, justify='center')
        self.entry.pack(side=tk.LEFT, padx=5)
        
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(pady=5)
        
        ttk.Button(btn_frame, text="验证", command=self._verify).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="刷新", command=self.reset).pack(side=tk.LEFT, padx=5)
        
        self.entry.bind('<Return>', lambda e: self._verify())
        
        self.draw()
    
    def draw(self):
        self.canvas.delete('all')
        
        data = self.vm.model.text_data
        if data is None:
            return
        
        cfg = self.vm.config.get('text_captcha', {})
        content_w = cfg.get('width', 280)
        content_h = cfg.get('height', 100)
        
        # Canvas填满背景
        self.canvas.create_rectangle(0, 0, self.width, self.height, fill=data.bg_color, outline='#ddd')
        
        # 计算居中偏移
        offset_x = (self.width - content_w) / 2
        offset_y = (self.height - content_h) / 2
        
        # 噪点
        for x, y in data.noise_dots:
            self.canvas.create_oval(offset_x + x-1, offset_y + y-1, offset_x + x+1, offset_y + y+1, fill='#999', outline='')
        
        # 干扰线
        for x1, y1, x2, y2 in data.noise_lines:
            self.canvas.create_line(offset_x + x1, offset_y + y1, offset_x + x2, offset_y + y2, fill='#bbb', width=1)
        
        # 字符
        for i, (x, y, size, color) in enumerate(data.char_positions):
            offset_y2 = (y - content_h/2) * 0.3
            self.canvas.create_text(
                offset_x + x, offset_y + y + offset_y2, text=data.code[i],
                font=('Arial', size, 'bold'), fill=color,
                angle=random.uniform(-20, 20)
            )
    
    def _verify(self):
        user_input = self.entry.get().strip()
        if user_input:
            self.vm.verify(user_input)
            self.entry.delete(0, tk.END)
    
    def reset(self):
        super().reset()
        self.entry.delete(0, tk.END)


class SliderCaptchaView(BaseCaptchaView):
    """滑块验证码视图（缺口+拼图块模式）"""
    
    def __init__(self, parent: tk.Widget, viewmodel: SliderCaptchaViewModel, width: int = 350, height: int = 320):
        self.vm: SliderCaptchaViewModel = viewmodel
        super().__init__(parent, viewmodel, width, height)
    
    def _build_ui(self):
        super()._build_ui()
        
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="刷新", command=self.reset).pack(side=tk.LEFT, padx=5)
        
        # 绑定鼠标事件
        self.canvas.bind('<Button-1>', self._on_press)
        self.canvas.bind('<B1-Motion>', self._on_drag)
        self.canvas.bind('<ButtonRelease-1>', self._on_release)
        
        self.draw()
    
    def draw(self):
        self.canvas.delete('all')
        
        data = self.vm.model.slider_data
        if data is None:
            return
        
        cfg = self.vm.config.get('slider_captcha', {})
        cw = cfg.get('width', 320)
        ch = cfg.get('height', 180)
        img_x = 10
        img_y = 10
        
        state = self.vm.get_state()
        
        # ========== 上方图片区域 ==========
        # 底色
        self.canvas.create_rectangle(img_x, img_y, img_x + cw, img_y + ch, fill='#f8f9fa', outline='#ccc', width=1)
        
        # 缺口位置
        gap_x = img_x + data.target_x
        gap_y = img_y + data.gap_y
        pw = data.piece_width
        ph = data.piece_height
        
        # 绘制背景条纹（跳过缺口区域，因为缺口是"挖掉"的）
        for stripe in data.stripes:
            sy = img_y + stripe['y']
            sh = stripe['height']
            # 缺口在条纹中间时，分段绘制背景
            if sy + sh <= gap_y or sy >= gap_y + ph:
                # 完全在缺口上方或下方
                self.canvas.create_rectangle(img_x, sy, img_x + cw, sy + sh, fill=stripe['color'], outline='')
            elif sy < gap_y and sy + sh > gap_y + ph:
                # 跨越整个缺口，分三段
                self.canvas.create_rectangle(img_x, sy, gap_x, gap_y, fill=stripe['color'], outline='')
                self.canvas.create_rectangle(gap_x + pw, sy, img_x + cw, gap_y, fill=stripe['color'], outline='')
                self.canvas.create_rectangle(img_x, gap_y + ph, img_x + cw, sy + sh, fill=stripe['color'], outline='')
            elif sy < gap_y < sy + sh <= gap_y + ph:
                # 上半部分在缺口上方
                self.canvas.create_rectangle(img_x, sy, gap_x, gap_y, fill=stripe['color'], outline='')
                self.canvas.create_rectangle(gap_x + pw, sy, img_x + cw, gap_y, fill=stripe['color'], outline='')
            elif gap_y <= sy < gap_y + ph < sy + sh:
                # 下半部分在缺口下方
                self.canvas.create_rectangle(img_x, gap_y + ph, img_x + cw, sy + sh, fill=stripe['color'], outline='')
            # 完全在缺口区域内，不绘制背景
        
        # 缺口：白色填充 + 虚线边框 + "?"提示
        if state == CaptchaState.SUCCESS:
            self.canvas.create_rectangle(gap_x, gap_y, gap_x + pw, gap_y + ph,
                                         outline='#4CAF50', width=3)
        else:
            self.canvas.create_rectangle(gap_x, gap_y, gap_x + pw, gap_y + ph,
                                         fill='white', outline='#bbb', width=2, dash=(5, 3))
            self.canvas.create_text(gap_x + pw/2, gap_y + ph/2,
                                    text='?', font=('Arial', 22, 'bold'), fill='#ccc')
        
        # 图片区域边框
        self.canvas.create_rectangle(img_x, img_y, img_x + cw, img_y + ch, outline='#ccc', width=1)
        
        # ========== 拼图块（在图片区域内，可移动）==========
        piece_x = img_x + data.piece_x
        piece_y = img_y + data.gap_y  # 和缺口同一高度
        
        if state == CaptchaState.SUCCESS:
            piece_border = '#4CAF50'
            shadow_color = '#aaaaaa'
        elif state == CaptchaState.FAILED:
            piece_border = '#f44336'
            shadow_color = '#aaaaaa'
        else:
            piece_border = '#1565C0'
            shadow_color = '#888888'
        
        # 拼图块阴影（向右下偏移）
        if state != CaptchaState.SUCCESS:
            self.canvas.create_rectangle(piece_x + 2, piece_y + 2, piece_x + pw + 2, piece_y + ph + 2,
                                         fill=shadow_color, outline='')
        
        # 拼图块上白边（高光）
        self.canvas.create_rectangle(piece_x, piece_y, piece_x + pw, piece_y + 2, fill='white', outline='')
        self.canvas.create_rectangle(piece_x, piece_y, piece_x + 2, piece_y + ph, fill='white', outline='')
        
        # 拼图块主体（绘制对应位置的条纹）
        for stripe in data.stripes:
            rel_y = stripe['y']
            rel_h = stripe['height']
            sy = piece_y + rel_y
            sh = rel_h
            # 只绘制在拼图块范围内的条纹
            if sy < piece_y + ph and sy + sh > piece_y:
                clip_top = max(sy, piece_y)
                clip_bottom = min(sy + sh, piece_y + ph)
                self.canvas.create_rectangle(piece_x + 2, clip_top, piece_x + pw - 2, clip_bottom,
                                             fill=stripe['color'], outline='')
        
        # 拼图块边框
        self.canvas.create_rectangle(piece_x, piece_y, piece_x + pw, piece_y + ph,
                                     outline=piece_border, width=2)
        
        # 拼图块下暗边
        self.canvas.create_rectangle(piece_x + 2, piece_y + ph - 3, piece_x + pw, piece_y + ph,
                                     fill=shadow_color, outline='')
        # 拼图块右暗边
        self.canvas.create_rectangle(piece_x + pw - 3, piece_y + 2, piece_x + pw, piece_y + ph,
                                     fill=shadow_color, outline='')
        
        # ========== 下方滑轨 ==========
        track_y = img_y + ch + 20
        track_h = 50
        self.canvas.create_rectangle(img_x, track_y, img_x + cw, track_y + track_h,
                                     fill='#e8e8e8', outline='#bbb', width=1)
        
        # 滑轨刻度
        for i in range(0, cw + 1, 20):
            self.canvas.create_line(img_x + i, track_y, img_x + i, track_y + 5, fill='#ccc')
        
        # 提示文字
        if state == CaptchaState.IDLE:
            self.canvas.create_text(img_x + cw/2 + 35, track_y + track_h/2,
                                    text='→ 拖动滑块填补缺口', font=('微软雅黑', 11), fill='#888')
        
        # ========== 滑块手柄 ==========
        slider_x = img_x + data.slider_x
        sw = 40  # 滑块手柄宽度
        sh = track_h - 6
        
        if state == CaptchaState.SUCCESS:
            slider_fill = '#4CAF50'
            slider_border = '#388E3C'
        elif state == CaptchaState.FAILED:
            slider_fill = '#f44336'
            slider_border = '#d32f2f'
        else:
            slider_fill = '#2196F3'
            slider_border = '#1565C0'
        
        # 阴影
        if state != CaptchaState.SUCCESS:
            self.canvas.create_rectangle(slider_x + 3, track_y + 5, slider_x + sw + 3, track_y + sh + 5,
                                         fill='#999', outline='')
        
        # 3D主体
        self.canvas.create_rectangle(slider_x, track_y + 2, slider_x + sw, track_y + sh + 2,
                                     fill=slider_fill, outline=slider_border, width=2)
        
        # 滑块中央竖线（拖拽把手）
        hx = slider_x + sw / 2
        self.canvas.create_rectangle(hx - 2, track_y + 8, hx + 2, track_y + sh - 4,
                                     fill='white', outline='')
        self.canvas.create_rectangle(hx - 6, track_y + 12, hx - 3, track_y + sh - 8,
                                     fill='white', outline='')
        self.canvas.create_rectangle(hx + 3, track_y + 12, hx + 6, track_y + sh - 8,
                                     fill='white', outline='')
        
        # 成功/失败边框
        if state == CaptchaState.SUCCESS:
            self.canvas.create_rectangle(img_x, img_y, img_x + cw, img_y + ch, outline='#4CAF50', width=3)
        elif state == CaptchaState.FAILED:
            self.canvas.create_rectangle(img_x, img_y, img_x + cw, img_y + ch, outline='#f44336', width=3)
    
    def _on_press(self, event):
        data = self.vm.model.slider_data
        if data is None or self.vm.get_state() == CaptchaState.SUCCESS:
            return
        
        cfg = self.vm.config.get('slider_captcha', {})
        ch = cfg.get('height', 180)
        track_y = 10 + ch + 20
        track_h = 50
        
        # 检查是否点在滑块上
        slider_x = 10 + data.slider_x
        sw = 40
        if (slider_x <= event.x <= slider_x + sw and
            track_y <= event.y <= track_y + track_h):
            self.vm.start_drag(event.x)
    
    def _on_drag(self, event):
        data = self.vm.model.slider_data
        if data is None:
            return
        self.vm.drag(event.x)
    
    def _on_release(self, event):
        self.vm.end_drag()


class PuzzleCaptchaView(BaseCaptchaView):
    """拼图验证码视图（数字华容道）"""
    
    def __init__(self, parent: tk.Widget, viewmodel: PuzzleCaptchaViewModel, width: int = 220, height: int = 220):
        self.vm: PuzzleCaptchaViewModel = viewmodel
        super().__init__(parent, viewmodel, width, height)
    
    def _build_ui(self):
        super()._build_ui()
        
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="刷新", command=self.reset).pack(side=tk.LEFT, padx=5)
        
        # 提示标签
        self.hint_label = tk.Label(
            self.frame, text="点击与空白相邻的数字块进行滑动",
            font=('微软雅黑', 10), fg='#888'
        )
        self.hint_label.pack(pady=2)
        
        # 绑定点击事件
        self.canvas.bind('<Button-1>', self._on_click)
        
        self.draw()
    
    def draw(self):
        self.canvas.delete('all')
        
        data = self.vm.model.puzzle_data
        if data is None:
            return
        
        piece_size = data.piece_size
        grid_size = data.grid_size
        grid_w = piece_size * grid_size
        grid_h = piece_size * grid_size
        
        offset_x = (self.width - grid_w) // 2
        offset_y = (self.height - grid_h) // 2
        
        state = self.vm.get_state()
        
        # 外框背景
        self.canvas.create_rectangle(offset_x - 3, offset_y - 3, offset_x + grid_w + 3, offset_y + grid_h + 3,
                                     fill='#ccc', outline='')
        
        # 绘制每个块
        for idx in range(grid_size * grid_size):
            row, col = divmod(idx, grid_size)
            x = offset_x + col * piece_size
            y = offset_y + row * piece_size
            value = data.grid[idx]
            
            if value == 0:
                # 空白格
                self.canvas.create_rectangle(x + 1, y + 1, x + piece_size - 1, y + piece_size - 1,
                                             fill='#e0e0e0', outline='#bbb', width=1)
            else:
                # 数字块 - 3D效果
                color_idx = (value - 1) % len(data.colors)
                color = data.colors[color_idx]
                
                # 上白边（高光）
                self.canvas.create_rectangle(x + 1, y + 1, x + piece_size - 1, y + 3, fill='white', outline='')
                # 左白边（高光）
                self.canvas.create_rectangle(x + 1, y + 1, x + 3, y + piece_size - 1, fill='white', outline='')
                # 主体
                self.canvas.create_rectangle(x + 2, y + 2, x + piece_size - 2, y + piece_size - 2,
                                             fill=color, outline='white', width=1)
                # 下暗边
                self.canvas.create_rectangle(x + 2, y + piece_size - 4, x + piece_size - 2, y + piece_size - 2,
                                             fill='#999999', outline='')
                # 右暗边
                self.canvas.create_rectangle(x + piece_size - 4, y + 2, x + piece_size - 2, y + piece_size - 2,
                                             fill='#999999', outline='')
                
                # 数字
                self.canvas.create_text(x + piece_size/2, y + piece_size/2,
                                        text=str(value), font=('Arial', 22, 'bold'), fill='white')
        
        # 成功/失败状态
        if state == CaptchaState.SUCCESS:
            self.canvas.create_rectangle(offset_x - 3, offset_y - 3, offset_x + grid_w + 3, offset_y + grid_h + 3,
                                         outline='#4CAF50', width=4)
        elif state == CaptchaState.FAILED:
            self.canvas.create_rectangle(offset_x - 3, offset_y - 3, offset_x + grid_w + 3, offset_y + grid_h + 3,
                                         outline='#f44336', width=4)
    
    def _on_click(self, event):
        data = self.vm.model.puzzle_data
        if data is None:
            return
        
        piece_size = data.piece_size
        grid_size = data.grid_size
        grid_w = piece_size * grid_size
        grid_h = piece_size * grid_size
        
        offset_x = (self.width - grid_w) // 2
        offset_y = (self.height - grid_h) // 2
        
        if offset_x <= event.x <= offset_x + grid_w and offset_y <= event.y <= offset_y + grid_h:
            col = int((event.x - offset_x) // piece_size)
            row = int((event.y - offset_y) // piece_size)
            idx = row * grid_size + col
            self.vm.click(idx)


class ClickCaptchaView(BaseCaptchaView):
    """点击验证码视图"""
    
    def __init__(self, parent: tk.Widget, viewmodel: ClickCaptchaViewModel, width: int = 400, height: int = 350):
        self.vm: ClickCaptchaViewModel = viewmodel
        super().__init__(parent, viewmodel, width, height)
    
    def _build_ui(self):
        super()._build_ui()
        
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="刷新", command=self.reset).pack(side=tk.LEFT, padx=5)
        
        # 目标提示
        self.target_label = tk.Label(
            self.frame, text="", font=('微软雅黑', 12, 'bold'),
            fg='#2196F3'
        )
        self.target_label.pack(pady=2)
        
        # 绑定点击事件
        self.canvas.bind('<Button-1>', self._on_click)
        
        self.draw()
    
    def draw(self):
        self.canvas.delete('all')
        
        data = self.vm.model.click_data
        if data is None:
            return
        
        cfg = self.vm.config.get('click_captcha', {})
        cw = cfg.get('width', 320)
        ch = cfg.get('height', 220)
        bg_color = cfg.get('bg_color', '#ffffff')
        highlight = cfg.get('highlight_color', '#FFD700')
        
        state = self.vm.get_state()
        
        # 背景
        self.canvas.create_rectangle(0, 0, cw, ch, fill=bg_color, outline='#ddd')
        
        # 绘制干扰元素
        random.seed(123)
        for _ in range(3):
            x1 = random.uniform(0, cw)
            y1 = random.uniform(0, ch)
            x2 = random.uniform(0, cw)
            y2 = random.uniform(0, ch)
            self.canvas.create_line(x1, y1, x2, y2, fill='#f0f0f0', width=2)
        random.seed()
        
        # 绘制字符
        for item in data.items:
            x, y = item['x'], item['y']
            size = item['size']
            color = item['color']
            
            if item['clicked']:
                # 已点击标记
                self.canvas.create_oval(
                    x - size, y - size, x + size, y + size,
                    outline=highlight, width=3
                )
                self.canvas.create_text(
                    x, y, text=item['char'],
                    font=('微软雅黑', size, 'bold'), fill=highlight
                )
                # 顺序标记
                order = item['target_order'] + 1
                self.canvas.create_oval(
                    x + size - 5, y - size - 5, x + size + 10, y - size + 10,
                    fill=highlight, outline=''
                )
                self.canvas.create_text(
                    x + size + 2, y - size + 2, text=str(order),
                    font=('Arial', 10, 'bold'), fill='white'
                )
            else:
                self.canvas.create_text(
                    x, y, text=item['char'],
                    font=('微软雅黑', size, 'bold'), fill=color
                )
        
        # 更新目标提示
        if state == CaptchaState.SUCCESS:
            self.target_label.config(text="✓ 验证成功！", fg='#4CAF50')
        elif state == CaptchaState.FAILED:
            self.target_label.config(text="✗ 验证失败", fg='#f44336')
        else:
            targets = data.targets[data.current_target_index:]
            if targets:
                self.target_label.config(
                    text=f"请按顺序点击：{' → '.join(targets)}", fg='#2196F3'
                )
            else:
                self.target_label.config(text="", fg='#2196F3')
    
    def _on_click(self, event):
        self.vm.click(event.x, event.y)
    
    def reset(self):
        super().reset()
        self.target_label.config(text="", fg='#2196F3')


class RotateCaptchaView(BaseCaptchaView):
    """旋转验证码视图"""
    
    def __init__(self, parent: tk.Widget, viewmodel: RotateCaptchaViewModel, width: int = 400, height: int = 380):
        self.vm: RotateCaptchaViewModel = viewmodel
        super().__init__(parent, viewmodel, width, height)
    
    def _build_ui(self):
        super()._build_ui()
        
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="验证", command=self._verify).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="刷新", command=self.reset).pack(side=tk.LEFT, padx=5)
        
        # 提示
        self.hint_label = tk.Label(
            self.frame, text="拖动外圈旋转图片至正确方向",
            font=('微软雅黑', 10), fg='#888'
        )
        self.hint_label.pack(pady=2)
        
        # 绑定事件
        self.canvas.bind('<Button-1>', self._on_press)
        self.canvas.bind('<B1-Motion>', self._on_drag)
        self.canvas.bind('<ButtonRelease-1>', self._on_release)
        
        self.draw()
    
    def draw(self):
        self.canvas.delete('all')
        
        data = self.vm.model.rotate_data
        if data is None:
            return
        
        cfg = self.vm.config.get('rotate_captcha', {})
        cw = cfg.get('width', 280)
        ch = cfg.get('height', 280)
        bg_color = cfg.get('bg_color', '#f8f9fa')
        ring_color = cfg.get('ring_color', '#dee2e6')
        handle_color = cfg.get('handle_color', '#2196F3')
        
        state = self.vm.get_state()
        cx, cy = cw / 2, ch / 2
        image_r = cfg.get('image_size', 200) / 2
        ring_r = image_r + 15
        
        self.vm.set_geometry((cx, cy), ring_r)
        
        # 背景
        self.canvas.create_rectangle(0, 0, cw, ch, fill=bg_color, outline='')
        
        # 外圈环
        self.canvas.create_oval(
            cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r,
            outline=ring_color, width=8
        )
        
        # 刻度线
        for i in range(12):
            angle = math.radians(i * 30)
            r1 = ring_r - 5
            r2 = ring_r + 5
            self.canvas.create_line(
                cx + r1 * math.cos(angle), cy + r1 * math.sin(angle),
                cx + r2 * math.cos(angle), cy + r2 * math.sin(angle),
                fill='#bbb', width=2
            )
        
        # 旋转手柄
        handle_angle = math.radians(data.current_angle)
        hx = cx + ring_r * math.cos(handle_angle)
        hy = cy + ring_r * math.sin(handle_angle)
        self.canvas.create_oval(
            hx - 10, hy - 10, hx + 10, hy + 10,
            fill=handle_color, outline='white', width=2
        )
        
        # 绘制旋转的图案
        angle_rad = math.radians(data.current_angle)
        
        # 根据类型绘制不同图案
        if data.image_type == 'arrow':
            self._draw_arrow(cx, cy, image_r, angle_rad)
        elif data.image_type == 'square':
            self._draw_square(cx, cy, image_r, angle_rad)
        elif data.image_type == 'triangle':
            self._draw_triangle(cx, cy, image_r, angle_rad)
        else:
            self._draw_cross(cx, cy, image_r, angle_rad)
        
        # 中心点
        self.canvas.create_oval(cx - 4, cy - 4, cx + 4, cy + 4, fill='#666', outline='')
        
        # 顶部指示器（正上方为目标方向）
        self.canvas.create_polygon(
            cx, cy - ring_r - 20,
            cx - 8, cy - ring_r - 5,
            cx + 8, cy - ring_r - 5,
            fill='#f44336', outline=''
        )
        
        # 成功/失败状态
        if state == CaptchaState.SUCCESS:
            self.canvas.create_oval(
                cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r,
                outline='#4CAF50', width=4
            )
        elif state == CaptchaState.FAILED:
            self.canvas.create_oval(
                cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r,
                outline='#f44336', width=4
            )
    
    def _draw_arrow(self, cx, cy, r, angle):
        pts = []
        # 箭头朝向 angle 方向
        for i, (dx, dy) in enumerate([(0, -1), (0.5, 0.5), (-0.5, 0.5)]):
            px = cx + r * (dx * math.cos(angle) - dy * math.sin(angle))
            py = cy + r * (dx * math.sin(angle) + dy * math.cos(angle))
            pts.extend([px, py])
        self.canvas.create_polygon(pts, fill='#3498db', outline='#2980b9', width=2)
    
    def _draw_square(self, cx, cy, r, angle):
        pts = []
        for i in range(4):
            a = angle + math.radians(i * 90 + 45)
            px = cx + r * 0.7 * math.cos(a)
            py = cy + r * 0.7 * math.sin(a)
            pts.extend([px, py])
        self.canvas.create_polygon(pts, fill='#e74c3c', outline='#c0392b', width=2)
    
    def _draw_triangle(self, cx, cy, r, angle):
        pts = []
        for i in range(3):
            a = angle + math.radians(i * 120 - 90)
            px = cx + r * 0.8 * math.cos(a)
            py = cy + r * 0.8 * math.sin(a)
            pts.extend([px, py])
        self.canvas.create_polygon(pts, fill='#2ecc71', outline='#27ae60', width=2)
    
    def _draw_cross(self, cx, cy, r, angle):
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        # 竖线
        for dx, dy, color in [(-0.15, 0, '#9b59b6'), (0.15, 0, '#9b59b6')]:
            x1 = cx + r * (dx * cos_a - (-0.7) * sin_a)
            y1 = cy + r * (dx * sin_a + (-0.7) * cos_a)
            x2 = cx + r * (dx * cos_a - 0.7 * sin_a)
            y2 = cy + r * (dx * sin_a + 0.7 * cos_a)
            self.canvas.create_line(x1, y1, x2, y2, fill=color, width=8)
        # 横线
        for dx, dy, color in [(0, -0.15, '#9b59b6'), (0, 0.15, '#9b59b6')]:
            x1 = cx + r * ((-0.5) * cos_a - dy * sin_a)
            y1 = cy + r * ((-0.5) * sin_a + dy * cos_a)
            x2 = cx + r * (0.5 * cos_a - dy * sin_a)
            y2 = cy + r * (0.5 * sin_a + dy * cos_a)
            self.canvas.create_line(x1, y1, x2, y2, fill=color, width=8)
    
    def _on_press(self, event):
        self.vm.start_rotate(event.x, event.y)
    
    def _on_drag(self, event):
        self.vm.rotate(event.x, event.y)
    
    def _on_release(self, event):
        self.vm.end_rotate()
    
    def _verify(self):
        if self.vm.model.rotate_data:
            self.vm.end_rotate()


class DragSortCaptchaView(BaseCaptchaView):
    """拖拽排序验证码视图"""
    
    def __init__(self, parent: tk.Widget, viewmodel: DragSortCaptchaViewModel, width: int = 440, height: int = 200):
        self.vm: DragSortCaptchaViewModel = viewmodel
        super().__init__(parent, viewmodel, width, height)
    
    def _build_ui(self):
        super()._build_ui()
        
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="验证", command=self._verify).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="刷新", command=self.reset).pack(side=tk.LEFT, padx=5)
        
        # 提示
        self.hint_label = tk.Label(
            self.frame, text="拖动交换位置，排列好后点击验证",
            font=('微软雅黑', 10), fg='#888'
        )
        self.hint_label.pack(pady=2)
        
        # 绑定事件
        self.canvas.bind('<Button-1>', self._on_press)
        self.canvas.bind('<B1-Motion>', self._on_drag)
        self.canvas.bind('<ButtonRelease-1>', self._on_release)
        
        self.draw()
    
    def _get_slot_positions(self):
        """计算槽位位置"""
        data = self.vm.model.drag_sort_data
        if data is None:
            return []
        cfg = self.vm.config.get('drag_sort_captcha', {})
        item_w = cfg.get('item_width', 70)
        item_h = cfg.get('item_height', 70)
        spacing = cfg.get('item_spacing', 10)
        cw = cfg.get('width', 400)
        ch = cfg.get('height', 150)
        start_x = (cw - (data.item_count * item_w + (data.item_count - 1) * spacing)) // 2
        start_y = (ch - item_h) // 2
        return [(start_x + i * (item_w + spacing), start_y) for i in range(data.item_count)]
    
    def draw(self):
        self.canvas.delete('all')
        
        data = self.vm.model.drag_sort_data
        if data is None:
            return
        
        cfg = self.vm.config.get('drag_sort_captcha', {})
        cw = cfg.get('width', 400)
        ch = cfg.get('height', 150)
        bg_color = cfg.get('bg_color', '#f5f5f5')
        slot_color = cfg.get('slot_color', '#e0e0e0')
        slot_border = cfg.get('slot_border', '#bdbdbd')
        
        state = self.vm.get_state()
        
        # 背景
        self.canvas.create_rectangle(0, 0, cw, ch, fill=bg_color, outline='#ddd')
        
        # 绘制槽位
        slot_positions = self._get_slot_positions()
        item_w = cfg.get('item_width', 70)
        item_h = cfg.get('item_height', 70)
        
        for i, (sx, sy) in enumerate(slot_positions):
            self.canvas.create_rectangle(
                sx, sy, sx + item_w, sy + item_h,
                fill=slot_color, outline=slot_border, width=1, dash=(2, 2)
            )
            self.canvas.create_text(
                sx + item_w / 2, sy + item_h / 2,
                text=str(i + 1), font=('Arial', 14), fill='#bbb'
            )
        
        # 绘制物品
        for item in data.items:
            ix = item['current_x']
            iy = item['current_y']
            iw = item['width']
            ih = item['height']
            
            is_dragging = data.dragging_item == item['id']
            
            # 阴影
            if is_dragging:
                self.canvas.create_rectangle(
                    ix + 4, iy + 4, ix + iw + 4, iy + ih + 4,
                    fill='#cccccc', outline=''
                )
            
            # 3D效果
            self.canvas.create_rectangle(ix, iy, ix + iw, iy + 2, fill='white', outline='')
            self.canvas.create_rectangle(ix, iy, ix + 2, iy + ih, fill='white', outline='')
            self.canvas.create_rectangle(
                ix + 1, iy + 1, ix + iw - 1, iy + ih - 1,
                fill=item['color'], outline='white' if not is_dragging else '#2196F3',
                width=2 if not is_dragging else 3
            )
            
            # 数字
            self.canvas.create_text(
                ix + iw / 2, iy + ih / 2,
                text=str(item['number']), font=('Arial', 20, 'bold'), fill='white'
            )
        
        # 成功/失败状态
        if state == CaptchaState.SUCCESS:
            self.canvas.create_rectangle(0, 0, cw, ch, outline='#4CAF50', width=4)
        elif state == CaptchaState.FAILED:
            self.canvas.create_rectangle(0, 0, cw, ch, outline='#f44336', width=4)
    
    def _on_press(self, event):
        data = self.vm.model.drag_sort_data
        if data is None:
            return
        
        for item in data.items:
            ix, iy = item['current_x'], item['current_y']
            iw, ih = item['width'], item['height']
            if (ix <= event.x <= ix + iw and iy <= event.y <= iy + ih):
                self.vm.start_drag(item['id'], event.x, event.y)
                break
    
    def _on_drag(self, event):
        self.vm.drag(event.x, event.y)
    
    def _on_release(self, event):
        self.vm.end_drag()
    
    def _verify(self):
        self.vm.verify()


class WordOrderCaptchaView(BaseCaptchaView):
    """语序点选验证码视图"""
    def __init__(self, parent, viewmodel, width=400, height=200):
        self.vm = viewmodel
        super().__init__(parent, viewmodel, width, height)
    def _build_ui(self):
        super()._build_ui()
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="刷新", command=self.reset).pack(side=tk.LEFT, padx=5)
        self.instruction_label = tk.Label(self.frame, text="", font=('微软雅黑', 11), fg='#2196F3')
        self.instruction_label.pack(pady=2)
        self.canvas.bind('<Button-1>', self._on_click)
        self.draw()
    def draw(self):
        self.canvas.delete('all')
        data = self.vm.model.word_order_data
        if data is None:
            return
        state = self.vm.get_state()
        words = data.shuffled_words
        n = len(words)
        box_w = min(80, (self.width - 40) // n)
        box_h = 60
        start_x = (self.width - n * box_w) // 2
        start_y = 30
        for i, word in enumerate(words):
            x = start_x + i * box_w
            y = start_y
            if i in data.clicked_order:
                bg = '#4CAF50'
            else:
                bg = '#2196F3'
            self.canvas.create_rectangle(x+2, y+2, x+box_w-2, y+box_h-2, fill=bg, outline='white', width=2)
            self.canvas.create_text(x + box_w//2, y + box_h//2, text=word, font=('微软雅黑', 16, 'bold'), fill='white')
        if state == CaptchaState.SUCCESS:
            self.instruction_label.config(text='验证成功！', fg='#4CAF50')
        elif state == CaptchaState.FAILED:
            self.instruction_label.config(text='顺序错误，请重试', fg='#f44336')
        else:
            instruction = data.instruction
            correct = data.words[:len(data.clicked_order)+1]
            self.instruction_label.config(text=f"{instruction} {' → '.join(correct)}", fg='#2196F3')
    def _on_click(self, event):
        data = self.vm.model.word_order_data
        if data is None:
            return
        words = data.shuffled_words
        n = len(words)
        box_w = min(80, (self.width - 40) // n)
        start_x = (self.width - n * box_w) // 2
        start_y = 30
        for i in range(n):
            x = start_x + i * box_w
            y = start_y
            if x <= event.x <= x + box_w and y <= event.y <= y + 60:
                self.vm.click(i)
                break
    def reset(self):
        super().reset()
        self.instruction_label.config(text='', fg='#2196F3')


class DifferenceClickCaptchaView(BaseCaptchaView):
    """差异点击验证码视图"""
    def __init__(self, parent, viewmodel, width=320, height=320):
        self.vm = viewmodel
        super().__init__(parent, viewmodel, width, height)
    def _build_ui(self):
        super()._build_ui()
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="刷新", command=self.reset).pack(side=tk.LEFT, padx=5)
        self.hint_label = tk.Label(self.frame, text="找出与其他不同的图形", font=('微软雅黑', 11), fg='#888')
        self.hint_label.pack(pady=2)
        self.canvas.bind('<Button-1>', self._on_click)
        self.draw()
    def draw(self):
        self.canvas.delete('all')
        data = self.vm.model.difference_click_data
        if data is None:
            return
        state = self.vm.get_state()
        cols = 3
        size = 80
        pad = 10
        start_x = (self.width - cols * (size + pad)) // 2
        start_y = 20
        for i, img in enumerate(data.images):
            row, col = divmod(i, cols)
            x = start_x + col * (size + pad)
            y = start_y + row * (size + pad)
            if i == data.clicked_index:
                border = '#4CAF50' if state == CaptchaState.SUCCESS else '#f44336'
                self.canvas.create_rectangle(x-2, y-2, x+size+2, y+size+2, outline=border, width=3)
            self.canvas.create_rectangle(x, y, x+size, y+size, fill=img['color'], outline='#ddd', width=1)
            cx, cy = x + size//2, y + size//2
            shape = img['shape']
            if shape == 'circle':
                self.canvas.create_oval(cx-20, cy-20, cx+20, cy+20, fill='white', outline='#333', width=2)
            elif shape == 'square':
                self.canvas.create_rectangle(cx-20, cy-20, cx+20, cy+20, fill='white', outline='#333', width=2)
            elif shape == 'triangle':
                self.canvas.create_polygon(cx, cy-20, cx-20, cy+20, cx+20, cy+20, fill='white', outline='#333', width=2)
    def _on_click(self, event):
        data = self.vm.model.difference_click_data
        if data is None or self.vm.get_state() != CaptchaState.IDLE:
            return
        cols = 3
        size = 80
        pad = 10
        start_x = (self.width - cols * (size + pad)) // 2
        start_y = 20
        for i in range(len(data.images)):
            row, col = divmod(i, cols)
            x = start_x + col * (size + pad)
            y = start_y + row * (size + pad)
            if x <= event.x <= x + size and y <= event.y <= y + size:
                self.vm.click(i)
                break


class NineGridCaptchaView(BaseCaptchaView):
    """九宫格验证码视图"""
    def __init__(self, parent, viewmodel, width=300, height=340):
        self.vm = viewmodel
        super().__init__(parent, viewmodel, width, height)
    def _build_ui(self):
        super()._build_ui()
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="刷新", command=self.reset).pack(side=tk.LEFT, padx=5)
        self.hint_label = tk.Label(self.frame, text="请点击所有动物", font=('微软雅黑', 11), fg='#888')
        self.hint_label.pack(pady=2)
        self.canvas.bind('<Button-1>', self._on_click)
        self.draw()
    def draw(self):
        self.canvas.delete('all')
        data = self.vm.model.nine_grid_data
        if data is None:
            return
        state = self.vm.get_state()
        size = 80
        pad = 5
        start_x = (self.width - 3 * (size + pad)) // 2
        start_y = 20
        for i, grid in enumerate(data.grids):
            row, col = divmod(i, 3)
            x = start_x + col * (size + pad)
            y = start_y + row * (size + pad)
            if i in data.clicked_indices:
                bg = '#4CAF50'
                border = '#2E7D32'
            else:
                bg = '#f5f5f5'
                border = '#ddd'
            self.canvas.create_rectangle(x, y, x+size, y+size, fill=bg, outline=border, width=2)
            self.canvas.create_text(x + size//2, y + size//2, text=grid['animal'], font=('Arial', 24))
        if state == CaptchaState.SUCCESS:
            self.hint_label.config(text='验证成功！', fg='#4CAF50')
        elif state == CaptchaState.FAILED:
            self.hint_label.config(text='验证失败', fg='#f44336')
    def _on_click(self, event):
        data = self.vm.model.nine_grid_data
        if data is None:
            return
        size = 80
        pad = 5
        start_x = (self.width - 3 * (size + pad)) // 2
        start_y = 20
        for i in range(9):
            row, col = divmod(i, 3)
            x = start_x + col * (size + pad)
            y = start_y + row * (size + pad)
            if x <= event.x <= x + size and y <= event.y <= y + size:
                self.vm.click(i)
                break


class SMSCaptchaView(BaseCaptchaView):
    """短信验证码（模拟）视图"""
    def __init__(self, parent, viewmodel, width=320, height=180):
        self.vm = viewmodel
        super().__init__(parent, viewmodel, width, height)
    def _build_ui(self):
        super()._build_ui()
        input_frame = ttk.Frame(self.frame)
        input_frame.pack(pady=5)
        tk.Label(input_frame, text="请输入验证码:", font=('微软雅黑', 11)).pack(side=tk.LEFT, padx=5)
        self.entry = tk.Entry(input_frame, font=('微软雅黑', 14), width=12, justify='center')
        self.entry.pack(side=tk.LEFT, padx=5)
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="验证", command=self._verify).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="刷新", command=self.reset).pack(side=tk.LEFT, padx=5)
        self.entry.bind('<Return>', lambda e: self._verify())
        self.draw()
    def draw(self):
        self.canvas.delete('all')
        data = self.vm.model.sms_data
        if data is None:
            return
        self.canvas.create_rectangle(0, 0, self.width, self.height, fill='#E3F2FD', outline='#BBDEFB')
        self.canvas.create_text(self.width//2, 40, text=data.display_code, font=('微软雅黑', 14, 'bold'), fill='#1565C0')
        self.canvas.create_text(self.width//2, 80, text='【模拟：验证码已发送到您的手机】', font=('微软雅黑', 10), fill='#666')
    def _verify(self):
        user_input = self.entry.get().strip()
        if user_input:
            self.vm.verify(user_input)
            self.entry.delete(0, tk.END)
    def reset(self):
        super().reset()
        self.entry.delete(0, tk.END)


class ScratchCardCaptchaView(BaseCaptchaView):
    """刮刮卡验证码视图"""
    def __init__(self, parent, viewmodel, width=320, height=220):
        self.vm = viewmodel
        super().__init__(parent, viewmodel, width, height)
    def _build_ui(self):
        super()._build_ui()
        input_frame = ttk.Frame(self.frame)
        input_frame.pack(pady=5)
        tk.Label(input_frame, text="刮开涂层后输入:", font=('微软雅黑', 11)).pack(side=tk.LEFT, padx=5)
        self.entry = tk.Entry(input_frame, font=('微软雅黑', 14), width=8, justify='center')
        self.entry.pack(side=tk.LEFT, padx=5)
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="验证", command=self._verify).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="刷新", command=self.reset).pack(side=tk.LEFT, padx=5)
        self.canvas.bind('<Button-1>', self._on_press)
        self.canvas.bind('<B1-Motion>', self._on_drag)
        self.canvas.bind('<ButtonRelease-1>', self._on_release)
        self.draw()
    def draw(self):
        self.canvas.delete('all')
        data = self.vm.model.scratch_card_data
        if data is None:
            return
        cx, cy = self.width//2, self.height//2
        cw, ch = 200, 80
        x1, y1 = cx - cw//2, cy - ch//2
        x2, y2 = cx + cw//2, cy + ch//2
        # 底层：答案
        self.canvas.create_rectangle(x1, y1, x2, y2, fill='#FFF8E1', outline='#FFE082')
        self.canvas.create_text(cx, cy, text=data.answer, font=('Arial', 28, 'bold'), fill='#F57F17')
        # 涂层
        scratched = set()
        for sx, sy in data.scratched:
            for dx in range(-15, 16):
                for dy in range(-15, 16):
                    px, py = int(sx+dx), int(sy+dy)
                    if x1 <= px <= x2 and y1 <= py <= y2:
                        scratched.add((px, py))
        for px in range(int(x1), int(x2)+1):
            for py in range(int(y1), int(y2)+1):
                if (px, py) not in scratched:
                    self.canvas.create_rectangle(px, py, px+1, py+1, fill='#9E9E9E', outline='')
        self.canvas.create_rectangle(x1, y1, x2, y2, outline='#757575', width=2)
    def _on_press(self, event):
        self.vm.start_drag(event.x, event.y)
    def _on_drag(self, event):
        self.vm.drag(event.x, event.y)
    def _on_release(self, event):
        self.vm.end_drag()
    def _verify(self):
        user_input = self.entry.get().strip()
        if user_input:
            self.vm.verify(user_input)
            self.entry.delete(0, tk.END)
    def reset(self):
        super().reset()
        self.entry.delete(0, tk.END)


class AreaClickCaptchaView(BaseCaptchaView):
    """面积验证视图"""
    def __init__(self, parent, viewmodel, width=320, height=240):
        self.vm = viewmodel
        super().__init__(parent, viewmodel, width, height)
    def _build_ui(self):
        super()._build_ui()
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="刷新", command=self.reset).pack(side=tk.LEFT, padx=5)
        self.hint_label = tk.Label(self.frame, text="", font=('微软雅黑', 11), fg='#888')
        self.hint_label.pack(pady=2)
        self.canvas.bind('<Button-1>', self._on_click)
        self.draw()
    def draw(self):
        self.canvas.delete('all')
        data = self.vm.model.area_click_data
        if data is None:
            return
        state = self.vm.get_state()
        self.canvas.create_rectangle(0, 0, self.width, self.height, fill='#f8f9fa', outline='#ddd')
        for i, shape in enumerate(data.shapes):
            self.canvas.create_oval(shape['cx']-shape['r'], shape['cy']-shape['r'], shape['cx']+shape['r'], shape['cy']+shape['r'], fill=shape['color'], outline='#333', width=2)
        if state == CaptchaState.SUCCESS:
            self.hint_label.config(text='验证成功！', fg='#4CAF50')
        elif state == CaptchaState.FAILED:
            self.hint_label.config(text='选择错误', fg='#f44336')
        else:
            target = '最大' if data.target_type == 'largest' else '最小'
            self.hint_label.config(text=f'请点击面积{target}的圆形', fg='#2196F3')
    def _on_click(self, event):
        data = self.vm.model.area_click_data
        if data is None or self.vm.get_state() != CaptchaState.IDLE:
            return
        for i, shape in enumerate(data.shapes):
            dist = ((event.x - shape['cx'])**2 + (event.y - shape['cy'])**2)**0.5
            if dist <= shape['r']:
                self.vm.click(i)
                break


class VoiceCaptchaView(BaseCaptchaView):
    """语音验证码（模拟）视图"""
    def __init__(self, parent, viewmodel, width=320, height=180):
        self.vm = viewmodel
        super().__init__(parent, viewmodel, width, height)
    def _build_ui(self):
        super()._build_ui()
        input_frame = ttk.Frame(self.frame)
        input_frame.pack(pady=5)
        tk.Label(input_frame, text="听到的验证码:", font=('微软雅黑', 11)).pack(side=tk.LEFT, padx=5)
        self.entry = tk.Entry(input_frame, font=('微软雅黑', 14), width=8, justify='center')
        self.entry.pack(side=tk.LEFT, padx=5)
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="验证", command=self._verify).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="刷新", command=self.reset).pack(side=tk.LEFT, padx=5)
        self.entry.bind('<Return>', lambda e: self._verify())
        self.draw()
    def draw(self):
        self.canvas.delete('all')
        data = self.vm.model.voice_data
        if data is None:
            return
        self.canvas.create_rectangle(0, 0, self.width, self.height, fill='#E8F5E9', outline='#C8E6C9')
        self.canvas.create_text(self.width//2, 50, text='[模拟语音播放中...]', font=('微软雅黑', 14, 'bold'), fill='#2E7D32')
        self.canvas.create_text(self.width//2, 90, text=data.display_text, font=('微软雅黑', 10), fill='#666')
    def _verify(self):
        user_input = self.entry.get().strip()
        if user_input:
            self.vm.verify(user_input)
            self.entry.delete(0, tk.END)
    def reset(self):
        super().reset()
        self.entry.delete(0, tk.END)


class FontRecognizeCaptchaView(BaseCaptchaView):
    """字体识别验证码视图"""
    def __init__(self, parent, viewmodel, width=320, height=180):
        self.vm = viewmodel
        super().__init__(parent, viewmodel, width, height)
    def _build_ui(self):
        super()._build_ui()
        input_frame = ttk.Frame(self.frame)
        input_frame.pack(pady=5)
        tk.Label(input_frame, text="请输入字符:", font=('微软雅黑', 11)).pack(side=tk.LEFT, padx=5)
        self.entry = tk.Entry(input_frame, font=('微软雅黑', 14), width=12, justify='center')
        self.entry.pack(side=tk.LEFT, padx=5)
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="验证", command=self._verify).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="刷新", command=self.reset).pack(side=tk.LEFT, padx=5)
        self.entry.bind('<Return>', lambda e: self._verify())
        self.draw()
    def draw(self):
        self.canvas.delete('all')
        data = self.vm.model.font_recognize_data
        if data is None:
            return
        self.canvas.create_rectangle(0, 0, self.width, self.height, fill='#f8f9fa', outline='#ddd')
        for i, (x, y, size, font_name) in enumerate(data.char_positions):
            self.canvas.create_text(x, y, text=data.code[i], font=(font_name, size, 'bold'), fill='#333')
    def _verify(self):
        user_input = self.entry.get().strip()
        if user_input:
            self.vm.verify(user_input)
            self.entry.delete(0, tk.END)
    def reset(self):
        super().reset()
        self.entry.delete(0, tk.END)


class BehaviorMockCaptchaView(BaseCaptchaView):
    """无感验证（模拟）视图"""
    def __init__(self, parent, viewmodel, width=320, height=180):
        self.vm = viewmodel
        super().__init__(parent, viewmodel, width, height)
        self._checking = False
    def _build_ui(self):
        super()._build_ui()
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="开始检测", command=self._start_check).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="刷新", command=self.reset).pack(side=tk.LEFT, padx=5)
        self.draw()
    def draw(self):
        self.canvas.delete('all')
        data = self.vm.model.behavior_data
        if data is None:
            return
        state = self.vm.get_state()
        self.canvas.create_rectangle(0, 0, self.width, self.height, fill='#f5f5f5', outline='#ddd')
        if state == CaptchaState.VERIFYING:
            # 进度条
            bar_w = 200
            bar_h = 20
            bx = (self.width - bar_w) // 2
            by = 60
            self.canvas.create_rectangle(bx, by, bx+bar_w, by+bar_h, fill='white', outline='#ccc')
            fill_w = int(bar_w * data.progress)
            self.canvas.create_rectangle(bx, by, bx+fill_w, by+bar_h, fill='#2196F3', outline='')
            self.canvas.create_text(self.width//2, 110, text='正在分析行为特征...', font=('微软雅黑', 12), fill='#666')
            self.canvas.create_text(self.width//2, 140, text=f'进度: {int(data.progress*100)}%', font=('微软雅黑', 10), fill='#888')
        elif state == CaptchaState.SUCCESS:
            self.canvas.create_text(self.width//2, 80, text='验证通过', font=('微软雅黑', 16, 'bold'), fill='#4CAF50')
            self.canvas.create_text(self.width//2, 120, text=f'行为评分: {data.fake_score:.2f}', font=('微软雅黑', 11), fill='#666')
        elif state == CaptchaState.FAILED:
            self.canvas.create_text(self.width//2, 80, text='验证失败', font=('微软雅黑', 16, 'bold'), fill='#f44336')
            self.canvas.create_text(self.width//2, 120, text=f'行为评分: {data.fake_score:.2f}', font=('微软雅黑', 11), fill='#666')
        else:
            self.canvas.create_text(self.width//2, 80, text='点击「开始检测」进行无感验证', font=('微软雅黑', 12), fill='#666')
    def _start_check(self):
        if self._checking:
            return
        self._checking = True
        self._check_step()
    def _check_step(self):
        if not self._checking:
            return
        result = self.vm.simulate_check()
        state = self.vm.get_state()
        if state == CaptchaState.IDLE or state == CaptchaState.VERIFYING:
            self.canvas.after(500, self._check_step)
        else:
            self._checking = False
    def reset(self):
        self._checking = False
        super().reset()


class WordOrderCaptchaView(BaseCaptchaView):
    """语序点选验证码视图"""
    def __init__(self, parent, viewmodel, width=400, height=200):
        self.vm = viewmodel
        super().__init__(parent, viewmodel, width, height)
    def _build_ui(self):
        super()._build_ui()
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="刷新", command=self.reset).pack(side=tk.LEFT, padx=5)
        self.instruction_label = tk.Label(self.frame, text="", font=('微软雅黑', 11), fg='#2196F3')
        self.instruction_label.pack(pady=2)
        self.canvas.bind('<Button-1>', self._on_click)
        self.draw()
    def draw(self):
        self.canvas.delete('all')
        data = self.vm.model.word_order_data
        if data is None:
            return
        state = self.vm.get_state()
        words = data.shuffled_words
        n = len(words)
        box_w = min(80, (self.width - 40) // n)
        box_h = 60
        start_x = (self.width - n * box_w) // 2
        start_y = 30
        for i, word in enumerate(words):
            x = start_x + i * box_w
            y = start_y
            if i in data.clicked_order:
                bg = '#4CAF50'
            else:
                bg = '#2196F3'
            self.canvas.create_rectangle(x+2, y+2, x+box_w-2, y+box_h-2, fill=bg, outline='white', width=2)
            self.canvas.create_text(x + box_w//2, y + box_h//2, text=word, font=('微软雅黑', 16, 'bold'), fill='white')
        if state == CaptchaState.SUCCESS:
            self.instruction_label.config(text='验证成功！', fg='#4CAF50')
        elif state == CaptchaState.FAILED:
            self.instruction_label.config(text='顺序错误，请重试', fg='#f44336')
        else:
            instruction = data.instruction
            correct = data.words[:len(data.clicked_order)+1]
            self.instruction_label.config(text=f"{instruction} {' → '.join(correct)}", fg='#2196F3')
    def _on_click(self, event):
        data = self.vm.model.word_order_data
        if data is None:
            return
        words = data.shuffled_words
        n = len(words)
        box_w = min(80, (self.width - 40) // n)
        start_x = (self.width - n * box_w) // 2
        start_y = 30
        for i in range(n):
            x = start_x + i * box_w
            y = start_y
            if x <= event.x <= x + box_w and y <= event.y <= y + 60:
                self.vm.click(i)
                break
    def reset(self):
        super().reset()
        self.instruction_label.config(text='', fg='#2196F3')


class DifferenceClickCaptchaView(BaseCaptchaView):
    """差异点击验证码视图"""
    def __init__(self, parent, viewmodel, width=320, height=320):
        self.vm = viewmodel
        super().__init__(parent, viewmodel, width, height)
    def _build_ui(self):
        super()._build_ui()
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="刷新", command=self.reset).pack(side=tk.LEFT, padx=5)
        self.hint_label = tk.Label(self.frame, text="找出与其他不同的图形", font=('微软雅黑', 11), fg='#888')
        self.hint_label.pack(pady=2)
        self.canvas.bind('<Button-1>', self._on_click)
        self.draw()
    def draw(self):
        self.canvas.delete('all')
        data = self.vm.model.difference_click_data
        if data is None:
            return
        state = self.vm.get_state()
        cols = 3
        size = 80
        pad = 10
        start_x = (self.width - cols * (size + pad)) // 2
        start_y = 20
        for i, img in enumerate(data.images):
            row, col = divmod(i, cols)
            x = start_x + col * (size + pad)
            y = start_y + row * (size + pad)
            if i == data.clicked_index:
                border = '#4CAF50' if state == CaptchaState.SUCCESS else '#f44336'
                self.canvas.create_rectangle(x-2, y-2, x+size+2, y+size+2, outline=border, width=3)
            self.canvas.create_rectangle(x, y, x+size, y+size, fill=img['color'], outline='#ddd', width=1)
            cx, cy = x + size//2, y + size//2
            shape = img['shape']
            if shape == 'circle':
                self.canvas.create_oval(cx-20, cy-20, cx+20, cy+20, fill='white', outline='#333', width=2)
            elif shape == 'square':
                self.canvas.create_rectangle(cx-20, cy-20, cx+20, cy+20, fill='white', outline='#333', width=2)
            elif shape == 'triangle':
                self.canvas.create_polygon(cx, cy-20, cx-20, cy+20, cx+20, cy+20, fill='white', outline='#333', width=2)
    def _on_click(self, event):
        data = self.vm.model.difference_click_data
        if data is None or self.vm.get_state() != CaptchaState.IDLE:
            return
        cols = 3
        size = 80
        pad = 10
        start_x = (self.width - cols * (size + pad)) // 2
        start_y = 20
        for i in range(len(data.images)):
            row, col = divmod(i, cols)
            x = start_x + col * (size + pad)
            y = start_y + row * (size + pad)
            if x <= event.x <= x + size and y <= event.y <= y + size:
                self.vm.click(i)
                break


class NineGridCaptchaView(BaseCaptchaView):
    """九宫格验证码视图"""
    def __init__(self, parent, viewmodel, width=300, height=340):
        self.vm = viewmodel
        super().__init__(parent, viewmodel, width, height)
    def _build_ui(self):
        super()._build_ui()
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="刷新", command=self.reset).pack(side=tk.LEFT, padx=5)
        self.hint_label = tk.Label(self.frame, text="请点击所有动物", font=('微软雅黑', 11), fg='#888')
        self.hint_label.pack(pady=2)
        self.canvas.bind('<Button-1>', self._on_click)
        self.draw()
    def draw(self):
        self.canvas.delete('all')
        data = self.vm.model.nine_grid_data
        if data is None:
            return
        state = self.vm.get_state()
        size = 80
        pad = 5
        start_x = (self.width - 3 * (size + pad)) // 2
        start_y = 20
        for i, grid in enumerate(data.grids):
            row, col = divmod(i, 3)
            x = start_x + col * (size + pad)
            y = start_y + row * (size + pad)
            if i in data.clicked_indices:
                bg = '#4CAF50'
                border = '#2E7D32'
            else:
                bg = '#f5f5f5'
                border = '#ddd'
            self.canvas.create_rectangle(x, y, x+size, y+size, fill=bg, outline=border, width=2)
            self.canvas.create_text(x + size//2, y + size//2, text=grid['animal'], font=('Arial', 24))
        if state == CaptchaState.SUCCESS:
            self.hint_label.config(text='验证成功！', fg='#4CAF50')
        elif state == CaptchaState.FAILED:
            self.hint_label.config(text='验证失败', fg='#f44336')
    def _on_click(self, event):
        data = self.vm.model.nine_grid_data
        if data is None:
            return
        size = 80
        pad = 5
        start_x = (self.width - 3 * (size + pad)) // 2
        start_y = 20
        for i in range(9):
            row, col = divmod(i, 3)
            x = start_x + col * (size + pad)
            y = start_y + row * (size + pad)
            if x <= event.x <= x + size and y <= event.y <= y + size:
                self.vm.click(i)
                break


class SMSCaptchaView(BaseCaptchaView):
    """短信验证码（模拟）视图"""
    def __init__(self, parent, viewmodel, width=320, height=180):
        self.vm = viewmodel
        super().__init__(parent, viewmodel, width, height)
    def _build_ui(self):
        super()._build_ui()
        input_frame = ttk.Frame(self.frame)
        input_frame.pack(pady=5)
        tk.Label(input_frame, text="请输入验证码:", font=('微软雅黑', 11)).pack(side=tk.LEFT, padx=5)
        self.entry = tk.Entry(input_frame, font=('微软雅黑', 14), width=12, justify='center')
        self.entry.pack(side=tk.LEFT, padx=5)
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="验证", command=self._verify).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="刷新", command=self.reset).pack(side=tk.LEFT, padx=5)
        self.entry.bind('<Return>', lambda e: self._verify())
        self.draw()
    def draw(self):
        self.canvas.delete('all')
        data = self.vm.model.sms_data
        if data is None:
            return
        self.canvas.create_rectangle(0, 0, self.width, self.height, fill='#E3F2FD', outline='#BBDEFB')
        self.canvas.create_text(self.width//2, 40, text=data.display_code, font=('微软雅黑', 14, 'bold'), fill='#1565C0')
        self.canvas.create_text(self.width//2, 80, text='【模拟：验证码已发送到您的手机】', font=('微软雅黑', 10), fill='#666')
    def _verify(self):
        user_input = self.entry.get().strip()
        if user_input:
            self.vm.verify(user_input)
            self.entry.delete(0, tk.END)
    def reset(self):
        super().reset()
        self.entry.delete(0, tk.END)


class ScratchCardCaptchaView(BaseCaptchaView):
    """刮刮卡验证码视图"""
    def __init__(self, parent, viewmodel, width=320, height=220):
        self.vm = viewmodel
        super().__init__(parent, viewmodel, width, height)
    def _build_ui(self):
        super()._build_ui()
        input_frame = ttk.Frame(self.frame)
        input_frame.pack(pady=5)
        tk.Label(input_frame, text="刮开涂层后输入:", font=('微软雅黑', 11)).pack(side=tk.LEFT, padx=5)
        self.entry = tk.Entry(input_frame, font=('微软雅黑', 14), width=8, justify='center')
        self.entry.pack(side=tk.LEFT, padx=5)
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="验证", command=self._verify).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="刷新", command=self.reset).pack(side=tk.LEFT, padx=5)
        self.canvas.bind('<Button-1>', self._on_press)
        self.canvas.bind('<B1-Motion>', self._on_drag)
        self.canvas.bind('<ButtonRelease-1>', self._on_release)
        self.draw()
    def draw(self):
        self.canvas.delete('all')
        data = self.vm.model.scratch_card_data
        if data is None:
            return
        cx, cy = self.width//2, self.height//2
        cw, ch = 200, 80
        x1, y1 = cx - cw//2, cy - ch//2
        x2, y2 = cx + cw//2, cy + ch//2
        # 底层：答案
        self.canvas.create_rectangle(x1, y1, x2, y2, fill='#FFF8E1', outline='#FFE082')
        self.canvas.create_text(cx, cy, text=data.answer, font=('Arial', 28, 'bold'), fill='#F57F17')
        # 涂层
        scratched = set()
        for sx, sy in data.scratched:
            for dx in range(-15, 16):
                for dy in range(-15, 16):
                    px, py = int(sx+dx), int(sy+dy)
                    if x1 <= px <= x2 and y1 <= py <= y2:
                        scratched.add((px, py))
        for px in range(int(x1), int(x2)+1):
            for py in range(int(y1), int(y2)+1):
                if (px, py) not in scratched:
                    self.canvas.create_rectangle(px, py, px+1, py+1, fill='#9E9E9E', outline='')
        self.canvas.create_rectangle(x1, y1, x2, y2, outline='#757575', width=2)
    def _on_press(self, event):
        self.vm.start_drag(event.x, event.y)
    def _on_drag(self, event):
        self.vm.drag(event.x, event.y)
    def _on_release(self, event):
        self.vm.end_drag()
    def _verify(self):
        user_input = self.entry.get().strip()
        if user_input:
            self.vm.verify(user_input)
            self.entry.delete(0, tk.END)
    def reset(self):
        super().reset()
        self.entry.delete(0, tk.END)


class AreaClickCaptchaView(BaseCaptchaView):
    """面积验证视图"""
    def __init__(self, parent, viewmodel, width=320, height=240):
        self.vm = viewmodel
        super().__init__(parent, viewmodel, width, height)
    def _build_ui(self):
        super()._build_ui()
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="刷新", command=self.reset).pack(side=tk.LEFT, padx=5)
        self.hint_label = tk.Label(self.frame, text="", font=('微软雅黑', 11), fg='#888')
        self.hint_label.pack(pady=2)
        self.canvas.bind('<Button-1>', self._on_click)
        self.draw()
    def draw(self):
        self.canvas.delete('all')
        data = self.vm.model.area_click_data
        if data is None:
            return
        state = self.vm.get_state()
        self.canvas.create_rectangle(0, 0, self.width, self.height, fill='#f8f9fa', outline='#ddd')
        for i, shape in enumerate(data.shapes):
            self.canvas.create_oval(shape['cx']-shape['r'], shape['cy']-shape['r'], shape['cx']+shape['r'], shape['cy']+shape['r'], fill=shape['color'], outline='#333', width=2)
        if state == CaptchaState.SUCCESS:
            self.hint_label.config(text='验证成功！', fg='#4CAF50')
        elif state == CaptchaState.FAILED:
            self.hint_label.config(text='选择错误', fg='#f44336')
        else:
            target = '最大' if data.target_type == 'largest' else '最小'
            self.hint_label.config(text=f'请点击面积{target}的圆形', fg='#2196F3')
    def _on_click(self, event):
        data = self.vm.model.area_click_data
        if data is None or self.vm.get_state() != CaptchaState.IDLE:
            return
        for i, shape in enumerate(data.shapes):
            dist = ((event.x - shape['cx'])**2 + (event.y - shape['cy'])**2)**0.5
            if dist <= shape['r']:
                self.vm.click(i)
                break


class VoiceCaptchaView(BaseCaptchaView):
    """语音验证码（模拟）视图"""
    def __init__(self, parent, viewmodel, width=320, height=180):
        self.vm = viewmodel
        super().__init__(parent, viewmodel, width, height)
    def _build_ui(self):
        super()._build_ui()
        input_frame = ttk.Frame(self.frame)
        input_frame.pack(pady=5)
        tk.Label(input_frame, text="听到的验证码:", font=('微软雅黑', 11)).pack(side=tk.LEFT, padx=5)
        self.entry = tk.Entry(input_frame, font=('微软雅黑', 14), width=8, justify='center')
        self.entry.pack(side=tk.LEFT, padx=5)
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="验证", command=self._verify).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="刷新", command=self.reset).pack(side=tk.LEFT, padx=5)
        self.entry.bind('<Return>', lambda e: self._verify())
        self.draw()
    def draw(self):
        self.canvas.delete('all')
        data = self.vm.model.voice_data
        if data is None:
            return
        self.canvas.create_rectangle(0, 0, self.width, self.height, fill='#E8F5E9', outline='#C8E6C9')
        self.canvas.create_text(self.width//2, 50, text='[模拟语音播放中...]', font=('微软雅黑', 14, 'bold'), fill='#2E7D32')
        self.canvas.create_text(self.width//2, 90, text=data.display_text, font=('微软雅黑', 10), fill='#666')
    def _verify(self):
        user_input = self.entry.get().strip()
        if user_input:
            self.vm.verify(user_input)
            self.entry.delete(0, tk.END)
    def reset(self):
        super().reset()
        self.entry.delete(0, tk.END)


class FontRecognizeCaptchaView(BaseCaptchaView):
    """字体识别验证码视图"""
    def __init__(self, parent, viewmodel, width=320, height=180):
        self.vm = viewmodel
        super().__init__(parent, viewmodel, width, height)
    def _build_ui(self):
        super()._build_ui()
        input_frame = ttk.Frame(self.frame)
        input_frame.pack(pady=5)
        tk.Label(input_frame, text="请输入字符:", font=('微软雅黑', 11)).pack(side=tk.LEFT, padx=5)
        self.entry = tk.Entry(input_frame, font=('微软雅黑', 14), width=12, justify='center')
        self.entry.pack(side=tk.LEFT, padx=5)
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="验证", command=self._verify).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="刷新", command=self.reset).pack(side=tk.LEFT, padx=5)
        self.entry.bind('<Return>', lambda e: self._verify())
        self.draw()
    def draw(self):
        self.canvas.delete('all')
        data = self.vm.model.font_recognize_data
        if data is None:
            return
        self.canvas.create_rectangle(0, 0, self.width, self.height, fill='#f8f9fa', outline='#ddd')
        for i, (x, y, size, font_name) in enumerate(data.char_positions):
            self.canvas.create_text(x, y, text=data.code[i], font=(font_name, size, 'bold'), fill='#333')
    def _verify(self):
        user_input = self.entry.get().strip()
        if user_input:
            self.vm.verify(user_input)
            self.entry.delete(0, tk.END)
    def reset(self):
        super().reset()
        self.entry.delete(0, tk.END)


class BehaviorMockCaptchaView(BaseCaptchaView):
    """无感验证（模拟）视图"""
    def __init__(self, parent, viewmodel, width=320, height=180):
        self.vm = viewmodel
        super().__init__(parent, viewmodel, width, height)
        self._checking = False
    def _build_ui(self):
        super()._build_ui()
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="开始检测", command=self._start_check).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="刷新", command=self.reset).pack(side=tk.LEFT, padx=5)
        self.draw()
    def draw(self):
        self.canvas.delete('all')
        data = self.vm.model.behavior_data
        if data is None:
            return
        state = self.vm.get_state()
        self.canvas.create_rectangle(0, 0, self.width, self.height, fill='#f5f5f5', outline='#ddd')
        if state == CaptchaState.VERIFYING:
            # 进度条
            bar_w = 200
            bar_h = 20
            bx = (self.width - bar_w) // 2
            by = 60
            self.canvas.create_rectangle(bx, by, bx+bar_w, by+bar_h, fill='white', outline='#ccc')
            fill_w = int(bar_w * data.progress)
            self.canvas.create_rectangle(bx, by, bx+fill_w, by+bar_h, fill='#2196F3', outline='')
            self.canvas.create_text(self.width//2, 110, text='正在分析行为特征...', font=('微软雅黑', 12), fill='#666')
            self.canvas.create_text(self.width//2, 140, text=f'进度: {int(data.progress*100)}%', font=('微软雅黑', 10), fill='#888')
        elif state == CaptchaState.SUCCESS:
            self.canvas.create_text(self.width//2, 80, text='验证通过', font=('微软雅黑', 16, 'bold'), fill='#4CAF50')
            self.canvas.create_text(self.width//2, 120, text=f'行为评分: {data.fake_score:.2f}', font=('微软雅黑', 11), fill='#666')
        elif state == CaptchaState.FAILED:
            self.canvas.create_text(self.width//2, 80, text='验证失败', font=('微软雅黑', 16, 'bold'), fill='#f44336')
            self.canvas.create_text(self.width//2, 120, text=f'行为评分: {data.fake_score:.2f}', font=('微软雅黑', 11), fill='#666')
        else:
            self.canvas.create_text(self.width//2, 80, text='点击「开始检测」进行无感验证', font=('微软雅黑', 12), fill='#666')
    def _start_check(self):
        if self._checking:
            return
        self._checking = True
        self._check_step()
    def _check_step(self):
        if not self._checking:
            return
        result = self.vm.simulate_check()
        state = self.vm.get_state()
        if state == CaptchaState.IDLE or state == CaptchaState.VERIFYING:
            self.canvas.after(500, self._check_step)
        else:
            self._checking = False
    def reset(self):
        self._checking = False
        super().reset()


class WordOrderCaptchaView(BaseCaptchaView):
    """语序点选验证码视图"""
    def __init__(self, parent, viewmodel, width=400, height=200):
        self.vm = viewmodel
        super().__init__(parent, viewmodel, width, height)
    def _build_ui(self):
        super()._build_ui()
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="刷新", command=self.reset).pack(side=tk.LEFT, padx=5)
        self.instruction_label = tk.Label(self.frame, text="", font=('微软雅黑', 11), fg='#2196F3')
        self.instruction_label.pack(pady=2)
        self.canvas.bind('<Button-1>', self._on_click)
        self.draw()
    def draw(self):
        self.canvas.delete('all')
        data = self.vm.model.word_order_data
        if data is None:
            return
        state = self.vm.get_state()
        words = data.shuffled_words
        n = len(words)
        box_w = min(80, (self.width - 40) // n)
        box_h = 60
        start_x = (self.width - n * box_w) // 2
        start_y = 30
        for i, word in enumerate(words):
            x = start_x + i * box_w
            y = start_y
            if i in data.clicked_order:
                bg = '#4CAF50'
            else:
                bg = '#2196F3'
            self.canvas.create_rectangle(x+2, y+2, x+box_w-2, y+box_h-2, fill=bg, outline='white', width=2)
            self.canvas.create_text(x + box_w//2, y + box_h//2, text=word, font=('微软雅黑', 16, 'bold'), fill='white')
        if state == CaptchaState.SUCCESS:
            self.instruction_label.config(text='验证成功！', fg='#4CAF50')
        elif state == CaptchaState.FAILED:
            self.instruction_label.config(text='顺序错误，请重试', fg='#f44336')
        else:
            instruction = data.instruction
            correct = data.words[:len(data.clicked_order)+1]
            self.instruction_label.config(text=f"{instruction} {' → '.join(correct)}", fg='#2196F3')
    def _on_click(self, event):
        data = self.vm.model.word_order_data
        if data is None:
            return
        words = data.shuffled_words
        n = len(words)
        box_w = min(80, (self.width - 40) // n)
        start_x = (self.width - n * box_w) // 2
        start_y = 30
        for i in range(n):
            x = start_x + i * box_w
            y = start_y
            if x <= event.x <= x + box_w and y <= event.y <= y + 60:
                self.vm.click(i)
                break
    def reset(self):
        super().reset()
        self.instruction_label.config(text='', fg='#2196F3')


class DifferenceClickCaptchaView(BaseCaptchaView):
    """差异点击验证码视图"""
    def __init__(self, parent, viewmodel, width=320, height=320):
        self.vm = viewmodel
        super().__init__(parent, viewmodel, width, height)
    def _build_ui(self):
        super()._build_ui()
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="刷新", command=self.reset).pack(side=tk.LEFT, padx=5)
        self.hint_label = tk.Label(self.frame, text="找出与其他不同的图形", font=('微软雅黑', 11), fg='#888')
        self.hint_label.pack(pady=2)
        self.canvas.bind('<Button-1>', self._on_click)
        self.draw()
    def draw(self):
        self.canvas.delete('all')
        data = self.vm.model.difference_click_data
        if data is None:
            return
        state = self.vm.get_state()
        cols = 3
        size = 80
        pad = 10
        start_x = (self.width - cols * (size + pad)) // 2
        start_y = 20
        for i, img in enumerate(data.images):
            row, col = divmod(i, cols)
            x = start_x + col * (size + pad)
            y = start_y + row * (size + pad)
            if i == data.clicked_index:
                border = '#4CAF50' if state == CaptchaState.SUCCESS else '#f44336'
                self.canvas.create_rectangle(x-2, y-2, x+size+2, y+size+2, outline=border, width=3)
            self.canvas.create_rectangle(x, y, x+size, y+size, fill=img['color'], outline='#ddd', width=1)
            cx, cy = x + size//2, y + size//2
            shape = img['shape']
            if shape == 'circle':
                self.canvas.create_oval(cx-20, cy-20, cx+20, cy+20, fill='white', outline='#333', width=2)
            elif shape == 'square':
                self.canvas.create_rectangle(cx-20, cy-20, cx+20, cy+20, fill='white', outline='#333', width=2)
            elif shape == 'triangle':
                self.canvas.create_polygon(cx, cy-20, cx-20, cy+20, cx+20, cy+20, fill='white', outline='#333', width=2)
    def _on_click(self, event):
        data = self.vm.model.difference_click_data
        if data is None or self.vm.get_state() != CaptchaState.IDLE:
            return
        cols = 3
        size = 80
        pad = 10
        start_x = (self.width - cols * (size + pad)) // 2
        start_y = 20
        for i in range(len(data.images)):
            row, col = divmod(i, cols)
            x = start_x + col * (size + pad)
            y = start_y + row * (size + pad)
            if x <= event.x <= x + size and y <= event.y <= y + size:
                self.vm.click(i)
                break


class NineGridCaptchaView(BaseCaptchaView):
    """九宫格验证码视图"""
    def __init__(self, parent, viewmodel, width=300, height=340):
        self.vm = viewmodel
        super().__init__(parent, viewmodel, width, height)
    def _build_ui(self):
        super()._build_ui()
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="刷新", command=self.reset).pack(side=tk.LEFT, padx=5)
        self.hint_label = tk.Label(self.frame, text="请点击所有动物", font=('微软雅黑', 11), fg='#888')
        self.hint_label.pack(pady=2)
        self.canvas.bind('<Button-1>', self._on_click)
        self.draw()
    def draw(self):
        self.canvas.delete('all')
        data = self.vm.model.nine_grid_data
        if data is None:
            return
        state = self.vm.get_state()
        size = 80
        pad = 5
        start_x = (self.width - 3 * (size + pad)) // 2
        start_y = 20
        for i, grid in enumerate(data.grids):
            row, col = divmod(i, 3)
            x = start_x + col * (size + pad)
            y = start_y + row * (size + pad)
            if i in data.clicked_indices:
                bg = '#4CAF50'
                border = '#2E7D32'
            else:
                bg = '#f5f5f5'
                border = '#ddd'
            self.canvas.create_rectangle(x, y, x+size, y+size, fill=bg, outline=border, width=2)
            self.canvas.create_text(x + size//2, y + size//2, text=grid['animal'], font=('Arial', 24))
        if state == CaptchaState.SUCCESS:
            self.hint_label.config(text='验证成功！', fg='#4CAF50')
        elif state == CaptchaState.FAILED:
            self.hint_label.config(text='验证失败', fg='#f44336')
    def _on_click(self, event):
        data = self.vm.model.nine_grid_data
        if data is None:
            return
        size = 80
        pad = 5
        start_x = (self.width - 3 * (size + pad)) // 2
        start_y = 20
        for i in range(9):
            row, col = divmod(i, 3)
            x = start_x + col * (size + pad)
            y = start_y + row * (size + pad)
            if x <= event.x <= x + size and y <= event.y <= y + size:
                self.vm.click(i)
                break


class SMSCaptchaView(BaseCaptchaView):
    """短信验证码（模拟）视图"""
    def __init__(self, parent, viewmodel, width=320, height=180):
        self.vm = viewmodel
        super().__init__(parent, viewmodel, width, height)
    def _build_ui(self):
        super()._build_ui()
        input_frame = ttk.Frame(self.frame)
        input_frame.pack(pady=5)
        tk.Label(input_frame, text="请输入验证码:", font=('微软雅黑', 11)).pack(side=tk.LEFT, padx=5)
        self.entry = tk.Entry(input_frame, font=('微软雅黑', 14), width=12, justify='center')
        self.entry.pack(side=tk.LEFT, padx=5)
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="验证", command=self._verify).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="刷新", command=self.reset).pack(side=tk.LEFT, padx=5)
        self.entry.bind('<Return>', lambda e: self._verify())
        self.draw()
    def draw(self):
        self.canvas.delete('all')
        data = self.vm.model.sms_data
        if data is None:
            return
        self.canvas.create_rectangle(0, 0, self.width, self.height, fill='#E3F2FD', outline='#BBDEFB')
        self.canvas.create_text(self.width//2, 40, text=data.display_code, font=('微软雅黑', 14, 'bold'), fill='#1565C0')
        self.canvas.create_text(self.width//2, 80, text='【模拟：验证码已发送到您的手机】', font=('微软雅黑', 10), fill='#666')
    def _verify(self):
        user_input = self.entry.get().strip()
        if user_input:
            self.vm.verify(user_input)
            self.entry.delete(0, tk.END)
    def reset(self):
        super().reset()
        self.entry.delete(0, tk.END)


class ScratchCardCaptchaView(BaseCaptchaView):
    """刮刮卡验证码视图"""
    def __init__(self, parent, viewmodel, width=320, height=220):
        self.vm = viewmodel
        super().__init__(parent, viewmodel, width, height)
    def _build_ui(self):
        super()._build_ui()
        input_frame = ttk.Frame(self.frame)
        input_frame.pack(pady=5)
        tk.Label(input_frame, text="刮开涂层后输入:", font=('微软雅黑', 11)).pack(side=tk.LEFT, padx=5)
        self.entry = tk.Entry(input_frame, font=('微软雅黑', 14), width=8, justify='center')
        self.entry.pack(side=tk.LEFT, padx=5)
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="验证", command=self._verify).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="刷新", command=self.reset).pack(side=tk.LEFT, padx=5)
        self.canvas.bind('<Button-1>', self._on_press)
        self.canvas.bind('<B1-Motion>', self._on_drag)
        self.canvas.bind('<ButtonRelease-1>', self._on_release)
        self.draw()
    def draw(self):
        self.canvas.delete('all')
        data = self.vm.model.scratch_card_data
        if data is None:
            return
        cx, cy = self.width//2, self.height//2
        cw, ch = 200, 80
        x1, y1 = cx - cw//2, cy - ch//2
        x2, y2 = cx + cw//2, cy + ch//2
        # 底层：答案
        self.canvas.create_rectangle(x1, y1, x2, y2, fill='#FFF8E1', outline='#FFE082')
        self.canvas.create_text(cx, cy, text=data.answer, font=('Arial', 28, 'bold'), fill='#F57F17')
        # 涂层
        scratched = set()
        for sx, sy in data.scratched:
            for dx in range(-15, 16):
                for dy in range(-15, 16):
                    px, py = int(sx+dx), int(sy+dy)
                    if x1 <= px <= x2 and y1 <= py <= y2:
                        scratched.add((px, py))
        for px in range(int(x1), int(x2)+1):
            for py in range(int(y1), int(y2)+1):
                if (px, py) not in scratched:
                    self.canvas.create_rectangle(px, py, px+1, py+1, fill='#9E9E9E', outline='')
        self.canvas.create_rectangle(x1, y1, x2, y2, outline='#757575', width=2)
    def _on_press(self, event):
        self.vm.start_drag(event.x, event.y)
    def _on_drag(self, event):
        self.vm.drag(event.x, event.y)
    def _on_release(self, event):
        self.vm.end_drag()
    def _verify(self):
        user_input = self.entry.get().strip()
        if user_input:
            self.vm.verify(user_input)
            self.entry.delete(0, tk.END)
    def reset(self):
        super().reset()
        self.entry.delete(0, tk.END)


class AreaClickCaptchaView(BaseCaptchaView):
    """面积验证视图"""
    def __init__(self, parent, viewmodel, width=320, height=240):
        self.vm = viewmodel
        super().__init__(parent, viewmodel, width, height)
    def _build_ui(self):
        super()._build_ui()
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="刷新", command=self.reset).pack(side=tk.LEFT, padx=5)
        self.hint_label = tk.Label(self.frame, text="", font=('微软雅黑', 11), fg='#888')
        self.hint_label.pack(pady=2)
        self.canvas.bind('<Button-1>', self._on_click)
        self.draw()
    def draw(self):
        self.canvas.delete('all')
        data = self.vm.model.area_click_data
        if data is None:
            return
        state = self.vm.get_state()
        self.canvas.create_rectangle(0, 0, self.width, self.height, fill='#f8f9fa', outline='#ddd')
        for i, shape in enumerate(data.shapes):
            self.canvas.create_oval(shape['cx']-shape['r'], shape['cy']-shape['r'], shape['cx']+shape['r'], shape['cy']+shape['r'], fill=shape['color'], outline='#333', width=2)
        if state == CaptchaState.SUCCESS:
            self.hint_label.config(text='验证成功！', fg='#4CAF50')
        elif state == CaptchaState.FAILED:
            self.hint_label.config(text='选择错误', fg='#f44336')
        else:
            target = '最大' if data.target_type == 'largest' else '最小'
            self.hint_label.config(text=f'请点击面积{target}的圆形', fg='#2196F3')
    def _on_click(self, event):
        data = self.vm.model.area_click_data
        if data is None or self.vm.get_state() != CaptchaState.IDLE:
            return
        for i, shape in enumerate(data.shapes):
            dist = ((event.x - shape['cx'])**2 + (event.y - shape['cy'])**2)**0.5
            if dist <= shape['r']:
                self.vm.click(i)
                break


class VoiceCaptchaView(BaseCaptchaView):
    """语音验证码（模拟）视图"""
    def __init__(self, parent, viewmodel, width=320, height=180):
        self.vm = viewmodel
        super().__init__(parent, viewmodel, width, height)
    def _build_ui(self):
        super()._build_ui()
        input_frame = ttk.Frame(self.frame)
        input_frame.pack(pady=5)
        tk.Label(input_frame, text="听到的验证码:", font=('微软雅黑', 11)).pack(side=tk.LEFT, padx=5)
        self.entry = tk.Entry(input_frame, font=('微软雅黑', 14), width=8, justify='center')
        self.entry.pack(side=tk.LEFT, padx=5)
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="验证", command=self._verify).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="刷新", command=self.reset).pack(side=tk.LEFT, padx=5)
        self.entry.bind('<Return>', lambda e: self._verify())
        self.draw()
    def draw(self):
        self.canvas.delete('all')
        data = self.vm.model.voice_data
        if data is None:
            return
        self.canvas.create_rectangle(0, 0, self.width, self.height, fill='#E8F5E9', outline='#C8E6C9')
        self.canvas.create_text(self.width//2, 50, text='[模拟语音播放中...]', font=('微软雅黑', 14, 'bold'), fill='#2E7D32')
        self.canvas.create_text(self.width//2, 90, text=data.display_text, font=('微软雅黑', 10), fill='#666')
    def _verify(self):
        user_input = self.entry.get().strip()
        if user_input:
            self.vm.verify(user_input)
            self.entry.delete(0, tk.END)
    def reset(self):
        super().reset()
        self.entry.delete(0, tk.END)


class FontRecognizeCaptchaView(BaseCaptchaView):
    """字体识别验证码视图"""
    def __init__(self, parent, viewmodel, width=320, height=180):
        self.vm = viewmodel
        super().__init__(parent, viewmodel, width, height)
    def _build_ui(self):
        super()._build_ui()
        input_frame = ttk.Frame(self.frame)
        input_frame.pack(pady=5)
        tk.Label(input_frame, text="请输入字符:", font=('微软雅黑', 11)).pack(side=tk.LEFT, padx=5)
        self.entry = tk.Entry(input_frame, font=('微软雅黑', 14), width=12, justify='center')
        self.entry.pack(side=tk.LEFT, padx=5)
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="验证", command=self._verify).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="刷新", command=self.reset).pack(side=tk.LEFT, padx=5)
        self.entry.bind('<Return>', lambda e: self._verify())
        self.draw()
    def draw(self):
        self.canvas.delete('all')
        data = self.vm.model.font_recognize_data
        if data is None:
            return
        self.canvas.create_rectangle(0, 0, self.width, self.height, fill='#f8f9fa', outline='#ddd')
        for i, (x, y, size, font_name) in enumerate(data.char_positions):
            self.canvas.create_text(x, y, text=data.code[i], font=(font_name, size, 'bold'), fill='#333')
    def _verify(self):
        user_input = self.entry.get().strip()
        if user_input:
            self.vm.verify(user_input)
            self.entry.delete(0, tk.END)
    def reset(self):
        super().reset()
        self.entry.delete(0, tk.END)


class BehaviorMockCaptchaView(BaseCaptchaView):
    """无感验证（模拟）视图"""
    def __init__(self, parent, viewmodel, width=320, height=180):
        self.vm = viewmodel
        super().__init__(parent, viewmodel, width, height)
        self._checking = False
    def _build_ui(self):
        super()._build_ui()
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="开始检测", command=self._start_check).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="刷新", command=self.reset).pack(side=tk.LEFT, padx=5)
        self.draw()
    def draw(self):
        self.canvas.delete('all')
        data = self.vm.model.behavior_data
        if data is None:
            return
        state = self.vm.get_state()
        self.canvas.create_rectangle(0, 0, self.width, self.height, fill='#f5f5f5', outline='#ddd')
        if state == CaptchaState.VERIFYING:
            # 进度条
            bar_w = 200
            bar_h = 20
            bx = (self.width - bar_w) // 2
            by = 60
            self.canvas.create_rectangle(bx, by, bx+bar_w, by+bar_h, fill='white', outline='#ccc')
            fill_w = int(bar_w * data.progress)
            self.canvas.create_rectangle(bx, by, bx+fill_w, by+bar_h, fill='#2196F3', outline='')
            self.canvas.create_text(self.width//2, 110, text='正在分析行为特征...', font=('微软雅黑', 12), fill='#666')
            self.canvas.create_text(self.width//2, 140, text=f'进度: {int(data.progress*100)}%', font=('微软雅黑', 10), fill='#888')
        elif state == CaptchaState.SUCCESS:
            self.canvas.create_text(self.width//2, 80, text='验证通过', font=('微软雅黑', 16, 'bold'), fill='#4CAF50')
            self.canvas.create_text(self.width//2, 120, text=f'行为评分: {data.fake_score:.2f}', font=('微软雅黑', 11), fill='#666')
        elif state == CaptchaState.FAILED:
            self.canvas.create_text(self.width//2, 80, text='验证失败', font=('微软雅黑', 16, 'bold'), fill='#f44336')
            self.canvas.create_text(self.width//2, 120, text=f'行为评分: {data.fake_score:.2f}', font=('微软雅黑', 11), fill='#666')
        else:
            self.canvas.create_text(self.width//2, 80, text='点击「开始检测」进行无感验证', font=('微软雅黑', 12), fill='#666')
    def _start_check(self):
        if self._checking:
            return
        self._checking = True
        self._check_step()
    def _check_step(self):
        if not self._checking:
            return
        result = self.vm.simulate_check()
        state = self.vm.get_state()
        if state == CaptchaState.IDLE or state == CaptchaState.VERIFYING:
            self.canvas.after(500, self._check_step)
        else:
            self._checking = False
    def reset(self):
        self._checking = False
        super().reset()
