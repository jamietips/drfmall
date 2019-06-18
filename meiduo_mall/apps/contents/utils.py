from goods.models import GoodsChannel

def get_categories():
    """

            {
                key-组号：value 这一组下面的所有一二三级
                '1':{
                        'channels当前这一组中所有的一级数据':[组1-cat1,组1-cat2...],
                        'sub_cats':当前这一组里面的所有二级数据
                        'sub_cats':[{id:cat2.id,name:cat2.name,sub_cats:[cat3,cat3]},{}]
                            cat2.id,cat2.name,cat2.sub_cats:[cat3,cat3]记录它里面的所有三级
                        }

                '2':{'channel':[],
                        'sub_cats':[],
                    }

            }
            """

    # 定义一个字典变量来包装所有商品类型数据

    categories = {}
    # 查询出所有的商品频道数据并前按照组号和列号进行排序
    good_channels_qs = GoodsChannel.objects.order_by('group_id','sequence')
    # 遍历商品频道查询集

    for channel in good_channels_qs:
        # 获取当前的组号

        group_id = channel.group_id
        # 判断当前组号在大字典中是否存在
        if group_id not in categories:
            categories[group_id] = {'channels':[],'sub_cats':[]}
        # 通过频道获取当前它对应的一级类别模型
        cat1 = channel.category
        # 把频道中的url赋值给对应的一级类别模型
        cat1.url = channel.url
        # 把一级类别数据，添加到指定组channels列表中
        categories[group_id]['channels'].append(cat1)

        # 获取当前一级下的所有二级
        cat2_qs = cat1.subs.all()
        # 遍历二级类型的查询集
        for cat2 in cat2_qs:
            # 通过指定的二级获取它下面的所有三级
            cat3_qs = cat2.subs.all()
            # 将当前二级下的所有三级查询集保存到二级的sub_cats属性上
            cat2.sub_cats = cat3_qs
            # 把当前这一组下面的所有二级添加到sub_cats中
            categories[group_id]['sub_cats'].append(cat2)
    return categories