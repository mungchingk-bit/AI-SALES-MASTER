"""自动脱敏模块 — 发送云端前移除敏感信息，保留说话方式和逻辑。"""
import re

# 脱敏规则：匹配模式 → 替换标签
RULES = [
    # 手机号
    (re.compile(r"1[3-9]\d{9}"), "[手机号]"),
    # 座机
    (re.compile(r"0\d{2,3}-?\d{7,8}"), "[座机号]"),
    # 身份证
    (re.compile(r"[1-9]\d{5}(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx]"), "[身份证]"),
    # 邮箱
    (re.compile(r"[\w.-]+@[\w.-]+\.\w+"), "[邮箱]"),
    # 微信号（纯数字6-20位前面带"微信"或"vx"等）
    (re.compile(r"(?:微信|vx|VX|WeChat)[：:]\s*\w{6,20}"), "[微信号]"),
    # 银行卡号
    (re.compile(r"\b\d{16,19}\b"), "[银行卡号]"),
    # 具体金额（带￥/$或"元""万"的数字）
    (re.compile(r"[￥¥$]\s*[\d,.]+"), "[金额]"),
    (re.compile(r"\d+(?:\.\d+)?\s*万?元"), "[金额]"),
    # 地址（省市区+路号）
    (re.compile(r"[一-鿿]{2,5}(?:省|市|区|县|镇)[一-鿿]{2,10}(?:路|街|道|巷|弄|号|栋|楼|室|层)"), "[地址]"),
]

# 中文姓名常见姓氏 + 2-3字名的模式（保守匹配，只匹配明确的称谓上下文）
NAME_PREFIXES = re.compile(
    r"(?:我叫|我是|这位是|先生|女士|小姐|总|经理|总监|老板|老师|主管|负责人)[：:：]?\s*"
)
# 简单的中文姓名（2-3字，前面有称谓上下文）
NAME_PATTERN = re.compile(r"[一-鿿]{2,4}")


def desensitize_text(text: str) -> str:
    """对文本进行脱敏处理，移除敏感信息但保留对话逻辑和说话方式。"""
    if not text:
        return text

    result = text

    # 应用规则
    for pattern, replacement in RULES:
        result = pattern.sub(replacement, result)

    # 处理带称谓上下文的姓名
    result = _desensitize_names(result)

    return result


def _desensitize_names(text: str) -> str:
    """脱敏带称谓上下文的姓名。"""
    # 匹配"X总""X经理""X先生""X女士"等
    title_pattern = re.compile(
        r"([一-鿿]{1,2})(总|经理|总监|主管|老板|先生|女士|小姐|老师)"
    )
    result = title_pattern.sub(r"[姓氏]\2", text)

    return result


def desensitize_messages(messages: list[dict]) -> list[dict]:
    """对消息列表进行脱敏。"""
    return [
        {"role": msg["role"], "content": desensitize_text(msg["content"])}
        for msg in messages
    ]


def preview_desensitization(original: str) -> str:
    """预览脱敏效果，返回对比文本供用户确认。"""
    desensitized = desensitize_text(original)
    if original == desensitized:
        return "未检测到敏感信息，无需脱敏。"

    # 找出被替换的内容
    changes = []
    for pattern, tag in RULES:
        matches = pattern.findall(original)
        if matches:
            for m in matches:
                m_str = m if isinstance(m, str) else m[0]
                if m_str not in str(changes):
                    changes.append(f"  {m_str} → {tag}")

    # 姓名检测
    title_matches = re.findall(r"([一-鿿]{1,2})(总|经理|总监|主管|老板|先生|女士|小姐|老师)", original)
    for name, title in title_matches:
        changes.append(f"  {name}{title} → [姓氏]{title}")

    header = f"检测到 {len(changes)} 处敏感信息将被替换：\n"
    return header + "\n".join(changes)
