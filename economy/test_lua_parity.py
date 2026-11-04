#!/usr/bin/env python3
"""
Проверка: формулы в output/EconomyConfig.lua считают то же самое, что модель на Python.

Нужна библиотека lupa (Lua внутри Python):  pip install lupa
Запуск (после python3 economy/model.py):    python3 economy/test_lua_parity.py

Lua 5.1 — ближайший к Luau (язык Roblox) вариант, поэтому проверяем на нём.
"""

import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import model as M  # noqa: E402

try:
    from lupa.lua51 import LuaRuntime
except ImportError:
    print("Нет библиотеки lupa. Установите: pip install lupa")
    sys.exit(2)


def close(a: float, b: float, rel: float = 1e-9) -> bool:
    return a == b or abs(a - b) <= rel * max(abs(a), abs(b), 1e-300)


def main() -> int:
    path = os.path.join(HERE, "output", "EconomyConfig.lua")
    with open(path, encoding="utf-8") as f:
        code = f.read()
    lua = LuaRuntime(unpack_returned_tuples=True)
    cfg = lua.execute(code)

    # Уровни берём из Lua-конфига — проверяем формулы, а не подбор.
    levels = []
    for i in range(1, len(cfg.Levels) + 1):
        lv = cfg.Levels[i]
        levels.append(dict(depth_mm=lv.depthMm, hardness=lv.hardness, peak=lv.peakWind, checkpoints=lv.checkpoints))

    rng = random.Random(42)
    fails = []
    checks = 0

    def check(name, py, lu):
        nonlocal checks
        checks += 1
        if not close(py, lu):
            fails.append(f"{name}: python={py!r} lua={lu!r}")

    # Константы магазина совпадают
    for k, tl in enumerate(M.TOOLS):
        check(f"tool{k}.power", tl.power, cfg.Tools[k + 1].power)
        check(f"tool{k}.price", tl.price, cfg.Tools[k + 1].price)
    for t, h in enumerate(M.HELPERS):
        check(f"helper{t}.dps", h.dps, cfg.Helpers[t + 1].powerPerSec)
        check(f"helper{t}.base", h.base_price, cfg.Helpers[t + 1].basePrice)

    for _ in range(3000):
        x = 10 ** rng.uniform(-1, 13)
        check(f"roundSig({x})", M.sig(x, 2), cfg.roundSig(x, 2))
        check(f"nicePrice({x})", M.nice(x), cfg.nicePrice(x))

        lvl = rng.randint(0, 200)
        check(f"strengthPrice({lvl})", M.str_price(lvl), cfg.strengthPrice(lvl))
        check(f"strengthMult({lvl})", M.str_mult(lvl), cfg.strengthMult(lvl))

        t = rng.randrange(len(M.HELPERS))
        owned = rng.randint(0, 119)
        check(f"helperPrice({t},{owned})", M.helper_price(t, owned), cfg.helperPrice(t + 1, owned))

        s = M.State()
        s.tool = rng.randrange(len(M.TOOLS))
        s.strength = rng.randint(0, 64)
        s.helpers = [rng.randint(0, 120) for _ in M.HELPERS]
        cps = rng.choice([0.0, 2.5, 4.0, 7.0])
        lua_helpers = lua.table_from(s.helpers)
        check("playerPowerPerSec", s.dps(cps), cfg.playerPowerPerSec(s.tool + 1, s.strength, lua_helpers, cps))

        L = rng.randrange(len(levels))
        lv = levels[L]
        depth = rng.uniform(0, lv["depth_mm"])
        dps = 10 ** rng.uniform(0, 10)
        party = rng.randint(1, 4)
        gust = rng.random() < 0.3
        check(f"driveRate(L{L + 1})", M.drive_rate(lv, depth, dps, party, gust),
              cfg.driveRateMmPerSec(L + 1, depth, dps, party, gust))
        check(f"peakRate(L{L + 1})", M.peak_rate(lv, dps, party), cfg.peakRateMmPerSec(L + 1, dps, party))

        frac = rng.random()
        check("layerAt", M.layer_mult(frac), cfg.layerAt(frac).hardnessMult)
        check("windStageAt", M.WIND_STAGES[M.wind_stage(frac)][3], cfg.windStageAt(frac).slowdown)

    # Граничные значения слоёв и стадий
    for frac in [0.0, 0.15, 0.3, 0.35, 0.55, 0.7, 0.75, 0.9, 0.999999, 1.0]:
        check(f"layerAt({frac})", M.layer_mult(frac), cfg.layerAt(frac).hardnessMult)
        check(f"windStageAt({frac})", M.WIND_STAGES[M.wind_stage(frac)][3], cfg.windStageAt(frac).slowdown)

    if fails:
        print(f"РАСХОЖДЕНИЙ: {len(fails)} из {checks}")
        for f in fails[:20]:
            print("  ", f)
        return 1
    print(f"OK: {checks} проверок, Lua и Python считают одинаково.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
