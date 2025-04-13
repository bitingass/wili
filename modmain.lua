Assets = {Asset("IMAGE", "images/saveslot_portraits/wili.tex"), Asset("ATLAS", "images/saveslot_portraits/wili.xml"),

          Asset("IMAGE", "images/selectscreen_portraits/wili.tex"),
          Asset("ATLAS", "images/selectscreen_portraits/wili.xml"),

          Asset("IMAGE", "images/selectscreen_portraits/wili_silho.tex"),
          Asset("ATLAS", "images/selectscreen_portraits/wili_silho.xml"), Asset("IMAGE", "bigportraits/wili.tex"),
          Asset("ATLAS", "bigportraits/wili.xml"), Asset("IMAGE", "images/map_icons/wili.tex"),
          Asset("ATLAS", "images/map_icons/wili.xml"), Asset("IMAGE", "images/avatars/avatar_wili.tex"),
          Asset("ATLAS", "images/avatars/avatar_wili.xml"), Asset("IMAGE", "images/avatars/avatar_ghost_wili.tex"),
          Asset("ATLAS", "images/avatars/avatar_ghost_wili.xml"),

          Asset("IMAGE", "images/avatars/self_inspect_wili.tex"),
          Asset("ATLAS", "images/avatars/self_inspect_wili.xml"), Asset("IMAGE", "images/inventoryimages/scimitar.tex"),
          Asset("ATLAS", "images/inventoryimages/scimitar.xml") -- Asset( "IMAGE", "images/names_wili.tex" ),
-- Asset( "ATLAS", "images/names_wili.xml" ),
-- Asset( "IMAGE", "images/names_gold_wili.tex" ),
-- Asset( "ATLAS", "images/names_gold_wili.xml" ),
}

TUNING.CHARACTER_PREFAB_MODCONFIGDATA = {}
TUNING.CHARACTER_PREFAB_MODCONFIGDATA["oneshotRate"] = GetModConfigData("oneshot_rate")
TUNING.CHARACTER_PREFAB_MODCONFIGDATA["gemGenRate"] = GetModConfigData("gem_gen_rate")

AddMinimapAtlas("images/map_icons/wili.xml")


-- prevent making friends
AddPrefabPostInit("pigman", function(inst)
    if GLOBAL.TheWorld.ismastersim then
        local oldPigOnGetItemFromPlayer = inst.components.trader.onaccept
        inst.components.trader.onaccept = function(inst, giver, item)
            if giver.prefab ~= "wili" then
                oldPigOnGetItemFromPlayer(inst, giver, item)
            else
                if item.components.edible ~= nil then
                    -- meat makes us friends (unless I'm a guard)
                    if (item.components.edible.foodtype == GLOBAL.FOODTYPE.MEAT or item.components.edible.foodtype ==
                        GLOBAL.FOODTYPE.HORRIBLE) and item.components.inventoryitem ~= nil and
                        ( -- make sure it didn't drop due to pockets full
                        item.components.inventoryitem:GetGrandOwner() == inst or
                            -- could be merged into a stack
                            (not item:IsValid() and inst.components.inventory:FindItem(function(obj)
                                return obj.prefab == item.prefab and obj.components.stackable ~= nil and
                                           obj.components.stackable:IsStack()
                            end) ~= nil)) then
                        if inst.components.combat:TargetIs(giver) then
                            inst.components.combat:SetTarget(nil)
                        elseif giver.components.leader ~= nil and
                            not (inst:HasTag("guard") or giver:HasTag("monster") or giver:HasTag("merm")) then

                            if giver.components.minigame_participator == nil then
                                giver:PushEvent("makefriend")
                                -- giver.components.leader:AddFollower(inst)
                            end
                            -- inst.components.follower:AddLoyaltyTime(item.components.edible:GetHunger() * TUNING.PIG_LOYALTY_PER_HUNGER)
                            -- inst.components.follower.maxfollowtime =
                            --     giver:HasTag("polite")
                            --     and TUNING.PIG_LOYALTY_MAXTIME + TUNING.PIG_LOYALTY_POLITENESS_MAXTIME_BONUS
                            --     or TUNING.PIG_LOYALTY_MAXTIME
                        end
                    end
                    if inst.components.sleeper:IsAsleep() then
                        inst.components.sleeper:WakeUp()
                    end
                end
                if item.components.equippable ~= nil and item.components.equippable.equipslot == GLOBAL.EQUIPSLOTS.HEAD then
                    local current = inst.components.inventory:GetEquippedItem(GLOBAL.EQUIPSLOTS.HEAD)
                    if current ~= nil then
                        inst.components.inventory:DropItem(current)
                    end
                    inst.components.inventory:Equip(item)
                    inst.AnimState:Show("hat")
                end
            end
        end

    end
end)

AddPrefabPostInit("bunnyman", function(inst)
    if GLOBAL.TheWorld.ismastersim then
        local oldBunnyOnGetItemFromPlayer = inst.components.trader.onaccept
        inst.components.trader.onaccept = function(inst, giver, item)
            if giver.prefab ~= "wili" then
                oldBunnyOnGetItemFromPlayer(inst, giver, item)
            else
                if item.components.edible ~= nil then
                    if (item.prefab == "carrot" or item.prefab == "carrot_cooked") and item.components.inventoryitem ~=
                        nil and ( -- make sure it didn't drop due to pockets full
                    item.components.inventoryitem:GetGrandOwner() == inst or
                        -- could be merged into a stack
                        (not item:IsValid() and inst.components.inventory:FindItem(function(obj)
                            return obj.prefab == item.prefab and obj.components.stackable ~= nil and
                                       obj.components.stackable:IsStack()
                        end) ~= nil)) then
                        if inst.components.combat:TargetIs(giver) then
                            inst.components.combat:SetTarget(nil)
                        elseif giver.components.leader ~= nil then
                            if giver.components.minigame_participator == nil then
                                giver:PushEvent("makefriend")
                                -- giver.components.leader:AddFollower(inst)
                            end
                            -- inst.components.follower:AddLoyaltyTime(
                            --     giver:HasTag("polite")
                            --     and TUNING.RABBIT_CARROT_LOYALTY + TUNING.RABBIT_POLITENESS_LOYALTY_BONUS
                            --     or TUNING.RABBIT_CARROT_LOYALTY
                            -- )
                        end
                    end
                    if inst.components.sleeper:IsAsleep() then
                        inst.components.sleeper:WakeUp()
                    end
                end

                -- I wear hats
                if item.components.equippable ~= nil and item.components.equippable.equipslot == GLOBAL.EQUIPSLOTS.HEAD then
                    local current = inst.components.inventory:GetEquippedItem(GLOBAL.EQUIPSLOTS.HEAD)
                    if current ~= nil then
                        inst.components.inventory:DropItem(current)
                    end
                    inst.components.inventory:Equip(item)
                    inst.AnimState:Show("hat")
                end
            end
        end
    end

end)

AddPrefabPostInit("rocky", function(inst)
    if GLOBAL.TheWorld.ismastersim then
        local oldRockyOnGetItemFromPlayer = inst.components.trader.onaccept
        inst.components.trader.onaccept = function(inst, giver, item)
            if giver.prefab ~= "wili" then
                oldRockyOnGetItemFromPlayer(inst, giver, item)
            else
                if item.components.edible ~= nil and item.components.edible.foodtype == GLOBAL.FOODTYPE.ELEMENTAL and
                    item.components.inventoryitem ~= nil and ( -- make sure it didn't drop due to pockets full
                item.components.inventoryitem:GetGrandOwner() == inst or
                    -- could be merged into a stack
                    (not item:IsValid() and inst.components.inventory:FindItem(function(obj)
                        return obj.prefab == item.prefab and obj.components.stackable ~= nil and
                                   obj.components.stackable:IsStack()
                    end) ~= nil)) then
                    if inst.components.combat:TargetIs(giver) then
                        inst.components.combat:SetTarget(nil)
                    elseif giver.components.leader ~= nil then
                        if not giver.components.minigame_participator then
                            giver:PushEvent("makefriend")
                            -- giver.components.leader:AddFollower(inst)
                        end
                        inst.components.follower:AddLoyaltyTime(
                            (giver:HasTag("polite") and TUNING.ROCKY_LOYALTY + TUNING.ROCKY_POLITENESS_LOYALTY_BONUS) or
                                TUNING.ROCKY_LOYALTY)
                        inst.sg:GoToState("rocklick")
                    end
                end

                if inst.components.sleeper:IsAsleep() then
                    inst.components.sleeper:WakeUp()
                end
            end
        end
    end

end)

AddPrefabPostInit("flower", function(inst)
    if GLOBAL.TheWorld.ismastersim then
        oldinit_flower = inst.components.pickable.onpickedfn
        inst.components.pickable.onpickedfn = function(inst, picker)
            if picker.prefab ~= "wili" then
                oldinit_flower(inst, picker)
            else
                local pos = inst:GetPosition()

                if picker ~= nil then
                    if picker.components.sanity ~= nil and not picker:HasTag("plantkin") then
                        -- picker.components.sanity:DoDelta(TUNING.SANITY_TINY)
                    end

                    if inst.animname == ROSE_NAME and picker.components.combat ~= nil and
                        not (picker.components.inventory ~= nil and
                            picker.components.inventory:EquipHasTag("bramble_resistant")) and
                        not picker:HasTag("shadowminion") then
                        picker.components.combat:GetAttacked(inst, TUNING.ROSE_DAMAGE)
                        picker:PushEvent("thorns")
                    end
                end

                GLOBAL.TheWorld:PushEvent("plantkilled", {
                    doer = picker,
                    pos = pos
                }) -- this event is pushed in other places too
            end
        end
    end

end)

-- prevent cx picking up Chester's Eyebone
local function PreventEyebonePickup(inst)
    if inst and inst.components.inventory then
        inst:ListenForEvent("itemget", function(inst, data)
            if data.item and (data.item.prefab == "chester_eyebone" or data.item.prefab == "hutch_fishbowl") then
                inst.components.inventory:DropItem(data.item)
                inst.components.talker:Say("no follower I need")
            end
        end)
    end
end

-- Apply the restriction to the custom character
local function ApplyEyeboneRestriction(inst)
    if inst.prefab == "wili" then
        inst:DoTaskInTime(0, function()
            PreventEyebonePickup(inst)
        end)
    end
end
AddPrefabPostInit("wili", ApplyEyeboneRestriction)

-- 改进的随机种子生成函数
local function better_random_seed()
    local time_seed = GLOBAL.tonumber(GLOBAL.tostring(GLOBAL.os.time()):reverse():sub(1, 6))
    local line_seed = GLOBAL.tonumber(GLOBAL.tostring(GLOBAL.debug.getinfo(1).currentline):reverse())
    return time_seed + line_seed
end

-- 在脚本开始时设置一次随机数种子
math.randomseed(better_random_seed())

local function onAttacked(inst, data)
    local chance = math.random(100)
    if chance < 13 then
        inst.components.talker:Say("Time To Revenge!")
        inst.components.health:SetInvincible(true)
        inst:DoTaskInTime(13, function()
            inst.components.health:SetInvincible(false)
        end)
    else
        inst.components.health:SetInvincible(false)
    end
end

local function onDamageImmunity(inst)
    if inst.components.combat then
        inst:ListenForEvent("attacked", onAttacked)
    end
end

AddPrefabPostInit("wili", onDamageImmunity)

local require = GLOBAL.require
local STRINGS = GLOBAL.STRINGS

STRINGS.NAMES.SCIMITAR = "Silver Moon Scimitar"
STRINGS.RECIPE_DESC.SCIMITAR = "Source of wealth!"
STRINGS.CHARACTERS.GENERIC.DESCRIBE.SCIMITAR = "Source of wealth!"

TUNING.GAMEMODE_STARTING_ITEMS.DEFAULT.WILI = {"scimitar"}
TUNING.STARTING_ITEM_IMAGE_OVERRIDE["scimitar"] = {
    atlas = "images/inventoryimages/scimitar.xml",
    image = "scimitar.tex"
}
PrefabFiles = {"wili", "wili_none", "scimitar"}
--- 制作栏部分
local wilitab = AddRecipeTab("wili's Tab", 996, "images/modicon.xml", "modicon.tex", "wili_builder")
local scimitar_recipe = AddRecipe("scimitar", {Ingredient("nightmarefuel", 2), Ingredient("goldnugget", 2),
                                               Ingredient("walrus_tusk", 1)}, wilitab, GLOBAL.TECH.NONE, nil, nil, nil,
    nil, "wili_builder", "images/inventoryimages/scimitar.xml", "scimitar.tex")

local shadow_forge_kit_recipe = AddRecipe("shadow_forge_kit", {Ingredient("nightmarefuel", 5),
                                                               Ingredient("dreadstone", 2), Ingredient("horrorfuel", 1)},
    wilitab, GLOBAL.TECH.NONE, nil, nil, nil, 1, "wili_builder")

local lunar_forge_kit_recipe = AddRecipe("lunar_forge_kit", {Ingredient("moonrocknugget", 5),
                                                             Ingredient("moonglass", 5), Ingredient("purebrilliance", 1)},
    wilitab, GLOBAL.TECH.NONE, nil, nil, nil, 1, "wili_builder")

local horrorfuel_recipe = AddRecipe("horrorfuel", {Ingredient("nightmarefuel", 3)}, wilitab, GLOBAL.TECH.NONE, nil, nil,
    nil, 2, "wili_builder")

local voidcloth_recipe = AddRecipe("voidcloth",
    {Ingredient("horrorfuel", 1), Ingredient("silk", 1), Ingredient("redgem", 1)}, wilitab, GLOBAL.TECH.NONE, nil, nil,
    nil, 3, "wili_builder")

local dreadstone_recipe = AddRecipe("dreadstone", {Ingredient("horrorfuel", 1), Ingredient("rocks", 1)}, wilitab,
    GLOBAL.TECH.NONE, nil, nil, nil, 3, "wili_builder")

local moonrocknugget_recipe = AddRecipe("moonrocknugget", {Ingredient("rocks", 2)}, wilitab, GLOBAL.TECH.NONE, nil, nil,
    nil, 3, "wili_builder")

local moonglass_recipe = AddRecipe("moonglass", {Ingredient("moonrocknugget", 1), Ingredient("bluegem", 1)}, wilitab,
    GLOBAL.TECH.NONE, nil, nil, nil, 3, "wili_builder")

local moonglass_charged_recipe = AddRecipe("moonglass_charged",
    {Ingredient("moonglass", 1), Ingredient("lightbulb", 1)}, wilitab, GLOBAL.TECH.NONE, nil, nil, nil, 3,
    "wili_builder")

local purebrilliance_recipe = AddRecipe("purebrilliance", {Ingredient("moonglass_charged", 3)}, wilitab,
    GLOBAL.TECH.NONE, nil, nil, nil, 3, "wili_builder")

local lunarplant_husk_recipe = AddRecipe("lunarplant_husk", {Ingredient("eggplant", 1), Ingredient("bluegem", 1)},
    wilitab, GLOBAL.TECH.NONE, nil, nil, nil, 3, "wili_builder")

local bluegem_recipe = AddRecipe("bluegem", {Ingredient("purplegem", 1)}, wilitab, GLOBAL.TECH.NONE, nil, nil, nil, 3,
    "wili_builder")

local redgem_recipe = AddRecipe("redgem", {Ingredient("purplegem", 1)}, wilitab, GLOBAL.TECH.NONE, nil, nil, nil, 3,
    "wili_builder")

local purplegem_recipe = AddRecipe("purplegem", {Ingredient("bluegem", 1), Ingredient("redgem", 1)}, wilitab,
    GLOBAL.TECH.NONE, nil, nil, nil, 3, "wili_builder")

local greengem_recipe = AddRecipe("greengem", {Ingredient("bluegem", 1), Ingredient("yellowgem", 1)}, wilitab,
    GLOBAL.TECH.NONE, nil, nil, nil, 3, "wili_builder")

local orangegem_recipe = AddRecipe("orangegem", {Ingredient("yellowgem", 1), Ingredient("redgem", 1)}, wilitab,
    GLOBAL.TECH.NONE, nil, nil, nil, 3, "wili_builder")

local yellowgem_recipe = AddRecipe("yellowgem", {Ingredient("opalpreciousgem", 1)}, wilitab, GLOBAL.TECH.NONE, nil, nil,
    nil, 5, "wili_builder")

local opalpreciousgem_recipe = AddRecipe("opalpreciousgem",
    {Ingredient("redgem", 1), Ingredient("bluegem", 1), Ingredient("purplegem", 1), Ingredient("greengem", 1),
     Ingredient("orangegem", 1), Ingredient("yellowgem", 1)}, wilitab, GLOBAL.TECH.NONE, nil, nil, nil, 1,
    "wili_builder")

local opalstaff_recipe = AddRecipe("opalstaff", {Ingredient("opalpreciousgem", 1), Ingredient("livinglog", 2),
                                                 Ingredient("nightmarefuel", 4)}, wilitab, GLOBAL.TECH.NONE, nil, nil,
    nil, 1, "wili_builder")
--- end of the character recipe tab

-- The character select screen lines
STRINGS.CHARACTER_TITLES.wili = "Moon Shadow Assassin"
STRINGS.CHARACTER_NAMES.wili = "Wili"
STRINGS.CHARACTER_DESCRIPTIONS.wili = "*seeing thing clear at night\n*ice cold\n*deadly weapon"
STRINGS.CHARACTER_QUOTES.wili = "\"kill every last one of them\""
STRINGS.CHARACTER_SURVIVABILITY.wili = "Slim"

-- Custom speech strings
STRINGS.CHARACTERS.WILI = require "speech_wili"

-- The character's name as appears in-game 
STRINGS.NAMES.WILI = "wili"
STRINGS.SKIN_NAMES.wili_none = "wili"

-- The skins shown in the cycle view window on the character select screen.
-- A good place to see what you can put in here is in skinutils.lua, in the function GetSkinModes
local skin_modes = {{
    type = "ghost_skin",
    anim_bank = "ghost",
    idle_anim = "idle",
    scale = 0.75,
    offset = {0, -25}
}}

-- Add mod character to mod character list. Also specify a gender. Possible genders are MALE, FEMALE, ROBOT, NEUTRAL, and PLURAL.
AddModCharacter("wili", "FEMALE", skin_modes)
