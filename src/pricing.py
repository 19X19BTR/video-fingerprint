"""
产品定价 & 套餐配置
"""

# ═══════════════════════════════════════════════
# 套餐定义
# ═══════════════════════════════════════════════

PLANS = {
    'trial': {
        'name': '免费试用',
        'credits': 20,
        'price': 0,
        'tag': '体验',
        'desc': '首次安装赠送，验证工具好用',
    },
    'basic': {
        'name': '基础版',
        'credits': 100,
        'price': 49,
        'tag': '',
        'desc': '适合个人博主，日常批量发布',
    },
    'standard': {
        'name': '标准版',
        'credits': 300,
        'price': 99,
        'tag': '🔥 热销',
        'desc': '性价比最高，多数用户首选',
    },
    'pro': {
        'name': '旗舰版',
        'credits': 800,
        'price': 149,
        'tag': '💎 超值',
        'desc': '适合 MCN / 工作室，量大从优',
    },
    'lifetime': {
        'name': '永久版',
        'credits': 0,   # 0 = 无限制
        'price': 499,
        'tag': '👑 永久',
        'desc': '一次购买，永久使用，不限条数',
    },
}


def get_plan_by_credits(credits: int) -> dict | None:
    """根据额度查找套餐"""
    for key, plan in PLANS.items():
        if plan['credits'] == credits:
            return {**plan, 'key': key}
    return None


def get_plan_by_price(price: int) -> dict | None:
    """根据价格查找套餐"""
    for key, plan in PLANS.items():
        if plan['price'] == price:
            return {**plan, 'key': key}
    return None


def format_plan_list() -> str:
    """格式化套餐列表（用于显示或打印）"""
    lines = []
    for key, plan in PLANS.items():
        if plan['price'] == 0:
            continue  # 跳过免费试用
        credits_txt = '不限量' if plan['credits'] == 0 else f"{plan['credits']}条"
        unit = f"¥{plan['price']/plan['credits']:.2f}/条" if plan['credits'] > 0 else ''
        tag = f" {plan['tag']}" if plan['tag'] else ''
        lines.append(f"{plan['name']}{tag}  {credits_txt}  ¥{plan['price']}  {unit}")
    return '\n'.join(lines)
