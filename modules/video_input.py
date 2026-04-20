"""
video_input.py - 视频输入处理模块
负责：本地文件保存、URL 视频下载（yt-dlp）
支持抖音/小红书等需要 Cookie 的中国平台
"""

import os
import streamlit as st


# 各平台专属请求头（模拟真实浏览器，避免被拦截）
PLATFORM_HEADERS = {
    "douyin": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Referer": "https://www.douyin.com/jingxuan",
    },
    "xiaohongshu": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Referer": "https://www.xiaohongshu.com/explore",
    },
    "bilibili": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Referer": "https://www.bilibili.com/",
    },
}


def _detect_platform(url: str) -> str:
    """根据 URL 判断平台"""
    if "douyin.com" in url or "iesdouyin.com" in url:
        return "douyin"
    if "xiaohongshu.com" in url or "xhslink.com" in url or "xhs.link" in url:
        return "xiaohongshu"
    if "bilibili.com" in url or "b23.tv" in url:
        return "bilibili"
    return "other"


class VideoInputHandler:
    """处理视频的两种输入方式：本地上传 和 URL 下载"""

    def __init__(self, temp_dir: str = "temp"):
        self.temp_dir = temp_dir
        os.makedirs(temp_dir, exist_ok=True)

    def download_from_url(
        self,
        url: str,
        cookie_source: str = "不使用",
        cookie_file_path: str = "",
    ) -> str | None:
        """
        使用 yt-dlp 从 URL 下载视频到本地 temp 目录

        参数：
          cookie_source  - Cookie 来源："Chrome" / "Edge" / "Firefox" / "Cookie文件" / "不使用"
          cookie_file_path - 当 cookie_source="Cookie文件" 时，Netscape 格式的 Cookie 文件路径

        返回：本地视频路径（失败返回 None）
        """
        try:
            import yt_dlp

            platform = _detect_platform(url)
            output_template = os.path.join(self.temp_dir, "%(id)s.%(ext)s")

            ydl_opts = {
                "outtmpl": output_template,
                "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "merge_output_format": "mp4",
                "quiet": True,
                "no_warnings": True,
                "max_filesize": 500 * 1024 * 1024,
                # 网络超时设置（抖音有时响应慢）
                "socket_timeout": 60,
                "retries": 5,
                # 绕过地区限制和 SSL 检查
                "geo_bypass": True,
                "nocheckcertificate": True,
                # 不使用缓存，避免旧数据干扰
                "no_cache_dir": True,
            }

            # ── 设置平台专属请求头 ──
            if platform in PLATFORM_HEADERS:
                ydl_opts["http_headers"] = PLATFORM_HEADERS[platform]

            # ── 设置 Cookie（抖音/小红书必须，B站可选）──
            browser_map = {
                "Chrome":  ("chrome",),
                "Edge":    ("edge",),
                "Firefox": ("firefox",),
            }

            if cookie_source in browser_map:
                # 直接从浏览器读取 Cookie，无需手动导出
                ydl_opts["cookiesfrombrowser"] = browser_map[cookie_source]
            elif cookie_source == "Cookie文件" and cookie_file_path:
                if os.path.exists(cookie_file_path):
                    ydl_opts["cookiefile"] = cookie_file_path
                else:
                    st.warning(f"Cookie 文件不存在：{cookie_file_path}，将尝试不使用 Cookie 下载")

            # ── 执行下载 ──
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                base = os.path.splitext(filename)[0]
                for ext in [".mp4", ".mkv", ".webm", ".flv", ".m4v", ".ts"]:
                    candidate = base + ext
                    if os.path.exists(candidate):
                        return candidate
                # 用视频 ID 在 temp 目录中二次查找
                video_id = info.get("id", "")
                if video_id:
                    for ext in [".mp4", ".mkv", ".webm", ".flv", ".m4v", ".ts"]:
                        candidate = os.path.join(self.temp_dir, f"{video_id}{ext}")
                        if os.path.exists(candidate):
                            return candidate
                return filename if os.path.exists(filename) else None

        except ImportError:
            st.error("未安装 yt-dlp，请运行：pip install yt-dlp")
            return None
        except Exception as e:
            err_msg = str(e)
            # 针对常见错误给出友好提示
            if "cookies" in err_msg.lower() or "Fresh cookies" in err_msg:
                st.error(
                    "❌ 下载失败：需要登录 Cookie\n\n"
                    "**解决方法**：\n"
                    "1. 在侧边栏「平台 Cookie」中选择你用来登录抖音/小红书的浏览器\n"
                    "2. 确保该浏览器已登录对应平台且未过期\n"
                    "3. 重新点击「开始分析」"
                )
            elif "Private video" in err_msg or "该内容仅" in err_msg:
                st.error("❌ 下载失败：该视频为私密视频或需要特定权限，无法下载")
            else:
                st.error(f"❌ 视频下载失败：{err_msg}")
            return None

    def cleanup_temp(self, video_path: str):
        """删除临时视频文件，释放磁盘空间"""
        if video_path and os.path.exists(video_path):
            os.remove(video_path)
