"""文件分类和配对模块"""
import os
import shutil
import re
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime, timedelta
from collections import defaultdict

from config import INVOICE_CATEGORIES, PENDING_CATEGORY
from invoice_analyzer import InvoiceInfo


class FileOrganizer:
    """文件组织器 - 负责分类、配对、移动/复制文件"""

    def __init__(self, output_dir: str, copy_mode: bool = False):
        self.output_dir = Path(output_dir)
        self.copy_mode = copy_mode  # True=复制, False=移动
        self._ensure_category_dirs()

    def _ensure_category_dirs(self):
        """确保分类目录存在"""
        for category_name in INVOICE_CATEGORIES.values():
            (self.output_dir / category_name).mkdir(parents=True, exist_ok=True)
        # 待确认目录
        (self.output_dir / PENDING_CATEGORY).mkdir(parents=True, exist_ok=True)

    def organize(self, invoice_infos: List[InvoiceInfo]) -> Dict[str, List[InvoiceInfo]]:
        """
        组织所有发票文件

        Args:
            invoice_infos: 发票信息列表

        Returns:
            分类后的字典 {类别: [发票信息列表]}
        """
        # 1. 配对凭证和发票
        paired_groups = self._pair_vouchers_and_invoices(invoice_infos)

        # 2. 移动文件到对应目录
        categorized = defaultdict(list)

        for group in paired_groups:
            # 获取配对组的实际消费日期（优先从凭证/行程单获取）
            group_date = ""
            has_voucher = False
            for info in group:
                if not info.is_invoice:  # 凭证/行程单
                    group_date = info.get_actual_date()
                    has_voucher = True
                    break
            # 如果没有凭证，用发票的实际消费日期
            if not group_date:
                for info in group:
                    group_date = info.get_actual_date()
                    if group_date:
                        break

            # 判断是否需要放到"待确认"目录
            # 条件：独立发票（没有配对凭证）且没有 service_date
            needs_confirmation = False
            if len(group) == 1 and group[0].is_invoice:
                # 独立发票，检查是否有实际消费日期
                if not group[0].service_date:
                    needs_confirmation = True

            # 获取分类
            if needs_confirmation:
                category_name = PENDING_CATEGORY
            else:
                category = self._get_category(group)
                category_name = INVOICE_CATEGORIES.get(category, "其他")

            # 创建子文件夹名称
            folder_name = self._generate_folder_name(group)
            target_folder = self.output_dir / category_name / folder_name

            # 确保文件夹存在
            target_folder.mkdir(parents=True, exist_ok=True)

            # 移动文件
            for idx, info in enumerate(group, 1):
                new_filename = self._generate_filename(info, idx, len(group), group_date)
                target_path = target_folder / new_filename

                # 移动文件
                self._move_file(info.file_path, target_path)

                # 更新文件路径
                info.file_path = str(target_path)
                categorized[category_name].append(info)

        return dict(categorized)

    def _pair_vouchers_and_invoices(self, invoice_infos: List[InvoiceInfo]) -> List[List[InvoiceInfo]]:
        """
        配对凭证和发票

        规则：
        1. 同一平台/商家
        2. 日期相同或相近（±1天）
        3. 金额相同或相近（±1%）
        """
        # 分离发票和凭证
        invoices = [i for i in invoice_infos if i.is_invoice]
        vouchers = [i for i in invoice_infos if not i.is_invoice]

        paired_groups = []
        used_vouchers = set()
        used_invoices = set()

        # 尝试配对
        for voucher in vouchers:
            best_match = None
            best_score = 0

            for invoice in invoices:
                if id(invoice) in used_invoices:
                    continue

                score = self._calculate_match_score(voucher, invoice)
                if score > best_score and score >= 2:  # 至少匹配2个条件
                    best_score = score
                    best_match = invoice

            if best_match:
                # 找到配对
                paired_groups.append([voucher, best_match])
                used_vouchers.add(id(voucher))
                used_invoices.add(id(best_match))
            else:
                # 未配对的凭证单独一组
                paired_groups.append([voucher])
                used_vouchers.add(id(voucher))

        # 未配对的发票单独一组
        for invoice in invoices:
            if id(invoice) not in used_invoices:
                paired_groups.append([invoice])

        return paired_groups

    def _calculate_match_score(self, voucher: InvoiceInfo, invoice: InvoiceInfo) -> int:
        """
        计算凭证和发票的匹配分数

        配对逻辑：以凭证/行程单的实际消费日期为准（因为发票可能是后补开的）
        """
        score = 0

        # 1. 平台/商家匹配（最重要）
        if self._normalize_merchant(voucher.subtype) == self._normalize_merchant(invoice.subtype):
            score += 3
        elif self._normalize_merchant(voucher.merchant) == self._normalize_merchant(invoice.merchant):
            score += 2

        # 2. 日期匹配 - 以凭证的实际消费日期为准
        # 凭证的 service_date 应该和发票的 service_date 匹配
        # 发票的开票日期(date)可能晚于实际消费日期
        voucher_date = voucher.get_actual_date()
        invoice_service_date = invoice.service_date or invoice.date

        if voucher_date and invoice_service_date:
            try:
                v_date = datetime.strptime(voucher_date, "%Y-%m-%d")
                i_date = datetime.strptime(invoice_service_date, "%Y-%m-%d")
                days_diff = abs((v_date - i_date).days)
                if days_diff == 0:
                    score += 2  # 日期完全匹配
                elif days_diff <= 1:
                    score += 1  # 相差1天也可接受
            except ValueError:
                pass

        # 3. 金额匹配
        if voucher.amount > 0 and invoice.amount > 0:
            diff = abs(voucher.amount - invoice.amount)
            max_amount = max(voucher.amount, invoice.amount)
            if diff <= max_amount * 0.01:  # 1% 误差范围内
                score += 3  # 金额完全匹配很重要
            elif diff <= max_amount * 0.05:  # 5% 误差范围内
                score += 1

        # 4. 类型匹配
        if voucher.type == invoice.type:
            score += 1

        return score

    def _normalize_merchant(self, name: str) -> str:
        """标准化商家名称"""
        if not name:
            return ""
        # 移除常见后缀和特殊字符
        name = re.sub(r'[（）()【】\[\]有限公司科技股份]', '', name)
        return name.strip().lower()

    def _get_category(self, group: List[InvoiceInfo]) -> str:
        """获取组的分类"""
        # 优先使用发票的分类
        for info in group:
            if info.is_invoice and info.type != "other":
                return info.type

        # 其次使用凭证的分类
        for info in group:
            if info.type != "other":
                return info.type

        return "other"

    def _generate_folder_name(self, group: List[InvoiceInfo]) -> str:
        """生成文件夹名称 - 以实际消费日期为准"""
        # 优先使用凭证/行程单的信息（因为它有准确的消费日期）
        # 其次使用发票的信息
        voucher_info = None
        invoice_info = None

        for info in group:
            if info.is_invoice:
                invoice_info = info
            else:
                voucher_info = info

        # 日期优先用凭证的实际消费日期
        actual_date = ""
        if voucher_info:
            actual_date = voucher_info.get_actual_date()
        if not actual_date and invoice_info:
            actual_date = invoice_info.get_actual_date()
        if not actual_date:
            actual_date = datetime.now().strftime("%Y-%m-%d")

        # 金额和商家优先用发票的（更正式）
        main_info = invoice_info or voucher_info or group[0]

        # 构建文件夹名
        parts = []

        # 日期（实际消费日期）
        parts.append(actual_date)

        # 商家/平台
        merchant = main_info.subtype or main_info.merchant or "未知"
        merchant = self._sanitize_filename(merchant)[:20]  # 限制长度
        parts.append(merchant)

        # 金额
        if main_info.amount > 0:
            parts.append(f"{main_info.amount:.2f}元")

        return "_".join(parts)

    def _generate_filename(self, info: InvoiceInfo, index: int, total: int, group_date: str = "") -> str:
        """
        生成明确的文件名
        格式: [序号_]日期_类型_商家_金额_描述.扩展名
        例如: 2024-01-15_发票_滴滴出行_35.00元_北京-上海.pdf

        Args:
            info: 发票信息
            index: 在配对组中的序号
            total: 配对组总数
            group_date: 配对组的实际消费日期（优先使用）
        """
        original_path = Path(info.file_path)
        suffix = original_path.suffix

        parts = []

        # 序号（如果是配对组）
        if total > 1:
            parts.append(f"{index:02d}")

        # 日期 - 优先使用配对组的日期（来自凭证/行程单），其次用自己的实际消费日期
        actual_date = group_date or info.get_actual_date()
        if actual_date:
            parts.append(actual_date)

        # 发票/凭证标识
        doc_type = "发票" if info.is_invoice else "凭证"
        parts.append(doc_type)

        # 商家/平台
        merchant = info.subtype or info.merchant
        if merchant:
            merchant = self._sanitize_filename(merchant)[:12]
            parts.append(merchant)

        # 金额
        if info.amount > 0:
            parts.append(f"{info.amount:.2f}元")

        # 行程描述（从 description 中提取有用信息）
        if info.description:
            # 提取行程信息（如 北京-上海、xxx到xxx）
            desc = self._extract_trip_info(info.description)
            if desc:
                desc = self._sanitize_filename(desc)[:15]
                parts.append(desc)

        filename = "_".join(parts) if parts else "未知文件"
        return f"{filename}{suffix}"

    def _extract_trip_info(self, description: str) -> str:
        """从描述中提取行程信息"""
        if not description:
            return ""

        # 尝试匹配常见的行程描述模式
        patterns = [
            r'从(.+?)到(.+?)(?:的|$)',  # 从A到B
            r'(.+?)[至到\-→](.+?)(?:的|$)',  # A至B, A到B, A-B, A→B
            r'(.+?)出发',  # A出发
        ]

        import re
        for pattern in patterns:
            match = re.search(pattern, description)
            if match:
                groups = match.groups()
                if len(groups) >= 2:
                    return f"{groups[0].strip()}-{groups[1].strip()}"
                elif len(groups) == 1:
                    return groups[0].strip()

        # 如果没有匹配到行程，返回简短描述
        desc = description[:20] if len(description) > 20 else description
        return desc

    def _sanitize_filename(self, name: str) -> str:
        """清理文件名，移除非法字符"""
        # 移除文件名非法字符
        name = re.sub(r'[<>:"/\\|?*]', '', name)
        # 移除多余空格
        name = re.sub(r'\s+', ' ', name).strip()
        return name

    def _move_file(self, src: str, dst: Path):
        """移动或复制文件"""
        src_path = Path(src)
        if src_path.exists():
            # 如果目标已存在，添加序号
            if dst.exists():
                stem = dst.stem
                suffix = dst.suffix
                counter = 1
                while dst.exists():
                    dst = dst.parent / f"{stem}_{counter}{suffix}"
                    counter += 1

            if self.copy_mode:
                shutil.copy2(str(src_path), str(dst))
                action = "复制"
            else:
                shutil.move(str(src_path), str(dst))
                action = "移动"
            print(f"  {action}: {src_path.name} -> {dst.relative_to(self.output_dir)}")
