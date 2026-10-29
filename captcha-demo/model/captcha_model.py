"""
人机验证 - Model 层
定义各类验证码的数据结构和状态
"""
import json
import random
import math
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any
from enum import Enum, auto


class CaptchaState(Enum):
    """验证码状态枚举"""
    IDLE = auto()        # 未开始/待验证
    VERIFYING = auto()   # 验证中
    SUCCESS = auto()     # 验证成功
    FAILED = auto()      # 验证失败
    EXPIRED = auto()     # 已过期


class CaptchaType(Enum):
    """验证码类型枚举"""
    TEXT = "text"
    SLIDER = "slider"
    PUZZLE = "puzzle"
    CLICK = "click"
    ROTATE = "rotate"
    DRAG_SORT = "drag_sort"
    WORD_ORDER = "word_order"
    DIFFERENCE_CLICK = "difference_click"
    NINE_GRID = "nine_grid"
    SMS_MOCK = "sms_mock"
    SCRATCH_CARD = "scratch_card"
    AREA_CLICK = "area_click"
    VOICE_MOCK = "voice_mock"
    FONT_RECOGNIZE = "font_recognize"
    BEHAVIOR_MOCK = "behavior_mock"


@dataclass
class TextCaptchaData:
    """文字验证码数据"""
    code: str = ""
    noise_lines: List[Tuple[float, float, float, float]] = field(default_factory=list)
    noise_dots: List[Tuple[float, float]] = field(default_factory=list)
    char_positions: List[Tuple[float, float, int, str]] = field(default_factory=list)
    bg_color: str = "#f8f9fa"
    user_input: str = ""


@dataclass
class SliderCaptchaData:
    """滑块验证码数据（缺口+拼图块模式）"""
    target_x: float = 0.0       # 缺口目标X位置
    piece_x: float = 0.0        # 拼图块当前X位置（在图片区域内）
    slider_x: float = 0.0       # 下方滑块X位置（相对轨道）
    is_dragging: bool = False
    track_width: float = 320
    track_height: float = 180
    piece_width: float = 60     # 拼图块宽度
    piece_height: float = 50    # 拼图块高度
    tolerance: float = 8
    gap_y: float = 0.0          # 缺口Y位置
    stripes: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class PuzzleCaptchaData:
    """拼图验证码数据（数字华容道）"""
    grid: List[int] = field(default_factory=list)
    grid_size: int = 3
    piece_size: int = 60
    tolerance: int = 5
    blank_idx: int = 8
    colors: List[str] = field(default_factory=list)
    bg_color: str = "#f5f5f5"
    grid_color: str = "#ddd"


@dataclass
class ClickCaptchaData:
    """点击验证码数据"""
    targets: List[str] = field(default_factory=list)
    clicks: List[Tuple[float, float]] = field(default_factory=list)
    items: List[Dict[str, Any]] = field(default_factory=list)
    target_count: int = 4
    current_target_index: int = 0


@dataclass
class RotateCaptchaData:
    """旋转验证码数据"""
    target_angle: float = 0.0
    current_angle: float = 0.0
    is_rotating: bool = False
    image_type: str = "arrow"
    snap_angle: float = 5


@dataclass
class DragSortCaptchaData:
    """拖拽排序验证码数据"""
    items: List[Dict[str, Any]] = field(default_factory=list)
    correct_order: List[int] = field(default_factory=list)
    current_order: List[int] = field(default_factory=list)
    dragging_item: Optional[int] = None
    drag_offset: Tuple[float, float] = (0, 0)
    item_count: int = 5


@dataclass
class WordOrderCaptchaData:
    """语序点选验证码数据"""
    words: List[str] = field(default_factory=list)
    shuffled_words: List[str] = field(default_factory=list)
    clicked_order: List[int] = field(default_factory=list)
    target_count: int = 4
    instruction: str = "请按正确语序依次点击："


@dataclass
class DifferenceClickCaptchaData:
    """差异点击验证码数据"""
    images: List[Dict[str, Any]] = field(default_factory=list)
    different_index: int = 0
    clicked_index: int = -1
    grid_cols: int = 3
    grid_rows: int = 3


@dataclass
class NineGridCaptchaData:
    """九宫格验证码数据"""
    grids: List[Dict[str, Any]] = field(default_factory=list)
    target_indices: List[int] = field(default_factory=list)
    clicked_indices: List[int] = field(default_factory=list)
    instruction: str = ""
    target_text: str = ""


@dataclass
class SMSCaptchaData:
    """短信验证码（模拟）数据"""
    code: str = ""
    user_input: str = ""
    display_code: str = ""


@dataclass
class ScratchCardCaptchaData:
    """刮刮卡验证码数据"""
    answer: str = ""
    user_input: str = ""
    scratched: List[Tuple[float, float]] = field(default_factory=list)
    threshold: float = 0.5
    card_width: float = 280
    card_height: float = 120


@dataclass
class AreaClickCaptchaData:
    """面积验证数据"""
    shapes: List[Dict[str, Any]] = field(default_factory=list)
    target_type: str = "largest"
    clicked_index: int = -1


@dataclass
class VoiceCaptchaData:
    """语音验证码（模拟）数据"""
    code: str = ""
    user_input: str = ""
    display_text: str = ""


@dataclass
class FontRecognizeCaptchaData:
    """字体识别验证码数据"""
    code: str = ""
    user_input: str = ""
    char_positions: List[Tuple[float, float, int, str]] = field(default_factory=list)


@dataclass
class BehaviorMockCaptchaData:
    """无感验证（模拟）数据"""
    fake_score: float = 0.0
    status: str = "analyzing"
    progress: float = 0.0


@dataclass
class CaptchaResult:
    """验证结果"""
    success: bool = False
    message: str = ""
    score: float = 0.0
    attempts: int = 0
    max_attempts: int = 3
    time_elapsed: float = 0.0


class CaptchaConfig:
    """验证码配置管理器"""
    
    _instance = None
    _config: Dict[str, Any] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def load(self, config_path: str):
        with open(config_path, 'r', encoding='utf-8') as f:
            self._config = json.load(f)
    
    def get(self, key: str, default=None):
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    @property
    def config(self) -> Dict[str, Any]:
        return self._config


class CaptchaModel:
    """
    验证码数据模型基类
    管理验证码的状态和数据
    """
    
    def __init__(self, captcha_type: CaptchaType):
        self.captcha_type = captcha_type
        self.state = CaptchaState.IDLE
        self.result = CaptchaResult()
        self.created_at = 0.0
        self.expires_in = 300  # 5分钟过期
        
        # 各类验证码专用数据
        self.text_data: Optional[TextCaptchaData] = None
        self.slider_data: Optional[SliderCaptchaData] = None
        self.puzzle_data: Optional[PuzzleCaptchaData] = None
        self.click_data: Optional[ClickCaptchaData] = None
        self.rotate_data: Optional[RotateCaptchaData] = None
        self.drag_sort_data: Optional[DragSortCaptchaData] = None
        self.word_order_data: Optional['WordOrderCaptchaData'] = None
        self.difference_click_data: Optional['DifferenceClickCaptchaData'] = None
        self.nine_grid_data: Optional['NineGridCaptchaData'] = None
        self.sms_data: Optional['SMSCaptchaData'] = None
        self.scratch_card_data: Optional['ScratchCardCaptchaData'] = None
        self.area_click_data: Optional['AreaClickCaptchaData'] = None
        self.voice_data: Optional['VoiceCaptchaData'] = None
        self.font_recognize_data: Optional['FontRecognizeCaptchaData'] = None
        self.behavior_data: Optional['BehaviorMockCaptchaData'] = None
    
    def reset(self):
        """重置状态"""
        self.state = CaptchaState.IDLE
        self.result = CaptchaResult()
        
    def generate(self, config: CaptchaConfig):
        """生成验证码数据 - 由子类实现"""
        raise NotImplementedError
        
    def verify(self, *args, **kwargs) -> CaptchaResult:
        """验证用户输入 - 由子类实现"""
        raise NotImplementedError


class TextCaptchaModel(CaptchaModel):
    """文字验证码模型"""
    
    def __init__(self):
        super().__init__(CaptchaType.TEXT)
        self.chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        
    def generate(self, config: CaptchaConfig):
        cfg = config.get('text_captcha', {})
        data = TextCaptchaData()
        
        char_count = cfg.get('char_count', 4)
        data.code = ''.join(random.choice(self.chars) for _ in range(char_count))
        data.bg_color = random.choice(cfg.get('bg_colors', ['#f8f9fa']))
        
        width = cfg.get('width', 280)
        height = cfg.get('height', 100)
        
        # 生成噪点
        for _ in range(cfg.get('noise_dots', 100)):
            data.noise_dots.append((
                random.uniform(0, width),
                random.uniform(0, height)
            ))
        
        # 生成干扰线
        for _ in range(cfg.get('noise_lines', 8)):
            data.noise_lines.append((
                random.uniform(0, width),
                random.uniform(0, height),
                random.uniform(0, width),
                random.uniform(0, height)
            ))
        
        # 生成字符位置和样式
        colors = cfg.get('colors', ['#1a1a2e'])
        font_min = cfg.get('font_size_min', 36)
        font_max = cfg.get('font_size_max', 48)
        
        step = width / (char_count + 1)
        for i, ch in enumerate(data.code):
            x = step * (i + 1)
            y = random.uniform(height * 0.35, height * 0.65)
            size = random.randint(font_min, font_max)
            color = random.choice(colors)
            data.char_positions.append((x, y, size, color))
        
        self.text_data = data
        self.state = CaptchaState.IDLE
        return data
    
    def verify(self, user_input: str) -> CaptchaResult:
        if self.text_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        
        self.result.attempts += 1
        self.text_data.user_input = user_input
        
        if user_input.upper() == self.text_data.code:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            if self.result.attempts >= self.result.max_attempts:
                self.state = CaptchaState.FAILED
                self.result.message = f"验证失败，已超过最大尝试次数({self.result.max_attempts}次)"
            else:
                self.state = CaptchaState.IDLE
                self.result.message = f"验证码错误，还剩{self.result.max_attempts - self.result.attempts}次机会"
        
        return self.result


class SliderCaptchaModel(CaptchaModel):
    """滑块验证码模型"""
    
    def __init__(self):
        super().__init__(CaptchaType.SLIDER)
        
    def generate(self, config: CaptchaConfig):
        cfg = config.get('slider_captcha', {})
        data = SliderCaptchaData()
        
        data.track_width = cfg.get('width', 320)
        data.track_height = cfg.get('height', 180)
        data.piece_width = cfg.get('piece_width', 60)
        data.piece_height = cfg.get('piece_height', 50)
        data.tolerance = cfg.get('tolerance', 8)
        
        # 缺口位置（在图片内部）
        data.gap_y = random.uniform(30, data.track_height - data.piece_height - 30)
        data.target_x = random.uniform(80, data.track_width - data.piece_width - 80)
        
        # 拼图块初始位置在图片最左侧
        data.piece_x = 0
        data.slider_x = 0
        
        # 生成彩色条纹（模拟图片）
        stripe_colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#FF9F43', '#A29BFE', '#FF6B9D', '#C44569']
        sh = data.track_height / len(stripe_colors)
        data.stripes = []
        for i, color in enumerate(stripe_colors):
            data.stripes.append({'y': i * sh, 'height': sh, 'color': color})
        
        self.slider_data = data
        self.state = CaptchaState.IDLE
        return data
    
    def verify(self, position: float) -> CaptchaResult:
        if self.slider_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        
        self.result.attempts += 1
        diff = abs(position - self.slider_data.target_x)
        
        if diff <= self.slider_data.tolerance:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = max(0, 1.0 - diff / self.slider_data.tolerance * 0.3)
            # 成功后吸附到正确位置
            self.slider_data.piece_x = self.slider_data.target_x
            self.slider_data.slider_x = self.slider_data.target_x
        else:
            if self.result.attempts >= self.result.max_attempts:
                self.state = CaptchaState.FAILED
                self.result.message = "验证失败，已超过最大尝试次数"
            else:
                self.state = CaptchaState.IDLE
                self.result.message = f"位置偏差过大，还剩{self.result.max_attempts - self.result.attempts}次机会"
        
        return self.result


class PuzzleCaptchaModel(CaptchaModel):
    """拼图验证码模型（数字华容道）"""
    
    def __init__(self):
        super().__init__(CaptchaType.PUZZLE)
        
    def generate(self, config: CaptchaConfig):
        cfg = config.get('puzzle_captcha', {})
        data = PuzzleCaptchaData()
        
        data.grid_size = cfg.get('grid_size', 3)
        data.piece_size = cfg.get('piece_size', 60)
        data.tolerance = cfg.get('tolerance', 5)
        data.colors = cfg.get('piece_colors', ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#FF9F43', '#A29BFE'])
        data.bg_color = cfg.get('bg_color', '#f5f5f5')
        data.grid_color = cfg.get('grid_color', '#ddd')
        
        total = data.grid_size * data.grid_size
        # 初始化：[1,2,3,4,5,6,7,8,0]
        grid = list(range(1, total)) + [0]
        blank_idx = total - 1
        
        # 随机打乱（通过模拟合法移动保证可解，只打乱5步保证简单）
        for _ in range(5):
            neighbors = []
            row, col = divmod(blank_idx, data.grid_size)
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = row + dr, col + dc
                if 0 <= nr < data.grid_size and 0 <= nc < data.grid_size:
                    neighbors.append(nr * data.grid_size + nc)
            if neighbors:
                swap_idx = random.choice(neighbors)
                grid[blank_idx], grid[swap_idx] = grid[swap_idx], grid[blank_idx]
                blank_idx = swap_idx
        
        data.grid = grid
        data.blank_idx = blank_idx
        
        self.puzzle_data = data
        self.state = CaptchaState.IDLE
        return data
    
    def move(self, idx: int) -> bool:
        """点击idx位置的块，若与空白相邻则交换。返回是否成功移动。"""
        if self.puzzle_data is None:
            return False
        
        data = self.puzzle_data
        blank_idx = data.blank_idx
        
        if idx == blank_idx:
            return False
        
        row, col = divmod(idx, data.grid_size)
        brow, bcol = divmod(blank_idx, data.grid_size)
        
        if abs(row - brow) + abs(col - bcol) == 1:
            data.grid[idx], data.grid[blank_idx] = data.grid[blank_idx], data.grid[idx]
            data.blank_idx = idx
            return True
        return False
    
    def verify(self) -> CaptchaResult:
        if self.puzzle_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        
        data = self.puzzle_data
        total = data.grid_size * data.grid_size
        expected = list(range(1, total)) + [0]
        
        if data.grid == expected:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            self.result.attempts += 1
            if self.result.attempts >= self.result.max_attempts:
                self.state = CaptchaState.FAILED
                self.result.message = "验证失败，已超过最大尝试次数"
            else:
                self.state = CaptchaState.IDLE
                self.result.message = f"拼图未完成，还剩{self.result.max_attempts - self.result.attempts}次机会"
        
        return self.result


class ClickCaptchaModel(CaptchaModel):
    """点击验证码模型"""
    
    def __init__(self):
        super().__init__(CaptchaType.CLICK)
        self.chars_pool = "一二三四五六七八九十甲乙丙丁"
        
    def generate(self, config: CaptchaConfig):
        cfg = config.get('click_captcha', {})
        data = ClickCaptchaData()
        
        data.target_count = cfg.get('target_count', 4)
        width = cfg.get('width', 320)
        height = cfg.get('height', 220)
        
        # 选择目标字符
        targets = random.sample(self.chars_pool, data.target_count)
        data.targets = targets
        data.current_target_index = 0
        data.clicks = []
        
        # 在画布上随机放置字符（包含目标字符和干扰字符）
        all_chars = targets + random.sample(
            [c for c in self.chars_pool if c not in targets], 
            min(6, len(self.chars_pool) - data.target_count)
        )
        colors = cfg.get('colors', ['#e74c3c'])
        
        # 随机位置，确保不重叠太多
        positions = []
        for _ in range(len(all_chars)):
            for _attempt in range(50):
                x = random.uniform(40, width - 40)
                y = random.uniform(50, height - 30)
                # 检查重叠
                overlap = False
                for px, py in positions:
                    if abs(x - px) < 35 and abs(y - py) < 35:
                        overlap = True
                        break
                if not overlap:
                    positions.append((x, y))
                    break
            else:
                positions.append((random.uniform(40, width - 40), random.uniform(50, height - 30)))
        
        for i, ch in enumerate(all_chars):
            is_target = ch in targets
            target_order = targets.index(ch) if is_target else -1
            data.items.append({
                'char': ch,
                'x': positions[i][0],
                'y': positions[i][1],
                'color': random.choice(colors),
                'is_target': is_target,
                'target_order': target_order,
                'clicked': False,
                'size': cfg.get('char_size', 28)
            })
        
        self.click_data = data
        self.state = CaptchaState.IDLE
        return data
    
    def verify(self, click_x: float, click_y: float) -> CaptchaResult:
        if self.click_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        
        data = self.click_data
        
        # 找到点击的字符
        clicked_item = None
        for item in data.items:
            dist = math.sqrt((click_x - item['x']) ** 2 + (click_y - item['y']) ** 2)
            if dist < 25:
                clicked_item = item
                break
        
        if clicked_item is None:
            self.result.attempts += 1
            if self.result.attempts >= self.result.max_attempts:
                self.state = CaptchaState.FAILED
                self.result.message = "验证失败，点击无效区域次数过多"
            else:
                self.result.message = "未点击到有效目标"
            return self.result
        
        if not clicked_item['is_target']:
            self.result.attempts += 1
            if self.result.attempts >= self.result.max_attempts:
                self.state = CaptchaState.FAILED
                self.result.message = "验证失败，点击了错误目标"
            else:
                self.result.message = f"点击了错误目标，还剩{self.result.max_attempts - self.result.attempts}次机会"
            return self.result
        
        # 检查顺序
        if clicked_item['target_order'] != data.current_target_index:
            self.result.attempts += 1
            if self.result.attempts >= self.result.max_attempts:
                self.state = CaptchaState.FAILED
                self.result.message = "验证失败，点击顺序错误"
            else:
                self.result.message = f"点击顺序错误，还剩{self.result.max_attempts - self.result.attempts}次机会"
            data.current_target_index = 0
            for item in data.items:
                item['clicked'] = False
            return self.result
        
        clicked_item['clicked'] = True
        data.current_target_index += 1
        data.clicks.append((click_x, click_y))
        
        if data.current_target_index >= len(data.targets):
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            next_target = data.targets[data.current_target_index]
            self.result.message = f"正确！请继续点击「{next_target}」"
        
        return self.result


class RotateCaptchaModel(CaptchaModel):
    """旋转验证码模型"""
    
    def __init__(self):
        super().__init__(CaptchaType.ROTATE)
        
    def generate(self, config: CaptchaConfig):
        cfg = config.get('rotate_captcha', {})
        data = RotateCaptchaData()
        
        data.target_angle = 0.0
        data.current_angle = random.uniform(30, 330)
        data.snap_angle = cfg.get('snap_angle', 5)
        data.image_type = random.choice(['arrow', 'square', 'triangle', 'cross'])
        
        self.rotate_data = data
        self.state = CaptchaState.IDLE
        return data
    
    def verify(self, angle: float) -> CaptchaResult:
        if self.rotate_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        
        self.result.attempts += 1
        diff = abs(angle % 360)
        if diff > 180:
            diff = 360 - diff
        
        if diff <= self.rotate_data.snap_angle:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = max(0, 1.0 - diff / self.rotate_data.snap_angle * 0.5)
        else:
            if self.result.attempts >= self.result.max_attempts:
                self.state = CaptchaState.FAILED
                self.result.message = "验证失败，已超过最大尝试次数"
            else:
                self.state = CaptchaState.IDLE
                self.result.message = f"旋转角度偏差 {diff:.1f}°，还剩{self.result.max_attempts - self.result.attempts}次机会"
        
        return self.result


class DragSortCaptchaModel(CaptchaModel):
    """拖拽排序验证码模型"""

    def __init__(self):
        super().__init__(CaptchaType.DRAG_SORT)

    def generate(self, config: CaptchaConfig):
        cfg = config.get('drag_sort_captcha', {})
        data = DragSortCaptchaData()
        data.item_count = cfg.get('item_count', 5)
        item_w = cfg.get('item_width', 70)
        item_h = cfg.get('item_height', 70)
        spacing = cfg.get('item_spacing', 10)
        cw = cfg.get('width', 400)
        ch = cfg.get('height', 150)
        colors = cfg.get('colors', ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7"])

        start_x = (cw - (data.item_count * item_w + (data.item_count - 1) * spacing)) // 2
        start_y = (ch - item_h) // 2

        data.correct_order = list(range(data.item_count))
        shuffled = data.correct_order.copy()
        random.shuffle(shuffled)
        while shuffled == data.correct_order and data.item_count > 1:
            random.shuffle(shuffled)
        data.current_order = shuffled.copy()

        items = []
        for i, idx in enumerate(shuffled):
            items.append({
                'id': idx,
                'label': str(idx + 1),
                'current_x': start_x + i * (item_w + spacing),
                'current_y': start_y,
                'width': item_w,
                'height': item_h,
                'color': colors[idx % len(colors)],
            })
        data.items = items
        data.dragging_item = None
        data.drag_offset = (0, 0)

        self.drag_sort_data = data
        self.state = CaptchaState.IDLE
        return data

    def verify(self) -> CaptchaResult:
        if self.drag_sort_data is None:
            return CaptchaResult(success=False, message="验证码未生成")

        self.result.attempts += 1

        # 根据当前位置计算顺序
        cfg = self.config
        if cfg is None:
            cfg = CaptchaConfig()
        scfg = cfg.get('drag_sort_captcha', {})
        item_w = scfg.get('item_width', 70)
        spacing = scfg.get('item_spacing', 10)
        cw = scfg.get('width', 400)
        start_x = (cw - (self.drag_sort_data.item_count * item_w + (self.drag_sort_data.item_count - 1) * spacing)) // 2

        # 按x坐标排序得到当前顺序
        sorted_items = sorted(self.drag_sort_data.items, key=lambda it: it['current_x'])
        current_ids = [it['id'] for it in sorted_items]

        if current_ids == self.drag_sort_data.correct_order:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            if self.result.attempts >= self.result.max_attempts:
                self.state = CaptchaState.FAILED
                self.result.message = "验证失败，已超过最大尝试次数"
            else:
                self.state = CaptchaState.IDLE
                self.result.message = f"排序不正确，还剩{self.result.max_attempts - self.result.attempts}次机会"

        return self.result


# ========== 新增验证码 Model ==========

class WordOrderCaptchaModel(CaptchaModel):
    """语序点选验证码模型"""
    def __init__(self):
        super().__init__(CaptchaType.WORD_ORDER)
        self.word_pool = [
            ["我", "爱", "中国", "编程"],
            ["今天", "天气", "真", "好"],
            ["人机", "验证", "很", "有趣"],
            ["Python", "是", "一门", "编程语言"],
            ["验证码", "可以", "防止", "机器人"],
        ]
    def generate(self, config: CaptchaConfig):
        data = WordOrderCaptchaData()
        sentence = random.choice(self.word_pool)
        data.words = sentence.copy()
        data.target_count = len(sentence)
        data.shuffled_words = sentence.copy()
        random.shuffle(data.shuffled_words)
        data.clicked_order = []
        self.word_order_data = data
        self.state = CaptchaState.IDLE
        return data
    def verify(self, clicked_index: int) -> 'CaptchaResult':
        if not hasattr(self, 'word_order_data') or self.word_order_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        data = self.word_order_data
        data.clicked_order.append(clicked_index)
        self.result.attempts += 1
        expected_word = data.words[len(data.clicked_order) - 1]
        actual_word = data.shuffled_words[clicked_index]
        if actual_word != expected_word:
            self.state = CaptchaState.FAILED
            self.result.success = False
            self.result.message = f"顺序错误，应是「{expected_word}」"
            data.clicked_order = []
            return self.result
        if len(data.clicked_order) >= data.target_count:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            next_word = data.words[len(data.clicked_order)]
            self.result.message = f"正确！请继续点击「{next_word}」"
        return self.result


class DifferenceClickCaptchaModel(CaptchaModel):
    """差异点击验证码模型"""
    def __init__(self):
        super().__init__(CaptchaType.DIFFERENCE_CLICK)
    def generate(self, config: CaptchaConfig):
        data = DifferenceClickCaptchaData()
        data.grid_cols = 3
        data.grid_rows = 3
        data.different_index = random.randint(0, 8)
        shapes = ["circle", "square", "triangle"]
        normal_shape = random.choice(shapes)
        different_shape = random.choice([s for s in shapes if s != normal_shape])
        colors = ["#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7", "#DDA0DD", "#FF9F43", "#A29BFE", "#FF6B9D", "#C44569"]
        for i in range(9):
            data.images.append({
                'shape': normal_shape if i != data.different_index else different_shape,
                'color': colors[i],
                'label': f'格{i+1}'
            })
        data.clicked_index = -1
        self.difference_click_data = data
        self.state = CaptchaState.IDLE
        return data
    def verify(self, clicked_index: int) -> 'CaptchaResult':
        if not hasattr(self, 'difference_click_data') or self.difference_click_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        data = self.difference_click_data
        data.clicked_index = clicked_index
        self.result.attempts += 1
        if clicked_index == data.different_index:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            if self.result.attempts >= self.result.max_attempts:
                self.state = CaptchaState.FAILED
                self.result.message = "验证失败"
            else:
                self.state = CaptchaState.IDLE
                self.result.message = f"不是这里，还剩{self.result.max_attempts - self.result.attempts}次"
        return self.result


class NineGridCaptchaModel(CaptchaModel):
    """九宫格验证码模型"""
    def __init__(self):
        super().__init__(CaptchaType.NINE_GRID)
    def generate(self, config: CaptchaConfig):
        data = NineGridCaptchaData()
        data.target_text = "动物"
        data.instruction = "请点击所有动物"
        animals = ["dog", "cat", "bird", "fish", "rabbit", "fox", "bear", "deer", "monkey"]
        selected = animals.copy()
        random.shuffle(selected)
        data.grids = []
        data.target_indices = []
        for i, animal in enumerate(selected[:9]):
            is_target = animal in animals[:3]
            if is_target:
                data.target_indices.append(i)
            data.grids.append({'index': i, 'animal': animal, 'is_target': is_target})
        data.clicked_indices = []
        self.nine_grid_data = data
        self.state = CaptchaState.IDLE
        return data
    def verify(self, clicked_index: int) -> 'CaptchaResult':
        if not hasattr(self, 'nine_grid_data') or self.nine_grid_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        data = self.nine_grid_data
        if clicked_index in data.clicked_indices:
            return self.result
        data.clicked_indices.append(clicked_index)
        self.result.attempts += 1
        all_clicked = all(idx in data.clicked_indices for idx in data.target_indices)
        if all_clicked:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            remaining = [idx for idx in data.target_indices if idx not in data.clicked_indices]
            self.result.message = f"已选 {len(data.clicked_indices)}，还需选择 {len(remaining)} 个"
        return self.result


class SMSCaptchaModel(CaptchaModel):
    """短信验证码（模拟）模型"""
    def __init__(self):
        super().__init__(CaptchaType.SMS_MOCK)
    def generate(self, config: CaptchaConfig):
        data = SMSCaptchaData()
        data.code = ''.join(random.choices('0123456789', k=6))
        data.display_code = f"【模拟短信】您的验证码是：{data.code}"
        data.user_input = ""
        self.sms_data = data
        self.state = CaptchaState.IDLE
        return data
    def verify(self, user_input: str) -> 'CaptchaResult':
        if not hasattr(self, 'sms_data') or self.sms_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        data = self.sms_data
        data.user_input = user_input
        self.result.attempts += 1
        if user_input.strip() == data.code:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            if self.result.attempts >= self.result.max_attempts:
                self.state = CaptchaState.FAILED
                self.result.message = "验证失败"
            else:
                self.state = CaptchaState.IDLE
                self.result.message = f"验证码错误，还剩{self.result.max_attempts - self.result.attempts}次"
        return self.result


class ScratchCardCaptchaModel(CaptchaModel):
    """刮刮卡验证码模型"""
    def __init__(self):
        super().__init__(CaptchaType.SCRATCH_CARD)
    def generate(self, config: CaptchaConfig):
        data = ScratchCardCaptchaData()
        data.answer = ''.join(random.choices('0123456789', k=4))
        data.user_input = ""
        data.scratched = []
        self.scratch_card_data = data
        self.state = CaptchaState.IDLE
        return data
    def add_scratch(self, x: float, y: float):
        if not hasattr(self, 'scratch_card_data') or self.scratch_card_data is None:
            return
        data = self.scratch_card_data
        data.scratched.append((x, y))
        if len(data.scratched) > 50:
            self.state = CaptchaState.VERIFYING
    def verify(self, user_input: str) -> 'CaptchaResult':
        if not hasattr(self, 'scratch_card_data') or self.scratch_card_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        data = self.scratch_card_data
        data.user_input = user_input
        self.result.attempts += 1
        if user_input.strip() == data.answer:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            if self.result.attempts >= self.result.max_attempts:
                self.state = CaptchaState.FAILED
                self.result.message = "验证失败"
            else:
                self.state = CaptchaState.IDLE
                self.result.message = f"答案错误，还剩{self.result.max_attempts - self.result.attempts}次"
        return self.result


class AreaClickCaptchaModel(CaptchaModel):
    """面积验证模型"""
    def __init__(self):
        super().__init__(CaptchaType.AREA_CLICK)
    def generate(self, config: CaptchaConfig):
        data = AreaClickCaptchaData()
        data.target_type = random.choice(["largest", "smallest"])
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7']
        for i in range(5):
            radius = random.uniform(18, 45)
            x = random.uniform(50, 250)
            y = random.uniform(40, 150)
            data.shapes.append({
                'cx': x, 'cy': y, 'r': radius,
                'area': 3.14159 * radius * radius,
                'color': colors[i]
            })
        data.clicked_index = -1
        self.area_click_data = data
        self.state = CaptchaState.IDLE
        return data
    def verify(self, clicked_index: int) -> 'CaptchaResult':
        if not hasattr(self, 'area_click_data') or self.area_click_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        data = self.area_click_data
        data.clicked_index = clicked_index
        self.result.attempts += 1
        areas = [s['area'] for s in data.shapes]
        if data.target_type == 'largest':
            target_idx = areas.index(max(areas))
        else:
            target_idx = areas.index(min(areas))
        if clicked_index == target_idx:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            if self.result.attempts >= self.result.max_attempts:
                self.state = CaptchaState.FAILED
                self.result.message = "验证失败"
            else:
                self.state = CaptchaState.IDLE
                self.result.message = f"不是这个，还剩{self.result.max_attempts - self.result.attempts}次"
        return self.result


class VoiceCaptchaModel(CaptchaModel):
    """语音验证码（模拟）模型"""
    def __init__(self):
        super().__init__(CaptchaType.VOICE_MOCK)
    def generate(self, config: CaptchaConfig):
        data = VoiceCaptchaData()
        data.code = ''.join(random.choices('0123456789', k=4))
        data.display_text = f"【模拟语音】请听播报：{data.code}"
        data.user_input = ""
        self.voice_data = data
        self.state = CaptchaState.IDLE
        return data
    def verify(self, user_input: str) -> 'CaptchaResult':
        if not hasattr(self, 'voice_data') or self.voice_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        data = self.voice_data
        data.user_input = user_input
        self.result.attempts += 1
        if user_input.strip() == data.code:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            if self.result.attempts >= self.result.max_attempts:
                self.state = CaptchaState.FAILED
                self.result.message = "验证失败"
            else:
                self.state = CaptchaState.IDLE
                self.result.message = f"输入错误，还剩{self.result.max_attempts - self.result.attempts}次"
        return self.result


class FontRecognizeCaptchaModel(CaptchaModel):
    """字体识别验证码模型"""
    def __init__(self):
        super().__init__(CaptchaType.FONT_RECOGNIZE)
        self.chars = "ABCD1234"
    def generate(self, config: CaptchaConfig):
        data = FontRecognizeCaptchaData()
        data.code = ''.join(random.choices(self.chars, k=4))
        cfg = config.get('text_captcha', {})
        width = cfg.get('width', 280)
        height = cfg.get('height', 100)
        for i, ch in enumerate(data.code):
            x = 30 + i * 60
            y = height / 2
            data.char_positions.append((x, y, 36, random.choice(['Arial', 'Courier', 'Times', 'Verdana'])))
        data.user_input = ""
        self.font_recognize_data = data
        self.state = CaptchaState.IDLE
        return data
    def verify(self, user_input: str) -> 'CaptchaResult':
        if not hasattr(self, 'font_recognize_data') or self.font_recognize_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        data = self.font_recognize_data
        data.user_input = user_input
        self.result.attempts += 1
        if user_input.upper().strip() == data.code:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            if self.result.attempts >= self.result.max_attempts:
                self.state = CaptchaState.FAILED
                self.result.message = "验证失败"
            else:
                self.state = CaptchaState.IDLE
                self.result.message = f"识别错误，还剩{self.result.max_attempts - self.result.attempts}次"
        return self.result


class BehaviorMockCaptchaModel(CaptchaModel):
    """无感验证（模拟）模型"""
    def __init__(self):
        super().__init__(CaptchaType.BEHAVIOR_MOCK)
    def generate(self, config: CaptchaConfig):
        data = BehaviorMockCaptchaData()
        data.fake_score = random.uniform(0.65, 0.98)
        data.status = "analyzing"
        data.progress = 0.0
        self.behavior_data = data
        self.state = CaptchaState.VERIFYING
        return data
    def simulate_check(self) -> 'CaptchaResult':
        if not hasattr(self, 'behavior_data') or self.behavior_data is None:
            return CaptchaResult(success=False, message="验证未生成")
        data = self.behavior_data
        data.progress = min(1.0, data.progress + 0.33)
        self.result.attempts += 1
        if data.progress >= 1.0:
            if data.fake_score > 0.8:
                self.state = CaptchaState.SUCCESS
                self.result.success = True
                self.result.message = f"无感验证通过（行为评分：{data.fake_score:.2f}）"
                self.result.score = data.fake_score
            else:
                self.state = CaptchaState.FAILED
                self.result.message = f"行为异常（行为评分：{data.fake_score:.2f}）"
        return self.result

# ========== 新增验证码 Model ==========

class WordOrderCaptchaModel(CaptchaModel):
    """语序点选验证码模型"""
    def __init__(self):
        super().__init__(CaptchaType.WORD_ORDER)
        self.word_pool = [
            ["我", "爱", "中国", "编程"],
            ["今天", "天气", "真", "好"],
            ["人机", "验证", "很", "有趣"],
            ["Python", "是", "一门", "编程语言"],
            ["验证码", "可以", "防止", "机器人"],
        ]
    def generate(self, config: CaptchaConfig):
        data = WordOrderCaptchaData()
        sentence = random.choice(self.word_pool)
        data.words = sentence.copy()
        data.target_count = len(sentence)
        data.shuffled_words = sentence.copy()
        random.shuffle(data.shuffled_words)
        data.clicked_order = []
        self.word_order_data = data
        self.state = CaptchaState.IDLE
        return data
    def verify(self, clicked_index: int) -> 'CaptchaResult':
        if not hasattr(self, 'word_order_data') or self.word_order_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        data = self.word_order_data
        data.clicked_order.append(clicked_index)
        self.result.attempts += 1
        expected_word = data.words[len(data.clicked_order) - 1]
        actual_word = data.shuffled_words[clicked_index]
        if actual_word != expected_word:
            self.state = CaptchaState.FAILED
            self.result.success = False
            self.result.message = f"顺序错误，应是「{expected_word}」"
            data.clicked_order = []
            return self.result
        if len(data.clicked_order) >= data.target_count:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            next_word = data.words[len(data.clicked_order)]
            self.result.message = f"正确！请继续点击「{next_word}」"
        return self.result


class DifferenceClickCaptchaModel(CaptchaModel):
    """差异点击验证码模型"""
    def __init__(self):
        super().__init__(CaptchaType.DIFFERENCE_CLICK)
    def generate(self, config: CaptchaConfig):
        data = DifferenceClickCaptchaData()
        data.grid_cols = 3
        data.grid_rows = 3
        data.different_index = random.randint(0, 8)
        shapes = ["circle", "square", "triangle"]
        normal_shape = random.choice(shapes)
        different_shape = random.choice([s for s in shapes if s != normal_shape])
        colors = ["#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7", "#DDA0DD", "#FF9F43", "#A29BFE", "#FF6B9D", "#C44569"]
        for i in range(9):
            data.images.append({
                'shape': normal_shape if i != data.different_index else different_shape,
                'color': colors[i],
                'label': f'格{i+1}'
            })
        data.clicked_index = -1
        self.difference_click_data = data
        self.state = CaptchaState.IDLE
        return data
    def verify(self, clicked_index: int) -> 'CaptchaResult':
        if not hasattr(self, 'difference_click_data') or self.difference_click_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        data = self.difference_click_data
        data.clicked_index = clicked_index
        self.result.attempts += 1
        if clicked_index == data.different_index:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            if self.result.attempts >= self.result.max_attempts:
                self.state = CaptchaState.FAILED
                self.result.message = "验证失败"
            else:
                self.state = CaptchaState.IDLE
                self.result.message = f"不是这里，还剩{self.result.max_attempts - self.result.attempts}次"
        return self.result


class NineGridCaptchaModel(CaptchaModel):
    """九宫格验证码模型"""
    def __init__(self):
        super().__init__(CaptchaType.NINE_GRID)
    def generate(self, config: CaptchaConfig):
        data = NineGridCaptchaData()
        data.target_text = "动物"
        data.instruction = "请点击所有动物"
        animals = ["dog", "cat", "bird", "fish", "rabbit", "fox", "bear", "deer", "monkey"]
        selected = animals.copy()
        random.shuffle(selected)
        data.grids = []
        data.target_indices = []
        for i, animal in enumerate(selected[:9]):
            is_target = animal in animals[:3]
            if is_target:
                data.target_indices.append(i)
            data.grids.append({'index': i, 'animal': animal, 'is_target': is_target})
            data.clicked_indices = []
        self.nine_grid_data = data
        self.state = CaptchaState.IDLE
        return data
    def verify(self, clicked_index: int) -> 'CaptchaResult':
        if not hasattr(self, 'nine_grid_data') or self.nine_grid_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        data = self.nine_grid_data
        if clicked_index in data.clicked_indices:
            return self.result
        data.clicked_indices.append(clicked_index)
        self.result.attempts += 1
        all_clicked = all(idx in data.clicked_indices for idx in data.target_indices)
        if all_clicked:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            remaining = [idx for idx in data.target_indices if idx not in data.clicked_indices]
            self.result.message = f"已选 {len(data.clicked_indices)}，还需选择 {len(remaining)} 个"
        return self.result


class SMSCaptchaModel(CaptchaModel):
    """短信验证码（模拟）模型"""
    def __init__(self):
        super().__init__(CaptchaType.SMS_MOCK)
    def generate(self, config: CaptchaConfig):
        data = SMSCaptchaData()
        data.code = ''.join(random.choices('0123456789', k=6))
        data.display_code = f"【模拟短信】您的验证码是：{data.code}"
        data.user_input = ""
        self.sms_data = data
        self.state = CaptchaState.IDLE
        return data
    def verify(self, user_input: str) -> 'CaptchaResult':
        if not hasattr(self, 'sms_data') or self.sms_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        data = self.sms_data
        data.user_input = user_input
        self.result.attempts += 1
        if user_input.strip() == data.code:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            if self.result.attempts >= self.result.max_attempts:
                self.state = CaptchaState.FAILED
                self.result.message = "验证失败"
            else:
                self.state = CaptchaState.IDLE
                self.result.message = f"验证码错误，还剩{self.result.max_attempts - self.result.attempts}次"
        return self.result


class ScratchCardCaptchaModel(CaptchaModel):
    """刮刮卡验证码模型"""
    def __init__(self):
        super().__init__(CaptchaType.SCRATCH_CARD)
    def generate(self, config: CaptchaConfig):
        data = ScratchCardCaptchaData()
        data.answer = ''.join(random.choices('0123456789', k=4))
        data.user_input = ""
        data.scratched = []
        self.scratch_card_data = data
        self.state = CaptchaState.IDLE
        return data
    def add_scratch(self, x: float, y: float):
        if not hasattr(self, 'scratch_card_data') or self.scratch_card_data is None:
            return
        data = self.scratch_card_data
        data.scratched.append((x, y))
        if len(data.scratched) > 50:
            self.state = CaptchaState.VERIFYING
    def verify(self, user_input: str) -> 'CaptchaResult':
        if not hasattr(self, 'scratch_card_data') or self.scratch_card_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        data = self.scratch_card_data
        data.user_input = user_input
        self.result.attempts += 1
        if user_input.strip() == data.answer:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            if self.result.attempts >= self.result.max_attempts:
                self.state = CaptchaState.FAILED
                self.result.message = "验证失败"
            else:
                self.state = CaptchaState.IDLE
                self.result.message = f"答案错误，还剩{self.result.max_attempts - self.result.attempts}次"
        return self.result


class AreaClickCaptchaModel(CaptchaModel):
    """面积验证模型"""
    def __init__(self):
        super().__init__(CaptchaType.AREA_CLICK)
    def generate(self, config: CaptchaConfig):
        data = AreaClickCaptchaData()
        data.target_type = random.choice(["largest", "smallest"])
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7']
        for i in range(5):
            radius = random.uniform(18, 45)
            x = random.uniform(50, 250)
            y = random.uniform(40, 150)
            data.shapes.append({
                'cx': x, 'cy': y, 'r': radius,
                'area': 3.14159 * radius * radius,
                'color': colors[i]
            })
        data.clicked_index = -1
        self.area_click_data = data
        self.state = CaptchaState.IDLE
        return data
    def verify(self, clicked_index: int) -> 'CaptchaResult':
        if not hasattr(self, 'area_click_data') or self.area_click_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        data = self.area_click_data
        data.clicked_index = clicked_index
        self.result.attempts += 1
        areas = [s['area'] for s in data.shapes]
        if data.target_type == 'largest':
            target_idx = areas.index(max(areas))
        else:
            target_idx = areas.index(min(areas))
        if clicked_index == target_idx:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            if self.result.attempts >= self.result.max_attempts:
                self.state = CaptchaState.FAILED
                self.result.message = "验证失败"
            else:
                self.state = CaptchaState.IDLE
                self.result.message = f"不是这个，还剩{self.result.max_attempts - self.result.attempts}次"
        return self.result


class VoiceCaptchaModel(CaptchaModel):
    """语音验证码（模拟）模型"""
    def __init__(self):
        super().__init__(CaptchaType.VOICE_MOCK)
    def generate(self, config: CaptchaConfig):
        data = VoiceCaptchaData()
        data.code = ''.join(random.choices('0123456789', k=4))
        data.display_text = f"【模拟语音】请听播报：{data.code}"
        data.user_input = ""
        self.voice_data = data
        self.state = CaptchaState.IDLE
        return data
    def verify(self, user_input: str) -> 'CaptchaResult':
        if not hasattr(self, 'voice_data') or self.voice_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        data = self.voice_data
        data.user_input = user_input
        self.result.attempts += 1
        if user_input.strip() == data.code:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            if self.result.attempts >= self.result.max_attempts:
                self.state = CaptchaState.FAILED
                self.result.message = "验证失败"
            else:
                self.state = CaptchaState.IDLE
                self.result.message = f"输入错误，还剩{self.result.max_attempts - self.result.attempts}次"
        return self.result


class FontRecognizeCaptchaModel(CaptchaModel):
    """字体识别验证码模型"""
    def __init__(self):
        super().__init__(CaptchaType.FONT_RECOGNIZE)
        self.chars = "ABCD1234"
    def generate(self, config: CaptchaConfig):
        data = FontRecognizeCaptchaData()
        data.code = ''.join(random.choices(self.chars, k=4))
        cfg = config.get('text_captcha', {})
        width = cfg.get('width', 280)
        height = cfg.get('height', 100)
        for i, ch in enumerate(data.code):
            x = 30 + i * 60
            y = height / 2
            data.char_positions.append((x, y, 36, random.choice(['Arial', 'Courier', 'Times', 'Verdana'])))
        data.user_input = ""
        self.font_recognize_data = data
        self.state = CaptchaState.IDLE
        return data
    def verify(self, user_input: str) -> 'CaptchaResult':
        if not hasattr(self, 'font_recognize_data') or self.font_recognize_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        data = self.font_recognize_data
        data.user_input = user_input
        self.result.attempts += 1
        if user_input.upper().strip() == data.code:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            if self.result.attempts >= self.result.max_attempts:
                self.state = CaptchaState.FAILED
                self.result.message = "验证失败"
            else:
                self.state = CaptchaState.IDLE
                self.result.message = f"识别错误，还剩{self.result.max_attempts - self.result.attempts}次"
        return self.result


class BehaviorMockCaptchaModel(CaptchaModel):
    """无感验证（模拟）模型"""
    def __init__(self):
        super().__init__(CaptchaType.BEHAVIOR_MOCK)
    def generate(self, config: CaptchaConfig):
        data = BehaviorMockCaptchaData()
        data.fake_score = random.uniform(0.65, 0.98)
        data.status = "analyzing"
        data.progress = 0.0
        self.behavior_data = data
        self.state = CaptchaState.VERIFYING
        return data
    def simulate_check(self) -> 'CaptchaResult':
        if not hasattr(self, 'behavior_data') or self.behavior_data is None:
            return CaptchaResult(success=False, message="验证未生成")
        data = self.behavior_data
        data.progress = min(1.0, data.progress + 0.33)
        self.result.attempts += 1
        if data.progress >= 1.0:
            if data.fake_score > 0.8:
                self.state = CaptchaState.SUCCESS
                self.result.success = True
                self.result.message = f"无感验证通过（行为评分：{data.fake_score:.2f}）"
                self.result.score = data.fake_score
            else:
                self.state = CaptchaState.FAILED
                self.result.message = f"行为异常（行为评分：{data.fake_score:.2f}）"
        return self.result

# ========== 新增验证码 Model ==========

class WordOrderCaptchaModel(CaptchaModel):
    """语序点选验证码模型"""
    def __init__(self):
        super().__init__(CaptchaType.WORD_ORDER)
        self.word_pool = [
            ["我", "爱", "中国", "编程"],
            ["今天", "天气", "真", "好"],
            ["人机", "验证", "很", "有趣"],
            ["Python", "是", "一门", "编程语言"],
            ["验证码", "可以", "防止", "机器人"],
        ]
    def generate(self, config: CaptchaConfig):
        data = WordOrderCaptchaData()
        sentence = random.choice(self.word_pool)
        data.words = sentence.copy()
        data.target_count = len(sentence)
        data.shuffled_words = sentence.copy()
        random.shuffle(data.shuffled_words)
        data.clicked_order = []
        self.word_order_data = data
        self.state = CaptchaState.IDLE
        return data
    def verify(self, clicked_index: int) -> 'CaptchaResult':
        if not hasattr(self, 'word_order_data') or self.word_order_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        data = self.word_order_data
        data.clicked_order.append(clicked_index)
        self.result.attempts += 1
        expected_word = data.words[len(data.clicked_order) - 1]
        actual_word = data.shuffled_words[clicked_index]
        if actual_word != expected_word:
            self.state = CaptchaState.FAILED
            self.result.success = False
            self.result.message = f"顺序错误，应是「{expected_word}」"
            data.clicked_order = []
            return self.result
        if len(data.clicked_order) >= data.target_count:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            next_word = data.words[len(data.clicked_order)]
            self.result.message = f"正确！请继续点击「{next_word}」"
        return self.result


class DifferenceClickCaptchaModel(CaptchaModel):
    """差异点击验证码模型"""
    def __init__(self):
        super().__init__(CaptchaType.DIFFERENCE_CLICK)
    def generate(self, config: CaptchaConfig):
        data = DifferenceClickCaptchaData()
        data.grid_cols = 3
        data.grid_rows = 3
        data.different_index = random.randint(0, 8)
        shapes = ["circle", "square", "triangle"]
        normal_shape = random.choice(shapes)
        different_shape = random.choice([s for s in shapes if s != normal_shape])
        colors = ["#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7", "#DDA0DD", "#FF9F43", "#A29BFE", "#FF6B9D", "#C44569"]
        for i in range(9):
            data.images.append({
                'shape': normal_shape if i != data.different_index else different_shape,
                'color': colors[i],
                'label': f'格{i+1}'
            })
        data.clicked_index = -1
        self.difference_click_data = data
        self.state = CaptchaState.IDLE
        return data
    def verify(self, clicked_index: int) -> 'CaptchaResult':
        if not hasattr(self, 'difference_click_data') or self.difference_click_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        data = self.difference_click_data
        data.clicked_index = clicked_index
        self.result.attempts += 1
        if clicked_index == data.different_index:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            if self.result.attempts >= self.result.max_attempts:
                self.state = CaptchaState.FAILED
                self.result.message = "验证失败"
            else:
                self.state = CaptchaState.IDLE
                self.result.message = f"不是这里，还剩{self.result.max_attempts - self.result.attempts}次"
        return self.result


class NineGridCaptchaModel(CaptchaModel):
    """九宫格验证码模型"""
    def __init__(self):
        super().__init__(CaptchaType.NINE_GRID)
    def generate(self, config: CaptchaConfig):
        data = NineGridCaptchaData()
        data.target_text = "动物"
        data.instruction = "请点击所有动物"
        animals = ["dog", "cat", "bird", "fish", "rabbit", "fox", "bear", "deer", "monkey"]
        selected = animals.copy()
        random.shuffle(selected)
        data.grids = []
        data.target_indices = []
        for i, animal in enumerate(selected[:9]):
            is_target = animal in animals[:3]
            if is_target:
                data.target_indices.append(i)
            data.grids.append({'index': i, 'animal': animal, 'is_target': is_target})
            data.clicked_indices = []
        self.nine_grid_data = data
        self.state = CaptchaState.IDLE
        return data
    def verify(self, clicked_index: int) -> 'CaptchaResult':
        if not hasattr(self, 'nine_grid_data') or self.nine_grid_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        data = self.nine_grid_data
        if clicked_index in data.clicked_indices:
            return self.result
        data.clicked_indices.append(clicked_index)
        self.result.attempts += 1
        all_clicked = all(idx in data.clicked_indices for idx in data.target_indices)
        if all_clicked:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            remaining = [idx for idx in data.target_indices if idx not in data.clicked_indices]
            self.result.message = f"已选 {len(data.clicked_indices)}，还需选择 {len(remaining)} 个"
        return self.result


class SMSCaptchaModel(CaptchaModel):
    """短信验证码（模拟）模型"""
    def __init__(self):
        super().__init__(CaptchaType.SMS_MOCK)
    def generate(self, config: CaptchaConfig):
        data = SMSCaptchaData()
        data.code = ''.join(random.choices('0123456789', k=6))
        data.display_code = f"【模拟短信】您的验证码是：{data.code}"
        data.user_input = ""
        self.sms_data = data
        self.state = CaptchaState.IDLE
        return data
    def verify(self, user_input: str) -> 'CaptchaResult':
        if not hasattr(self, 'sms_data') or self.sms_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        data = self.sms_data
        data.user_input = user_input
        self.result.attempts += 1
        if user_input.strip() == data.code:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            if self.result.attempts >= self.result.max_attempts:
                self.state = CaptchaState.FAILED
                self.result.message = "验证失败"
            else:
                self.state = CaptchaState.IDLE
                self.result.message = f"验证码错误，还剩{self.result.max_attempts - self.result.attempts}次"
        return self.result


class ScratchCardCaptchaModel(CaptchaModel):
    """刮刮卡验证码模型"""
    def __init__(self):
        super().__init__(CaptchaType.SCRATCH_CARD)
    def generate(self, config: CaptchaConfig):
        data = ScratchCardCaptchaData()
        data.answer = ''.join(random.choices('0123456789', k=4))
        data.user_input = ""
        data.scratched = []
        self.scratch_card_data = data
        self.state = CaptchaState.IDLE
        return data
    def add_scratch(self, x: float, y: float):
        if not hasattr(self, 'scratch_card_data') or self.scratch_card_data is None:
            return
        data = self.scratch_card_data
        data.scratched.append((x, y))
        if len(data.scratched) > 50:
            self.state = CaptchaState.VERIFYING
    def verify(self, user_input: str) -> 'CaptchaResult':
        if not hasattr(self, 'scratch_card_data') or self.scratch_card_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        data = self.scratch_card_data
        data.user_input = user_input
        self.result.attempts += 1
        if user_input.strip() == data.answer:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            if self.result.attempts >= self.result.max_attempts:
                self.state = CaptchaState.FAILED
                self.result.message = "验证失败"
            else:
                self.state = CaptchaState.IDLE
                self.result.message = f"答案错误，还剩{self.result.max_attempts - self.result.attempts}次"
        return self.result


class AreaClickCaptchaModel(CaptchaModel):
    """面积验证模型"""
    def __init__(self):
        super().__init__(CaptchaType.AREA_CLICK)
    def generate(self, config: CaptchaConfig):
        data = AreaClickCaptchaData()
        data.target_type = random.choice(["largest", "smallest"])
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7']
        for i in range(5):
            radius = random.uniform(18, 45)
            x = random.uniform(50, 250)
            y = random.uniform(40, 150)
            data.shapes.append({
                'cx': x, 'cy': y, 'r': radius,
                'area': 3.14159 * radius * radius,
                'color': colors[i]
            })
        data.clicked_index = -1
        self.area_click_data = data
        self.state = CaptchaState.IDLE
        return data
    def verify(self, clicked_index: int) -> 'CaptchaResult':
        if not hasattr(self, 'area_click_data') or self.area_click_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        data = self.area_click_data
        data.clicked_index = clicked_index
        self.result.attempts += 1
        areas = [s['area'] for s in data.shapes]
        if data.target_type == 'largest':
            target_idx = areas.index(max(areas))
        else:
            target_idx = areas.index(min(areas))
        if clicked_index == target_idx:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            if self.result.attempts >= self.result.max_attempts:
                self.state = CaptchaState.FAILED
                self.result.message = "验证失败"
            else:
                self.state = CaptchaState.IDLE
                self.result.message = f"不是这个，还剩{self.result.max_attempts - self.result.attempts}次"
        return self.result


class VoiceCaptchaModel(CaptchaModel):
    """语音验证码（模拟）模型"""
    def __init__(self):
        super().__init__(CaptchaType.VOICE_MOCK)
    def generate(self, config: CaptchaConfig):
        data = VoiceCaptchaData()
        data.code = ''.join(random.choices('0123456789', k=4))
        data.display_text = f"【模拟语音】请听播报：{data.code}"
        data.user_input = ""
        self.voice_data = data
        self.state = CaptchaState.IDLE
        return data
    def verify(self, user_input: str) -> 'CaptchaResult':
        if not hasattr(self, 'voice_data') or self.voice_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        data = self.voice_data
        data.user_input = user_input
        self.result.attempts += 1
        if user_input.strip() == data.code:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            if self.result.attempts >= self.result.max_attempts:
                self.state = CaptchaState.FAILED
                self.result.message = "验证失败"
            else:
                self.state = CaptchaState.IDLE
                self.result.message = f"输入错误，还剩{self.result.max_attempts - self.result.attempts}次"
        return self.result


class FontRecognizeCaptchaModel(CaptchaModel):
    """字体识别验证码模型"""
    def __init__(self):
        super().__init__(CaptchaType.FONT_RECOGNIZE)
        self.chars = "ABCD1234"
    def generate(self, config: CaptchaConfig):
        data = FontRecognizeCaptchaData()
        data.code = ''.join(random.choices(self.chars, k=4))
        cfg = config.get('text_captcha', {})
        width = cfg.get('width', 280)
        height = cfg.get('height', 100)
        for i, ch in enumerate(data.code):
            x = 30 + i * 60
            y = height / 2
            data.char_positions.append((x, y, 36, random.choice(['Arial', 'Courier', 'Times', 'Verdana'])))
        data.user_input = ""
        self.font_recognize_data = data
        self.state = CaptchaState.IDLE
        return data
    def verify(self, user_input: str) -> 'CaptchaResult':
        if not hasattr(self, 'font_recognize_data') or self.font_recognize_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        data = self.font_recognize_data
        data.user_input = user_input
        self.result.attempts += 1
        if user_input.upper().strip() == data.code:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            if self.result.attempts >= self.result.max_attempts:
                self.state = CaptchaState.FAILED
                self.result.message = "验证失败"
            else:
                self.state = CaptchaState.IDLE
                self.result.message = f"识别错误，还剩{self.result.max_attempts - self.result.attempts}次"
        return self.result


class BehaviorMockCaptchaModel(CaptchaModel):
    """无感验证（模拟）模型"""
    def __init__(self):
        super().__init__(CaptchaType.BEHAVIOR_MOCK)
    def generate(self, config: CaptchaConfig):
        data = BehaviorMockCaptchaData()
        data.fake_score = random.uniform(0.65, 0.98)
        data.status = "analyzing"
        data.progress = 0.0
        self.behavior_data = data
        self.state = CaptchaState.VERIFYING
        return data
    def simulate_check(self) -> 'CaptchaResult':
        if not hasattr(self, 'behavior_data') or self.behavior_data is None:
            return CaptchaResult(success=False, message="验证未生成")
        data = self.behavior_data
        data.progress = min(1.0, data.progress + 0.33)
        self.result.attempts += 1
        if data.progress >= 1.0:
            if data.fake_score > 0.8:
                self.state = CaptchaState.SUCCESS
                self.result.success = True
                self.result.message = f"无感验证通过（行为评分：{data.fake_score:.2f}）"
                self.result.score = data.fake_score
            else:
                self.state = CaptchaState.FAILED
                self.result.message = f"行为异常（行为评分：{data.fake_score:.2f}）"
        return self.result


# ========== 新增验证码 Model ==========

class WordOrderCaptchaModel(CaptchaModel):
    """语序点选验证码模型"""
    def __init__(self):
        super().__init__(CaptchaType.WORD_ORDER)
        self.word_pool = [
            ["我", "爱", "中国", "编程"],
            ["今天", "天气", "真", "好"],
            ["人机", "验证", "很", "有趣"],
            ["Python", "是", "一门", "编程语言"],
            ["验证码", "可以", "防止", "机器人"],
        ]
    def generate(self, config: CaptchaConfig):
        from dataclasses import field
        data = WordOrderCaptchaData()
        import random
        sentence = random.choice(self.word_pool)
        data.words = sentence.copy()
        data.target_count = len(sentence)
        data.shuffled_words = sentence.copy()
        random.shuffle(data.shuffled_words)
        data.clicked_order = []
        self.word_order_data = data
        self.state = CaptchaState.IDLE
        return data
    def verify(self, clicked_index: int) -> 'CaptchaResult':
        if not hasattr(self, 'word_order_data') or self.word_order_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        data = self.word_order_data
        data.clicked_order.append(clicked_index)
        self.result.attempts += 1
        expected_word = data.words[len(data.clicked_order) - 1]
        actual_word = data.shuffled_words[clicked_index]
        if actual_word != expected_word:
            self.state = CaptchaState.FAILED
            self.result.success = False
            self.result.message = f"顺序错误，应是「{expected_word}」"
            data.clicked_order = []
            return self.result
        if len(data.clicked_order) >= data.target_count:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            next_word = data.words[len(data.clicked_order)]
            self.result.message = f"正确！请继续点击「{next_word}」"
        return self.result


class DifferenceClickCaptchaModel(CaptchaModel):
    """差异点击验证码模型"""
    def __init__(self):
        super().__init__(CaptchaType.DIFFERENCE_CLICK)
    def generate(self, config: CaptchaConfig):
        import random
        data = DifferenceClickCaptchaData()
        data.grid_cols = 3
        data.grid_rows = 3
        data.different_index = random.randint(0, 8)
        shapes = ["circle", "square", "triangle"]
        normal_shape = random.choice(shapes)
        different_shape = random.choice([s for s in shapes if s != normal_shape])
        colors = ['#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#FF9F43', '#A29BFE', '#FF6B9D', '#C44569']
        for i in range(9):
            data.images.append({
                'shape': normal_shape if i != data.different_index else different_shape,
                'color': colors[i],
                'label': f'格{i+1}'
            })
        data.clicked_index = -1
        self.difference_click_data = data
        self.state = CaptchaState.IDLE
        return data
    def verify(self, clicked_index: int) -> 'CaptchaResult':
        if not hasattr(self, 'difference_click_data') or self.difference_click_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        data = self.difference_click_data
        data.clicked_index = clicked_index
        self.result.attempts += 1
        if clicked_index == data.different_index:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            if self.result.attempts >= self.result.max_attempts:
                self.state = CaptchaState.FAILED
                self.result.message = "验证失败"
            else:
                self.state = CaptchaState.IDLE
                self.result.message = f"不是这里，还剩{self.result.max_attempts - self.result.attempts}次"
        return self.result


class NineGridCaptchaModel(CaptchaModel):
    """九宫格验证码模型"""
    def __init__(self):
        super().__init__(CaptchaType.NINE_GRID)
    def generate(self, config: CaptchaConfig):
        import random
        data = NineGridCaptchaData()
        data.target_text = "动物"
        data.instruction = "请点击所有动物"
        animals = ["dog", "cat", "bird", "fish", "rabbit", "fox", "bear", "deer", "monkey"]
        selected = animals.copy()
        random.shuffle(selected)
        data.grids = []
        data.target_indices = []
        for i, animal in enumerate(selected[:9]):
            is_target = animal in animals[:3]
            if is_target:
                data.target_indices.append(i)
            data.grids.append({'index': i, 'animal': animal, 'is_target': is_target})
        data.clicked_indices = []
        self.nine_grid_data = data
        self.state = CaptchaState.IDLE
        return data
    def verify(self, clicked_index: int) -> 'CaptchaResult':
        if not hasattr(self, 'nine_grid_data') or self.nine_grid_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        data = self.nine_grid_data
        if clicked_index in data.clicked_indices:
            return self.result
        data.clicked_indices.append(clicked_index)
        self.result.attempts += 1
        all_clicked = all(idx in data.clicked_indices for idx in data.target_indices)
        if all_clicked:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            remaining = [idx for idx in data.target_indices if idx not in data.clicked_indices]
            self.result.message = f"已选 {len(data.clicked_indices)}，还需选择 {len(remaining)} 个"
        return self.result


class SMSCaptchaModel(CaptchaModel):
    """短信验证码（模拟）模型"""
    def __init__(self):
        super().__init__(CaptchaType.SMS_MOCK)
    def generate(self, config: CaptchaConfig):
        import random
        data = SMSCaptchaData()
        data.code = ''.join(random.choices('0123456789', k=6))
        data.display_code = f"【模拟短信】您的验证码是：{data.code}"
        data.user_input = ""
        self.sms_data = data
        self.state = CaptchaState.IDLE
        return data
    def verify(self, user_input: str) -> 'CaptchaResult':
        if not hasattr(self, 'sms_data') or self.sms_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        data = self.sms_data
        data.user_input = user_input
        self.result.attempts += 1
        if user_input.strip() == data.code:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            if self.result.attempts >= self.result.max_attempts:
                self.state = CaptchaState.FAILED
                self.result.message = "验证失败"
            else:
                self.state = CaptchaState.IDLE
                self.result.message = f"验证码错误，还剩{self.result.max_attempts - self.result.attempts}次"
        return self.result


class ScratchCardCaptchaModel(CaptchaModel):
    """刮刮卡验证码模型"""
    def __init__(self):
        super().__init__(CaptchaType.SCRATCH_CARD)
    def generate(self, config: CaptchaConfig):
        import random
        data = ScratchCardCaptchaData()
        data.answer = ''.join(random.choices('0123456789', k=4))
        data.user_input = ""
        data.scratched = []
        self.scratch_card_data = data
        self.state = CaptchaState.IDLE
        return data
    def add_scratch(self, x: float, y: float):
        if not hasattr(self, 'scratch_card_data') or self.scratch_card_data is None:
            return
        data = self.scratch_card_data
        data.scratched.append((x, y))
        if len(data.scratched) > 50:
            self.state = CaptchaState.VERIFYING
    def verify(self, user_input: str) -> 'CaptchaResult':
        if not hasattr(self, 'scratch_card_data') or self.scratch_card_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        data = self.scratch_card_data
        data.user_input = user_input
        self.result.attempts += 1
        if user_input.strip() == data.answer:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            if self.result.attempts >= self.result.max_attempts:
                self.state = CaptchaState.FAILED
                self.result.message = "验证失败"
            else:
                self.state = CaptchaState.IDLE
                self.result.message = f"答案错误，还剩{self.result.max_attempts - self.result.attempts}次"
        return self.result


class AreaClickCaptchaModel(CaptchaModel):
    """面积验证模型"""
    def __init__(self):
        super().__init__(CaptchaType.AREA_CLICK)
    def generate(self, config: CaptchaConfig):
        import random, math
        data = AreaClickCaptchaData()
        data.target_type = random.choice(["largest", "smallest"])
        num_shapes = 5
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7']
        for i in range(num_shapes):
            radius = random.uniform(18, 45)
            x = random.uniform(50, 250)
            y = random.uniform(40, 150)
            data.shapes.append({
                'cx': x, 'cy': y, 'r': radius,
                'area': math.pi * radius * radius,
                'color': colors[i]
            })
        data.clicked_index = -1
        self.area_click_data = data
        self.state = CaptchaState.IDLE
        return data
    def verify(self, clicked_index: int) -> 'CaptchaResult':
        if not hasattr(self, 'area_click_data') or self.area_click_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        data = self.area_click_data
        data.clicked_index = clicked_index
        self.result.attempts += 1
        areas = [s['area'] for s in data.shapes]
        if data.target_type == "largest":
            target_idx = areas.index(max(areas))
        else:
            target_idx = areas.index(min(areas))
        if clicked_index == target_idx:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            if self.result.attempts >= self.result.max_attempts:
                self.state = CaptchaState.FAILED
                self.result.message = "验证失败"
            else:
                self.state = CaptchaState.IDLE
                self.result.message = f"不是这个，还剩{self.result.max_attempts - self.result.attempts}次"
        return self.result


class VoiceCaptchaModel(CaptchaModel):
    """语音验证码（模拟）模型"""
    def __init__(self):
        super().__init__(CaptchaType.VOICE_MOCK)
    def generate(self, config: CaptchaConfig):
        import random
        data = VoiceCaptchaData()
        data.code = ''.join(random.choices('0123456789', k=4))
        data.display_text = f"【模拟语音】请听播报：{data.code}"
        data.user_input = ""
        self.voice_data = data
        self.state = CaptchaState.IDLE
        return data
    def verify(self, user_input: str) -> 'CaptchaResult':
        if not hasattr(self, 'voice_data') or self.voice_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        data = self.voice_data
        data.user_input = user_input
        self.result.attempts += 1
        if user_input.strip() == data.code:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            if self.result.attempts >= self.result.max_attempts:
                self.state = CaptchaState.FAILED
                self.result.message = "验证失败"
            else:
                self.state = CaptchaState.IDLE
                self.result.message = f"输入错误，还剩{self.result.max_attempts - self.result.attempts}次"
        return self.result


class FontRecognizeCaptchaModel(CaptchaModel):
    """字体识别验证码模型"""
    def __init__(self):
        super().__init__(CaptchaType.FONT_RECOGNIZE)
        self.chars = "ABCD1234"
    def generate(self, config: CaptchaConfig):
        import random
        data = FontRecognizeCaptchaData()
        data.code = ''.join(random.choices(self.chars, k=4))
        cfg = config.get('text_captcha', {})
        width = cfg.get('width', 280)
        height = cfg.get('height', 100)
        for i, ch in enumerate(data.code):
            x = 30 + i * 60
            y = height / 2
            data.char_positions.append((x, y, 36, random.choice(['Arial', 'Courier', 'Times', 'Verdana'])))
        data.user_input = ""
        self.font_recognize_data = data
        self.state = CaptchaState.IDLE
        return data
    def verify(self, user_input: str) -> 'CaptchaResult':
        if not hasattr(self, 'font_recognize_data') or self.font_recognize_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        data = self.font_recognize_data
        data.user_input = user_input
        self.result.attempts += 1
        if user_input.upper().strip() == data.code:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            if self.result.attempts >= self.result.max_attempts:
                self.state = CaptchaState.FAILED
                self.result.message = "验证失败"
            else:
                self.state = CaptchaState.IDLE
                self.result.message = f"识别错误，还剩{self.result.max_attempts - self.result.attempts}次"
        return self.result


class BehaviorMockCaptchaModel(CaptchaModel):
    """无感验证（模拟）模型"""
    def __init__(self):
        super().__init__(CaptchaType.BEHAVIOR_MOCK)
    def generate(self, config: CaptchaConfig):
        import random
        data = BehaviorMockCaptchaData()
        data.fake_score = random.uniform(0.65, 0.98)
        data.status = "analyzing"
        data.progress = 0.0
        self.behavior_data = data
        self.state = CaptchaState.VERIFYING
        return data
    def simulate_check(self) -> 'CaptchaResult':
        if not hasattr(self, 'behavior_data') or self.behavior_data is None:
            return CaptchaResult(success=False, message="验证未生成")
        data = self.behavior_data
        data.progress = min(1.0, data.progress + 0.33)
        self.result.attempts += 1
        if data.progress >= 1.0:
            if data.fake_score > 0.8:
                self.state = CaptchaState.SUCCESS
                self.result.success = True
                self.result.message = f"无感验证通过（行为评分：{data.fake_score:.2f}）"
                self.result.score = data.fake_score
            else:
                self.state = CaptchaState.FAILED
                self.result.message = f"行为异常（行为评分：{data.fake_score:.2f}）"
        return self.result



# ========== 新增验证码 Model ==========

class WordOrderCaptchaModel(CaptchaModel):
    """语序点选验证码模型"""
    def __init__(self):
        super().__init__(CaptchaType.WORD_ORDER)
        self.word_pool = [
            ["我", "爱", "中国", "编程"],
            ["今天", "天气", "真", "好"],
            ["人机", "验证", "很", "有趣"],
            ["Python", "是", "一门", "编程语言"],
            ["验证码", "可以", "防止", "机器人"],
        ]
    def generate(self, config: CaptchaConfig):
        from dataclasses import field
        data = WordOrderCaptchaData()
        import random
        sentence = random.choice(self.word_pool)
        data.words = sentence.copy()
        data.target_count = len(sentence)
        data.shuffled_words = sentence.copy()
        random.shuffle(data.shuffled_words)
        data.clicked_order = []
        self.word_order_data = data
        self.state = CaptchaState.IDLE
        return data
    def verify(self, clicked_index: int) -> 'CaptchaResult':
        if not hasattr(self, 'word_order_data') or self.word_order_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        data = self.word_order_data
        data.clicked_order.append(clicked_index)
        self.result.attempts += 1
        expected_word = data.words[len(data.clicked_order) - 1]
        actual_word = data.shuffled_words[clicked_index]
        if actual_word != expected_word:
            self.state = CaptchaState.FAILED
            self.result.success = False
            self.result.message = f"顺序错误，应是「{expected_word}」"
            data.clicked_order = []
            return self.result
        if len(data.clicked_order) >= data.target_count:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            next_word = data.words[len(data.clicked_order)]
            self.result.message = f"正确！请继续点击「{next_word}」"
        return self.result


class DifferenceClickCaptchaModel(CaptchaModel):
    """差异点击验证码模型"""
    def __init__(self):
        super().__init__(CaptchaType.DIFFERENCE_CLICK)
    def generate(self, config: CaptchaConfig):
        import random
        data = DifferenceClickCaptchaData()
        data.grid_cols = 3
        data.grid_rows = 3
        data.different_index = random.randint(0, 8)
        shapes = ["circle", "square", "triangle"]
        normal_shape = random.choice(shapes)
        different_shape = random.choice([s for s in shapes if s != normal_shape])
        colors = ['#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#FF9F43', '#A29BFE', '#FF6B9D', '#C44569']
        for i in range(9):
            data.images.append({
                'shape': normal_shape if i != data.different_index else different_shape,
                'color': colors[i],
                'label': f'格{i+1}'
            })
        data.clicked_index = -1
        self.difference_click_data = data
        self.state = CaptchaState.IDLE
        return data
    def verify(self, clicked_index: int) -> 'CaptchaResult':
        if not hasattr(self, 'difference_click_data') or self.difference_click_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        data = self.difference_click_data
        data.clicked_index = clicked_index
        self.result.attempts += 1
        if clicked_index == data.different_index:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            if self.result.attempts >= self.result.max_attempts:
                self.state = CaptchaState.FAILED
                self.result.message = "验证失败"
            else:
                self.state = CaptchaState.IDLE
                self.result.message = f"不是这里，还剩{self.result.max_attempts - self.result.attempts}次"
        return self.result


class NineGridCaptchaModel(CaptchaModel):
    """九宫格验证码模型"""
    def __init__(self):
        super().__init__(CaptchaType.NINE_GRID)
    def generate(self, config: CaptchaConfig):
        import random
        data = NineGridCaptchaData()
        data.target_text = "动物"
        data.instruction = "请点击所有动物"
        animals = ["dog", "cat", "bird", "fish", "rabbit", "fox", "bear", "deer", "monkey"]
        selected = animals.copy()
        random.shuffle(selected)
        data.grids = []
        data.target_indices = []
        for i, animal in enumerate(selected[:9]):
            is_target = animal in animals[:3]
            if is_target:
                data.target_indices.append(i)
            data.grids.append({'index': i, 'animal': animal, 'is_target': is_target})
        data.clicked_indices = []
        self.nine_grid_data = data
        self.state = CaptchaState.IDLE
        return data
    def verify(self, clicked_index: int) -> 'CaptchaResult':
        if not hasattr(self, 'nine_grid_data') or self.nine_grid_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        data = self.nine_grid_data
        if clicked_index in data.clicked_indices:
            return self.result
        data.clicked_indices.append(clicked_index)
        self.result.attempts += 1
        all_clicked = all(idx in data.clicked_indices for idx in data.target_indices)
        if all_clicked:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            remaining = [idx for idx in data.target_indices if idx not in data.clicked_indices]
            self.result.message = f"已选 {len(data.clicked_indices)}，还需选择 {len(remaining)} 个"
        return self.result


class SMSCaptchaModel(CaptchaModel):
    """短信验证码（模拟）模型"""
    def __init__(self):
        super().__init__(CaptchaType.SMS_MOCK)
    def generate(self, config: CaptchaConfig):
        import random
        data = SMSCaptchaData()
        data.code = ''.join(random.choices('0123456789', k=6))
        data.display_code = f"【模拟短信】您的验证码是：{data.code}"
        data.user_input = ""
        self.sms_data = data
        self.state = CaptchaState.IDLE
        return data
    def verify(self, user_input: str) -> 'CaptchaResult':
        if not hasattr(self, 'sms_data') or self.sms_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        data = self.sms_data
        data.user_input = user_input
        self.result.attempts += 1
        if user_input.strip() == data.code:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            if self.result.attempts >= self.result.max_attempts:
                self.state = CaptchaState.FAILED
                self.result.message = "验证失败"
            else:
                self.state = CaptchaState.IDLE
                self.result.message = f"验证码错误，还剩{self.result.max_attempts - self.result.attempts}次"
        return self.result


class ScratchCardCaptchaModel(CaptchaModel):
    """刮刮卡验证码模型"""
    def __init__(self):
        super().__init__(CaptchaType.SCRATCH_CARD)
    def generate(self, config: CaptchaConfig):
        import random
        data = ScratchCardCaptchaData()
        data.answer = ''.join(random.choices('0123456789', k=4))
        data.user_input = ""
        data.scratched = []
        self.scratch_card_data = data
        self.state = CaptchaState.IDLE
        return data
    def add_scratch(self, x: float, y: float):
        if not hasattr(self, 'scratch_card_data') or self.scratch_card_data is None:
            return
        data = self.scratch_card_data
        data.scratched.append((x, y))
        if len(data.scratched) > 50:
            self.state = CaptchaState.VERIFYING
    def verify(self, user_input: str) -> 'CaptchaResult':
        if not hasattr(self, 'scratch_card_data') or self.scratch_card_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        data = self.scratch_card_data
        data.user_input = user_input
        self.result.attempts += 1
        if user_input.strip() == data.answer:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            if self.result.attempts >= self.result.max_attempts:
                self.state = CaptchaState.FAILED
                self.result.message = "验证失败"
            else:
                self.state = CaptchaState.IDLE
                self.result.message = f"答案错误，还剩{self.result.max_attempts - self.result.attempts}次"
        return self.result


class AreaClickCaptchaModel(CaptchaModel):
    """面积验证模型"""
    def __init__(self):
        super().__init__(CaptchaType.AREA_CLICK)
    def generate(self, config: CaptchaConfig):
        import random, math
        data = AreaClickCaptchaData()
        data.target_type = random.choice(["largest", "smallest"])
        num_shapes = 5
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7']
        for i in range(num_shapes):
            radius = random.uniform(18, 45)
            x = random.uniform(50, 250)
            y = random.uniform(40, 150)
            data.shapes.append({
                'cx': x, 'cy': y, 'r': radius,
                'area': math.pi * radius * radius,
                'color': colors[i]
            })
        data.clicked_index = -1
        self.area_click_data = data
        self.state = CaptchaState.IDLE
        return data
    def verify(self, clicked_index: int) -> 'CaptchaResult':
        if not hasattr(self, 'area_click_data') or self.area_click_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        data = self.area_click_data
        data.clicked_index = clicked_index
        self.result.attempts += 1
        areas = [s['area'] for s in data.shapes]
        if data.target_type == "largest":
            target_idx = areas.index(max(areas))
        else:
            target_idx = areas.index(min(areas))
        if clicked_index == target_idx:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            if self.result.attempts >= self.result.max_attempts:
                self.state = CaptchaState.FAILED
                self.result.message = "验证失败"
            else:
                self.state = CaptchaState.IDLE
                self.result.message = f"不是这个，还剩{self.result.max_attempts - self.result.attempts}次"
        return self.result


class VoiceCaptchaModel(CaptchaModel):
    """语音验证码（模拟）模型"""
    def __init__(self):
        super().__init__(CaptchaType.VOICE_MOCK)
    def generate(self, config: CaptchaConfig):
        import random
        data = VoiceCaptchaData()
        data.code = ''.join(random.choices('0123456789', k=4))
        data.display_text = f"【模拟语音】请听播报：{data.code}"
        data.user_input = ""
        self.voice_data = data
        self.state = CaptchaState.IDLE
        return data
    def verify(self, user_input: str) -> 'CaptchaResult':
        if not hasattr(self, 'voice_data') or self.voice_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        data = self.voice_data
        data.user_input = user_input
        self.result.attempts += 1
        if user_input.strip() == data.code:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            if self.result.attempts >= self.result.max_attempts:
                self.state = CaptchaState.FAILED
                self.result.message = "验证失败"
            else:
                self.state = CaptchaState.IDLE
                self.result.message = f"输入错误，还剩{self.result.max_attempts - self.result.attempts}次"
        return self.result


class FontRecognizeCaptchaModel(CaptchaModel):
    """字体识别验证码模型"""
    def __init__(self):
        super().__init__(CaptchaType.FONT_RECOGNIZE)
        self.chars = "ABCD1234"
    def generate(self, config: CaptchaConfig):
        import random
        data = FontRecognizeCaptchaData()
        data.code = ''.join(random.choices(self.chars, k=4))
        cfg = config.get('text_captcha', {})
        width = cfg.get('width', 280)
        height = cfg.get('height', 100)
        for i, ch in enumerate(data.code):
            x = 30 + i * 60
            y = height / 2
            data.char_positions.append((x, y, 36, random.choice(['Arial', 'Courier', 'Times', 'Verdana'])))
        data.user_input = ""
        self.font_recognize_data = data
        self.state = CaptchaState.IDLE
        return data
    def verify(self, user_input: str) -> 'CaptchaResult':
        if not hasattr(self, 'font_recognize_data') or self.font_recognize_data is None:
            return CaptchaResult(success=False, message="验证码未生成")
        data = self.font_recognize_data
        data.user_input = user_input
        self.result.attempts += 1
        if user_input.upper().strip() == data.code:
            self.state = CaptchaState.SUCCESS
            self.result.success = True
            self.result.message = "验证成功"
            self.result.score = 1.0
        else:
            if self.result.attempts >= self.result.max_attempts:
                self.state = CaptchaState.FAILED
                self.result.message = "验证失败"
            else:
                self.state = CaptchaState.IDLE
                self.result.message = f"识别错误，还剩{self.result.max_attempts - self.result.attempts}次"
        return self.result


class BehaviorMockCaptchaModel(CaptchaModel):
    """无感验证（模拟）模型"""
    def __init__(self):
        super().__init__(CaptchaType.BEHAVIOR_MOCK)
    def generate(self, config: CaptchaConfig):
        import random
        data = BehaviorMockCaptchaData()
        data.fake_score = random.uniform(0.65, 0.98)
        data.status = "analyzing"
        data.progress = 0.0
        self.behavior_data = data
        self.state = CaptchaState.VERIFYING
        return data
    def simulate_check(self) -> 'CaptchaResult':
        if not hasattr(self, 'behavior_data') or self.behavior_data is None:
            return CaptchaResult(success=False, message="验证未生成")
        data = self.behavior_data
        data.progress = min(1.0, data.progress + 0.33)
        self.result.attempts += 1
        if data.progress >= 1.0:
            if data.fake_score > 0.8:
                self.state = CaptchaState.SUCCESS
                self.result.success = True
                self.result.message = f"无感验证通过（行为评分：{data.fake_score:.2f}）"
                self.result.score = data.fake_score
            else:
                self.state = CaptchaState.FAILED
                self.result.message = f"行为异常（行为评分：{data.fake_score:.2f}）"
        return self.result

