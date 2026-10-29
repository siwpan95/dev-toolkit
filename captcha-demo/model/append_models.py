"""临时脚本：向 captcha_model.py 追加新的 Model 类"""
import os

filepath = os.path.join(os.path.dirname(__file__), 'captcha_model.py')

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

new_models = r"""

# ========== 新增验证码 Model ==========

class WordOrderCaptchaModel(CaptchaModel):
    \"\"\"语序点选验证码模型\"\"\"
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
    \"\"\"差异点击验证码模型\"\"\"
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
    \"\"\"九宫格验证码模型\"\"\"
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
    \"\"\"短信验证码（模拟）模型\"\"\"
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
    \"\"\"刮刮卡验证码模型\"\"\"
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
    \"\"\"面积验证模型\"\"\"
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
    \"\"\"语音验证码（模拟）模型\"\"\"
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
    \"\"\"字体识别验证码模型\"\"\"
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
    \"\"\"无感验证（模拟）模型\"\"\"
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

"""

content = content + new_models

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("Done! Appended", len(new_models), "chars")
