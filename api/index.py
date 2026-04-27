"""
Vercel Serverless Function 入口
"""
import sys
import os

# 添加 backend 目录到 Python 路径
backend_dir = os.path.join(os.path.dirname(__file__), '..', 'tute-ai-assistant', 'backend')
backend_dir = os.path.abspath(backend_dir)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# 导入 Flask 应用
from app import app

# Vercel 使用 'app' 变量作为 WSGI 入口
# 不需要额外的 handler 类
