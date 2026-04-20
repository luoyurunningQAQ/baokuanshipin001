"""
koc_profiler.py - KOC 档案管理模块 v2（人设引擎）

新增功能：
  - 完整人设 Schema：LanguageDNA + VisualSignature + CoreValue + ViralMechanics
  - aggregate_batch_features()：聚合 5-10 个视频的技术特征供批量分析
  - get_profile_summary()：返回 UI 展示用的摘要数据（不含大字段）
  - 兼容旧版单视频档案
"""

import json
import os
from datetime import datetime


# ── 新版完整档案 Schema（供 AI 参考）────────────────────────────────────────
PROFILE_SCHEMA_EXAMPLE = {
    "koc_name": "张老师汽车频道",
    "content_genre": "[生活幽默]",
    "videos_analyzed": 7,
    "created_at": "2025-04-16 14:30:00",
    "updated_at": "2025-04-16 14:30:00",

    "language_dna": {
        "tone": "幽默娱乐型",
        "dialect": "东北话",
        "catchphrases": ["整个大的", "老铁们", "这玩意儿贼好"],
        "opening_patterns": ["来，今天给大家整个...", "老铁们，你们知道吗..."],
        "closing_patterns": ["关注一下，不吃亏", "下期见，白白"],
        "humor_style": "反转型 — 先铺垫严肃问题，再用东北话给出喜剧答案",
        "avg_sentence_length": "短句为主，≤15字/句",
        "vocabulary_level": "口语化，刻意避开专业术语",
        "voice_characteristics": "平稳叙述 → 关键处突然抬高语调制造惊喜",
    },

    "visual_signature": {
        "preferred_angles": ["车内怼脸近景", "副驾视角"],
        "editing_pace": "中速（3-5s/镜）",
        "avg_shot_duration": 4.2,
        "motion_style": "静态为主，偶有手持晃动增加真实感",
        "transition_style": "硬切为主",
        "color_tone": "自然色，不过度调色",
        "signature_props": ["车内公仔摆件", "东北棉服"],
        "framing_preference": "中景+近景交替",
    },

    "core_value": {
        "primary_topic": "家用 SUV 性价比 + 东北家庭真实用车场景",
        "target_audience": "25-40 岁二孩家庭，预算 20-40 万，注重实用而非性能",
        "selling_angle": "真实车主视角证言，用接地气的方式消除购车疑虑",
        "unique_authority": "非专业评测人，胜在真实感和亲切感",
        "content_strengths": ["亲切感强，信任度高", "东北话辨识度高", "家庭场景真实"],
        "content_weaknesses": ["缺乏技术深度", "不适合极客/性能车受众"],
    },

    "viral_mechanics": {
        "hook_type": "台词钩子",
        "hook_formula": "提问设悬（0-3s）→ 对方困惑铺垫（3-8s）→ 金句爆发（8-15s）",
        "interaction_design": "暗号梗引导评论区接龙，L9/L7 车主自发续写",
        "avg_video_length": 38,
        "peak_engagement_moment": "视频 60-80% 处（金句爆发点）",
        "content_rhythm": "慢热型 — 开场低密度，高潮迭起",
    },
}


class KOCProfiler:
    """管理 KOC 风格档案的增删改查 + 批量特征聚合"""

    def __init__(self, profiles_dir: str = "koc_profiles"):
        self.profiles_dir = profiles_dir
        os.makedirs(profiles_dir, exist_ok=True)

    def _profile_path(self, koc_name: str) -> str:
        safe_name = (
            koc_name
            .replace("/", "_").replace("\\", "_")
            .replace(" ", "_").replace("　", "_")
        )
        return os.path.join(self.profiles_dir, f"{safe_name}_profile.json")

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def save_profile(self, koc_name: str, profile_data: dict):
        """保存档案，自动维护 created_at / updated_at 时间戳"""
        path = self._profile_path(koc_name)
        profile_data["koc_name"] = koc_name
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        profile_data["updated_at"] = now
        if not os.path.exists(path):
            profile_data["created_at"] = now
        with open(path, "w", encoding="utf-8") as f:
            json.dump(profile_data, f, ensure_ascii=False, indent=2)

    def load_profile(self, koc_name: str) -> dict | None:
        path = self._profile_path(koc_name)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def list_profiles(self) -> list[str]:
        names = []
        for filename in os.listdir(self.profiles_dir):
            if filename.endswith("_profile.json"):
                names.append(filename[: -len("_profile.json")])
        return sorted(names)

    def delete_profile(self, koc_name: str):
        path = self._profile_path(koc_name)
        if os.path.exists(path):
            os.remove(path)

    # ── 批量特征聚合（供多视频 KOC 人设提取使用）──────────────────────────────

    def aggregate_batch_features(self, all_features: list[dict]) -> dict:
        """
        聚合多个视频的本地技术特征，返回统计摘要供 AI 人设提取使用。

        输入：[features_dict, ...]（每个 dict 来自 LocalAnalyzer.extract_features()）
        输出：聚合后的摘要 dict
        """
        n = max(len(all_features), 1)

        # ── 时长 & 镜头节奏 ──
        durations = [f.get("duration_seconds", 0) for f in all_features]
        avg_duration = sum(durations) / n

        total_scenes = sum(f.get("scene_changes", 0) for f in all_features)
        avg_shot = avg_duration / max(total_scenes / n, 1)

        # ── BGM ──
        tempos = [f.get("bgm_tempo_bpm", 0) for f in all_features if f.get("bgm_tempo_bpm")]
        avg_tempo = sum(tempos) / max(len(tempos), 1)

        # ── 运动强度（众数）──
        motions = [f.get("motion_intensity", "medium") for f in all_features]
        dominant_motion = max(set(motions), key=motions.count)

        # ── ASR 台词合并（最多 4 段，避免 token 超限）──
        transcripts = [
            f.get("speech_transcript", "")
            for f in all_features
            if f.get("asr_status") == "success"
            and f.get("speech_transcript")
            and "未安装" not in f.get("speech_transcript", "")
        ]
        combined_transcripts = (
            "\n--- 视频分隔线 ---\n".join(transcripts[:4])
            if transcripts
            else "【未提取 — 建议安装 openai-whisper 后重新分析以提升人设提取精度】"
        )

        # ── OCR 文字合并 ──
        ocr_texts = [
            f.get("screen_texts", "")
            for f in all_features
            if f.get("ocr_status") == "success"
            and f.get("screen_texts")
            and "未安装" not in f.get("screen_texts", "")
        ]
        combined_ocr = " | ".join(ocr_texts[:4]) or "【未提取】"

        # ── 方言检测（任一视频检测到即记录）──
        dialects = [f.get("speech_dialect") for f in all_features if f.get("speech_dialect")]
        dominant_dialect = dialects[0] if dialects else None

        # ── 视频时长分布（短/中/长比例）──
        short  = sum(1 for d in durations if d < 30)
        medium = sum(1 for d in durations if 30 <= d < 90)
        long_  = sum(1 for d in durations if d >= 90)

        return {
            "videos_count":          n,
            "avg_duration_seconds":  round(avg_duration, 1),
            "avg_shot_duration":     round(avg_shot, 1),
            "avg_tempo_bpm":         round(avg_tempo, 1),
            "dominant_motion":       dominant_motion,
            "detected_dialect":      dominant_dialect,
            "duration_distribution": f"短片(<30s):{short}个 中片(30-90s):{medium}个 长片(>90s):{long_}个",
            "combined_transcripts":  combined_transcripts[:3500],  # ~1000 tokens
            "combined_screen_texts": combined_ocr[:900],
        }

    # ── UI 摘要（供分析 Tab 展示，不含大字段）──────────────────────────────────

    def get_profile_summary(self, koc_name: str) -> dict | None:
        """
        返回适合 UI 展示的摘要数据。
        去除 combined_transcripts 等大字段，只保留展示所需的关键字段。
        """
        profile = self.load_profile(koc_name)
        if not profile:
            return None

        lang = profile.get("language_dna", {})
        vis  = profile.get("visual_signature", {})
        core = profile.get("core_value", {})
        mech = profile.get("viral_mechanics", {})

        return {
            # 基础信息
            "koc_name":        profile.get("koc_name", koc_name),
            "content_genre":   profile.get("content_genre", "未知"),
            "videos_analyzed": profile.get("videos_analyzed", 1),
            "updated_at":      profile.get("updated_at", "—"),

            # Language DNA
            "tone":          lang.get("tone", "—"),
            "dialect":       lang.get("dialect", "未检测到"),
            "catchphrases":  lang.get("catchphrases", []),
            "opening":       lang.get("opening_patterns", []),
            "humor_style":   lang.get("humor_style"),
            "voice":         lang.get("voice_characteristics", "—"),
            "sentence_len":  lang.get("avg_sentence_length", "—"),

            # Visual Signature
            "angles":        vis.get("preferred_angles", []),
            "editing_pace":  vis.get("editing_pace", "—"),
            "avg_shot":      vis.get("avg_shot_duration", "—"),
            "motion_style":  vis.get("motion_style", "—"),
            "props":         vis.get("signature_props", []),
            "framing":       vis.get("framing_preference", "—"),

            # Core Value
            "primary_topic": core.get("primary_topic", "—"),
            "audience":      core.get("target_audience", "—"),
            "selling_angle": core.get("selling_angle", "—"),
            "strengths":     core.get("content_strengths", []),
            "weaknesses":    core.get("content_weaknesses", []),

            # Viral Mechanics
            "hook_type":     mech.get("hook_type", "—"),
            "hook_formula":  mech.get("hook_formula", "—"),
            "interaction":   mech.get("interaction_design", "—"),
            "peak_moment":   mech.get("peak_engagement_moment", "—"),
            "avg_length":    mech.get("avg_video_length", "—"),
        }
