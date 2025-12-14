#!/bin/bash
cd "$(dirname "$0")"

clear
echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║         📋 报销助手                  ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

# 选择模式
echo "  请选择操作："
echo ""
echo "     [1] 处理新的发票（识别、分类、生成报表）"
echo "     [2] 重新生成报表（已整理好的文件夹）"
echo "     [q] 退出"
echo ""
printf "  请输入选项 [1/2/q]: "
read -r MODE

case $MODE in
    1)
        # 处理新发票
        REPORT_MODE=""
        ;;
    2)
        # 重新生成报表
        REPORT_MODE="--report"
        ;;
    q|Q)
        echo "  已退出"
        exit 0
        ;;
    *)
        REPORT_MODE=""
        ;;
esac

# 时间戳
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# 获取输入目录
echo ""
echo "  👉 把文件夹拖到这里，按回车："
echo ""
printf "     "
read -r INPUT_DIR
INPUT_DIR=$(echo "$INPUT_DIR" | sed "s/^'//" | sed "s/'$//" | sed 's/\\ / /g')

# 检查目录
if [ ! -d "$INPUT_DIR" ]; then
    echo ""
    echo "  ❌ 文件夹不存在"
    echo "  按任意键退出..."
    read -n 1
    exit 1
fi

# 如果是重新生成报表模式
if [ -n "$REPORT_MODE" ]; then
    echo ""
    echo "  ⏳ 重新生成报表..."
    echo ""
    python3 reimbursement.py --report --input "$INPUT_DIR"
else
    # 统计文件数量
    FILE_COUNT=$(find "$INPUT_DIR" -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.pdf" \) | wc -l | tr -d ' ')

    echo ""
    echo "  ┌──────────────────────────────────────┐"
    echo "  │ 📂 文件夹: $(basename "$INPUT_DIR")"
    echo "  │ 📄 找到 $FILE_COUNT 个发票文件"
    echo "  └──────────────────────────────────────┘"
    echo ""

    if [ "$FILE_COUNT" -eq 0 ]; then
        echo "  ⚠️  没有找到发票文件（jpg/png/pdf）"
        echo "  按任意键退出..."
        read -n 1
        exit 1
    fi

    # 选择处理方式
    echo "  📋 请选择处理方式："
    echo ""
    echo "     [1] 移动文件（整理后原文件夹清空）"
    echo "     [2] 复制文件（保留原文件）"
    echo "     [q] 退出"
    echo ""
    printf "  请输入选项 [1/2/q]: "
    read -r COPY_MODE

    case $COPY_MODE in
        1) COPY_FLAG="" ;;
        2) COPY_FLAG="--copy" ;;
        q|Q) echo "  已取消"; exit 0 ;;
        *) COPY_FLAG="" ;;
    esac

    # 输出目录
    INPUT_BASENAME=$(basename "$INPUT_DIR")
    INPUT_PARENT=$(dirname "$INPUT_DIR")
    OUTPUT_DIR="${INPUT_PARENT}/${INPUT_BASENAME}_报销结果_${TIMESTAMP}"

    echo ""
    echo "  ⏳ 开始处理..."
    echo ""

    python3 reimbursement.py --input "$INPUT_DIR" --output "$OUTPUT_DIR" $COPY_FLAG
fi

echo ""
echo "  ✅ 完成！"
echo ""
echo "  按任意键退出..."
read -n 1
