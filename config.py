"""配置管理模块"""
import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# DeepSeek API 配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# 支持的文件格式
SUPPORTED_IMAGE_FORMATS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}
SUPPORTED_PDF_FORMAT = ".pdf"

# 发票分类
INVOICE_CATEGORIES = {
    "taxi": "打车票",
    "train": "火车飞机票",
    "flight": "火车飞机票",
    "hotel": "住宿费",
    "meal": "餐费",
    "other": "其他"
}

# 特殊分类
PENDING_CATEGORY = "待确认"  # 无法确定消费日期的发票

# 分类关键词（用于辅助识别）
CATEGORY_KEYWORDS = {
    "taxi": ["滴滴", "高德", "美团打车", "曹操", "首汽", "出租车", "网约车", "快车", "专车", "打车"],
    "train": ["12306", "火车票", "高铁", "动车", "铁路", "车票"],
    "flight": ["航空", "机票", "登机牌", "航班", "携程", "飞猪", "去哪儿"],
    "hotel": ["酒店", "宾馆", "住宿", "客房", "民宿", "如家", "汉庭", "全季", "亚朵", "希尔顿", "万豪"],
    "meal": ["餐饮", "餐厅", "饭店", "美团", "饿了么", "外卖", "午餐", "晚餐", "早餐"]
}
