"""密码加密工具"""

import hashlib
from app.config import settings


# TODO: 优先级3，生产1，使用更安全的加密算法，MD5 已不再安全

def encrypt_password(password: str) -> str:
    """
    加密密码（MD5 + 盐值）
    MD5(password + salt)
    """
    salted_password = password + settings.password_salt
    return hashlib.md5(salted_password.encode()).hexdigest()


def verify_password(plain_password: str, encrypted_password: str) -> bool:
    """验证密码"""
    return encrypt_password(plain_password) == encrypted_password
