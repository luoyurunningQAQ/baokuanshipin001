"""
local_analysis.py - 本地视觉/音频/语音/文字特征提取模块（v2）

新增（可选依赖）：
  - ASR 语音转文字：openai-whisper（pip install openai-whisper）
  - OCR 屏幕文字识别：easyocr（pip install easyocr）

无论是否安装可选依赖，核心视觉/音频分析均可正常运行。
"""

import os
import numpy as np


class LocalAnalyzer:
    """本地特征提取器：镜头切换 + 音频节拍 + 语音转文字（可选）+ 屏幕 OCR（可选）"""

    def extract_features(self, video_path: str) -> dict:
        """
        综合提取视频特征，返回结构：
        {
          # 视觉（核心）
          "duration_seconds": 62.3,
          "scene_changes": 14,
          "scene_change_timestamps": [2.1, 5.4, ...],
          "motion_intensity": "high",
          "fps": 30.0,

          # 音频（核心）
          "audio_peak_rms": 0.312,
          "bgm_tempo_bpm": 128.0,
          "bgm_beat_timestamps": [...],
          "bgm_transition_points": [3.5, 22.1, ...],
          "bgm_energy_curve": [...],

          # 语音（可选，需 openai-whisper）
          "speech_transcript": "全文转写",
          "speech_segments": [{"start":0.0,"end":2.1,"text":"..."},...],
          "speech_language": "zh",
          "speech_dialect": "东北话",   # 或 None
          "asr_status": "success",

          # 屏幕文字（可选，需 easyocr）
          "screen_texts": "字幕1 | 字幕2 | ...",
          "screen_text_details": [{"time":0.0,"text":"..."},...],
          "ocr_status": "success",
        }
        """
        features = {}
        features.update(self._analyze_visual(video_path))
        features.update(self._analyze_audio(video_path))
        features.update(self._extract_speech(video_path))
        features.update(self._extract_screen_text(video_path))
        return features

    # ── 视觉分析（OpenCV）────────────────────────────────────────────────────

    def _analyze_visual(self, video_path: str) -> dict:
        """OpenCV 镜头切换检测和运动强度分析"""
        try:
            import cv2

            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return {"visual_error": "无法打开视频文件"}

            fps          = cap.get(cv2.CAP_PROP_FPS) or 30
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration     = total_frames / fps

            scene_changes  = []
            motion_scores  = []
            prev_gray      = None
            frame_idx      = 0
            sample_interval = max(1, int(fps / 6))  # 每秒约6帧采样

            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                if frame_idx % sample_interval == 0:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    gray = cv2.resize(gray, (320, 180))
                    if prev_gray is not None:
                        diff_score = float(np.mean(cv2.absdiff(prev_gray, gray)))
                        motion_scores.append(diff_score)
                        if diff_score > 30:
                            scene_changes.append(round(frame_idx / fps, 2))
                    prev_gray = gray
                frame_idx += 1

            cap.release()

            avg_motion = float(np.mean(motion_scores)) if motion_scores else 0
            motion_intensity = (
                "low"    if avg_motion < 8  else
                "medium" if avg_motion < 20 else
                "high"
            )

            return {
                "duration_seconds":        round(duration, 1),
                "scene_changes":           len(scene_changes),
                "scene_change_timestamps": scene_changes,
                "motion_intensity":        motion_intensity,
                "fps":                     round(fps, 1),
            }

        except ImportError:
            return {"visual_error": "未安装 opencv-python"}
        except Exception as e:
            return {"visual_error": str(e)}

    # ── 音频分析（Librosa）───────────────────────────────────────────────────

    def _analyze_audio(self, video_path: str) -> dict:
        """MoviePy 提取音轨，Librosa 分析节拍/能量/BGM 转换点"""
        audio_path = None
        try:
            from moviepy.editor import VideoFileClip
            import librosa

            audio_path = video_path.rsplit(".", 1)[0] + "_audio_tmp.wav"
            clip = VideoFileClip(video_path)
            if clip.audio is None:
                return {"audio_error": "视频无音轨"}
            clip.audio.write_audiofile(audio_path, verbose=False, logger=None)
            clip.close()

            y, sr = librosa.load(audio_path, mono=True)
            rms   = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
            times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=512)

            tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
            beat_times = [round(t, 2) for t in librosa.frames_to_time(beat_frames, sr=sr).tolist()]

            rms_diff    = np.abs(np.diff(rms))
            threshold   = float(np.mean(rms_diff) + 2 * np.std(rms_diff))
            trans_idxs  = np.where(rms_diff > threshold)[0]
            trans_times = [
                round(float(times[i]), 2)
                for i in trans_idxs
                if i == trans_idxs[0] or
                   times[i] - times[trans_idxs[trans_idxs < i][-1]] > 1.0
            ]

            duration_s      = int(times[-1]) + 1 if len(times) > 0 else 0
            energy_per_sec  = []
            for sec in range(duration_s):
                mask = (times >= sec) & (times < sec + 1)
                energy_per_sec.append(round(float(np.mean(rms[mask])), 4) if mask.any() else 0.0)

            return {
                "audio_peak_rms":       round(float(np.max(rms)), 4),
                "audio_avg_rms":        round(float(np.mean(rms)), 4),
                "bgm_tempo_bpm":        round(float(tempo), 1),
                "bgm_beat_timestamps":  beat_times[:30],
                "bgm_transition_points": trans_times,
                "bgm_energy_curve":     energy_per_sec,
            }

        except ImportError as e:
            return {"audio_error": f"缺少依赖：{e}"}
        except Exception as e:
            return {"audio_error": str(e)}
        finally:
            if audio_path and os.path.exists(audio_path):
                os.remove(audio_path)

    # ── ASR 语音转文字（openai-whisper，可选）────────────────────────────────

    def _extract_speech(self, video_path: str) -> dict:
        """
        使用 openai-whisper 进行语音识别，提取台词和方言特征。
        未安装时优雅降级，不影响核心分析。
        安装：pip install openai-whisper
        """
        try:
            import whisper

            # base 模型平衡速度与精度；如需更高精度可改为 "small" 或 "medium"
            model  = whisper.load_model("base")
            result = model.transcribe(video_path, language=None, verbose=False)

            detected_lang = result.get("language", "unknown")
            full_text     = result.get("text", "").strip()

            segments = [
                {
                    "start": round(seg["start"], 1),
                    "end":   round(seg["end"],   1),
                    "text":  seg["text"].strip(),
                }
                for seg in result.get("segments", [])[:25]
            ]

            # 方言关键词检测（规则匹配，辅助 AI 判断）
            dialect = None
            dialect_markers = {
                "东北话": ["整", "咋", "哈哩", "老铁", "贼", "可劲儿", "嗯哪", "寻思"],
                "川渝话": ["安逸", "耍", "要得", "嗯哦", "咋个", "哇塞", "巴适"],
                "粤语":   ["系咁", "唔係", "喺", "嘅", "咁", "咗", "佢"],
            }
            for dialect_name, markers in dialect_markers.items():
                if any(m in full_text for m in markers):
                    dialect = dialect_name
                    break

            return {
                "speech_transcript": full_text,
                "speech_segments":   segments,
                "speech_language":   detected_lang,
                "speech_dialect":    dialect,
                "asr_status":        "success",
            }

        except ImportError:
            return {
                "speech_transcript": "【ASR 未安装 — pip install openai-whisper 开启台词分析，可识别方言/爆款金句/暗号梗】",
                "asr_status":        "not_installed",
            }
        except Exception as e:
            return {
                "speech_transcript": f"【ASR 识别失败：{e}】",
                "asr_status":        "error",
            }

    # ── OCR 屏幕文字识别（easyocr，可选）────────────────────────────────────

    def _extract_screen_text(self, video_path: str) -> dict:
        """
        使用 easyocr 识别视频帧中的字幕/贴纸/标题文字。
        每5秒采样一帧，重点检测画面下部字幕区域。
        未安装时优雅降级，不影响核心分析。
        安装：pip install easyocr
        """
        try:
            import cv2
            import easyocr

            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return {"screen_texts": "【无法打开视频进行 OCR】", "ocr_status": "error"}

            fps            = cap.get(cv2.CAP_PROP_FPS) or 30
            sample_interval = max(1, int(fps * 5))  # 每5秒采样一帧

            # 支持中文简体和英文；verbose=False 抑制初始化日志
            reader     = easyocr.Reader(["ch_sim", "en"], verbose=False)
            results    = []
            seen_texts = set()
            frame_idx  = 0

            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                if frame_idx % sample_interval == 0:
                    timestamp = round(frame_idx / fps, 1)
                    h, w      = frame.shape[:2]

                    # 检测上部 20%（片头标题/角标）+ 下部 45%（字幕/片尾字幕区）
                    roi_top    = frame[:int(h * 0.20), :]
                    roi_bottom = frame[int(h * 0.55):, :]
                    detected_top    = reader.readtext(roi_top,    detail=0, paragraph=True)
                    detected_bottom = reader.readtext(roi_bottom, detail=0, paragraph=True)
                    detected = detected_top + detected_bottom

                    for text in detected:
                        text = text.strip()
                        if len(text) >= 3 and text not in seen_texts:
                            seen_texts.add(text)
                            results.append({"time": timestamp, "text": text})

                frame_idx += 1

            cap.release()

            combined = " | ".join(r["text"] for r in results[:20])
            return {
                "screen_texts":        combined or "未检测到文字叠加",
                "screen_text_details": results[:20],
                "ocr_status":          "success",
            }

        except ImportError:
            return {
                "screen_texts": "【OCR 未安装 — pip install easyocr 开启字幕/贴纸文字识别，可提取爆款金句/暗号字幕】",
                "ocr_status":   "not_installed",
            }
        except Exception as e:
            return {
                "screen_texts": f"【OCR 识别失败：{e}】",
                "ocr_status":   "error",
            }
