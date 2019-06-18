from django.conf.urls import url
from . import views

urlpatterns = [
    # 提供注册界面
    url(r'^register/$', views.RegisterView.as_view(),name='register'),
    url(r'^usernames/(?P<username>[a-zA-Z0-9_-]{5,20})/count/$', views.UsernameCountView.as_view()),

    # 注册电话是否重复应用
    url(r'^Mobiles/(?P<mobile>1[3-9]d{9})/count/$', views.MobileCountView.as_view()),

    # 用户登录
    url(r'^login/$',views.LoginView.as_view(),name= 'login'),
    url(r'^logout/$',views.LogoutView.as_view(),name= 'logout'),
    url(r'^info/$', views.UserInfoView.as_view(), name="info"),
    # 添加邮箱
    url(r'^emails/$', views.EmailView.as_view()),
    # 验证邮箱
    url(r'^emails/verification/$', views.VerifyEmailView.as_view()),
    # 用户收获地址

    url(r'^addresses/$',views.AddressView.as_view(),name='address'),
    # 用户地址添加
    url(r'^addresses/create/$',views.CreateAddressView.as_view()),
    # 用户收货地址修改和删除
    url(r'^addresses/(?P<address_id>\d+)/$', views.UpdateDestroyAddressView.as_view()),
    # 设置默认地址
    url(r'^addresses/(?P<address_id>\d+)/default/$', views.UpdateDestroyAddressView.as_view()),
    # 用户修改地址标签
    url(r'^addresses/(?P<address_id>\d+)/title/$', views.UpdateTitleAddressView.as_view()),
    # 修改用户密码
    url(r'^password/$', views.ChangePasswordView.as_view()),
    # 商品浏览记录
    url(r'^browse_histories/$', views.UserBrowseHistory.as_view()),

]


