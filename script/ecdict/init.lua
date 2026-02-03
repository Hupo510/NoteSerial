print('ecdict init')

ecdict = python.import("ecdict")

local function ecdict_translate(content)
    return ecdict.ecdict_translate(content)
end

-- 初始化转换插件脚本 --
local function convert_init()
    convert.register(ecdict_translate, "本地英汉词典翻译")
end

convert_init()
