import os
import tempfile

# LLM Provider: "ollama" (本地) | "openai" (国内云端，自动脱敏) | "claude" (海外云端，自动脱敏)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")

# Ollama Configuration (本地模型)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")

# OpenAI-Compatible Configuration (国内云端模型)
# DeepSeek: https://platform.deepseek.com
# 通义千问: https://dashscope.aliyuncs.com/compatible-mode
# 智谱GLM: https://open.bigmodel.cn
# Kimi: https://api.moonshot.cn
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "deepseek-chat")
FAST_MODEL = os.getenv("FAST_MODEL", "")  # 快速模型用于训练对话，留空则用 OPENAI_MODEL
EVAL_MODEL = os.getenv("EVAL_MODEL", "")  # 评估专用模型，留空则用 OPENAI_MODEL

# Claude Configuration (海外云端模型)
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

# Temperature Settings
CUSTOMER_TEMP = 0.7
SALES_TEMP = 0.7
EXTRACTION_TEMP = 0.2
EVALUATION_TEMP = 0.3
MAX_TOKENS_RESPONSE = 1024
MAX_TOKENS_EVALUATION = 4096

# Desensitization (脱敏)
DESENSITIZE_ENABLED = True  # 发送云端前自动脱敏
DESENSITIZE_PREVIEW = True  # 脱敏后预览确认

# Style Configuration
MAX_STYLE_SLOTS = 4
MAX_CHUNK_TOKENS = 8000

# Sales Users (销售名单，用于多用户登录)
SALES_USERS = os.getenv("SALES_USERS", "免免,CC,茉莉,丸子").split(",")

# Session Configuration
MAX_TURNS_PER_SESSION = 30
PHASE_DETECTION_INTERVAL = 3

# Evaluation Weights
EVAL_WEIGHTS = {
    "沟通表达": 1.0,
    "需求发掘": 1.5,
    "价值主张": 1.2,
    "异议处理": 1.5,
    "流程完整": 1.0,
    "关系建立": 1.0,
    "风格运用": 0.8,
    "收尾技巧": 1.0,
}

# Evaluation Dimensions (评估维度列表)
EVAL_DIMENSIONS = ["沟通表达", "需求发掘", "价值主张", "异议处理", "流程完整", "关系建立", "风格运用", "收尾技巧"]

# Dynamic Difficulty (动态难度)
DIFFICULTY_THRESHOLD_EASY = 5.0
DIFFICULTY_THRESHOLD_HARD = 7.0
DIFFICULTY_LOOKBACK = 5

# Phrase Extraction (话术自动提取)
PHRASE_EXTRACTION_ENABLED = True
PHRASE_EXTRACTION_THRESHOLD = 6.0

# File Upload Configuration
MAX_FILE_SIZE_MB = 25
OCR_MODE = os.getenv("OCR_MODE", "ollama_vision")  # "ollama_vision" or "tesseract"
OLLAMA_VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "minicpm-v")
SUPPORTED_FILE_EXTENSIONS = {
    "docx", "doc", "pdf", "xlsx", "xls",
    "pptx", "ppt", "txt", "csv", "json",
    "jpg", "jpeg", "png",
}

# Data Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _resolve_dir(env_name: str, default: str) -> str:
    configured = os.getenv(env_name, "").strip()
    path = configured or default
    return os.path.abspath(os.path.expandvars(os.path.expanduser(path)))


DATA_DIR = _resolve_dir("AI_SALES_DATA_DIR", os.path.join(BASE_DIR, "data"))
TEMP_DIR = _resolve_dir("AI_SALES_TEMP_DIR", os.path.join(DATA_DIR, "temp"))
STYLES_DIR = os.path.join(DATA_DIR, "styles")
SESSIONS_DIR = os.path.join(DATA_DIR, "sessions")
EVALUATIONS_DIR = os.path.join(DATA_DIR, "evaluations")
REPORTS_DIR = os.path.join(DATA_DIR, "reports")
KNOWLEDGE_DIR = os.path.join(DATA_DIR, "knowledge")
FILE_DOWNLOAD_DIR = os.path.join(DATA_DIR, "downloads")

# Scenario History (场景历史，训练去重)
SCENARIO_HISTORY_DIR = os.path.join(DATA_DIR, "scenario_history")

# Weekly Review (每周复盘)
WEEKLY_REVIEW_DIR = os.path.join(DATA_DIR, "weekly_reviews")

# Keep uploaded and generated temporary files with the configured application data.
os.environ["GRADIO_TEMP_DIR"] = TEMP_DIR
tempfile.tempdir = TEMP_DIR

# Ensure data directories exist
for d in [DATA_DIR, TEMP_DIR, STYLES_DIR, SESSIONS_DIR, EVALUATIONS_DIR, REPORTS_DIR, KNOWLEDGE_DIR, FILE_DOWNLOAD_DIR, SCENARIO_HISTORY_DIR, WEEKLY_REVIEW_DIR]:
    os.makedirs(d, exist_ok=True)
