import os
import discord
import logging
import config
from discord.ext import commands
from dotenv import load_dotenv
from core.training_manager import TrainingManager
from core.file_discussion_manager import FileDiscussionManager
from prompts.customer_simulation import WEDDING_SCENARIOS
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

load_dotenv()

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
            synced = await bot.tree.sync(guild=guild)
            logging.info(f"Synced {len(synced)} slash commands to guild: {guild.name}")
    except Exception as e:
        logging.error(f"Failed to sync slash commands: {e}")
    if TARGET_CHANNEL_ID:
        channel = bot.get_channel(int(TARGET_CHANNEL_ID))
        if channel:
            await channel.send("✅ 销售大师 Bot 已上线！输入 `/` 查看所有命令。")


# === 斜杠命令 ===

@bot.tree.command(name="start", description="开始销售训练（AI当客户，你练销售）")
@discord.app_commands.describe(style="选择销售风格（可选）", doc="文档编号，基于文档内容训练（可选）")
async def slash_start(interaction: discord.Interaction, style: str = None, doc: int = None):
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
                await interaction.response.send_message(f"❌ 未找到风格「{style}」。暂无风格，用 `/start` 使用默认。")
            return

    scenario = WEDDING_SCENARIOS["酒店婚宴"]
    scenario["product"] = "婚礼策划服务"
    scenario["industry"] = "婚庆"

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
        style_profile_id=style_profile_id,
    )
    active_sessions[interaction.channel_id] = session.id

    embed = discord.Embed(
        title="🚀 销售实战训练开始！",
        description=f"**场景**：{scenario['wedding_type']}\n**客户设定**：{scenario['core_needs']}\n**销售风格**：{style_display}{doc_info}\n\nAI 扮演客户，请开始你的销售话术！",
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed)
    await interaction.channel.send("👤 **客户（AI）**: 您好，我想咨询一下婚礼策划...")


@bot.tree.command(name="learn", description="学习模式（AI当销售，你当客户）")
@discord.app_commands.describe(style="选择销售风格（可选）")
async def slash_learn(interaction: discord.Interaction, style: str = None):
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

    scenario = WEDDING_SCENARIOS["酒店婚宴"]
    scenario["product"] = "婚礼策划服务"
    scenario["industry"] = "婚庆"
    scenario["customer_description"] = "正在筹备婚礼的备婚新人"

    session = manager.create_session(
        mode="salesperson",
        scenario=scenario,
        style_profile_id=style_profile_id,
    )
    active_sessions[interaction.channel_id] = session.id

    embed = discord.Embed(
        title="📚 学习模式开始！",
        description=f"**场景**：{scenario['wedding_type']}\n**销售风格**：{style_display}\n\nAI 扮演销售，你扮演客户。先说一句话作为客户开场吧！",
        color=discord.Color.purple()
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="stop", description="结束当前训练")
async def slash_stop(interaction: discord.Interaction):
    if not is_allowed_user(interaction.user.id):
        await interaction.response.send_message("❌ 你没有使用权限。", ephemeral=True)
        return

    stopped = False
    if interaction.channel_id in active_sessions:
        del active_sessions[interaction.channel_id]
        stopped = True
    if interaction.channel_id in active_doc_sessions:
        del active_doc_sessions[interaction.channel_id]
        stopped = True
    if interaction.channel_id in active_report_sessions:
        del active_report_sessions[interaction.channel_id]
        stopped = True
    if file_manager.has_session(interaction.channel_id):
        file_manager.end_session(interaction.channel_id)
        stopped = True

    if stopped:
        await interaction.response.send_message("✅ 已结束。用 `/start` 或 `/learn` 开启新一轮。")
    else:
        await interaction.response.send_message("❌ 当前没有进行中的会话。")


@bot.tree.command(name="styles", description="查看可选的销售风格")
async def slash_styles(interaction: discord.Interaction):
    if not is_allowed_user(interaction.user.id):
        await interaction.response.send_message("❌ 你没有使用权限。", ephemeral=True)
        return

    styles = get_style_choices()
    if styles:
        style_list = "\n".join(f"• {s}" for s in styles)
        await interaction.response.send_message(f"🎭 **可选销售风格**：\n{style_list}\n\n用 `/start style:风格名` 指定风格")
    else:
        await interaction.response.send_message("暂无销售风格。可在网页版「风格管理」中提取。")


@bot.tree.command(name="files", description="查看你上传过的文档列表")
async def slash_files(interaction: discord.Interaction):
    if not is_allowed_user(interaction.user.id):
        await interaction.response.send_message("❌ 你没有使用权限。", ephemeral=True)
        return

    docs = doc_store.list_by_user(interaction.user.id, is_admin=is_admin(interaction.user.id))
    if not docs:
        await interaction.response.send_message("📭 暂无文档。直接发送文件附件即可上传。")
        return

    lines = ["📑 **文档列表**：\n"]
    for d in docs:
        owner = "" if is_admin(interaction.user.id) else ""
        if is_admin(interaction.user.id):
            owner = f" | 上传者：{d.uploader_name or d.uploader_id}" if d.uploader_id != str(interaction.user.id) else ""
        lines.append(f"**#{d.number}** {d.filename} ({d.file_type}){owner} — {d.created_at[:10]}")

    lines.append("\n`/doc 编号` 查看讨论 | `/start doc:编号` 基于文档训练 | `/del 编号` 删除")
    await interaction.response.send_message("\n".join(lines))


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


@bot.tree.command(name="help", description="查看所有命令")
async def slash_help(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📖 销售大师 命令列表",
        description=(
            "**训练**\n"
            "/start — 销售训练（AI当客户）\n"
            "/start style:风格 doc:编号 — 指定风格/文档\n"
            "/learn — 学习模式（AI当销售）\n"
            "/stop — 结束当前会话\n\n"
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
            "/styles — 查看可选风格"
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
                        for i, msg in enumerate(doc_entry.conversation[-6:])  # 最近3轮
                    ]
                    messages.append({"role": "user", "content": message.content})

                    response = client.chat(
                        messages=messages, system_prompt=system_prompt,
                        temperature=0.5, max_tokens=2048,
                    )
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

                    messages = list(report.chat_history[-6:])  # 最近3轮
                    messages.append({"role": "user", "content": message.content})

                    response = client.chat(
                        messages=messages, system_prompt=system_prompt,
                        temperature=0.5, max_tokens=2048,
                    )

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
                ai_response, style_note, receptivity, phase = manager.process_user_message(
                    session_id, message.content
                )

                await message.reply(f"👤 **客户（AI）**: {ai_response}")

                if style_note:
                    await message.channel.send(f"🎭 **风格注解**：{style_note}")

                if receptivity <= 0:
                    await message.channel.send("⚠️ **客户已离开**：看来你的沟通方式让客户失去了兴趣。训练结束。")
                    del active_sessions[message.channel_id]

            except Exception as e:
                await message.channel.send(f"❌ 运行出错: {str(e)}")
                logging.error(f"Error processing message: {e}")


if __name__ == "__main__":
    bot.run(TOKEN)
