"""
人机验证演示系统 - 主窗口
"""
import os
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Optional

from model.captcha_model import CaptchaConfig, CaptchaState, CaptchaResult
from viewmodel.captcha_viewmodel import CaptchaFactory, BaseCaptchaViewModel
from view.captcha_views import (
    BaseCaptchaView, TextCaptchaView, SliderCaptchaView,
    PuzzleCaptchaView, ClickCaptchaView, RotateCaptchaView, DragSortCaptchaView,
    WordOrderCaptchaView, DifferenceClickCaptchaView, NineGridCaptchaView,
    SMSCaptchaView, ScratchCardCaptchaView, AreaClickCaptchaView,
    VoiceCaptchaView, FontRecognizeCaptchaView, BehaviorMockCaptchaView
)


class MainWindow:
    """主窗口"""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.config = CaptchaConfig()
        self._load_config()
        
        self.current_viewmodel: Optional[BaseCaptchaViewModel] = None
        self.current_view: Optional[BaseCaptchaView] = None
        self.views: Dict[str, BaseCaptchaView] = {}
        
        self._setup_window()
        self._build_ui()
        self._show_captcha('text')
    
    def _load_config(self):
        """加载配置文件"""
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'captcha_config.json')
        config_path = os.path.abspath(config_path)
        if os.path.exists(config_path):
            self.config.load(config_path)
        else:
            print(f"警告: 配置文件未找到: {config_path}")
    
    def _setup_window(self):
        """设置窗口"""
        app_cfg = self.config.get('app', {})
        self.root.title(app_cfg.get('title', '人机验证演示系统'))
        self.root.geometry(f"{app_cfg.get('width', 900)}x{app_cfg.get('height', 680)}")
        self.root.minsize(850, 600)
        self.root.configure(bg='#fafafa')
        
        # 设置样式
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Title.TLabel', font=('微软雅黑', 18, 'bold'), foreground='#333')
        style.configure('Subtitle.TLabel', font=('微软雅黑', 10), foreground='#666')
        style.configure('Type.TButton', font=('微软雅黑', 11))
        style.configure('Active.Type.TButton', font=('微软雅黑', 11, 'bold'))
    
    def _build_ui(self):
        """构建UI"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题区域
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(
            title_frame, text='人机验证演示系统',
            style='Title.TLabel'
        ).pack(anchor=tk.W)
        
        ttk.Label(
            title_frame,
            text='点击下方按钮切换不同类型的人机验证，体验各类验证码的交互方式',
            style='Subtitle.TLabel'
        ).pack(anchor=tk.W, pady=(5, 0))
        
        # 分隔线
        ttk.Separator(main_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
        # 左侧：验证码类型选择（可滚动）
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 15))

        # 标题
        ttk.Label(left_frame, text='验证码类型', font=('微软雅黑', 12, 'bold')).pack(anchor=tk.W, pady=(0, 10))

        # 可滚动的画布区域
        left_canvas = tk.Canvas(left_frame, highlightthickness=0, bg='#fafafa')
        left_scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=left_canvas.yview)
        left_scrollable = ttk.Frame(left_canvas)

        left_scrollable.bind(
            '<Configure>',
            lambda e: left_canvas.configure(scrollregion=left_canvas.bbox('all'))
        )

        canvas_window = left_canvas.create_window((0, 0), window=left_scrollable, anchor='nw')
        left_canvas.configure(yscrollcommand=left_scrollbar.set)

        # Canvas 宽度变化时同步内部 frame 宽度
        def _on_canvas_configure(event):
            left_canvas.itemconfig(canvas_window, width=event.width)

        left_canvas.bind('<Configure>', _on_canvas_configure)

        left_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        left_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 鼠标滚轮支持
        def _on_mousewheel(event):
            left_canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')

        left_canvas.bind('<Enter>', lambda e: left_canvas.bind_all('<MouseWheel>', _on_mousewheel))
        left_canvas.bind('<Leave>', lambda e: left_canvas.unbind_all('<MouseWheel>'))

        # 类型按钮
        self.type_buttons: Dict[str, ttk.Button] = {}
        types = self.config.get('captcha_types', [])

        for t in types:
            btn_frame = ttk.Frame(left_scrollable)
            btn_frame.pack(fill=tk.X, pady=2)

            btn = ttk.Button(
                btn_frame,
                text=f"  {t['name']}",
                command=lambda tid=t['id']: self._show_captcha(tid)
            )
            btn.pack(fill=tk.X)
            self.type_buttons[t['id']] = btn

            # 难度标签
            diff_color = {'简单': '#4CAF50', '中等': '#FF9800', '困难': '#f44336'}.get(t['difficulty'], '#888')
            tk.Label(
                btn_frame, text=t['difficulty'],
                font=('微软雅黑', 8), fg=diff_color
            ).pack(side=tk.RIGHT, padx=3)

        # 信息面板
        info_frame = ttk.LabelFrame(left_scrollable, text='说明', padding=10)
        info_frame.pack(fill=tk.X, pady=(10, 0))

        self.info_label = tk.Label(
            info_frame, text='', font=('微软雅黑', 10),
            fg='#555', wraplength=165, justify=tk.LEFT
        )
        self.info_label.pack(fill=tk.X)

        # 状态面板
        self.status_frame = ttk.LabelFrame(left_scrollable, text='验证状态', padding=10)
        self.status_frame.pack(fill=tk.X, pady=(8, 0))

        self.status_label = tk.Label(
            self.status_frame, text='待验证',
            font=('微软雅黑', 11), fg='#888'
        )
        self.status_label.pack()

        self.score_label = tk.Label(
            self.status_frame, text='',
            font=('微软雅黑', 9), fg='#666'
        )
        self.score_label.pack()
        
        # 右侧：验证码展示区域
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 验证码标题
        self.captcha_title = ttk.Label(
            right_frame, text='',
            font=('微软雅黑', 14, 'bold'), foreground='#333'
        )
        self.captcha_title.pack(anchor=tk.W, pady=(0, 5))
        
        # Canvas 容器
        self.view_container = ttk.Frame(right_frame)
        self.view_container.pack(fill=tk.BOTH, expand=True)
        
        # 底部：全局按钮
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
        
        ttk.Separator(bottom_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(
            bottom_frame, text='关于',
            command=self._show_about
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            bottom_frame, text='退出',
            command=self.root.quit
        ).pack(side=tk.RIGHT, padx=5)
    
    def _show_captcha(self, captcha_type: str):
        """显示指定类型的验证码"""
        # 更新按钮状态
        for tid, btn in self.type_buttons.items():
            if tid == captcha_type:
                btn.configure(text=f"▶ {CaptchaFactory.get_types().get(tid, tid)}")
            else:
                btn.configure(text=f"  {CaptchaFactory.get_types().get(tid, tid)}")
        
        # 清除当前视图
        for widget in self.view_container.winfo_children():
            widget.destroy()
        
        # 创建新的 ViewModel
        self.current_viewmodel = CaptchaFactory.create(captcha_type, self.config)
        
        # 设置结果回调
        self.current_viewmodel.on_result = self._on_result
        
        # 创建视图
        view_class = {
            'text': TextCaptchaView,
            'slider': SliderCaptchaView,
            'puzzle': PuzzleCaptchaView,
            'click': ClickCaptchaView,
            'rotate': RotateCaptchaView,
            'drag_sort': DragSortCaptchaView,
            'word_order': WordOrderCaptchaView,
            'difference_click': DifferenceClickCaptchaView,
            'nine_grid': NineGridCaptchaView,
            'sms_mock': SMSCaptchaView,
            'scratch_card': ScratchCardCaptchaView,
            'area_click': AreaClickCaptchaView,
            'voice_mock': VoiceCaptchaView,
            'font_recognize': FontRecognizeCaptchaView,
            'behavior_mock': BehaviorMockCaptchaView,
        }.get(captcha_type)
        
        if view_class:
            self.current_view = view_class(self.view_container, self.current_viewmodel)
            self.current_view.pack(fill=tk.BOTH, expand=True)
        
        # 生成验证码
        self.current_viewmodel.create()
        
        # 更新信息
        types = self.config.get('captcha_types', [])
        for t in types:
            if t['id'] == captcha_type:
                self.captcha_title.config(text=t['name'])
                self.info_label.config(text=f"{t['description']}\n\n难度: {t['difficulty']}")
                break
        
        self._update_status()
    
    def _on_result(self, result: CaptchaResult):
        """处理验证结果"""
        self._update_status()
    
    def _update_status(self):
        """更新状态显示"""
        if self.current_viewmodel is None:
            return
        
        state = self.current_viewmodel.get_state()
        result = self.current_viewmodel.get_result()
        
        state_text = {
            CaptchaState.IDLE: '待验证',
            CaptchaState.VERIFYING: '验证中...',
            CaptchaState.SUCCESS: '✓ 验证通过',
            CaptchaState.FAILED: '✗ 验证失败',
            CaptchaState.EXPIRED: '已过期',
        }.get(state, '未知')
        
        state_color = {
            CaptchaState.IDLE: '#888',
            CaptchaState.VERIFYING: '#2196F3',
            CaptchaState.SUCCESS: '#4CAF50',
            CaptchaState.FAILED: '#f44336',
            CaptchaState.EXPIRED: '#FF9800',
        }.get(state, '#888')
        
        self.status_label.config(text=state_text, fg=state_color)
        
        if result:
            score_text = f"尝试次数: {result.attempts}/{result.max_attempts}"
            if result.score > 0:
                score_text += f"  |  得分: {result.score:.2f}"
            if result.time_elapsed > 0:
                score_text += f"  |  用时: {result.time_elapsed:.1f}s"
            self.score_label.config(text=score_text)
        else:
            self.score_label.config(text='')
    
    def _show_about(self):
        """显示关于信息"""
        messagebox.showinfo(
            '关于',
            '人机验证演示系统 v2.0\n\n'
            '本程序用于演示各类人机验证（CAPTCHA）的交互方式。\n'
            '涵盖市面上常见的验证码类型，包括文字、滑块、拼图、\n'
            '点击、旋转、拖拽排序、语序点选、差异点击、九宫格、\n'
            '短信模拟、刮刮卡、面积验证、语音模拟、字体识别、\n'
            '无感验证等。\n\n'
            '技术栈: Python + Tkinter (Canvas)\n'
            '架构模式: MVVM\n'
            '配置分离: JSON'
        )


def run():
    """运行程序"""
    root = tk.Tk()
    app = MainWindow(root)
    root.mainloop()


if __name__ == '__main__':
    run()
