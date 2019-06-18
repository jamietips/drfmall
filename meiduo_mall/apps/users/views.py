import json

from django import http
import re
from django.conf import settings
from django.contrib.auth import login, authenticate, logout, mixins
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.utils.decorators import method_decorator
from django_redis import get_redis_connection
from django.shortcuts import render, redirect

from goods.models import SKU
from django.views import View
import logging
logger = logging.getLogger('django')
# Create your views here.
from users.models import User
from meiduo_mall.utils.response_code import RETCODE
from users.utils import generate_email_verify_url, check_verify_token
from celery_tasks.email.tasks import send_verify_email
from meiduo_mall.utils.views import LoginRequiredView
from .models import Address


class RegisterView(View):

    """注册"""
    def get(self, request):
        """提供注册界面"""
        # http://127.0.0.1/register
        # http://127.0.0.1:8000/register/index/
        return render(request,'register.html')

    def post(self, request):

        """注册功能逻辑"""
        # 1.接收前端传入的表单数据
        # 用户名，密码，密码2，手机号，短信验证码，同意协议
        query_dict = request.POST
        username = query_dict.get('username')
        password = query_dict.get('password')
        password2 = query_dict.get('password2')
        mobile = query_dict.get('mobile')
        sms_code = query_dict.get('sms_code')
        allow = query_dict.get('allow')
        # 单选框如果勾选就是'on',如果没有勾选None


        # all None,False,
        # 校验前端传入的参数是否齐全
        if all([username,password,password2,mobile,sms_code,allow]) is False:
            return http.HttpResponseForbidden('缺少必传参数')

        # 校验数据前端传入数据是否符合要求
        # 校验数据是否满足需求
        if not re.match(r'^[a-zA-Z0-9_-]{5,20}$',username):
            return http.HttpResponseForbidden('请输入5-20个字符的用户名')

        if not re.match(r'[0-9A-Za-z]{8,20}$',password):
            return http.HttpResponseForbidden('请输入8-20位的密码')

        if password != password2:
            return http.HttpResponseForbidden('两次输入的密码不一样')

        if not re.match(r'^1[3-9]\d{9}$',mobile):
            return http.HttpResponseForbidden('您输入的手机格式不对')

        # TODO 短信验证码后期再补充校验逻辑
        redis_conn = get_redis_connection('verify_code')
        sms_code_server = redis_conn.get('sms_%s'%mobile)

        redis_conn.delete('sms_%s'%mobile)  #删除redis中的短信验证码，让验证码只能用一次


        # 校验短信验证码是否过期
        if sms_code_server is None:
            return http.HttpResponseForbidden('短信验证码过期')

        sms_code_server = sms_code_server.decode() #把bytes类型转换成子服串

        # 判断前端和后端的短信验证码是否一致
        if sms_code != sms_code_server:
            return http.HttpResponseForbidden('请输入正确的短信验证码')


        # 保存数据，创建user
        # User.objects.create()
        # user.set_password() 对密码进行加密
        # user.check_password()校验密码的
        user = User.objects.create_user(username=username,password=password,mobile=mobile)

        # 当用户登陆后，将用户的user.id存储到 session 生成cookie
        login(request, user)

        # 保存数据，创建user

        # 响应：重定向到首页
        return redirect('/')


class UsernameCountView(View):

    """判断用户是否重复注册"""
    def get(self,request,username):

        count = User.objects.filter(username=username).count()

        response_data = {'count':count, 'code': RETCODE.OK, 'errmsg': 'OK'}

        return http.JsonResponse(response_data)


class MobileCountView(View):

    """判断电话是否重复注册"""
    def get(self,request,Mobile):

        count = User.objects.filter(Mobile=Mobile).count()

        response_data = {'count':count, 'code': RETCODE.OK, 'errmsg': 'OK'}

        return http.JsonResponse(response_data)


class LoginView(View):

    """用户登录"""
    def get(self,request):

        """展示登录界面"""
        return render(request,'login.html')

    def post(self,request):

        """用户登录逻辑"""
        # 1.接收表单数据
        username = request.POST.get('username')
        password = request.POST.get('password')
        remembered = request.POST.get('remembered')

        # 2.校验
        # try:
        #     user = User.objects.get(username=username)
        #
        # except User.DoesNotExist:
        #     return
        #
        # if user.check_password(password) is False:
        #     return
        if re.match(r'^1[3-9\d{9}]',username):
            User.USERNAME_FIELD = 'mobile'

        # 用户校验有可能返回user模型对象，有可能返回None
        user = authenticate(request,username=username,password=password)
        User.USERNAME_FIELD = 'username'

        if user is None:
            return render(request,'login.html',{'account_errmsg':'用户名或者密码错误'})


        # 状态保持
        login(request,user)

        # 如果用户没有点击记信登录

        if remembered != 'on':
            request.session.set_expiry(0)  #此行代码实际最终会将cookie中的sessionid设置为浏览器关闭就失效
        # session如果会话结束就过期，应该设置过期时间为0,但是cookie如果设置会话结束就过期不能设置为0,应设置为None
        response = redirect('/')
        response.set_cookie('username',user.username,max_age=settings.SESSION_COOKIE_AGE if remembered else None)
        # 重定向到首页
        return response


class LogoutView(View):

    """退出登录"""
    def get(self,request):

        # 1.清除状态保持信息
        logout(request)

        # 2.创建响应对象之重定向到登录页面
        # response = redirect('/login/')
        # 2
        response = redirect(reverse('users:login'))





        # 3.清除cookie中的username
        response.delete_cookie('username')

        # 4.响应

        return response


# class UserInfoView(View):
#
#     """展示用户中心"""
#
#     def get(self,request):     # request = HttpRequest()
#
#         user = request.user #request.user获取当前登录的用户属性 如用户python
#         print(user)
#         if user.is_authenticated:  #判断用户 是否登录，登录后再显示用户中心界面，每登录重定向到登录页
#             return render(request,'user_center_info.html')
#
#         else:
#             return redirect('/login/?next=/info/')
#
#
# class UserInfoView(View):
#
#     """展示用户中心"""
#     @method_decorator(login_required)
#     def get(self,request):
#
#         """展示用户中心界面"""
#         return render(request,'user_center_info.html')


class UserInfoView(mixins.LoginRequiredMixin,View):

    """展示用户中心"""

    def get(self,request):

        """展示用户中心界面"""
        return render(request,'user_center_info.html')


class EmailView(mixins.LoginRequiredMixin,View):

    """设置用户邮箱"""
    def put(self, request):

        """设置用户邮箱"""
        # 接收请求体数据

        # json.loads将字符串类型格式 解码成python数据风格
        json_dict = json.loads(request.body.decode())
        email = json_dict.get('email')

        # 校验

        if not email:
            return http.HttpResponseForbidden('缺少email参数')
        if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return http.HttpResponseForbidden('参数email有误')

        # 修改用户的email字段
        user = request.user
        # user.email = email
        # user.save()
        # 乐观锁
        User.objects.filter(username=user.username,email='').update(email=email)

        # 在此就应该对当前设置的邮箱发一封激活有邮件
        # from django.core.mail import send_mail
        # send_mail()
        # 生成邮箱激活url
        verify_url = generate_email_verify_url(user)
        send_verify_email.delay(email, verify_url)  # 使用celery异步发送邮件


        # 响应
        return http.JsonResponse({'code':RETCODE.OK,'errmsg':'添加邮箱成功'})



class VerifyEmailView(View):
    """激活邮箱"""

    def get(self,request):

        # 接收参数中的token
        token = request.GET.get('token')

        # 校验

        if token is None:
            return http.HttpResponseForbidden('缺少token')
        # 对token解密并获取user
        user = check_verify_token(token)

        if user is None:

            return http.HttpResponseForbidden('token无效')
        # 修改指定user的email_active字段
        user.email_active = True
        user.save()

        # 激活成功加到用户中心
        return redirect('/info/')





class AddressView(LoginRequiredView):

    """用户收获地址展示"""
    def get(self,request):
        """用户收获地址展示"""
        user = request.user
        # 查询当前用户的收货地址
        address_qs = Address.objects.filter(user=user,is_deleted=False)
        # 定义一个列表变量来包装所有的收获地址
        addresses = []
        for address_model in address_qs:
            addresses.append({
                'id':address_model.id,
                'tittle':address_model.title,
                'receiver':address_model.receiver,
                'province':address_model.province,
                'province_id':address_model.province_id,
                "city_id": address_model.city.id,
                "district": address_model.district.name,
                "district_id": address_model.district.id,
                "place": address_model.place,
                "mobile": address_model.mobile,
                "tel": address_model.tel,
                "email": address_model.email

            })
            # 准备渲染数据
        context = {
            'addresses':addresses,
            'default_address_id':user.default_address_id
        }
        return render(request,'user_center_site.html',context)

class CreateAddressView(LoginRequiredView):
    """收货地址新增"""

    def post(self, request):
        # 判断用户的收货地址是否上限
        user = request.user
        # user.addresses.filter(is_deleted=False).count()
        count = Address.objects.filter(user=user, is_deleted=False).count()
        if count >= 20:  # 地址不能超过上限
            return http.JsonResponse({'code': RETCODE.THROTTLINGERR, 'errmsg': '收货超过上限'})
        # 接收请求体数据
        json_dict = json.loads(request.body.decode())
        title = json_dict.get('title')
        receiver = json_dict.get('receiver')
        province_id = json_dict.get('province_id')
        city_id = json_dict.get('city_id')
        district_id = json_dict.get('district_id')
        place = json_dict.get('place')
        mobile = json_dict.get('mobile')
        tel = json_dict.get('tel')
        email = json_dict.get('email')
        # 校验
        if all([title, receiver, province_id, city_id, district_id, place, mobile]) is False:
            return http.HttpResponseForbidden('缺少必传参数')
        if not re.match(r'^1[3-9]\d{9}$', mobile):
            return http.HttpResponseForbidden('参数mobile有误')
        if tel:
            if not re.match(r'^(0[0-9]{2,3}-)?([2-9][0-9]{6,7})+(-[0-9]{1,4})?$', tel):
                return http.HttpResponseForbidden('参数tel有误')
        if email:
            if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
                return http.HttpResponseForbidden('参数email有误')

        try:
            # 保存收货地址数据
            address_model = Address.objects.create(
                user=request.user,
                title=title,
                receiver=receiver,
                province_id=province_id,
                city_id=city_id,
                district_id=district_id,
                place=place,
                mobile=mobile,
                tel=tel,
                email=email
            )
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'code': RETCODE.PARAMERR, 'errmsg': '新增收货地址失败'})

        # 如果当前用户还没有默认收货地址,就把当前新增的这个收货地址设置为它的默认地址
        if user.default_address is None:
            user.default_address = address_model
            user.save()

        # 把保存好的模型对象转换成字段,再响应给前端
        address_dict = {
            'id': address_model.id,
            'title': address_model.title,
            "receiver": address_model.receiver,
            "province": address_model.province.name,
            "province_id": address_model.province.id,
            "city": address_model.city.name,
            "city_id": address_model.city.id,
            "district": address_model.district.name,
            "district_id": address_model.district.id,
            "place": address_model.place,
            "mobile": address_model.mobile,
            "tel": address_model.tel,
            "email": address_model.email
        }
        # 响应
        return http.JsonResponse({'code': RETCODE.OK, 'errmsg': '新增地址成功', 'address': address_dict})


class UpdateDestroyAddressView(LoginRequiredView):

    """修改和删除用户收获地址"""
    def put(self,request,address_id):

        """接收请求数据"""
        json_dict = json.loads(request.body.decode())
        title = json_dict.get('title')
        receiver = json_dict.get('receiver')
        province_id = json_dict.get('province_id')
        city_id = json_dict.get('city_id')
        district_id = json_dict.get('district_id')
        place = json_dict.get('place')
        mobile = json_dict.get('mobile')
        tel = json_dict.get('tel')
        email = json_dict.get('email')

        # 校验
        if all([title,receiver,province_id,city_id,district_id,place,mobile]) is False:
            return http.HttpResponseForbidden('缺少比传参数')
        if not re.match(r'^[3-9]\d{9}$',mobile):
            return http.HttpResponseForbidden('参数mobile有误')
        if tel:
            if not re.match(r'^(0[0-9]{2,3}-)?([2-9][0-9]{6,7})+(-[0-9]{1,4})?$', tel):
                return http.HttpResponseForbidden('参数tel有误')
        if email:
            if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
                return http.HttpResponseForbidden('参数email有误')


        try:
            # 修改收获地址数据
            Address.objects.filter(id=address_id).update(
                title = title,
                receiver=receiver,
                province_id=province_id,
                city_id=city_id,
                district_id=district_id,
                place=place,
                mobile=mobile,
                tel=tel,
                email=email
            )
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'code':RETCODE.PARAMERR,'errmsg':'修改收获地址失败'
                                                                       ''})
        # 获取到修改后的地址模型对象
        address_model = Address.objects.get(id=address_id)
        address_dict = {
            'id':address_model.id,
            'title':address_model.title,
            'receiver':address_model.receiver,
            'province':address_model.province.name,
            'province_id':address_model.province.id,
            'city':address_model.city.name,
            'city_id':address_model.city.id,
            "district": address_model.district.name,
            "district_id": address_model.district.id,
            "place": address_model.place,
            "mobile": address_model.mobile,
            "tel": address_model.tel,
            "email": address_model.email
        }

        # 响应
        return http.JsonResponse({'code':RETCODE.OK,'errmsg':'修改地址成功','address':address_dict})
    def delete(self, request, address_id):
        """删除收货地址"""
        try:
            address = Address.objects.get(id=address_id)
            address.is_deleted = True
            address.save()
            return http.JsonResponse({'code': RETCODE.OK, 'errmsg': '删除地址成功'})
        except Address.DoesNotExist:
            return http.JsonResponse({'code': RETCODE.PARAMERR, 'errmsg': 'address_id不存在'})


class DefaultAddressView(LoginRequiredView,View):
    """设置默认地址"""
    def put(self,request,address_id):
        """设置默认地址"""
        try:
            # 接收参数，查询地址
            address = Address.objects.get(id=address_id)

            # 设置地址为默认地址
            request.user.default_address = address

            request.user.save()

        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'code':RETCODE.DBERR,'errmsg':'设置默认地址失败'})

        # 响应设置默认地址结果
        return http.JsonResponse({'code':RETCODE.OK,'errmsg':'设置默认地址成功'})

class UpdateTitleAddressView(LoginRequiredView,View):

    """设置地址标题"""

    def put(self,request,address_id):
        """设置地址标签"""
        # 接收参数：地址标题
        json_dict = json.loads(request.body.decode())
        title = json_dict.get('title')

        try:
            # 查询地址
            address = Address.objects.get(id=address_id)


            # 设置新的地址标题

            address.title = title
            address.save()

        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'code':RETCODE.DBERR,'errmsg':'设置地址标签失败'})

    # 响应删除地址结果

        return http.JsonResponse({'code':RETCODE.OK,'errmsg':'设置地址标签成功'})


class ChangePasswordView(LoginRequiredView):
    """修改用户密码"""
    def get(self, request):
        return render(request, 'user_center_pass.html')

    def post(self, request):
        # 接收请求体中的表单数据
        query_dict = request.POST
        old_password = query_dict.get('old_pwd')
        new_password = query_dict.get('new_pwd')
        new_password2 = query_dict.get('new_cpwd')

        # 校验
        if all([old_password, new_password, new_password2]) is False:
            return http.HttpResponseForbidden('缺少必传参数')
        user = request.user  # 获取当前登录用户
        if user.check_password(old_password) is False:
            return render(request, 'user_center_pass.html', {'origin_pwd_errmsg': '原密码错误'})
        if not re.match(r'^[0-9A-Za-z]{8,20}$', new_password):
            return http.HttpResponseForbidden('密码最少8位，最长20位')
        if new_password != new_password2:
            return http.HttpResponseForbidden('两次输入的密码不一致')

        # 修改用户的密码 set_password方法
        user.set_password(new_password)
        user.save()
        # 清除状态保持信息
        logout(request)
        # 清除cookie中的username
        response = redirect('/login/')
        response.delete_cookie('username')
        # 重定向到login界面
        return response


class UserBrowseHistory(LoginRequiredView):
    """商品浏览记录"""

    def post(self, request):
        """保存浏览记录逻辑"""

        # 1.接收请求体中的sku_id
        json_dict = json.loads(request.body.decode())
        sku_id = json_dict.get('sku_id')

        try:
            # 2.校验sku_id的真实有效性
            sku = SKU.objects.get(id=sku_id)
        except SKU.DoesNotExist:
            return http.HttpResponseForbidden('sku_id不存在')

        # 创建redis连接对象
        redis_conn = get_redis_connection('history')
        pl = redis_conn.pipeline()
        # 获取当前用户
        user = request.user
        # 拼接用户list的key
        key = 'history_%s' % user.id
        # 先去重
        pl.lrem(key, 0, sku_id)
        # 添加到列表的开头
        pl.lpush(key, sku_id)
        # 截取列表中的前五个元素
        pl.ltrim(key, 0, 4)
        # 执行管道
        pl.execute()

        # 响应
        return http.JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK'})

    def get(self, request):
        """获取用户浏览记录逻辑"""
        # 1. 获取当前的登录用户对象
        user = request.user
        # 2.创建redis连接对象
        redis_conn = get_redis_connection('history')
        # 获取当前用户在redis中的所有浏览记录列表
        sku_ids = redis_conn.lrange('history_%s' % user.id, 0, -1)

        # sku_qs = SKU.objects.filter(id__in=sku_ids)  # 不要这样写,会影响顺序
        skus = []  # 用来保存sku字典
        # 再通过列表中的sku_id获取到每个sku模型
        for sku_id in sku_ids:
            # 再将sku模型转换成字典
            sku_model = SKU.objects.get(id=sku_id)
            skus.append({
                'id': sku_model.id,
                'name': sku_model.name,
                'default_image_url': sku_model.default_image.url,
                'price': sku_model.price
            })

        # 响应
        return http.JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK', 'skus': skus})