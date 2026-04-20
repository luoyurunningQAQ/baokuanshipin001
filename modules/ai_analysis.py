"""
ai_analysis.py - AI 深度分析模块（v3 - KOC 人设引擎 + 风格迁移）

v2 功能保留（类型感知 + 对话优先 + 反幻觉）。

v3 新增：
  6. KOC 批量人设提取：extract_koc_persona_batch()
     — 接收 5-10 个视频的聚合特征，输出完整 LanguageDNA/VisualSignature/CoreValue/ViralMechanics 档案
  7. 风格迁移脚本生成：generate_adapted_script()
     — 爆款视频成功公式 × KOC 人设 DNA = 「KOC 定制执行手册」
     — 包含 [Persona Fit] + [Style Transfer Logic] + [Adapted Shot Script] + [Director's Notes]

支持四种 AI 引擎：
  GPT-4o · Gemini 1.5 Pro · 通义千问 · 本地模式（无需 API）
"""

import json
import os


# ── 系统提示词（所有模式共享，v2：含反幻觉铁律 + 类型分类指引）─────────────────
AUTOMOTIVE_SYSTEM_PROMPT = """你是一位专业的汽车品牌内容策略师，专门分析短视频爆款规律。

━━━ 铁律：严禁幻觉（最高优先级）━━━
你只能分析视频中实际存在的内容（台词、字幕、画面、声音）。
✗ 禁止：视频未出现"0-100加速"却在报告中提及
✗ 禁止：未听到底盘测试台词却分析"底盘调校优秀"
✗ 禁止：对视频中未出现的技术参数做任何评价
✓ 正确：如某内容未检测到，直接写「未检测到」，不要编造
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【第一步：内容类型判定（必须先完成，再做后续分析）】
将视频归入以下四类之一，并明确写出判定依据：
- [硬核技术]：专业参数测试、工程解析、实测数据对比、专业评测人出镜
- [生活幽默]：方言梗、剧情反转、日常对话喜剧、家庭/朋友互动、暗号/黑话
- [豪华展示]：高端生活方式、品牌氛围、情感体验、慢节奏美学叙事
- [争议话题]：拉踩对比、颠覆认知、社会话题、挑战权威/常识

【第二步：对话/文字优先分析（核心）】
ASR 台词和 OCR 字幕是最直接的爆款线索，优先于视觉分析：
- 识别「爆款金句」：能引发转发/评论/模仿的核心台词
- 识别「记忆符号」：暗号、口头禅、重复性语言标记（如"爸/儿"人设）
- 识别方言特征：东北话/川渝话/粤语等（方言本身即传播因子）
- 识别「设悬钩子」：引发好奇的开场话语，促使用户看到最后

【第三步：精细化视觉符号识别（拒绝泛化）】
不要写"车辆展示镜头"，要识别具体互动动作：
[坐进车内] [语音指令互动（说明触发词）] [门把手操作（说明手势）]
[内饰配件特写（说明具体配件：挂件/香薰/座垫等）]
[车主面部反应（惊喜/满意/得意/尴尬）] [旁观者/朋友反应镜头]
[品牌 Logo 特写] [对比物件出镜] [实测数据上屏幕] [车外环境/场景]

【汽车专业术语使用规则：仅当视频中确实出现时引用】
NVH（噪音/震动/粗糙感）· 推背感 · 转向手感 · 刹车脚感 · 底盘调校
静态走位 · 动态跟拍 · 车内 POV · 仪表台特写 · 铺陈镜头 · 场景化营销"""


# ── KOC 风格分析提示词（v2：类型感知 + ASR/OCR 输入）────────────────────────
KOC_ANALYSIS_PROMPT_TEMPLATE = """请分析以下汽车 KOC（关键意见消费者）的视频，提炼其内容风格档案。

KOC 名称：{koc_name}
补充说明：{notes}

【技术特征】
- 视频时长：{duration}秒
- 镜头切换：{scene_changes}次（平均 {avg_shot}秒/镜）
- 运动强度：{motion_intensity}
- BGM 节拍：{tempo} BPM

【语音转写（ASR）】
{speech_transcript}

【屏幕文字（OCR）】
{screen_texts}

请先判断该 KOC 的内容类型，再输出以下 JSON（只输出 JSON，不要额外说明）：
{{
  "content_genre": "内容类型（[硬核技术]/[生活幽默]/[豪华展示]/[争议话题] 四选一）",
  "persona": "KOC 人设（2-3句：定位/受众/核心价值主张）",
  "tone": "语言风格（理性专业/情感共鸣/幽默娱乐/技术极客/生活记录）",
  "dialect": "使用方言（东北话/川渝话/粤语/普通话/未检测到）",
  "signature_phrases": ["从 ASR 提取的标志性台词或口头禅，最多3句；无ASR则写空列表"],
  "style": "视觉风格描述",
  "pacing": "节奏特征（快切≤2s/镜 | 中速3-5s/镜 | 慢节奏≥5s/镜）",
  "keywords": ["常用词汇3-5个"],
  "typical_structure": "典型视频结构（如：开场暗号→情境铺垫→爆点互动→品牌植入→引导互动）",
  "automotive_focus": "擅长的汽车内容领域",
  "viral_mechanics": "惯用爆款机制（幽默对话/数据冲击/情感共鸣/争议话题/人设IP）",
  "adaptation_priority": "品牌合作最重要的适配维度（台词节奏/BGM节点/镜头语言/话题设计）",
  "content_strengths": "内容优势2-3点（基于视频实际内容）",
  "suggested_collab_angles": ["品牌合作的3个建议切入角度（必须匹配该KOC的内容类型）"]
}}"""


# ── 主分析提示词（v2：6段结构化报告，类型自适应）────────────────────────────
VIRAL_ANALYSIS_PROMPT_TEMPLATE = """请对以下汽车视频进行深度爆款分析，严格遵守"仅分析实际检测到的内容"原则。

{koc_context_section}
【本地技术特征】
- 视频时长：{duration}秒
- 镜头切换：{scene_changes}次 | 时间点：{scene_timestamps}
- 运动强度：{motion_intensity}
- BGM 节拍：{tempo} BPM | 能量突变点：{bgm_transitions}
- 音频峰值 RMS：{audio_peak}

【语音识别（ASR）转写内容】
{speech_transcript}

【屏幕文字（OCR）识别内容】
{screen_texts}

━━━ 严格按以下6段格式输出 Markdown 报告 ━━━

---

# AutoViral AI 爆款分析报告

## ① 内容类型判定

**判定结果**：`[硬核技术 / 生活幽默 / 豪华展示 / 争议话题]`（选一个，用反引号标注）

**判定依据**：（必须引用上方 ASR/OCR 或技术特征中的具体内容，2-3句，不得引用未检测到的内容）

---

## ② 钩子识别（视频前3-5秒）

**钩子类型**（基于实际检测到的内容打 ✓，未检测到的不打）：
- [ ] 台词钩子 — ASR 检测到的开场台词
- [ ] 字幕钩子 — OCR 检测到的文字叠加
- [ ] 视觉钩子 — 特定画面/动作
- [ ] 声音钩子 — BGM 节奏/特殊音效

**爆款金句**：（直接引用 ASR/OCR 原文；若未提取到语音/文字则写"⚠️ ASR/OCR 未提取，建议配置 AI 模式获取台词分析"）

**钩子时间轴**：（标注金句/关键画面出现的时间点，精确到秒）

---

## ③ 爆款驱动力分析

> ⚠️ 评分严格基于视频实际内容，未出现的因素标注「未检测到」，不得猜测

| 驱动力维度 | 强度 | 视频中的具体表现（引用实际内容，或写"未检测到"） |
|-----------|------|----------------------------------------------|
| 幽默互动   | ★☆☆☆☆ | |
| 人设塑造   | ★☆☆☆☆ | |
| 情感共鸣   | ★☆☆☆☆ | |
| 信息价值   | ★☆☆☆☆ | |
| 视觉冲击   | ★☆☆☆☆ | |
| 话题争议   | ★☆☆☆☆ | |

---

## ④ 精细化视觉符号清单

（只列出视频中实际出现的符号，使用以下标签并补充具体说明；未出现的标签不要列出）

可用标签：[坐进车内] [语音指令互动] [门把手操作] [内饰配件特写] [车主面部反应] [旁观者反应镜头] [品牌 Logo 特写] [对比物件出镜] [实测数据上屏] [车外环境/场景]

检测到的符号：
- （格式示例：[语音指令互动] → 车主说"你好理想"触发车辆响应，出现在 3.2s）

---

## ⑤ 逐场景脚本表

| 时间段 | 内容类型 | 具体场景/互动 | 台词/字幕（引用原文，无对白写"—"） | BGM 状态 | 情感目标 |
|--------|---------|-------------|--------------------------------|---------|---------|
（根据镜头切换时间点填写，台词栏只引用 ASR/OCR 实际检测到的内容）

---

## ⑥ 复制执行指南

（根据①判定的内容类型，**只输出对应策略**，其他类型的策略不要输出）

### 若判定为 [生活幽默]
- **台词包袱结构**：铺垫时间点 → 递进 → 爆发点（精确到秒）
- **方言/口头禅复用**：保留原始方言特色，或提炼为品牌专属口头禅
- **互动机制设计**：如何让观众主动参与（暗号接龙/评论区互动/对话续写）
- **人设对立面**：建议的说话人角色组合（如：懂车帝×不懂车朋友）
- **BGM 策略**：轻快生活化 BGM，服务台词节奏，音量低于人声
- ⚠️ **不建议**：高速剪辑（破坏幽默节拍）、堆砌技术参数

### 若判定为 [硬核技术]
- **数据可视化方案**：将抽象参数转化为可感知的体验镜头
- **BGM 节点对齐**：数据揭示/测试峰值时刻 与 Beat Drop 精确同步
- **专业术语口语化**：每个术语配对对应的感受描述
- **对比/实测结构**：before/after 或横向对比的镜头设计
- **BGM 策略**：高 BPM（120-140），数据节点精确切换

### 若判定为 [豪华展示]
- **氛围镜头设计**：建议慢节奏（≥4s/镜），黄金时段光线
- **感官细节清单**：门关合声、皮质触感、香氛等多感官描述
- **生活场景融合**：将车融入高质量生活场景（商务/家庭/旅行）
- **静态走位必拍**：标准绕车走位 + 细节特写组合
- **BGM 策略**：低 BPM 大气感 BGM，音乐与镜头节奏统一

### 若判定为 [争议话题]
- **话题对立面设计**：选取有讨论空间（而非恶意攻击）的矛盾点
- **数据背书策略**：争议性观点必须配实测数据，增强可信度
- **留白技巧**：不把话说死，为评论区发言预留空间
- **前3秒争议点**：如何在开场直接抛出引发讨论的核心问题
- **BGM 策略**：中等 BPM，配合争议点的情绪递进

---

*由 AutoViral AI 生成 | {datetime}*
*⚠️ 本报告仅分析视频中实际检测到的内容，「未检测到」不代表该特征不存在*"""


class AIAnalyzer:
    """AI 分析调度器：根据配置选择 GPT-4o / Gemini / 通义千问 / 本地模式"""

    def __init__(self, provider: str, api_key: str):
        self.provider = provider
        self.api_key = api_key

    def analyze_viral_video(
        self,
        video_path: str,
        local_features: dict,
        koc_context: str = "",
    ) -> str:
        """
        分析视频爆款规律
        返回：完整的 Markdown 报告字符串
        """
        prompt = self._build_viral_prompt(local_features, koc_context)

        if self.provider == "GPT-4o（OpenAI）" and self.api_key:
            return self._call_openai(prompt)
        elif self.provider == "Gemini 1.5 Pro（Google）" and self.api_key:
            return self._call_gemini(prompt)
        elif self.provider == "通义千问（阿里云）" and self.api_key:
            return self._call_qianwen(prompt)
        else:
            return self._local_fallback_report(local_features)

    def analyze_koc_style(
        self,
        video_path: str,
        koc_name: str,
        notes: str,
        local_features: dict,
    ) -> dict:
        """分析 KOC 风格，返回档案字典"""
        duration = local_features.get("duration_seconds", 0)
        scene_changes = local_features.get("scene_changes", 1)
        avg_shot = round(duration / max(scene_changes, 1), 1)

        prompt = KOC_ANALYSIS_PROMPT_TEMPLATE.format(
            koc_name=koc_name,
            notes=notes or "无",
            duration=duration,
            scene_changes=scene_changes,
            avg_shot=avg_shot,
            motion_intensity=local_features.get("motion_intensity", "未知"),
            tempo=local_features.get("bgm_tempo_bpm", "未知"),
            speech_transcript=local_features.get(
                "speech_transcript", "【未提取 — 建议安装 openai-whisper 后重新分析】"
            ),
            screen_texts=local_features.get(
                "screen_texts", "【未提取 — 建议安装 easyocr 后重新分析】"
            ),
        )

        if self.provider == "GPT-4o（OpenAI）" and self.api_key:
            raw = self._call_openai(prompt)
        elif self.provider == "Gemini 1.5 Pro（Google）" and self.api_key:
            raw = self._call_gemini(prompt)
        elif self.provider == "通义千问（阿里云）" and self.api_key:
            raw = self._call_qianwen(prompt)
        else:
            raw = self._local_koc_fallback(koc_name, notes, local_features)

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            import re
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except Exception:
                    pass
            return {
                "content_genre": "未判定",
                "persona": notes or f"{koc_name} 的风格档案",
                "tone": "待分析",
                "dialect": "未检测到",
                "signature_phrases": [],
                "style": "待分析",
                "raw_output": raw,
            }

    # ── OpenAI GPT-4o ─────────────────────────────────────────────────────────

    def _call_openai(self, user_prompt: str) -> str:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": AUTOMOTIVE_SYSTEM_PROMPT},
                    {"role": "user",   "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=4096,
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"GPT-4o 调用失败：{e}\n\n将使用本地分析结果。"

    # ── 阿里云百炼 通义千问 ──────────────────────────────────────────────────

    def _call_qianwen(self, user_prompt: str) -> str:
        try:
            from openai import OpenAI
            client = OpenAI(
                api_key=self.api_key,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            )
            response = client.chat.completions.create(
                model="qwen-plus",
                messages=[
                    {"role": "system", "content": AUTOMOTIVE_SYSTEM_PROMPT},
                    {"role": "user",   "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=4096,
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"通义千问调用失败：{e}\n\n将使用本地分析结果。"

    # ── Google Gemini 1.5 Pro ──────────────────────────────────────────────────

    def _call_gemini(self, user_prompt: str) -> str:
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(
                model_name="gemini-1.5-pro",
                system_instruction=AUTOMOTIVE_SYSTEM_PROMPT,
            )
            response = model.generate_content(user_prompt)
            return response.text
        except Exception as e:
            return f"Gemini 调用失败：{e}\n\n将使用本地分析结果。"

    # ── 本地模式 Fallback（v2：类型启发 + 反幻觉声明）────────────────────────

    def _local_fallback_report(self, features: dict) -> str:
        """无 API 时，基于本地技术特征生成规则性报告（不调用任何 AI）"""
        scene_changes = features.get("scene_changes", 0)
        duration      = features.get("duration_seconds", 60)
        motion        = features.get("motion_intensity", "medium")
        tempo         = features.get("bgm_tempo_bpm", 120)
        transitions   = features.get("bgm_transition_points", [])
        asr_text      = features.get("speech_transcript", "")
        ocr_text      = features.get("screen_texts", "")

        avg_shot = round(duration / max(scene_changes, 1), 1)

        # ── 基于技术特征的类型启发（仅供参考，非 AI 判断）─────────────────
        if asr_text and any(kw in asr_text for kw in ["哈哩", "老铁", "贼", "整", "咋", "安逸", "耍", "喺"]):
            genre_hint = "[生活幽默]（检测到方言特征）"
        elif motion == "high" and tempo > 120:
            genre_hint = "[硬核技术] 或 [生活幽默]（高运动强度 + 快节奏）"
        elif motion == "low" and avg_shot > 4:
            genre_hint = "[豪华展示]（低运动强度 + 慢节奏）"
        elif tempo > 130:
            genre_hint = "[硬核技术]（高 BPM，快剪）"
        else:
            genre_hint = "无法判定（建议配置 AI API 获取精准判定）"

        pacing_desc = (
            f"快切（{avg_shot}s/镜，适合抖音/快手）" if avg_shot < 2.5
            else f"中速（{avg_shot}s/镜，注意力抓取与信息量平衡）" if avg_shot < 5
            else f"慢节奏（{avg_shot}s/镜，适合 B站/视频号深度内容）"
        )
        bgm_pts = ", ".join([f"{t}s" for t in transitions[:5]]) or "未检测到突变点"

        asr_section = (
            f"转写内容：{asr_text[:300]}{'...' if len(asr_text) > 300 else ''}"
            if asr_text and "未安装" not in asr_text
            else "⚠️ 未提取（安装 openai-whisper 后可获得台词分析）"
        )
        ocr_section = (
            f"识别内容：{ocr_text[:200]}"
            if ocr_text and "未安装" not in ocr_text
            else "⚠️ 未提取（安装 easyocr 后可获得字幕识别）"
        )

        from datetime import datetime
        return f"""# AutoViral AI 爆款分析报告（本地模式）

> ⚠️ **本地模式限制说明**
> - 当前未调用 AI API，报告基于视觉/音频**统计特征**生成，无法理解台词语义和画面内容
> - 配置 API Key（推荐通义千问）后可获得完整的类型判定、台词分析、精细视觉符号识别
> - 本模式**严禁推断未检测到的内容**（加速性能、悬架评价等），只报告数字指标

---

## ① 内容类型判定

**判定结果**：基于启发规则推断为 {genre_hint}

**说明**：本地模式无法理解台词和画面语义，类型判定仅供参考。

---

## ② 钩子识别

**ASR 语音内容**：{asr_section}

**OCR 屏幕文字**：{ocr_section}

> ⚠️ 本地模式无法识别「爆款金句」和「钩子类型」，需配置 AI API 后才能分析台词驱动力。

---

## ③ 爆款驱动力分析（仅技术维度）

| 驱动力维度 | 状态 | 说明 |
|-----------|------|------|
| 幽默互动 | 未检测到 | 需 AI 理解台词语义 |
| 人设塑造 | 未检测到 | 需 AI 理解台词语义 |
| 情感共鸣 | 未检测到 | 需 AI 理解台词语义 |
| 信息价值 | 未检测到 | 需 AI 理解画面内容 |
| 视觉冲击 | {motion.upper()} | 运动强度：{motion}（OpenCV 检测） |
| 话题争议 | 未检测到 | 需 AI 理解台词语义 |

---

## ④ 精细化视觉符号清单

> ⚠️ 本地模式无法识别具体互动（语音指令/面部反应/内饰配件），需配置 AI API。

**可用技术数据**：
- 镜头切换次数：{scene_changes} 次
- 剪辑节奏：{pacing_desc}
- 平均镜头时长：{avg_shot}s
- 画面运动强度：{motion}

---

## ⑤ 逐场景脚本表（技术时间线）

| 切换时间点 | 台词/字幕 | BGM 状态 |
|-----------|---------|---------|
{"".join([f"| {t}s | ⚠️ 需 AI 分析 | — |\n" for t in features.get("scene_change_timestamps", [])[:10]])}

---

## ⑥ BGM 技术数据

- **节拍**：{tempo} BPM
- **BGM 能量突变点**（建议镜头切换/字幕出现时间点）：{bgm_pts}

> 💡 **提升建议**：配置通义千问 API Key 后，系统将自动进行台词分析、类型判定、精细视觉符号识别，生成完整的6段报告。

---

*由 AutoViral AI 本地模式生成 | {datetime.now().strftime("%Y-%m-%d %H:%M")}*
*⚠️ 本报告仅包含可客观测量的技术特征，不对未检测到的内容做任何推断*"""

    def _local_koc_fallback(self, koc_name: str, notes: str, features: dict) -> str:
        """本地模式下的 KOC 档案基础版"""
        duration     = features.get("duration_seconds", 0)
        scene_changes = features.get("scene_changes", 1)
        avg_shot     = round(duration / max(scene_changes, 1), 1)
        asr_text     = features.get("speech_transcript", "")

        dialect = "未检测到"
        if asr_text:
            dialect_map = {
                "东北话": ["整", "咋", "老铁", "贼", "可劲儿", "嗯哪"],
                "川渝话": ["安逸", "耍", "要得", "嗯哦"],
                "粤语":   ["系咁", "唔係", "喺", "嘅"],
            }
            for d, markers in dialect_map.items():
                if any(m in asr_text for m in markers):
                    dialect = d
                    break

        return json.dumps({
            "content_genre": "未判定（本地模式）",
            "persona": notes or f"{koc_name}（待 AI 深度分析）",
            "tone": "未分析（本地模式无法理解台词语义）",
            "dialect": dialect,
            "signature_phrases": [],
            "style": "未分析",
            "pacing": f"{avg_shot}s/镜（{'快切' if avg_shot < 3 else '中速' if avg_shot < 5 else '慢节奏'}）",
            "keywords": [],
            "typical_structure": "待分析",
            "automotive_focus": notes or "待分析",
            "viral_mechanics": "未分析（需 AI API）",
            "adaptation_priority": "未分析（需 AI API）",
            "content_strengths": "本地模式无法深度分析，请配置 API Key 后重新分析",
            "suggested_collab_angles": [],
            "note": "此档案由本地模式生成，建议配置 API Key 后重新分析以获得完整档案（含类型判定/台词分析/合作策略）",
        }, ensure_ascii=False)

    # ── API 级 ASR / OCR 语义增强 ─────────────────────────────────────────────
    # 当本地 whisper / easyocr 未安装时，通过 AI API 直接提取台词和屏幕文字

    @staticmethod
    def _detect_dialect(text: str):
        """规则匹配方言特征，返回方言名称或 None"""
        markers = {
            "东北话": ["整", "咋", "老铁", "贼", "嗯哪", "寻思", "可劲儿"],
            "川渝话": ["安逸", "耍", "要得", "巴适", "咋个", "嗯哦"],
            "粤语":   ["唔係", "喺", "嘅", "咁", "佢", "系咁"],
        }
        for name, kws in markers.items():
            if any(k in text for k in kws):
                return name
        return None

    def enhance_with_api_asr_ocr(
        self,
        video_path: str,
        local_features: dict,
        on_step=None,
    ) -> dict:
        """
        当本地 ASR/OCR 未安装时，通过 AI API 提取台词和屏幕文字，
        回填到 local_features（不覆盖已成功提取的字段）。

        支持：
          - 通义千问（阿里云）：qwen-audio-turbo ASR + qwen-vl-max OCR
          - GPT-4o（OpenAI）：Whisper API ASR + GPT-4o Vision OCR
          - Gemini 1.5 Pro（Google）：File API 单次提取 ASR + OCR

        on_step: callable(str) — 进度回调，每个子步骤时调用
        """
        def _step(msg):
            if callable(on_step):
                on_step(msg)

        needs_asr = local_features.get("asr_status") in ("not_installed", "error")
        needs_ocr = local_features.get("ocr_status") in ("not_installed", "error")

        if not needs_asr and not needs_ocr:
            return local_features

        if "通义千问" in self.provider and self.api_key:
            return self._enhance_qwen(video_path, local_features, needs_asr, needs_ocr, _step)
        elif "GPT-4o" in self.provider and self.api_key:
            return self._enhance_gpt4o(video_path, local_features, needs_asr, needs_ocr, _step)
        elif "Gemini" in self.provider and self.api_key:
            return self._enhance_gemini(video_path, local_features, needs_asr, needs_ocr, _step)
        return local_features

    def _enhance_qwen(self, video_path, local_features, needs_asr, needs_ocr, step):
        """通义千问：qwen-audio-turbo 提取台词，qwen-vl-max 识别屏幕文字"""
        import base64
        import os
        from openai import OpenAI

        client = OpenAI(
            api_key=self.api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

        # ── ASR：提取音轨 → qwen-audio-turbo ─────────────────────────────────
        if needs_asr:
            step("🔊 阶段1/3：提取视频音轨...")
            audio_path = None
            try:
                from moviepy.editor import VideoFileClip

                audio_path = video_path.rsplit(".", 1)[0] + "_asr_qwen_tmp.mp3"
                clip = VideoFileClip(video_path)
                if clip.audio:
                    clip.audio.write_audiofile(
                        audio_path, verbose=False, logger=None, codec="mp3"
                    )
                    clip.close()
                    step("🔊 阶段1/3：qwen-audio-turbo 识别台词中...")
                    with open(audio_path, "rb") as af:
                        audio_b64 = base64.b64encode(af.read()).decode()
                    resp = client.chat.completions.create(
                        model="qwen-audio-turbo",
                        messages=[{
                            "role": "user",
                            "content": [
                                {
                                    "type": "audio_url",
                                    "audio_url": {
                                        "url": f"data:audio/mp3;base64,{audio_b64}"
                                    },
                                },
                                {
                                    "type": "text",
                                    "text": (
                                        "请完整转写这段视频的所有语音台词，"
                                        "保留方言特色和语气词，直接输出转写文本，"
                                        "无需添加时间戳或格式符号。"
                                    ),
                                },
                            ],
                        }],
                        max_tokens=2000,
                    )
                    transcript = (resp.choices[0].message.content or "").strip()
                    if transcript:
                        local_features["speech_transcript"] = transcript
                        local_features["asr_status"] = "api_qwen_audio"
                        dialect = self._detect_dialect(transcript)
                        if dialect:
                            local_features["speech_dialect"] = dialect
                else:
                    clip.close()
            except Exception as e:
                step(f"⚠️ ASR 提取失败：{e}")
            finally:
                if audio_path and os.path.exists(audio_path):
                    os.remove(audio_path)

        # ── OCR：提取关键帧 → qwen-vl-max ────────────────────────────────────
        if needs_ocr:
            step("👁️ 阶段2/3：提取关键帧（每2秒1帧）...")
            frames_b64 = []
            try:
                import cv2

                cap = cv2.VideoCapture(video_path)
                if cap.isOpened():
                    fps = cap.get(cv2.CAP_PROP_FPS) or 30
                    interval = max(1, int(fps * 2))
                    idx = 0
                    while len(frames_b64) < 16:
                        ret, frame = cap.read()
                        if not ret:
                            break
                        if idx % interval == 0:
                            h, w = frame.shape[:2]
                            frame_s = cv2.resize(frame, (640, int(640 * h / w)))
                            _, buf = cv2.imencode(
                                ".jpg", frame_s, [cv2.IMWRITE_JPEG_QUALITY, 70]
                            )
                            frames_b64.append(base64.b64encode(buf).decode())
                        idx += 1
                    cap.release()
            except Exception as e:
                step(f"⚠️ 关键帧提取失败：{e}")

            if frames_b64:
                step(f"👁️ 阶段2/3：qwen-vl-max 扫描屏幕文字（{len(frames_b64)} 帧）...")
                try:
                    content = [{
                        "type": "text",
                        "text": (
                            "请逐帧识别视频截图中出现的所有字幕、标题贴纸、"
                            "品牌 Logo 和屏幕文字，每行一条，"
                            "只列出实际看到的文字，没有文字的帧请跳过。"
                        ),
                    }]
                    for b64 in frames_b64:
                        content.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                        })
                    resp = client.chat.completions.create(
                        model="qwen-vl-max",
                        messages=[{"role": "user", "content": content}],
                        max_tokens=1000,
                    )
                    ocr_raw = resp.choices[0].message.content or ""
                    lines = [
                        l.strip()
                        for l in ocr_raw.split("\n")
                        if l.strip() and len(l.strip()) >= 2
                    ]
                    local_features["screen_texts"] = (
                        " | ".join(lines[:20]) or "未检测到文字叠加"
                    )
                    local_features["ocr_status"] = "api_qwen_vl"
                except Exception as e:
                    step(f"⚠️ OCR 提取失败：{e}")

        step("🤖 阶段3/3：语义数据合并完成")
        return local_features

    def _enhance_gpt4o(self, video_path, local_features, needs_asr, needs_ocr, step):
        """GPT-4o：Whisper API 提取台词，GPT-4o Vision 识别屏幕文字"""
        import base64
        import os
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)

        # ── ASR：Whisper API ──────────────────────────────────────────────────
        if needs_asr:
            step("🔊 阶段1/3：提取音轨并调用 Whisper API...")
            audio_path = None
            try:
                from moviepy.editor import VideoFileClip

                audio_path = video_path.rsplit(".", 1)[0] + "_asr_gpt_tmp.mp3"
                clip = VideoFileClip(video_path)
                if clip.audio:
                    clip.audio.write_audiofile(
                        audio_path, verbose=False, logger=None, codec="mp3"
                    )
                    clip.close()
                    with open(audio_path, "rb") as af:
                        t_resp = client.audio.transcriptions.create(
                            model="whisper-1", file=af, language="zh"
                        )
                    transcript = (t_resp.text or "").strip()
                    if transcript:
                        local_features["speech_transcript"] = transcript
                        local_features["asr_status"] = "api_whisper"
                        dialect = self._detect_dialect(transcript)
                        if dialect:
                            local_features["speech_dialect"] = dialect
                else:
                    clip.close()
            except Exception as e:
                step(f"⚠️ Whisper ASR 失败：{e}")
            finally:
                if audio_path and os.path.exists(audio_path):
                    os.remove(audio_path)

        # ── OCR：GPT-4o Vision ────────────────────────────────────────────────
        if needs_ocr:
            step("👁️ 阶段2/3：提取关键帧并调用 GPT-4o Vision...")
            frames_b64 = []
            try:
                import cv2

                cap = cv2.VideoCapture(video_path)
                if cap.isOpened():
                    fps = cap.get(cv2.CAP_PROP_FPS) or 30
                    interval = max(1, int(fps * 2))
                    idx = 0
                    while len(frames_b64) < 16:
                        ret, frame = cap.read()
                        if not ret:
                            break
                        if idx % interval == 0:
                            h, w = frame.shape[:2]
                            frame_s = cv2.resize(frame, (640, int(640 * h / w)))
                            _, buf = cv2.imencode(
                                ".jpg", frame_s, [cv2.IMWRITE_JPEG_QUALITY, 70]
                            )
                            frames_b64.append(base64.b64encode(buf).decode())
                        idx += 1
                    cap.release()
            except Exception as e:
                step(f"⚠️ 关键帧提取失败：{e}")

            if frames_b64:
                try:
                    content = [{
                        "type": "text",
                        "text": "请识别这些视频帧中的所有字幕、标题贴纸和屏幕文字，每行一条，只列出实际看到的文字。",
                    }]
                    for b64 in frames_b64:
                        content.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{b64}",
                                "detail": "low",
                            },
                        })
                    resp = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "user", "content": content}],
                        max_tokens=800,
                    )
                    ocr_raw = resp.choices[0].message.content or ""
                    lines = [
                        l.strip()
                        for l in ocr_raw.split("\n")
                        if l.strip() and len(l.strip()) >= 2
                    ]
                    if lines:
                        local_features["screen_texts"] = " | ".join(lines[:20])
                        local_features["ocr_status"] = "api_gpt4o"
                except Exception as e:
                    step(f"⚠️ GPT-4o OCR 失败：{e}")

        step("🤖 阶段3/3：语义数据合并完成")
        return local_features

    def _enhance_gemini(self, video_path, local_features, needs_asr, needs_ocr, step):
        """Gemini 1.5 Pro：File API 上传视频，单次提取 ASR + OCR"""
        import re
        import time

        try:
            import google.generativeai as genai
        except ImportError:
            step("⚠️ google-generativeai 未安装")
            return local_features

        genai.configure(api_key=self.api_key)
        ext = video_path.rsplit(".", 1)[-1].lower()
        mime_map = {
            "mp4": "video/mp4", "mov": "video/quicktime",
            "avi": "video/x-msvideo", "mkv": "video/x-matroska",
        }
        mime = mime_map.get(ext, "video/mp4")

        step("🔊 阶段1/3：上传视频到 Gemini File API...")
        try:
            video_file = genai.upload_file(video_path, mime_type=mime)
        except Exception as e:
            step(f"⚠️ 视频上传失败：{e}")
            return local_features

        step("🔊 阶段1/3：等待 Gemini 视频处理...")
        waited = 0
        while video_file.state.name == "PROCESSING" and waited < 120:
            time.sleep(3)
            waited += 3
            video_file = genai.get_file(video_file.name)

        if video_file.state.name != "ACTIVE":
            step("⚠️ Gemini 视频处理失败或超时")
            return local_features

        step("👁️ 阶段2/3：Gemini 提取台词和屏幕文字...")
        parts = []
        if needs_asr:
            parts.append(
                "1.【台词转写（ASR）】请逐字转写视频中的全部语音台词，保留方言特色，每段台词占一行。"
            )
        if needs_ocr:
            parts.append(
                "2.【屏幕文字（OCR）】请列出视频中出现的所有字幕、标题贴纸、品牌Logo等屏幕文字，每行一条。"
            )
        prompt = "请分析这个视频并提取以下内容：\n\n" + "\n".join(parts) + "\n\n只提取实际存在的内容，不要推测。"

        try:
            model = genai.GenerativeModel("gemini-1.5-pro")
            response = model.generate_content([video_file, prompt])
            text = response.text or ""
            step("🤖 阶段3/3：解析提取结果...")

            if needs_asr and "台词转写" in text:
                asr_start = text.find("【台词转写")
                asr_end = text.find("【屏幕文字") if "【屏幕文字" in text else len(text)
                asr_raw = re.sub(r"【.*?】", "", text[asr_start:asr_end])
                transcript = "\n".join(l.strip() for l in asr_raw.split("\n") if l.strip())
                if transcript:
                    local_features["speech_transcript"] = transcript
                    local_features["asr_status"] = "api_gemini"
                    dialect = self._detect_dialect(transcript)
                    if dialect:
                        local_features["speech_dialect"] = dialect

            if needs_ocr and "屏幕文字" in text:
                ocr_start = text.find("【屏幕文字")
                ocr_raw = re.sub(r"【.*?】", "", text[ocr_start:])
                lines = [l.strip() for l in ocr_raw.split("\n") if l.strip()]
                if lines:
                    local_features["screen_texts"] = " | ".join(lines[:20])
                    local_features["ocr_status"] = "api_gemini"

        except Exception as e:
            step(f"⚠️ Gemini 提取失败：{e}")
        finally:
            try:
                genai.delete_file(video_file.name)
            except Exception:
                pass

        return local_features

    # ── Prompt 构建（v2：注入 ASR/OCR 数据）──────────────────────────────────

    def _build_viral_prompt(self, features: dict, koc_context: str) -> str:
        from datetime import datetime

        koc_section = ""
        if koc_context:
            koc_section = f"【参考 KOC 档案（请据此调整分析视角和复制策略）】\n{koc_context}\n\n"

        transitions = features.get("bgm_transition_points", [])
        transition_str = ", ".join([f"{t}s" for t in transitions]) or "未检测到"
        scene_ts       = features.get("scene_change_timestamps", [])
        scene_str      = ", ".join([f"{t}s" for t in scene_ts[:15]]) or "未检测到"

        # ASR / OCR 数据（优先级最高的分析输入）
        speech_transcript = features.get(
            "speech_transcript",
            "【未提取 — 安装 openai-whisper（pip install openai-whisper）后可获得台词分析】"
        )
        screen_texts = features.get(
            "screen_texts",
            "【未提取 — 安装 easyocr（pip install easyocr）后可获得字幕识别】"
        )

        return VIRAL_ANALYSIS_PROMPT_TEMPLATE.format(
            koc_context_section=koc_section,
            duration=features.get("duration_seconds", "未知"),
            scene_changes=features.get("scene_changes", 0),
            scene_timestamps=scene_str,
            motion_intensity=features.get("motion_intensity", "未知"),
            tempo=features.get("bgm_tempo_bpm", "未知"),
            bgm_transitions=transition_str,
            audio_peak=features.get("audio_peak_rms", "未知"),
            speech_transcript=speech_transcript,
            screen_texts=screen_texts,
            datetime=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )


# ══════════════════════════════════════════════════════════════════════════════
# v3 新增：KOC 批量人设提取提示词
# ══════════════════════════════════════════════════════════════════════════════

KOC_PERSONA_BATCH_PROMPT = """你是一位专业的 KOC 内容策略分析师，擅长从多视频样本中提炼 KOC 的内容人设 DNA。

━━━ 铁律：严禁幻觉 ━━━
所有分析必须基于下方提供的 ASR/OCR/技术数据，不得引用未出现的内容。
━━━━━━━━━━━━━━━━━━━━━━━━━

KOC 名称：{koc_name}
用户补充说明：{notes}

【批量视频统计特征（共 {video_count} 个视频）】
- 平均视频时长：{avg_duration}秒
- 平均镜头时长：{avg_shot}秒/镜
- 平均 BGM BPM：{avg_tempo}
- 主要运动强度：{dominant_motion}
- 视频时长分布：{duration_distribution}
- 检测到的方言：{detected_dialect}

【合并 ASR 台词（多视频，--- 为视频分隔线）】
{combined_transcripts}

【合并 OCR 屏幕文字】
{combined_screen_texts}

请输出完整的 KOC 人设档案 JSON（只输出 JSON，不要额外说明文字）：
{{
  "content_genre": "主要内容类型（[硬核技术]/[生活幽默]/[豪华展示]/[争议话题]）",

  "language_dna": {{
    "tone": "语言风格（幽默娱乐/理性专业/情感共鸣/技术极客/生活记录）",
    "dialect": "方言（东北话/川渝话/粤语/普通话/未检测到）",
    "catchphrases": ["从ASR提取的标志性口头禅，最多5句；无ASR则空列表"],
    "opening_patterns": ["常用开场句式1-2个，无则空列表"],
    "closing_patterns": ["常用收尾句式1-2个，无则空列表"],
    "humor_style": "幽默风格（反转型/自嘲型/无厘头型/无）",
    "avg_sentence_length": "句长特征（短句≤10字/长句≥20字/混合）",
    "vocabulary_level": "词汇层级（口语化/专业术语/混合）",
    "voice_characteristics": "声音语气特点（激情型/平稳型/悬念型/温和型）"
  }},

  "visual_signature": {{
    "preferred_angles": ["常用拍摄角度，最多3个（车内自拍/怼脸近景/车外全景/低机位/跟拍/混合）"],
    "editing_pace": "剪辑节奏描述",
    "avg_shot_duration": {avg_shot},
    "motion_style": "运动风格（静态为主/动态跟拍/手持晃动/混合）",
    "transition_style": "转场风格（硬切/淡入淡出/J-cut/混合）",
    "color_tone": "色调风格（自然/高饱和/电影感/暗调）",
    "signature_props": ["标志性道具/场景元素，从ASR/OCR推断，最多3个；不确定则空列表"],
    "framing_preference": "构图偏好（中景为主/近景为主/全景为主）"
  }},

  "core_value": {{
    "primary_topic": "核心内容方向",
    "target_audience": "目标受众（年龄/性别/购车需求/收入层次）",
    "selling_angle": "内容核心说服逻辑",
    "unique_authority": "该KOC的独特权威性来源",
    "content_strengths": ["内容优势，最多3条，基于实际检测内容"],
    "content_weaknesses": ["内容局限，1-2条，诚实分析"]
  }},

  "viral_mechanics": {{
    "hook_type": "钩子类型（台词钩子/视觉钩子/字幕钩子/声音钩子）",
    "hook_formula": "开场公式（如：提问→设悬→反转）",
    "interaction_design": "互动设计方式",
    "avg_video_length": {avg_duration},
    "peak_engagement_moment": "高光时刻时间段（如：视频60-80%处）",
    "content_rhythm": "内容节奏（快节奏高密度/慢热型/高潮迭起）"
  }}
}}"""


# ══════════════════════════════════════════════════════════════════════════════
# v3 新增：风格迁移脚本生成提示词（爆款公式 × KOC DNA = 定制执行手册）
# ══════════════════════════════════════════════════════════════════════════════

STYLE_TRANSFER_PROMPT = """你是一位专业的汽车内容策略师，擅长将爆款视频的成功公式「移植」到特定 KOC 的内容风格中。

━━━ 铁律：严禁幻觉 ━━━
① 爆款分析：只分析视频中实际存在的内容（ASR/OCR/技术特征）
② KOC 定制：台词/场景/风格必须忠实于 KOC 档案中记录的真实特点
③ 未出现的技术参数（加速/悬架/NVH等）严禁在未有视频依据时出现
━━━━━━━━━━━━━━━━━━━━━━━━━

【爆款视频原始特征（本地检测数据）】
- 视频时长：{duration}秒
- 镜头切换：{scene_changes}次 | 时间点：{scene_timestamps}
- 运动强度：{motion_intensity}
- BGM 节拍：{tempo} BPM | 能量突变点：{bgm_transitions}

【语音识别（ASR）台词】
{speech_transcript}

【屏幕文字（OCR）】
{screen_texts}

【KOC 人设档案 · {koc_name}】
内容类型：{koc_genre}

语言 DNA：
- 语言风格：{koc_tone} | 方言：{koc_dialect}
- 标志性口头禅：{koc_catchphrases}
- 开场公式：{koc_opening}
- 幽默风格：{koc_humor_style}

视觉签名：
- 偏好拍摄角度：{koc_angles}
- 剪辑节奏：{koc_editing_pace}（平均 {koc_avg_shot}s/镜）
- 标志性道具/场景：{koc_props}

核心价值：
- 核心内容方向：{koc_primary_topic}
- 目标受众：{koc_audience}
- 说服逻辑：{koc_selling_angle}

爆款机制：
- 钩子公式：{koc_hook_formula}
- 高光时刻：{koc_peak_moment}

━━━ 请按以下5段结构输出「KOC 定制执行手册」Markdown 报告 ━━━

---

# AutoViral AI · KOC 定制执行手册

**KOC**：{koc_name} · {koc_genre} · 基于 {videos_analyzed} 个视频档案

---

## ① 爆款公式解析

**视频内容类型**：（判定结果，基于 ASR/OCR/技术特征）

**核心钩子**：（引用 ASR/OCR 原文；若未提取则写"⚠️ ASR/OCR 未提取，无法识别台词钩子"）

**最强驱动力**：（从幽默互动/人设塑造/情感共鸣/信息价值/视觉冲击/话题争议中选2-3个，引用具体证据）

**原版成功的核心结构**：（用公式描述，如"设悬(0-3s) → 铺垫(3-8s) → 爆点(8-15s)"）

---

## ② 人设适配分析 [Persona Fit]

**适配度**：★★★☆☆（0-5星，说明评分依据，诚实评估）

**天然契合点**：（爆款视频哪些元素与 {koc_name} 的风格天然吻合？具体说明）

**需要重新诠释**：（哪些元素与 KOC 风格不符，需要如何调整才能不"水土不服"？）

**风险提示**：（若直接复制不做调整会产生什么问题？）

---

## ③ 风格迁移映射 [Style Transfer Logic]

| 爆款原版元素 | 迁移逻辑 | {koc_name} 适配版本 |
|------------|---------|-------------------|
| （原版钩子/台词） | （保留结构，用KOC语言重写） | （用{koc_dialect}{koc_tone}风格的台词示例） |
| （原版场景） | （适配KOC视觉习惯：{koc_angles}） | （具体视觉动作描述） |
| （原版互动设计） | （匹配KOC粉丝群体特点） | （适配版互动方案） |

---

## ④ 定制逐镜脚本 [Adapted Shot-by-Shot Script]

> 台词全部使用 {koc_name} 的真实口吻（{koc_dialect} · {koc_tone}）撰写
> 时间节点与爆款视频原版对应，但内容完全重新创作

| 镜头 | 时间点 | 视觉动作（适配{koc_name}习惯） | 台词/文案（{koc_name}口吻原创） | BGM/剪辑指令 |
|------|--------|------------------------------|-------------------------------|------------|
（每个镜头对应爆款视频的原始时间区间，镜头数量与原版一致）

---

## ⑤ 导演手记 [Director's Notes]

> 直接对 {koc_name} 说，像导演对演员下指令：具体到秒数、镜头角度、台词语气

1. **开场（0-Xs）**：（具体拍摄指令，说明用哪个角度、什么道具、什么表情开场）
2. **标志性台词时机**：在 __s 处，切换到你惯用的语气，说出 "[口头禅示例]"，因为这里是...
3. **视觉签名嵌入**：在 __s，将你的标志性道具/场景（{koc_props}）带入画面，强化辨识度
4. **方言/口头禅植入**：在 [具体场景] 时，用 {koc_dialect} 说 [具体台词]，原因是...
5. **剪辑节奏指令**：保持 {koc_avg_shot}s/镜基准节奏，在 [时间点] 加速至 __s/镜制造高潮
6. **互动收尾设计**：结尾用 [具体方式] 引导 {koc_name} 的粉丝互动，利用了他们的 [群体特点]

---

*由 AutoViral AI 生成 | {datetime}*
*基于 {koc_name} 的 {videos_analyzed} 个视频档案 × 爆款视频实际检测数据*
*⚠️ 所有台词为 AI 基于 KOC 风格原创，请 KOC 本人根据实际口感二次调整*"""


# ══════════════════════════════════════════════════════════════════════════════
# v3 新增方法（追加到 AIAnalyzer 类）
# ══════════════════════════════════════════════════════════════════════════════

# 用 monkey-patch 方式将新方法注入 AIAnalyzer 类
def _extract_koc_persona_batch(self, koc_name: str, notes: str, batch_features: dict) -> dict:
    """
    批量 KOC 人设提取（v3）
    接收 KOCProfiler.aggregate_batch_features() 的输出，调用 AI 生成完整人设档案 JSON。
    """
    prompt = KOC_PERSONA_BATCH_PROMPT.format(
        koc_name=koc_name,
        notes=notes or "无",
        video_count=batch_features.get("videos_count", 1),
        avg_duration=batch_features.get("avg_duration_seconds", "未知"),
        avg_shot=batch_features.get("avg_shot_duration", "未知"),
        avg_tempo=batch_features.get("avg_tempo_bpm", "未知"),
        dominant_motion=batch_features.get("dominant_motion", "未知"),
        duration_distribution=batch_features.get("duration_distribution", "未知"),
        detected_dialect=batch_features.get("detected_dialect") or "未检测到",
        combined_transcripts=batch_features.get(
            "combined_transcripts",
            "【未提取 — 建议安装 openai-whisper 后重新分析以提升人设提取精度】"
        ),
        combined_screen_texts=batch_features.get("combined_screen_texts", "【未提取】"),
    )

    if self.provider == "GPT-4o（OpenAI）" and self.api_key:
        raw = self._call_openai(prompt)
    elif self.provider == "Gemini 1.5 Pro（Google）" and self.api_key:
        raw = self._call_gemini(prompt)
    elif self.provider == "通义千问（阿里云）" and self.api_key:
        raw = self._call_qianwen(prompt)
    else:
        raw = self._local_koc_batch_fallback(koc_name, notes, batch_features)

    # 解析 JSON
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        import re
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
        # 最终兜底
        return {
            "content_genre": "未判定",
            "language_dna": {"tone": "待分析", "dialect": batch_features.get("detected_dialect") or "未检测到", "catchphrases": []},
            "visual_signature": {"preferred_angles": [], "avg_shot_duration": batch_features.get("avg_shot_duration", 0)},
            "core_value": {"primary_topic": notes or "待分析", "content_strengths": []},
            "viral_mechanics": {"hook_type": "待分析", "hook_formula": "待分析"},
            "raw_output": raw[:500],
            "parse_error": "JSON 解析失败，已保存原始输出",
        }


def _local_koc_batch_fallback(self, koc_name: str, notes: str, batch_features: dict) -> str:
    """本地模式下的批量 KOC 档案基础版"""
    dialect = batch_features.get("detected_dialect") or "未检测到"
    avg_shot = batch_features.get("avg_shot_duration", 0)
    pacing = "快切" if avg_shot < 3 else "中速" if avg_shot < 5 else "慢节奏"

    return json.dumps({
        "content_genre": "未判定（本地模式）",
        "language_dna": {
            "tone": "未分析（需 AI API）",
            "dialect": dialect,
            "catchphrases": [],
            "opening_patterns": [],
            "closing_patterns": [],
            "humor_style": None,
            "avg_sentence_length": "未分析",
            "vocabulary_level": "未分析",
            "voice_characteristics": "未分析",
        },
        "visual_signature": {
            "preferred_angles": [],
            "editing_pace": f"{pacing}（{avg_shot}s/镜）",
            "avg_shot_duration": avg_shot,
            "motion_style": batch_features.get("dominant_motion", "未知"),
            "transition_style": "未分析",
            "color_tone": "未分析",
            "signature_props": [],
            "framing_preference": "未分析",
        },
        "core_value": {
            "primary_topic": notes or "待分析",
            "target_audience": "未分析",
            "selling_angle": "未分析",
            "unique_authority": "未分析",
            "content_strengths": ["本地模式无法深度分析"],
            "content_weaknesses": ["需配置 API Key 重新分析"],
        },
        "viral_mechanics": {
            "hook_type": "未分析",
            "hook_formula": "未分析",
            "interaction_design": "未分析",
            "avg_video_length": batch_features.get("avg_duration_seconds", 0),
            "peak_engagement_moment": "未分析",
            "content_rhythm": "未分析",
        },
        "note": f"此档案由本地模式生成（{batch_features.get('videos_count', 1)} 个视频）。配置 API Key 后重新分析可获得完整人设档案。",
    }, ensure_ascii=False)


def _generate_adapted_script(self, local_features: dict, koc_profile: dict) -> str:
    """
    风格迁移脚本生成（v3）
    将爆款视频的成功公式移植到 KOC 的内容风格，生成「KOC 定制执行手册」。
    """
    prompt = self._build_style_transfer_prompt(local_features, koc_profile)

    if self.provider == "GPT-4o（OpenAI）" and self.api_key:
        return self._call_openai(prompt)
    elif self.provider == "Gemini 1.5 Pro（Google）" and self.api_key:
        return self._call_gemini(prompt)
    elif self.provider == "通义千问（阿里云）" and self.api_key:
        return self._call_qianwen(prompt)
    else:
        return self._local_style_transfer_fallback(local_features, koc_profile)


def _build_style_transfer_prompt(self, features: dict, koc: dict) -> str:
    from datetime import datetime

    lang = koc.get("language_dna", {})
    vis  = koc.get("visual_signature", {})
    core = koc.get("core_value", {})
    mech = koc.get("viral_mechanics", {})

    transitions = features.get("bgm_transition_points", [])
    scene_ts    = features.get("scene_change_timestamps", [])

    catchphrases = lang.get("catchphrases", [])
    catchphrase_str = "、".join(f'"{p}"' for p in catchphrases[:3]) if catchphrases else "（未检测到）"

    return STYLE_TRANSFER_PROMPT.format(
        duration        = features.get("duration_seconds", "未知"),
        scene_changes   = features.get("scene_changes", 0),
        scene_timestamps= ", ".join([f"{t}s" for t in scene_ts[:15]]) or "未检测到",
        motion_intensity= features.get("motion_intensity", "未知"),
        tempo           = features.get("bgm_tempo_bpm", "未知"),
        bgm_transitions = ", ".join([f"{t}s" for t in transitions]) or "未检测到",
        speech_transcript = features.get("speech_transcript", "【未提取】"),
        screen_texts    = features.get("screen_texts", "【未提取】"),

        koc_name        = koc.get("koc_name", "KOC"),
        koc_genre       = koc.get("content_genre", "未知"),
        koc_tone        = lang.get("tone", "—"),
        koc_dialect     = lang.get("dialect", "普通话"),
        koc_catchphrases= catchphrase_str,
        koc_opening     = str(lang.get("opening_patterns", [])),
        koc_humor_style = lang.get("humor_style") or "无",
        koc_angles      = "、".join(vis.get("preferred_angles", [])) or "—",
        koc_editing_pace= vis.get("editing_pace", "—"),
        koc_avg_shot    = vis.get("avg_shot_duration", "—"),
        koc_props       = "、".join(vis.get("signature_props", [])) or "（未检测到）",
        koc_primary_topic = core.get("primary_topic", "—"),
        koc_audience    = core.get("target_audience", "—"),
        koc_selling_angle = core.get("selling_angle", "—"),
        koc_hook_formula= mech.get("hook_formula", "—"),
        koc_peak_moment = mech.get("peak_engagement_moment", "—"),
        videos_analyzed = koc.get("videos_analyzed", 1),
        datetime        = datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


def _local_style_transfer_fallback(self, features: dict, koc: dict) -> str:
    """本地模式：无法执行风格迁移，输出提示"""
    from datetime import datetime
    koc_name = koc.get("koc_name", "KOC")
    lang = koc.get("language_dna", {})
    catchphrases = lang.get("catchphrases", [])
    dialect = lang.get("dialect", "未检测到")

    return f"""# AutoViral AI · KOC 定制执行手册（本地模式）

> ⚠️ **风格迁移需要 AI API**
> 本地模式无法理解台词语义和 KOC 风格，无法执行风格迁移分析。
> 请配置通义千问 / GPT-4o / Gemini 1.5 Pro 后使用此功能。

**KOC 档案**：{koc_name}
**方言**：{dialect}
**口头禅（已存档）**：{', '.join(catchphrases) if catchphrases else '（未提取，需 openai-whisper）'}

**技术数据已就绪**：
- 视频时长：{features.get("duration_seconds", "—")}s
- 镜头切换：{features.get("scene_changes", "—")} 次
- BGM：{features.get("bgm_tempo_bpm", "—")} BPM

> 💡 配置 API Key 后点击「🎭 生成定制执行手册」即可完整运行风格迁移分析。

*由 AutoViral AI 本地模式生成 | {datetime.now().strftime("%Y-%m-%d %H:%M")}*"""


# ── 将新方法注入 AIAnalyzer 类 ──────────────────────────────────────────────
AIAnalyzer.extract_koc_persona_batch    = _extract_koc_persona_batch
AIAnalyzer._local_koc_batch_fallback    = _local_koc_batch_fallback
AIAnalyzer.generate_adapted_script      = _generate_adapted_script
AIAnalyzer._build_style_transfer_prompt = _build_style_transfer_prompt
AIAnalyzer._local_style_transfer_fallback = _local_style_transfer_fallback
