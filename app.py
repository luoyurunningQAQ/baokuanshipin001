"""
AutoViral AI - 汽车品牌爆款视频分析系统 v3
面向汽车品牌产品经理，分析爆款视频规律，生成可复用的拍摄脚本。
v3 新增：KOC 人设引擎（批量建档 + 风格迁移 + 定制执行手册）
"""

import json
import os

import streamlit as st

from modules.koc_profiler import KOCProfiler
from modules.video_input import VideoInputHandler
from modules.ai_analysis import AIAnalyzer
from modules.local_analysis import LocalAnalyzer
from modules.report_generator import ReportGenerator
from modules.cookie_helper import extract_and_save, get_saved_cookie_file, get_cookie_file_mtime

# ─────────────────────────────────────────────
# 页面基础配置
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="AutoViral AI",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# Session State 初始化
# ─────────────────────────────────────────────
DEFAULTS = {
    "api_provider":       "本地模式（无需API）",
    "api_key":            "",
    "api_saved":          False,
    "cookie_source":      "未配置",
    "cookie_file_path":   "",
    "asr_ocr_cache":      {},   # {video_path: {asr/ocr 字段}} 避免同一视频重复提取
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ─────────────────────────────────────────────
# 侧边栏：系统配置
# ─────────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        st.title("⚙️ 系统配置")
        st.markdown("---")

        # ── AI 模型 ──
        st.subheader("🤖 AI 模型")
        provider = st.selectbox(
            "选择分析引擎",
            options=[
                "本地模式（无需API）",
                "通义千问（阿里云）",
                "GPT-4o（OpenAI）",
                "Gemini 1.5 Pro（Google）",
            ],
            index=["本地模式（无需API）", "通义千问（阿里云）", "GPT-4o（OpenAI）", "Gemini 1.5 Pro（Google）"].index(
                st.session_state.api_provider
                if st.session_state.api_provider in ["本地模式（无需API）", "通义千问（阿里云）", "GPT-4o（OpenAI）", "Gemini 1.5 Pro（Google）"]
                else "本地模式（无需API）"
            ),
            help="本地模式：基础视觉/音频分析，速度快；API 模式：完整台词/类型/风格迁移分析",
        )

        api_key = ""
        if provider != "本地模式（无需API）":
            hints = {
                "通义千问（阿里云）": ("sk-...", "阿里云百炼控制台 → API Key 管理"),
                "GPT-4o（OpenAI）":  ("sk-...", "platform.openai.com → API Keys"),
                "Gemini 1.5 Pro（Google）": ("AIza...", "aistudio.google.com → API Keys"),
            }
            placeholder, help_text = hints.get(provider, ("", ""))
            api_key = st.text_input(
                "API Key", value=st.session_state.api_key,
                type="password", placeholder=placeholder, help=help_text,
            )

        # ── Cookie ──
        st.markdown("---")
        st.subheader("🍪 平台 Cookie")
        st.caption("下载抖音/小红书视频必须配置，B站可不配置")

        cookie_source = st.selectbox(
            "登录抖音所用浏览器",
            options=["未配置", "Chrome", "Edge", "Firefox"],
            index=["未配置", "Chrome", "Edge", "Firefox"].index(
                st.session_state.cookie_source
                if st.session_state.cookie_source in ["未配置", "Chrome", "Edge", "Firefox"]
                else "未配置"
            ),
        )

        if cookie_source != "未配置":
            existing_file = get_saved_cookie_file(cookie_source)
            mtime         = get_cookie_file_mtime(cookie_source)
            if existing_file:
                st.success(f"✅ Cookie 已提取（{mtime}）")
            else:
                st.warning("⚠️ 尚未提取，点击下方按钮")

            if st.button(f"🔑 一键提取 {cookie_source} Cookie", use_container_width=True):
                with st.spinner(f"正在从 {cookie_source} 提取 Cookie..."):
                    ok, result = extract_and_save(cookie_source)
                if ok:
                    st.session_state.cookie_file_path = result
                    st.success(f"✅ 提取成功：{result}")
                    st.rerun()
                else:
                    st.error(result)

            with st.expander("无法提取？改用手动导出"):
                st.markdown(
                    "1. Chrome 安装插件：Get cookies.txt LOCALLY\n"
                    "2. 打开 douyin.com 并确保已登录\n"
                    "3. 导出 cookies.txt 并填入路径"
                )
                manual_path = st.text_input(
                    "Cookie 文件路径",
                    value=st.session_state.cookie_file_path,
                    placeholder=r"C:\Users\你的用户名\Downloads\cookies.txt",
                )
                if st.button("使用此文件", use_container_width=True):
                    st.session_state.cookie_file_path = manual_path
                    st.success("已设置！")

        if st.button("💾 保存配置", use_container_width=True):
            st.session_state.api_provider  = provider
            st.session_state.api_key       = api_key
            st.session_state.api_saved     = True
            st.session_state.cookie_source = cookie_source
            st.success("配置已保存！")

        # ── 状态展示 ──
        st.markdown("---")
        st.subheader("📊 当前状态")
        if st.session_state.api_provider == "本地模式（无需API）":
            st.info("🖥️ 本地分析模式")
        elif st.session_state.api_key:
            st.success(f"✅ {st.session_state.api_provider}")
        else:
            st.warning("⚠️ 未填写 API Key")

        cookie_src = st.session_state.cookie_source
        if cookie_src in ["Chrome", "Edge", "Firefox"] and get_saved_cookie_file(cookie_src):
            st.success(f"🍪 Cookie 就绪（{cookie_src}）")
        elif st.session_state.cookie_file_path:
            st.success("🍪 使用手动 Cookie 文件")
        else:
            st.warning("🍪 未配置 Cookie（抖音链接将失败）")

        # ── KOC 档案统计 ──
        st.markdown("---")
        st.subheader("👤 KOC 档案库")
        profiler = KOCProfiler()
        profiles = profiler.list_profiles()
        if profiles:
            st.metric("已保存档案", len(profiles))
            for name in profiles:
                p = profiler.load_profile(name)
                genre = p.get("content_genre", "") if p else ""
                n_vids = p.get("videos_analyzed", 1) if p else 1
                st.caption(f"· {name}  {genre}  [{n_vids}v]")
        else:
            st.caption("暂无 KOC 档案")

        st.markdown("---")
        st.caption("AutoViral AI v3.0 | KOC 人设引擎")


# ─────────────────────────────────────────────
# 主区域：标签页
# ─────────────────────────────────────────────
def render_main():
    st.title("🚗 AutoViral AI")
    st.markdown("**汽车品牌爆款视频分析系统** v3 · 台词优先 · 类型感知 · KOC 人设引擎")
    st.markdown("---")

    tab_analysis, tab_koc, tab_reports = st.tabs([
        "🔍 爆款分析",
        "👤 KOC 档案管理",
        "📄 历史报告",
    ])

    with tab_analysis:
        render_tab_analysis()
    with tab_koc:
        render_tab_koc()
    with tab_reports:
        render_tab_reports()


# ─────────────────────────────────────────────
# KOC 摘要卡片（分析 Tab 内使用）
# ─────────────────────────────────────────────
def render_koc_summary_card(profile: dict):
    """在分析 Tab 中展示 KOC 人设摘要卡片"""
    lang = profile.get("language_dna", {})
    vis  = profile.get("visual_signature", {})
    core = profile.get("core_value", {})
    mech = profile.get("viral_mechanics", {})

    with st.container(border=True):
        koc_name = profile.get("koc_name", "KOC")
        genre    = profile.get("content_genre", "—")
        n_vids   = profile.get("videos_analyzed", 1)
        st.markdown(f"##### 👤 {koc_name} · {genre}")
        st.caption(f"基于 {n_vids} 个视频分析 · 更新于 {profile.get('updated_at','—')}")

        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("语言风格", lang.get("tone", "—"))
            dialect = lang.get("dialect", "未检测到")
            st.caption(f"方言：{dialect}")
        with c2:
            st.metric("剪辑节奏", f"{vis.get('avg_shot_duration','—')}s/镜")
            st.caption(vis.get("editing_pace", "—"))
        with c3:
            st.metric("钩子类型", mech.get("hook_type", "—"))
            st.caption(mech.get("hook_formula", "—")[:30] + "…" if mech.get("hook_formula", "") else "—")

        phrases = lang.get("catchphrases", [])
        if phrases:
            st.markdown("**口头禅**：" + "  ·  ".join(f"`{p}`" for p in phrases[:3]))

        st.caption(
            f"**核心方向**：{core.get('primary_topic','—')}  |  "
            f"**受众**：{core.get('target_audience','—')[:30]}…"
            if len(core.get("target_audience","")) > 30
            else f"**核心方向**：{core.get('primary_topic','—')}  |  **受众**：{core.get('target_audience','—')}"
        )


# ─────────────────────────────────────────────
# 标签页1：爆款分析
# ─────────────────────────────────────────────
def render_tab_analysis():
    st.subheader("🔍 爆款视频分析")
    st.markdown("上传或输入视频，AI 分析爆款规律；可选择 KOC 人设适配，生成定制执行手册。")

    col_input, col_koc = st.columns([2, 1])

    # ── 视频输入 ──
    with col_input:
        st.markdown("#### 📹 视频输入")
        input_mode = st.radio("输入方式", ["上传本地文件", "输入视频URL"], horizontal=True)

        video_path = None
        video_url  = None

        if input_mode == "上传本地文件":
            uploaded = st.file_uploader(
                "选择 MP4 文件",
                type=["mp4", "mov", "avi"],
                help="支持 MP4、MOV、AVI，建议 < 500MB",
            )
            if uploaded:
                os.makedirs("temp", exist_ok=True)
                temp_path = f"temp/{uploaded.name}"
                with open(temp_path, "wb") as f:
                    f.write(uploaded.getbuffer())
                video_path = temp_path
                st.success(f"✅ 已上传：{uploaded.name}")
        else:
            video_url = st.text_input(
                "视频链接",
                placeholder="支持 B站、抖音、YouTube 等平台链接",
            )

    # ── KOC 人设适配 ──
    with col_koc:
        st.markdown("#### 👤 KOC 人设适配")
        profiler = KOCProfiler()
        profiles = profiler.list_profiles()

        apply_persona = False
        koc_profile   = None

        if profiles:
            selected_koc = st.selectbox(
                "选择 KOC",
                options=["不使用 KOC 档案"] + profiles,
                help="选择已建档的 KOC，AI 将为其生成定制执行手册",
            )

            if selected_koc != "不使用 KOC 档案":
                koc_profile = profiler.load_profile(selected_koc)
                if koc_profile:
                    apply_persona = st.toggle(
                        "🎭 应用 KOC 人设适配",
                        value=True,
                        help=(
                            "**开启**：生成「KOC 定制执行手册」"
                            "（风格迁移 + 逐镜脚本 + 导演手记）\n\n"
                            "**关闭**：生成标准爆款分析报告，KOC 档案仅作参考"
                        ),
                    )
                    render_koc_summary_card(koc_profile)
        else:
            selected_koc = "不使用 KOC 档案"
            st.info("暂无 KOC 档案\n\n请先到「KOC 档案管理」标签页建立档案")

        if not apply_persona and selected_koc != "不使用 KOC 档案" and koc_profile:
            st.caption("ℹ️ KOC 档案已加载，将作为分析参考（非风格迁移模式）")

    st.markdown("---")

    # ── 分析按钮 ──
    col_btn, col_tip = st.columns([1, 3])
    with col_btn:
        btn_label = "🎭 生成定制执行手册" if apply_persona else "🚀 开始分析"
        analyze_btn = st.button(
            btn_label,
            use_container_width=True,
            type="primary",
            disabled=(not video_path and not video_url),
        )
    with col_tip:
        if not video_path and not video_url:
            st.markdown("*请先上传视频或输入链接*")
        elif apply_persona:
            st.markdown(f"*将为 **{selected_koc}** 生成定制执行手册*")

    if analyze_btn:
        if apply_persona and koc_profile:
            _run_adapted_analysis(video_path, video_url, koc_profile)
        else:
            koc_context = ""
            if koc_profile:
                koc_context = json.dumps(koc_profile, ensure_ascii=False)
            _run_analysis(video_path, video_url, koc_context)


# ─────────────────────────────────────────────
# 爆款分析流程（标准模式）
# ─────────────────────────────────────────────
def _run_analysis(video_path, video_url, koc_context=""):
    """执行标准爆款分析流程（5步）"""
    handler      = VideoInputHandler()
    analyzer     = AIAnalyzer(provider=st.session_state.api_provider, api_key=st.session_state.api_key)
    local_analyzer = LocalAnalyzer()
    report_gen   = ReportGenerator()
    profiler     = KOCProfiler()

    with st.status("正在处理视频...", expanded=True) as status:
        st.write("📥 Step 1/5：获取视频文件...")
        if video_url:
            cookie_src  = st.session_state.cookie_source
            cookie_file = get_saved_cookie_file(cookie_src) or st.session_state.cookie_file_path
            if cookie_file:
                st.write("🍪 使用已提取的 Cookie 文件...")
            video_path = handler.download_from_url(
                video_url,
                cookie_source="Cookie文件" if cookie_file else cookie_src,
                cookie_file_path=cookie_file,
            )
            if not video_path:
                status.update(label="❌ 视频下载失败", state="error")
                return
        st.write(f"✅ 视频就绪：{video_path}")

        st.write("🔬 Step 2/5：本地视觉+音频特征提取...")
        local_features = local_analyzer.extract_features(video_path)
        st.write(
            f"✅ 镜头切换 {local_features.get('scene_changes', 0)} 次 · "
            f"BGM {local_features.get('bgm_tempo_bpm', '—')} BPM"
        )

        asr_status = local_features.get("asr_status", "not_installed")
        ocr_status = local_features.get("ocr_status", "not_installed")

        # ── 当本地 ASR/OCR 未安装时，通过 API 自动提取 ──────────────────────
        needs_api_enhance = (
            (asr_status in ("not_installed", "error") or ocr_status in ("not_installed", "error"))
            and bool(st.session_state.api_key)
            and "本地模式" not in st.session_state.api_provider
        )
        # 命中缓存则直接复用（同一视频路径不重复调用 API）
        _cache_key = video_path
        if needs_api_enhance and _cache_key in st.session_state.asr_ocr_cache:
            local_features.update(st.session_state.asr_ocr_cache[_cache_key])
            asr_status = local_features.get("asr_status", "not_installed")
            ocr_status = local_features.get("ocr_status", "not_installed")
            st.write(f"✅ Step 3/5：ASR/OCR 命中缓存 [{asr_status}] [{ocr_status}]（跳过重新提取）")
            needs_api_enhance = False

        if needs_api_enhance:
            st.write(f"🎯 Step 3/5：API 语义提取（{st.session_state.api_provider}）...")

            def _asr_ocr_step(msg):
                st.write(f"   {msg}")

            local_features = analyzer.enhance_with_api_asr_ocr(
                video_path, local_features, on_step=_asr_ocr_step
            )
            # 缓存结果
            st.session_state.asr_ocr_cache[_cache_key] = {
                k: local_features.get(k) for k in [
                    "speech_transcript", "asr_status", "speech_dialect",
                    "screen_texts", "ocr_status",
                ]
            }
            asr_status = local_features.get("asr_status", "not_installed")
            ocr_status = local_features.get("ocr_status", "not_installed")
            transcript_len = len(local_features.get("speech_transcript", ""))
            st.write(
                f"✅ 语义提取完成：台词 {transcript_len} 字 [{asr_status}]"
                + (f" · {local_features.get('speech_dialect', '')}方言"
                   if local_features.get("speech_dialect") else "")
                + f" · OCR [{ocr_status}]"
            )
        else:
            st.write(
                f"🎤 Step 3/5：ASR 台词识别 [{asr_status}] + "
                f"OCR 屏幕文字 [{ocr_status}]"
            )
            if asr_status == "success":
                transcript = local_features.get("speech_transcript", "")
                st.write(f"✅ ASR 转写完成（{len(transcript)} 字）"
                         + (f" · 检测到{local_features.get('speech_dialect','')}方言"
                            if local_features.get("speech_dialect") else ""))
            elif asr_status == "not_installed":
                st.warning("⚠️ openai-whisper 未安装（配置 API Key 后可自动通过 API 提取台词）")

        st.write(f"🤖 Step 4/5：AI 深度分析（{st.session_state.api_provider}）...")
        koc_context_display = ""
        if koc_context:
            koc_name_display = json.loads(koc_context).get("koc_name", "KOC")
            st.write(f"✅ 已加载 KOC 档案：{koc_name_display}（作为分析参考）")
            koc_context_display = koc_context

        analysis_result = analyzer.analyze_viral_video(
            video_path=video_path,
            local_features=local_features,
            koc_context=koc_context_display,
        )

        st.write("📝 Step 5/5：生成结构化报告...")
        report = report_gen.generate(analysis_result, local_features, video_path)
        status.update(label="✅ 分析完成！", state="complete")

    st.markdown("---")
    st.markdown("## 📊 分析报告")
    st.markdown(report)

    report_path = report_gen.save(report, video_path)
    st.download_button(
        "⬇️ 下载报告（Markdown）",
        data=report,
        file_name=os.path.basename(report_path),
        mime="text/markdown",
    )


# ─────────────────────────────────────────────
# KOC 人设适配分析流程（v3 新增）
# ─────────────────────────────────────────────
def _run_adapted_analysis(video_path, video_url, koc_profile: dict):
    """执行 KOC 风格迁移分析，生成「定制执行手册」"""
    handler        = VideoInputHandler()
    analyzer       = AIAnalyzer(provider=st.session_state.api_provider, api_key=st.session_state.api_key)
    local_analyzer = LocalAnalyzer()
    report_gen     = ReportGenerator()

    koc_name = koc_profile.get("koc_name", "KOC")

    with st.status(f"正在为 {koc_name} 生成定制执行手册...", expanded=True) as status:
        st.write("📥 Step 1/3：获取视频文件...")
        if video_url:
            cookie_src  = st.session_state.cookie_source
            cookie_file = get_saved_cookie_file(cookie_src) or st.session_state.cookie_file_path
            video_path  = handler.download_from_url(
                video_url,
                cookie_source="Cookie文件" if cookie_file else cookie_src,
                cookie_file_path=cookie_file,
            )
            if not video_path:
                status.update(label="❌ 视频下载失败", state="error")
                return
        st.write(f"✅ 视频就绪：{video_path}")

        st.write("🔬 Step 2/3：特征提取（视觉 + 音频 + ASR + OCR）...")
        local_features = local_analyzer.extract_features(video_path)
        asr_st = local_features.get("asr_status", "not_installed")
        ocr_st = local_features.get("ocr_status", "not_installed")
        st.write(
            f"✅ 镜头 {local_features.get('scene_changes', 0)} 次 · "
            f"BGM {local_features.get('bgm_tempo_bpm', '—')} BPM · "
            f"ASR [{asr_st}]"
        )

        # ── API 语义增强（ASR/OCR）────────────────────────────────────────────
        _needs_api = (
            (asr_st in ("not_installed", "error") or ocr_st in ("not_installed", "error"))
            and bool(st.session_state.api_key)
            and "本地模式" not in st.session_state.api_provider
        )
        _cache_key = video_path
        if _needs_api and _cache_key in st.session_state.asr_ocr_cache:
            local_features.update(st.session_state.asr_ocr_cache[_cache_key])
            asr_st = local_features.get("asr_status", "not_installed")
            st.write(f"✅ ASR/OCR 命中缓存 [{asr_st}]（跳过重新提取）")
            _needs_api = False

        if _needs_api:
            st.write(f"🎯 API 语义提取（台词 + 屏幕文字）...")

            def _asr_ocr_step_a(msg):
                st.write(f"   {msg}")

            local_features = analyzer.enhance_with_api_asr_ocr(
                video_path, local_features, on_step=_asr_ocr_step_a
            )
            st.session_state.asr_ocr_cache[_cache_key] = {
                k: local_features.get(k) for k in [
                    "speech_transcript", "asr_status", "speech_dialect",
                    "screen_texts", "ocr_status",
                ]
            }
            asr_st = local_features.get("asr_status", "not_installed")
            ocr_st = local_features.get("ocr_status", "not_installed")
            st.write(f"✅ 语义提取完成：ASR [{asr_st}] · OCR [{ocr_st}]")

        st.write(f"🎭 Step 3/3：风格迁移分析 → {koc_name} 定制版（{st.session_state.api_provider}）...")
        adapted_report = analyzer.generate_adapted_script(
            local_features=local_features,
            koc_profile=koc_profile,
        )

        report = report_gen.generate(adapted_report, local_features, video_path)
        status.update(label=f"✅ {koc_name} 定制执行手册生成完毕！", state="complete")

    st.markdown("---")
    st.markdown(f"## 🎭 KOC 定制执行手册 · {koc_name}")
    st.markdown(report)

    report_path = report_gen.save(report, video_path)
    st.download_button(
        f"⬇️ 下载定制手册（Markdown）",
        data=report,
        file_name=os.path.basename(report_path),
        mime="text/markdown",
    )


# ─────────────────────────────────────────────
# 标签页2：KOC 档案管理（v3 重写）
# ─────────────────────────────────────────────
def render_tab_koc():
    st.subheader("👤 KOC 档案管理")
    st.markdown(
        "上传 **5-10 个**代表视频，AI 提取完整人设 DNA（语言风格、视觉签名、核心价值、爆款机制）。"
        "档案一次建立，长期复用。"
    )

    # 建档成功后通过 session_state 传递提示（st.rerun 后显示）
    _created_name = st.session_state.pop("koc_just_created", None)
    _created_summary = st.session_state.pop("koc_created_summary", None)
    if _created_name:
        st.success(f"✅ KOC 档案「{_created_name}」已建立！共分析 {_created_summary.get('videos', '?')} 个视频。")
        if _created_summary:
            c1, c2, c3, c4 = st.columns(4)
            with c1: st.metric("内容类型", _created_summary.get("content_genre", "—"))
            with c2: st.metric("语言风格", _created_summary.get("tone", "—"))
            with c3: st.metric("方言", _created_summary.get("dialect", "—"))
            with c4: st.metric("分析视频数", _created_summary.get("videos", "—"))
            _phrases = _created_summary.get("catchphrases", [])
            if _phrases:
                st.markdown("**识别到的口头禅**：" + "  ·  ".join(f"`{p}`" for p in _phrases))

    profiler = KOCProfiler()
    col_create, col_view = st.columns([1, 1])

    # ── 建立新档案 ──
    with col_create:
        st.markdown("#### ➕ 建立新档案")

        koc_name = st.text_input(
            "KOC 名称",
            placeholder="例如：张老师汽车频道",
            help="唯一标识，将作为档案文件名",
        )

        input_mode = st.radio(
            "视频来源",
            ["📁 上传本地文件（推荐）", "🔗 输入视频链接"],
            horizontal=True,
        )

        koc_files = []
        koc_urls  = []

        if "上传本地文件" in input_mode:
            koc_files = st.file_uploader(
                "上传代表视频（5-10 个，越多越准）",
                type=["mp4", "mov", "avi"],
                accept_multiple_files=True,
                key="koc_batch_upload",
                help="建议上传 5-10 个最能代表该 KOC 风格的视频",
            )
            if koc_files:
                st.caption(f"✅ 已选择 {len(koc_files)} 个文件")
                if len(koc_files) < 3:
                    st.warning("⚠️ 建议至少上传 3 个视频以获得更准确的人设分析")
        else:
            urls_text = st.text_area(
                "视频链接（每行一个，5-10 条）",
                height=130,
                placeholder="https://www.bilibili.com/video/...\nhttps://v.douyin.com/...",
            )
            if urls_text.strip():
                koc_urls = [u.strip() for u in urls_text.strip().split("\n") if u.strip()]
                st.caption(f"✅ 已输入 {len(koc_urls)} 条链接")

        koc_notes = st.text_area(
            "补充说明（可选）",
            placeholder="例如：专注新能源 SUV，受众 25-35 岁男性，擅长东北话幽默",
            height=80,
        )

        btn_disabled = not koc_name or (not koc_files and not koc_urls)
        if st.button(
            "🔍 分析并建立人设档案",
            type="primary",
            disabled=btn_disabled,
            use_container_width=True,
        ):
            _create_koc_profile_batch(profiler, koc_name, koc_files, koc_urls, koc_notes)

    # ── 查看现有档案 ──
    with col_view:
        st.markdown("#### 📋 现有档案")
        profiles = profiler.list_profiles()

        if not profiles:
            st.info("暂无档案\n\n请在左侧建立第一个 KOC 档案")
        else:
            sel_col, del_col = st.columns([4, 1])
            with sel_col:
                selected = st.selectbox("选择查看", profiles, key="koc_view_select")
            with del_col:
                st.write("")  # 与 selectbox 对齐的垂直间距
                if st.button(
                    "🗑️ 删除",
                    key="koc_inline_delete_btn",
                    type="secondary",
                    use_container_width=True,
                    help="删除当前选中的 KOC 档案",
                ):
                    if selected:
                        profiler.delete_profile(selected)
                        st.session_state.pop("koc_view_select", None)
                        st.rerun()
            if selected:
                render_koc_profile_detail(profiler, selected)


def render_koc_profile_detail(profiler: KOCProfiler, koc_name: str):
    """展示 KOC 档案详细信息（带分区展示）"""
    profile = profiler.load_profile(koc_name)
    if not profile:
        st.error("档案不存在")
        return

    lang = profile.get("language_dna", {})
    vis  = profile.get("visual_signature", {})
    core = profile.get("core_value", {})
    mech = profile.get("viral_mechanics", {})

    st.markdown(
        f"**{profile.get('content_genre','—')}** · "
        f"分析视频数：**{profile.get('videos_analyzed', 1)}** 个 · "
        f"更新于 {profile.get('updated_at','—')}"
    )

    # Language DNA
    with st.expander("🧬 语言 DNA", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            st.metric("语言风格", lang.get("tone", "—"))
            st.metric("方言", lang.get("dialect", "未检测到"))
        with c2:
            st.metric("句长特征", lang.get("avg_sentence_length", "—"))
            st.metric("声音特点", lang.get("voice_characteristics", "—"))

        phrases = lang.get("catchphrases", [])
        if phrases:
            st.markdown("**标志性口头禅**")
            for p in phrases:
                st.code(p, language=None)

        openings = lang.get("opening_patterns", [])
        if openings:
            st.markdown("**常用开场句式**")
            for o in openings:
                st.caption(f"▸ {o}")

        if lang.get("humor_style"):
            st.info(f"😄 幽默风格：{lang['humor_style']}")

    # Visual Signature
    with st.expander("🎬 视觉签名"):
        c1, c2 = st.columns(2)
        with c1:
            st.metric("剪辑节奏", vis.get("editing_pace", "—"))
            st.metric("平均镜头时长", f"{vis.get('avg_shot_duration','—')}s")
        with c2:
            st.metric("运动风格", vis.get("motion_style", "—"))
            st.metric("转场风格", vis.get("transition_style", "—"))

        angles = vis.get("preferred_angles", [])
        if angles:
            st.markdown("**偏好拍摄角度**：" + " · ".join(f"`{a}`" for a in angles))

        props = vis.get("signature_props", [])
        if props:
            st.markdown("**标志性道具/场景**：" + " · ".join(f"`{p}`" for p in props))

    # Core Value
    with st.expander("💡 核心价值"):
        st.markdown(f"**内容方向**：{core.get('primary_topic', '—')}")
        st.markdown(f"**目标受众**：{core.get('target_audience', '—')}")
        st.markdown(f"**说服逻辑**：{core.get('selling_angle', '—')}")
        st.markdown(f"**权威来源**：{core.get('unique_authority', '—')}")

        strengths = core.get("content_strengths", [])
        if strengths:
            st.markdown("**内容优势**：" + " · ".join(f"`{s}`" for s in strengths))

        weaknesses = core.get("content_weaknesses", [])
        if weaknesses:
            st.markdown("**内容局限**：" + " · ".join(f"`{w}`" for w in weaknesses))

    # Viral Mechanics
    with st.expander("⚡ 爆款机制"):
        c1, c2 = st.columns(2)
        with c1:
            st.metric("钩子类型", mech.get("hook_type", "—"))
            st.metric("高光时刻", mech.get("peak_engagement_moment", "—"))
        with c2:
            st.metric("内容节奏", mech.get("content_rhythm", "—"))
            st.metric("平均视频时长", f"{mech.get('avg_video_length','—')}s")
        st.markdown(f"**开场公式**：{mech.get('hook_formula','—')}")
        st.markdown(f"**互动设计**：{mech.get('interaction_design','—')}")

    # 操作按钮
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button(f"🗑️ 删除「{koc_name}」", type="secondary", use_container_width=True):
            profiler.delete_profile(koc_name)
            # 清除 selectbox 的 session_state，防止 rerun 后试图恢复已删除条目
            st.session_state.pop("koc_view_select", None)
            st.rerun()
    with col_b:
        if st.button("📄 查看完整 JSON", use_container_width=True):
            st.json(profile)


# ─────────────────────────────────────────────
# KOC 批量建档流程（v3 新增）
# ─────────────────────────────────────────────
def _create_koc_profile_batch(
    profiler: KOCProfiler,
    koc_name: str,
    uploaded_files: list,
    urls: list,
    notes: str,
):
    """批量处理视频，提取 KOC 完整人设档案"""
    handler        = VideoInputHandler()
    local_analyzer = LocalAnalyzer()
    analyzer       = AIAnalyzer(
        provider=st.session_state.api_provider,
        api_key=st.session_state.api_key,
    )

    # 确保 koc_profiles 目录存在（双重保障，KOCProfiler.__init__ 已建但显式再建更安全）
    os.makedirs(profiler.profiles_dir, exist_ok=True)

    # Windows 路径安全：temp 文件名中的 koc_name 只保留 ASCII 字母/数字
    safe_koc_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in koc_name)[:30]

    all_features = []

    with st.status(f"正在为「{koc_name}」建立人设档案...", expanded=True) as status:

        # ── 处理上传文件 ──
        for i, uploaded in enumerate(uploaded_files[:10]):
            st.write(f"📹 [{i+1}/{len(uploaded_files[:10])}] 提取特征：{uploaded.name}")
            os.makedirs("temp", exist_ok=True)
            # 使用 ASCII 安全名称，避免 Windows + OpenCV 中文路径问题
            safe_filename = "".join(c if c.isalnum() or c in "-_." else "_" for c in uploaded.name)
            temp_path = f"temp/koc_{safe_koc_id}_{i}_{safe_filename}"
            with open(temp_path, "wb") as f:
                f.write(uploaded.getbuffer())
            try:
                features = local_analyzer.extract_features(temp_path)
                all_features.append(features)
                st.write(
                    f"   ✅ 镜头 {features.get('scene_changes',0)} 次 · "
                    f"ASR [{features.get('asr_status','—')}]"
                )
            except Exception as e:
                st.warning(f"   ⚠️ 跳过（提取失败）：{e}")
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)

        # ── 处理 URL ──
        for i, url in enumerate(urls[:10]):
            short_url = url[:60] + ("..." if len(url) > 60 else "")
            st.write(f"🔗 [{i+1}/{len(urls[:10])}] 下载：{short_url}")
            cookie_src  = st.session_state.cookie_source
            cookie_file = get_saved_cookie_file(cookie_src) or st.session_state.cookie_file_path
            video_path  = handler.download_from_url(
                url,
                cookie_source="Cookie文件" if cookie_file else cookie_src,
                cookie_file_path=cookie_file,
            )
            if video_path:
                try:
                    features = local_analyzer.extract_features(video_path)
                    all_features.append(features)
                    st.write(
                        f"   ✅ 镜头 {features.get('scene_changes',0)} 次 · "
                        f"ASR [{features.get('asr_status','—')}]"
                    )
                except Exception as e:
                    st.warning(f"   ⚠️ 特征提取失败：{e}")
                finally:
                    handler.cleanup_temp(video_path)
            else:
                st.warning(f"   ⚠️ 跳过（下载失败）：{short_url}")

        if not all_features:
            status.update(label="❌ 没有成功处理的视频", state="error")
            st.error("所有视频均处理失败，请检查文件格式或网络连接。")
            return

        # ── 聚合特征 ──
        st.write(f"🔬 聚合 {len(all_features)} 个视频的特征数据...")
        batch_features = profiler.aggregate_batch_features(all_features)
        st.write(
            f"✅ 平均时长 {batch_features['avg_duration_seconds']}s · "
            f"平均镜头 {batch_features['avg_shot_duration']}s/镜 · "
            f"BPM {batch_features['avg_tempo_bpm']}"
        )

        # ── AI 人设提取 ──
        st.write(f"🤖 AI 提取人设 DNA（{st.session_state.api_provider}）...")
        try:
            profile = analyzer.extract_koc_persona_batch(
                koc_name=koc_name,
                notes=notes,
                batch_features=batch_features,
            )
            profile["videos_analyzed"] = len(all_features)
        except Exception as e:
            status.update(label="❌ AI 人设提取失败", state="error")
            st.error(f"AI 分析出错：{e}\n\n请检查 API Key 配置，或切换为本地模式重试。")
            return

        # ── 保存 JSON 到 koc_profiles/ ──
        st.write(f"💾 保存 KOC 人设档案到 `{profiler.profiles_dir}/`...")
        try:
            profiler.save_profile(koc_name, profile)
        except Exception as e:
            status.update(label="❌ 档案保存失败", state="error")
            st.error(f"写入文件失败：{e}\n\n请检查 `{profiler.profiles_dir}/` 目录的写入权限。")
            return

        # 验证文件确实已写入磁盘
        saved_path = profiler._profile_path(koc_name)
        if not os.path.exists(saved_path):
            status.update(label="❌ 档案写入验证失败", state="error")
            st.error(f"文件保存后找不到：{saved_path}")
            return

        status.update(label=f"✅ 档案建立完成：{koc_name}（已写入 {saved_path}）", state="complete")

    # 将成功摘要存入 session_state，st.rerun 后在页面顶部展示
    lang = profile.get("language_dna", {})
    st.session_state["koc_just_created"] = koc_name
    st.session_state["koc_created_summary"] = {
        "content_genre": profile.get("content_genre", "—"),
        "tone":          lang.get("tone", "—"),
        "dialect":       lang.get("dialect", "未检测到"),
        "videos":        len(all_features),
        "catchphrases":  lang.get("catchphrases", [])[:3],
    }
    st.rerun()


# ─────────────────────────────────────────────
# 标签页3：历史报告
# ─────────────────────────────────────────────
def render_tab_reports():
    st.subheader("📄 历史报告")

    reports_dir = "reports"
    if not os.path.exists(reports_dir):
        st.info("暂无历史报告")
        return

    report_files = sorted(
        [f for f in os.listdir(reports_dir) if f.endswith(".md")],
        reverse=True,
    )

    if not report_files:
        st.info("暂无历史报告，完成一次爆款分析后报告将保存在这里")
        return

    selected_report = st.selectbox("选择报告", report_files)
    if selected_report:
        with open(f"{reports_dir}/{selected_report}", "r", encoding="utf-8") as f:
            content = f.read()
        st.markdown(content)
        st.download_button(
            "⬇️ 下载此报告",
            data=content,
            file_name=selected_report,
            mime="text/markdown",
        )


# ─────────────────────────────────────────────
# 入口
# ─────────────────────────────────────────────
if __name__ == "__main__":
    render_sidebar()
    render_main()
