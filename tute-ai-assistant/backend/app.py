"""
天津职业技术师范大学校园AI助手 - 后端服务
基于 Flask + RAG (检索增强生成) 的 API 服务
"""

import os
import re

# 设置项目基础目录（确保所有路径都是绝对路径）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from config import Config

# RAG 相关导入
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

app = Flask(__name__, static_folder=os.path.join(BASE_DIR, '../frontend'))
# 配置 CORS - 允许所有来源访问（支持外网前端调用）
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# ==================== RAG 向量检索系统 ====================

class VectorStore:
    """基于 FAISS 的向量检索系统"""

    def __init__(self):
        self.vectorstore = None
        self.embeddings = None
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,      # 每个块约 500 字
            chunk_overlap=50,    # 重叠 50 字，避免断句
            separators=["\n\n", "\n", "。", "；", " ", ""]
        )

    def init_embeddings(self):
        """初始化 Embedding 模型（使用轻量级中文模型）"""
        if self.embeddings is None:
            print("正在加载 Embedding 模型...")
            # 使用轻量级中文句子向量模型
            self.embeddings = HuggingFaceEmbeddings(
                model_name="shibing624/text2vec-base-chinese",
                model_kwargs={'device': 'cpu'},
                encode_kwargs={'normalize_embeddings': True}
            )
            print("Embedding 模型加载完成！")

    def load_and_index_documents(self):
        """加载文档并建立向量索引"""
        self.init_embeddings()

        all_chunks = []
        sources = []
        loaded_files = []

        # 动态加载 knowledge_base 目录中的所有 .txt 文件
        kb_dir = Config.KNOWLEDGE_BASE_DIR
        print(f"正在扫描知识库目录: {kb_dir}")

        if os.path.exists(kb_dir) and os.path.isdir(kb_dir):
            txt_files = [f for f in os.listdir(kb_dir) if f.endswith('.txt')]
            print(f"找到 {len(txt_files)} 个文件: {txt_files}")  # 新增日志：显示加载的文件数量

            for filename in txt_files:
                filepath = os.path.join(kb_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if not content.strip():
                            print(f"  [跳过] 空文件: {filename}")
                            continue
                        chunks = self.text_splitter.split_text(content)
                        all_chunks.extend(chunks)
                        # 从文件名生成来源标签
                        source_name = filename.replace('.txt', '')
                        sources.extend([source_name] * len(chunks))
                        loaded_files.append(filename)
                        print(f"  [OK] {filename}: {len(chunks)} 个片段")
                except Exception as e:
                    print(f"  [错误] 读取失败 {filename}: {e}")
        else:
            print(f"[警告] 知识库目录不存在: {kb_dir}")

        if all_chunks:
            # 构建元数据
            metadatas = [{"source": src, "chunk_index": i} for i, src in enumerate(sources)]

            # 创建 FAISS 向量库
            print(f"正在构建向量索引，共 {len(all_chunks)} 个片段...")
            self.vectorstore = FAISS.from_texts(
                texts=all_chunks,
                embedding=self.embeddings,
                metadatas=metadatas
            )
            print("向量索引构建完成！")
            return True
        else:
            print("警告：没有加载到任何文档内容")
            return False

    def search(self, query: str, k: int = 3):
        """
        检索与问题最相关的片段
        返回: List[Document]
        """
        if self.vectorstore is None:
            return []

        results = self.vectorstore.similarity_search(query, k=k)
        return results


# 全局向量库实例
vector_store = VectorStore()

# 启动就绪标志 - 用于健康检查
is_ready = False


# ==================== 对话历史管理 ====================

class ChatHistory:
    """简单的对话历史管理器（内存存储）"""

    def __init__(self, max_rounds: int = 5):
        self.max_rounds = max_rounds
        self.history = {}  # user_id -> list of messages

    def get_user_id(self, request) -> str:
        """获取用户标识（使用 IP + User-Agent 的简单哈希）"""
        ip = request.remote_addr or 'unknown'
        ua = request.headers.get('User-Agent', '')
        import hashlib
        return hashlib.md5(f"{ip}:{ua}".encode()).hexdigest()[:16]

    def add_message(self, user_id: str, role: str, content: str):
        """添加一条消息到历史"""
        if user_id not in self.history:
            self.history[user_id] = []

        self.history[user_id].append({
            "role": role,
            "content": content
        })

        # 只保留最近 max_rounds 轮（每轮包含 user + assistant 两条）
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
        """将历史格式化为字符串，用于插入 prompt"""
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


# ==================== AI API 调用 ====================

def call_kimi_api(api_key: str, system_prompt: str, user_message: str, history: list = None):
    """调用 Kimi (Moonshot AI) API，支持对话历史"""
    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=api_key,
            base_url="https://api.moonshot.cn/v1"
        )

        # 构建消息列表
        messages = [{"role": "system", "content": system_prompt}]

        # 添加历史对话
        if history:
            for msg in history:
                messages.append({
                    "role": "user" if msg["role"] == "user" else "assistant",
                    "content": msg["content"]
                })

        # 添加当前消息
        messages.append({"role": "user", "content": user_message})

        response = client.chat.completions.create(
            model="moonshot-v1-8k",
            messages=messages,
            temperature=0.7,
            max_tokens=2000
        )

        if response.choices and len(response.choices) > 0:
            reply = response.choices[0].message.content
            return {'success': True, 'reply': reply}
        else:
            return {'success': False, 'error': 'API 返回空响应'}

    except Exception as e:
        return {'success': False, 'error': f'Kimi API 调用失败: {str(e)}'}


def call_gemini_api(api_key: str, system_prompt: str, user_message: str, history: list = None):
    """调用 Google Gemini API"""
    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro')

        # Gemini 不支持标准的多轮对话格式，需要拼接成单条 prompt
        full_prompt = system_prompt

        if history:
            full_prompt += "\n\n【历史对话】\n"
            for msg in history:
                role_name = "学生" if msg["role"] == "user" else "学长"
                full_prompt += f"{role_name}：{msg['content']}\n"

        full_prompt += f"\n学生现在问：{user_message}"

        response = model.generate_content(full_prompt)

        if response and response.text:
            return {'success': True, 'reply': response.text}
        else:
            return {'success': False, 'error': 'API 返回空响应'}

    except Exception as e:
        return {'success': False, 'error': f'Gemini API 调用失败: {str(e)}'}


def call_openai_api(api_key: str, system_prompt: str, user_message: str,
                    model: str = 'gpt-3.5-turbo', history: list = None):
    """调用 OpenAI API (或兼容接口如 DeepSeek)，支持对话历史"""
    try:
        from openai import OpenAI

        # 判断是否使用 DeepSeek
        if 'deepseek' in model.lower():
            client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")
            model = "deepseek-chat"
        else:
            client = OpenAI(api_key=api_key)

        # 构建消息列表
        messages = [{"role": "system", "content": system_prompt}]

        # 添加历史对话
        if history:
            for msg in history:
                messages.append({
                    "role": "user" if msg["role"] == "user" else "assistant",
                    "content": msg["content"]
                })

        # 添加当前消息
        messages.append({"role": "user", "content": user_message})

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7,
            max_tokens=2000
        )

        if response.choices and len(response.choices) > 0:
            reply = response.choices[0].message.content
            return {'success': True, 'reply': reply}
        else:
            return {'success': False, 'error': 'API 返回空响应'}

    except Exception as e:
        return {'success': False, 'error': f'OpenAI API 调用失败: {str(e)}'}


# ==================== 核心回复生成逻辑 ====================

def build_system_prompt(retrieved_docs: list, user_question: str, history_text: str) -> str:
    """
    构建学长风格的 System Prompt

    角色设定：精通校规、亲切自然的学长
    """

    # 将检索到的片段组织成引用材料
    context_parts = []
    for i, doc in enumerate(retrieved_docs, 1):
        source = doc.metadata.get("source", "学生手册")
        context_parts.append(f"【参考资料{i}】（来自{source}）\n{doc.page_content}")

    context_text = "\n\n".join(context_parts) if context_parts else "（本次问题未匹配到具体校规条款）"

    prompt = f"""你是天津职业技术师范大学的一位热心学长，名叫"天职小咕"。你熟悉学校的一草一木，对校规校纪了如指掌，平时喜欢帮助学弟学妹解答各种问题。

【你的性格特点】
1. 亲切自然：像朋友聊天一样，不说教、不照搬条文
2. 善于联想：能根据校规推断出实际生活中的答案
3. 实用主义：不仅告诉"是什么"，还告诉"怎么办"
4. 幽默风趣：偶尔来点轻松的表达，但保持尊重

【回答原则】
- 严禁直接复制粘贴原文，要用自己的话归纳总结
- 如果资料里没直接说，可以根据已有信息合理推断
- 结合学生的实际场景给出建议（比如"熬夜打游戏"要提醒断电时间）
- 使用口语化表达，可以适当使用"咱学校"、"学长建议"、"注意哈"等亲切用语
- 如果确实完全不知道，诚实地说"这个学长也不太确定，建议问问辅导员"

【检索到的校规资料】
{context_text}

【对话历史】
{history_text}

【当前问题】
学生问：{user_question}

请以上述资料为基础，用学长的口吻给出亲切、实用、有温度的回答："""

    return prompt


def generate_reply(user_message: str, user_id: str = None) -> str:
    """
    生成 AI 回复（RAG + 对话历史）

    流程：
    1. 用 RAG 检索最相关的 3 个片段
    2. 获取对话历史
    3. 构建学长风格 prompt
    4. 调用 AI API
    """

    # 1. RAG 检索（只取 top 3）
    retrieved_docs = vector_store.search(user_message, k=3)

    if not retrieved_docs:
        print(f"警告：未检索到相关内容，问题：{user_message[:50]}...")

    # 2. 获取对话历史
    history = []
    history_text = "（暂无历史对话）"
    if user_id:
        history = chat_history.get_history(user_id)
        history_text = chat_history.format_history_for_prompt(user_id)

    # 3. 构建 Prompt
    system_prompt = build_system_prompt(retrieved_docs, user_message, history_text)

    # 4. 调用 AI
    provider, api_key = Config.get_active_api_key()

    if not api_key:
        return "抱歉，AI 服务未配置好。请联系管理员配置 API 密钥。"

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

        return reply
    else:
        print(f"API 调用失败: {result.get('error')}")
        return "抱歉，我脑子短路了一下...请稍后再试，或者换个问法？"


# ==================== API 路由 ====================

@app.route('/')
def index():
    """主页"""
    return send_from_directory('../frontend', 'index.html')


@app.route('/<path:path>')
def static_files(path):
    """静态文件服务"""
    return send_from_directory('../frontend', path)


@app.route('/api/chat', methods=['POST'])
def chat():
    """聊天 API"""
    try:
        data = request.get_json()

        if not data or 'message' not in data:
            return jsonify({'error': '缺少必要参数: message'}), 400

        user_message = data['message'].strip()

        if not user_message:
            return jsonify({'error': '消息内容不能为空'}), 400

        # 获取用户 ID（用于对话历史）
        user_id = chat_history.get_user_id(request)

        # 生成回复
        reply = generate_reply(user_message, user_id)

        return jsonify({
            'success': True,
            'reply': reply,
            'ai_name': Config.AI_NAME
        })

    except Exception as e:
        print(f"聊天接口错误: {e}")
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
        user_id = chat_history.get_user_id(request)
        chat_history.clear_history(user_id)
        return jsonify({
            'success': True,
            'message': '对话历史已清空'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查接口 - 用于前端判断服务是否就绪"""
    vector_ready = vector_store.vectorstore is not None
    provider, _ = Config.get_active_api_key()

    # 只有当向量库和AI配置都就绪时才返回 ready 状态
    if is_ready and vector_ready and provider:
        return jsonify({
            'status': 'ready',
            'vector_store_ready': True,
            'ai_provider': provider,
            'ai_name': Config.AI_NAME
        })
    else:
        return jsonify({
            'status': 'initializing',
            'vector_store_ready': vector_ready,
            'ai_provider': provider or 'not_configured',
            'ai_name': Config.AI_NAME,
            'message': 'AI 正在研读最新手册，请稍候...'
        }), 503


@app.route('/api/config', methods=['GET'])
def get_config():
    """获取前端配置"""
    return jsonify({
        'ai_name': Config.AI_NAME,
        'ai_avatar': Config.AI_AVATAR_PATH
    })


# ==================== 启动前检查 ====================

def check_prerequisites():
    """
    启动前检查：确保知识库文件加载完毕且向量数据库准备就绪
    返回: (success: bool, error_message: str)
    """
    print("=" * 50)
    print("天津职业技术师范大学校园AI助手")
    print("天职小咕 - 你的热心学长")
    print("=" * 50)

    # 1. 检查知识库目录是否存在且有文件
    kb_dir = Config.KNOWLEDGE_BASE_DIR
    print(f"\n[启动检查] 检查知识库目录...")
    print(f"   目录: {kb_dir}")

    if not os.path.exists(kb_dir):
        return False, f"知识库目录不存在: {kb_dir}"

    # 2. 初始化 RAG 向量库
    print("\n[启动检查] 正在加载知识库（RAG 模式）...")
    print("   - 文档切分大小：500 字/块")
    print("   - 检索数量：Top 3 最相关片段")

    success = vector_store.load_and_index_documents()

    if not success:
        return False, "知识库加载失败，未找到有效的文档文件"

    print("[OK] 知识库加载完成！")

    # 3. 检查 API 配置
    provider, _ = Config.get_active_api_key()
    if not provider:
        return False, "未配置 API 密钥，请在 .env 文件中配置至少一个 AI 提供商的 API 密钥"

    print(f"[OK] AI 提供商: {provider}")

    return True, None


# ==================== 主程序入口 ====================

if __name__ == '__main__':
    # 启动前检查 - 只有通过后才启动 Web 服务器
    success, error_message = check_prerequisites()

    if not success:
        print("\n" + "!" * 50)
        print("启动失败 - 未能通过启动检查")
        print("!" * 50)
        print(f"\n错误原因: {error_message}")
        print("\n请检查：")
        print("  1. knowledge_base/ 目录是否存在且有 .txt 文件")
        print("  2. .env 文件中是否配置了 API 密钥")
        print("\n如需帮助，请参考 README.md")
        exit(1)

    # 标记为就绪状态
    is_ready = True
    print("\n" + "=" * 50)
    print("启动检查通过 - 所有系统就绪！")
    print(f"启动服务: http://localhost:{Config.FLASK_PORT}")
    print("按 Ctrl+C 停止服务")
    print("=" * 50 + "\n")

    # 统一使用 0.0.0.0:5000，确保外网可访问
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True
    )
