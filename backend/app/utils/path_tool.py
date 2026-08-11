"""
路径工具
统一管理项目中的路径，避免硬编码相对路径带来的定位问题。
"""

import os
from pathlib import Path


# backend/app/utils/path_tool.py

def get_root_path() -> Path:
    """
    获取项目的根目录路径。
    因此从当前文件向上回溯 3 级即可到达根目录。
    如果你的项目结构不同，请相应调整 parents 的层级。
    """
    # __file__ 指向当前文件 path_tool.py
    # .resolve() 将路径转换为绝对路径，并解析符号链接
    # .parents[2] 向上回溯 3 级: path_tool.py -> utils -> app -> backend（ROOT）
    return Path(__file__).resolve().parents[2]


def get_abs_path(relative_path: str = "") -> Path:
    """
    基于项目根目录获取绝对路径。

    Args:
        relative_path (str): 相对于项目根目录的路径字符串。
                             例如: "app/config.yaml" 或 "data/logs"
    
    Returns:
        Path: 拼接后的绝对路径对象。
    """
    root = get_root_path()
    if relative_path:
        return root / relative_path
    return root


# 根目录：backend/
ROOT_PATH = get_root_path()

if __name__ == '__main__':
    print(get_root_path())
    print(get_abs_path("app/data"))