import os
from dotenv import load_dotenv
from wechatpayv3 import WeChatPay, WeChatPayType
from loguru import logger
import json
import time
import random
import string

# 加载环境变量
load_dotenv()


class wxpayService:
    """
    微信支付服务封装类
    文档参考：
    - 支付: https://pay.weixin.qq.com/wiki/doc/apiv3/apis/chapter3_5_1.shtml
    """

    # 初始化微信支付
    def __init__(self):
        self.wxpay = WeChatPay(
            appid=os.getenv("APPID"),
            mchid=os.getenv("MCHID"),
            private_key=self._read_key_file("cert/apiclient_key.pem"),
            cert_dir="cert",
            wechatpay_type=WeChatPayType.MINIPROG,
            cert_serial_no=os.getenv("CERT_SERIAL_NO"),
            apiv3_key=os.getenv("API_V3_KEY"),
        )

    # 支付
    def prepay(self, order, openid, money):
        out_trade_no = str(order.order_no)
        try:
            http_code, http_result = self.wxpay.pay(
                description="门禁系统充值",
                out_trade_no=out_trade_no,
                amount={"total": int(money), "currency": "CNY"},
                payer={"openid": openid},
                notify_url=os.getenv("API_URL") + "/pay_notify",  # 支付结果通知地址
            )
        except Exception as e:
            info = f"支付下单异常, openid: {openid}, money: {money}, error: {e}"
            logger.error(info)
            raise Exception(info)

        if http_code != 200:
            info = f"状态码异常, http_code: {http_code}, pay_result: {http_result}"
            logger.error(info)
            raise Exception(info)

        pay_result = json.loads(http_result)

        if "prepay_id" not in pay_result:
            info = f"prepay_id不存在, pay_result: {pay_result}"
            logger.error(info)
            raise Exception(info)

        # 生成小程序支付参数
        payment_params = self._generate_payment_params(pay_result["prepay_id"])
        payment_params["out_trade_no"] = out_trade_no
        payment_params["prepay_id"] = pay_result["prepay_id"]

        return payment_params

    def verify_notify_sign(self, headers, body):
        """验证支付通知签名"""
        return self.wxpay.callback(headers, body)

    def _generate_payment_params(self, prepay_id):
        """生成小程序支付参数"""

        # 生成时间戳
        timestamp = str(int(time.time()))

        # 生成随机字符串
        nonce_str = "".join(random.choices(string.ascii_letters + string.digits, k=32))

        # 生成package
        package = f"prepay_id={prepay_id}"

        # 生成签名
        sign_str = [self.wxpay._appid, timestamp, nonce_str, package]
        signature = self.wxpay.sign(sign_str)

        return {
            "appId": self.wxpay._appid,
            "timeStamp": timestamp,
            "nonceStr": nonce_str,
            "package": package,
            "signType": "RSA",
            "paySign": signature,
        }

    def _read_key_file(self, file_path: str) -> str:
        """安全读取密钥文件"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"密钥文件不存在: {file_path}")
        with open(file_path, "r") as f:
            return f.read()
