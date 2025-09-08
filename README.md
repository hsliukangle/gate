# 项目介绍
测试

### 运行环境
python、sanic、mysql

### 具体流程
1.运行环境
```
python -m venv .venv

source .venv/bin/activate

cd gate

pip install -r requirements.txt
```

2.创建数据库
```
创建gate数据库

导入date.sql文件
```
3.修改env配置并运行项目
```
python main.py

将运行在8000端口
```

4.开始测试前准备

创建一个进入二维码（参数为该用户的openid）
```
http://127.0.0.1:8000/qrcode?openid=oaAmq4tUFeaCwIwU7GDxiHHYnV8
```

响应
```
{
    "qrcode": "6e10825d-5c0b-4b5c-9fb4-0caefac33cea"
}
```

5.心跳接口

http://127.0.0.1:8000/getStatus?Key=23685&Serial=R12034

```
观察数据库devices表，是否有数据插入，以及数据变化
```
6.同步开关闸口接口

>Card为该用户的二维码内容，暂时为明文，比如：6e10825d-5c0b-4b5c-9fb4-0caefac33cea

```
进入
http://127.0.0.1:8000/searchCardAcs?type=9&Reader=0&Serial=R12034&Card=6e10825d-5c0b-4b5c-9fb4-0caefac33cea
```
```
离开
http://127.0.0.1:8000/searchCardAcs?type=9&Reader=1&Serial=R12034&Card=6e10825d-5c0b-4b5c-9fb4-0caefac33cea
```

## 预期
1. 数据库devices表中，每次请求都会更新活跃时间
2. 数据库enter_log表中，获取二维码后进入与离开4个字段都为空，进入后有进入记录，离开后有离开记录
