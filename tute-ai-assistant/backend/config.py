import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 项目基础目录（绝对路径）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Config:
    """应用配置类"""

    # Flask 配置
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')
    FLASK_PORT = int(os.environ.get('FLASK_PORT', 5000))

    # AI API 密钥
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
    DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
    KIMI_API_KEY = os.environ.get('KIMI_API_KEY', '')

    # 知识库文件路径（使用绝对路径，确保服务器运行时可找到）
    KNOWLEDGE_BASE_DIR = os.environ.get('KNOWLEDGE_BASE_DIR') or os.path.join(BASE_DIR, 'knowledge_base')

    # AI 助手配置
    AI_NAME = "天职小咕"
    AI_AVATAR_PATH = "/static/avatar.png"

    @classmethod
    def get_active_api_key(cls):
        """获取可用的 API 密钥"""
        if cls.KIMI_API_KEY:
            return 'kimi', cls.KIMI_API_KEY
        elif cls.GEMINI_API_KEY:
            return 'gemini', cls.GEMINI_API_KEY
        elif cls.OPENAI_API_KEY:
            return 'openai', cls.OPENAI_API_KEY
        elif cls.DEEPSEEK_API_KEY:
            return 'deepseek', cls.DEEPSEEK_API_KEY
        return None, None
