"""OCR 处理模块 - 提取图片和PDF中的文字"""
import os
from pathlib import Path
from typing import Optional
import fitz  # PyMuPDF
from PIL import Image
import io

from config import SUPPORTED_IMAGE_FORMATS, SUPPORTED_PDF_FORMAT


class OCRHandler:
    """OCR 处理器"""

    def __init__(self):
        self._ocr = None

    @property
    def ocr(self):
        """延迟加载 PaddleOCR（首次使用时才加载，避免启动慢）"""
        if self._ocr is None:
            from paddleocr import PaddleOCR
            # 使用中英文模型，禁用GPU（更通用）
            self._ocr = PaddleOCR(use_angle_cls=True, lang='ch', use_gpu=False, show_log=False)
        return self._ocr

    def extract_text(self, file_path: str) -> str:
        """
        从文件中提取文字

        Args:
            file_path: 文件路径（图片或PDF）

        Returns:
            提取的文字内容
        """
        file_path = Path(file_path)
        suffix = file_path.suffix.lower()

        if suffix in SUPPORTED_IMAGE_FORMATS:
            return self._extract_from_image(str(file_path))
        elif suffix == SUPPORTED_PDF_FORMAT:
            return self._extract_from_pdf(str(file_path))
        else:
            raise ValueError(f"不支持的文件格式: {suffix}")

    def _extract_from_image(self, image_path: str) -> str:
        """从图片提取文字"""
        result = self.ocr.ocr(image_path, cls=True)

        if not result or not result[0]:
            return ""

        # 提取所有识别的文字
        texts = []
        for line in result[0]:
            if line and len(line) >= 2:
                text = line[1][0]  # 获取识别的文字
                texts.append(text)

        return "\n".join(texts)

    def _extract_from_pdf(self, pdf_path: str) -> str:
        """从 PDF 提取文字"""
        texts = []

        # 打开 PDF
        doc = fitz.open(pdf_path)

        for page_num in range(len(doc)):
            page = doc[page_num]

            # 首先尝试直接提取文字（电子 PDF）
            text = page.get_text()

            if text.strip():
                texts.append(text)
            else:
                # 如果没有文字，说明是扫描件，用 OCR
                # 将页面转为图片
                pix = page.get_pixmap(dpi=200)
                img_data = pix.tobytes("png")

                # 使用 OCR 识别
                img = Image.open(io.BytesIO(img_data))
                # 保存临时文件给 PaddleOCR
                temp_path = f"/tmp/pdf_page_{page_num}.png"
                img.save(temp_path)

                ocr_text = self._extract_from_image(temp_path)
                if ocr_text:
                    texts.append(ocr_text)

                # 清理临时文件
                if os.path.exists(temp_path):
                    os.remove(temp_path)

        doc.close()
        return "\n".join(texts)

    def is_supported_file(self, file_path: str) -> bool:
        """检查文件是否支持"""
        suffix = Path(file_path).suffix.lower()
        return suffix in SUPPORTED_IMAGE_FORMATS or suffix == SUPPORTED_PDF_FORMAT


# 全局实例
ocr_handler = OCRHandler()


def extract_text_from_file(file_path: str) -> str:
    """便捷函数：从文件提取文字"""
    return ocr_handler.extract_text(file_path)


def is_supported_file(file_path: str) -> bool:
    """便捷函数：检查文件是否支持"""
    return ocr_handler.is_supported_file(file_path)
