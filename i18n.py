#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
i18n.py —— 论文多语言层（第 92 轮建）

为什么单独一层
--------------
之前所有英文 text 都硬编码在 paper.py 里。要「全面转多语言」，
不是把 100 处字符串逐个翻译，而是把"可翻译的结构"抽出来：
章节标题、图注前缀、固定短语、摘要框架。
**数据相关的内容（列名、数值、结论句）仍走各自的英文化流程** ——
那些要靠 describe()/label_en()，与语言包是两件事。

引擎差异（实测）
----------------
    pdflatex   拉丁字母，最稳
    xelatex    + fontspec + babel，能排西里尔/希腊
    中日韩      需要 ctex 或 xeCJK —— 本机 MiKTeX 未安装（已查）
所以 LANGS 里每种语言自己声明引擎与所需宏包，
生成时据此挑引擎，缺包时**明确报出来**而不是编译成一堆问号。
"""

from __future__ import annotations

# ══════════════════════════════════════════════════════════════════════
#  语言表
# ══════════════════════════════════════════════════════════════════════
LANGS = {
    "en": dict(
        name="English", native="English", engine="pdflatex",
        babel=None, extra_pkgs=[], needs=[],
        font=r"C:\Windows\Fonts\arial.ttf",
        sections=["Summary", "Introduction", "Assumptions and Notations",
                  "Model Formulation", "Model Solution and Results",
                  "Sensitivity Analysis", "Evaluation", "References",
                  "Appendix"],
        phrases=dict(
            figure="Figure", table="Table", where="where",
            team="Team", page="Page",
            assumptions="Assumptions", notations="Notations",
            limitations="Limitations", strengths="Strengths",
            governing="Governing relations", dimensionless="Dimensionless groups",
            model_selection="Model selection", sensitivity="Sensitivity",
            core_code="Core Code", keywords="Keywords",
        ),
    ),
    "zh": dict(
        name="Chinese", native="中文", engine="xelatex",
        babel=None, extra_pkgs=["ctex"], needs=["ctex"],
        font=r"C:\Windows\Fonts\msyh.ttc",
        sections=["摘要", "问题重述", "模型假设与符号说明",
                  "模型建立", "模型求解与结果",
                  "敏感性分析", "模型评价", "参考文献", "附录"],
        phrases=dict(
            figure="图", table="表", where="其中",
            team="队号", page="第",
            assumptions="模型假设", notations="符号说明",
            limitations="模型局限", strengths="模型优点",
            governing="控制方程", dimensionless="无量纲数",
            model_selection="模型选择", sensitivity="敏感性",
            core_code="核心代码", keywords="关键词",
        ),
    ),
    "ja": dict(
        name="Japanese", native="日本語", engine="xelatex",
        babel=None, extra_pkgs=["ctex"], needs=["ctex"],
        font=r"C:\Windows\Fonts\msyh.ttc",
        sections=["概要", "はじめに", "仮定と記号",
                  "モデル定式化", "解法と結果",
                  "感度分析", "評価", "参考文献", "付録"],
        phrases=dict(
            figure="図", table="表", where="ここで",
            team="チーム", page="ページ",
            assumptions="仮定", notations="記号",
            limitations="限界", strengths="長所",
            governing="支配方程式", dimensionless="無次元数",
            model_selection="モデル選択", sensitivity="感度",
            core_code="コアコード", keywords="キーワード",
        ),
    ),
    "ko": dict(
        name="Korean", native="한국어", engine="xelatex",
        babel=None, extra_pkgs=["ctex"], needs=["ctex"],
        font=r"C:\Windows\Fonts\msyh.ttc",
        sections=["요약", "서론", "가정과 기호",
                  "모델 정식화", "해법과 결과",
                  "민감도 분석", "평가", "참고문헌", "부록"],
        phrases=dict(
            figure="그림", table="표", where="여기서",
            team="팀", page="페이지",
            assumptions="가정", notations="기호",
            limitations="한계", strengths="장점",
            governing="지배방정식", dimensionless="무차원수",
            model_selection="모델 선택", sensitivity="민감도",
            core_code="핵심 코드", keywords="키워드",
        ),
    ),
    "fr": dict(
        name="French", native="Français", engine="xelatex",
        babel="french", extra_pkgs=[], needs=[],
        font=r"C:\Windows\Fonts\arial.ttf",
        sections=["Résumé", "Introduction", "Hypothèses et notations",
                  "Formulation du modèle", "Solution et résultats",
                  "Analyse de sensibilité", "Évaluation",
                  "Références", "Annexe"],
        phrases=dict(
            figure="Figure", table="Tableau", where="où",
            team="Équipe", page="Page",
            assumptions="Hypothèses", notations="Notations",
            limitations="Limites", strengths="Points forts",
            governing="Équations gouvernantes",
            dimensionless="Groupes sans dimension",
            model_selection="Sélection du modèle",
            sensitivity="Sensibilité", core_code="Code principal",
            keywords="Mots-clés",
        ),
    ),
    "de": dict(
        name="German", native="Deutsch", engine="xelatex",
        babel="ngerman", extra_pkgs=[], needs=[],
        font=r"C:\Windows\Fonts\arial.ttf",
        sections=["Zusammenfassung", "Einleitung",
                  "Annahmen und Notation", "Modellformulierung",
                  "Lösung und Ergebnisse", "Sensitivitätsanalyse",
                  "Bewertung", "Literatur", "Anhang"],
        phrases=dict(
            figure="Abbildung", table="Tabelle", where="wobei",
            team="Team", page="Seite",
            assumptions="Annahmen", notations="Notation",
            limitations="Grenzen", strengths="Stärken",
            governing="Grundgleichungen",
            dimensionless="Dimensionslose Kennzahlen",
            model_selection="Modellauswahl",
            sensitivity="Sensitivität", core_code="Kerncode",
            keywords="Schlagwörter",
        ),
    ),
    "es": dict(
        name="Spanish", native="Español", engine="xelatex",
        babel="spanish", extra_pkgs=[], needs=[],
        font=r"C:\Windows\Fonts\arial.ttf",
        sections=["Resumen", "Introducción", "Supuestos y notación",
                  "Formulación del modelo", "Solución y resultados",
                  "Análisis de sensibilidad", "Evaluación",
                  "Referencias", "Apéndice"],
        phrases=dict(
            figure="Figura", table="Tabla", where="donde",
            team="Equipo", page="Página",
            assumptions="Supuestos", notations="Notación",
            limitations="Limitaciones", strengths="Fortalezas",
            governing="Ecuaciones gobernantes",
            dimensionless="Grupos adimensionales",
            model_selection="Selección del modelo",
            sensitivity="Sensibilidad", core_code="Código principal",
            keywords="Palabras clave",
        ),
    ),
    "ru": dict(
        name="Russian", native="Русский", engine="xelatex",
        babel="russian", extra_pkgs=[], needs=[],
        font=r"C:\Windows\Fonts\arial.ttf",
        sections=["Аннотация", "Введение", "Допущения и обозначения",
                  "Формулировка модели", "Решение и результаты",
                  "Анализ чувствительности", "Оценка",
                  "Литература", "Приложение"],
        phrases=dict(
            figure="Рисунок", table="Таблица", where="где",
            team="Команда", page="Стр.",
            assumptions="Допущения", notations="Обозначения",
            limitations="Ограничения", strengths="Преимущества",
            governing="Управляющие уравнения",
            dimensionless="Безразмерные комплексы",
            model_selection="Выбор модели",
            sensitivity="Чувствительность", core_code="Основной код",
            keywords="Ключевые слова",
        ),
    ),
}

DEFAULT = "en"


def get(lang: str) -> dict:
    """取语言包；不认识的回落到英文（并保留请求的键，便于报错）。"""
    return LANGS.get(str(lang or DEFAULT).lower().replace("_", "-")[:2],
                     LANGS[DEFAULT])


def t(lang: str, key: str, default: str = "") -> str:
    """取一个固定短语。"""
    return get(lang)["phrases"].get(key, default or key)


def sections(lang: str) -> list:
    return get(lang)["sections"]


def engine(lang: str) -> str:
    return get(lang)["engine"]


def preamble_extra(lang: str) -> list:
    """该语言需要的额外 \\usepackage 行。"""
    p = get(lang)
    out = []
    for pk in p.get("extra_pkgs") or []:
        out.append(f"\\usepackage{{{pk}}}")
    if p.get("babel"):
        out.append(f"\\usepackage[{p['babel']}]{{babel}}")
    return out


def missing(lang: str, have: dict) -> list:
    """该语言缺哪些宏包。have 形如 {'ctex': False, 'fontspec': True}。"""
    p = get(lang)
    return [k for k in (p.get("needs") or []) if not have.get(k)]


def available() -> list:
    return sorted(LANGS)


# ══════════════════════════════════════════════════════════════════════
#  章节标题：每种语言一份**独立**的文本
#
#  为什么不用「英文原文 + 后处理替换」
#  ----------------------------------
#  替换式做法（拿英文当模板逐句 replace）会让两种语言互相干扰：
#  改一句英文，两种语言的输出都跟着变；中文里想调整语序也没法调，
#  因为中文是从英文派生的。
#  这里每种语言各写各的，英文那份**逐字照抄现在的论文**，
#  中文那份独立撰写。两者之间没有运行时依赖。
#
#  占位符用 <<name>> 而不是 {name}：LaTeX 正文里 { } 是分组括号，
#  用 str.format 会把它们全当占位。
# ══════════════════════════════════════════════════════════════════════

SECT = {
    "en": {
        "limitations": "Limitations",
        "intro": "Introduction",
        "assumptions": "Assumptions and Notations",
        "mech": "Mechanistic basis",
        "p1": "Problem 1: How the geometry governs <<y>>",
        "p2": "Problem 2: Design selection under constraints",
        "p3": "Problem 3: How stable are the conclusions?",
        "p4": "Problem 4: Does the choice survive a change of priorities?",
        "p5": "Problem 5: Can this design be manufactured?",
        "eval": "Evaluation",
        "disclosure": "AI Disclosure and Human Verification",
        "code": "Core Code",
    },
    "zh": {
        "limitations": "局限性",
        "intro": "引言",
        "assumptions": "模型假设与符号说明",
        "mech": "机理基础",
        "p1": "第 1 问：几何结构如何决定 <<y>>",
        "p2": "第 2 问：约束条件下的方案选择",
        "p3": "第 3 问：结论有多稳定",
        "p4": "第 4 问：优先级变化后结论是否依然成立",
        "p5": "第 5 问：该方案能否被制造出来",
        "eval": "模型评价",
        "disclosure": "AI 使用声明与人工核验",
        "code": "核心代码",
    },
}

# 各语言自己的段落文本（摘要、结论、表头、图注……）。
# 结构同 SECT：每种语言一份，不共享模板。
BODY = {
    "en": {},
    "zh": {},
}


def is_en(lang: str) -> bool:
    """是不是英文。"""
    return not lang or str(lang).lower().startswith("en")


def name(lang: str, orig: str, en: str = "") -> str:
    """按语言取名称：英文用 en（英文化后的名字），中文用原名。

    这是「两种语言互不干扰」的关键入口 —— 列名、模型名、指标名
    全部走它。中文版不该出现 thermal resistance 这种英文列名，
    英文版也不该出现「产量」。
    """
    return en if is_en(lang) else orig


def sec(lang: str, key: str, **kw) -> str:
    """取章节标题。找不到就回落英文。"""
    t = SECT.get(_lk(lang), {}).get(key)
    if t is None:
        t = SECT["en"].get(key, key)
    return _fill(t, kw)


def body(lang: str, key: str, **kw) -> str:
    """取段落文本。找不到就回落英文。"""
    t = BODY.get(_lk(lang), {}).get(key)
    if t is None:
        t = BODY["en"].get(key, "")
    return _fill(t, kw)


def _lk(lang: str) -> str:
    return str(lang or DEFAULT).lower().replace("_", "-")[:2]


def _fill(t: str, kw: dict) -> str:
    for k, v in kw.items():
        t = t.replace("<<" + k + ">>", str(v))
    return t
