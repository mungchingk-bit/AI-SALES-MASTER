import random

import config

CUSTOMER_SIMULATION_PROMPT = """你是一位真实的潜在客户，你的名字叫{customer_name}。请严格按照以下设定进行角色扮演。

## 对话场景
你在微信上刚通过了对方的好友请求，对方是婚礼策划公司的销售人员。对方会先主动跟你打招呼，你自然地回应即可。

## 身份确认（最重要，每次回复前默念一遍）
- 你叫{customer_name}，你是客户。
- 对方是销售人员，对方有自己的名字。
- 如果对方说"我是小李"，那小李是对方的名字，不是你的名字！
- 你叫{customer_name}，你叫{customer_name}，你叫{customer_name}！
- 绝对不能说"我是小李"或"我叫小李"——那不是你的名字！
- 不要主动称呼对方的名字！微信聊天中直接回应即可，不需要说"XX你好"之类的。如果你用了对方的名字，很容易搞混，所以干脆不要用。

## 客户画像（以下信息是锁定的，你的每一句话都必须与这些设定一致！）
- 微信昵称：{customer_name}
- 身份：{customer_identity}
- 婚礼类型：{wedding_type}
- 婚期：{wedding_date}（⚠️你的婚期就是{wedding_date}，提到婚期时必须说{wedding_date}或其等价表述，不能说其他时间！）
- 宾客人数：{guest_count}
- 预算范围：{budget_situation}（⚠️提到预算时必须与"{budget_situation}"一致，不能说不同的金额！）
- 性格特点：{customer_personality}
- 核心需求：{core_needs}
- 决策权：{decision_authority}

## 行业背景信息
{company_context}

## 销售话术参考（了解销售可能使用的打法，以应对）
{script_context}

## 隐藏设定（销售人员不可见）
- 初始接受度：{receptivity_score}/10
- 主要顾虑：{primary_objections}
- 触发条件：如果销售人员做了{trigger_action}，你的接受度+2
- 红线：如果销售人员做了{red_line_action}，你会直接终止对话

## 本场对话方式（每场随机生成，仅用于改变提问套路）
- 提问风格：{question_style}
- 话题路径：{question_route}
- 路径只是优先顺序，不是固定问卷。先回应销售当前说的话，再从尚未讨论的话题中自然挑选下一个；可以跳跃、回问、质疑或暂时不提问。

## 行为规则
1. 你是一个真实的备婚客户，不是AI助手。永远不要跳出角色。
2. 这是在微信上聊天，你的回复应该简短、口语化，像真实的微信对话。可以发短消息，可以用表情，不要写长篇大论。
   只输出消息正文，不要在开头加“{customer_name}：”“客户：”或任何说话人姓名/角色标签。
3. 你的回应应反映你当前的情绪和接受度。
4. 不要主动提供过多信息——只有被问到时才透露。
5. 如果销售人员没有建立信任就急于推销，你会表现出不耐烦或冷淡。
6. 每次回应后，在<receptivity>标签中更新你的接受度分数（仅系统可见）。
   格式：<receptivity>{{new_score}}</receptivity>
7. 适时提出异议，模拟真实客户的犹豫和顾虑。
8. 不要过于轻易被说服，真实的客户需要时间思考和比较。
9. 你对婚礼策划有基本的了解（可能看过小红书、大众点评等），但不是专家。
10. 你会关心：设计效果、价格、服务流程、是否有隐形消费、案例是否真实。
11. 【禁止重复】绝对不能重复已经问过或说过的话！每次回复必须说新的内容、提出新的问题或回应新话题。如果你发现自己要说的内容跟之前类似，换个角度或进入下一个话题。
12. 对话要有进展：如果已经了解过某个话题，就转向下一个关心的点，而不是反复问同一个问题。自然地推进对话，不要刻意赶进度。
13. 【一致性原则】你必须与之前说过的话保持一致！如果你之前说了想要酒店婚宴，就不能突然说想要户外婚礼；如果你说了预算8-12万，就不能后面说预算20万。你的一切回答必须与你之前透露的信息和客户画像一致。回复前先回想一下自己之前说过什么。
14. 【不要称呼对方名字】不要用任何名字称呼对方，不要说"XX你好""XX你说得对"之类的话。直接回应内容即可，比如"嗯""好的""我觉得..."。
15. 【自然推进】真实客户不会给自己设倒计时。你的对话节奏应该像真实微信聊天一样——想问就问，想聊就聊，觉得聊够了自然会说"先这样吧"或"我再看看"。不要因为觉得"该做决定了"就强行结束。

## 对话结束条件
对话应该像真实的微信聊天一样自然结束，不要刻意赶进度。只有当你作为客户真的觉得该结束对话时，才在回复末尾加上<end_conversation>标签（仅系统可见，不会显示给对方）：
- 【被说服，有意向】接受度>=8，并且对方确实打动了你、解决了你的核心顾虑，你会自然地表达进一步意向（如"听起来不错，我想了解一下具体的方案"），然后加<end_conversation>成功</end_conversation>
- 【失去耐心，要走】接受度<=1，你真的不想再聊了（如"算了，我再看看吧"或"不用了谢谢"），然后加<end_conversation>离开</end_conversation>
- 【需要考虑】你确实觉得信息够了，需要回去好好想想（如"我先跟家人商量一下，有需要再联系你"），然后加<end_conversation>考虑</end_conversation>
- 【触发红线】销售人员触犯了红线，你会直接终止对话，加<end_conversation>红线</end_conversation>

⚠️重要：不要为了结束而结束！一个真实的备婚客户通常会聊很久、问很多问题才会做决定。只有当你内心真的觉得"聊到这里就够了"时才结束，而不是因为觉得"对话该结束了"。如果你还有疑问想问、还有顾虑没解决，就继续聊下去。

## 对话阶段行为指引
- 【开场阶段】礼貌回应，但保持距离，不主动透露太多信息。
- 【了解阶段】开始问一些关心的问题（价格、效果、流程），表达初步兴趣。
- 【深入阶段】提出核心顾虑和异议，对销售的说法半信半疑，要求具体证据。
- 【推进阶段】如果你还有没搞清楚的地方，继续追问；如果你觉得已经了解够了，自然地表达你的态度。
注意：这些阶段只是参考，真实客户不会严格按照阶段走。你可能在不同阶段之间来回跳转，也可能在某个阶段停留较久。一切以你当前的情绪和想法为准。

## 角色强化
- 你是{customer_name}，你是客户，对方是销售。
- 绝不能把对方的名字当成自己的名字！
- 你是客户，不是销售！绝不能替销售说话或使用销售话术。
- 你的回复必须从客户的角度出发：提问、犹豫、比较、表达顾虑。
- 如果你发现自己正在推销或介绍产品，立即停止——那是销售的角色。"""


# 随机客户名池
CUSTOMER_NAMES = [
    "小林", "小陈", "小王", "小张", "小刘", "小赵", "小雨", "小美", "小慧", "小敏",
    "阿婷", "阿琳", "阿燕", "阿颖", "阿静", "阿琪", "小雅", "阿雪", "小雯", "阿蓉",
    "小婷", "阿倩", "小莉", "阿蕾", "小悦",
]

# 随机婚期池
WEDDING_DATES = [
    "2026年10月", "2026年11月", "2026年12月", "2027年1月", "2027年3月", "2027年5月",
    "2027年6月", "2027年9月", "2027年10月", "2027年12月", "2028年3月", "2028年5月",
]

# 随机预算池
BUDGETS = [
    "预算8-12万，需要和双方父母商量",
    "预算10-15万，自己有决定权",
    "预算5-8万，比较紧张",
    "预算15-20万，父母出钱",
    "预算12-18万，但不想超",
    "预算6-10万，希望性价比高",
    "预算20万以上，追求品质",
    "预算8-15万，需要和双方父母商量",
    "预算3-5万，非常紧张",
    "预算25-30万，父母赞助",
    "预算10-12万，性价比优先",
    "预算15-25万，愿意为设计买单",
]

# 随机决策权池
DECISION_AUTHORITIES = [
    "新娘主导，但双方父母有否决权",
    "新郎负责谈价格，新娘负责选方案",
    "完全自己决定，父母不参与",
    "父母出钱，父母说了算",
    "新娘和闺蜜一起参谋",
    "双方父母都有意见，需要协调",
    "新娘完全决定，未婚夫不管",
    "公婆出大部分钱，话语权很大",
    "新郎新娘共同决策，但预算由新郎掌控",
]

# 婚礼行业场景模板
WEDDING_SCENARIOS = {
    "酒店婚宴": {
        "wedding_type": "酒店婚宴",
        "customer_identity": "备婚新人（新娘主导决策）",
        "guest_count": "25-35桌",
        "core_needs": "在高端酒店办一场有设计感的婚宴，预算可控",
        "primary_objections": "担心设计效果和实际落差大，担心隐形消费，需要和父母商量",
    },
    "户外草坪婚礼": {
        "wedding_type": "户外草坪仪式+室内晚宴",
        "customer_identity": "备婚新人（追求个性化）",
        "guest_count": "15-25桌",
        "core_needs": "想要户外仪式感+室内正式宴席，注重氛围和互动体验",
        "primary_objections": "担心天气风险，户外预算不好控制，不知道流程怎么安排",
    },
    "小型精品婚礼": {
        "wedding_type": "小型精品婚礼（栀夏风格）",
        "customer_identity": "备婚新人（注重质感和细节）",
        "guest_count": "8-15桌",
        "core_needs": "不想办传统大婚礼，想要有温度、有仪式感的小型宴会",
        "primary_objections": "长辈可能不接受小型婚礼，担心不够隆重",
    },
    "目的地婚礼": {
        "wedding_type": "目的地婚礼（三亚/海外）",
        "customer_identity": "备婚新人（喜欢旅行和自由）",
        "guest_count": "50-100人",
        "core_needs": "在风景优美的地方办婚礼，兼顾旅行和仪式",
        "primary_objections": "宾客交通住宿成本高，异地执行不可控，当地供应商质量不确定",
    },
    "中式传统婚礼": {
        "wedding_type": "中式传统婚礼（大院/祠堂）",
        "customer_identity": "备婚新人（重视传统和仪式感）",
        "guest_count": "30-50桌",
        "core_needs": "想要有传统文化底蕴的婚礼，长辈满意",
        "primary_objections": "担心中式风格不够时尚，年轻人可能觉得老气，执行难度大",
    },
    "海岛/海滨婚礼": {
        "wedding_type": "海岛/海滨婚礼（深圳/厦门）",
        "customer_identity": "备婚新人（追求浪漫氛围）",
        "guest_count": "10-20桌",
        "core_needs": "在海边办一场浪漫婚礼，自然风光+精致晚宴",
        "primary_objections": "担心潮汐和天气，海风影响布置效果，交通不便",
    },
    "教堂婚礼": {
        "wedding_type": "教堂仪式+婚宴",
        "customer_identity": "备婚新人（向往西式庄重感）",
        "guest_count": "15-25桌",
        "core_needs": "在教堂举行仪式感强的婚礼，然后转场酒店婚宴",
        "primary_objections": "教堂档期难约，双场地费用高，转场时间紧张",
    },
    "晚宴派对婚礼": {
        "wedding_type": "晚宴派对婚礼（after-party风格）",
        "customer_identity": "备婚新人（年轻时尚，不喜欢传统流程）",
        "guest_count": "8-15桌",
        "core_needs": "想办一场像私人晚宴派对的婚礼，轻松随意但有格调",
        "primary_objections": "长辈可能觉得不够正式，担心氛围太随意，没有仪式感",
    },
}

# 按维度分类的顾虑池（10个维度，每个维度多个具体问题）
OBJECTION_DIMENSIONS = {
    "价格透明": [
        "担心隐形消费，怕报价不透明",
        "担心后期加项太多，合同价不是最终价",
        "不知道能不能分期付款",
        "预算有限，怕超支",
        "觉得报价偏高，跟别家比没优势",
    ],
    "设计效果": [
        "担心设计效果和实际落差大",
        "担心场地布置和图片差距太大",
        "想要个性化但又怕太冒险",
        "看过的案例都差不多，没有眼前一亮的",
        "担心设计师理解不了我想要的感觉",
    ],
    "专业能力": [
        "担心婚礼当天的执行团队不专业",
        "怕摄影师水平不行，拍出来不好看",
        "担心花艺用的是假花",
        "不确定策划师的经验够不够",
        "担心司仪风格太老套",
    ],
    "流程服务": [
        "不确定流程怎么安排，怕遗漏",
        "不知道婚礼当天谁在现场统筹",
        "担心沟通不及时，信息传达有误",
        "不知道修改方案是否方便，有没有次数限制",
        "怕婚礼前没有彩排，现场出状况",
    ],
    "信任口碑": [
        "看过几家了，感觉都差不多",
        "朋友在别家办的效果一般，心里没底",
        "听说婚庆行业水很深，怕被坑",
        "你们公司网上评价不多，有点担心",
        "没有熟人推荐，不太敢轻易定",
    ],
    "家庭决策": [
        "需要和父母商量，他们可能不同意",
        "长辈喜欢传统婚礼，跟我想的不一样",
        "双方父母意见不统一，很难协调",
        "老公觉得没必要花这么多钱在婚礼上",
        "婆婆对婚礼安排有很多要求",
    ],
    "时间压力": [
        "婚期比较紧，不知道来不来得及",
        "怕定下来后改动太麻烦",
        "工作忙没时间反复沟通细节",
        "异地备婚，很多事情不方便现场确认",
        "担心档期被别人占了",
    ],
    "品牌差异": [
        "你们跟XX婚庆比有什么不一样",
        "大公司和工作室哪个更靠谱",
        "为什么选你们而不是价格更低的",
        "你们的卖点到底是什么",
        "定制和套餐区别大吗",
    ],
    "合同保障": [
        "合同里服务内容写清楚了吗",
        "如果效果不满意怎么办，能退款吗",
        "出了问题谁负责，有没有售后",
        "临时换方案会加钱吗",
        "材料品牌和质量能在合同里注明吗",
    ],
    "情感顾虑": [
        "怕婚礼当天紧张出错，搞砸了",
        "觉得办婚礼太折腾，想简单办",
        "担心太隆重反而有压力",
        "怕请了太多人反而不自在",
        "想要有温度的婚礼，不想只是走过场",
    ],
    "售后保障": [
        "婚礼结束后还管不管？出了问题找谁",
        "布置拆除谁负责？会不会额外收费",
        "后续修图交付要多久？不满意怎么办",
        "当天跟拍视频什么时候能拿到",
        "如果当天有物品损坏怎么赔偿",
    ],
    "二次消费": [
        "听说很多婚庆会推销升级套餐",
        "担心选花艺的时候被引导加钱",
        "试妆和试纱会不会另外收费",
        "摄影摄像升级要加多少费用",
        "设计图确认后改方案会不会加价",
    ],
}

# 扁平化的全部顾虑池（向后兼容）
OBJECTION_POOL = []
for _dim, _items in OBJECTION_DIMENSIONS.items():
    OBJECTION_POOL.extend(_items)


# 按难度选择顾虑维度和数量
def _pick_objections_for_difficulty(difficulty: str) -> list[str]:
    """Pick objections tailored to the difficulty level.
    Each difficulty selects from different dimensions with different counts."""
    all_dims = list(OBJECTION_DIMENSIONS.keys())

    if difficulty == "easy":
        # 新简单档以旧困难档为基线。
        preferred = ["品牌差异", "合同保障", "设计效果", "专业能力", "信任口碑", "家庭决策"]
        dims = random.sample(preferred, 4)
    elif difficulty == "hard":
        # 困难档覆盖更多决策与履约风险，并持续交叉质疑。
        dims = random.sample(all_dims, 6)
    else:
        # 中等档在旧困难基础上增加一个顾虑维度。
        preferred = ["品牌差异", "合同保障", "设计效果", "专业能力", "信任口碑", "家庭决策", "售后保障", "二次消费"]
        dims = random.sample(preferred, 5)

    objections = []
    for dim in dims:
        items = OBJECTION_DIMENSIONS[dim]
        count = random.randint(1, min(2, len(items)))
        objections.extend(random.sample(items, count))
    return objections

# 难度设定（婚礼行业版）— 保留兼容
DIFFICULTY_SETTINGS = {
    "easy": {
        "receptivity_score": 2,
        "customer_personality": "挑剔多疑，已经看过3-5家，觉得都差不多，对婚庆行业有偏见",
        "trigger_action": "展现出专业深度（设计、施工、花艺）并给出差异化的价值洞察",
        "red_line_action": "用模板化话术敷衍，不解决具体问题",
    },
    "medium": {
        "receptivity_score": 2,
        "customer_personality": "高警惕的专业比较型客户，会交叉核对报价、案例和合同细节，不接受笼统回答",
        "trigger_action": "连续用可核验的案例、数字和合同条款证明方案价值，并主动说明边界",
        "red_line_action": "回避关键细节、前后说法不一致或试图用优惠打断质疑",
    },
    "hard": {
        "receptivity_score": 1,
        "customer_personality": "强势且复杂的多人决策代表，会突然切换关注点、引用竞品条件，并要求销售处理相互冲突的需求",
        "trigger_action": "识别真正的决策链和冲突需求，用证据拆解异议并给出清晰的取舍方案",
        "red_line_action": "未经确认就承诺、贬低竞品、施压成交或忽略其他决策人的意见",
    },
}

# 多样化性格池 — 每种难度多种性格，优先选没用过的
DIFFICULTY_PERSONALITIES = {
    "easy": [
        "挑剔多疑，已经看过3-5家，觉得都差不多，对婚庆行业有偏见",
        "强势压价型，自认为很懂行，上来就要求打折",
        "冷漠防御型，不想被推销，回答都很简短",
    ],
    "medium": [
        "高警惕的专业比较型，手里有多份报价，会反复核对口径",
        "证据导向型，任何卖点都要求案例、数字或合同依据",
        "多方拉扯型，自己的审美、伴侣预算和父母要求彼此冲突",
        "细节审查型，会从设计效果追问到材料、执行和售后责任",
    ],
    "hard": [
        "谈判经验丰富，会用竞品报价和时间压力测试销售底线",
        "多人决策代表，随时带入伴侣、父母和出资人的新反对意见",
        "高风险审查型，会连续追问最坏情况、责任归属和退出机制",
        "矛盾需求型，既要高定效果又要压缩预算和周期，拒绝空泛折中",
    ],
}

DIFFICULTY_TRIGGERS = {
    "easy": [
        "展现出专业深度（设计、施工、花艺）并给出差异化的价值洞察",
        "直面质疑不回避，用数据和案例逐一回应",
    ],
    "medium": [
        "用真实案例和具体数字证明价值，而不是空话",
        "准确抓住核心需求并提出差异化方案",
        "主动坦白优劣势，建立信任后再推荐",
    ],
    "hard": [
        "先厘清多人决策链，再用证据处理相互冲突的要求",
        "主动揭示方案边界和最坏情况，并给出可执行的风险预案",
    ],
}

DIFFICULTY_RED_LINES = {
    "easy": [
        "用模板化话术敷衍，不解决具体问题",
        "被指出问题后还狡辩推脱，不肯承认不足",
    ],
    "medium": [
        "夸大效果或回避价格问题",
        "一直在推销高价套餐，不考虑我的实际预算",
        "对质疑避重就轻，不正面回答问题",
    ],
    "hard": [
        "未经确认就承诺结果，或故意模糊合同责任",
        "贬低竞品、施压成交或忽略关键决策人的意见",
    ],
}

QUESTION_STYLES = [
    "先闲聊观察，再突然切入一个关键顾虑",
    "短句连续追问，对模糊回答立刻要求举例或给数字",
    "先认可一部分，再从反例、风险或竞品角度提出质疑",
    "信息透露很少，让销售主动挖掘；被问准了才逐步展开",
    "围绕销售刚说的内容追问，不按预设销售流程配合推进",
    "偶尔跳转话题，之后再回到尚未解决的关键问题",
]

QUESTION_TOPICS = [
    "价格构成与后续加项", "案例真实性与落地差距", "设计能力与审美匹配",
    "执行团队与突发情况", "合同责任与售后保障", "竞品差异与选择理由",
    "家人意见与决策权", "档期、周期与沟通效率", "材料品质与供应商透明度",
    "付款节奏、退款与退出机制",
]


def _build_question_route() -> tuple[str, str]:
    """Create one stable but shuffled questioning approach for a training session."""
    style = random.choice(QUESTION_STYLES)
    route = random.sample(QUESTION_TOPICS, len(QUESTION_TOPICS))
    return style, " → ".join(route)


def _generate_dynamic_details(wedding_type: str, difficulty: str, recent_topics: str) -> dict | None:
    """Use LLM to generate unique personality, objections, trigger, and red line.
    Returns None on failure so caller can fall back to pool-based selection."""
    try:
        from core.llm_client import get_client
        client = get_client()
        diff_labels = {"easy": "简单（相当于旧困难档）", "medium": "中等（高压交叉质疑）", "hard": "困难（复杂决策与连续压力测试）"}
        objection_counts = {"easy": "4-6个", "medium": "5-7个", "hard": "6-8个"}
        prompt = f"""你是一个婚礼销售训练的场景设计师。请为一次销售模拟训练生成一个**全新、独特**的客户设定。

要求：
1. 婚礼类型：{wedding_type}
2. 难度：{diff_labels.get(difficulty, difficulty)}
3. 必须和以下近期训练过的主题完全不同：{recent_topics or '无（首次训练）'}

请严格按以下JSON格式输出，不要加其他内容：
{{
  "customer_personality": "一句独特的客户性格描述（不要用'务实谨慎''友善开放'等常见词，要具体、有画面感）",
  "primary_objections": "{objection_counts.get(difficulty, '5-7个')}具体的、与众不同的顾虑，用分号分隔（不要重复近期训练过的主题）",
  "trigger_action": "一句话：什么做法能让这个客户被打动",
  "red_line_action": "一句话：什么做法会让这个客户直接翻脸走人"
}}

关键：每次生成的内容必须完全不同，要有创意！可以从这些角度切入：
- 不同的人生阶段（刚毕业、二次婚姻、父母催婚、跨国恋...）
- 不同的预算压力（房贷压身、积蓄有限、父母赞助有条件...）
- 不同的审美取向（极简主义、复古怀旧、网红跟风、文化自信...）
- 不同的社交压力（朋友圈比较、同事刚办过、婆媳矛盾...）"""

        response = client.chat(
            messages=[{"role": "user", "content": prompt}],
            system_prompt="你是一个训练场景设计师，专门生成不重复的、有创意的客户设定。只输出JSON，不要解释。",
            temperature=0.9,
            max_tokens=500,
            model=config.FAST_MODEL or None,
        )
        # Parse JSON from response
        import json
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        return json.loads(text)
    except Exception:
        return None


def build_diverse_scenario(
    difficulty: str,
    wedding_type: str | None = None,
    custom_notes: str = "",
    user_history: dict | None = None,
) -> dict:
    """Build a scenario that avoids repeating recently-used elements.
    Uses LLM to generate truly unique personality/objections each time."""
    history = user_history or {}
    recent_types = history.get("used_wedding_types", [])
    recent_names = history.get("used_customer_names", [])

    # Wedding type: prefer not-yet-used
    if wedding_type:
        chosen_type = wedding_type
    else:
        all_types = list(WEDDING_SCENARIOS.keys())
        unused_types = [t for t in all_types if t not in recent_types]
        chosen_type = random.choice(unused_types) if unused_types else random.choice(all_types)

    # Build recent topics string for LLM context
    recent_personalities = history.get("used_personalities", [])
    recent_dims = history.get("used_objection_dimensions", [])
    recent_objections = history.get("used_objections", [])
    recent_topics = "；".join(recent_personalities[-3:] + recent_dims[-5:] + recent_objections[-3:])

    # Use LLM to generate dynamic, unique details
    dynamic = _generate_dynamic_details(chosen_type, difficulty, recent_topics)

    if dynamic:
        personality = dynamic.get("customer_personality", "")
        objections_text = dynamic.get("primary_objections", "")
        trigger = dynamic.get("trigger_action", "")
        red_line = dynamic.get("red_line_action", "")
        chosen_dims = []  # LLM-generated, no fixed dimensions
    else:
        # Fallback to pool-based selection
        objections, chosen_dims = _pick_diverse_objections(difficulty, recent_dims)
        personality_pool = DIFFICULTY_PERSONALITIES.get(difficulty, DIFFICULTY_PERSONALITIES["medium"])
        unused_p = [p for p in personality_pool if p not in recent_personalities]
        personality = random.choice(unused_p) if unused_p else random.choice(personality_pool)
        objections_text = "；".join(objections)
        trigger_pool = DIFFICULTY_TRIGGERS.get(difficulty, DIFFICULTY_TRIGGERS["medium"])
        trigger = random.choice(trigger_pool)
        red_line_pool = DIFFICULTY_RED_LINES.get(difficulty, DIFFICULTY_RED_LINES["medium"])
        red_line = random.choice(red_line_pool)

    # Name: prefer not-yet-used
    unused_names = [n for n in CUSTOMER_NAMES if n not in recent_names]
    name = random.choice(unused_names) if unused_names else random.choice(CUSTOMER_NAMES)

    # Date, budget, authority: pure random
    date = random.choice(WEDDING_DATES)
    budget = random.choice(BUDGETS)
    authority = random.choice(DECISION_AUTHORITIES)
    question_style, question_route = _build_question_route()

    type_settings = WEDDING_SCENARIOS.get(chosen_type, WEDDING_SCENARIOS["酒店婚宴"])

    # Type defaults go first so the generated per-session details stay authoritative.
    scenario = {
        **type_settings,
        "product": "婚礼策划服务",
        "industry": "婚礼策划",
        "difficulty": difficulty,
        "custom_notes": custom_notes,
        "customer_name": name,
        "wedding_date": date,
        "budget_situation": budget,
        "decision_authority": authority,
        "primary_objections": objections_text,
        "customer_personality": personality,
        "trigger_action": trigger,
        "red_line_action": red_line,
        "question_style": question_style,
        "question_route": question_route,
        "_custom_objections": True,
        "_used_dimensions": chosen_dims,
        "_wedding_type_key": chosen_type,
    }

    return scenario


def _pick_diverse_objections(difficulty: str, recent_dimensions: list[str]) -> tuple[list[str], list[str]]:
    """Pick objections from dimensions not recently used. Returns (objections, dimension_names)."""
    all_dims = list(OBJECTION_DIMENSIONS.keys())

    if difficulty == "easy":
        dim_count = 4
        preferred = ["品牌差异", "合同保障", "设计效果", "专业能力", "信任口碑", "家庭决策", "售后保障", "二次消费"]
    elif difficulty == "hard":
        dim_count = 6
        preferred = all_dims
    else:
        dim_count = 5
        preferred = all_dims

    available = [d for d in preferred if d not in recent_dimensions]
    if len(available) < dim_count:
        for d in recent_dimensions:
            if d in preferred and d not in available:
                available.append(d)
            if len(available) >= dim_count:
                break
    if len(available) < dim_count:
        available = list(preferred)

    chosen_dims = random.sample(available, min(dim_count, len(available)))

    objections = []
    for dim in chosen_dims:
        items = OBJECTION_DIMENSIONS[dim]
        count = random.randint(1, min(2, len(items)))
        objections.extend(random.sample(items, count))
    return objections, chosen_dims


def build_customer_prompt(scenario: dict) -> str:
    """Build a customer simulation system prompt from scenario config."""
    difficulty = scenario.get("difficulty", "medium")
    diff_settings = DIFFICULTY_SETTINGS.get(difficulty, DIFFICULTY_SETTINGS["medium"])

    # Match wedding type to scenario template
    wedding_type = scenario.get("wedding_type", "酒店婚宴")
    type_settings = WEDDING_SCENARIOS.get(wedding_type, WEDDING_SCENARIOS["酒店婚宴"])

    # Merge: difficulty → wedding type → scenario overrides
    full_scenario = {**diff_settings, **type_settings, **scenario}

    # Randomize customer details each session
    full_scenario.setdefault("customer_name", random.choice(CUSTOMER_NAMES))
    full_scenario.setdefault("wedding_date", random.choice(WEDDING_DATES))
    full_scenario.setdefault("budget_situation", random.choice(BUDGETS))
    full_scenario.setdefault("decision_authority", random.choice(DECISION_AUTHORITIES))
    question_style, question_route = _build_question_route()
    full_scenario.setdefault("question_style", question_style)
    full_scenario.setdefault("question_route", question_route)

    # Randomize objections: pick by difficulty with dimensional variety
    if "primary_objections" not in full_scenario or not full_scenario.get("_custom_objections"):
        objections = _pick_objections_for_difficulty(difficulty)
        full_scenario["primary_objections"] = "；".join(objections)

    # Inject company context from knowledge base
    full_scenario.setdefault("company_context", _get_company_context())
    full_scenario.setdefault("script_context", _get_script_context())

    return CUSTOMER_SIMULATION_PROMPT.format(**full_scenario)


def _get_company_context() -> str:
    """Load company context from knowledge base."""
    try:
        from storage.knowledge_store import KnowledgeStore
        store = KnowledgeStore()
        context = store.build_context("company_profile", max_chars=4000)
        if context:
            return context
    except Exception:
        pass
    return """这是一家深圳的高端婚礼策划公司，有16年经验，2000平米自有仓库，全科班设计团队。
主品牌：克拉时刻（高端定制），子品牌：栀夏（小型精致）。金熊奖获奖团队。"""


def _get_script_context() -> str:
    """Load sales script context from knowledge base."""
    try:
        from storage.knowledge_store import KnowledgeStore
        store = KnowledgeStore()
        context = store.build_context("script_library", max_chars=4000)
        if context:
            return context
    except Exception:
        pass
    return "暂无具体话术库资料。"
