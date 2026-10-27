-- This information tells other players more about the mod
name = "Moon Shadow Assassin"
description = "Wili come from a female assassin Alliance.\nShe come here because she was framed by friends."
author = "Frankie Zhang"
version = "1.2.3"

-- This is the URL name of the mod's thread on the forum; the part after the ? and before the first & in the url
forumthread = ""

-- This lets other players know if your mod is out of date, update it to match the current version in the game
api_version = 10

-- Compatible with Don't Starve Together
dst_compatible = true

-- Not compatible with Don't Starve
dont_starve_compatible = false
reign_of_giants_compatible = false
shipwrecked_compatible = false

-- Character mods are required by all clients
all_clients_require_mod = true

icon_atlas = "modicon.xml"
icon = "modicon.tex"

-- The mod's tags displayed on the server list
server_filter_tags = {"character"}

local invincibility_rate_options = {}
for percent = 0, 100 do
    invincibility_rate_options[#invincibility_rate_options + 1] = {
        description = percent == 0 and "关闭" or (percent == 13 and "13%（默认）" or percent .. "%"),
        hover = "受到攻击时有" .. percent .. "%概率获得13秒无敌",
        data = percent / 100
    }
end

configuration_options = {{
    name = "oneshot_rate", -- 配置项名换，在modmain.lua里获取配置值时要用到
    hover = "攻击时秒杀的概率", -- 鼠标移到配置项上时所显示的信息
    options = {{ -- 配置项目可选项
        description = "默认", -- 可选项上显示的内容
        hover = "默认为4%", -- 鼠标移动到可选项上显示的信息
        data = 0.04 -- 可选项选中时的值，在modmain.lua里获取到的值就是这个数据，类型可以为整形，布尔，浮点，字符串
    }, {
        description = "小",
        hover = "1%",
        data = 0.01
    }, {
        description = "非常小",
        hover = "0.1%",
        data = 0.001
    }, {
        description = "无",
        hover = "0",
        data = -1
    }},
    default = 0.04 -- 默认值，与可选项里的值匹配作为默认值
}, {
    name = "gem_gen_rate", -- 配置项名换，在modmain.lua里获取配置值时要用到
    hover = "宝石生成的概率", -- 鼠标移到配置项上时所显示的信息
    options = {{ -- 配置项目可选项
        description = "默认", -- 可选项上显示的内容
        hover = "默认为4%", -- 鼠标移动到可选项上显示的信息
        data = 0.04 -- 可选项选中时的值，在modmain.lua里获取到的值就是这个数据，类型可以为整形，布尔，浮点，字符串
    }, {
        description = "小",
        hover = "1%",
        data = 0.01
    }, {
        description = "非常小",
        hover = "0.1%",
        data = 0.001
    }, {
        description = "无",
        hover = "0",
        data = -1
    }},
    default = 0.04 -- 默认值，与可选项里的值匹配作为默认值
}, {
    name = "invincibility_rate",
    label = "无敌触发概率",
    hover = "受到攻击时获得13秒无敌的概率，0%为关闭",
    options = invincibility_rate_options,
    default = 0.13
}}
