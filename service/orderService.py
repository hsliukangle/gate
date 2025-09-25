from models import Order, User


class orderService:
    async def add_order(self, openid, money):
        """获取用户信息"""
        user = await User.get_or_none(openid=openid)
        if not user:
            raise NotFound("未找到用户")

        """创建订单"""
        order = await Order.create_order(user.id, money)
        return order
