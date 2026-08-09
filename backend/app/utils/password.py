"""密码加密工具"""

import hashlib

import bcrypt

from app.config import settings


def _sha256_prehash(password: str) -> bytes:
    """对密码做 SHA-256 预哈希，返回十六进制摘要的 ASCII 字节。

    背景：bcrypt 只取密码前 72 字节，直接对任意长度密码加密会截断；
    先做 SHA-256 预哈希即可支持任意长度密码，同时统一字节编码。
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest().encode("ascii")


def encrypt_password(password: str) -> str:
    """加密密码：bcrypt(sha256(password))，自带随机盐。

    Returns:
        bcrypt 密文（$2b$ 前缀，ASCII 字符串）。
    """
    hashed = bcrypt.hashpw(_sha256_prehash(password), bcrypt.gensalt(rounds=settings.bcrypt_rounds))
    return hashed.decode("ascii")


def verify_password(plain_password: str, encrypted_password: str) -> bool:
    """验证密码（bcrypt(sha256(password))）。

    Args:
        plain_password: 用户输入的明文密码。
        encrypted_password: 数据库中存储的 bcrypt 密文。

    Returns:
        密码匹配返回 True，否则 False（密文格式非法也返回 False）。
    """
    try:
        return bcrypt.checkpw(_sha256_prehash(plain_password), encrypted_password.encode("ascii"))
    except ValueError:
        return False
