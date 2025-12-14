"""发票分析模块 - 调用 DeepSeek API 分析发票内容"""
import json
import re
from dataclasses import dataclass, asdict
from typing import Optional
import requests

from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL


@dataclass
class InvoiceInfo:
    """发票信息"""
    type: str  # taxi, train, flight, hotel, meal, other
    subtype: str  # 具体类型，如"滴滴出行"、"12306"等
    amount: float  # 金额
    date: str  # 开票日期 YYYY-MM-DD
    service_date: str  # 实际消费/服务日期 YYYY-MM-DD（打车时间、入住时间等）
    merchant: str  # 商家名称
    invoice_number: str  # 发票号码
    is_invoice: bool  # True=发票, False=凭证/行程单
    description: str  # 简要描述
    raw_text: str  # 原始OCR文字
    file_path: str  # 文件路径

    def to_dict(self) -> dict:
        return asdict(self)

    def get_actual_date(self) -> str:
        """获取实际消费日期（优先 service_date）"""
        return self.service_date or self.date or ""


class InvoiceAnalyzer:
    """发票分析器"""

    SYSTEM_PROMPT = """你是一个专业的发票识别助手。请分析以下发票/凭证的OCR文字内容，提取关键信息。

请严格按照以下JSON格式返回，不要返回其他内容：
{
    "type": "taxi|train|flight|hotel|meal|other",
    "subtype": "具体平台或类型，如滴滴出行、12306、XX航空、XX酒店、XX餐厅等",
    "amount": 123.45,
    "date": "YYYY-MM-DD",
    "service_date": "YYYY-MM-DD",
    "merchant": "商家/公司名称",
    "invoice_number": "发票号码，如果没有则为空字符串",
    "is_invoice": true或false,
    "description": "简要描述这是什么"
}

分类说明：
- taxi: 出租车、网约车（滴滴、高德、美团打车等）
- train: 火车票（12306、高铁、动车等）
- flight: 机票（各航空公司、机场）
- hotel: 住宿（酒店、宾馆、民宿）
- meal: 餐饮（餐厅、外卖）
- other: 其他类型

is_invoice 说明：
- true: 这是正式发票（有发票代码、发票号码、税额等）
- false: 这是行程单、收据、凭证等非正式发票

日期说明（非常重要）：
- date: 开票日期（发票上的开票时间）
- service_date: 实际消费/服务日期，这是最重要的日期！
  - 打车：乘车时间、行程开始时间
  - 火车/飞机：乘车/乘机日期、出发时间
  - 酒店：入住日期
  - 餐饮：消费日期
  - 注意：发票可能是后补开的，开票日期可能晚于实际消费日期

注意：
1. 金额请提取实际支付金额，不是税额
2. 日期请转换为 YYYY-MM-DD 格式
3. service_date 比 date 更重要，请优先准确提取实际消费日期
4. 如果某字段无法识别，请合理推断或留空
5. 只返回JSON，不要有其他文字"""

    def __init__(self, api_key: str = None, base_url: str = None):
        self.api_key = api_key or DEEPSEEK_API_KEY
        self.base_url = base_url or DEEPSEEK_BASE_URL

        if not self.api_key:
            raise ValueError("请设置 DEEPSEEK_API_KEY 环境变量或传入 api_key")

    def analyze(self, ocr_text: str, file_path: str) -> InvoiceInfo:
        """
        分析发票内容

        Args:
            ocr_text: OCR 提取的文字
            file_path: 文件路径

        Returns:
            InvoiceInfo 对象
        """
        if not ocr_text.strip():
            return self._create_empty_info(file_path, "无法识别内容")

        # 调用 DeepSeek API
        try:
            result = self._call_api(ocr_text)
            return self._parse_result(result, ocr_text, file_path)
        except Exception as e:
            print(f"  [警告] 分析失败: {e}")
            return self._create_empty_info(file_path, f"分析失败: {str(e)}", ocr_text)

    def _call_api(self, ocr_text: str) -> dict:
        """调用 DeepSeek API"""
        url = f"{self.base_url}/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "model": DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": f"请分析以下发票内容：\n\n{ocr_text}"}
            ],
            "temperature": 0.1,  # 低温度，更确定性的输出
            "max_tokens": 1000
        }

        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()

        result = response.json()
        content = result["choices"][0]["message"]["content"]

        # 解析 JSON
        # 尝试从响应中提取 JSON
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            return json.loads(json_match.group())
        else:
            raise ValueError(f"无法从响应中提取JSON: {content}")

    def _parse_result(self, result: dict, ocr_text: str, file_path: str) -> InvoiceInfo:
        """解析 API 返回结果"""
        return InvoiceInfo(
            type=result.get("type", "other"),
            subtype=result.get("subtype", "未知"),
            amount=float(result.get("amount", 0) or 0),
            date=result.get("date", ""),
            service_date=result.get("service_date", ""),
            merchant=result.get("merchant", ""),
            invoice_number=result.get("invoice_number", ""),
            is_invoice=result.get("is_invoice", True),
            description=result.get("description", ""),
            raw_text=ocr_text,
            file_path=file_path
        )

    def _create_empty_info(self, file_path: str, description: str, ocr_text: str = "") -> InvoiceInfo:
        """创建空的发票信息"""
        return InvoiceInfo(
            type="other",
            subtype="未识别",
            amount=0.0,
            date="",
            service_date="",
            merchant="",
            invoice_number="",
            is_invoice=False,
            description=description,
            raw_text=ocr_text,
            file_path=file_path
        )


# 全局实例（延迟初始化）
_analyzer = None


def get_analyzer(api_key: str = None) -> InvoiceAnalyzer:
    """获取分析器实例"""
    global _analyzer
    if _analyzer is None:
        _analyzer = InvoiceAnalyzer(api_key)
    return _analyzer


def analyze_invoice(ocr_text: str, file_path: str, api_key: str = None) -> InvoiceInfo:
    """便捷函数：分析发票"""
    analyzer = get_analyzer(api_key)
    return analyzer.analyze(ocr_text, file_path)
