-- EconomyConfig (ModuleScript)
-- Сгенерировано economy/model.py. Не правьте числа руками: меняйте модель и запускайте заново.
-- Единицы: глубина в мм; сила, твёрдость, ветер и монеты — в «единицах силы». 1 сила = 1 монета.
-- Совместимо с Lua 5.1 / Luau.

local Config = {}

Config.Layers = {
	{ upTo = 0.15, hardnessMult = 1.0, name = "Трава" },
	{ upTo = 0.35, hardnessMult = 1.6, name = "Земля" },
	{ upTo = 0.55, hardnessMult = 2.5, name = "Глина" },
	{ upTo = 0.75, hardnessMult = 4.0, name = "Камни" },
	{ upTo = 0.9, hardnessMult = 6.0, name = "Корни" },
	{ upTo = 1.0, hardnessMult = 9.0, name = "Скала" },
}

Config.WindStages = {
	{ upTo = 0.3, name = "Штормовое предупреждение", beaufort = 8, slowdown = 0.15 },
	{ upTo = 0.7, name = "Шторм", beaufort = 10, slowdown = 0.3 },
	{ upTo = 1.0, name = "Ураган", beaufort = 11, slowdown = 0.45 },
}

Config.Gust = { every = 75, seconds = 6, extra = 1.0 }
Config.Peak = { seconds = 60, pull = 0.005, failLossFrac = 0.03, failReturnFrac = 0.97 }
Config.Rewards = { chestSecondsOfIncome = 10, giftEverySec = 600, giftSecondsOfIncome = 45 }
Config.PartyScalePerExtraPlayer = 0.75

Config.Levels = {
	{
		name = "Корова",
		stake = "Колышек",
		depthMm = 1000,
		hardness = 21,
		checkpoints = 22,
		peakWind = 370,
	},
	{
		name = "Воздушный шар",
		stake = "Кол",
		depthMm = 2000,
		hardness = 270,
		checkpoints = 29,
		peakWind = 6100,
	},
	{
		name = "Дом",
		stake = "Столб",
		depthMm = 4000,
		hardness = 2200,
		checkpoints = 36,
		peakWind = 77000,
	},
	{
		name = "Цирк-шапито",
		stake = "Бревно",
		depthMm = 6000,
		hardness = 25000,
		checkpoints = 48,
		peakWind = 950000,
	},
	{
		name = "Корабль",
		stake = "Свая",
		depthMm = 10000,
		hardness = 160000,
		checkpoints = 48,
		peakWind = 10000000,
	},
	{
		name = "Дирижабль",
		stake = "Стальная свая",
		depthMm = 15000,
		hardness = 1400000,
		checkpoints = 60,
		peakWind = 110000000,
	},
	{
		name = "Летающий остров",
		stake = "Колонна",
		depthMm = 25000,
		hardness = 8700000,
		checkpoints = 60,
		peakWind = 1100000000,
	},
	{
		name = "Луна",
		stake = "Гвоздь-небоскрёб",
		depthMm = 50000,
		hardness = 50000000,
		checkpoints = 72,
		peakWind = 1.1e+10,
	},
}

Config.Tools = {
	{ name = "Кулак", power = 1, price = 0, unlockLevel = 1 },
	{ name = "Тапок", power = 3, price = 60, unlockLevel = 1 },
	{ name = "Ботинок", power = 9, price = 310, unlockLevel = 1 },
	{ name = "Молоток", power = 27, price = 1600, unlockLevel = 2 },
	{ name = "Кувалда", power = 81, price = 8400, unlockLevel = 2 },
	{ name = "Отбойный молоток", power = 243, price = 44000, unlockLevel = 3 },
	{ name = "Пневмомолот", power = 729, price = 230000, unlockLevel = 3 },
	{ name = "Копёр", power = 2187, price = 1200000, unlockLevel = 4 },
	{ name = "Гидромолот", power = 6561, price = 6200000, unlockLevel = 4 },
	{ name = "Наковальня с неба", power = 19683, price = 32000000, unlockLevel = 5 },
	{ name = "Сейф с неба", power = 59049, price = 170000000, unlockLevel = 5 },
	{ name = "Бетонная плита", power = 177147, price = 870000000, unlockLevel = 6 },
	{ name = "Кит с неба", power = 531441, price = 4500000000, unlockLevel = 6 },
	{ name = "Метеорит", power = 1594323, price = 2.3e+10, unlockLevel = 7 },
	{ name = "Комета", power = 4782969, price = 1.2e+11, unlockLevel = 7 },
	{ name = "Нейтронная звезда", power = 14348907, price = 6.3e+11, unlockLevel = 8 },
	{ name = "Чёрная дыра", power = 43046721, price = 3.3e+12, unlockLevel = 8 },
}

Config.Helpers = {
	{ name = "Дятел", powerPerSec = 2, basePrice = 40, priceGrowth = 1.1, maxCount = 120, unlockLevel = 1 },
	{ name = "Сосед с молотком", powerPerSec = 18, basePrice = 440, priceGrowth = 1.1, maxCount = 120, unlockLevel = 2 },
	{ name = "Бригада строителей", powerPerSec = 160, basePrice = 4800, priceGrowth = 1.1, maxCount = 120, unlockLevel = 3 },
	{ name = "Робот-молотобоец", powerPerSec = 1500, basePrice = 53000, priceGrowth = 1.1, maxCount = 120, unlockLevel = 4 },
	{ name = "Баран-таран", powerPerSec = 13000, basePrice = 590000, priceGrowth = 1.1, maxCount = 120, unlockLevel = 5 },
	{ name = "Слон", powerPerSec = 120000, basePrice = 6400000, priceGrowth = 1.1, maxCount = 120, unlockLevel = 6 },
	{ name = "Великан", powerPerSec = 1100000, basePrice = 71000000, priceGrowth = 1.1, maxCount = 120, unlockLevel = 7 },
	{ name = "Робот-гигант", powerPerSec = 9600000, basePrice = 780000000, priceGrowth = 1.1, maxCount = 120, unlockLevel = 8 },
}

Config.Strength = { stepMult = 0.15, basePrice = 30, priceGrowth = 1.3, capPerLevel = 8 }

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

return Config
