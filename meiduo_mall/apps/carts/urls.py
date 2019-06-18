from django.conf.urls import url

from . import views


urlpatterns = [
    # 购物车
    url(r'^carts/$', views.CartsView.as_view()),
# 购物车全选
    url(r'^carts/selection/$', views.CartsSelectedAllView.as_view()),

    url(r'^carts/simple/$', views.CartsSimpleView.as_view()),

]