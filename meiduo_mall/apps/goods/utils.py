def get_breadcrumb(category):

    """包装面包屑导航数据"""
    #获取一级类别
    cat1 = category.parent.parent
    # 把频道中的url赋值到一级类别的url属性上
    cat1.url = cat1.goodschannel_set.all()[0].url
    breadcrumb = {
        'cat1':cat1,
        'cat2':category.parent,
        'cat3': category
    }
    return breadcrumb