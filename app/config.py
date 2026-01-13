"""配置管理模块"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv


def get_config_dir() -> Path:
    """获取配置目录（支持打包环境）"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包环境 - 使用用户目录
        if sys.platform == 'darwin':
            config_dir = Path.home() / 'Library' / 'Application Support' / 'ExpenseHelper'
        elif sys.platform == 'win32':
            config_dir = Path(os.environ.get('APPDATA', '')) / 'ExpenseHelper'
        else:
            config_dir = Path.home() / '.config' / 'ExpenseHelper'
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir
    else:
        # 开发环境
        return Path(__file__).parent


# 配置文件路径
CONFIG_DIR = get_config_dir()
ENV_FILE = CONFIG_DIR / ".env"

# 加载 .env 文件
load_dotenv(ENV_FILE)

# API 配置（支持硅基流动 SiliconFlow）
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.siliconflow.cn")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-ai/DeepSeek-V3")


def is_configured() -> bool:
    """检查是否已配置 API Key"""
    return bool(DEEPSEEK_API_KEY and DEEPSEEK_API_KEY != "your_api_key_here")


def save_config(api_key: str, base_url: str = None, model: str = None) -> None:
    """保存配置到 .env 文件"""
    if base_url is None:
        base_url = "https://api.siliconflow.cn"
    if model is None:
        model = "deepseek-ai/DeepSeek-V3"

    config_content = f"""# API 配置（硅基流动 SiliconFlow）
DEEPSEEK_API_KEY={api_key}
DEEPSEEK_BASE_URL={base_url}
DEEPSEEK_MODEL={model}
"""

    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write(config_content)

    # 重新加载配置
    load_dotenv(ENV_FILE, override=True)

    # 更新全局变量
    global DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
    DEEPSEEK_API_KEY = api_key
    DEEPSEEK_BASE_URL = base_url
    DEEPSEEK_MODEL = model


def setup_wizard() -> bool:
    """首次配置向导，返回是否配置成功"""
    print("\n" + "=" * 60)
    print("🎉 欢迎使用报销助手！")
    print("=" * 60)
    print("\n首次使用需要配置 API Key，只需配置一次，之后就不用再填了。\n")

    print("📖 获取 API Key 步骤：")
    print("-" * 60)
    print("1. 打开硅基流动官网注册/登录：")
    print("   👉 https://cloud.siliconflow.cn/i/Wd45d1wI")
    print("   （使用此邀请链接注册可获得额外额度）\n")
    print("2. 登录后，点击左侧菜单「API 密钥」")
    print("3. 点击「新建 API 密钥」，复制生成的密钥")
    print("-" * 60)

    print("\n请粘贴你的 API Key（输入后按回车）：")
    api_key = input().strip()

    if not api_key:
        print("\n❌ 未输入 API Key，配置取消")
        return False

    # 验证 API Key 格式（硅基流动的 key 通常以 sk- 开头）
    if not api_key.startswith("sk-"):
        print("\n⚠️  注意：API Key 通常以 'sk-' 开头，请确认是否正确")
        confirm = input("是否继续保存？[y/N]: ").strip().lower()
        if confirm != 'y':
            print("配置取消")
            return False

    # 保存配置
    save_config(api_key)

    print("\n✅ 配置已保存！之后运行将自动使用此配置。")
    print("=" * 60)

    return True


def get_api_key() -> str:
    """获取 API Key，如果未配置则启动配置向导"""
    if is_configured():
        return DEEPSEEK_API_KEY

    if setup_wizard():
        return DEEPSEEK_API_KEY

    return ""

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
