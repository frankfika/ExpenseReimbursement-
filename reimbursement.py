#!/usr/bin/env python3
"""
报销助手 - 自动识别、分类发票并生成报销统计报表

使用方法:
    python reimbursement.py --input ./发票文件夹 --output ./报销结果
    python reimbursement.py  # 交互模式
"""
import argparse
import os
import sys
from pathlib import Path
from typing import List, Dict

from config import DEEPSEEK_API_KEY, INVOICE_CATEGORIES
from ocr_handler import extract_text_from_file, is_supported_file
from invoice_analyzer import analyze_invoice, InvoiceInfo
from file_organizer import FileOrganizer
from report_generator import generate_report


def scan_files(input_dir: str) -> List[str]:
    """扫描目录下所有支持的文件"""
    files = []
    input_path = Path(input_dir)

    if not input_path.exists():
        raise FileNotFoundError(f"目录不存在: {input_dir}")

    for file_path in input_path.rglob("*"):
        if file_path.is_file() and is_supported_file(str(file_path)):
            files.append(str(file_path))

    return sorted(files)


def normalize_category(folder_name: str) -> str:
    """
    从文件夹名称中提取标准分类名
    例如: "打车票（已完成）" -> "打车票"
         "火车票:飞机票（已完成）" -> "火车飞机票"
         "饮食-差肯德基发票（完成）" -> "餐费"
    """
    import re
    # 移除括号及其内容
    name = re.sub(r'[（(][^）)]*[）)]', '', folder_name)
    # 移除常见后缀
    name = re.sub(r'[-_].*$', '', name) if len(name) > 4 else name
    name = name.strip()

    # 分类关键词映射
    category_keywords = {
        '打车': '打车票',
        '出租': '打车票',
        '网约车': '打车票',
        '火车': '火车飞机票',
        '飞机': '火车飞机票',
        '高铁': '火车飞机票',
        '机票': '火车飞机票',
        '酒店': '住宿费',
        '住宿': '住宿费',
        '宾馆': '住宿费',
        '餐': '餐费',
        '饮食': '餐费',
        '吃饭': '餐费',
        '外卖': '餐费',
    }

    for keyword, category in category_keywords.items():
        if keyword in name:
            return category

    # 如果已经是标准分类名，直接返回
    standard_categories = ['打车票', '火车飞机票', '住宿费', '餐费', '其他', '待确认']
    for cat in standard_categories:
        if cat in folder_name:
            return cat

    return folder_name  # 保留原名


def scan_organized_dir(organized_dir: str, use_ai: bool = False, api_key: str = None) -> Dict[str, List[InvoiceInfo]]:
    """
    扫描已整理好的目录，从文件名中提取信息
    如果 use_ai=True，对于无法从文件名解析的文件，会调用 AI 分析

    目录结构：
    organized_dir/
    ├── 打车票/
    │   └── 2024-01-15_滴滴_35.00元/
    │       └── 2024-01-15_发票_滴滴_35.00元.pdf
    ├── 餐费/
    └── ...
    """
    import re
    from collections import defaultdict
    categorized = defaultdict(list)
    organized_path = Path(organized_dir)

    if not organized_path.exists():
        raise FileNotFoundError(f"目录不存在: {organized_dir}")

    # 收集所有需要处理的文件
    files_to_process = []

    # 遍历分类目录
    for category_dir in organized_path.iterdir():
        if not category_dir.is_dir():
            continue

        folder_name = category_dir.name
        if folder_name.startswith('.'):
            continue

        # 标准化分类名
        category_name = normalize_category(folder_name)

        # 遍历该分类下的所有文件
        for file_path in category_dir.rglob("*"):
            if not file_path.is_file() or not is_supported_file(str(file_path)):
                continue

            files_to_process.append((file_path, category_name))

    # 处理所有文件
    total = len(files_to_process)
    ai_analyzed_count = 0

    for idx, (file_path, category_name) in enumerate(files_to_process, 1):
        filename = file_path.stem  # 不含扩展名
        parent_folder = file_path.parent.name

        # 先尝试从文件名提取信息
        info = parse_filename(filename, str(file_path), category_name, parent_folder)

        # 如果金额为0且启用了AI，尝试用AI分析
        if use_ai and info.amount == 0:
            print(f"  [{idx}/{total}] AI 分析: {filename}...")
            ai_info = analyze_file_with_ai(str(file_path), category_name, api_key)
            if ai_info and ai_info.amount > 0:
                info = ai_info
                ai_analyzed_count += 1

        categorized[category_name].append(info)

    if use_ai and ai_analyzed_count > 0:
        print(f"  AI 分析了 {ai_analyzed_count} 个文件")

    return dict(categorized)


def parse_filename(filename: str, file_path: str, category: str, parent_folder: str = "") -> InvoiceInfo:
    """从文件名解析发票信息，如果信息不完整则尝试从父文件夹名提取"""
    import re

    # 合并文件名和父文件夹名来提取信息
    combined_text = f"{parent_folder}_{filename}"

    # 默认值
    date = ""
    service_date = ""
    amount = 0.0
    is_invoice = True
    merchant = ""
    description = ""

    # 尝试提取日期 (YYYY-MM-DD)
    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', combined_text)
    if date_match:
        date = date_match.group(1)
        service_date = date

    # 尝试提取金额 (数字+元)
    amount_match = re.search(r'(\d+\.?\d*)元', combined_text)
    if amount_match:
        amount = float(amount_match.group(1))

    # 判断是发票还是凭证
    if '凭证' in filename or '行程单' in filename:
        is_invoice = False
    elif '发票' in filename:
        is_invoice = True

    # 提取商家（在日期和金额之间的部分）
    parts = combined_text.split('_')
    for part in parts:
        if part and part not in ['发票', '凭证', '行程单', '01', '02', '03'] and not re.match(r'\d{4}-\d{2}-\d{2}', part) and '元' not in part and not part.isdigit():
            if len(part) >= 2:
                merchant = part
                break

    # 类型映射
    type_map = {
        '打车票': 'taxi',
        '火车飞机票': 'train',
        '住宿费': 'hotel',
        '餐费': 'meal',
        '其他': 'other',
        '待确认': 'other'
    }
    inv_type = type_map.get(category, 'other')

    return InvoiceInfo(
        type=inv_type,
        subtype=merchant,
        amount=amount,
        date=date,
        service_date=service_date,
        merchant=merchant,
        invoice_number="",
        is_invoice=is_invoice,
        description=description,
        raw_text="",
        file_path=file_path
    )


def analyze_file_with_ai(file_path: str, category: str, api_key: str = None) -> InvoiceInfo:
    """使用 AI 分析文件内容"""
    from ocr_handler import extract_text_from_file
    from invoice_analyzer import analyze_invoice

    try:
        # OCR 提取文字
        ocr_text = extract_text_from_file(file_path)
        if not ocr_text.strip():
            return None

        # 调用 AI 分析
        info = analyze_invoice(ocr_text, file_path, api_key)

        # 使用传入的分类覆盖（如果用户已经手动分类）
        type_map = {
            '打车票': 'taxi',
            '火车飞机票': 'train',
            '住宿费': 'hotel',
            '餐费': 'meal',
            '其他': 'other',
            '待确认': 'other'
        }
        if category in type_map:
            info.type = type_map[category]

        return info
    except Exception as e:
        print(f"  [警告] AI 分析失败: {e}")
        return None


def regenerate_report(args):
    """重新生成报表（扫描已整理好的目录）"""
    # 获取目录
    organized_dir = args.input
    if not organized_dir:
        organized_dir = input("请输入已整理好的报销结果文件夹路径: ").strip()
        if not organized_dir:
            print("错误: 未指定文件夹")
            sys.exit(1)

    organized_dir = os.path.abspath(organized_dir)
    if not os.path.isdir(organized_dir):
        print(f"错误: 目录不存在: {organized_dir}")
        sys.exit(1)

    # 获取 API Key（用于 AI 分析）
    api_key = args.api_key if hasattr(args, 'api_key') else None
    if not api_key:
        api_key = DEEPSEEK_API_KEY

    print("\n" + "=" * 50)
    print("报销助手 - 重新生成报表")
    print("=" * 50)
    print(f"扫描目录: {organized_dir}")
    print("=" * 50)

    # 询问是否使用 AI 分析
    use_ai = False
    if api_key:
        print("\n  对于文件名中没有金额信息的文件，是否使用 AI 识别？")
        print("  [1] 是（需要调用 API，较慢但准确）")
        print("  [2] 否（仅从文件名提取，快速但可能不完整）")
        choice = input("  请选择 [1/2，默认2]: ").strip()
        use_ai = choice == "1"

    # 扫描目录
    print("\n[步骤1] 扫描已整理的文件...")
    try:
        categorized = scan_organized_dir(organized_dir, use_ai=use_ai, api_key=api_key)
    except FileNotFoundError as e:
        print(f"错误: {e}")
        sys.exit(1)

    total_files = sum(len(infos) for infos in categorized.values())
    if total_files == 0:
        print("未找到任何发票文件")
        sys.exit(0)

    print(f"找到 {total_files} 个文件，{len(categorized)} 个分类")

    # 生成报表
    print("\n[步骤2] 生成统计报表...")
    report_path = generate_report(organized_dir, categorized)
    print(f"报表已生成: {report_path}")

    # 显示汇总
    print("\n" + "=" * 50)
    print("汇总如下：")
    print("=" * 50)

    total_amount = 0.0
    for category_name in ['打车票', '火车飞机票', '住宿费', '餐费', '待确认', '其他']:
        if category_name in categorized:
            infos = categorized[category_name]
            invoice_amount = sum(i.amount for i in infos if i.is_invoice)
            invoice_count = len([i for i in infos if i.is_invoice])
            if invoice_count > 0 or category_name == '待确认':
                print(f"  {category_name}: {invoice_count} 张, ¥{invoice_amount:.2f}")
                total_amount += invoice_amount

    print("-" * 50)
    print(f"  总计: ¥{total_amount:.2f}")
    print("=" * 50)
    print(f"\n统计报表: {report_path}")


def process_files(files: List[str], api_key: str = None) -> List[InvoiceInfo]:
    """处理所有文件，提取发票信息"""
    invoice_infos = []
    total = len(files)

    print(f"\n正在处理 {total} 个文件...\n")

    for idx, file_path in enumerate(files, 1):
        filename = Path(file_path).name
        print(f"[{idx}/{total}] 处理: {filename}")

        try:
            # 1. OCR 提取文字
            print(f"  - OCR 识别中...")
            ocr_text = extract_text_from_file(file_path)

            if not ocr_text.strip():
                print(f"  - [警告] 未能识别到文字")

            # 2. 调用大模型分析
            print(f"  - 分析发票内容...")
            info = analyze_invoice(ocr_text, file_path, api_key)

            # 3. 显示识别结果
            category = INVOICE_CATEGORIES.get(info.type, "其他")
            doc_type = "发票" if info.is_invoice else "凭证"
            print(f"  - 结果: [{category}] {doc_type} | {info.subtype} | ¥{info.amount:.2f}")

            invoice_infos.append(info)

        except Exception as e:
            print(f"  - [错误] 处理失败: {e}")
            # 创建错误信息
            invoice_infos.append(InvoiceInfo(
                type="other",
                subtype="处理失败",
                amount=0.0,
                date="",
                service_date="",
                merchant="",
                invoice_number="",
                is_invoice=False,
                description=f"处理失败: {str(e)}",
                raw_text="",
                file_path=file_path
            ))

    return invoice_infos


def main():
    parser = argparse.ArgumentParser(
        description="报销助手 - 自动识别、分类发票并生成报销统计报表",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python reimbursement.py --input ./发票 --output ./报销结果
  python reimbursement.py  # 交互模式

环境变量:
  DEEPSEEK_API_KEY  DeepSeek API 密钥（必需）
  DEEPSEEK_MODEL    模型名称（默认: deepseek-chat）
        """
    )

    parser.add_argument(
        "--input", "-i",
        help="发票文件夹路径"
    )
    parser.add_argument(
        "--output", "-o",
        help="输出目录路径"
    )
    parser.add_argument(
        "--api-key", "-k",
        help="DeepSeek API 密钥（也可通过环境变量 DEEPSEEK_API_KEY 设置）"
    )
    parser.add_argument(
        "--copy", "-c",
        action="store_true",
        help="复制文件而不是移动（保留原文件）"
    )
    parser.add_argument(
        "--report", "-r",
        action="store_true",
        help="仅重新生成报表（扫描已整理好的目录）"
    )

    args = parser.parse_args()

    # 如果是重新生成报表模式
    if args.report:
        regenerate_report(args)
        return

    # 获取 API Key
    api_key = args.api_key or DEEPSEEK_API_KEY
    if not api_key:
        print("错误: 请设置 DeepSeek API 密钥")
        print("  方式1: 设置环境变量 DEEPSEEK_API_KEY")
        print("  方式2: 使用 --api-key 参数")
        print("  方式3: 在 .env 文件中设置 DEEPSEEK_API_KEY=your_key")
        sys.exit(1)

    # 获取输入目录
    input_dir = args.input
    if not input_dir:
        input_dir = input("请输入发票文件夹路径: ").strip()
        if not input_dir:
            print("错误: 未指定发票文件夹")
            sys.exit(1)

    # 检查输入目录
    input_dir = os.path.abspath(input_dir)
    if not os.path.isdir(input_dir):
        print(f"错误: 目录不存在: {input_dir}")
        sys.exit(1)

    # 获取输出目录
    output_dir = args.output
    if not output_dir:
        default_output = os.path.join(os.path.dirname(input_dir), "报销结果")
        output_dir = input(f"请输入输出目录路径 [默认: {default_output}]: ").strip()
        if not output_dir:
            output_dir = default_output

    output_dir = os.path.abspath(output_dir)

    print("\n" + "=" * 50)
    print("报销助手")
    print("=" * 50)
    print(f"输入目录: {input_dir}")
    print(f"输出目录: {output_dir}")
    print("=" * 50)

    # 1. 扫描文件
    print("\n[步骤1] 扫描发票文件...")
    try:
        files = scan_files(input_dir)
    except FileNotFoundError as e:
        print(f"错误: {e}")
        sys.exit(1)

    if not files:
        print("未找到任何支持的文件（jpg/png/pdf）")
        sys.exit(0)

    print(f"找到 {len(files)} 个文件")

    # 2. 处理文件
    print("\n[步骤2] 识别发票内容...")
    invoice_infos = process_files(files, api_key)

    # 3. 分类和配对
    print("\n[步骤3] 分类和配对文件...")
    copy_mode = getattr(args, 'copy', False)
    organizer = FileOrganizer(output_dir, copy_mode=copy_mode)
    categorized = organizer.organize(invoice_infos)

    # 4. 生成报表
    print("\n[步骤4] 生成统计报表...")
    report_path = generate_report(output_dir, categorized)
    print(f"报表已生成: {report_path}")

    # 5. 显示汇总
    print("\n" + "=" * 50)
    print("处理完成！汇总如下：")
    print("=" * 50)

    total_amount = 0.0
    for category_name in ['打车票', '火车飞机票', '住宿费', '餐费', '其他']:
        if category_name in categorized:
            infos = categorized[category_name]
            invoice_amount = sum(i.amount for i in infos if i.is_invoice)
            invoice_count = len([i for i in infos if i.is_invoice])
            print(f"  {category_name}: {invoice_count} 张, ¥{invoice_amount:.2f}")
            total_amount += invoice_amount

    print("-" * 50)
    print(f"  总计: ¥{total_amount:.2f}")
    print("=" * 50)
    print(f"\n文件已整理到: {output_dir}")
    print(f"统计报表: {report_path}")


if __name__ == "__main__":
    main()
