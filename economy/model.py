#!/usr/bin/env python3
"""
Модель экономики «Прибей, пока не унесло!» (рабочее название).

Что делает скрипт:
  1. Симулирует игрока: он бьёт по колышку и покупает апгрейды.
  2. Подбирает твёрдость грунта и силу ветра на каждом уровне так,
     чтобы уровень длился целевое время (TARGET_MIN).
  3. Округляет найденные числа (как они пойдут в игру) и перепроверяет.
  4. Прогоняет те же числа на других типах игроков
     (медленный, быстрый, импульсивный покупатель, кооп 2 и 4 игрока).
  5. Сохраняет отчёт (economy/output/report.md)
     и конфиг для Roblox (economy/output/EconomyConfig.lua).

Запуск:  python3 economy/model.py
Зависимостей нет, нужен только Python 3.9+.

ВАЖНО: это модель, а не реальные игроки. Главное допущение — скорость
кликов (CPS). Реальные цифры надо проверять плейтестом.
"""

from __future__ import annotations

import copy
import math
import os
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# 1. ЦЕЛИ
# ---------------------------------------------------------------------------

# Сколько минут должен длиться каждый уровень у «обычного» игрока.
TARGET_MIN = [9, 12, 15, 20, 20, 25, 25, 30]

LEVELS = [
    # name — объект, который уносит ураган; stake — чем держим; depth_mm — на сколько вбить
    dict(name="Корова",          stake="Колышек",          depth_mm=1_000),
    dict(name="Воздушный шар",   stake="Кол",              depth_mm=2_000),
    dict(name="Дом",             stake="Столб",            depth_mm=4_000),
    dict(name="Цирк-шапито",     stake="Бревно",           depth_mm=6_000),
    dict(name="Корабль",         stake="Свая",             depth_mm=10_000),
    dict(name="Дирижабль",       stake="Стальная свая",    depth_mm=15_000),
    dict(name="Летающий остров", stake="Колонна",          depth_mm=25_000),
    dict(name="Луна",            stake="Гвоздь-небоскрёб", depth_mm=50_000),
]

# ---------------------------------------------------------------------------
# 2. ГРУНТ И ВЕТЕР
# ---------------------------------------------------------------------------

# Слои грунта: (до какой доли глубины, множитель твёрдости, название).
# Твёрдость слоя = базовая твёрдость уровня * множитель.
LAYERS = [
    (0.15, 1.0, "Трава"),
    (0.35, 1.6, "Земля"),
    (0.55, 2.5, "Глина"),
    (0.75, 4.0, "Камни"),
    (0.90, 6.0, "Корни"),
    (1.00, 9.0, "Скала"),
]

# Стадии ветра: (до какой доли глубины, название, баллы по шкале Бофорта, замедление).
# Замедление — на сколько процентов ветер гасит каждый удар. Оно считается
# от силы самого игрока, поэтому одинаково честно для медленных и быстрых.
WIND_STAGES = [
    (0.30, "Штормовое предупреждение", 8,  0.15),
    (0.70, "Шторм",                    10, 0.30),
    (1.00, "Ураган",                   11, 0.45),
]
# Порыв: на несколько секунд ветер становится сильнее игрока, и колышек
# ползёт обратно (но не выше последней вехи).
# Скорость колышка во время порыва = сила игрока * (1 - замедление - GUST_EXTRA).
# Пример: в «Урагане» 1 - 0.45 - 1.0 = -0.45 → колышек лезет назад
# со скоростью 45% от того, как игрок его вбивает. В «Предупреждении» -15%.
GUST_EVERY = 75           # порыв каждые N секунд
GUST_SEC = 6              # длительность порыва
GUST_EXTRA = 1.0

# Пик урагана (12 баллов) — единственная жёсткая проверка уровня:
# сила игрока в секунду против абсолютной силы урагана.
PEAK_K = 1.00             # сила пика = доля от силы эталонного игрока в момент, когда колышек дошёл до дна.
                          # САМАЯ ЧУВСТВИТЕЛЬНАЯ РУЧКА: при 1.15 обычный игрок играет 4 часа вместо 2.5.
PEAK_SEC = 60             # сколько секунд держать пик
# Если сила пати меньше силы урагана, колышек вылезает:
# скорость = (1 - сила пати / сила урагана) * PEAK_PULL * глубина в секунду.
# При 0.005 и провале на 3% выстоять минуту можно, только имея >= 90% силы урагана.
PEAK_PULL = 0.005
PEAK_FAIL_LOSS = 0.03     # если колышек вылез на 3% глубины — его вырвало
PEAK_FAIL_RETURN = 0.97   # после провала колышек остаётся на 97% глубины: добиваешь потерянное и снова

# ---------------------------------------------------------------------------
# 3. НАГРАДЫ
# ---------------------------------------------------------------------------

CHECKPOINT_EVERY_SEC = 25  # целевой интервал между вехами (кол-во вех = время уровня / 25 с)
CHEST_SECONDS = 10         # сундук на вехе = 10 секунд дохода игрока
GIFT_EVERY = 600           # подарок за время в игре каждые 10 минут
GIFT_SECONDS = 45          # подарок = 45 секунд дохода

# ---------------------------------------------------------------------------
# 4. МАГАЗИН
# ---------------------------------------------------------------------------
# Монеты: 1 единица силы удара = 1 монета (и от игрока, и от помощников).
# Монеты не зависят от твёрдости — твёрдый слой замедляет колышек, но не доход.

@dataclass
class Tool:
    name: str
    power: float      # сила одного удара
    price: float
    unlock: int       # с какого уровня (0 = корова) доступен


@dataclass
class Helper:
    name: str
    dps: float        # сила в секунду от одного помощника
    base_price: float
    unlock: int
    max_count: int = 120


TOOL_NAMES = [
    "Кулак",
    "Тапок", "Ботинок",
    "Молоток", "Кувалда",
    "Отбойный молоток", "Пневмомолот",
    "Копёр", "Гидромолот",
    "Наковальня с неба", "Сейф с неба",
    "Бетонная плита", "Кит с неба",
    "Метеорит", "Комета",
    "Нейтронная звезда", "Чёрная дыра",
]
HELPER_NAMES = [
    "Дятел", "Сосед с молотком", "Бригада строителей", "Робот-молотобоец",
    "Баран-таран", "Слон", "Великан", "Робот-гигант",
]

TOOL_POWER_RATIO = 3.0     # каждый следующий инструмент бьёт в N раз сильнее
TOOL_PRICE_BASE = 60
TOOL_PRICE_RATIO = 5.2     # и стоит в N раз дороже

HELPER_DPS_BASE = 2.0
HELPER_DPS_RATIO = 9.0     # следующий тип помощника в N раз сильнее
HELPER_PRICE_BASE = 40
HELPER_PRICE_RATIO = 11.0  # и в N раз дороже
HELPER_PRICE_GROWTH = 1.10 # каждый следующий помощник того же типа дороже на 10%
HELPER_MAX = 120

# «Сила» — общий множитель: умножает и удары, и помощников.
STR_STEP = 0.15            # +15% за уровень
STR_PRICE_BASE = 30
STR_PRICE_GROWTH = 1.30
STR_CAP_PER_LEVEL = 8      # на каждом уровне игры открывается ещё 8 уровней Силы


def nice(x: float) -> float:
    """Округляет цену до «красивого» числа (2 значащие цифры)."""
    if x < 100:
        return float(math.floor(x + 0.5))
    return sig(x, 2)


def sig(x: float, digits: int = 2) -> float:
    """Округляет до N значащих цифр (так числа пойдут в конфиг игры)."""
    if x == 0:
        return 0.0
    p = 10.0 ** (int(math.floor(math.log10(abs(x)) + 1e-9)) - digits + 1)
    return float(math.floor(x / p + 0.5) * p)


def build_shop():
    tools = [Tool(TOOL_NAMES[0], 1.0, 0.0, 0)]
    for k in range(1, len(TOOL_NAMES)):
        tools.append(Tool(
            name=TOOL_NAMES[k],
            power=float(round(TOOL_POWER_RATIO ** k)),
            price=nice(TOOL_PRICE_BASE * TOOL_PRICE_RATIO ** (k - 1)),
            unlock=(k - 1) // 2,   # по 2 инструмента на уровень
        ))
    helpers = []
    for t, name in enumerate(HELPER_NAMES):
        helpers.append(Helper(
            name=name,
            dps=sig(HELPER_DPS_BASE * HELPER_DPS_RATIO ** t),
            base_price=nice(HELPER_PRICE_BASE * HELPER_PRICE_RATIO ** t),
            unlock=t,
            max_count=HELPER_MAX,
        ))
    return tools, helpers


TOOLS, HELPERS = build_shop()


def str_mult(lvl: int) -> float:
    return 1.0 + STR_STEP * lvl


def str_price(lvl: int) -> float:
    return nice(STR_PRICE_BASE * STR_PRICE_GROWTH ** lvl)


def helper_price(t: int, owned: int) -> float:
    return nice(HELPERS[t].base_price * HELPER_PRICE_GROWTH ** owned)


# ---------------------------------------------------------------------------
# 5. ИГРОК
# ---------------------------------------------------------------------------

@dataclass
class Profile:
    name: str
    cps: float              # кликов в секунду
    buyer: str = "smart"    # smart — копит на самое выгодное; impulsive — тратит сразу
    party: int = 1          # размер пати


@dataclass
class State:
    coins: float = 0.0
    tool: int = 0
    strength: int = 0
    helpers: list = field(default_factory=lambda: [0] * len(HELPERS))
    playtime: float = 0.0
    next_gift: float = GIFT_EVERY

    def hit_power(self) -> float:
        return TOOLS[self.tool].power * str_mult(self.strength)

    def helper_dps(self) -> float:
        return sum(HELPERS[t].dps * n for t, n in enumerate(self.helpers)) * str_mult(self.strength)

    def dps(self, cps: float) -> float:
        return self.hit_power() * cps + self.helper_dps()


def party_scale(n: int) -> float:
    """Во сколько раз твёрже грунт и сильнее ветер для пати из n игроков."""
    return 1.0 + 0.75 * (n - 1)


def shop_options(s: State, level: int, cps: float):
    opts = []
    mult = str_mult(s.strength)
    nt = s.tool + 1
    if nt < len(TOOLS) and TOOLS[nt].unlock <= level:
        gain = (TOOLS[nt].power - TOOLS[s.tool].power) * mult * cps
        opts.append(("tool", nt, TOOLS[nt].price, gain))
    if s.strength < STR_CAP_PER_LEVEL * (level + 1):
        base = TOOLS[s.tool].power * cps + sum(HELPERS[t].dps * n for t, n in enumerate(s.helpers))
        opts.append(("str", None, str_price(s.strength), base * STR_STEP))
    for t, h in enumerate(HELPERS):
        if h.unlock <= level and s.helpers[t] < h.max_count:
            opts.append(("helper", t, helper_price(t, s.helpers[t]), h.dps * mult))
    return opts


def apply_buy(s: State, opt) -> None:
    kind, idx, price, _ = opt
    s.coins -= price
    if kind == "tool":
        s.tool = idx
    elif kind == "str":
        s.strength += 1
    else:
        s.helpers[idx] += 1


def shop(s: State, level: int, prof: Profile) -> list:
    bought = []
    while True:
        opts = shop_options(s, level, prof.cps)
        if not opts:
            break
        if prof.buyer == "smart":
            best = max(opts, key=lambda o: o[3] / o[2])
            if best[2] > s.coins:
                break
        else:
            affordable = [o for o in opts if o[2] <= s.coins]
            if not affordable:
                break
            best = max(affordable, key=lambda o: o[3] / o[2])
        apply_buy(s, best)
        bought.append(best)
    return bought


# ---------------------------------------------------------------------------
# 6. УРОВЕНЬ
# ---------------------------------------------------------------------------

DT = 0.5


def layer_mult(frac: float) -> float:
    for upto, mult, _ in LAYERS:
        if frac < upto:
            return mult
    return LAYERS[-1][1]


def wind_stage(frac: float) -> int:
    for i, (upto, *_rest) in enumerate(WIND_STAGES):
        if frac < upto:
            return i
    return len(WIND_STAGES) - 1


def drive_rate(lv: dict, depth: float, team_dps: float, party: int, gust: bool) -> float:
    """Скорость колышка, мм/с, вне пика. Отрицательная во время порыва."""
    frac = depth / lv["depth_mm"]
    k = 1.0 - WIND_STAGES[wind_stage(frac)][3] - (GUST_EXTRA if gust else 0.0)
    h = lv["hardness"] * layer_mult(frac) * party_scale(party)
    return team_dps * k / h


def peak_rate(lv: dict, team_dps: float, party: int) -> float:
    """Скорость колышка, мм/с, во время пика урагана: 0 или отрицательная."""
    wind = lv["peak"] * party_scale(party)
    if team_dps >= wind:
        return 0.0
    return -(1.0 - team_dps / wind) * PEAK_PULL * lv["depth_mm"]


def run_level(s: State, level: int, lv: dict, prof: Profile, cap_sec: float = 6 * 3600):
    """Прогоняет один уровень. Меняет состояние игрока s. Возвращает (время, метрики)."""
    D = lv["depth_mm"]
    n = prof.party
    cp_count = lv["checkpoints"]
    cp = D / cp_count

    t = 0.0
    depth = 0.0
    floor_cp = 0
    rewarded_cp = 0
    phase = "drive"
    peak_t = 0.0
    stage_seen = -1

    m = dict(purchases=0, fails=0, peak_wait=0.0, max_gap=0.0, events=0, gaps=[],
             entry_dps=[None] * len(WIND_STAGES), bottom_dps=None, reached_bottom_at=None,
             start_dps=s.dps(prof.cps), end_dps=None, tools_bought=[], last_buy=0.0)
    last_event = 0.0

    def event():
        nonlocal last_event
        if t > last_event:
            m["gaps"].append(t - last_event)
        m["max_gap"] = max(m["max_gap"], t - last_event)
        m["events"] += 1
        last_event = t

    while t < cap_sec:
        bought = shop(s, level, prof)
        if bought:
            m["last_buy"] = t
            m["purchases"] += len(bought)
            m["tools_bought"] += [TOOLS[o[1]].name for o in bought if o[0] == "tool"]
            event()

        my_dps = s.dps(prof.cps)
        team_dps = my_dps * n
        s.coins += my_dps * DT

        s.playtime += DT
        if s.playtime >= s.next_gift:
            s.coins += GIFT_SECONDS * my_dps
            s.next_gift += GIFT_EVERY
            event()

        if phase == "drive":
            frac = depth / D
            st = wind_stage(frac)
            if st > stage_seen:
                for k in range(stage_seen + 1, st + 1):
                    m["entry_dps"][k] = team_dps
                stage_seen = st
            gust = (t % GUST_EVERY) < GUST_SEC and t >= GUST_EVERY
            depth += drive_rate(lv, depth, team_dps, n, gust) * DT
            depth = max(depth, floor_cp * cp)
            while rewarded_cp < cp_count and depth >= (rewarded_cp + 1) * cp - 1e-9:
                rewarded_cp += 1
                s.coins += CHEST_SECONDS * my_dps
                event()
            floor_cp = max(floor_cp, min(int(depth / cp + 1e-9), cp_count))
            if depth >= D:
                depth = D
                phase = "peak"
                peak_t = 0.0
                if m["bottom_dps"] is None:
                    m["bottom_dps"] = team_dps
                    m["reached_bottom_at"] = t
        else:
            depth += peak_rate(lv, team_dps, n) * DT
            peak_t += DT
            if D - depth > PEAK_FAIL_LOSS * D:
                m["fails"] += 1
                phase = "drive"
                depth = PEAK_FAIL_RETURN * D
                floor_cp = int(depth / cp + 1e-9)
            elif peak_t >= PEAK_SEC:
                t += DT
                break
        t += DT

    m["end_dps"] = s.dps(prof.cps)
    m["max_gap"] = max(m["max_gap"], t - last_event)
    m["gaps"].append(t - last_event)
    m["finished"] = t < cap_sec
    if m["reached_bottom_at"] is not None:
        m["peak_wait"] = t - m["reached_bottom_at"]
    m["click_share"] = s.hit_power() * prof.cps / max(1e-9, s.dps(prof.cps))
    return t, m


# ---------------------------------------------------------------------------
# 7. ПОДБОР ЧИСЕЛ
# ---------------------------------------------------------------------------

REF = Profile("Обычный", cps=4.0)


def time_for(state0: State, level: int, lv: dict, prof: Profile) -> float:
    s = copy.deepcopy(state0)
    t, _ = run_level(s, level, lv, prof)
    return t


def bisect_hardness(state0: State, level: int, lv: dict, target: float) -> float:
    lo, hi = 1e-6, 1e15
    for _ in range(60):
        mid = math.sqrt(lo * hi)
        lv["hardness"] = mid
        if time_for(state0, level, lv, REF) < target:
            lo = mid
        else:
            hi = mid
        if hi / lo < 1.002:
            break
    return math.sqrt(lo * hi)


def tune():
    """Подбирает твёрдость и ветер для каждого уровня по «обычному» игроку."""
    state = State()
    tuned = []
    for L, base in enumerate(LEVELS):
        target = TARGET_MIN[L] * 60
        lv = dict(base)
        lv["checkpoints"] = max(10, round(target / CHECKPOINT_EVERY_SEC))
        # Шаг 1: твёрдость подбираем без пика (пик = 0, эталон его всегда держит).
        # С пиком подбор ломается: срывы делают время немонотонным по твёрдости.
        lv["peak"] = 0.0
        lv["hardness"] = sig(bisect_hardness(state, L, lv, target), 2)
        # Шаг 2: сила пика = PEAK_K * сила эталона в момент, когда колышек дошёл до дна.
        s = copy.deepcopy(state)
        _, m = run_level(s, L, lv, REF)
        lv["peak"] = sig(PEAK_K * m["bottom_dps"], 2)

        t, _ = run_level(state, L, lv, REF)   # двигаем игрока дальше
        tuned.append(lv)
    return tuned


def play_game(levels: list, prof: Profile):
    state = State()
    rows = []
    for L, lv in enumerate(levels):
        t, m = run_level(state, L, lv, prof)
        rows.append((t, m))
        if not m["finished"]:
            break
    return rows, state


# ---------------------------------------------------------------------------
# 8. ОТЧЁТ И ЭКСПОРТ
# ---------------------------------------------------------------------------

def fmt_num(x: float) -> str:
    """1234 → 1.2K, как обычно показывают в Roblox-симуляторах."""
    for unit, div in (("T", 1e12), ("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if abs(x) >= div:
            return f"{x / div:.1f}{unit}"
    return f"{x:.0f}" if abs(x) >= 10 else f"{x:.1f}"


def fmt_time(sec: float) -> str:
    sec = int(round(sec))
    h, rem = divmod(sec, 3600)
    mnt, s = divmod(rem, 60)
    return f"{h}:{mnt:02d}:{s:02d}" if h else f"{mnt}:{s:02d}"


PROFILES = [
    REF,
    Profile("Медленный", cps=2.5),
    Profile("Быстрый", cps=7.0),
    Profile("Импульсивный", cps=4.0, buyer="impulsive"),
    Profile("Кооп ×2", cps=4.0, party=2),
    Profile("Кооп ×4", cps=4.0, party=4),
]


def report(levels: list) -> str:
    out = []
    out.append("# Модель экономики — отчёт\n")
    out.append("> Сгенерировано `economy/model.py`. **Это модель, а не данные реальных игроков.** "
               "Главное допущение: «обычный» игрок кликает 4 раза в секунду, всё время в игре и покупает "
               "самое выгодное. Кат-сцены, меню и походы по карте во время не входят.\n")

    # --- эталонный прогон
    rows, _ = play_game(levels, REF)
    out.append("## Эталонный игрок (4 клика/с, копит на самое выгодное)\n")
    out.append("| # | Уровень | Цель | Вышло | С начала игры | Покупок | 90% пауз короче | Самая длинная пауза | "
               "Доля помощников в силе | Сила/с: начало → конец | Пик урагана |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|")
    total = 0.0
    for L, (t, m) in enumerate(rows):
        total += t
        g = sorted(m["gaps"])
        p90 = g[int(0.9 * (len(g) - 1))] if g else 0.0
        peak = "с 1-й попытки" if m["fails"] == 0 else f"срывов: {m['fails']}"
        out.append(
            f"| {L + 1} | {levels[L]['name']} | {TARGET_MIN[L]}:00 | {fmt_time(t)} | {fmt_time(total)} | "
            f"{m['purchases']} | {fmt_time(p90)} | {fmt_time(m['max_gap'])} | {100 * (1 - m['click_share']):.0f}% | "
            f"{fmt_num(m['start_dps'])} → {fmt_num(m['end_dps'])} | {peak} |")
    out.append("")
    out.append("**Пауза** — отрезок, когда игрок ничего не купил, не открыл веху и не получил подарок. "
               "Самая длинная пауза обычно и есть минута пика урагана — это кульминация, а не пустое время.\n")

    # --- профили
    out.append("## Разные игроки на тех же числах\n")
    out.append("| Игрок | " + " | ".join(f"Ур. {i + 1}" for i in range(len(levels))) + " | Вся игра |")
    out.append("|" + "---|" * (len(levels) + 2))
    for prof in PROFILES:
        rows, _ = play_game(levels, prof)
        cells = []
        tot = 0.0
        fails = 0
        for (t, m) in rows:
            tot += t
            fails += m["fails"]
            cells.append(fmt_time(t) + ("" if m["finished"] else " ⛔"))
        cells += ["—"] * (len(levels) - len(rows))
        note = f" (срывов на пике: {fails})" if fails else ""
        out.append(f"| {prof.name}, {prof.cps:g} к/с{', пати ' + str(prof.party) if prof.party > 1 else ''} | "
                   + " | ".join(cells) + f" | **{fmt_time(tot)}**{note} |")
    out.append("")
    out.append("- **Медленный / Быстрый** — тот же умный покупатель, но кликает 2,5 или 7 раз в секунду.\n"
               "- **Импульсивный** — тратит монеты сразу на лучшее из того, что уже по карману, никогда не копит.\n"
               "- **Кооп** — все игроки в пати одинаковые, бьют один колышек. Грунт и пик урагана для пати "
               "сильнее: × (1 + 0.75 × (игроков − 1)).\n")

    # --- уровни
    out.append("## Числа уровней (идут в конфиг)\n")
    out.append("| # | Объект | Чем держим | Глубина | Твёрдость | Вех | Сила пика урагана |")
    out.append("|---|---|---|---|---|---|---|")
    for L, lv in enumerate(levels):
        out.append(f"| {L + 1} | {lv['name']} | {lv['stake']} | {lv['depth_mm'] / 1000:g} м | "
                   f"{fmt_num(lv['hardness'])} | {lv['checkpoints']} | {fmt_num(lv['peak'])} |")
    out.append("")
    out.append("**Твёрдость** — сколько силы нужно, чтобы вбить колышек на 1 мм в верхнем слое. Глубже умножается:\n")
    out.append("| Слой | До глубины | Твёрдость × |")
    out.append("|---|---|---|")
    prev = 0.0
    for upto, mult, name in LAYERS:
        out.append(f"| {name} | {prev * 100:.0f}–{upto * 100:.0f}% | ×{mult:g} |")
        prev = upto
    out.append("")
    out.append("## Ветер\n")
    out.append("| Стадия | До глубины | Баллы (Бофорт) | Гасит удар на |")
    out.append("|---|---|---|---|")
    prev = 0.0
    for upto, name, beaufort, slow in WIND_STAGES:
        out.append(f"| {name} | {prev * 100:.0f}–{upto * 100:.0f}% | {beaufort} | {slow * 100:.0f}% |")
        prev = upto
    out.append(f"| Пик урагана | на дне | 12 | абсолютная сила из таблицы уровней, держать {PEAK_SEC} с |")
    out.append("")
    out.append(f"**Порыв:** каждые {GUST_EVERY} с на {GUST_SEC} с. Колышек ползёт назад со скоростью "
               f"(замедление стадии) от силы игрока, но не выше последней вехи.\n")
    need = 1 - PEAK_FAIL_LOSS / (PEAK_PULL * PEAK_SEC)
    out.append(f"**Пик:** если сила пати меньше силы урагана, колышек вылезает со скоростью "
               f"(1 − сила пати / сила урагана) × {PEAK_PULL * 100:g}% глубины в секунду. Вылез на "
               f"{PEAK_FAIL_LOSS * 100:.0f}% — вырвало: откат на {PEAK_FAIL_RETURN * 100:.0f}% глубины, добиваешь "
               f"и пробуешь снова. Итог для игрока: чтобы выстоять {PEAK_SEC} с, нужно хотя бы {need * 100:.0f}% "
               f"силы урагана.\n")

    # --- магазин
    out.append("## Инструменты\n")
    out.append("| # | Инструмент | Сила удара | Цена | Открывается на уровне |")
    out.append("|---|---|---|---|---|")
    for k, tl in enumerate(TOOLS):
        out.append(f"| {k} | {tl.name} | {fmt_num(tl.power)} | {fmt_num(tl.price) if tl.price else 'с начала'} | "
                   f"{tl.unlock + 1} |")
    out.append("")
    out.append("## Помощники (автоматизация)\n")
    out.append("| Помощник | Сила/с | Цена первого | Каждый следующий дороже на | Максимум | Открывается на уровне |")
    out.append("|---|---|---|---|---|---|")
    for h in HELPERS:
        out.append(f"| {h.name} | {fmt_num(h.dps)} | {fmt_num(h.base_price)} | {(HELPER_PRICE_GROWTH - 1) * 100:.0f}% | "
                   f"{h.max_count} | {h.unlock + 1} |")
    out.append("")
    out.append(f"## Сила\n\n+{STR_STEP * 100:.0f}% ко всей силе (удары и помощники) за уровень. "
               f"Цена: {STR_PRICE_BASE} × {STR_PRICE_GROWTH}^уровень. "
               f"Потолок: {STR_CAP_PER_LEVEL} уровней Силы на каждый открытый уровень игры.\n")
    out.append("## Награды\n")
    out.append(f"- Веха: сундук = {CHEST_SECONDS} с дохода игрока. Вехи равномерно по глубине, "
               f"примерно каждые {CHECKPOINT_EVERY_SEC} с.\n"
               f"- Подарок за время в игре: каждые {GIFT_EVERY // 60} мин = {GIFT_SECONDS} с дохода.\n"
               "- Монеты: 1 единица силы = 1 монета, и от ударов, и от помощников. "
               "Твёрдый слой замедляет колышек, но не доход.\n")
    out.append("## Чего модель не знает\n")
    out.append("- Сколько реально кликают игроки в Roblox. 4 клика/с — допущение.\n"
               "- Ритм-комбо, ивенты кроме порывов (корова, молния, «попал по пальцу»), донат и бусты.\n"
               "- Что игрок отвлекается, уходит в AFK, выходит и возвращается.\n"
               "- Интерес: модель считает минуты, но не может сказать, весело ли это. Это только плейтест.\n")
    return "\n".join(out)


def lua_number(x: float) -> str:
    return f"{x:.10g}"


LUA_FUNCTIONS = r"""
-- ---------------------------------------------------------------------------
-- Формулы. Те же, что в economy/model.py. Проверены тестом economy/test_lua_parity.py.
-- ---------------------------------------------------------------------------

-- Округление до N значащих цифр (как в модели)
function Config.roundSig(x, digits)
	if x == 0 then
		return 0
	end
	local e = math.floor(math.log10(math.abs(x)) + 1e-9)
	local p = 10 ^ (e - digits + 1)
	return math.floor(x / p + 0.5) * p
end

-- «Красивая» цена: до 100 — целое, дальше 2 значащие цифры
function Config.nicePrice(x)
	if x < 100 then
		return math.floor(x + 0.5)
	end
	return Config.roundSig(x, 2)
end

function Config.strengthMult(strengthLevel)
	return 1 + Config.Strength.stepMult * strengthLevel
end

function Config.strengthPrice(strengthLevel)
	return Config.nicePrice(Config.Strength.basePrice * Config.Strength.priceGrowth ^ strengthLevel)
end

-- Сколько уровней Силы можно купить, когда открыт уровень игры levelIndex (1..8)
function Config.strengthCap(levelIndex)
	return Config.Strength.capPerLevel * levelIndex
end

-- helperIndex 1..8, owned — сколько таких помощников уже куплено
function Config.helperPrice(helperIndex, owned)
	local h = Config.Helpers[helperIndex]
	return Config.nicePrice(h.basePrice * h.priceGrowth ^ owned)
end

-- Сила игрока в секунду (столько же он получает монет в секунду)
-- toolIndex 1..17, helperCounts — массив из 8 чисел
function Config.playerPowerPerSec(toolIndex, strengthLevel, helperCounts, clicksPerSec)
	local helpers = 0
	for i, n in ipairs(helperCounts) do
		helpers = helpers + Config.Helpers[i].powerPerSec * n
	end
	local tool = Config.Tools[toolIndex].power
	return (tool * clicksPerSec + helpers) * Config.strengthMult(strengthLevel)
end

function Config.partyScale(partySize)
	return 1 + Config.PartyScalePerExtraPlayer * (partySize - 1)
end

-- frac = глубина / полная глубина (0..1)
function Config.layerAt(frac)
	for _, layer in ipairs(Config.Layers) do
		if frac < layer.upTo then
			return layer
		end
	end
	return Config.Layers[#Config.Layers]
end

function Config.windStageAt(frac)
	for _, stage in ipairs(Config.WindStages) do
		if frac < stage.upTo then
			return stage
		end
	end
	return Config.WindStages[#Config.WindStages]
end

-- Скорость колышка (мм в секунду) вне пика урагана.
-- teamPowerPerSec — сумма силы всех игроков пати. Отрицательно во время порыва.
function Config.driveRateMmPerSec(levelIndex, depthMm, teamPowerPerSec, partySize, isGust)
	local level = Config.Levels[levelIndex]
	local frac = depthMm / level.depthMm
	local stage = Config.windStageAt(frac)
	local k = 1 - stage.slowdown
	if isGust then
		k = k - Config.Gust.extra
	end
	local hardness = level.hardness * Config.layerAt(frac).hardnessMult * Config.partyScale(partySize)
	return teamPowerPerSec * k / hardness
end

-- Скорость колышка во время пика урагана: 0, если пати не слабее урагана, иначе отрицательная.
function Config.peakRateMmPerSec(levelIndex, teamPowerPerSec, partySize)
	local level = Config.Levels[levelIndex]
	local wind = level.peakWind * Config.partyScale(partySize)
	if teamPowerPerSec >= wind then
		return 0
	end
	return -(1 - teamPowerPerSec / wind) * Config.Peak.pull * level.depthMm
end

-- Глубина вехи номер i (1..checkpoints)
function Config.checkpointDepthMm(levelIndex, i)
	local level = Config.Levels[levelIndex]
	return level.depthMm * i / level.checkpoints
end
"""


def export_lua(levels: list) -> str:
    L = []
    L.append("-- EconomyConfig (ModuleScript)")
    L.append("-- Сгенерировано economy/model.py. Не правьте числа руками: меняйте модель и запускайте заново.")
    L.append("-- Единицы: глубина в мм; сила, твёрдость, ветер и монеты — в «единицах силы». 1 сила = 1 монета.")
    L.append("-- Совместимо с Lua 5.1 / Luau.")
    L.append("")
    L.append("local Config = {}")
    L.append("")
    L.append("Config.Layers = {")
    for upto, mult, name in LAYERS:
        L.append(f'\t{{ upTo = {upto}, hardnessMult = {mult}, name = "{name}" }},')
    L.append("}")
    L.append("")
    L.append("Config.WindStages = {")
    for upto, name, beaufort, slow in WIND_STAGES:
        L.append(f'\t{{ upTo = {upto}, name = "{name}", beaufort = {beaufort}, slowdown = {slow} }},')
    L.append("}")
    L.append("")
    L.append(f"Config.Gust = {{ every = {GUST_EVERY}, seconds = {GUST_SEC}, extra = {GUST_EXTRA} }}")
    L.append(f"Config.Peak = {{ seconds = {PEAK_SEC}, pull = {PEAK_PULL}, failLossFrac = {PEAK_FAIL_LOSS}, "
             f"failReturnFrac = {PEAK_FAIL_RETURN} }}")
    L.append(f"Config.Rewards = {{ chestSecondsOfIncome = {CHEST_SECONDS}, giftEverySec = {GIFT_EVERY}, "
             f"giftSecondsOfIncome = {GIFT_SECONDS} }}")
    L.append("Config.PartyScalePerExtraPlayer = 0.75")
    L.append("")
    L.append("Config.Levels = {")
    for lv in levels:
        L.append("\t{")
        L.append(f'\t\tname = "{lv["name"]}",')
        L.append(f'\t\tstake = "{lv["stake"]}",')
        L.append(f'\t\tdepthMm = {lv["depth_mm"]},')
        L.append(f'\t\thardness = {lua_number(lv["hardness"])},')
        L.append(f'\t\tcheckpoints = {lv["checkpoints"]},')
        L.append(f'\t\tpeakWind = {lua_number(lv["peak"])},')
        L.append("\t},")
    L.append("}")
    L.append("")
    L.append("Config.Tools = {")
    for tl in TOOLS:
        L.append(f'\t{{ name = "{tl.name}", power = {lua_number(tl.power)}, price = {lua_number(tl.price)}, '
                 f'unlockLevel = {tl.unlock + 1} }},')
    L.append("}")
    L.append("")
    L.append("Config.Helpers = {")
    for h in HELPERS:
        L.append(f'\t{{ name = "{h.name}", powerPerSec = {lua_number(h.dps)}, basePrice = {lua_number(h.base_price)}, '
                 f'priceGrowth = {HELPER_PRICE_GROWTH}, maxCount = {h.max_count}, unlockLevel = {h.unlock + 1} }},')
    L.append("}")
    L.append("")
    L.append(f"Config.Strength = {{ stepMult = {STR_STEP}, basePrice = {STR_PRICE_BASE}, "
             f"priceGrowth = {STR_PRICE_GROWTH}, capPerLevel = {STR_CAP_PER_LEVEL} }}")
    L.append(LUA_FUNCTIONS)
    L.append("return Config")
    L.append("")
    return "\n".join(L)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(here, "output")
    os.makedirs(out_dir, exist_ok=True)
    print("Подбираю числа уровней...")
    levels = tune()
    text = report(levels)
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write(text)
    with open(os.path.join(out_dir, "EconomyConfig.lua"), "w", encoding="utf-8") as f:
        f.write(export_lua(levels))
    print(text)


if __name__ == "__main__":
    main()
