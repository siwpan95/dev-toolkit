# -*- coding: utf-8 -*-
"""
__main__.py — python -m yasuo 入口
"""
from .gui_app import CryptoGUI


def main():
    gui = CryptoGUI()
    gui.run()


if __name__ == "__main__":
    main()
