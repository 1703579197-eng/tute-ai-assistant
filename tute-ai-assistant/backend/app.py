"""
天津职业技术师范大学校园AI助手 - 后端服务
基于 Flask + RAG (检索增强生成) 的 API 服务
Vercel 部署优化版本
"""

import os
import sys
import hashlib

# ==================== 路径配置（Vercel 兼容 - 彻底绝对化）====================

# 使用绝对路径确保在 Serverless 环境下能正确找到文件
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, '..', 'frontend')
FRONTEND_DIR = os.path.abspath(FRONTEND_DIR)  # 转换为绝对路径
KNOWLEDGE_BASE_DIR = os.path.join(BASE_DIR, 'knowledge_base')
KNOWLEDGE_BASE_DIR = os.path.abspath(KNOWLEDGE_BASE_DIR)  # 转换为绝对路径

print(f"[INIT] BASE_DIR: {BASE_DIR}", flush=True)
print(f"[INIT] FRONTEND_DIR: {FRONTEND_DIR}", flush=True)
print(f"[INIT] KNOWLEDGE_BASE_DIR: {KNOWLEDGE_BASE_DIR}", flush=True)
print(f"[INIT] 当前工作目录: {os.getcwd()}", flush=True)

# 确保知识库目录存在
try:
    os.makedirs(KNOWLEDGE_BASE_DIR, exist_ok=True)
    print(f"[INIT] 知识库目录已确保存在", flush=True)
except Exception as e:
    print(f"[ERROR] 创建知识库目录失败: {e}", flush=True)

from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS

# 尝试导入 config，如果失败则使用默认配置
try:
    from config import Config
    print(f"[INIT] 配置文件加载成功", flush=True)
except Exception as e:
    print(f"[WARN] 加载 config.py 失败: {e}，使用默认配置", flush=True)
    class Config:
        AI_NAME = "天职小咕"
        AI_AVATAR_PATH = "/static/avatar.png"
        KIMI_API_KEY = os.environ.get('KIMI_API_KEY', '')
        GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
        OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
        DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')

        @classmethod
        def get_active_api_key(cls):
            if cls.KIMI_API_KEY:
                return 'kimi', cls.KIMI_API_KEY
            elif cls.GEMINI_API_KEY:
                return 'gemini', cls.GEMINI_API_KEY
            elif cls.OPENAI_API_KEY:
                return 'openai', cls.OPENAI_API_KEY
            elif cls.DEEPSEEK_API_KEY:
                return 'deepseek', cls.DEEPSEEK_API_KEY
            return None, None

# 尝试导入 RAG 相关库
try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_community.vectorstores import FAISS
    print(f"[INIT] RAG 库导入成功", flush=True)
    RAG_AVAILABLE = True
except Exception as e:
    print(f"[WARN] RAG 库导入失败: {e}", flush=True)
    RAG_AVAILABLE = False

# ==================== Flask 应用初始化 ====================

app = Flask(__name__)

# 配置 CORS - 允许所有来源访问
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

print(f"[INIT] Flask 应用初始化完成", flush=True)

# ==================== 环境变量检查 ====================

def check_api_key():
    """检查 API 密钥是否配置，返回 (provider, api_key, error_message)"""
    try:
        provider, api_key = Config.get_active_api_key()
    except Exception as e:
        print(f"[ERROR] 获取 API 密钥失败: {e}", flush=True)
        return None, None, f"获取 API 密钥失败: {e}"

    if not api_key:
        error_msg = (
            "未配置 API 密钥！请在 Vercel 环境变量中设置以下任一密钥："
            "KIMI_API_KEY、GEMINI_API_KEY、OPENAI_API_KEY 或 DEEPSEEK_API_KEY"
        )
        print(f"[ERROR] {error_msg}", flush=True)
        return None, None, error_msg

    print(f"[OK] API 提供商: {provider}", flush=True)
    return provider, api_key, None

# ==================== RAG 向量检索系统 ====================

class VectorStore:
    """基于 FAISS 的向量检索系统"""

    def __init__(self):
        self.vectorstore = None
        self.embeddings = None
        self.text_splitter = None
        if RAG_AVAILABLE:
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=500,
                chunk_overlap=50,
                separators=["\n\n", "\n", "。", "；", " ", ""]
            )
            print(f"[INIT] VectorStore 初始化完成", flush=True)
        else:
            print(f"[WARN] VectorStore 初始化失败 - RAG 不可用", flush=True)

    def init_embeddings(self):
        """初始化 Embedding 模型"""
        if not RAG_AVAILABLE:
            print(f"[WARN] 无法初始化 Embedding - RAG 库不可用", flush=True)
            return False

        if self.embeddings is None:
            print(f"[INIT] 正在加载 Embedding 模型...", flush=True)
            try:
                self.embeddings = HuggingFaceEmbeddings(
                    model_name="shibing624/text2vec-base-chinese",
                    model_kwargs={'device': 'cpu'},
                    encode_kwargs={'normalize_embeddings': True}
                )
                print(f"[OK] Embedding 模型加载完成！", flush=True)
                return True
            except Exception as e:
                print(f"[ERROR] Embedding 模型加载失败: {e}", flush=True)
                return False
        return True

    def load_and_index_documents(self):
        """加载文档并建立向量索引 - 带容错处理"""
        print(f"[INIT] 开始加载知识库...", flush=True)

        if not RAG_AVAILABLE:
            print(f"[WARN] RAG 库不可用，跳过知识库加载", flush=True)
            return True  # 允许空知识库启动

        if not self.init_embeddings():
            print(f"[WARN] Embedding 初始化失败，使用空知识库", flush=True)
            return True  # 允许空知识库启动

        all_chunks = []

        # 优先使用环境变量配置的路径，否则使用默认路径
        kb_file = os.environ.get('KNOWLEDGE_FILE_PATH') or os.path.join(KNOWLEDGE_BASE_DIR, 'custom_knowledge.txt')
        kb_file = os.path.abspath(kb_file)

        print(f"[INIT] 知识库文件路径: {kb_file}", flush=True)
        print(f"[INIT] 检查文件是否存在: {os.path.exists(kb_file)}", flush=True)

        # 检查文件是否存在
        if os.path.exists(kb_file) and os.path.isfile(kb_file):
            try:
                print(f"[INIT] 正在读取知识库文件...", flush=True)
                with open(kb_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if content.strip():
                        chunks = self.text_splitter.split_text(content)
                        all_chunks.extend(chunks)
                        print(f"[OK] 知识库加载成功: {len(chunks)} 个片段", flush=True)
                    else:
                        print(f"[WARN] 知识库文件为空: {kb_file}", flush=True)
            except Exception as e:
                print(f"[ERROR] 读取知识库文件失败: {e}", flush=True)
                # 容错：返回空知识库，不阻塞程序
                print(f"[WARN] 使用空知识库继续启动", flush=True)
                return True
        else:
            print(f"[WARN] 知识库文件不存在: {kb_file}", flush=True)
            # 尝试列出 knowledge_base 目录内容
            try:
                if os.path.exists(KNOWLEDGE_BASE_DIR):
                    files = os.listdir(KNOWLEDGE_BASE_DIR)
                    print(f"[INFO] knowledge_base 目录内容: {files}", flush=True)
                else:
                    print(f"[WARN] knowledge_base 目录不存在", flush=True)
            except Exception as e:
                print(f"[ERROR] 无法列出目录内容: {e}", flush=True)

        if all_chunks:
            try:
                # 构建元数据
                metadatas = [{"source": "知识库", "chunk_index": i} for i in range(len(all_chunks))]

                # 创建 FAISS 向量库
                print(f"[INIT] 正在构建向量索引，共 {len(all_chunks)} 个片段...", flush=True)
                self.vectorstore = FAISS.from_texts(
                    texts=all_chunks,
                    embedding=self.embeddings,
                    metadatas=metadatas
                )
                print(f"[OK] 向量索引构建完成！", flush=True)
                return True
            except Exception as e:
                print(f"[ERROR] 构建向量索引失败: {e}", flush=True)
                # 容错：允许空知识库启动
                print(f"[WARN] 使用空知识库继续启动", flush=True)
                return True
        else:
            print(f"[WARN] 知识库为空，将使用通用模式回答问题", flush=True)
            return True  # 允许空知识库启动

    def search(self, query: str, k: int = 3):
        """检索与问题最相关的片段"""
        if self.vectorstore is None:
            return []

        try:
            results = self.vectorstore.similarity_search(query, k=k)
            return results
        except Exception as e:
            print(f"[ERROR] 向量检索失败: {e}", flush=True)
            return []


# 全局向量库实例
vector_store = VectorStore()

# 启动就绪标志 - 用于健康检查
is_ready = False
startup_error = None


# ==================== 对话历史管理 ====================

class ChatHistory:
    """简单的对话历史管理器（内存存储）"""

    def __init__(self, max_rounds: int = 5):
        self.max_rounds = max_rounds
        self.history = {}

    def get_user_id(self, request) -> str:
        """获取用户标识"""
        ip = request.remote_addr or 'unknown'
        ua = request.headers.get('User-Agent', '')
        return hashlib.md5(f"{ip}:{ua}".encode()).hexdigest()[:16]

    def add_message(self, user_id: str, role: str, content: str):
        """添加一条消息到历史"""
        if user_id not in self.history:
            self.history[user_id] = []

        self.history[user_id].append({
            "role": role,
            "content": content
        })

        # 只保留最近 max_rounds 轮
        max_messages = self.max_rounds * 2
        if len(self.history[user_id]) > max_messages:
            self.history[user_id] = self.history[user_id][-max_messages:]

    def get_history(self, user_id: str) -> list:
        """获取用户的对话历史"""
        return self.history.get(user_id, [])

    def clear_history(self, user_id: str):
        """清空用户的对话历史"""
        if user_id in self.history:
            del self.history[user_id]

    def format_history_for_prompt(self, user_id: str) -> str:
        """将历史格式化为字符串"""
        history = self.get_history(user_id)
        if not history:
            return "（暂无历史对话）"

        lines = []
        for msg in history:
            role_name = "学生" if msg["role"] == "user" else "学长"
            lines.append(f"{role_name}：{msg['content']}")

        return "\n".join(lines)


# 全局对话历史实例
chat_history = ChatHistory(max_rounds=5)


# ==================== 知识库内容加载（带容错）====================

def load_handbook_content():
    """
    加载手册内容 - 带容错处理
    如果文件不存在或读取失败，返回默认字符串
    """
    kb_file = os.environ.get('KNOWLEDGE_FILE_PATH') or os.path.join(KNOWLEDGE_BASE_DIR, 'custom_knowledge.txt')
    kb_file = os.path.abspath(kb_file)

    print(f"[INIT] 尝试加载手册: {kb_file}", flush=True)

    if not os.path.exists(kb_file):
        print(f"[ERROR] 手册文件不存在: {kb_file}", flush=True)
        print(f"[WARN] 返回默认内容: '手册正在维护中'", flush=True)
        return "手册正在维护中，请稍后再试。"

    try:
        with open(kb_file, 'r', encoding='utf-8') as f:
            content = f.read()
            if content.strip():
                print(f"[OK] 手册加载成功，内容长度: {len(content)} 字符", flush=True)
                return content
            else:
                print(f"[WARN] 手册文件为空", flush=True)
                return "手册内容为空，请联系管理员。"
    except Exception as e:
        print(f"[ERROR] 读取手册失败: {e}", flush=True)
        return "手册读取失败，请稍后重试。"


# ==================== AI API 调用 ====================

def call_kimi_api(api_key: str, system_prompt: str, user_message: str, history: list = None):
    """调用 Kimi (Moonshot AI) API"""
    try:
        print(f"[API] 开始调用 Kimi API...", flush=True)
        from openai import OpenAI

        client = OpenAI(
            api_key=api_key,
            base_url="https://api.moonshot.cn/v1"
        )

        messages = [{"role": "system", "content": system_prompt}]

        if history:
            for msg in history:
                messages.append({
                    "role": "user" if msg["role"] == "user" else "assistant",
                    "content": msg["content"]
                })

        messages.append({"role": "user", "content": user_message})

        response = client.chat.completions.create(
            model="moonshot-v1-8k",
            messages=messages,
            temperature=0.7,
            max_tokens=2000
        )

        if response.choices and len(response.choices) > 0:
            reply = response.choices[0].message.content
            print(f"[API] Kimi API 调用成功", flush=True)
            return {'success': True, 'reply': reply}
        else:
            return {'success': False, 'error': 'API 返回空响应'}

    except Exception as e:
        print(f"[ERROR] Kimi API 调用失败: {e}", flush=True)
        return {'success': False, 'error': f'Kimi API 调用失败: {str(e)}'}


def call_gemini_api(api_key: str, system_prompt: str, user_message: str, history: list = None):
    """调用 Google Gemini API"""
    try:
        print(f"[API] 开始调用 Gemini API...", flush=True)
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro')

        full_prompt = system_prompt

        if history:
            full_prompt += "\n\n【历史对话】\n"
            for msg in history:
                role_name = "学生" if msg["role"] == "user" else "学长"
                full_prompt += f"{role_name}：{msg['content']}\n"

        full_prompt += f"\n学生现在问：{user_message}"

        response = model.generate_content(full_prompt)

        if response and response.text:
            print(f"[API] Gemini API 调用成功", flush=True)
            return {'success': True, 'reply': response.text}
        else:
            return {'success': False, 'error': 'API 返回空响应'}

    except Exception as e:
        print(f"[ERROR] Gemini API 调用失败: {e}", flush=True)
        return {'success': False, 'error': f'Gemini API 调用失败: {str(e)}'}


def call_openai_api(api_key: str, system_prompt: str, user_message: str,
                    model: str = 'gpt-3.5-turbo', history: list = None):
    """调用 OpenAI API (或兼容接口如 DeepSeek)"""
    try:
        print(f"[API] 开始调用 OpenAI/DeepSeek API...", flush=True)
        from openai import OpenAI

        if 'deepseek' in model.lower():
            client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")
            model = "deepseek-chat"
        else:
            client = OpenAI(api_key=api_key)

        messages = [{"role": "system", "content": system_prompt}]

        if history:
            for msg in history:
                messages.append({
                    "role": "user" if msg["role"] == "user" else "assistant",
                    "content": msg["content"]
                })

        messages.append({"role": "user", "content": user_message})

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7,
            max_tokens=2000
        )

        if response.choices and len(response.choices) > 0:
            reply = response.choices[0].message.content
            print(f"[API] OpenAI/DeepSeek API 调用成功", flush=True)
            return {'success': True, 'reply': reply}
        else:
            return {'success': False, 'error': 'API 返回空响应'}

    except Exception as e:
        print(f"[ERROR] OpenAI API 调用失败: {e}", flush=True)
        return {'success': False, 'error': f'OpenAI API 调用失败: {str(e)}'}


# ==================== 核心回复生成逻辑 ====================

def build_system_prompt(retrieved_docs: list, user_question: str, history_text: str) -> str:
    """构建学长风格的 System Prompt"""

    context_parts = []
    for i, doc in enumerate(retrieved_docs, 1):
        source = doc.metadata.get("source", "知识库")
        context_parts.append(f"【参考资料{i}】（来自{source}）\n{doc.page_content}")

    context_text = "\n\n".join(context_parts) if context_parts else "（本次问题未匹配到知识库内容）"

    prompt = f"""你是天津职业技术师范大学的一位热心学长，名叫"天职小咕"。你熟悉学校的方方面面，平时喜欢帮助学弟学妹解答各种问题。

【你的性格特点】
1. 亲切自然：像朋友聊天一样，不说教
2. 善于联想：能根据已有信息推断出实际答案
3. 实用主义：不仅告诉"是什么"，还告诉"怎么办"
4. 幽默风趣：偶尔来点轻松的表达，但保持尊重

【回答原则】
- 知识库有相关内容时，基于资料回答，严禁直接复制粘贴原文
- 知识库没有相关内容时，根据你的知识合理回答
- 结合学生的实际场景给出建议
- 使用口语化表达，可以适当使用"咱学校"、"学长建议"、"注意哈"等亲切用语
- 如果确实完全不知道，诚实地说"这个学长也不太确定，建议问问辅导员"

【检索到的知识库资料】
{context_text}

【对话历史】
{history_text}

【当前问题】
学生问：{user_question}

请用学长的口吻给出亲切、实用、有温度的回答："""

    return prompt


def generate_reply(user_message: str, user_id: str = None) -> str:
    """生成 AI 回复（RAG + 对话历史）"""

    print(f"[CHAT] 开始生成回复，用户消息: {user_message[:50]}...", flush=True)

    # 检查 API 密钥
    provider, api_key, error = check_api_key()
    if error:
        return f"抱歉，AI 服务未配置好。{error}"

    # RAG 检索
    retrieved_docs = vector_store.search(user_message, k=3)

    if not retrieved_docs:
        print(f"[WARN] 未检索到相关内容", flush=True)

    # 获取对话历史
    history = []
    history_text = "（暂无历史对话）"
    if user_id:
        history = chat_history.get_history(user_id)
        history_text = chat_history.format_history_for_prompt(user_id)

    # 构建 Prompt
    system_prompt = build_system_prompt(retrieved_docs, user_message, history_text)

    # 调用 AI
    if provider == 'kimi':
        result = call_kimi_api(api_key, system_prompt, user_message, history)
    elif provider == 'gemini':
        result = call_gemini_api(api_key, system_prompt, user_message, history)
    elif provider == 'openai':
        result = call_openai_api(api_key, system_prompt, user_message, 'gpt-3.5-turbo', history)
    elif provider == 'deepseek':
        result = call_openai_api(api_key, system_prompt, user_message, 'deepseek-chat', history)
    else:
        return "抱歉，未找到可用的 AI 服务提供商。"

    if result['success']:
        reply = result['reply']

        # 保存对话历史
        if user_id:
            chat_history.add_message(user_id, "user", user_message)
            chat_history.add_message(user_id, "assistant", reply)

        print(f"[CHAT] 回复生成成功", flush=True)
        return reply
    else:
        print(f"[ERROR] API 调用失败: {result.get('error')}", flush=True)
        return "抱歉，我脑子短路了一下...请稍后再试，或者换个问法？"


# ==================== API 路由 ====================

@app.route('/api/chat', methods=['POST'])
def chat():
    """聊天 API"""
    try:
        print(f"[API] 收到聊天请求", flush=True)

        # 检查是否已就绪
        if not is_ready:
            print(f"[WARN] 服务未就绪，返回 503", flush=True)
            return jsonify({
                'success': False,
                'error': startup_error or '服务正在初始化中，请稍后再试'
            }), 503

        data = request.get_json()

        if not data or 'message' not in data:
            return jsonify({'error': '缺少必要参数: message'}), 400

        user_message = data['message'].strip()

        if not user_message:
            return jsonify({'error': '消息内容不能为空'}), 400

        # 获取用户 ID
        user_id = chat_history.get_user_id(request)
        print(f"[API] 用户ID: {user_id}", flush=True)

        # 生成回复
        reply = generate_reply(user_message, user_id)

        return jsonify({
            'success': True,
            'reply': reply,
            'ai_name': Config.AI_NAME
        })

    except Exception as e:
        print(f"[ERROR] 聊天接口错误: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': '服务器开小差了，请稍后再试~'
        }), 500


@app.route('/api/chat/clear', methods=['POST'])
def clear_chat():
    """清空对话历史"""
    try:
        print(f"[API] 收到清空历史请求", flush=True)
        user_id = chat_history.get_user_id(request)
        chat_history.clear_history(user_id)
        return jsonify({
            'success': True,
            'message': '对话历史已清空'
        })
    except Exception as e:
        print(f"[ERROR] 清空对话历史失败: {e}", flush=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    global is_ready, startup_error

    vector_ready = vector_store.vectorstore is not None
    provider, api_key = Config.get_active_api_key()

    status_data = {
        'status': 'ready' if (is_ready and provider) else 'initializing',
        'vector_store_ready': vector_ready,
        'ai_provider': provider or 'not_configured',
        'ai_name': Config.AI_NAME if hasattr(Config, 'AI_NAME') else '天职小咕',
        'knowledge_base_path': KNOWLEDGE_BASE_DIR,
        'base_dir': BASE_DIR,
        'frontend_dir': FRONTEND_DIR
    }

    if is_ready and provider:
        return jsonify(status_data)
    else:
        status_data['message'] = startup_error or 'AI 正在研读最新手册，请稍候...'
        return jsonify(status_data), 503


@app.route('/api/config', methods=['GET'])
def get_config():
    """获取前端配置"""
    return jsonify({
        'ai_name': Config.AI_NAME if hasattr(Config, 'AI_NAME') else '天职小咕',
        'ai_avatar': Config.AI_AVATAR_PATH if hasattr(Config, 'AI_AVATAR_PATH') else '/static/avatar.png'
    })


# ==================== 万能 Catch-all 路由（修复 404 问题）====================

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    """
    万能路由：
    - 如果请求的是文件且存在，发送文件
    - 否则一律返回 index.html（支持前端路由）
    """
    print(f"[ROUTE] 收到请求路径: '{path}'", flush=True)
    print(f"[ROUTE] FRONTEND_DIR: {FRONTEND_DIR}", flush=True)

    # 如果路径为空，直接返回 index.html
    if not path:
        index_path = os.path.join(FRONTEND_DIR, 'index.html')
        print(f"[ROUTE] 返回首页: {index_path}", flush=True)
        if os.path.exists(index_path):
            return send_file(index_path)
        else:
            print(f"[ERROR] index.html 不存在: {index_path}", flush=True)
            return jsonify({'error': 'Frontend not found'}), 404

    # 构建完整文件路径
    file_path = os.path.join(FRONTEND_DIR, path)
    file_path = os.path.abspath(file_path)
    print(f"[ROUTE] 检查文件: {file_path}", flush=True)

    # 安全检查：确保路径在 FRONTEND_DIR 内
    if not file_path.startswith(FRONTEND_DIR):
        print(f"[WARN] 路径安全检查失败，返回 index.html", flush=True)
        return send_file(os.path.join(FRONTEND_DIR, 'index.html'))

    # 如果文件存在且是文件，发送文件
    if os.path.exists(file_path) and os.path.isfile(file_path):
        print(f"[ROUTE] 发送文件: {file_path}", flush=True)
        return send_file(file_path)

    # 否则返回 index.html（支持前端路由）
    index_path = os.path.join(FRONTEND_DIR, 'index.html')
    print(f"[ROUTE] 文件不存在，返回 index.html: {index_path}", flush=True)
    if os.path.exists(index_path):
        return send_file(index_path)
    else:
        print(f"[ERROR] index.html 不存在: {index_path}", flush=True)
        return jsonify({'error': 'Frontend not found'}), 404


# ==================== 启动前检查 ====================

def check_prerequisites():
    """
    启动前检查
    返回: (success: bool, error_message: str)
    """
    print("=" * 50, flush=True)
    print("天津职业技术师范大学校园AI助手", flush=True)
    print("天职小咕 - 你的热心学长", flush=True)
    print("=" * 50, flush=True)
    print(f"\n[INFO] FRONTEND_DIR: {FRONTEND_DIR}", flush=True)
    print(f"[INFO] KNOWLEDGE_BASE_DIR: {KNOWLEDGE_BASE_DIR}", flush=True)
    print(f"[INFO] BASE_DIR: {BASE_DIR}", flush=True)
    print(f"[INFO] 当前工作目录: {os.getcwd()}", flush=True)

    # 检查前端目录
    print("\n[启动检查] 检查前端目录...", flush=True)
    if os.path.exists(FRONTEND_DIR):
        print(f"[OK] 前端目录存在: {FRONTEND_DIR}", flush=True)
        try:
            files = os.listdir(FRONTEND_DIR)
            print(f"[INFO] 前端目录内容: {files[:10]}...", flush=True)  # 只显示前10个
        except Exception as e:
            print(f"[WARN] 无法列出前端目录内容: {e}", flush=True)
    else:
        print(f"[WARN] 前端目录不存在: {FRONTEND_DIR}", flush=True)

    # 检查 API 配置
    print("\n[启动检查] 检查 API 密钥配置...", flush=True)
    provider, api_key, api_error = check_api_key()

    if api_error:
        return False, api_error

    # 初始化 RAG 向量库
    print("\n[启动检查] 正在加载知识库...", flush=True)
    try:
        success = vector_store.load_and_index_documents()
        if success:
            print("[OK] 知识库加载完成！", flush=True)
        else:
            print("[WARN] 知识库加载遇到问题，但允许继续启动", flush=True)
    except Exception as e:
        print(f"[ERROR] 知识库加载异常: {e}", flush=True)
        import traceback
        traceback.print_exc()
        print("[WARN] 使用空知识库继续启动", flush=True)

    return True, None


# ==================== Vercel 部署入口 ====================

print("[INIT] 正在执行启动检查...", flush=True)

# 启动前检查 - Vercel 需要在导入时执行初始化
try:
    success, error_message = check_prerequisites()

    if not success:
        startup_error = error_message
        print("\n" + "!" * 50, flush=True)
        print("启动失败 - 未能通过启动检查", flush=True)
        print("!" * 50, flush=True)
        print(f"\n错误原因: {error_message}", flush=True)
        print("\n请检查：", flush=True)
        print("  1. Vercel 环境变量中是否配置了 API 密钥（KIMI_API_KEY 等）", flush=True)
        print("  2. Vercel 项目设置中的 Environment Variables", flush=True)
    else:
        # 标记为就绪状态
        is_ready = True
        startup_error = None
        print("\n" + "=" * 50, flush=True)
        print("启动检查通过 - 所有系统就绪！", flush=True)
        print("=" * 50 + "\n", flush=True)
except Exception as e:
    startup_error = f"启动检查异常: {str(e)}"
    print(f"[ERROR] 启动检查异常: {e}", flush=True)
    import traceback
    traceback.print_exc()

# 标准入口 - 修复语法错误，只有一个 if __name__ == '__main__'
if __name__ == '__main__':
    print("[MAIN] 本地开发模式启动...", flush=True)
    app.run(host='0.0.0.0', port=5000)
