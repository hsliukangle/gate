import tool
from sanic import Sanic, response
from sanic.request import Request
from dotenv import load_dotenv
from tortoise import Tortoise
from models import User, EnterLog, Device, Order
from config import DB_CONFIG
from sanic.exceptions import NotFound, BadRequest
from loguru import logger
from service.wxpayService import wxpayService

# 加载.env文件
load_dotenv()

# 设置日志配置
logger.add("gate.log")

# 初始化Sanic应用
app = Sanic(__name__)


# 初始化数据库
@app.listener("before_server_start")
async def init_db(app, loop):
    await Tortoise.init(config=DB_CONFIG)
    # 生成数据表（如果不存在）
    # await Tortoise.generate_schemas()


@app.listener("after_server_stop")
async def close_db(app, loop):
    await Tortoise.close_connections()


@app.exception(NotFound)
async def handle_not_found(request, exception):
    return response.json({"code": 404, "msg": str(exception)}, status=404)


@app.exception(BadRequest)
async def handle_bad_request(request, exception):
    return response.json({"code": 400, "msg": str(exception)}, status=400)


@app.route("/")
async def index(request: Request):
    return response.text("ok!")


"""
--------------------------------------------------------小程序接口
"""


@app.route("/open_id")
async def open_id(request: Request):
    code = request.args.get("code")
    if not code:
        raise BadRequest("缺少参数: code")
    openid = tool.get_openid(code)

    logger.info(f"open_id -> code: {code}, openid: {openid}")

    return response.json({"openid": openid})


@app.route("/login", methods=["POST"])
async def login(request: Request):
    openid = request.json.get("openid")
    avatar = request.json.get("avatar")
    nickName = request.json.get("nickName")
    encryptedData = request.json.get("encryptedData")
    iv = request.json.get("iv")

    if not openid or not avatar or not nickName or not encryptedData or not iv:
        raise BadRequest("缺少参数: openid, avatar, nickName, encryptedData, iv")

    # 获取session_key并解密数据
    session_key = tool._session_cache.get(openid)
    if not session_key:
        raise BadRequest("未能正常解密session_key")

    phone = tool.decrypt_data_get_phone(session_key, encryptedData, iv)
    print(f"解密得到的手机号: {phone}")

    # 检查用户是否存在，不存在则创建
    user = await User.get_or_create_user(
        openid=openid, nickname=nickName, avatar=avatar, phone=phone
    )

    return response.json(
        {
            "id": user.id,
            "openid": user.openid,
            "nickname": user.nickname,
            "avatar": user.avatar,
            "phone": user.phone,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }
    )


@app.route("/qrcode")
async def qrcode(request: Request):
    openid = request.args.get("openid")
    if not openid:
        raise BadRequest("缺少参数: openid")

    enter_log = await EnterLog.get_enter_log(openid)

    logger.info(f"qrcode -> openid: {openid}, qrcode: {enter_log.qrcode}")

    # 返回记录信息
    return response.json(
        {
            "qrcode": enter_log.qrcode,
            "enter_at": enter_log.enter_at.isoformat() if enter_log.enter_at else None,
            "leave_at": enter_log.leave_at.isoformat() if enter_log.leave_at else None,
        }
    )


@app.route("/pay")
async def pay(request: Request):

    openid = request.args.get("openid")
    if not openid:
        raise BadRequest("缺少参数: openid")

    try:
        money = 0.01
        # 创建订单
        order = await Order.create_order(openid, money)
        # 预支付
        pay_res = wxpayService().prepay(order, openid)
        return response.json(pay_res)
    except Exception as e:
        logger.error(f"支付异常请稍后重试, error: {e}")
        # 更新订单为失败
        await Order.update_order_pay_fail(order.order_no, str(e))
        raise BadRequest(f"支付异常请稍后重试")


@app.route("/pay_notify", methods=["POST"])
async def pay_notify(request: Request):

    try:
        # 验证通知签名
        verify_res = wxpayService().verify_notify_sign(request.headers, request.body)
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
--------------------------------------------------------服务器接口
"""


@app.route("/getStatus")
async def get_status(request: Request):

    logger.info(f"getStatus -> {dict(request.args)}")

    try:
        key = request.args.get("Key")
        Serial = request.args.get("Serial")
        if not key or not Serial:
            raise BadRequest("缺少参数: Key, Serial")

        # 更新或创建设备并更新活跃状态
        await Device.update_or_create_device(Serial)

        # 返回记录信息
        return response.json({"Key": key})

    except (NotFound, TypeError, ValueError, BadRequest) as e:
        logger.info(f"getStatus error -> " + e.message)
        return response.json({"Key": key})


@app.route("/searchCardAcs")
async def search_card_acs(request: Request):

    logger.info(f"searchCardAcs -> {dict(request.args)}")

    try:
        type = int(request.args.get("type"))
        Reader = int(request.args.get("Reader"))
        Card = request.args.get("Card")
        Serial = request.args.get("Serial")

        type = request.args.get("type")
        Reader = request.args.get("Reader")
        Card = request.args.get("Card")
        Serial = request.args.get("Serial")

        # 处理Base64编码的二维码
        if int(type) != 9:
            raise BadRequest("类型必须为二维码")

        # 如果是base64处理过需要解码
        Card = tool.decodeBase64(Card).decode("utf-8")

        Reader = int(Reader)

        # 更新或创建设备并更新活跃状态
        await Device.update_or_create_device(Serial)

        # 如果是进入，维护进入记录
        if Reader == 0:
            await EnterLog.maintain_enter_log(Card, Serial)
        # 如果是退出，维护退出记录
        elif Reader == 1:
            await EnterLog.maintain_leave_log(Card, Serial)

        print(f"类型: {type}, 进出: {Reader}, 内容: {Card}, 设备: {Serial}")

        return response.json({"ActIndex": Reader, "AcsRes": "1", "Time": "1"})

    except (NotFound, TypeError, ValueError, BadRequest) as e:
        logger.info(f"searchCardAcs error -> " + e.message)
        return response.json({"ActIndex": 0, "AcsRes": "0", "Time": "0"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
