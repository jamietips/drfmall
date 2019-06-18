# 异步文件任务
from celery_tasks.sms.yuntongxun.sms import  CCP
from celery_tasks.main import celery_app

@celery_app.task() #只有用celery装饰器装饰过才是celery任务
def send_sms_code(mobile,sms_code):
    """


    :param mobile: 手机号
    :param sms_code: 短信验证码

    :return:  成功0或者失败-1

    """
    CCP().send_template_sms(mobile,[sms_code,5],1)


#

