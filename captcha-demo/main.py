#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
人机验证演示系统
================
采用 MVVM 架构，py 与 json 分离，使用 tkinter Canvas 绘制界面。

覆盖的验证码类型：
1. 文字验证码 - 在干扰背景中识别文字字符
2. 滑块验证码 - 拖动滑块填补缺口
3. 拼图验证码 - 将碎片拼回正确位置
4. 点击验证码 - 按顺序点击指定目标
5. 旋转验证码 - 旋转图片至正确方向
6. 拖拽排序验证码 - 将元素按正确顺序排列

运行方式:
    python main.py

项目结构:
    captcha_demo/
    ├── main.py              # 程序入口
    ├── config/
    │   └── captcha_config.json   # 配置文件
    ├── model/
    │   └── captcha_model.py      # 数据模型 (Model)
    ├── viewmodel/
    │   └── captcha_viewmodel.py  # 业务逻辑 (ViewModel)
    └── view/
        ├── main_window.py        # 主窗口
        └── captcha_views.py      # 验证码视图 (View)
"""

import sys
import os

# 将项目根目录加入路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from view.main_window import run

if __name__ == '__main__':
    run()
