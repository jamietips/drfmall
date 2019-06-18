from django.shortcuts import render
from django.views import View

from contents.models import ContentCategory,Content
from goods.models import GoodsCategory,GoodsChannel
from .utils import get_categories

# Create your views here.
# class IndexView(View):
#
#     """首页"""
#     def get(self,request):
#         # return render(request,'index.html')
#
#     """
#         {
#             key_组号：value 这一组下面的所有一二三级
#             '1': {
#                     'channels-当前这一组中所有的一级数据' : [组1-cat1,组1-cat2...],
#                     'sub_cats':当前这一组里面的所有二级数据
#                     'sub_cats':[{id:cat2.id,name:cat2.name,sub_cats:[cats,cat3]},{}]
#
#                             cat2.id,cat.name,cat2.sub_cats:[cat3,cat3] 记录它里面的所有三级
#                     }
#             '2': {'channels':[],
#                         'sub_cats': [],
#                     }
#             }
#
#     """
#
#         # 定义一个字典变量用来包装所有商品类型数据
#         categories = {}
#         # 查询出所有的商品频道数据并且按照组号和列号进行排序
#         good_channels_qs = GoodsChannel.objects.order_by('group_id','sequence')
#         # 遍历商品频道查询集
#         for channel in good_channels_qs:
#             # 获取当前的组号
#             group_id = channel.group_id
#             # 判断当前组号再大字典中是否存在
#             if group_id not in categories:
#
#                 # 不存在就代表本组是第一次过来，准备空数据格式
#                 categories[group_id]={'channels':[],'sub_cats':[]}
#
#                 # 通过频道获取当前它对应的一级类别模型
#             cat1 = channel.category
#
#             # 把频道中url赋值给对应的一级类别模型
#             cat1.url = channel.url
#             # 把一级类别数据，添加到指定组的channels列表中
#             categories[group_id]['channels'].append(cat1)
#
#             # 获取当前一级下的所有二级
#
#             cat2_qs = cat1.subs.all()
#             # 遍历二级类型的查询集
#             for cat2 in cat2_qs:
#                 # 通过指定二级获取下它下面的所有三级
#                 cat3_qs = cat2.subs.all()
#                 # 将当前二级下的所有三级查询集保存到二级的sub_cats属性上
#                 cat2.sub_cats = cat3_qs
#
#                 # 把当前这一组下面的所有二级添加sub_cats中
#                 categories[group_id]['sub_cats'].append(cat2)
#
#         # 查询出首页广告数据
#         """
#         {
#             'index_lbt':[lbt1,lbt2,lbt3],
#             'index_kx':[]
#         }
#         """
#         # 定义一个字典用来包装所有广告数据
#         contents = {}
#         # 获取所有广告类别
#         content_category_qs = ContentCategory.objects.all()
#         # 遍历广告类别查询集构建广告数据格式
#         for cat in content_category_qs:
#             contents[cat.key]= cat.content_set.filter(status=True).order_by('sequence')
#
#         context={
#             'categories':categories, #类别数据
#             'contents':contents #广告数据
#
#         }
#
#     return render(request, 'index.html', context)

class IndexView(View):
    """首页"""


    def get(self,request):

        # 查询出首页广告数据
        """
        {
            'index_lbt': [lbt1, lbt2, lbt3],
            'index_kx' : []
        }
        """
        # 定义一个字典用来包装所有广告数据
        contents = {}
        # 获取所有广告类别
        content_category_qs = ContentCategory.objects.all()
        # 遍历广告类别查询集构建广告数据格式
        for cat in content_category_qs:
            contents[cat.key] = cat.content_set.filter(status=True).order_by('sequence')


        context = {
            'categories': get_categories(),  # 类别数据
            'contents': contents  # 广告数据
        }
        return render(request, 'index.html', context)