"""Chinese display names for every seed-domain entity (and domain titles).

Entities are synthetic in all five domains; these are equally synthetic
Chinese renderings -- transliterations for the invented drug and company
names, translations for the descriptive endpoint / routine / operation names.
Keyed by the English display name used in the transcripts.
"""

DOMAIN_ZH = {
    "Platform API governance": "平台 API 治理",
    "Procurement compliance": "采购合规",
    "Medication constraint tracking (synthetic formulary)": "用药约束跟踪（合成药典）",
    "Household automation preferences": "家居自动化偏好",
    "Financial operation permissions": "金融操作权限",
}

ENTITY_ZH = {
    # -- devops: endpoints ---------------------------------------------------
    "orders-v1": "订单-v1", "orders-v2": "订单-v2", "orders-v3": "订单-v3",
    "billing-v1": "计费-v1", "billing-v2": "计费-v2", "billing-v3": "计费-v3",
    "search-alpha": "搜索-alpha", "search-beta": "搜索-beta", "search-ga": "搜索-GA",
    "ledger-legacy": "账本-旧版", "ledger-next": "账本-新版", "ledger-edge": "账本-边缘",
    "notify-batch": "通知-批量", "notify-stream": "通知-流式", "notify-push": "通知-推送",
    "auth-basic": "鉴权-基础", "auth-oidc": "鉴权-OIDC", "auth-mtls": "鉴权-mTLS",
    "media-cdn1": "媒体-CDN1", "media-cdn2": "媒体-CDN2", "media-origin": "媒体-源站",
    "report-sync": "报表-同步", "report-async": "报表-异步", "report-warehouse": "报表-数仓",
    # -- procurement: vendors -----------------------------------------------
    "Northgate Supply": "北门供应", "Alder & Voss": "奥德沃斯", "Merridian Labs": "梅里迪安实验室",
    "Kestrel Freight": "红隼货运", "Bluepoint Print": "蓝点印务", "Calder Metals": "考尔德金属",
    "Harrowfield Foods": "哈罗菲尔德食品", "Ivory Lane Catering": "象牙巷餐饮",
    "Juniper Fabrication": "杜松制造", "Larkmoor Textiles": "拉克摩尔纺织", "Marlowe Optics": "马洛光学",
    "Norrey Plastics": "诺里塑业", "Ostrand Tooling": "奥斯特兰工具", "Pemberly Paper": "彭伯利纸业",
    "Quillon Chemical": "奎隆化工", "Ravensmark Steel": "鸦印钢铁", "Selby Logistics": "塞尔比物流",
    "Thornwick Glass": "索恩威克玻璃", "Ubrecht Bearings": "乌布雷希特轴承",
    "Vallory Packaging": "瓦洛里包装", "Westmere Cabling": "西米尔线缆", "Yarrow Instruments": "亚罗仪器",
    "Zephrin Coatings": "泽弗林涂料", "Ashcombe Rentals": "阿什科姆租赁",
    # -- clinical: synthetic formulary --------------------------------------
    "Veltroxin": "维曲辛", "Amoradine": "阿莫拉定", "Belquinol": "贝喹诺", "Cerraphen": "塞拉芬",
    "Dolvastat": "多伐司他", "Elmirixan": "艾米瑞生", "Fenoprazil": "非诺普拉齐", "Gyrandol": "吉兰多",
    "Halovexin": "哈洛韦辛", "Iprazomide": "伊普拉唑胺", "Jendracil": "珍德拉西", "Kalmoterol": "卡莫特罗",
    "Lestafine": "莱斯他芬", "Mordacil": "莫达西", "Nuvaxetine": "努伐西汀", "Orbisant": "奥比生",
    "Pyrraline": "派拉林", "Quexadrol": "喹沙醇", "Rovastigen": "罗伐司替", "Sildaphen": "西地芬",
    "Tremacor": "特雷马可", "Uvantrel": "优凡特雷", "Vorcelide": "沃塞利德", "Xanthipex": "占替派",
    # -- smarthome: routines -------------------------------------------------
    "Full Bright": "全亮", "Warm Dim": "暖光调暗", "Movie Mode": "影院模式", "Deep Clean": "深度清洁",
    "Robot Vac": "扫地机", "Loud Doorbell": "响铃门铃", "Chime Only": "仅提示音", "Open Blinds": "开百叶",
    "Close Blinds": "关百叶", "Heat Boost": "加热增强", "Cool Blast": "强力制冷", "Eco Hold": "节能保持",
    "Kitchen Spotlight": "厨房射灯", "Hallway Path": "走廊夜灯", "Garden Flood": "花园泛光灯",
    "Sprinkler Run": "喷灌", "Pool Pump": "泳池泵", "Sauna Preheat": "桑拿预热", "Coffee Start": "咖啡机启动",
    "Oven Preheat": "烤箱预热", "Garage Open": "开车库", "Gate Unlock": "开大门", "Speaker Party": "派对音响",
    "White Noise": "白噪音",
    # -- finance: settlement operations -------------------------------------
    "Wire-Domestic": "境内电汇", "Wire-Cross": "跨境电汇", "Wire-Sameday": "当日电汇",
    "ACH-Batch": "ACH 批量", "ACH-Reversal": "ACH 冲正", "FX-Spot": "外汇即期", "FX-Forward": "外汇远期",
    "FX-Swap": "外汇掉期", "Repo-Open": "开放式回购", "Repo-Term": "定期回购", "Sweep-Nightly": "夜间归集",
    "Sweep-Intraday": "日内归集", "Card-Settle": "卡清算", "Card-Chargeback": "卡拒付",
    "Ledger-Adjust": "账务调整", "Ledger-Writeoff": "账务核销", "Escrow-Release": "托管释放",
    "Escrow-Hold": "托管冻结", "Payout-Bulk": "批量付款", "Payout-Single": "单笔付款",
    "Refund-Manual": "手动退款", "Refund-Auto": "自动退款", "Collateral-Post": "缴纳担保品",
    "Collateral-Pull": "收回担保品",
}

from .hard_ext import EXTRA_ZH  # noqa: E402
ENTITY_ZH.update(EXTRA_ZH)
