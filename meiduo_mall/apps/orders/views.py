from django.core.paginator import Paginator, EmptyPage
from django import http
from django.http import JsonResponse
from django.shortcuts import render
from django_redis import get_redis_connection
from decimal import Decimal
import json


from django import http
from django.utils import timezone
from django.db import transaction

from meiduo_mall.utils.views import LoginRequiredView
from users.models import Address
from goods.models import SKU
from .models import OrderInfo, OrderGoods
from meiduo_mall.utils.response_code import RETCODE
import logging
logger = logging.getLogger()

class OrderSettlementView(LoginRequiredView):
    """去结算界面逻辑"""

    def get(self, request):

        # 1.查询数据(登录用户的收货地址,  展示购物车中勾选商品的一些数据)
        addresses = Address.objects.filter(user=request.user, is_deleted=False)
        # 1.1 判断是否查询到用户收货,没有 设置变量为None
        addresses = addresses if addresses.exists() else None
        # 2. 获取登录用户
        user = request.user
        # 2.1 创建redis连接
        redis_conn = get_redis_connection('carts')
        # 2.2 获取出hash和set集合中购物车数据
        redis_dict = redis_conn.hgetall('carts_%s' % user.id)  # {1: 2, 16: 1}
        selected_ids = redis_conn.smembers('selected_%s' % user.id)  # {1, 16}
        # 2.3 定义一个字典变量用来保存勾选的商品id和count
        cart_dict = {}
        # 遍历set集合 包装勾选商品及count
        for sku_id_bytes in selected_ids:
            cart_dict[int(sku_id_bytes)] = int(redis_dict[sku_id_bytes])  # {1:2, 16: 2}

        # 3. 获取勾选商品的sku模型
        skus = SKU.objects.filter(id__in=cart_dict.keys())
        total_count = 0  # 统计商品数量
        total_amount = Decimal('0.00')  # 商品总价
        # 遍历sku查询集给sku模型多定义count和小计数据
        for sku in skus:
            # 给sku模型多定义count属性记录数量
            sku.count = cart_dict[sku.id]
            sku.amount = sku.price * sku.count  # 小计

            # 累加商品总量
            total_count += sku.count
            # 累加商品小计得到商品总价
            total_amount += sku.amount

        # 运费
        freight = Decimal('10.00')

        # 构造模板需要渲染的数据
        context = {
            'addresses': addresses,  # 用户收货地址
            'skus': skus,  # 勾选商品的sku查询集
            'total_count': total_count,  # 总数量
            'total_amount': total_amount,  # 商品总价
            'freight': freight,  # 运费
            'payment_amount': total_amount + freight  # 总金额
        }
        # 响应
        return render(request, 'place_order.html', context)


class OrderCommitView(LoginRequiredView):
    """提交订单逻辑"""

    def post(self, request):
        # 四张表的操作要么一起成功,要么一起失败


        # 一, 保存一个订单基本信息记录
        # 获取请求体数据
        json_dict = json.loads(request.body.decode())
        address_id = json_dict.get('address_id')  # 收货地址id
        pay_method = json_dict.get('pay_method')  # 支付方式

        # 校验
        if all([address_id, pay_method]) is False:
            return http.HttpResponseForbidden('缺少必传参数')
        try:
            address = Address.objects.get(id=address_id)
        except Address.DoesNotExist:
            return http.HttpResponseForbidden('address_id不存在')

        if pay_method not in [OrderInfo.PAY_METHODS_ENUM['CASH'], OrderInfo.PAY_METHODS_ENUM['ALIPAY']]:
            return http.HttpResponseForbidden('非法支付方式')

        user = request.user
        # 201906041219470000000001
        # 生成订单编号:  获取当前时间 + 用户user_id
        order_id = timezone.now().strftime('%Y%m%d%H%M%S') + ('%09d' % user.id)

        status = (OrderInfo.ORDER_STATUS_ENUM['UNPAID']
                  if pay_method == OrderInfo.PAY_METHODS_ENUM['ALIPAY']
                  else OrderInfo.ORDER_STATUS_ENUM['UNSEND'])

        # 手动开启事务
        with transaction.atomic():

            # 创建事务的保存点
            save_point = transaction.savepoint()
            try:
                # 保存订单记录
                order = OrderInfo.objects.create(
                    order_id=order_id,
                    user=user,
                    address=address,
                    total_count=0,
                    total_amount=Decimal(0.00),
                    freight=Decimal('10.00'),
                    pay_method=pay_method,
                    status=status
                )

                # 二, 修改sku的库存和销量
                # 创建redis连接
                redis_conn = get_redis_connection('carts')
                # 获取hash和set数据
                redis_dict = redis_conn.hgetall('carts_%s' % user.id)
                selected_ids = redis_conn.smembers('selected_%s' % user.id)
                # 定义一个字典用来包装要购物车的商品id和count
                cart_dict = {}
                # 遍历set集合包装数据
                for sku_id_bytes in selected_ids:
                    cart_dict[int(sku_id_bytes)] = int(redis_dict[sku_id_bytes])

                # sku_qs = SKU.objects.filter(id__in=cart_dict.keys()) # 不要一下全部查询出来,会有缓存问题
                # 遍历要购物车商品的字典
                for sku_id in cart_dict:
                    while True:
                        # 一次只查询出一个sku模型
                        sku = SKU.objects.get(id=sku_id)
                        # 获取用户此商品要购物车的数量
                        buy_count = cart_dict[sku_id]
                        # 定义两个变量用来记录当前sku的原本库存和销量
                        origin_stock = sku.stock
                        origin_sales = sku.sales

                        # import time
                        # time.sleep(5)

                        # 判断当前要购物车的商品库存是否充足
                        if buy_count > origin_stock:
                            # 库存不足就回滚
                            transaction.savepoint_rollback(save_point)
                            # 如果库存不足,提前响应
                            return http.JsonResponse({'code': RETCODE.STOCKERR, 'errmsg': '库存不足'})

                        # 如果能购买,计算新的库存和销量
                        new_stock = origin_stock - buy_count
                        new_sales = origin_sales + buy_count
                        # 修改sku模型库存和销量
                        # sku.stock = new_stock
                        # sku.sales = new_sales
                        # sku.save()
                        result = SKU.objects.filter(id=sku_id, stock=origin_stock).update(stock=new_stock, sales=new_sales)

                        if result == 0:
                            continue

                        # 三, 修改spu的销量
                        spu = sku.spu
                        spu.sales += buy_count
                        spu.save()

                        # 四, 保存订单中的商品记录
                        OrderGoods.objects.create(
                            order=order,
                            sku=sku,
                            count=buy_count,
                            price=sku.price
                        )

                        # 累加商品总数量
                        order.total_count += buy_count
                        # 累加商品总价
                        order.total_amount += (sku.price * buy_count)

                        break # 当前商品下单成功,继续买下一个
                # 累加运费
                order.total_amount += order.freight
                order.save()
            except Exception:
                # 暴力回滚
                transaction.savepoint_rollback(save_point)
                return http.JsonResponse({'code': RETCODE.DBERR, 'errmsg': '下单失败'})
            else:
                # 提交事务
                transaction.savepoint_commit(save_point)



        # 删除已结算的购物车数据
        pl = redis_conn.pipeline()
        pl.hdel('carts_%s' % user.id, *selected_ids)
        pl.delete('selected_%s' % user.id)
        # pl.srem('selected_%s' % user.id, *selected_ids)
        pl.execute()

        return http.JsonResponse({'code': RETCODE.OK, 'errmsg': '下单成功', 'order_id': order_id})


class OrderSuccessView(LoginRequiredView):
    """提交订单成功后的界面"""

    def get(self, request):
        # 接收查询参数数据
        query_dict = request.GET
        order_id = query_dict.get('order_id')
        payment_amount = query_dict.get('payment_amount')
        pay_method = query_dict.get('pay_method')

        # 校验
        try:
            OrderInfo.objects.get(order_id=order_id, pay_method=pay_method, total_amount=payment_amount)
        except OrderInfo.DoesNotExist:
            return http.HttpResponseForbidden('订单信息有误')

        # 包装模板要进行渲染的数据
        context = {
            'order_id': order_id,
            'pay_method': pay_method,
            'payment_amount': payment_amount
        }

        # 响应
        return render(request, 'order_success.html', context)


class AllOrdersView(LoginRequiredView):

    """展示所有订单"""
    def get(self,request,page_num):

        user = request.user
        order_qs = OrderInfo.objects.filter(user=user).order_by('-create_time')
        paginator = Paginator(order_qs, 2)
        try:
            # 获取指定页的数据
            page_orders = paginator.page(page_num)
        except EmptyPage:
            return http.HttpResponseForbidden('当前不存在')
        # 获取总页数据
        total_page = paginator.num_pages

        # 遍历订单，获取订单信息

        for order in page_orders:
            # 为订单赋值付款方式属性
            order.pay_method_name = OrderInfo.PAY_METHOD_CHOICES[order.pay_method-1][1]
            # 为订单赋值付款状态属性
            order.status_name = OrderInfo.ORDER_STATUS_CHOICES[order.status-1][1]
            # print(order)
            # 通过OrderInfo的外建获取子表goods的所有属性
            goods = order.skus.all()
            order.sku_list = []
            for good in goods:
                sku = good.sku
                sku.count = good.count
                sku.amount = good.count*good.price
                order.sku_list.append(sku)

        context={
            'page_orders':page_orders,
            'page_num': page_num,
            'total_page': total_page

        }



        return render(request,'user_center_order.html',context=context)

class LeaveComments(LoginRequiredView):

    def get(self,request):

        # 接收查询参数order_id
        order_id = request.GET.get('order_id')
        # 校验
        try:
            order = OrderInfo.objects.get(order_id=order_id)
            print(order)
        except OrderInfo.DoesNotExist as e:
            logger.error(e)
            return http.HttpResponseForbidden('该订单不存在')
        # 获取该订单的所有商品sku
        goods = order.skus.filter(is_commented=False)
        # print(goods)
        skus = []
        for good in goods:
            sku = good.sku
            skus.append({
                'order_id': order_id,
                # 由于后续要用到OrderGood模型属性，所以此处传入good.id，而不是sku.id
                'sku_id' : good.id,
                'default_image_url': sku.default_image.url,
                'name' : sku.name,
                'price': str(sku.price)



            })
        # 转化为json字符串
        json_skus = json.dumps(skus)
        # 序列化
        context = {
            'uncomment_goods_list' :json_skus

        }

        return render(request,'goods_judge.html',context)


    def post(self,request):
        # 将前端传来的数据,接收过来
        json_dict = json.loads(request.body.decode())
        order_id = json_dict.get('order_id')
        sku_id = json_dict.get('sku_id')
        comment = json_dict.get('comment')
        score = json_dict.get('score')
        is_anonymous = json_dict.get('is_anonymous')

        # 校验
        if not all([order_id,sku_id,comment,score]):
            return JsonResponse({'code':RETCODE.DBERR,'error': '非法请求'})
        try:
            order = OrderInfo.objects.get(order_id=order_id)
        except OrderInfo.DoesNotExist as e:
            logger.error(e)
            return JsonResponse({'code':RETCODE.DBERR,'errmsg':'order_id不存在'})






