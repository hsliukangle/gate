from tortoise.models import Model
from tortoise import fields
from tool import getNowTime
import uuid
from sanic.exceptions import NotFound


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
    user = fields.ForeignKeyField(
        "models.User", related_name="enter_logs", description="用户ID"
    )
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

    class Meta:
        table = "enter_log"
        table_description = "用户进入记录表"

    @classmethod
    async def get_or_create_enter_log(cls, openid):
        # 获取用户信息
        user = await User.get_or_none(openid=openid)
        current_time = getNowTime()

        if not user:
            raise NotFound("未找到用户")

        enter_log = await cls.get_or_none(user_id=user.id, leave_at=None)

        if not enter_log:

            # 生成UUID
            log_uuid = str(uuid.uuid4())

            enter_log = await cls.create(
                user_id=user.id,
                qrcode=log_uuid,
                created_at=current_time,
                updated_at=current_time,
            )

        return enter_log

    @classmethod
    async def maintain_enter_log(cls, qrcode, device_no):
        """维护进入记录"""
        # 检查是否存在未完成的记录
        enter_log = await cls.get_or_none(
            qrcode=qrcode,
            enter_at=None,
            enter_device_no=None,
            leave_at=None,
            leave_device_no=None,
        )
        current_time = getNowTime()

        if not enter_log:
            raise NotFound("未找到未进入记录")

        # 更新进入时间和设备号
        enter_log.enter_at = current_time
        enter_log.enter_device_no = device_no
        enter_log.updated_at = current_time
        await enter_log.save()

    @classmethod
    async def maintain_leave_log(cls, qrcode, device_no):
        """维护离开记录"""
        # 检查是否存在未完成的记录
        enter_log = await cls.get_or_none(
            qrcode=qrcode, leave_at=None, leave_device_no=None
        )
        current_time = getNowTime()

        if not enter_log or not enter_log.enter_at or not enter_log.enter_device_no:
            raise NotFound("未找到未离开记录")

        # 更新离开时间和设备号
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
