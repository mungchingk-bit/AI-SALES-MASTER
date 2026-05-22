import os

# LLM Provider: "ollama" (本地，数据不出本机) | "claude" (云端，需脱敏)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")

# Ollama Configuration (本地模型)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")

# Claude Configuration (云端模型)
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

# Temperature Settings
CUSTOMER_TEMP = 0.9
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

# Data Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
STYLES_DIR = os.path.join(DATA_DIR, "styles")
SESSIONS_DIR = os.path.join(DATA_DIR, "sessions")
EVALUATIONS_DIR = os.path.join(DATA_DIR, "evaluations")

# Ensure data directories exist
for d in [STYLES_DIR, SESSIONS_DIR, EVALUATIONS_DIR]:
    os.makedirs(d, exist_ok=True)
