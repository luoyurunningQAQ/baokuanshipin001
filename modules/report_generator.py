"""
report_generator.py - 报告生成与保存模块
负责将 AI 分析结果保存为带时间戳的 Markdown 文件
"""

import os
from datetime import datetime


class ReportGenerator:
    """Markdown 报告的包装和保存"""

    def __init__(self, reports_dir: str = "reports"):
        self.reports_dir = reports_dir
        os.makedirs(reports_dir, exist_ok=True)

    def generate(self, ai_output: str, local_features: dict, video_path: str) -> str:
        """
        对 AI 输出做最后加工：
        - 如果 AI 已输出完整 Markdown，直接返回
        - 补充本地特征数据作为附录
        """
        video_name = os.path.basename(video_path) if video_path else "未知视频"

        header = f"> **分析视频**：{video_name}  \n"
        header += f"> **分析时间**：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n\n"

        # 追加本地特征附录（方便回溯）
        appendix = "\n\n---\n\n## 附录：本地技术特征\n\n"
        appendix += "| 指标 | 数值 |\n|------|------|\n"
        for key, val in local_features.items():
            if key not in ("bgm_energy_curve", "bgm_beat_timestamps", "scene_change_timestamps"):
                appendix += f"| {key} | {val} |\n"

        return header + ai_output + appendix

    def save(self, report_content: str, video_path: str) -> str:
        """
        保存报告为 Markdown 文件
        文件名格式：report_YYYYMMDD_HHMMSS_视频名.md
        返回：保存路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        video_name = os.path.splitext(os.path.basename(video_path))[0] if video_path else "unknown"
        # 清理文件名中的特殊字符
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in video_name)[:30]

        filename = f"report_{timestamp}_{safe_name}.md"
        filepath = os.path.join(self.reports_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(report_content)

        return filepath
