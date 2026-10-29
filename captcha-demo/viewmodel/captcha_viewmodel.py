"""
人机验证 - ViewModel 层
处理业务逻辑，连接 Model 和 View
"""
import time
import math
from typing import Callable, Optional, Dict, Any, Tuple
from model.captcha_model import (
    CaptchaModel, CaptchaType, CaptchaState, CaptchaConfig, CaptchaResult,
    TextCaptchaModel, SliderCaptchaModel, PuzzleCaptchaModel,
    ClickCaptchaModel, RotateCaptchaModel, DragSortCaptchaModel,
    WordOrderCaptchaModel, DifferenceClickCaptchaModel, NineGridCaptchaModel,
    SMSCaptchaModel, ScratchCardCaptchaModel, AreaClickCaptchaModel,
    VoiceCaptchaModel, FontRecognizeCaptchaModel, BehaviorMockCaptchaModel
)


class BaseCaptchaViewModel:
    """验证码 ViewModel 基类"""
    
    def __init__(self, config: CaptchaConfig):
        self.config = config
        self.model: Optional[CaptchaModel] = None
        self.on_state_change: Optional[Callable] = None
        self.on_result: Optional[Callable[[CaptchaResult], None]] = None
        self.start_time: float = 0
    
    def set_callbacks(self, state_change: Callable, result_callback: Callable[[CaptchaResult], None]):
        self.on_state_change = state_change
        self.on_result = result_callback
    
    def notify_state_change(self):
        if self.on_state_change:
            self.on_state_change()
    
    def notify_result(self, result: CaptchaResult):
        if self.on_result:
            self.on_result(result)
    
    def create(self):
        """创建并生成验证码"""
        raise NotImplementedError
    
    def reset(self):
        """重置验证码"""
        if self.model:
            self.model.reset()
            self.create()
    
    def get_state(self) -> CaptchaState:
        return self.model.state if self.model else CaptchaState.IDLE
    
    def get_result(self) -> Optional[CaptchaResult]:
        return self.model.result if self.model else None


class TextCaptchaViewModel(BaseCaptchaViewModel):
    """文字验证码 ViewModel"""
    
    def __init__(self, config: CaptchaConfig):
        super().__init__(config)
        self.model = TextCaptchaModel()
    
    def create(self):
        self.model.generate(self.config)
        self.start_time = time.time()
        self.notify_state_change()
    
    def verify(self, user_input: str) -> CaptchaResult:
        result = self.model.verify(user_input)
        result.time_elapsed = time.time() - self.start_time
        self.notify_state_change()
        self.notify_result(result)
        return result


class SliderCaptchaViewModel(BaseCaptchaViewModel):
    """滑块验证码 ViewModel（缺口+拼图块模式）"""
    
    def __init__(self, config: CaptchaConfig):
        super().__init__(config)
        self.model = SliderCaptchaModel()
        self._drag_offset: float = 0
    
    def create(self):
        self.model.generate(self.config)
        self.start_time = time.time()
        self.notify_state_change()
    
    def start_drag(self, mouse_x: float):
        """开始拖动，鼠标在滑块上的偏移"""
        if self.model.slider_data:
            self._drag_offset = mouse_x - self.model.slider_data.slider_x
            self.model.slider_data.is_dragging = True
            self.model.state = CaptchaState.VERIFYING
    
    def drag(self, mouse_x: float):
        """拖动滑块，更新拼图块和滑块位置"""
        if self.model.slider_data and self.model.slider_data.is_dragging:
            data = self.model.slider_data
            max_x = data.track_width - data.piece_width
            new_x = mouse_x - self._drag_offset
            data.slider_x = max(0, min(new_x, max_x))
            data.piece_x = data.slider_x  # 拼图块跟随滑块
            self.notify_state_change()
    
    def end_drag(self):
        """结束拖动，验证位置"""
        if self.model.slider_data:
            self.model.slider_data.is_dragging = False
            result = self.model.verify(self.model.slider_data.piece_x)
            result.time_elapsed = time.time() - self.start_time
            self.notify_state_change()
            self.notify_result(result)
            return result
        return None
    
    def reset_slider(self):
        """重置滑块到初始位置"""
        if self.model.slider_data:
            self.model.slider_data.piece_x = 0
            self.model.slider_data.slider_x = 0
            self.model.state = CaptchaState.IDLE
            self.notify_state_change()


class PuzzleCaptchaViewModel(BaseCaptchaViewModel):
    """拼图验证码 ViewModel（数字华容道）"""
    
    def __init__(self, config: CaptchaConfig):
        super().__init__(config)
        self.model = PuzzleCaptchaModel()
    
    def create(self):
        self.model.generate(self.config)
        self.start_time = time.time()
        self.notify_state_change()
    
    def click(self, idx: int):
        """点击指定索引的块"""
        moved = self.model.move(idx)
        if moved:
            self.notify_state_change()
            # 自动检查是否完成
            self._check_complete()
    
    def _check_complete(self):
        """检查是否完成拼图"""
        data = self.model.puzzle_data
        if data is None:
            return None
        total = data.grid_size * data.grid_size
        expected = list(range(1, total)) + [0]
        if data.grid == expected:
            result = self.model.verify()
            result.time_elapsed = time.time() - self.start_time
            self.notify_state_change()
            self.notify_result(result)
            return result
        return None
    
    def verify(self) -> CaptchaResult:
        result = self.model.verify()
        result.time_elapsed = time.time() - self.start_time
        self.notify_state_change()
        self.notify_result(result)
        return result


class ClickCaptchaViewModel(BaseCaptchaViewModel):
    """点击验证码 ViewModel"""
    
    def __init__(self, config: CaptchaConfig):
        super().__init__(config)
        self.model = ClickCaptchaModel()
    
    def create(self):
        self.model.generate(self.config)
        self.start_time = time.time()
        self.notify_state_change()
    
    def click(self, x: float, y: float) -> CaptchaResult:
        result = self.model.verify(x, y)
        result.time_elapsed = time.time() - self.start_time
        self.notify_state_change()
        self.notify_result(result)
        return result
    
    def get_target_text(self) -> str:
        if self.model.click_data:
            targets = self.model.click_data.targets
            clicked = self.model.click_data.current_target_index
            remaining = targets[clicked:] if clicked < len(targets) else []
            return ' → '.join(remaining)
        return ""


class RotateCaptchaViewModel(BaseCaptchaViewModel):
    """旋转验证码 ViewModel"""
    
    def __init__(self, config: CaptchaConfig):
        super().__init__(config)
        self.model = RotateCaptchaModel()
        self.center = (0, 0)
        self.radius = 0
    
    def create(self):
        self.model.generate(self.config)
        self.start_time = time.time()
        self.notify_state_change()
    
    def set_geometry(self, center: Tuple[float, float], radius: float):
        self.center = center
        self.radius = radius
    
    def start_rotate(self, x: float, y: float):
        if self.model.rotate_data:
            self.model.rotate_data.is_rotating = True
            self.model.state = CaptchaState.VERIFYING
            self._update_angle(x, y)
    
    def rotate(self, x: float, y: float):
        if self.model.rotate_data and self.model.rotate_data.is_rotating:
            self._update_angle(x, y)
            self.notify_state_change()
    
    def _update_angle(self, x: float, y: float):
        dx = x - self.center[0]
        dy = y - self.center[1]
        angle = math.degrees(math.atan2(dy, dx))
        self.model.rotate_data.current_angle = angle
    
    def end_rotate(self):
        if self.model.rotate_data:
            self.model.rotate_data.is_rotating = False
            angle = self.model.rotate_data.current_angle
            result = self.model.verify(angle)
            result.time_elapsed = time.time() - self.start_time
            self.notify_state_change()
            self.notify_result(result)
            return result
        return None


class DragSortCaptchaViewModel(BaseCaptchaViewModel):
    """拖拽排序验证码 ViewModel"""
    
    def __init__(self, config: CaptchaConfig):
        super().__init__(config)
        self.model = DragSortCaptchaModel()
    
    def create(self):
        self.model.generate(self.config)
        self.start_time = time.time()
        self.notify_state_change()
    
    def start_drag(self, item_id: int, mouse_x: float, mouse_y: float):
        if self.model.drag_sort_data:
            for item in self.model.drag_sort_data.items:
                if item['id'] == item_id:
                    self.model.drag_sort_data.dragging_item = item_id
                    self.model.drag_sort_data.drag_offset = (
                        mouse_x - item['current_x'],
                        mouse_y - item['current_y']
                    )
                    self.model.state = CaptchaState.VERIFYING
                    break
    
    def drag(self, mouse_x: float, mouse_y: float):
        if self.model.drag_sort_data and self.model.drag_sort_data.dragging_item is not None:
            offset = self.model.drag_sort_data.drag_offset
            for item in self.model.drag_sort_data.items:
                if item['id'] == self.model.drag_sort_data.dragging_item:
                    item['current_x'] = mouse_x - offset[0]
                    item['current_y'] = mouse_y - offset[1]
                    break
            self.notify_state_change()
    
    def end_drag(self):
        if self.model.drag_sort_data:
            dragging_id = self.model.drag_sort_data.dragging_item
            self.model.drag_sort_data.dragging_item = None
            
            if dragging_id is not None:
                dragged_item = None
                for item in self.model.drag_sort_data.items:
                    if item['id'] == dragging_id:
                        dragged_item = item
                        break
                
                if dragged_item:
                    # 检查是否与其他item重叠，交换位置
                    swapped = False
                    for item in self.model.drag_sort_data.items:
                        if item['id'] != dragging_id:
                            if (abs(dragged_item['current_x'] - item['current_x']) < dragged_item['width'] * 0.8 and
                                abs(dragged_item['current_y'] - item['current_y']) < dragged_item['height'] * 0.8):
                                dragged_item['current_x'], item['current_x'] = item['current_x'], dragged_item['current_x']
                                dragged_item['current_y'], item['current_y'] = item['current_y'], dragged_item['current_y']
                                swapped = True
                                break
                    
                    # 没有重叠，吸附回最近的槽位
                    if not swapped:
                        cfg = self.config.get('drag_sort_captcha', {})
                        item_w = cfg.get('item_width', 70)
                        item_h = cfg.get('item_height', 70)
                        spacing = cfg.get('item_spacing', 10)
                        cw = cfg.get('width', 400)
                        start_x = (cw - (self.model.drag_sort_data.item_count * item_w + (self.model.drag_sort_data.item_count - 1) * spacing)) // 2
                        start_y = (cfg.get('height', 150) - item_h) // 2
                        
                        # 找到最近的空槽位
                        slot_positions = []
                        for i in range(self.model.drag_sort_data.item_count):
                            sx = start_x + i * (item_w + spacing)
                            sy = start_y
                            slot_positions.append((sx, sy))
                        
                        # 标记已占用的槽位
                        occupied = set()
                        for item in self.model.drag_sort_data.items:
                            if item['id'] != dragging_id:
                                for j, (sx, sy) in enumerate(slot_positions):
                                    if abs(item['current_x'] - sx) < 10 and abs(item['current_y'] - sy) < 10:
                                        occupied.add(j)
                                        break
                        
                        # 找到最近的空槽位
                        min_dist = float('inf')
                        nearest = None
                        for j, (sx, sy) in enumerate(slot_positions):
                            if j not in occupied:
                                dist = math.sqrt((dragged_item['current_x'] - sx)**2 + (dragged_item['current_y'] - sy)**2)
                                if dist < min_dist:
                                    min_dist = dist
                                    nearest = (sx, sy)
                        
                        if nearest:
                            dragged_item['current_x'] = nearest[0]
                            dragged_item['current_y'] = nearest[1]
            
            self.model.state = CaptchaState.IDLE
            self.notify_state_change()
            # 不自动验证！让用户自己点验证按钮
        return None
    
    def verify(self) -> CaptchaResult:
        """手动验证排序是否正确"""
        result = self.model.verify()
        result.time_elapsed = time.time() - self.start_time
        self.notify_state_change()
        self.notify_result(result)
        return result


class WordOrderCaptchaViewModel(BaseCaptchaViewModel):
    """语序点选验证码 ViewModel"""
    def __init__(self, config: CaptchaConfig):
        super().__init__(config)
        self.model = WordOrderCaptchaModel()
    def create(self):
        self.model.generate(self.config)
        self.start_time = time.time()
        self.notify_state_change()
    def click(self, clicked_index: int) -> CaptchaResult:
        result = self.model.verify(clicked_index)
        result.time_elapsed = time.time() - self.start_time
        self.notify_state_change()
        self.notify_result(result)
        return result


class DifferenceClickCaptchaViewModel(BaseCaptchaViewModel):
    """差异点击验证码 ViewModel"""
    def __init__(self, config: CaptchaConfig):
        super().__init__(config)
        self.model = DifferenceClickCaptchaModel()
    def create(self):
        self.model.generate(self.config)
        self.start_time = time.time()
        self.notify_state_change()
    def click(self, clicked_index: int) -> CaptchaResult:
        result = self.model.verify(clicked_index)
        result.time_elapsed = time.time() - self.start_time
        self.notify_state_change()
        self.notify_result(result)
        return result


class NineGridCaptchaViewModel(BaseCaptchaViewModel):
    """九宫格验证码 ViewModel"""
    def __init__(self, config: CaptchaConfig):
        super().__init__(config)
        self.model = NineGridCaptchaModel()
    def create(self):
        self.model.generate(self.config)
        self.start_time = time.time()
        self.notify_state_change()
    def click(self, clicked_index: int) -> CaptchaResult:
        result = self.model.verify(clicked_index)
        result.time_elapsed = time.time() - self.start_time
        self.notify_state_change()
        self.notify_result(result)
        return result


class SMSCaptchaViewModel(BaseCaptchaViewModel):
    """短信验证码（模拟） ViewModel"""
    def __init__(self, config: CaptchaConfig):
        super().__init__(config)
        self.model = SMSCaptchaModel()
    def create(self):
        self.model.generate(self.config)
        self.start_time = time.time()
        self.notify_state_change()
    def verify(self, user_input: str) -> CaptchaResult:
        result = self.model.verify(user_input)
        result.time_elapsed = time.time() - self.start_time
        self.notify_state_change()
        self.notify_result(result)
        return result


class ScratchCardCaptchaViewModel(BaseCaptchaViewModel):
    """刮刮卡验证码 ViewModel"""
    def __init__(self, config: CaptchaConfig):
        super().__init__(config)
        self.model = ScratchCardCaptchaModel()
        self._is_dragging = False
    def create(self):
        self.model.generate(self.config)
        self.start_time = time.time()
        self._is_dragging = False
        self.notify_state_change()
    def start_drag(self, x: float, y: float):
        self._is_dragging = True
        self.model.state = CaptchaState.VERIFYING
    def drag(self, x: float, y: float):
        if self._is_dragging:
            self.model.add_scratch(x, y)
            self.notify_state_change()
    def end_drag(self):
        self._is_dragging = False
        self.notify_state_change()
    def verify(self, user_input: str) -> CaptchaResult:
        result = self.model.verify(user_input)
        result.time_elapsed = time.time() - self.start_time
        self.notify_state_change()
        self.notify_result(result)
        return result


class AreaClickCaptchaViewModel(BaseCaptchaViewModel):
    """面积验证 ViewModel"""
    def __init__(self, config: CaptchaConfig):
        super().__init__(config)
        self.model = AreaClickCaptchaModel()
    def create(self):
        self.model.generate(self.config)
        self.start_time = time.time()
        self.notify_state_change()
    def click(self, clicked_index: int) -> CaptchaResult:
        result = self.model.verify(clicked_index)
        result.time_elapsed = time.time() - self.start_time
        self.notify_state_change()
        self.notify_result(result)
        return result


class VoiceCaptchaViewModel(BaseCaptchaViewModel):
    """语音验证码（模拟） ViewModel"""
    def __init__(self, config: CaptchaConfig):
        super().__init__(config)
        self.model = VoiceCaptchaModel()
    def create(self):
        self.model.generate(self.config)
        self.start_time = time.time()
        self.notify_state_change()
    def verify(self, user_input: str) -> CaptchaResult:
        result = self.model.verify(user_input)
        result.time_elapsed = time.time() - self.start_time
        self.notify_state_change()
        self.notify_result(result)
        return result


class FontRecognizeCaptchaViewModel(BaseCaptchaViewModel):
    """字体识别验证码 ViewModel"""
    def __init__(self, config: CaptchaConfig):
        super().__init__(config)
        self.model = FontRecognizeCaptchaModel()
    def create(self):
        self.model.generate(self.config)
        self.start_time = time.time()
        self.notify_state_change()
    def verify(self, user_input: str) -> CaptchaResult:
        result = self.model.verify(user_input)
        result.time_elapsed = time.time() - self.start_time
        self.notify_state_change()
        self.notify_result(result)
        return result


class BehaviorMockCaptchaViewModel(BaseCaptchaViewModel):
    """无感验证（模拟） ViewModel"""
    def __init__(self, config: CaptchaConfig):
        super().__init__(config)
        self.model = BehaviorMockCaptchaModel()
    def create(self):
        self.model.generate(self.config)
        self.start_time = time.time()
        self.notify_state_change()
    def simulate_check(self) -> CaptchaResult:
        result = self.model.simulate_check()
        result.time_elapsed = time.time() - self.start_time
        self.notify_state_change()
        self.notify_result(result)
        return result


class WordOrderCaptchaViewModel(BaseCaptchaViewModel):
    """语序点选验证码 ViewModel"""
    def __init__(self, config: CaptchaConfig):
        super().__init__(config)
        self.model = WordOrderCaptchaModel()
    def create(self):
        self.model.generate(self.config)
        self.start_time = time.time()
        self.notify_state_change()
    def click(self, clicked_index: int) -> CaptchaResult:
        result = self.model.verify(clicked_index)
        result.time_elapsed = time.time() - self.start_time
        self.notify_state_change()
        self.notify_result(result)
        return result


class DifferenceClickCaptchaViewModel(BaseCaptchaViewModel):
    """差异点击验证码 ViewModel"""
    def __init__(self, config: CaptchaConfig):
        super().__init__(config)
        self.model = DifferenceClickCaptchaModel()
    def create(self):
        self.model.generate(self.config)
        self.start_time = time.time()
        self.notify_state_change()
    def click(self, clicked_index: int) -> CaptchaResult:
        result = self.model.verify(clicked_index)
        result.time_elapsed = time.time() - self.start_time
        self.notify_state_change()
        self.notify_result(result)
        return result


class NineGridCaptchaViewModel(BaseCaptchaViewModel):
    """九宫格验证码 ViewModel"""
    def __init__(self, config: CaptchaConfig):
        super().__init__(config)
        self.model = NineGridCaptchaModel()
    def create(self):
        self.model.generate(self.config)
        self.start_time = time.time()
        self.notify_state_change()
    def click(self, clicked_index: int) -> CaptchaResult:
        result = self.model.verify(clicked_index)
        result.time_elapsed = time.time() - self.start_time
        self.notify_state_change()
        self.notify_result(result)
        return result


class SMSCaptchaViewModel(BaseCaptchaViewModel):
    """短信验证码（模拟） ViewModel"""
    def __init__(self, config: CaptchaConfig):
        super().__init__(config)
        self.model = SMSCaptchaModel()
    def create(self):
        self.model.generate(self.config)
        self.start_time = time.time()
        self.notify_state_change()
    def verify(self, user_input: str) -> CaptchaResult:
        result = self.model.verify(user_input)
        result.time_elapsed = time.time() - self.start_time
        self.notify_state_change()
        self.notify_result(result)
        return result


class ScratchCardCaptchaViewModel(BaseCaptchaViewModel):
    """刮刮卡验证码 ViewModel"""
    def __init__(self, config: CaptchaConfig):
        super().__init__(config)
        self.model = ScratchCardCaptchaModel()
        self._is_dragging = False
    def create(self):
        self.model.generate(self.config)
        self.start_time = time.time()
        self._is_dragging = False
        self.notify_state_change()
    def start_drag(self, x: float, y: float):
        self._is_dragging = True
        self.model.state = CaptchaState.VERIFYING
    def drag(self, x: float, y: float):
        if self._is_dragging:
            self.model.add_scratch(x, y)
            self.notify_state_change()
    def end_drag(self):
        self._is_dragging = False
        self.notify_state_change()
    def verify(self, user_input: str) -> CaptchaResult:
        result = self.model.verify(user_input)
        result.time_elapsed = time.time() - self.start_time
        self.notify_state_change()
        self.notify_result(result)
        return result


class AreaClickCaptchaViewModel(BaseCaptchaViewModel):
    """面积验证 ViewModel"""
    def __init__(self, config: CaptchaConfig):
        super().__init__(config)
        self.model = AreaClickCaptchaModel()
    def create(self):
        self.model.generate(self.config)
        self.start_time = time.time()
        self.notify_state_change()
    def click(self, clicked_index: int) -> CaptchaResult:
        result = self.model.verify(clicked_index)
        result.time_elapsed = time.time() - self.start_time
        self.notify_state_change()
        self.notify_result(result)
        return result


class VoiceCaptchaViewModel(BaseCaptchaViewModel):
    """语音验证码（模拟） ViewModel"""
    def __init__(self, config: CaptchaConfig):
        super().__init__(config)
        self.model = VoiceCaptchaModel()
    def create(self):
        self.model.generate(self.config)
        self.start_time = time.time()
        self.notify_state_change()
    def verify(self, user_input: str) -> CaptchaResult:
        result = self.model.verify(user_input)
        result.time_elapsed = time.time() - self.start_time
        self.notify_state_change()
        self.notify_result(result)
        return result


class FontRecognizeCaptchaViewModel(BaseCaptchaViewModel):
    """字体识别验证码 ViewModel"""
    def __init__(self, config: CaptchaConfig):
        super().__init__(config)
        self.model = FontRecognizeCaptchaModel()
    def create(self):
        self.model.generate(self.config)
        self.start_time = time.time()
        self.notify_state_change()
    def verify(self, user_input: str) -> CaptchaResult:
        result = self.model.verify(user_input)
        result.time_elapsed = time.time() - self.start_time
        self.notify_state_change()
        self.notify_result(result)
        return result


class BehaviorMockCaptchaViewModel(BaseCaptchaViewModel):
    """无感验证（模拟） ViewModel"""
    def __init__(self, config: CaptchaConfig):
        super().__init__(config)
        self.model = BehaviorMockCaptchaModel()
    def create(self):
        self.model.generate(self.config)
        self.start_time = time.time()
        self.notify_state_change()
    def simulate_check(self) -> CaptchaResult:
        result = self.model.simulate_check()
        result.time_elapsed = time.time() - self.start_time
        self.notify_state_change()
        self.notify_result(result)
        return result


class WordOrderCaptchaViewModel(BaseCaptchaViewModel):
    """语序点选验证码 ViewModel"""
    def __init__(self, config: CaptchaConfig):
        super().__init__(config)
        self.model = WordOrderCaptchaModel()
    def create(self):
        self.model.generate(self.config)
        self.start_time = time.time()
        self.notify_state_change()
    def click(self, clicked_index: int) -> CaptchaResult:
        result = self.model.verify(clicked_index)
        result.time_elapsed = time.time() - self.start_time
        self.notify_state_change()
        self.notify_result(result)
        return result


class DifferenceClickCaptchaViewModel(BaseCaptchaViewModel):
    """差异点击验证码 ViewModel"""
    def __init__(self, config: CaptchaConfig):
        super().__init__(config)
        self.model = DifferenceClickCaptchaModel()
    def create(self):
        self.model.generate(self.config)
        self.start_time = time.time()
        self.notify_state_change()
    def click(self, clicked_index: int) -> CaptchaResult:
        result = self.model.verify(clicked_index)
        result.time_elapsed = time.time() - self.start_time
        self.notify_state_change()
        self.notify_result(result)
        return result


class NineGridCaptchaViewModel(BaseCaptchaViewModel):
    """九宫格验证码 ViewModel"""
    def __init__(self, config: CaptchaConfig):
        super().__init__(config)
        self.model = NineGridCaptchaModel()
    def create(self):
        self.model.generate(self.config)
        self.start_time = time.time()
        self.notify_state_change()
    def click(self, clicked_index: int) -> CaptchaResult:
        result = self.model.verify(clicked_index)
        result.time_elapsed = time.time() - self.start_time
        self.notify_state_change()
        self.notify_result(result)
        return result


class SMSCaptchaViewModel(BaseCaptchaViewModel):
    """短信验证码（模拟） ViewModel"""
    def __init__(self, config: CaptchaConfig):
        super().__init__(config)
        self.model = SMSCaptchaModel()
    def create(self):
        self.model.generate(self.config)
        self.start_time = time.time()
        self.notify_state_change()
    def verify(self, user_input: str) -> CaptchaResult:
        result = self.model.verify(user_input)
        result.time_elapsed = time.time() - self.start_time
        self.notify_state_change()
        self.notify_result(result)
        return result


class ScratchCardCaptchaViewModel(BaseCaptchaViewModel):
    """刮刮卡验证码 ViewModel"""
    def __init__(self, config: CaptchaConfig):
        super().__init__(config)
        self.model = ScratchCardCaptchaModel()
        self._is_dragging = False
    def create(self):
        self.model.generate(self.config)
        self.start_time = time.time()
        self._is_dragging = False
        self.notify_state_change()
    def start_drag(self, x: float, y: float):
        self._is_dragging = True
        self.model.state = CaptchaState.VERIFYING
    def drag(self, x: float, y: float):
        if self._is_dragging:
            self.model.add_scratch(x, y)
            self.notify_state_change()
    def end_drag(self):
        self._is_dragging = False
        self.notify_state_change()
    def verify(self, user_input: str) -> CaptchaResult:
        result = self.model.verify(user_input)
        result.time_elapsed = time.time() - self.start_time
        self.notify_state_change()
        self.notify_result(result)
        return result


class AreaClickCaptchaViewModel(BaseCaptchaViewModel):
    """面积验证 ViewModel"""
    def __init__(self, config: CaptchaConfig):
        super().__init__(config)
        self.model = AreaClickCaptchaModel()
    def create(self):
        self.model.generate(self.config)
        self.start_time = time.time()
        self.notify_state_change()
    def click(self, clicked_index: int) -> CaptchaResult:
        result = self.model.verify(clicked_index)
        result.time_elapsed = time.time() - self.start_time
        self.notify_state_change()
        self.notify_result(result)
        return result


class VoiceCaptchaViewModel(BaseCaptchaViewModel):
    """语音验证码（模拟） ViewModel"""
    def __init__(self, config: CaptchaConfig):
        super().__init__(config)
        self.model = VoiceCaptchaModel()
    def create(self):
        self.model.generate(self.config)
        self.start_time = time.time()
        self.notify_state_change()
    def verify(self, user_input: str) -> CaptchaResult:
        result = self.model.verify(user_input)
        result.time_elapsed = time.time() - self.start_time
        self.notify_state_change()
        self.notify_result(result)
        return result


class FontRecognizeCaptchaViewModel(BaseCaptchaViewModel):
    """字体识别验证码 ViewModel"""
    def __init__(self, config: CaptchaConfig):
        super().__init__(config)
        self.model = FontRecognizeCaptchaModel()
    def create(self):
        self.model.generate(self.config)
        self.start_time = time.time()
        self.notify_state_change()
    def verify(self, user_input: str) -> CaptchaResult:
        result = self.model.verify(user_input)
        result.time_elapsed = time.time() - self.start_time
        self.notify_state_change()
        self.notify_result(result)
        return result


class BehaviorMockCaptchaViewModel(BaseCaptchaViewModel):
    """无感验证（模拟） ViewModel"""
    def __init__(self, config: CaptchaConfig):
        super().__init__(config)
        self.model = BehaviorMockCaptchaModel()
    def create(self):
        self.model.generate(self.config)
        self.start_time = time.time()
        self.notify_state_change()
    def simulate_check(self) -> CaptchaResult:
        result = self.model.simulate_check()
        result.time_elapsed = time.time() - self.start_time
        self.notify_state_change()
        self.notify_result(result)
        return result


class CaptchaFactory:
    """验证码工厂"""
    
    _viewmodels: Dict[str, type] = {
        'text': TextCaptchaViewModel,
        'slider': SliderCaptchaViewModel,
        'puzzle': PuzzleCaptchaViewModel,
        'click': ClickCaptchaViewModel,
        'rotate': RotateCaptchaViewModel,
        'drag_sort': DragSortCaptchaViewModel,
        'word_order': WordOrderCaptchaViewModel,
        'difference_click': DifferenceClickCaptchaViewModel,
        'nine_grid': NineGridCaptchaViewModel,
        'sms_mock': SMSCaptchaViewModel,
        'scratch_card': ScratchCardCaptchaViewModel,
        'area_click': AreaClickCaptchaViewModel,
        'voice_mock': VoiceCaptchaViewModel,
        'font_recognize': FontRecognizeCaptchaViewModel,
        'behavior_mock': BehaviorMockCaptchaViewModel,
    }
    
    @classmethod
    def create(cls, captcha_type: str, config: CaptchaConfig) -> BaseCaptchaViewModel:
        vm_class = cls._viewmodels.get(captcha_type)
        if vm_class:
            return vm_class(config)
        raise ValueError(f"未知的验证码类型: {captcha_type}")
    
    @classmethod
    def get_types(cls) -> Dict[str, str]:
        return {
            'text': '文字验证码',
            'slider': '滑块验证码',
            'puzzle': '拼图验证码',
            'click': '点击验证码',
            'rotate': '旋转验证码',
            'drag_sort': '拖拽排序验证码',
            'word_order': '语序点选验证码',
            'difference_click': '差异点击验证码',
            'nine_grid': '九宫格验证码',
            'sms_mock': '短信验证（模拟）',
            'scratch_card': '刮刮卡验证码',
            'area_click': '面积验证',
            'voice_mock': '语音验证（模拟）',
            'font_recognize': '字体识别验证码',
            'behavior_mock': '无感验证（模拟）',
        }
