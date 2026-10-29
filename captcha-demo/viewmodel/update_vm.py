"""更新 captcha_viewmodel.py：添加新 ViewModel 并更新 Factory"""
import os

filepath = os.path.join(os.path.dirname(__file__), 'captcha_viewmodel.py')

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 插入新 ViewModel 类
new_vms = '''

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

'''

content = content.replace('\n\nclass CaptchaFactory:', new_vms + '\nclass CaptchaFactory:')

# 2. 更新 _viewmodels
old_vms = """    _viewmodels: Dict[str, type] = {
        'text': TextCaptchaViewModel,
        'slider': SliderCaptchaViewModel,
        'puzzle': PuzzleCaptchaViewModel,
        'click': ClickCaptchaViewModel,
        'rotate': RotateCaptchaViewModel,
        'drag_sort': DragSortCaptchaViewModel,
    }"""

new_vms_dict = """    _viewmodels: Dict[str, type] = {
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
    }"""

content = content.replace(old_vms, new_vms_dict)

# 3. 更新 get_types
old_types = """    def get_types(cls) -> Dict[str, str]:
        return {
            'text': '文字验证码',
            'slider': '滑块验证码',
            'puzzle': '拼图验证码',
            'click': '点击验证码',
            'rotate': '旋转验证码',
            'drag_sort': '拖拽排序验证码',
        }"""

new_types = """    def get_types(cls) -> Dict[str, str]:
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
        }"""

content = content.replace(old_types, new_types)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("ViewModel updated successfully!")
