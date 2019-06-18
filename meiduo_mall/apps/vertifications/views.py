import random
import logging
from celery_tasks.sms.tasks import send_sms_code

from django import http
from django_redis import get_redis_connection


from meiduo_mall.libs.captcha.captcha import captcha
# Create your views here.
from django.views import View

# from celery_tasks.sms.yuntongxun import CCP
from meiduo_mall.utils.response_code import RETCODE
from vertifications.constants import SMS_CODE_REDIS_EXPIRES


class ImageCodeView(View):

    """图形验证码"""

    def get(self,request,uuid):
        # 1.调用SDK方法,生成图形验证码
        # name表示SDK内部生成的唯一标识
        # text 表示 图形验证码文字内容
        # image图片bytes类型数据
        name, text,image = captcha.generate_captcha()
        # 2.将图形验证码的文字储存到redis数据库中
        redis_conn = get_redis_connection("verify_code")
        redis_conn.setex('img_%s'%uuid,SMS_CODE_REDIS_EXPIRES,text)
        # 3.响应图片内容给前端
        return http.HttpResponse(image, content_type='image/png')


logger = logging.getLogger('django')

class SMSCodeView(View):
    """短信验证码"""
    def get(self, request, mobile):

        # 创建redis连接对象
        redis_conn = get_redis_connection('verify_code')
        # 尝试去redis中获取此手机号有没有发送过短信的标记，如果有，直接响应

        send_flag = redis_conn.get('send_flag%s' % mobile)
        print(send_flag)

        if send_flag:  # 判断有没有标记
            return http.JsonResponse({'code': RETCODE.THROTTLINGERR, 'errmsg': '频繁发送短信'})

        # 提取前端url查询参数传入的image_code,uuid
        image_code_client = request.GET.get('image_code')
        uuid = request.GET.get('uuid')

        # 校验all()
        if not all([image_code_client,uuid]):
            return http.JsonResponse({'code' : RETCODE.NECESSARYPARAMERR, 'errmsg':'缺少必传参数'})




        # 提取图形验证码
        image_code_server = redis_conn.get('img_%s'%uuid)

        if image_code_server is None:
            # 图形验证码过期或者不存在
            return http.JsonResponse({'code':RETCODE.IMAGECODEERR,'errmsg':'图形验证码失效'})

        # 删除图形验证码，避免恶意测试图形验证码
        redis_conn.delete('img_%s'%uuid)

        # 获取redis中的图形验证码和前端传入的进行比较

        image_code_server = image_code_server.decode() #byte转字符串
        if image_code_client.lower() != image_code_server.lower(): #转小写后比较
            return http.JsonResponse({'code':RETCODE.IMAGECODEERR,'errmsg':'输入的图形有误'})

        # 生成一个随机的6位数字，作为短信验证码

        sms_code = '%06d'%random.randint(0,999999)
        logger.info(sms_code)

        # 管道技术

        p1 = redis_conn.pipeline()

        # 把短信验证码存储到redis，以备后期注册是校验
        # 保存短信验证码
        # redis_conn.setex('sms_%s'%mobile, SMS_CODE_REDIS_EXPIRES,sms_code)
        p1.setex('sms_%s' % mobile, SMS_CODE_REDIS_EXPIRES, sms_code)
        # 向redis存储一个此手机号已发送过短信的标记
        p1.setex('send_flag_%s'%mobile,60,1)
        # 执行管道
        p1.execute()
        # 发短信 容联云通讯

        # 发送短信验证码
        # CCP().send_template_sms(mobile,[sms_code,SMS_CODE_REDIS_EXPIRES//60],1)
        send_sms_code.delay(mobile, sms_code)


        # 响应结果
        return http.JsonResponse({'code':RETCODE.OK,'errmsg':'发送短信成功'})