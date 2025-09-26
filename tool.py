import base64
from datetime import datetime

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
