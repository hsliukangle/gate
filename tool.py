import requests
import os
import base64
from Crypto.Cipher import AES
from datetime import datetime
import json

# 简单的内存缓存
_session_cache = {}


def get_openid(code):

    try:

        appid = os.getenv("APPID")
        secret = os.getenv("SECRET")
        url = f"https://api.weixin.qq.com/sns/jscode2session?appid={appid}&secret={secret}&js_code={code}&grant_type=authorization_code"
        response = requests.get(url)
        data = response.json()

        openid = data.get("openid", None)
        session_key = data.get("session_key", None)
        if not openid or not session_key:
            return response.json({"error": "Failed to get parameter"}, status=500)

        _session_cache[openid] = session_key

        return openid

    except Exception as e:
        print(f"解密失败: {e}")
        return None


def decrypt_data_get_phone(session_key, encrypted_data, iv):
    try:
        # 解码
        session_key = base64.b64decode(session_key)
        encrypted_data = base64.b64decode(encrypted_data)
        iv = base64.b64decode(iv)

        # AES解密
        cipher = AES.new(session_key, AES.MODE_CBC, iv)
        decrypted = cipher.decrypt(encrypted_data)

        # 去除PKCS7填充
        unpad = lambda s: s[: -ord(s[len(s) - 1 :])]
        decrypted_data = unpad(decrypted)

        # 转换为JSON字符串并返回
        json_data = json.loads(decrypted_data.decode("utf-8"))

        return json_data.get("phoneNumber")
    except Exception as e:
        print(f"解密失败: {e}")
        return None


def decodeBase64(value):
    value = value.replace(" ", "+")
    value = value.replace("-", "+").replace("_", "/")
    ln = (len(value) % 4) & 0xFF
    if ln == 2:
        value += "=="
    if ln == 3:
        value += "="
    value = base64.b64decode(value)
    return value

def getNowTime():
        # 获取当前时间
        now = datetime.now()
        return now.strftime("%Y-%m-%d %H:%M:%S")
