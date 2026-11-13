#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""汇芯技能管家 · Windows 本地版

一个零第三方依赖的本地 Web 工具，用浏览器界面管理本机各 AI 工具的技能目录：
WorkBuddy / Claude Code / Codex / Gemini / Grok Bot / Agents 共享。

只读扫描技能文件，不修改、不删除任何技能；分类与收藏保存在本工具自己的 data/state.json。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

APP_NAME = "汇芯技能管家"
VERSION = "1.0.0-win"
ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
HOME = Path.home()

SKIP_DIR_NAMES = {
    "node_modules", ".git", "__pycache__", ".venv", "venv",
    "build", "dist", "target", ".next", ".cache", ".idea", ".vscode",
}
MD_SKIP_NAMES = {"readme.md", "changelog.md", "license.md", "notice.md"}


# ---------------------------------------------------------------- 状态存储

def _state_dir() -> Path:
    primary = ROOT / "data"
    try:
        primary.mkdir(parents=True, exist_ok=True)
        return primary
    except Exception:
        fallback = Path(os.environ.get("LOCALAPPDATA", str(HOME))) / "HuixinSkillsManager"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


STATE_PATH = _state_dir() / "state.json"

DEFAULT_STATE = {
    "collections": [],
    "overrides": {},
    "pins": [],
    "projects": [],
    "settings": {
        "showBackups": False,
        "sort": "recent",
        "theme": "light",
    },
}

CATEGORIES = [
    ("wechat", "公众号与内容", [
        ("公众号", 3), ("微信", 3), ("wechat", 3), ("gzh", 3), ("排版", 3),
        ("推文", 3), ("写作", 3), ("文章", 2), ("文案", 2), ("标题", 2),
        ("爆款", 2), ("草稿", 2), ("头条", 2), ("toutiao", 3), ("小红书", 2),
        ("九宫格", 2), ("朋友圈", 2), ("自媒体", 2), ("内容策略", 3),
    ]),
    ("video", "视频制作", [
        ("视频", 2), ("video", 3), ("口播", 3), ("分镜", 3), ("剪辑", 3),
        ("剪映", 3), ("短片", 2), ("宣传片", 3), ("抖音", 3), ("动画", 2),
        ("镜头", 2), ("配音", 2), ("字幕", 2), ("成片", 2), ("渲染", 2),
        ("mp4", 2), ("tiktok", 2), ("影视", 2),
    ]),
    ("design", "设计与配图", [
        ("封面", 3), ("配图", 3), ("插画", 3), ("海报", 3), ("拼豆", 3),
        ("图纸", 3), ("配色", 2), ("图片", 2), ("logo", 2), ("卡通", 2),
        ("头像", 2), ("抠图", 2), ("视觉", 2), ("image", 2), ("设计", 2),
    ]),
    ("research", "选题与调研", [
        ("选题", 3), ("热点", 3), ("调研", 3), ("抓取", 3), ("爬取", 3),
        ("雷达", 3), ("竞品", 3), ("趋势", 2), ("榜单", 2), ("搜索", 2),
        ("采集", 2), ("对标", 2), ("资讯", 2), ("热搜", 2),
    ]),
    ("knowledge", "知识与沉淀", [
        ("知识库", 3), ("笔记", 3), ("拆书", 4), ("蒸馏", 4), ("资料", 2),
        ("读书", 2), ("卡片", 2), ("复盘", 2), ("记忆", 2), ("沉淀", 2),
        ("中医", 3), ("经方", 3), ("医案", 3),
    ]),
    ("strategy", "商业与决策", [
        ("商业", 3), ("决策", 3), ("战略", 3), ("jtbd", 3), ("诊断", 2),
        ("对标", 2), ("增长", 2), ("定位", 2), ("商业模式", 3),
    ]),
    ("business", "企业与交付", [
        ("客户", 3), ("交付", 3), ("报价", 3), ("发票", 3), ("sop", 3),
        ("crm", 3), ("销售", 3), ("商单", 3), ("合同", 2), ("订单", 2),
        ("课程", 3),
    ]),
    ("office", "办公与协作", [
        ("表格", 3), ("文档", 3), ("excel", 3), ("ppt", 3), ("word", 3),
        ("周报", 3), ("邮件", 3), ("钉钉", 3), ("飞书", 3), ("企业微信", 3),
        ("会议", 2), ("日程", 2), ("协作", 2), ("office", 2), ("签到", 2),
        ("校对", 3), ("润色", 3),
    ]),
    ("dev", "开发与工具", [
        ("部署", 3), ("调试", 3), ("git", 3), ("技能管理", 3), ("技能管家", 3),
        ("技能创建", 3),
        ("cli", 2), ("代码", 2), ("脚本", 2), ("自动化", 2), ("python", 2),
        ("node", 2), ("mcp", 2), ("数据库", 2), ("浏览器", 1), ("api", 1),
        ("skill", 1), ("agent", 1),
    ]),
]
CATEGORY_IDS = {c[0] for c in CATEGORIES} | {"other"}
CATEGORY_LABELS = {c[0]: c[1] for c in CATEGORIES}
CATEGORY_LABELS["other"] = "其他技能"

KNOWN_NAMES = {
    # 视频 / 视觉
    "faceless-explainer": "无脸解说视频",
    "general-video": "通用视频制作",
    "cinema-os": "AI 视频导演",
    "hyperframes": "Hyperframes 帧动画",
    "hyperframes-animation": "Hyperframes 动画",
    "hyperframes-audio": "Hyperframes 音频",
    "hyperframes-cli": "Hyperframes 命令行",
    "hyperframes-core": "Hyperframes 核心",
    "hyperframes-creative": "Hyperframes 创意",
    "hyperframes-keyframes": "Hyperframes 关键帧",
    "hyperframes-registry": "Hyperframes 组件库",
    "hyperframes-studio": "Hyperframes 工作台",
    "dark-infographic-video": "暗黑图解视频",
    "workbuddy-replica-video": "参考片复刻",
    "workbuddy-tutorial-video": "WorkBuddy 教程视频",
    "visual-tutorial-video": "可视化教程视频",
    "psych-kepu-video": "心理科普视频",
    "vibe-knowledge": "Vibe 知识动画",
    "create-outfit-transition-video": "服装换装视频",
    "promo-creator-skills": "产品宣传片",
    "topic-card-video": "话题卡片视频",
    "workbuddy-chat-rap-video": "说唱聊天视频",
    "space-video-cover": "视频封面",
    "jianying-editor-skill-ai": "剪映剪辑",
    "jianying-draft-pipeline": "剪映草稿流水线",
    # 内容 / 公众号
    "aihot": "AI 热点资讯",
    "ai-trending-topics": "AI 爆款选题",
    "content-planner": "选题与内容日历",
    "content-strategy": "内容策略",
    "viral-title": "爆款标题",
    "viral-video-topics": "爆款视频选题",
    "wechat-formatter": "公众号排版",
    "wechat-cover-generator": "公众号封面",
    "wechat-ninegrid": "朋友圈九宫格",
    "wechat-article-downloader": "公众号文章下载",
    "wechat-article-search": "公众号文章搜索",
    "wechat-auto-publisher": "公众号自动发布",
    "wechat-autopilot-main-account": "公众号托管",
    "wechat-remote-push": "公众号远程推送",
    "wechat-fixed-ip-publish": "固定 IP 发布",
    "wechat-10w-hot": "10w+ 热点",
    "gzh-topic-intake": "公众号选题采集",
    "article-to-cards": "文章转卡片",
    "article-illustrator": "文章配图",
    "cover-pop": "封面图生成",
    "wechat-to-koubo": "文章转口播",
    "multi-platform-publisher-ent": "多平台发布",
    "toutiao-article": "头条文章",
    "toutiao-news-rewrite": "头条新闻改写",
    "toutiao-travel-agent": "头条旅游写作",
    "toutiao-travel-rewrite": "头条旅游改写",
    "toutiao-sports": "头条体育写作",
    "toutiao-entertainment": "头条娱乐写作",
    "toutiao-agent-setup": "头条 Agent 搭建",
    "ai工具评测公众号": "AI 工具评测",
    # 设计 / 图像
    "photo-to-cartoon": "照片转卡通",
    "pindou-blueprint": "拼豆图纸",
    "ian-xiaohei-illustrations": "小黑正文配图",
    "imagegen": "图像生成",
    # 知识 / 方法
    "cangjie-skill": "仓颉 Skill 蒸馏",
    "seed-thinking": "种子思维",
    "thought-sprout": "思维发芽",
    "hypit": "Hypit 视频",
    "nihaixia": "倪海厦中医",
    "zsxq": "知识星球",
    "ima-skills": "IMA 知识库",
    "skill-creator": "技能创建器",
    "text-proofread": "中文校对",
    "humanizer": "去 AI 味",
    "release-archive": "发布归档",
    # 商业 / 办公
    "dbs": "商业工具箱",
    "dbs-action": "执行阻滞诊断",
    "dbs-benchmark": "对标筛选",
    "dbs-chatroom": "专家聊天室",
    "dbs-chatroom-austrian": "奥派聊天室",
    "dbs-decision": "决策立案",
    "dbs-deconstruct": "概念拆解",
    "dbs-diagnosis": "商业模式诊断",
    "dbs-hook": "旧版钩子",
    "dbs-jtbd": "JTBD 分析",
    "dbs-learning": "主题学习",
    "dbs-restore": "恢复诊断存档",
    "dbs-save": "保存诊断存档",
    "dbs-spread": "传播机制拆解",
    "dbs-update": "更新 dbskill",
    "dbs-xhs-title": "小红书标题",
    "dbs-content-risk-check": "内容风险检查",
    "dbs-content-value": "内容价值评估",
    "dbs-agent-migration": "规则文件迁移",
    "dbs-ai-check": "AI 痕迹检测",
    "dbs-report": "诊断报告",
    "dbs-standard-answer": "标准答案",
    "dbs-theory-grounding": "理论依据",
    "dbs-knowledge": "知识库",
    "dbs-script-flow": "脚本流程",
    "dbs-skill-maker": "技能生成",
    "dbs-title-cover-intro": "标题封面导语",
    "dbs-video-extract": "视频拆解",
    "dbs-video-navigation": "视频导航",
    "dbs-wechat-html": "公众号 HTML",
    "dbs-resonate": "共鸣分析",
    "dbs-goal": "目标梳理",
    "dbs-good-question": "好问题",
    "dbs-human-dispatch": "人工派发",
    "dbs-install-skill": "安装技能",
    "dbs-content": "内容诊断",
    "dbs-content-system": "内容系统",
    "action-campaign-goal-execution": "目标执行",
    "child-recognition-book": "幼儿识字书",
    "course-business-workflow": "课程业务流",
    "delivery-kickoff": "交付启动",
    "delivery-inspector": "交付检查",
    "delivery-to-growth": "交付转增长",
    "product-matrix-builder": "产品矩阵",
    "pricing-guardian": "定价守门",
    "lead-ops-console": "线索运营",
    "workbuddy-geo-rewriter": "GEO 改写",
    "tourism-guide-harvester__skillhub": "旅游攻略采集",
    "ctrip-travel-writer-v2__skillhub": "携程旅游写作",
    "cclean__skillhub": "C 盘清理",
    "trending-hub-pro__skillhub": "趋势雷达",
    "wx-gzh-link-crawler": "公众号链接抓取",
    "media-use": "媒体素材库",
    "product-launch-video": "产品发布视频",
    "openai-docs": "OpenAI 文档",
    "review-agent": "代码评审",
    "skill-installer": "技能安装器",
    "playwright": "浏览器自动化",
    "find-skills": "技能查找",
    "bggg-creator-image2ppt": "图片转 PPT",
    "yuanliuwei-writer": "袁六伟文风写作",
    "khazix-writer": "卡兹克文风写作",
    "replicate-video-ad": "参考广告复刻",
    "crypto-failure-fingerprint": "加密故障指纹",
    "drama-commerce-production": "剧情带货视频",
    "lincong-wechat-draft": "公众号排版推送",
    "lincong-writer": "林聪文风写作",
    "pindou-template-update": "拼豆模板更新",
    "red-white-explainer": "红白图解视频",
    "wx-cli-win": "微信数据 CLI",
    "weread-skills": "微信读书助手",
    "3d-map-video": "三维地图视频",
    "dual-account-content-factory-v5-codex": "双账号内容工厂",
    "experience-extraction-mentor": "经验萃取教练",
    "image-story-video-wizard": "图片故事视频",
    "wechat-moments-camp": "朋友圈训练营",
    "wechat-sticker": "微信贴图",
    "xhs-ecommerce-ops": "小红书电商运营",
    "huixin-skills-manager": "汇芯技能管家",
}

_CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")


def has_cjk(text: str) -> bool:
    return bool(text and _CJK.search(text))


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\u3000", " ")).strip()


def load_state() -> dict:
    data = json.loads(json.dumps(DEFAULT_STATE))
    try:
        raw = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return data
    if not isinstance(raw, dict):
        return data
    if isinstance(raw.get("collections"), list):
        data["collections"] = sanitize_collections(raw["collections"])
    if isinstance(raw.get("overrides"), dict):
        data["overrides"] = sanitize_overrides(raw["overrides"])
    if isinstance(raw.get("pins"), list):
        data["pins"] = [str(k) for k in raw["pins"] if isinstance(k, str)][:2000]
    if isinstance(raw.get("projects"), list):
        data["projects"] = [str(k) for k in raw["projects"] if isinstance(k, str)][:50]
    if isinstance(raw.get("settings"), dict):
        for key, value in raw["settings"].items():
            if key in data["settings"] and isinstance(value, type(data["settings"][key])):
                data["settings"][key] = value
    return data


def sanitize_collections(items) -> list:
    out = []
    for item in items[:200]:
        if not isinstance(item, dict):
            continue
        cid = str(item.get("id") or "").strip()[:64]
        name = str(item.get("name") or "").strip()[:40]
        keys = item.get("keys")
        if not cid or not name:
            continue
        out.append({
            "id": cid,
            "name": name,
            "keys": [str(k) for k in (keys or []) if isinstance(k, str)][:2000],
        })
    return out


def sanitize_overrides(items) -> dict:
    out = {}
    for key, value in list(items.items())[:5000]:
        if isinstance(key, str) and value in CATEGORY_IDS and value != "other":
            out[key[:1000]] = value
    return out


def save_state(state: dict) -> dict:
    cleaned = {
        "collections": sanitize_collections(state.get("collections") or []),
        "overrides": sanitize_overrides(state.get("overrides") or {}),
        "pins": [str(k)[:1000] for k in (state.get("pins") or []) if isinstance(k, str)][:2000],
        "projects": [str(k)[:500] for k in (state.get("projects") or []) if isinstance(k, str)][:50],
        "settings": {},
    }
    incoming = state.get("settings") or {}
    for key, default in DEFAULT_STATE["settings"].items():
        value = incoming.get(key, default)
        cleaned["settings"][key] = value if isinstance(value, type(default)) else default
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, STATE_PATH)
    return cleaned


# ---------------------------------------------------------------- 解析

FM_BLOCK = re.compile(r"\A\ufeff?---\r?\n(.*?)\r?\n---\s*(?:\r?\n|$)", re.S)


def parse_frontmatter(text: str) -> dict:
    match = FM_BLOCK.match(text)
    if not match:
        return {}
    lines = match.group(1).splitlines()
    data = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        km = re.match(r"^([A-Za-z0-9_.-]+)\s*:\s*(.*)$", line)
        if not km:
            i += 1
            continue
        key, value = km.group(1), km.group(2).strip()
        if value in (">", ">-", ">+", "|", "|-", "|+"):
            style = value[0]
            i += 1
            parts = []
            while i < len(lines):
                cur = lines[i]
                if cur.strip() and not cur.startswith((" ", "\t")):
                    break
                parts.append(cur.strip())
                i += 1
            if style == "|":
                data[key] = "\n".join(parts).strip()
            else:
                folded = " ".join(part for part in parts if part)
                folded = re.sub(r"(?<=[\u4e00-\u9fff，。、；：！？])\s+(?=[\u4e00-\u9fff])", "", folded)
                data[key] = normalize_ws(folded)
            continue
        if value[:1] in ("'", '"'):
            quote = value[0]
            body = value[1:]
            if body.endswith(quote) and len(body) >= 1:
                data[key] = body[:-1]
                i += 1
                continue
            buf = [body]
            i += 1
            while i < len(lines):
                cur = lines[i].strip()
                buf.append(cur)
                i += 1
                if cur.endswith(quote):
                    break
            data[key] = " ".join(buf).rstrip(quote).strip()
            continue
        data[key] = value
        i += 1
    return data


def extract_title(desc: str) -> str:
    text = desc.strip().strip("\"'“”「」 ")
    text = re.sub(r"^(当用户|用户)(说|提到|要求|需要)[^，,。]*[，,。]?\s*", "", text)
    text = re.sub(r"^【[^】]*】\s*", "", text)
    bracket = re.split(r"[（(]", text, maxsplit=1)[0].strip()
    if len(bracket) >= 6:
        text = bracket
    for part in re.split(r"[，,。；;：:！!？?\n]", text):
        part = part.strip()
        if len(part) >= 6:
            text = part
            break
    text = text.strip(" -—·:：\"'“”「」")
    if len(text) > 18:
        text = text[:18].rstrip("，,、 ") + "…"
    return text


def pick_display_name(name: str, folder: str, desc: str) -> str:
    for cand in (folder, name):
        if cand and has_cjk(cand) and not cand.startswith(("_", ".")):
            return cand.strip()
    for cand in (name, folder):
        hit = KNOWN_NAMES.get((cand or "").lower())
        if hit:
            return hit
    if has_cjk(desc):
        title = extract_title(desc)
        if len(title) >= 2:
            return title
    if desc:
        first = re.split(r"[.。!?！？\n]", desc.strip(), maxsplit=1)[0].strip(" -—·:：")
        if len(first) >= 3:
            return first[:30] + ("…" if len(first) > 30 else "")
    return (name or folder or "未命名技能").strip()


def classify(name: str, folder: str, desc: str, path: str) -> str:
    folder_low = (folder or "").lower()
    name_low = (name or "").lower()
    if name_low.startswith("dbs") and any(k in name_low for k in ("wechat", "xhs", "gzh")):
        return "wechat"
    if folder_low.startswith("dbs") or name_low.startswith("dbs"):
        return "strategy"
    if folder_low.startswith("hyperframes"):
        return "video"
    display = KNOWN_NAMES.get(name_low) or KNOWN_NAMES.get(folder_low) or ""
    hay_name = f"{name} {folder} {display}".lower()
    hay_desc = desc.lower()
    hay_path = path.lower()
    best, best_score = "other", 0
    for cid, _label, keywords in CATEGORIES:
        score = 0
        for kw, weight in keywords:
            if kw in hay_name:
                score += weight * 2
            elif kw in hay_desc:
                score += weight
            elif kw in hay_path:
                score += 1
        if score > best_score:
            best, best_score = cid, score
    return best if best_score >= 3 else "other"


# ---------------------------------------------------------------- 扫描

def source_defs() -> list:
    return [
        {"id": "workbuddy", "label": "WorkBuddy", "color": "#2563eb",
         "paths": [HOME / ".workbuddy" / "skills"]},
        {"id": "claude", "label": "Claude Code", "color": "#c2410c",
         "paths": [HOME / ".claude" / "skills"]},
        {"id": "codex", "label": "Codex", "color": "#0f766e",
         "paths": [HOME / ".codex" / "skills"]},
        {"id": "gemini", "label": "Gemini", "color": "#4338ca",
         "paths": [HOME / ".gemini" / "skills", HOME / ".gemini" / "config" / "skills"]},
        {"id": "grok", "label": "Grok Bot", "color": "#7e22ce",
         "paths": [HOME / ".grokbot" / "skills"]},
        {"id": "agents", "label": "Agents 共享", "color": "#be123c",
         "paths": [HOME / ".agents" / "skills"]},
    ]


def iter_skill_files(root: Path, show_backups: bool):
    if not root.exists():
        return
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        kept = []
        for name in dirnames:
            if name in SKIP_DIR_NAMES:
                continue
            if not show_backups and name.startswith("_backup"):
                continue
            kept.append(name)
        dirnames[:] = kept
        base = Path(dirpath)
        if "SKILL.md" in filenames:
            yield base / "SKILL.md", base
            dirnames[:] = []
            continue
        md_files = [
            f for f in filenames
            if f.lower().endswith(".md") and f.lower() not in MD_SKIP_NAMES
        ]
        if len(md_files) == 1 and md_files[0].lower() == f"{base.name}.md".lower():
            yield base / md_files[0], base


def make_key(path: Path) -> str:
    return hashlib.sha1(str(path).lower().encode("utf-8")).hexdigest()[:16]


class Scanner:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.skills: list = []
        self.revision = ""
        self.scanned_at = 0.0
        self.extra_roots: list = []
        self.source_counts: dict = {}

    def compute_revision(self, show_backups: bool) -> str:
        digest = hashlib.md5()
        for definition in source_defs():
            for root in definition["paths"]:
                if not root.exists():
                    continue
                for md, _folder in iter_skill_files(root, show_backups):
                    try:
                        stat = md.stat()
                        digest.update(f"{md}|{stat.st_mtime_ns}|{stat.st_size}".encode("utf-8"))
                    except OSError:
                        continue
        for root in self.extra_roots:
            for md, _folder in iter_skill_files(Path(root), show_backups):
                try:
                    stat = md.stat()
                    digest.update(f"{md}|{stat.st_mtime_ns}|{stat.st_size}".encode("utf-8"))
                except OSError:
                    continue
        return digest.hexdigest()

    def scan(self, force: bool = False) -> list:
        with self.lock:
            state = load_state()
            settings = state["settings"]
            now = time.time()
            if not force and self.skills and now - self.scanned_at < 2.0:
                return self.skills

            show_backups = bool(settings.get("showBackups"))
            merged: dict = {}
            counts: dict = {}

            roots = []
            for definition in source_defs():
                for root in definition["paths"]:
                    if root.exists():
                        roots.append((definition["id"], definition["label"], root, False))
            for project in state.get("projects") or []:
                base = Path(os.path.expandvars(os.path.expanduser(project)))
                if not base.exists():
                    continue
                for sub in (".workbuddy/skills", ".claude/skills", ".agents/skills",
                            ".gemini/skills", ".grokbot/skills", "skills"):
                    candidate = base / sub
                    if candidate.exists():
                        roots.append(("project", "项目", candidate, True))
            for extra in self.extra_roots:
                path = Path(extra)
                if path.exists():
                    roots.append(("project", "项目", path, True))

            for source_id, source_label, root, is_project in roots:
                for md_path, folder in iter_skill_files(root, show_backups):
                    skill = self._build_skill(md_path, folder, root, source_id,
                                              source_label, is_project, settings)
                    if not skill:
                        continue
                    key = skill["key"]
                    if key in merged:
                        if skill["source"] not in merged[key]["sources"]:
                            merged[key]["sources"].append(skill["source"])
                            merged[key]["sourceLabels"].append(skill["sourceLabel"])
                        continue
                    merged[key] = skill
                    counts[source_id] = counts.get(source_id, 0) + 1

            self.skills = list(merged.values())
            self.source_counts = counts
            self.scanned_at = now
            self.revision = self.compute_revision(show_backups)
            return self.skills

    def _build_skill(self, md_path: Path, folder: Path, root: Path, source_id: str,
                     source_label: str, is_project: bool, settings: dict):
        try:
            raw = md_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return None
        meta = parse_frontmatter(raw)
        name = str(meta.get("name") or "").strip()
        desc = normalize_ws(str(meta.get("description") or ""))
        folder_name = folder.name
        if not name:
            name = folder_name
        display = pick_display_name(name, folder_name, desc)
        try:
            stat = md_path.stat()
            updated = int(stat.st_mtime)
            size = stat.st_size
        except OSError:
            updated, size = 0, 0

        suite = None
        if folder.parent != root:
            suite = folder.parent.name
        builtin = ".system" in md_path.parts or "builtin" in str(md_path).lower()

        category = classify(name, folder_name, desc, str(md_path))
        return {
            "key": make_key(md_path),
            "name": name,
            "displayName": display,
            "folder": folder_name,
            "description": desc[:400],
            "source": source_id,
            "sourceLabel": source_label,
            "sources": [source_id],
            "sourceLabels": [source_label],
            "path": str(md_path),
            "dir": str(folder),
            "category": category,
            "suite": suite,
            "builtin": builtin,
            "project": is_project,
            "updatedAt": updated,
            "size": size,
        }

    def find(self, key: str):
        for skill in self.skills:
            if skill["key"] == key:
                return skill
        return None


SCANNER = Scanner()


def build_payload() -> dict:
    state = load_state()
    skills = SCANNER.scan()
    overrides = state["overrides"]
    pins = set(state["pins"])

    items = []
    cat_counts = {cid: 0 for cid in CATEGORY_LABELS}
    source_counts = {}
    for skill in skills:
        item = dict(skill)
        item["category"] = overrides.get(skill["key"], skill["category"])
        item["categoryLabel"] = CATEGORY_LABELS.get(item["category"], "其他技能")
        item["pinned"] = skill["key"] in pins
        item["collectionIds"] = [
            c["id"] for c in state["collections"] if skill["key"] in c["keys"]
        ]
        cat_counts[item["category"]] = cat_counts.get(item["category"], 0) + 1
        for sid in skill["sources"]:
            source_counts[sid] = source_counts.get(sid, 0) + 1
        items.append(item)

    sources = []
    for definition in source_defs():
        count = source_counts.get(definition["id"], 0)
        if count == 0:
            continue
        sources.append({
            "id": definition["id"],
            "label": definition["label"],
            "color": definition["color"],
            "count": count,
            "exists": any(p.exists() for p in definition["paths"]),
        })
    project_count = source_counts.get("project", 0)
    if project_count:
        sources.append({"id": "project", "label": "项目", "color": "#475569",
                        "count": project_count, "exists": True})

    categories = [
        {"id": "all", "label": "全部技能", "count": len(items)},
        {"id": "pinned", "label": "我的收藏", "count": sum(1 for i in items if i["pinned"])},
    ]
    for cid, label in CATEGORY_LABELS.items():
        if cid == "other":
            continue
        categories.append({"id": cid, "label": label, "count": cat_counts.get(cid, 0)})
    categories.append({"id": "other", "label": "其他技能", "count": cat_counts.get("other", 0)})

    return {
        "app": APP_NAME,
        "version": VERSION,
        "generatedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
        "revision": SCANNER.revision,
        "statePath": str(STATE_PATH),
        "skills": items,
        "categories": categories,
        "collections": state["collections"],
        "overrides": overrides,
        "pins": state["pins"],
        "projects": state["projects"],
        "settings": state["settings"],
        "sources": sources,
        "stats": {
            "total": len(items),
            "sources": len(sources),
            "pinned": sum(1 for i in items if i["pinned"]),
            "collections": len(state["collections"]),
        },
    }


# ---------------------------------------------------------------- 打开文件

def reveal_in_explorer(path: Path) -> bool:
    try:
        if os.name == "nt":
            subprocess.Popen(["explorer", f"/select,{path}"])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path.parent)])
        return True
    except Exception:
        return False


def open_with_default(path: Path) -> bool:
    try:
        if os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- HTTP

MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".json": "application/json; charset=utf-8",
}
STATIC_FILES = {"/", "/index.html", "/app.css", "/app.js", "/favicon.svg"}


class Handler(BaseHTTPRequestHandler):
    server_version = f"HuixinSkills/{VERSION}"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # noqa: A003
        pass

    @property
    def token(self) -> str:
        return getattr(self.server, "token", "")

    def _send(self, body: bytes, status=200, content_type="text/plain; charset=utf-8",
              extra_headers=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if extra_headers:
            for key, value in extra_headers.items():
                self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, obj, status=200):
        self._send(json.dumps(obj, ensure_ascii=False).encode("utf-8"), status,
                   "application/json; charset=utf-8")

    def _query(self) -> dict:
        return {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}

    def _authorized(self, query: dict) -> bool:
        header = self.headers.get("X-Token", "")
        return bool(self.token) and (header == self.token or query.get("t") == self.token)

    def _body(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return None
        if length <= 0 or length > 4_000_000:
            return None
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            return None

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        route, query = parsed.path, self._query()

        if route in STATIC_FILES:
            return self._serve_static(route)

        if route == "/api/bootstrap":
            SCANNER.scan(force=query.get("force") == "1")
            return self._json(build_payload())

        if route == "/api/revision":
            show_backups = bool(load_state()["settings"].get("showBackups"))
            revision = SCANNER.compute_revision(show_backups)
            SCANNER.revision = revision
            return self._json({"revision": revision, "total": len(SCANNER.skills)})

        if route == "/api/skill":
            key = query.get("key", "")
            skill = SCANNER.find(key)
            if not skill:
                return self._json({"error": "not found"}, 404)
            try:
                markdown = Path(skill["path"]).read_text(encoding="utf-8", errors="replace")
            except Exception as exc:
                return self._json({"error": str(exc)}, 500)
            return self._json({
                "key": key,
                "name": skill["name"],
                "displayName": skill["displayName"],
                "path": skill["path"],
                "markdown": markdown,
            })

        if route == "/api/export":
            payload = build_payload()
            body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            return self._send(body, 200, "application/json; charset=utf-8", {
                "Content-Disposition": 'attachment; filename="huixin-skills-export.json"',
            })

        return self._json({"error": "not found"}, 404)

    def do_POST(self):  # noqa: N802
        parsed = urlparse(self.path)
        route, query = parsed.path, self._query()
        if not self._authorized(query):
            return self._json({"error": "forbidden"}, 403)
        body = self._body()

        if route == "/api/state":
            if not isinstance(body, dict):
                return self._json({"error": "bad body"}, 400)
            saved = save_state(body)
            return self._json({"ok": True, "state": saved})

        if route in ("/api/reveal", "/api/open"):
            if not isinstance(body, dict):
                return self._json({"error": "bad body"}, 400)
            skill = SCANNER.find(str(body.get("key") or ""))
            if not skill:
                return self._json({"error": "unknown skill"}, 404)
            target = Path(skill["path"])
            ok = reveal_in_explorer(target) if route == "/api/reveal" else open_with_default(target)
            return self._json({"ok": bool(ok)})

        if route == "/api/refresh":
            SCANNER.scan(force=True)
            return self._json({"ok": True, "total": len(SCANNER.skills),
                               "revision": SCANNER.revision})

        return self._json({"error": "not found"}, 404)

    def _serve_static(self, route: str):
        name = "index.html" if route in ("/", "/index.html") else route.lstrip("/")
        path = (WEB_DIR / name).resolve()
        if not str(path).startswith(str(WEB_DIR.resolve())) or not path.exists():
            return self._send(b"Not Found", 404)
        mime = MIME.get(path.suffix.lower(), "application/octet-stream")
        return self._send(path.read_bytes(), 200, mime)


def find_port(preferred: int) -> int:
    import socket
    for offset in range(30):
        port = preferred + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise SystemExit("没有可用端口（8765-8794 全被占用）")


def main() -> None:
    parser = argparse.ArgumentParser(description=f"{APP_NAME} Windows 本地版")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--token", default="", help="固定访问令牌（仅调试用）")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--extra-root", action="append", default=[],
                        help="额外扫描目录，可重复")
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    SCANNER.extra_roots = args.extra_root
    port = find_port(args.port)
    token = args.token or secrets.token_urlsafe(18)

    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    httpd.token = token  # type: ignore[attr-defined]
    httpd.daemon_threads = True

    url = f"http://127.0.0.1:{port}/?t={token}"
    print("=" * 56)
    print(f"  {APP_NAME}  v{VERSION}")
    print(f"  地址：{url}")
    print(f"  数据：{STATE_PATH}")
    print("  关闭此窗口即停止服务")
    print("=" * 56)

    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
