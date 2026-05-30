import socket

import gradio as gr

import config
from storage.user_store import UserStore


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def build_login_ui():
    """构建登录/注册UI，返回所有组件供 layout 绑定事件。"""
    user_store = UserStore()

    login_phone = gr.Textbox(label="手机号", placeholder="输入注册时使用的手机号")
    login_password = gr.Textbox(label="密码", placeholder="输入密码", type="password")
    login_btn = gr.Button("登录", variant="primary", size="lg")
    login_msg = gr.Markdown("", visible=False)

    gr.Markdown("---")

    with gr.Accordion("注册新账号", open=False):
        gr.Markdown("**仅限已授权的手机号才能注册**，未授权请联系管理员")
        reg_phone = gr.Textbox(label="手机号", placeholder="输入你的手机号")
        reg_display = gr.Textbox(label="你的名字", placeholder="如: 小张")
        reg_password = gr.Textbox(label="设置密码", placeholder="至少4位", type="password")
        reg_password2 = gr.Textbox(label="确认密码", placeholder="再输入一次", type="password")
        reg_btn = gr.Button("注册并登录", variant="primary")
        reg_msg = gr.Markdown("", visible=False)

    logged_in_user = gr.State(None)

    def do_login(phone, password):
        if not phone or not password:
            return (None, gr.update(visible=True, value="**请输入手机号和密码**"),
                    gr.update(visible=False), gr.update(visible=True), "", gr.update(choices=[]))
        if user_store.authenticate(phone, password):
            user = user_store.get_user(phone)
            display = user["display_name"]
            role_label = "管理员" if user["role"] == "admin" else "销售"
            sales_names = [u["display_name"] for u in user_store.list_sales()]
            return (
                user["username"],
                gr.update(visible=False),
                gr.update(visible=True),
                gr.update(visible=False),
                f"**欢迎，{display}！** 角色：{role_label}",
                gr.update(choices=sales_names, value=display if user["role"] == "sales" else None),
            )
        return (None, gr.update(visible=True, value="**手机号或密码错误**"),
                gr.update(visible=False), gr.update(visible=True), "", gr.update(choices=[]))

    def do_register(phone, display_name, password, password2):
        if not phone or not password:
            return (None, gr.update(visible=True, value="**请填写手机号和密码**"),
                    gr.update(visible=False), gr.update(visible=True), "", gr.update(choices=[]))
        if password != password2:
            return (None, gr.update(visible=True, value="**两次输入的密码不一致**"),
                    gr.update(visible=False), gr.update(visible=True), "", gr.update(choices=[]))
        ok, msg = user_store.register(phone, display_name, password)
        if not ok:
            return (None, gr.update(visible=True, value=f"**{msg}**"),
                    gr.update(visible=False), gr.update(visible=True), "", gr.update(choices=[]))
        user = user_store.get_user(phone)
        display = user["display_name"]
        sales_names = [u["display_name"] for u in user_store.list_sales()]
        return (
            user["username"],
            gr.update(visible=False),
            gr.update(visible=True),
            gr.update(visible=False),
            f"**欢迎，{display}！** 注册成功",
            gr.update(choices=sales_names, value=display),
        )

    components = {
        "login_phone": login_phone,
        "login_password": login_password,
        "login_btn": login_btn,
        "login_msg": login_msg,
        "reg_phone": reg_phone,
        "reg_display": reg_display,
        "reg_password": reg_password,
        "reg_password2": reg_password2,
        "reg_btn": reg_btn,
        "reg_msg": reg_msg,
        "logged_in_user": logged_in_user,
        "do_login": do_login,
        "do_register": do_register,
    }
    return components


def build_main_header():
    """构建主应用头部。返回组件字典。"""
    user_store = UserStore()
    sales_names = [u["display_name"] for u in user_store.list_sales()]

    welcome_md = gr.Markdown("")

    gr.Markdown(
        """
# AI SALES MASTER - 销售实战训练大师
模拟真实客户与销售对练 | 4种销售风格学习 | 专业维度评估与改进建议
"""
    )

    with gr.Row():
        user_dropdown = gr.Dropdown(
            choices=sales_names,
            label="当前销售",
            scale=2,
            allow_custom_value=True,
        )

    return {"user_dropdown": user_dropdown, "welcome_md": welcome_md}


def create_admin_tab():
    """管理面板作为独立 Tab。"""
    user_store = UserStore()

    with gr.Row():
        with gr.Column():
            gr.Markdown("### 添加手机号授权")
            gr.Markdown("只有被授权的手机号才能注册。")
            add_phone = gr.Textbox(label="手机号", placeholder="11位手机号")
            add_name = gr.Textbox(label="姓名", placeholder="如: 小张")
            add_phone_btn = gr.Button("添加授权", variant="primary")
            add_phone_result = gr.Markdown("")

        with gr.Column():
            gr.Markdown("### 移除手机号")
            remove_phone = gr.Textbox(label="手机号", placeholder="输入要移除的手机号")
            remove_phone_btn = gr.Button("移除")
            remove_phone_result = gr.Markdown("")

    gr.Markdown("### 已授权手机号")
    phones_display = gr.Dataframe(
        value=_refresh_phones_table(user_store),
        headers=["手机号", "姓名", "添加时间"],
        interactive=False,
    )

    gr.Markdown("---")
    gr.Markdown("### 已注册账号")
    users_display = gr.Dataframe(
        value=_refresh_users_table(user_store),
        headers=["账号", "姓名", "手机号", "角色", "注册时间"],
        interactive=False,
    )

    with gr.Row():
        reset_user = gr.Textbox(label="重置密码-手机号", placeholder="输入手机号", scale=2)
        reset_pwd = gr.Textbox(label="新密码", placeholder="至少4位", scale=2)
        reset_btn = gr.Button("重置密码", scale=1)
    reset_result = gr.Markdown("")

    gr.Markdown("---")
    gr.Markdown("### 修改密码")
    with gr.Row():
        change_old = gr.Textbox(label="原密码", type="password", scale=2)
        change_new = gr.Textbox(label="新密码", placeholder="至少4位", type="password", scale=2)
        change_btn = gr.Button("修改密码", scale=1)
    change_result = gr.Markdown("")

    def _do_add_phone(phone, name):
        ok, msg = user_store.add_allowed_phone(phone, name)
        return msg, _refresh_phones_table(user_store)

    def _do_remove_phone(phone):
        ok, msg = user_store.remove_allowed_phone(phone)
        return msg, _refresh_phones_table(user_store)

    def _do_reset(username, new_pwd):
        if not username or not new_pwd:
            return "请输入手机号和新密码"
        ok, msg = user_store.reset_password(username, new_pwd)
        return msg

    def _do_change_pwd(old_pwd, new_pwd):
        if not old_pwd or not new_pwd:
            return "请输入原密码和新密码"
        if len(new_pwd) < 4:
            return "新密码至少4位"
        ok, msg = user_store.change_password("admin", old_pwd, new_pwd)
        return msg

    add_phone_btn.click(fn=_do_add_phone, inputs=[add_phone, add_name],
                        outputs=[add_phone_result, phones_display])
    remove_phone_btn.click(fn=_do_remove_phone, inputs=[remove_phone],
                           outputs=[remove_phone_result, phones_display])
    reset_btn.click(fn=_do_reset, inputs=[reset_user, reset_pwd], outputs=[reset_result])
    change_btn.click(fn=_do_change_pwd, inputs=[change_old, change_new], outputs=[change_result])


def _refresh_phones_table(user_store=None):
    if user_store is None:
        user_store = UserStore()
    phones = user_store.list_allowed_phones()
    return [[p["phone"], p["name"], p.get("added_at", "")[:10]] for p in phones]


def _refresh_users_table(user_store=None):
    if user_store is None:
        user_store = UserStore()
    users = user_store.list_all()
    rows = []
    for u in users:
        rows.append([u["username"], u["display_name"], u.get("phone", ""),
                    "管理员" if u["role"] == "admin" else "销售",
                    u.get("created_at", "")[:10]])
    return rows


def create_footer() -> gr.Markdown:
    return gr.Markdown(
        """
---
AI SALES MASTER | Powered by Claude API | 销售实战训练平台
"""
    )
