from tool import decodeBase64
from sanic import Sanic, response
from sanic.request import Request
from dotenv import load_dotenv
from tortoise import Tortoise
from models import User, EnterLog, Device, Order
from config import DB_CONFIG
from sanic.exceptions import BadRequest
from loguru import logger
from service.wechatService import weChatPay, weChatTool

# 加载.env文件
load_dotenv()

# 设置日志配置
logger.add("gate.log")

# 初始化Sanic应用
app = Sanic(__name__)


# 为L2DuZBtxbl.txt文件创建专门的路由
@app.route("/L2DuZBtxbl.txt")
async def serve_specific_file(request):
    file_path = "./L2DuZBtxbl.txt"
    try:
        with open(file_path, "r") as f:
            content = f.read()
        return response.text(content)
    except Exception as e:
        logger.error(f"无法读取文件: {e}")
        return response.text("文件不存在", status=404)


# 初始化数据库
@app.listener("before_server_start")
async def init_db(app, loop):
    await Tortoise.init(config=DB_CONFIG)
    # 生成数据表（如果不存在）
    # await Tortoise.generate_schemas()


@app.listener("after_server_stop")
async def close_db(app, loop):
    await Tortoise.close_connections()


@app.exception(BadRequest)
async def handle_bad_request(request, exception):
    return response.json({"code": 400, "msg": str(exception)}, status=400)


@app.route("/")
async def index(request: Request):
    return response.text("ok!")


"""
--------------------------------------------------------小程序接口
"""


# 获取openid
@app.route("/openid")
async def openid(request: Request):

    code = request.args.get("code")
    if not code:
        raise BadRequest("缺少参数")

    try:
        openid = weChatTool().get_openid(code)
        return response.json({"openid": openid})
    except Exception as e:
        logger.error(f"获取openid失败: {e}")
        raise BadRequest("获取openid失败")


# 注册&登录
@app.route("/login", methods=["POST"])
async def login(request: Request):

    openid = request.json.get("openid")
    avatar = request.json.get("avatar")
    nickName = request.json.get("nickName")
    encryptedData = request.json.get("encryptedData")
    iv = request.json.get("iv")
    if not openid or not avatar or not nickName or not encryptedData or not iv:
        raise BadRequest("缺少参数: openid, avatar, nickName, encryptedData, iv")

    try:
        session_key = weChatTool().session_cache.get(openid)
        if not session_key:
            raise BadRequest("未获取到session_key")

        phone = weChatTool().decrypt_data_get_phone(session_key, encryptedData, iv)
        user = await User.get_or_create_user(
            openid=openid, nickname=nickName, avatar=avatar, phone=phone
        )
        return response.json(
            {
                "id": user.id,
                "openid": user.openid,
                "nickname": user.nickname,
                "avatar": user.avatar,
            }
        )
    except Exception as e:
        logger.error(f"登录失败: {e}")
        raise BadRequest("登录失败")


# 用户查看二维码
@app.route("/qrcode")
async def qrcode(request: Request):

    user_id = request.args.get("user_id")
    order_id = request.args.get("order_id")
    if not user_id:
        raise BadRequest("缺少参数")

    enter_log = await EnterLog.get_enter_log(user_id, order_id)

    # 返回记录信息
    return response.json(
        {
            "qrcode": enter_log.qrcode,
            "enter_at": enter_log.enter_at.isoformat() if enter_log.enter_at else None,
            "leave_at": enter_log.leave_at.isoformat() if enter_log.leave_at else None,
        }
    )


# 教练查看二维码
@app.route("/coach_qrcode")
async def coach_qrcode(request: Request):

    user_id = request.args.get("user_id")
    if not user_id:
        raise BadRequest("缺少参数")

    order = await Order.get_user_last_order(user_id)
    if not order:
        raise BadRequest("教练无关联订单")

    enter_log = await EnterLog.get_enter_log(user_id, order.id)
    if not enter_log:
        raise BadRequest("教练无入闸二维码")

    return response.json({"order_id": order.id, "qrcode": enter_log.qrcode})


# 预支付下单
@app.route("/pay")
async def pay(request: Request):

    user_id = request.args.get("user_id")
    if not user_id:
        raise BadRequest("缺少参数")

    try:
        # 金额
        money = 0.01
        # 创建订单
        order, user = await Order.create_order(user_id, money)
        # 预支付
        pay_res = weChatPay().prepay(order, user.openid)
        return response.json(pay_res)
    except Exception as e:
        logger.error(f"支付异常请稍后重试, error: {e}")
        # 更新订单为失败
        await Order.update_order_pay_fail(order.order_no, str(e))
        raise BadRequest(f"支付异常请稍后重试")


# 支付结果通知
@app.route("/pay_notify", methods=["POST"])
async def pay_notify(request: Request):

    try:
        # 验证通知签名
        verify_res = weChatPay().verify_notify_sign(request.headers, request.body)
        if verify_res is None:
            raise Exception("支付通知签名验证失败")

        resource = verify_res.get("resource", {})
        out_trade_no = resource.get("out_trade_no")
        transaction_id = resource.get("transaction_id")
        trade_state = resource.get("trade_state")
        payer = resource.get("payer")
        openid = payer.get("openid")

        # 根据交易状态处理订单
        if trade_state != "SUCCESS":
            raise Exception(f"支付通知状态非正常 {str(resource)}")

        # 更新订单为已支付
        order = await Order.update_order_paid(out_trade_no, transaction_id)
        if not order:
            raise Exception(f"订单不存在 {out_trade_no}")

        # 创建入闸机二维码
        await EnterLog.get_enter_log(openid, order.id)

        return response.json({"code": 200, "msg": "success"})

    except Exception as e:
        logger.error(f"回调异常, error: {e}")
        raise BadRequest(f"回调异常")


"""
--------------------------------------------------------闸机设备接口
"""


# 闸机心跳
@app.route("/getStatus")
async def get_status(request: Request):

    try:
        key = request.args.get("Key")
        Serial = request.args.get("Serial")
        if not key or not Serial:
            raise BadRequest("缺少参数: Key, Serial")

        # 更新或创建设备并更新活跃状态
        await Device.update_or_create_device(Serial)

    except Exception as e:
        logger.info(f"闸机心跳,error: {e}")

    return response.json({"Key": key})


# 闸机请求
@app.route("/searchCardAcs")
async def search_card_acs(request: Request):

    try:
        type = int(request.args.get("type"))
        Reader = int(request.args.get("Reader"))
        Card = request.args.get("Card")
        Serial = request.args.get("Serial")

        # 处理Base64编码的二维码
        if int(type) != 9:
            raise BadRequest("类型必须为二维码")

        # base64解码
        Card = decodeBase64(Card).decode("utf-8")

        # 更新或创建设备并更新活跃状态
        await Device.update_or_create_device(Serial)

        # 维护进入记录
        if Reader == 0:
            await EnterLog.update_enter_log(Card, Serial)
        # 维护退出记录
        elif Reader == 1:
            await EnterLog.update_leave_log(Card, Serial)
        # 如果是其他类型，抛出错误
        else:
            raise BadRequest("Reader类型错误")

        ActIndex = Reader
        AcsRes = "1"
        Time = "1"

    except Exception as e:
        logger.info(f"闸机请求,error: {e}")
        ActIndex = 0
        AcsRes = "0"
        Time = "0"

    return response.json({"ActIndex": ActIndex, "AcsRes": AcsRes, "Time": Time})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
