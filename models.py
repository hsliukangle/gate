from tortoise.models import Model
from tortoise import fields
from tool import getNowTime
import uuid
from datetime import datetime
import random
from sanic.exceptions import BadRequest


# 自定义MyDatetimeField，用于MySQL中设置DATETIME(0)
class MyDatetimeField(fields.DatetimeField):
    class _db_mysql:
        SQL_TYPE = "DATETIME(0)"


class User(Model):
    id = fields.IntField(pk=True, unsigned=True, auto_increment=True)
    nickname = fields.CharField(max_length=255, null=True, description="昵称")
    avatar = fields.CharField(max_length=255, null=True, description="头像")
    openid = fields.CharField(
        max_length=255, null=True, description="openid", index=True
    )
    phone = fields.CharField(max_length=255, null=True, description="手机号")
    created_at = MyDatetimeField(null=True)
    updated_at = MyDatetimeField(null=True)

    class Meta:
        table = "users"
        table_description = "用户表"

    @classmethod
    async def get_or_create_user(cls, openid, nickname=None, avatar=None, phone=None):
        # 检查用户是否存在
        user = await cls.get_or_none(openid=openid)
        current_time = getNowTime()

        if not user:
            # 创建新用户
            user = await cls.create(
                openid=openid,
                nickname=nickname,
                avatar=avatar,
                phone=phone,
                created_at=current_time,
                updated_at=current_time,
            )
        else:
            # 更新现有用户信息
            update_fields = []
            if nickname and user.nickname != nickname:
                user.nickname = nickname
                update_fields.append("nickname")
            if avatar and user.avatar != avatar:
                user.avatar = avatar
                update_fields.append("avatar")
            if phone and user.phone != phone:
                user.phone = phone
                update_fields.append("phone")

            if update_fields:
                user.updated_at = getNowTime()
                update_fields.append("updated_at")
                await user.save(update_fields=update_fields)

        return user


class EnterLog(Model):
    id = fields.IntField(pk=True, unsigned=True, auto_increment=True)
    qrcode = fields.CharField(max_length=255, null=True, description="二维码")
    enter_at = MyDatetimeField(null=True, description="进入时间")
    enter_device_no = fields.CharField(
        max_length=255, null=True, description="进入设备号"
    )
    leave_at = MyDatetimeField(null=True, description="离开时间")
    leave_device_no = fields.CharField(
        max_length=255, null=True, description="离开设备号"
    )
    created_at = MyDatetimeField(null=True)
    updated_at = MyDatetimeField(null=True)
    user_id = fields.IntField(description="用户ID")
    order_id = fields.IntField(description="订单ID")

    class Meta:
        table = "enter_log"
        table_description = "用户进入记录表"

    @classmethod
    async def get_enter_log(cls, user_id, order_id):
        """获取用户信息"""
        user = await User.get_or_none(id=user_id)
        if not user:
            raise BadRequest("未找到用户")

        current_time = getNowTime()

        enter_log = await cls.get_or_none(
            user_id=user.id, order_id=order_id, leave_at=None
        )

        # 普通用户才能直接创建，教练需要支付创建
        if not order_id and not enter_log:
            enter_log = await cls.create(
                user_id=user.id,
                order_id=order_id,
                qrcode=str(uuid.uuid4()),
                created_at=current_time,
                updated_at=current_time,
            )
        return enter_log

    @classmethod
    async def update_enter_log(cls, qrcode, device_no):

        # 维护进入
        enter_log = await cls.get_or_none(qrcode=qrcode)
        if not enter_log:
            raise BadRequest(f"未找到 {qrcode} 的授权记录")
        if enter_log.enter_at or enter_log.enter_device_no:
            raise BadRequest(f"此二维码 {qrcode} 记录判断此前已进入")
        if enter_log.leave_at or enter_log.leave_device_no:
            raise BadRequest(f"此二维码 {qrcode} 记录判断此前已离开")

        # 更新进入时间和设备号
        current_time = getNowTime()
        enter_log.enter_at = current_time
        enter_log.enter_device_no = device_no
        enter_log.updated_at = current_time
        await enter_log.save()

    @classmethod
    async def update_leave_log(cls, qrcode, device_no):

        # 维护离开
        enter_log = await cls.get_or_none(qrcode=qrcode)
        if not enter_log:
            raise BadRequest(f"未找到 {qrcode} 的授权记录")
        if not enter_log.enter_at or not enter_log.enter_device_no:
            raise BadRequest(f"此二维码 {qrcode} 记录判断此前还未进入")
        if enter_log.leave_at or enter_log.leave_device_no:
            raise BadRequest(f"此二维码 {qrcode} 记录判断此前已离开")

        # 更新离开时间和设备号
        current_time = getNowTime()
        enter_log.leave_at = current_time
        enter_log.leave_device_no = device_no
        enter_log.updated_at = current_time
        await enter_log.save()


class Device(Model):
    id = fields.IntField(pk=True, unsigned=True, auto_increment=True)
    device_no = fields.CharField(max_length=255, null=True, description="设备号")
    first_active_at = MyDatetimeField(null=True, description="激活时间")
    active_at = MyDatetimeField(null=True, description="活跃时间")
    created_at = MyDatetimeField(null=True)
    updated_at = MyDatetimeField(null=True)

    class Meta:
        table = "devices"
        table_description = "设备表"

    @classmethod
    async def update_or_create_device(cls, device_no):
        """更新或创建设备记录，并更新活跃状态"""
        # 检查设备是否存在
        device = await cls.get_or_none(device_no=device_no)
        current_time = getNowTime()

        if not device:
            # 创建新设备记录
            device = await cls.create(
                device_no=device_no,
                first_active_at=current_time,
                active_at=current_time,
                created_at=current_time,
                updated_at=current_time,
            )
        else:
            # 更新设备活跃状态
            update_fields = []
            # 如果是首次激活，更新first_active_at
            if not device.first_active_at:
                device.first_active_at = current_time
                update_fields.append("first_active_at")

            # 始终更新active_at和updated_at
            device.active_at = current_time
            device.updated_at = current_time
            update_fields.extend(["active_at", "updated_at"])

            await device.save(update_fields=update_fields)

        return device


class Order(Model):
    # 订单状态常量
    STATUS_CREATED = 10  # 已创建
    STATUS_PAYING = 20  # 付款中
    STATUS_COMPLETED = 30  # 已完成
    STATUS_FAILED = 40  # 已失败
    STATUS_CANCELLED = 50  # 已取消

    id = fields.IntField(pk=True, unsigned=True, auto_increment=True)
    order_no = fields.CharField(max_length=255, default="", description="订单号")
    out_order_no = fields.CharField(
        max_length=255, default="", description="外部订单号"
    )
    money = fields.DecimalField(
        max_digits=8, decimal_places=2, default=0.00, description="金额"
    )
    status = fields.IntField(
        default=STATUS_CREATED,
        description="状态 10已创建 20付款中 30已完成 40已失败 50已取消",
    )
    note = fields.TextField(description="备注")
    user_id = fields.IntField(description="用户ID")
    paid_at = MyDatetimeField(null=True)
    created_at = MyDatetimeField(null=True)
    updated_at = MyDatetimeField(null=True)

    class Meta:
        table = "orders"
        table_description = "订单表"

    @classmethod
    def generate_order_no(cls):
        # 获取当前时间
        now = datetime.now().strftime("%Y%m%d%H%M%S")
        # 生成5位随机数
        random_part = str(random.randint(10000, 99999))
        # 组合订单号
        return now + random_part

    @classmethod
    async def create_order(cls, user_id, money):
        """获取用户信息"""
        user = await User.get_or_none(id=user_id)
        if not user:
            raise BadRequest("未找到用户")

        """创建订单"""
        current_time = getNowTime()
        order_no = cls.generate_order_no()

        order = await cls.create(
            order_no=order_no,
            out_order_no="",
            money=money,
            status=cls.STATUS_PAYING,  # 直接就是付款中
            note="",
            user_id=user.id,
            created_at=current_time,
            updated_at=current_time,
        )

        return order, user

    @classmethod
    async def update_order_paid(cls, order_no, transaction_id):
        """根据订单号更新订单为已支付"""
        order = await cls.get_or_none(order_no=order_no, status=cls.STATUS_PAYING)
        if order:
            order.status = cls.STATUS_COMPLETED
            order.out_order_no = transaction_id
            order.paid_at = getNowTime()
            order.updated_at = getNowTime()
            await order.save()
        return order

    @classmethod
    async def update_order_pay_fail(cls, order_no, note):
        """根据订单号更新订单为失败"""
        order = await cls.get_or_none(order_no=order_no)
        if order:
            order.status = cls.STATUS_FAILED
            order.note = note
            order.updated_at = getNowTime()
            await order.save()
        return order

    @classmethod
    async def get_user_last_order(cls, user_id):
        """根据用户ID获取用户最新订单"""
        return (
            await cls.get_or_none(user_id=user_id, status=cls.STATUS_COMPLETED)
            .order_by("-created_at")
            .first()
        )
