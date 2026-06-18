"""用户账号管理模块 — 支持手机号注册、白名单验证。"""
import hashlib
import json
import os
import uuid
from datetime import datetime

import config


def _hash_password(password: str) -> str:
    """SHA-256 加盐哈希密码。"""
    salt = "sales_master_2026"
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()


class UserStore:
    def __init__(self):
        self.users_file = os.path.join(config.DATA_DIR, "users.json")
        self.phones_file = os.path.join(config.DATA_DIR, "allowed_phones.json")
        self._ensure_default()

    def _ensure_default(self):
        """首次运行时创建默认管理员和白名单文件。"""
        if not os.path.exists(self.users_file):
            default_users = [{
                "id": str(uuid.uuid4()),
                "username": "admin",
                "display_name": "管理员",
                "phone": "",
                "password_hash": _hash_password("admin123"),
                "role": "admin",
                "created_at": datetime.now().isoformat(),
            }]
            with open(self.users_file, "w", encoding="utf-8") as f:
                json.dump(default_users, f, ensure_ascii=False, indent=2)

        if not os.path.exists(self.phones_file):
            # 默认示例白名单
            default_phones = [
                {"phone": "13800000001", "name": "免免", "added_at": datetime.now().isoformat()},
                {"phone": "13800000002", "name": "CC", "added_at": datetime.now().isoformat()},
                {"phone": "13800000003", "name": "茉莉", "added_at": datetime.now().isoformat()},
                {"phone": "13800000004", "name": "丸子", "added_at": datetime.now().isoformat()},
            ]
            with open(self.phones_file, "w", encoding="utf-8") as f:
                json.dump(default_phones, f, ensure_ascii=False, indent=2)

    def _load_users(self) -> list[dict]:
        if not os.path.exists(self.users_file):
            return []
        with open(self.users_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_users(self, users: list[dict]):
        with open(self.users_file, "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=2)

    def _load_allowed_phones(self) -> list[dict]:
        if not os.path.exists(self.phones_file):
            return []
        with open(self.phones_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_allowed_phones(self, phones: list[dict]):
        with open(self.phones_file, "w", encoding="utf-8") as f:
            json.dump(phones, f, ensure_ascii=False, indent=2)

    def is_phone_allowed(self, phone: str) -> bool:
        """检查手机号是否在白名单中。"""
        phones = self._load_allowed_phones()
        return any(p["phone"] == phone for p in phones)

    def get_phone_name(self, phone: str) -> str:
        """获取白名单中手机号对应的姓名。"""
        phones = self._load_allowed_phones()
        match = next((p for p in phones if p["phone"] == phone), None)
        return match["name"] if match else ""

    def authenticate(self, username: str, password: str) -> bool:
        """验证登录（username 可以是账号或手机号）。"""
        users = self._load_users()
        pwd_hash = _hash_password(password)
        return any(
            (u["username"] == username or u.get("phone") == username) and u["password_hash"] == pwd_hash
            for u in users
        )

    def get_user(self, username: str) -> dict | None:
        """获取用户信息（支持账号或手机号查询）。"""
        users = self._load_users()
        return next((u for u in users if u["username"] == username or u.get("phone") == username), None)

    def get_display_name(self, username: str) -> str:
        user = self.get_user(username)
        return user["display_name"] if user else username

    def list_sales(self) -> list[dict]:
        return [u for u in self._load_users() if u["role"] == "sales"]

    def list_all(self) -> list[dict]:
        return self._load_users()

    def list_allowed_phones(self) -> list[dict]:
        return self._load_allowed_phones()

    def register(self, phone: str, display_name: str, password: str) -> tuple[bool, str]:
        """用手机号注册。必须白名单内的手机号才能注册。"""
        if not phone or not password:
            return False, "手机号和密码不能为空"
        if len(phone) != 11 or not phone.isdigit():
            return False, "请输入正确的11位手机号"
        if len(password) < 4:
            return False, "密码至少4位"

        # 检查白名单
        if not self.is_phone_allowed(phone):
            return False, "该手机号未在授权名单中，请联系管理员添加"

        # 检查是否已注册
        users = self._load_users()
        if any(u.get("phone") == phone for u in users):
            return False, "该手机号已注册，请直接登录"

        # 用手机号作为登录账号
        username = phone
        if not display_name:
            display_name = self.get_phone_name(phone) or phone

        new_user = {
            "id": str(uuid.uuid4()),
            "username": username,
            "display_name": display_name,
            "phone": phone,
            "password_hash": _hash_password(password),
            "role": "sales",
            "created_at": datetime.now().isoformat(),
        }
        users.append(new_user)
        self._save_users(users)
        return True, f"注册成功！欢迎 {display_name}"

    def add_allowed_phone(self, phone: str, name: str) -> tuple[bool, str]:
        """管理员添加手机号到白名单。"""
        if len(phone) != 11 or not phone.isdigit():
            return False, "请输入正确的11位手机号"
        phones = self._load_allowed_phones()
        if any(p["phone"] == phone for p in phones):
            return False, f"手机号 {phone} 已在白名单中"
        phones.append({"phone": phone, "name": name or phone, "added_at": datetime.now().isoformat()})
        self._save_allowed_phones(phones)
        return True, f"已添加 {name or phone}（{phone}）到授权名单"

    def remove_allowed_phone(self, phone: str) -> tuple[bool, str]:
        """从白名单移除手机号。"""
        phones = self._load_allowed_phones()
        original = len(phones)
        phones = [p for p in phones if p["phone"] != phone]
        if len(phones) == original:
            return False, f"手机号 {phone} 不在白名单中"
        self._save_allowed_phones(phones)
        return True, f"已从授权名单移除 {phone}"

    def change_password(self, username: str, old_password: str, new_password: str) -> tuple[bool, str]:
        if not self.authenticate(username, old_password):
            return False, "原密码错误"
        if len(new_password) < 4:
            return False, "新密码至少4位"
        users = self._load_users()
        for u in users:
            if u["username"] == username or u.get("phone") == username:
                u["password_hash"] = _hash_password(new_password)
                break
        self._save_users(users)
        return True, "密码修改成功"

    def reset_password(self, username: str, new_password: str) -> tuple[bool, str]:
        if len(new_password) < 4:
            return False, "新密码至少4位"
        users = self._load_users()
        found = False
        for u in users:
            if u["username"] == username or u.get("phone") == username:
                u["password_hash"] = _hash_password(new_password)
                found = True
                break
        if not found:
            return False, "用户不存在"
        self._save_users(users)
        return True, f"密码已重置"

    def delete_user(self, username: str) -> tuple[bool, str]:
        if username == "admin":
            return False, "不能删除管理员账号"
        users = self._load_users()
        original = len(users)
        users = [u for u in users if u["username"] != username and u.get("phone") != username]
        if len(users) == original:
            return False, f"用户不存在"
        self._save_users(users)
        return True, f"用户已删除"
