import os
import asyncio
import discord
import logging
from dotenv import load_dotenv
load_dotenv()
import config
from discord.ext import commands
from core.training_manager import TrainingManager
from core.file_discussion_manager import FileDiscussionManager
from prompts.customer_simulation import build_diverse_scenario
from prompts.file_discussion import FILE_DISCUSSION_SYSTEM_PROMPT
from prompts.report_chat import REPORT_CHAT_SYSTEM_PROMPT
from storage.style_store import StyleStore
from storage.doc_store import DocStore
from storage.report_store import ReportStore
from storage.knowledge_store import KnowledgeStore
from core.llm_client import get_client
from utils.file_parser import extract_text
from utils.text_utils import estimate_tokens, truncate_to_token_limit

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
TARGET_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")
ALLOWED_USER_IDS = os.getenv("ALLOWED_USER_IDS", "").split(",")

if not TOKEN or TOKEN == "your_bot_token_here":
    logging.error("请在 .env 文件中设置有效的 DISCORD_BOT_TOKEN")
    exit(1)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

manager = TrainingManager()
file_manager = FileDiscussionManager()
style_store = StyleStore()
doc_store = DocStore()
report_store = ReportStore()
knowledge_store = KnowledgeStore()
active_sessions = {}

_evaluator_instance = None


def _get_evaluator():
    global _evaluator_instance
    if _evaluator_instance is None:
        from core.evaluator import Evaluator
        _evaluator_instance = Evaluator()
    return _evaluator_instance

# channel_id -> doc_number (当前讨论的文档编号)
active_doc_sessions = {}

# channel_id -> report_id (当前讨论的面聊报告)
active_report_sessions = {}

# 管理员用户ID列表（admin角色，可查看所有文档）
ADMIN_USER_IDS = {"1374278183612055572"}


def is_allowed_user(user_id: int) -> bool:
    if not ALLOWED_USER_IDS or ALLOWED_USER_IDS == [""]:
        return True
    return str(user_id) in ALLOWED_USER_IDS


def is_dm(channel) -> bool:
    return isinstance(channel, discord.DMChannel)


def get_style_choices():
    profiles = style_store.list_all()
    if not profiles:
        return []
    return [p.name for p in profiles]


def is_admin(user_id: int) -> bool:
    return str(user_id) in ADMIN_USER_IDS or not ADMIN_USER_IDS


def can_access_doc(doc, user_id: int) -> bool:
    """Admin can access all docs; sales only their own."""
    return is_admin(user_id) or str(doc.uploader_id) == str(user_id)


@bot.event
async def on_ready():
    logging.info(f"Bot online: {bot.user.name} (ID: {bot.user.id})")
    try:
        for guild in bot.guilds:
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            logging.info(f"Synced {len(synced)} slash commands to guild: {guild.name}")
    except Exception as e:
        logging.error(f"Failed to sync slash commands: {e}")


# === 斜杠命令 ===

@bot.tree.command(name="start", description="开始销售训练（AI当客户，你练销售）")
@discord.app_commands.describe(difficulty="选择难度", doc="文档编号，基于文档内容训练（可选）")
@discord.app_commands.choices(difficulty=[
    discord.app_commands.Choice(name="自动", value="auto"),
    discord.app_commands.Choice(name="简单", value="easy"),
    discord.app_commands.Choice(name="中等", value="medium"),
    discord.app_commands.Choice(name="困难", value="hard"),
])
async def slash_start(interaction: discord.Interaction, difficulty: str = None, doc: int = None):
    if not is_allowed_user(interaction.user.id):
        await interaction.response.send_message("❌ 你没有使用权限。", ephemeral=True)
        return

    if file_manager.has_session(interaction.channel_id):
        file_manager.end_session(interaction.channel_id)
    if interaction.channel_id in active_doc_sessions:
        del active_doc_sessions[interaction.channel_id]
    if interaction.channel_id in active_report_sessions:
        del active_report_sessions[interaction.channel_id]

    # Dynamic difficulty: auto-recommend based on history
    if difficulty and difficulty in ("easy", "medium", "hard"):
        diff_key = difficulty
    else:
        from core.difficulty_engine import DifficultyEngine
        diff_key = DifficultyEngine().recommend(interaction.user.display_name)

    # Use diverse scenario generation (same as web version)
    from prompts.customer_simulation import build_diverse_scenario
    from storage.scenario_history_store import ScenarioHistoryStore
    history_store = ScenarioHistoryStore()
    user_history = history_store.get_recent(interaction.user.display_name)

    scenario = build_diverse_scenario(
        difficulty=diff_key,
        custom_notes="",
        user_history=user_history,
    )

    # Record what was used for next time
    history_store.record_session(interaction.user.display_name, {
        "wedding_type": scenario.get("_wedding_type_key") or scenario.get("wedding_type"),
        "objection_dimensions": scenario.get("_used_dimensions", []),
        "personality": scenario.get("customer_personality", ""),
        "customer_name": scenario.get("customer_name", ""),
        "primary_objections": scenario.get("primary_objections", ""),
    })

    # 如果指定了文档，把文档内容注入场景
    doc_info = ""
    if doc:
        doc_entry = doc_store.get(doc)
        if not doc_entry:
            await interaction.response.send_message(f"❌ 文档编号 {doc} 不存在。用 `/files` 查看文档列表。")
            return
        if not can_access_doc(doc_entry, interaction.user.id):
            await interaction.response.send_message(f"❌ 你没有权限查看文档 {doc}。")
            return
        doc_info = f"\n**参考文档**：#{doc} {doc_entry.filename}"
        scenario["custom_notes"] = scenario.get("custom_notes", "") + f"\n\n参考文档内容：\n{doc_entry.content[:3000]}"

    session = manager.create_session(
        mode="customer",
        scenario=scenario,
        style_profile_id=None,
    )
    session.user = interaction.user.display_name
    manager.session_store.save(session)
    active_sessions[interaction.channel_id] = session.id

    diff_labels = {"easy": "简单", "medium": "中等", "hard": "困难"}
    embed = discord.Embed(
        title="🚀 销售实战训练开始！",
        description=f"**场景**：{scenario['wedding_type']}\n**难度**：{diff_labels[diff_key]}\n**客户设定**：{scenario['core_needs']}{doc_info}\n\n请主动打招呼开始对话！",
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed)
    await interaction.channel.send("——— ✅ 已添加好友 ———")


@bot.tree.command(name="learn", description="学习模式（AI当销售，你当客户）")
@discord.app_commands.describe(style="选择销售风格（可选）", difficulty="选择难度")
@discord.app_commands.choices(difficulty=[
    discord.app_commands.Choice(name="自动", value="auto"),
    discord.app_commands.Choice(name="简单", value="easy"),
    discord.app_commands.Choice(name="中等", value="medium"),
    discord.app_commands.Choice(name="困难", value="hard"),
])
async def slash_learn(interaction: discord.Interaction, style: str = None, difficulty: str = None):
    if not is_allowed_user(interaction.user.id):
        await interaction.response.send_message("❌ 你没有使用权限。", ephemeral=True)
        return

    if file_manager.has_session(interaction.channel_id):
        file_manager.end_session(interaction.channel_id)
    if interaction.channel_id in active_doc_sessions:
        del active_doc_sessions[interaction.channel_id]
    if interaction.channel_id in active_report_sessions:
        del active_report_sessions[interaction.channel_id]

    style_profile_id = None
    style_display = "默认顾问式"

    if style:
        profiles = style_store.list_all()
        for p in profiles:
            if p.name == style or style in p.name:
                style_profile_id = p.id
                style_display = p.name
                break
        if not style_profile_id:
            styles = get_style_choices()
            if styles:
                await interaction.response.send_message(f"❌ 未找到风格「{style}」。可选：{'、'.join(styles)}")
            else:
                await interaction.response.send_message(f"❌ 未找到风格「{style}」。用 `/learn` 使用默认。")
            return

    # Dynamic difficulty
    if difficulty and difficulty in ("easy", "medium", "hard"):
        diff_key = difficulty
    else:
        from core.difficulty_engine import DifficultyEngine
        diff_key = DifficultyEngine().recommend(interaction.user.display_name)

    # Use diverse scenario generation (same as web version)
    from prompts.customer_simulation import build_diverse_scenario
    from storage.scenario_history_store import ScenarioHistoryStore
    history_store = ScenarioHistoryStore()
    user_history = history_store.get_recent(interaction.user.display_name)

    scenario = build_diverse_scenario(
        difficulty=diff_key,
        custom_notes="",
        user_history=user_history,
    )
    scenario["customer_description"] = "正在筹备婚礼的备婚新人"

    # Record what was used for next time
    history_store.record_session(interaction.user.display_name, {
        "wedding_type": scenario.get("_wedding_type_key") or scenario.get("wedding_type"),
        "objection_dimensions": scenario.get("_used_dimensions", []),
        "personality": scenario.get("customer_personality", ""),
        "customer_name": scenario.get("customer_name", ""),
        "primary_objections": scenario.get("primary_objections", ""),
    })

    session = manager.create_session(
        mode="salesperson",
        scenario=scenario,
        style_profile_id=style_profile_id,
    )
    session.user = interaction.user.display_name
    manager.session_store.save(session)
    active_sessions[interaction.channel_id] = session.id

    diff_labels = {"easy": "简单", "medium": "中等", "hard": "困难"}
    embed = discord.Embed(
        title="📚 学习模式开始！",
        description=f"**场景**：{scenario['wedding_type']}\n**难度**：{diff_labels[diff_key]}\n**销售风格**：{style_display}\n\nAI 扮演销售，你扮演客户。先说一句话作为客户开场吧！",
        color=discord.Color.purple()
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="stop", description="结束当前训练并生成评估报告")
async def slash_stop(interaction: discord.Interaction):
    if not is_allowed_user(interaction.user.id):
        await interaction.response.send_message("❌ 你没有使用权限。", ephemeral=True)
        return

    session_id = active_sessions.pop(interaction.channel_id, None)
    doc_cleared = interaction.channel_id in active_doc_sessions
    report_cleared = interaction.channel_id in active_report_sessions
    if doc_cleared:
        del active_doc_sessions[interaction.channel_id]
    if report_cleared:
        del active_report_sessions[interaction.channel_id]
    if file_manager.has_session(interaction.channel_id):
        file_manager.end_session(interaction.channel_id)

    if session_id:
        await interaction.response.send_message("⏳ 正在生成训练评估报告，请稍候...")
        try:
            session = await asyncio.to_thread(manager.end_session, session_id)
            evaluator = _get_evaluator()

            # Full report (includes summary internally)
            try:
                full_report = await asyncio.wait_for(
                    asyncio.to_thread(evaluator.evaluate, session_id),
                    timeout=60
                )
            except asyncio.TimeoutError:
                logging.error(f"[stop] Evaluation timeout for session {session_id[:8]}")
                full_report = None
            except Exception:
                full_report = None

            # Fallback: summary only
            summary = full_report.conversation_summary if full_report else None
            if not summary:
                try:
                    summary = await asyncio.wait_for(
                        asyncio.to_thread(evaluator.generate_summary_only, session_id),
                        timeout=15
                    )
                except Exception:
                    summary = None

            turn_count = len(session.conversation) // 2
            receptivity = session.receptivity_history
            recep_text = f"{receptivity[0]}→{receptivity[-1]}" if receptivity and len(receptivity) >= 2 else "-"

            desc = f"**对话轮次**：{turn_count}轮\n**客户接受度**：{recep_text}\n\n"
            if summary and len(summary) > 3800:
                desc += summary[:3800] + "\n..."
            else:
                desc += summary or ""

            embed = discord.Embed(
                title="📋 训练评估报告",
                description=desc[:4096],
                color=discord.Color.gold()
            )

            if full_report and full_report.deal_progression:
                dp = full_report.deal_progression
                dp_text = ""
                if dp.get("current_stage"):
                    dp_text += f"**当前阶段**：{dp['current_stage']}\n"
                if dp.get("risk_level"):
                    dp_text += f"**风险等级**：{dp['risk_level']} — {dp.get('risk_reason', '')}\n"
                if dp.get("next_steps"):
                    dp_text += "\n**下一步**：\n"
                    for step in dp["next_steps"][:3]:
                        dp_text += f"{step.get('step', '?')}. {step.get('action', '')}\n"
                        if step.get("script"):
                            dp_text += f"   话术：{step['script'][:80]}\n"
                if dp.get("win_strategy"):
                    dp_text += f"\n**赢单策略**：{dp['win_strategy']}"
                if dp_text:
                    embed.add_field(name="签单路径", value=dp_text[:1024], inline=False)

            if full_report and full_report.dimension_scores:
                scores_text = ""
                for dim, data in full_report.dimension_scores.items():
                    score = data.get("score", 0) if isinstance(data, dict) else data
                    bar = "█" * score + "░" * (10 - score)
                    scores_text += f"{dim}：{bar} {score}/10\n"
                if scores_text:
                    embed.add_field(name="维度评分", value=scores_text[:1024], inline=False)

            if full_report:
                footer = "完整评估报告（含雷达图）请在网页版「评估报告」Tab查看"
                extracted = getattr(full_report, '_extracted_phrases', 0)
                if extracted:
                    footer += f" | 已自动提取{extracted}条优秀话术"
                embed.set_footer(text=footer)

            await interaction.channel.send(embed=embed)
        except Exception as e:
            logging.error(f"Failed to generate evaluation: {e}")
            await interaction.channel.send(f"✅ 训练已结束，但评估报告生成失败：{str(e)[:200]}")
    else:
        cleared = []
        if doc_cleared:
            cleared.append("文档讨论")
        if report_cleared:
            cleared.append("报告讨论")
        if cleared:
            await interaction.response.send_message(f"✅ 已结束：{'、'.join(cleared)}")
        else:
            await interaction.response.send_message("❌ 当前没有进行中的会话。")


@bot.tree.command(name="evaluate", description="查看训练评估报告")
@discord.app_commands.describe(number="训练编号（用 /history 查看，留空则最近一次）")
async def slash_evaluate(interaction: discord.Interaction, number: int = None):
    if not is_allowed_user(interaction.user.id):
        await interaction.response.send_message("❌ 你没有使用权限。", ephemeral=True)
        return

    sessions = _get_completed_sessions()
    if not sessions:
        await interaction.response.send_message("📭 暂无已完成的训练记录。先用 `/start` 开始一次训练。")
        return

    if number is not None:
        total = len(sessions)
        if number < 1 or number > total:
            await interaction.response.send_message(f"❌ 编号 #{number} 不存在。用 `/history` 查看所有记录（共{total}条）。")
            return
        session = sessions[number - 1]
    else:
        session = sessions[-1]

    # Auto-fix stale active sessions
    if session.status == "active":
        from storage.session_store import SessionStore
        from datetime import datetime
        session.status = "completed"
        session.end_reason = session.end_reason or "考虑"
        if not session.ended_at:
            session.ended_at = datetime.now().isoformat()
        SessionStore().save(session)

    session_id = session.id
    turn_count = len(session.conversation) // 2
    status_label = {"completed": "已完成", "abandoned": "已放弃"}.get(session.status, session.status)
    started = session.started_at[:10] if session.started_at else "?"

    await interaction.response.send_message(f"⏳ 正在生成评估报告（{started} | {turn_count}轮 | {status_label}），请稍候...")

    try:
        evaluator = _get_evaluator()
        logging.info(f"[evaluate] Starting for session {session_id[:8]}")

        # Full report (includes summary + progression + dimensions)
        try:
            full_report = await asyncio.wait_for(
                asyncio.to_thread(evaluator.evaluate, session_id),
                timeout=60
            )
        except asyncio.TimeoutError:
            logging.error(f"[evaluate] Timeout for session {session_id[:8]}")
            full_report = None
        except Exception as e:
            logging.error(f"[evaluate] evaluate() error: {e}")
            full_report = None

        # Fallback: summary only if full report failed
        summary = full_report.conversation_summary if full_report else None
        if not summary:
            try:
                summary = await asyncio.wait_for(
                    asyncio.to_thread(evaluator.generate_summary_only, session_id),
                    timeout=15
                )
            except Exception:
                summary = "总结生成失败，请稍后重试。"

        recep = session.receptivity_history
        recep_text = f"{recep[0]}→{recep[-1]}" if recep and len(recep) >= 2 else "-"

        desc = f"**日期**：{started}\n**对话轮次**：{turn_count}轮\n**客户接受度**：{recep_text}\n**状态**：{status_label}\n\n"
        if summary and len(summary) > 3500:
            desc += summary[:3500] + "\n..."
        else:
            desc += summary or ""

        embed = discord.Embed(title="📋 训练评估报告", description=desc[:4096], color=discord.Color.gold())

        if full_report and full_report.deal_progression:
            dp = full_report.deal_progression
            dp_text = ""
            if dp.get("current_stage"):
                dp_text += f"**当前阶段**：{dp['current_stage']}\n"
            if dp.get("risk_level"):
                dp_text += f"**风险等级**：{dp['risk_level']} — {dp.get('risk_reason', '')}\n"
            if dp.get("next_steps"):
                dp_text += "\n**下一步**：\n"
                for step in dp["next_steps"][:3]:
                    dp_text += f"{step.get('step', '?')}. {step.get('action', '')}\n"
                    if step.get("script"):
                        dp_text += f"   话术：{step['script'][:80]}\n"
            if dp.get("win_strategy"):
                dp_text += f"\n**赢单策略**：{dp['win_strategy']}"
            if dp_text:
                embed.add_field(name="签单路径", value=dp_text[:1024], inline=False)

        if full_report and full_report.dimension_scores:
            scores_text = ""
            for dim, data in full_report.dimension_scores.items():
                score = data.get("score", 0) if isinstance(data, dict) else data
                bar = "█" * score + "░" * (10 - score)
                scores_text += f"{dim}：{bar} {score}/10\n"
            if scores_text:
                embed.add_field(name="维度评分", value=scores_text[:1024], inline=False)

        if full_report:
            embed.set_footer(text="完整评估报告（含雷达图）请在网页版「评估报告」Tab查看")

        await interaction.channel.send(embed=embed)
    except asyncio.TimeoutError:
        logging.error(f"[evaluate] Overall timeout for session {session_id[:8]}")
        await interaction.channel.send("⚠️ 评估报告生成超时，LLM可能暂时不可用。请稍后再试或查看网页版。")
    except Exception as e:
        logging.error(f"[evaluate] Unexpected error: {e}", exc_info=True)
        await interaction.channel.send(f"⚠️ 评估报告生成失败：{str(e)[:200]}")


@bot.tree.command(name="history", description="查看过往训练记录")
@discord.app_commands.describe(page="页码（每页5条）")
async def slash_history(interaction: discord.Interaction, page: int = 1):
    if not is_allowed_user(interaction.user.id):
        await interaction.response.send_message("❌ 你没有使用权限。", ephemeral=True)
        return

    from storage.session_store import SessionStore
    sess_store = SessionStore()
    sessions = sess_store.list_all()
    completed = [s for s in sessions if (
        (s.status in ("completed", "abandoned") and len(s.conversation) >= 2) or
        (s.status == "active" and len(s.conversation) >= 4)
    )]
    if not completed:
        await interaction.response.send_message("📭 暂无训练记录。先用 `/start` 开始一次训练。")
        return

    per_page = 5
    total = len(completed)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    # Show newest first, paginate
    reversed_list = list(reversed(completed))
    start_idx = (page - 1) * per_page
    page_items = reversed_list[start_idx:start_idx + per_page]

    lines = [f"📝 **训练历史**（第{page}/{total_pages}页）：\n"]
    for i, s in enumerate(page_items, start=1):
        global_idx = total - start_idx - i + 1  # 1-based from oldest
        turn_count = len(s.conversation) // 2
        status_label = {"completed": "✅", "abandoned": "⚠️", "active": "🔄"}.get(s.status, "")
        mode_label = "练习" if s.mode == "customer" else "学习"
        recep = s.receptivity_history
        recep_text = f"{recep[0]}→{recep[-1]}" if recep and len(recep) >= 2 else "-"
        started = s.started_at[:10] if s.started_at else "?"
        end_labels = {"成功": "有意向", "离开": "离开", "考虑": "考虑", "红线": "红线"}
        end_text = end_labels.get(s.end_reason, s.end_reason or "-")
        lines.append(f"{status_label} **#{global_idx}** {started} | {mode_label} | {turn_count}轮 | 接受度{recep_text} | {end_text}")

    lines.append(f"\n`/evaluate` 最近一次 | `/evaluate number:编号` 指定记录 | `/history page:{page+1 if page < total_pages else 1}` 翻页")
    await interaction.response.send_message("\n".join(lines))


# Store completed sessions list for /evaluate number lookup
def _get_completed_sessions():
    from storage.session_store import SessionStore
    sess_store = SessionStore()
    sessions = sess_store.list_all()
    return [s for s in sessions if (
        (s.status in ("completed", "abandoned") and len(s.conversation) >= 2) or
        (s.status == "active" and len(s.conversation) >= 4)
    )]


@bot.tree.command(name="styles", description="查看可选的销售风格")
async def slash_styles(interaction: discord.Interaction):
    if not is_allowed_user(interaction.user.id):
        await interaction.response.send_message("❌ 你没有使用权限。", ephemeral=True)
        return

    styles = get_style_choices()
    if styles:
        style_list = "\n".join(f"• {s}" for s in styles)
        await interaction.response.send_message(f"🎭 **可选销售风格**：\n{style_list}\n\n用 `/learn style:风格名` 指定风格")
    else:
        await interaction.response.send_message("暂无销售风格。可在网页版「风格管理」中提取。")


class DocSelectView(discord.ui.View):
    """下拉菜单选择文档，点选即可打开讨论。"""

    def __init__(self, docs: list, user_id: int, is_admin_flag: bool):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.is_admin = is_admin_flag

        options = []
        for d in docs[:25]:  # Discord 最多 25 个选项
            label = f"#{d.number} {d.filename}"
            if len(label) > 100:
                label = label[:97] + "..."
            summary_preview = (d.summary[:60] + "...") if len(d.summary) > 60 else d.summary
            options.append(discord.SelectOption(
                label=label,
                description=summary_preview,
                value=str(d.number),
            ))

        self.select = discord.ui.Select(
            placeholder="选择文档查看...",
            options=options,
        )
        self.select.callback = self._on_select
        self.add_item(self.select)

    async def _on_select(self, interaction: discord.Interaction):
        if not is_allowed_user(interaction.user.id):
            await interaction.response.send_message("❌ 你没有使用权限。", ephemeral=True)
            return

        number = int(self.select.values[0])
        doc_entry = doc_store.get(number)
        if not doc_entry:
            await interaction.response.send_message(f"❌ 文档 #{number} 不存在。", ephemeral=True)
            return

        if not can_access_doc(doc_entry, interaction.user.id):
            await interaction.response.send_message(f"❌ 你没有权限查看文档 #{number}。", ephemeral=True)
            return

        active_doc_sessions[interaction.channel_id] = number
        if interaction.channel_id in active_sessions:
            del active_sessions[interaction.channel_id]
        if interaction.channel_id in active_report_sessions:
            del active_report_sessions[interaction.channel_id]

        summary_preview = doc_entry.summary[:1000]
        conv_count = len(doc_entry.conversation) // 2
        embed = discord.Embed(
            title=f"📄 文档 #{number}：{doc_entry.filename}",
            description=f"**类型**：{doc_entry.file_type}\n**上传时间**：{doc_entry.created_at[:10]}\n**历史对话**：{conv_count}轮\n\n{summary_preview}\n\n你可以直接提问关于这份文档的内容。用 `/stop` 结束讨论。",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)


@bot.tree.command(name="files", description="查看你上传过的文档列表")
@discord.app_commands.describe(search="按文件名关键词筛选（可选）", mine="只看我上传的（可选）")
async def slash_files(interaction: discord.Interaction, search: str = None, mine: bool = None):
    if not is_allowed_user(interaction.user.id):
        await interaction.response.send_message("❌ 你没有使用权限。", ephemeral=True)
        return

    # mine=True 或非admin用户只看自己的
    show_all = is_admin(interaction.user.id) and not mine
    docs = doc_store.list_by_user(interaction.user.id, is_admin=show_all)
    if not docs:
        await interaction.response.send_message("📭 暂无文档。直接发送文件附件即可上传。")
        return

    # 按关键词筛选
    if search:
        search_lower = search.lower()
        docs = [d for d in docs if search_lower in d.filename.lower() or search_lower in d.summary.lower()]
        if not docs:
            await interaction.response.send_message(f"📭 没有匹配「{search}」的文档。")
            return

    lines = ["📑 **文档列表**：\n"]
    for d in docs:
        owner = ""
        if show_all and d.uploader_id != str(interaction.user.id):
            owner = f" | 👤{d.uploader_name or d.uploader_id}"
        # 摘要失败时用文件类型和大小代替
        if d.summary and not d.summary.startswith("摘要生成失败"):
            summary_brief = (d.summary[:40] + "...") if len(d.summary) > 40 else d.summary
        else:
            summary_brief = f"({d.file_type})"
        lines.append(f"**#{d.number}** {d.filename} ({d.file_type}){owner} — {d.created_at[:10]}\n　{summary_brief}")

    lines.append("\n👇 也可以在下方下拉菜单直接选择文档")
    view = DocSelectView(docs, interaction.user.id, is_admin=show_all)
    await interaction.response.send_message("\n".join(lines), view=view)


@bot.tree.command(name="doc", description="查看并讨论指定编号的文档")
@discord.app_commands.describe(number="文档编号")
async def slash_doc(interaction: discord.Interaction, number: int):
    if not is_allowed_user(interaction.user.id):
        await interaction.response.send_message("❌ 你没有使用权限。", ephemeral=True)
        return

    doc_entry = doc_store.get(number)
    if not doc_entry:
        await interaction.response.send_message(f"❌ 文档 #{number} 不存在。用 `/files` 查看列表。")
        return

    if not can_access_doc(doc_entry, interaction.user.id):
        await interaction.response.send_message(f"❌ 你没有权限查看文档 #{number}。")
        return

    # 设置当前频道讨论该文档
    active_doc_sessions[interaction.channel_id] = number

    # 结束其他会话
    if interaction.channel_id in active_sessions:
        del active_sessions[interaction.channel_id]
    if interaction.channel_id in active_report_sessions:
        del active_report_sessions[interaction.channel_id]

    summary_preview = doc_entry.summary[:1000]
    conv_count = len(doc_entry.conversation) // 2
    embed = discord.Embed(
        title=f"📄 文档 #{number}：{doc_entry.filename}",
        description=f"**类型**：{doc_entry.file_type}\n**上传时间**：{doc_entry.created_at[:10]}\n**历史对话**：{conv_count}轮\n\n{summary_preview}\n\n你可以直接提问关于这份文档的内容。用 `/stop` 结束讨论。",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="del", description="删除指定编号的文档")
@discord.app_commands.describe(number="文档编号")
async def slash_del(interaction: discord.Interaction, number: int):
    if not is_allowed_user(interaction.user.id):
        await interaction.response.send_message("❌ 你没有使用权限。", ephemeral=True)
        return

    doc_entry = doc_store.get(number)
    if not doc_entry:
        await interaction.response.send_message(f"❌ 文档 #{number} 不存在。")
        return

    if not can_access_doc(doc_entry, interaction.user.id):
        await interaction.response.send_message(f"❌ 你没有权限删除文档 #{number}。")
        return

    if doc_store.delete(number):
        if active_doc_sessions.get(interaction.channel_id) == number:
            del active_doc_sessions[interaction.channel_id]
        await interaction.response.send_message(f"✅ 文档 #{number} 已删除。")
    else:
        await interaction.response.send_message(f"❌ 删除失败。")


@bot.tree.command(name="reports", description="查看面聊分析报告列表")
async def slash_reports(interaction: discord.Interaction):
    if not is_allowed_user(interaction.user.id):
        await interaction.response.send_message("❌ 你没有使用权限。", ephemeral=True)
        return

    reports = report_store.list_all()
    if not reports:
        await interaction.response.send_message("📭 暂无面聊报告。可在网页版「风格管理」中导入并生成。")
        return

    lines = ["📋 **面聊分析报告**：\n"]
    for i, r in enumerate(reports, 1):
        lines.append(
            f"**#{i}** {r.source_title} — 销售：{r.sales_name} — {r.created_at[:10]}\n"
            f"　评价：{r.summary[:80]}"
        )

    lines.append("\n`/report number:编号` 查看详细并与AI教练讨论")
    await interaction.response.send_message("\n".join(lines))


@bot.tree.command(name="report", description="查看面聊报告详情并与AI教练讨论")
@discord.app_commands.describe(number="报告编号（用 /reports 查看）")
async def slash_report(interaction: discord.Interaction, number: int):
    if not is_allowed_user(interaction.user.id):
        await interaction.response.send_message("❌ 你没有使用权限。", ephemeral=True)
        return

    reports = report_store.list_all()
    if number < 1 or number > len(reports):
        await interaction.response.send_message(f"❌ 编号 #{number} 不存在。用 `/reports` 查看列表。")
        return

    report = reports[number - 1]

    # 结束其他会话
    if interaction.channel_id in active_sessions:
        del active_sessions[interaction.channel_id]
    if interaction.channel_id in active_doc_sessions:
        del active_doc_sessions[interaction.channel_id]
    active_report_sessions[interaction.channel_id] = report.id

    highlights_text = "\n".join(f"✅ {h}" for h in report.highlights[:5])
    improvements_text = "\n".join(f"⚠️ {im}" for im in report.improvements[:5])
    scripts_text = ""
    for s in report.corrected_scripts[:3]:
        scripts_text += f"**原文**：{s.get('original', '')[:100]}\n**改写**：{s.get('corrected', '')[:100]}\n**原因**：{s.get('reason', '')[:80]}\n\n"
    next_steps_text = "\n".join(f"➡️ {ns}" for ns in report.next_steps[:3])

    desc = (
        f"**销售**：{report.sales_name}\n"
        f"**来源**：{report.source_title}\n"
        f"**日期**：{report.created_at[:10]}\n\n"
        f"**整体评价**：{report.summary}\n\n"
        f"**做得好的**：\n{highlights_text}\n\n"
        f"**需改进的**：\n{improvements_text}\n"
    )
    if scripts_text:
        desc += f"\n**改进话术**：\n{scripts_text}"
    if next_steps_text:
        desc += f"\n**下一步建议**：\n{next_steps_text}"

    embed = discord.Embed(
        title=f"📋 面聊报告 — {report.source_title}",
        description=desc[:4000],
        color=discord.Color.orange()
    )
    await interaction.response.send_message(embed=embed)
    await interaction.channel.send("💬 你可以直接提问关于这次面聊的内容，AI教练会基于报告回答你。用 `/stop` 结束讨论。")


@bot.tree.command(name="knowledge", description="查看知识库中的面聊记录")
async def slash_knowledge(interaction: discord.Interaction):
    if not is_allowed_user(interaction.user.id):
        await interaction.response.send_message("❌ 你没有使用权限。", ephemeral=True)
        return

    entries = knowledge_store.list_by_category("customer_doc")
    if not entries:
        await interaction.response.send_message("📭 暂无面聊记录。可在网页版导入或运行 `scripts/import_knowledge.py`。")
        return

    lines = ["🎙️ **线下面聊记录**：\n"]
    for i, e in enumerate(entries, 1):
        lines.append(f"**#{i}** {e.title} — {e.created_at[:10]}")

    lines.append("\n`/report number:编号` 查看对应分析报告")
    await interaction.response.send_message("\n".join(lines))


@bot.tree.command(name="weekly", description="生成本周训练复盘报告")
async def slash_weekly(interaction: discord.Interaction):
    if not is_allowed_user(interaction.user.id):
        await interaction.response.send_message("❌ 你没有使用权限。", ephemeral=True)
        return

    await interaction.response.send_message("⏳ 正在生成每周复盘报告，请稍候...")

    try:
        from core.weekly_review import WeeklyReviewer
        reviewer = WeeklyReviewer()
        review = await asyncio.wait_for(
            asyncio.to_thread(reviewer.generate, interaction.user.display_name),
            timeout=60
        )

        if not review:
            await interaction.channel.send("📭 本周暂无训练数据，无法生成复盘。先完成几次训练再来查看！")
            return

        lines = [f"**周期**：{review.week_start} ~ {review.week_end}"]
        lines.append(f"**训练次数**：{review.session_count}次")
        lines.append(f"**成功次数**：{review.success_count}次")
        lines.append(f"**平均总分**：{review.avg_overall_score}/10")
        lines.append(f"**分数趋势**：{review.score_trend}")

        if review.avg_dimension_scores:
            dim_text = "、".join(f"{k}{v}分" for k, v in review.avg_dimension_scores.items())
            lines.append(f"**各维度**：{dim_text}")

        if review.summary:
            lines.append(f"\n**本周总结**：{review.summary}")

        if review.suggestions:
            lines.append("\n**改进建议**：")
            for i, s in enumerate(review.suggestions, 1):
                lines.append(f"{i}. {s}")

        if review.focus_areas:
            lines.append("\n**下周重点**：")
            for i, f in enumerate(review.focus_areas, 1):
                lines.append(f"{i}. {f}")

        embed = discord.Embed(
            title="📊 每周训练复盘",
            description="\n".join(lines)[:4096],
            color=discord.Color.teal()
        )
        await interaction.channel.send(embed=embed)
    except asyncio.TimeoutError:
        await interaction.channel.send("⚠️ 复盘报告生成超时，请稍后重试。")
    except Exception as e:
        logging.error(f"[weekly] Error: {e}")
        await interaction.channel.send(f"⚠️ 生成失败：{str(e)[:200]}")


@bot.tree.command(name="help", description="查看所有命令")
async def slash_help(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📖 销售大师 命令列表",
        description=(
            "**训练**\n"
            "/start — 销售训练（AI当客户）\n"
            "/start difficulty:难度 doc:编号 — 指定难度/文档\n"
            "/learn — 学习模式（AI当销售）\n"
            "/learn style:风格 difficulty:难度 — 指定风格/难度\n"
            "/stop — 结束当前会话并生成评估报告\n"
            "/evaluate — 查看最近一次训练的评估报告\n"
            "/evaluate number:编号 — 查看指定训练的评估报告\n"
            "/history — 查看过往训练记录\n\n"
            "**文档**\n"
            "/files — 查看文档列表\n"
            "/doc number:编号 — 查看/讨论文档\n"
            "/del number:编号 — 删除文档\n"
            "💡 直接发送文件附件即可上传\n\n"
            "**面聊记录**\n"
            "/reports — 查看面聊分析报告列表\n"
            "/report number:编号 — 查看报告并讨论\n"
            "/knowledge — 查看原始面聊记录\n\n"
            "**风格**\n"
            "/styles — 查看可选风格\n\n"
            "**复盘**\n"
            "/weekly — 生成本周训练复盘报告"
        ),
        color=discord.Color.gold()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


# === 消息处理 ===

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if not is_allowed_user(message.author.id):
        return

    if is_dm(message.channel) and message.content.strip() == "":
        await message.channel.send("输入 `/` 查看所有命令！")
        return

    # 处理文件附件 — 自动保存到文档库
    if message.attachments:
        for attachment in message.attachments:
            ext = attachment.filename.lower().split(".")[-1]
            if ext not in config.SUPPORTED_FILE_EXTENSIONS:
                continue

            if attachment.size > config.MAX_FILE_SIZE_MB * 1024 * 1024:
                await message.reply(f"❌ 文件 {attachment.filename} 超过 {config.MAX_FILE_SIZE_MB}MB 限制")
                continue

            async with message.channel.typing():
                await message.reply("📄 正在处理文件，请稍候...")

                # 下载文件
                import tempfile
                download_dir = config.FILE_DOWNLOAD_DIR
                os.makedirs(download_dir, exist_ok=True)
                file_path = os.path.join(download_dir, f"{message.channel.id}_{attachment.filename}")
                await attachment.save(file_path)

                try:
                    # 提取文本
                    text = extract_text(file_path)
                    if text.startswith("[无法解析") or text.startswith("[无法进行") or text.startswith("[OCR"):
                        await message.reply(f"❌ 文件处理失败：{text}")
                        continue

                    # 截断过长内容
                    from prompts.file_discussion import FILE_DISCUSSION_TOO_LONG_NOTE
                    full_content = text
                    if estimate_tokens(text) > config.MAX_CHUNK_TOKENS:
                        text = truncate_to_token_limit(text, config.MAX_CHUNK_TOKENS) + FILE_DISCUSSION_TOO_LONG_NOTE

                    # 生成摘要
                    from prompts.file_discussion import FILE_SUMMARY_PROMPT
                    client = get_client()
                    file_type_label = {
                        "docx": "Word文档", "doc": "Word文档", "pdf": "PDF文档",
                        "xlsx": "Excel表格", "xls": "Excel表格",
                        "pptx": "PowerPoint演示", "ppt": "PowerPoint演示",
                        "txt": "文本文件", "csv": "CSV表格", "json": "JSON文件",
                        "jpg": "图片", "jpeg": "图片", "png": "图片",
                    }.get(ext, "未知类型")

                    prompt = FILE_SUMMARY_PROMPT.format(
                        filename=attachment.filename, file_type=file_type_label, file_content=full_content
                    )
                    try:
                        summary = client.chat(messages=[], system_prompt=prompt, temperature=config.EXTRACTION_TEMP, max_tokens=2048)
                    except Exception as e:
                        logging.error(f"Summary generation failed: {e}")
                        summary = f"摘要生成失败：{str(e)}"

                    # 保存到文档库
                    uploader_name = message.author.display_name
                    doc_entry = doc_store.add(
                        filename=attachment.filename, file_type=file_type_label,
                        content=text, summary=summary,
                        uploader_id=message.author.id, uploader_name=uploader_name,
                    )

                    # 设置为当前讨论文档
                    active_doc_sessions[message.channel.id] = doc_entry.number
                    if message.channel.id in active_sessions:
                        del active_sessions[message.channel.id]
                    if message.channel.id in active_report_sessions:
                        del active_report_sessions[message.channel.id]

                    summary_preview = summary[:1000]
                    embed = discord.Embed(
                        title=f"📄 文档已保存为 #{doc_entry.number}",
                        description=f"**文件名**：{attachment.filename}\n**类型**：{file_type_label}\n\n{summary_preview}\n\n你可以直接提问。用 `/files` 查看所有文档。",
                        color=discord.Color.green()
                    )
                    await message.reply(embed=embed)

                except Exception as e:
                    await message.reply(f"❌ 文件处理失败: {str(e)}")
                    logging.error(f"Error processing attachment: {e}")
                finally:
                    try:
                        os.remove(file_path)
                    except OSError:
                        pass
        return

    # 文档讨论 Q&A
    if message.channel.id in active_doc_sessions and not message.content.startswith("/"):
        doc_number = active_doc_sessions[message.channel.id]
        doc_entry = doc_store.get(doc_number)
        if doc_entry and can_access_doc(doc_entry, message.author.id):
            async with message.channel.typing():
                try:
                    client = get_client()
                    system_prompt = FILE_DISCUSSION_SYSTEM_PROMPT.format(
                        filename=doc_entry.filename, file_type=doc_entry.file_type,
                        file_summary=doc_entry.summary, file_content=doc_entry.content,
                    )
                    messages = [
                        {"role": "user" if i % 2 == 0 else "assistant", "content": msg}
                        for i, msg in enumerate(doc_entry.conversation[-6:])
                    ]
                    messages.append({"role": "user", "content": message.content})

                    def _call_llm():
                        return client.chat(
                            messages=messages, system_prompt=system_prompt,
                            temperature=0.5, max_tokens=2048,
                        )

                    response = await asyncio.to_thread(_call_llm)
                    doc_store.update_conversation(doc_number, message.content, response)
                    await message.reply(f"📄 **文档#{doc_number}助手**：{response}")
                except Exception as e:
                    await message.reply(f"❌ 处理出错: {str(e)}")
            return

    # 面聊报告讨论 Q&A
    if message.channel.id in active_report_sessions and not message.content.startswith("/"):
        report_id = active_report_sessions[message.channel.id]
        report = report_store.load(report_id)
        if report:
            async with message.channel.typing():
                try:
                    client = get_client()

                    # 获取原始面聊内容
                    raw_content = ""
                    entries = knowledge_store.list_by_category("customer_doc")
                    for e in entries:
                        if e.title == report.source_title or e.source_file == report.source_file:
                            raw_content = e.content[:4000]
                            break

                    highlights_text = "\n".join(f"- {h}" for h in report.highlights)
                    improvements_text = "\n".join(f"- {im}" for im in report.improvements)
                    scripts_text = ""
                    for s in report.corrected_scripts:
                        scripts_text += f"原文：{s.get('original', '')}\n改写：{s.get('corrected', '')}\n原因：{s.get('reason', '')}\n\n"
                    next_steps_text = "\n".join(f"- {ns}" for ns in report.next_steps)

                    system_prompt = REPORT_CHAT_SYSTEM_PROMPT.format(
                        sales_name=report.sales_name,
                        source_title=report.source_title,
                        summary=report.summary,
                        highlights=highlights_text,
                        improvements=improvements_text,
                        corrected_scripts=scripts_text,
                        next_steps=next_steps_text,
                        conversation_content=raw_content or "（未找到原始面聊记录）",
                    )

                    messages = list(report.chat_history[-6:])
                    messages.append({"role": "user", "content": message.content})

                    def _call_llm():
                        return client.chat(
                            messages=messages, system_prompt=system_prompt,
                            temperature=0.5, max_tokens=2048,
                        )

                    response = await asyncio.to_thread(_call_llm)

                    # 保存聊天历史
                    report.chat_history.append({"role": "user", "content": message.content})
                    report.chat_history.append({"role": "assistant", "content": response})
                    report_store.save_chat_history(report_id, report.chat_history)

                    await message.reply(f"🏀 **教练**：{response}")
                except Exception as e:
                    await message.reply(f"❌ 处理出错: {str(e)}")
            return

    # 训练对话
    if message.channel.id in active_sessions:
        session_id = active_sessions[message.channel.id]

        async with message.channel.typing():
            try:
                # Run LLM call in thread to avoid blocking event loop
                ai_response, style_note, receptivity, phase = await asyncio.wait_for(
                    asyncio.to_thread(manager.process_user_message, session_id, message.content),
                    timeout=30
                )

                session = manager.get_session(session_id)
                if session and session.mode == "salesperson":
                    role_label = "💼 **销售（AI）**"
                else:
                    role_label = "👤 **客户（AI）**"

                # Combine response + style note into one message
                reply_text = f"{role_label}: {ai_response}"
                if style_note:
                    reply_text += f"\n\n🎭 **风格注解**：{style_note}"
                await message.reply(reply_text)

                # Session ended naturally
                if session and session.status != "active":
                    end_labels = {"成功": "客户有意向，对话成功结束！", "离开": "客户失去耐心离开了", "考虑": "客户表示需要再考虑", "红线": "触犯红线，客户直接离开"}
                    end_text = end_labels.get(session.end_reason, "对话已结束")
                    del active_sessions[message.channel.id]

                    # Generate evaluation report in thread
                    try:
                        evaluator = _get_evaluator()

                        # Full report (includes summary internally)
                        try:
                            full_report = await asyncio.wait_for(
                                asyncio.to_thread(evaluator.evaluate, session_id),
                                timeout=60
                            )
                        except asyncio.TimeoutError:
                            logging.error(f"[on_message] Evaluation timeout for session {session_id[:8]}")
                            full_report = None
                        except Exception:
                            full_report = None

                        # Fallback: summary only
                        summary = full_report.conversation_summary if full_report else None
                        if not summary:
                            try:
                                summary = await asyncio.wait_for(
                                    asyncio.to_thread(evaluator.generate_summary_only, session_id),
                                    timeout=15
                                )
                            except Exception:
                                summary = None

                        turn_count = len(session.conversation) // 2
                        recep_hist = session.receptivity_history
                        recep_text = f"{recep_hist[0]}→{recep_hist[-1]}" if recep_hist and len(recep_hist) >= 2 else "-"

                        desc = f"**对话结束**：{end_text}\n**对话轮次**：{turn_count}轮\n**客户接受度**：{recep_text}\n\n"
                        if summary and len(summary) > 3600:
                            desc += summary[:3600] + "\n..."
                        else:
                            desc += summary or ""

                        embed = discord.Embed(title="📋 训练评估报告", description=desc[:4096], color=discord.Color.gold())

                        if full_report and full_report.deal_progression:
                            dp = full_report.deal_progression
                            dp_text = ""
                            if dp.get("current_stage"):
                                dp_text += f"**当前阶段**：{dp['current_stage']}\n"
                            if dp.get("risk_level"):
                                dp_text += f"**风险等级**：{dp['risk_level']} — {dp.get('risk_reason', '')}\n"
                            if dp.get("next_steps"):
                                dp_text += "\n**下一步**：\n"
                                for step in dp["next_steps"][:3]:
                                    dp_text += f"{step.get('step', '?')}. {step.get('action', '')}\n"
                                    if step.get("script"):
                                        dp_text += f"   话术：{step['script'][:80]}\n"
                            if dp.get("win_strategy"):
                                dp_text += f"\n**赢单策略**：{dp['win_strategy']}"
                            if dp_text:
                                embed.add_field(name="签单路径", value=dp_text[:1024], inline=False)

                        if full_report and full_report.dimension_scores:
                            scores_text = ""
                            for dim, data in full_report.dimension_scores.items():
                                score = data.get("score", 0) if isinstance(data, dict) else data
                                bar = "█" * score + "░" * (10 - score)
                                scores_text += f"{dim}：{bar} {score}/10\n"
                            if scores_text:
                                embed.add_field(name="维度评分", value=scores_text[:1024], inline=False)

                        if full_report:
                            embed.set_footer(text="完整评估报告（含雷达图）请在网页版「评估报告」Tab查看")

                        await message.channel.send(embed=embed)
                    except Exception as e:
                        logging.error(f"Failed to generate evaluation: {e}")
                        await message.channel.send(f"⚠️ 评估报告生成失败：{str(e)[:200]}")

            except asyncio.TimeoutError:
                await message.channel.send("❌ 回复超时，LLM可能暂时不可用，请稍后重试。")
                logging.error(f"LLM call timeout for session {session_id[:8] if session_id else '?'}")
            except Exception as e:
                await message.channel.send(f"❌ 运行出错: {str(e)}")
                logging.error(f"Error processing message: {e}")

    await bot.process_commands(message)


if __name__ == "__main__":
    bot.run(TOKEN)
