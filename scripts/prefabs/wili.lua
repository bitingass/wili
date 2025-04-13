local MakePlayerCharacter = require "prefabs/player_common"

local oneshot_weapon_name = {"nightsword", "glasscutter", "shovel_lunarplant", "pickaxe_lunarplant", "moonglassaxe",
                             "voidcloth_scythe", "batbat", "ruins_bat", "shadow_battleaxe", "sword_lunarplant"}

local assets = {Asset("SCRIPT", "scripts/prefabs/player_common.lua"), Asset("SOUNDPACKAGE", "sound/wili.fev"),
                Asset("SOUND", "sound/wili_bank00.fsb"), Asset("ANIM", "anim/wili.zip"),
                Asset("ANIM", "anim/ghost_wili_build.zip")}

-- Your character's stats
TUNING.WILI_HEALTH = 88
TUNING.WILI_HUNGER = 132
TUNING.WILI_SANITY = 176

-- Custom starting inventory
TUNING.GAMEMODE_STARTING_ITEMS.DEFAULT.WILI = {"scimitar", "lunar_forge_kit", "shadow_forge_kit"}

local start_inv = {"scimitar", "lunar_forge_kit", "shadow_forge_kit"}
for k, v in pairs(TUNING.GAMEMODE_STARTING_ITEMS) do
    start_inv[string.lower(k)] = v.WILI
end
local prefabs = {}

-- When the character is revived from human
local function onbecamehuman(inst)
    -- Set speed when not a ghost (optional)
    inst.components.locomotor:SetExternalSpeedMultiplier(inst, "wili_speed_mod", 1.75)
end

local function onbecameghost(inst)
    -- Remove speed modifier when becoming a ghost
    inst.components.locomotor:RemoveExternalSpeedMultiplier(inst, "wili_speed_mod")
end

-- When loading or spawning the character
local function onload(inst)
    inst:ListenForEvent("ms_respawnedfromghost", onbecamehuman)
    inst:ListenForEvent("ms_becameghost", onbecameghost)

    if inst:HasTag("playerghost") then
        onbecameghost(inst)
    else
        onbecamehuman(inst)
    end
end

-- This initializes for both the server and client. Tags can be added here.
local common_postinit = function(inst)
    -- Minimap icon
    inst.MiniMapEntity:SetIcon("wili.tex")
    inst:AddTag("wili_builder")
end

local function better_random_seed()
    local time_seed = tonumber(tostring(os.time()):reverse():sub(1, 6))
    local line_seed = tonumber(tostring(debug.getinfo(1).currentline):reverse())
    return time_seed + line_seed
end

local function table_contains(table, value)
    for k, v in pairs(table) do
        if v == value then
            return true
        end
    end
    return false
end

-- 在脚本开始时设置一次随机数种子
math.randomseed(better_random_seed())

local oneshot_rate = TUNING.CHARACTER_PREFAB_MODCONFIGDATA["oneshotRate"]
local ONESHOT_CHANCE = 1 + (-1.0) * oneshot_rate

local changedamage = function(inst, data)
    local hand = inst.components.inventory:GetEquippedItem(EQUIPSLOTS.HANDS)
    if hand and math.random() >= ONESHOT_CHANCE and table_contains(oneshot_weapon_name, hand.prefab) then
        inst.SoundEmitter:PlaySound("wili/skill/coup_de_grace")
        inst.components.combat.damagemultiplier = 99999
        inst.components.talker:Say("Give you relief!")
    else
        inst.components.combat.damagemultiplier = 2
    end
end

local function onattack(inst, owner, target)
    owner.Transform:SetPosition(target.Transform:GetWorldPosition())
end

-- 下面代码是由于一些武器本身有特殊效果，因此需要将源代码移植
local function batbat_attack(inst, owner, target)
    onattack(inst, owner, target)
    if owner.components.health and owner.components.health:GetPercent() < 1 and not target:HasTag("wall") then
        owner.components.health:DoDelta(TUNING.BATBAT_DRAIN, false, "batbat")
        owner.components.sanity:DoDelta(-TUNING.BATBAT_DRAIN * 0.5)
    end
end

local function NoHoles(pt)
    return not TheWorld.Map:IsPointNearHole(pt)
end
local function ruins_bat_attack(inst, owner, target)
    onattack(inst, owner, target)
    if math.random() < 0.4 then
        local pt
        if target ~= nil and target:IsValid() then
            pt = target:GetPosition()
        else
            pt = owner:GetPosition()
            target = nil
        end
        local offset = FindWalkableOffset(pt, math.random() * TWOPI, 2, 3, false, true, NoHoles, false, true)
        if offset ~= nil then
            inst.SoundEmitter:PlaySound("dontstarve/common/shadowTentacleAttack_1")
            inst.SoundEmitter:PlaySound("dontstarve/common/shadowTentacleAttack_2")
            local tentacle = SpawnPrefab("shadowtentacle")
            if tentacle ~= nil then
                tentacle.owner = owner
                tentacle.Transform:SetPosition(pt.x + offset.x, 0, pt.z + offset.z)
                tentacle.components.combat:SetTarget(target)
            end
        end
    end
end

local function shadow_battleaxe_attack(inst, owner, target)
    onattack(inst, owner, target)
    if target ~= nil and target:IsValid() then
        inst:DoAttackEffects(owner, target)
    end

    if target.components.health ~= nil and target.components.health:IsDead() then
        inst.components.hunger:DoDelta(TUNING.SHADOW_BATTLEAXE.HUNGER_GAIN_ONKILL, false)

        if inst._trackedentities[target] == nil then -- The tracking will give us the kill stack.
            local is_epic = inst:CheckForEpicCreatureKilled(target)

            if owner ~= nil and not is_epic then
                inst:SayRegularChatLine("creature_killed", owner)
            end
        end

    elseif inst:IsEpicCreature(target) and inst.epic_kill_count <
        TUNING.SHADOW_BATTLEAXE.LEVEL_THRESHOLDS[#TUNING.SHADOW_BATTLEAXE.LEVEL_THRESHOLDS] then
        inst:TrackTarget(target)
    end

    if inst._lifesteal == nil or inst._lifesteal <= 0 then
        return
    end

    inst:DoLifeSteal(owner, target)
end

local function glassglasscutter_attack(inst, owner, target)
    onattack(inst, owner, target)
    inst.components.weapon.attackwear = target ~= nil and target:IsValid() and
                                            (target:HasTag("shadow") or target:HasTag("shadowminion") or
                                                target:HasTag("shadowchesspiece") or target:HasTag("stalker") or
                                                target:HasTag("stalkerminion") or target:HasTag("shadowthrall")) and
                                            TUNING.GLASSCUTTER.SHADOW_WEAR or 1
end

local function sword_lunarplant_attack(inst, owner, target)
    onattack(inst, owner, target)
    if target ~= nil and target:IsValid() then
        SpawnPrefab("hitsparks_fx"):Setup(owner, target)
    end
end

local function moonglassaxe_attack(inst, owner, target)
    onattack(inst, owner, target)
    inst.components.weapon.attackwear = target ~= nil and target:IsValid() and
                                            (target:HasTag("shadow") or target:HasTag("shadowminion") or
                                                target:HasTag("shadowchesspiece") or target:HasTag("stalker") or
                                                target:HasTag("stalkerminion")) and TUNING.MOONGLASSAXE.SHADOW_WEAR or
                                            TUNING.MOONGLASSAXE.ATTACKWEAR
end

local hitsparks_fx_colouroverride = {1, 0, 0}
local function voidcloth_scythe_attack(inst, owner, target)
    onattack(inst, owner, target)
    if target ~= nil and target:IsValid() then
        local spark = SpawnPrefab("hitsparks_fx")
        spark:Setup(owner, target, nil, hitsparks_fx_colouroverride)
        spark.black:set(true)
    end
end

local attack_functions = {
    nightsword = onattack,
    glasscutter = glassglasscutter_attack,
    shovel_lunarplant = onattack,
    pickaxe_lunarplant = onattack,
    moonglassaxe = moonglassaxe_attack,
    voidcloth_scythe = voidcloth_scythe_attack,
    batbat = batbat_attack,
    ruins_bat = ruins_bat_attack,
    sword_lunarplant = sword_lunarplant_attack,
    shadow_battleaxe = shadow_battleaxe_attack
}

-- 特殊武器切换武器代码
local function changeweapon(inst)
    local hand = inst.components.inventory:GetEquippedItem(EQUIPSLOTS.HANDS)
    if hand and hand.components.weapon then
        hand.components.weapon.temp_attack = hand.components.weapon.onattack
        local weapon_name = hand.prefab
        if table_contains(oneshot_weapon_name, weapon_name) then
            hand.components.weapon:SetRange(TUNING.BOOMERANG_DISTANCE, TUNING.BOOMERANG_DISTANCE + 1)
            local attack_fn = attack_functions[weapon_name]
            if attack_fn then
                hand.components.weapon.onattack = attack_fn
            end
        end
        -- if theWeaponname == "batbat" then
        --     hand.components.weapon:SetRange(TUNING.BOOMERANG_DISTANCE, TUNING.BOOMERANG_DISTANCE + 1)
        --     hand.components.weapon.onattack = batbat_attack
        -- elseif theWeaponname == "ruins_bat" then
        --     hand.components.weapon:SetRange(TUNING.BOOMERANG_DISTANCE, TUNING.BOOMERANG_DISTANCE + 1)
        --     hand.components.weapon.onattack = ruins_bat_attack
        -- elseif theWeaponname == "shadow_battleaxe" then
        --     hand.components.weapon:SetRange(TUNING.BOOMERANG_DISTANCE, TUNING.BOOMERANG_DISTANCE + 1)
        --     hand.components.weapon.onattack = shadow_battleaxe_attack
        -- elseif theWeaponname == "sword_lunarplant" then
        --     hand.components.weapon:SetRange(TUNING.BOOMERANG_DISTANCE, TUNING.BOOMERANG_DISTANCE + 1)
        --     hand.components.weapon.onattack = sword_lunarplant_attack
        -- elseif table_contains(oneshot_weapon_name, thename) then
        --     hand.components.weapon:SetRange(TUNING.BOOMERANG_DISTANCE, TUNING.BOOMERANG_DISTANCE + 1)
        --     hand.components.weapon.onattack = onattack
        -- end
        -- 这是源作者的代码，讲道理，这么写和GTA:V的19.8亿次if有什么区别(笑哭)
    end
end

local function recoverweapon(inst, data)
    local item = data.item
    local thename
    if item then
        thename = item.prefab
        if item.components.weapon and table_contains(oneshot_weapon_name, thename) then
            item.components.weapon.onattack = item.components.weapon.temp_attack
            item.components.weapon:SetRange(nil)
        end
    end

end

local ZERO_DISTANCE = 10
local ZERO_DISTSQ = ZERO_DISTANCE * ZERO_DISTANCE
local UPDATE_SPAWNLIGHT_ONEOF_TAGS = {"HASHEATER", "spawnlight"}
local UPDATE_NOSPAWNLIGHT_MUST_TAGS = {"HASHEATER"}

function OnUpdate(self, dt, applyhealthdelta)
    self.inst.Light:Enable(true)
    self.inst.Light:SetRadius(13)
    self.inst.Light:SetFalloff(0.75)
    self.inst.Light:SetIntensity(.6)
    self.inst.Light:SetColour(235 / 255, 12 / 255, 12 / 255)

    self.externalheaterpower = 0
    self.delta = 0
    self.rate = 0

    if self.settemp ~= nil or self.inst.is_teleporting or
        (self.inst.components.health ~= nil and self.inst.components.health:IsInvincible()) then
        return
    end

    local x, y, z = self.inst.Transform:GetWorldPosition()

    -- Can override range, e.g. in special containers
    local mintemp = self.mintemp
    local maxtemp = self.maxtemp

    local owner = self.inst.components.inventoryitem ~= nil and self.inst.components.inventoryitem.owner or nil
    local inside_pocket_container = owner ~= nil and owner:HasTag("pocketdimension_container")

    local ambient_temperature = inside_pocket_container and TheWorld.state.temperature or GetTemperatureAtXZ(x, z)

    if owner ~= nil and owner:HasTag("fridge") and not owner:HasTag("nocool") then
        -- Inside a fridge, excluding icepack ("nocool")
        -- Don't cool it below freezing unless ambient temperature is below freezing
        mintemp = math.max(mintemp, math.min(0, ambient_temperature))
        self.rate = owner:HasTag("lowcool") and -.5 * TUNING.WARM_DEGREES_PER_SEC or -TUNING.WARM_DEGREES_PER_SEC
    else
        local sleepingbag_ambient_temp = self.inst.sleepingbag ~= nil and
                                             self.inst.sleepingbag.components.sleepingbag.ambient_temp
        if sleepingbag_ambient_temp then
            ambient_temperature = sleepingbag_ambient_temp
        end

        local ents
        if not inside_pocket_container then
            -- Prepare to figure out the temperature where we are standing
            ents = self.usespawnlight and
                       TheSim:FindEntities(x, y, z, ZERO_DISTANCE, nil, self.ignoreheatertags,
                    UPDATE_SPAWNLIGHT_ONEOF_TAGS) or
                       TheSim:FindEntities(x, y, z, ZERO_DISTANCE, UPDATE_NOSPAWNLIGHT_MUST_TAGS, self.ignoreheatertags)
            if self.usespawnlight and #ents > 0 then
                for i, v in ipairs(ents) do
                    if v.components.heater == nil and v:HasTag("spawnlight") then
                        ambient_temperature = math.clamp(ambient_temperature, 10, TUNING.OVERHEAT_TEMP - 20)
                        table.remove(ents, i)
                        break
                    end
                end
            end
        end

        if self.sheltered_level > 1 then
            ambient_temperature = math.min(ambient_temperature, self.overheattemp - 5)
        end

        self.delta = (ambient_temperature + self.totalmodifiers + self:GetMoisturePenalty()) - self.current
        -- print(self.delta + self.current, "initial target")

        if self.inst.components.inventory ~= nil then
            for k, v in pairs(self.inst.components.inventory.equipslots) do
                if v.components.heater ~= nil then
                    local heat = v.components.heater:GetEquippedHeat()
                    if heat ~= nil and ((heat > self.current and v.components.heater:IsExothermic()) or
                        (heat < self.current and v.components.heater:IsEndothermic())) then
                        self.delta = self.delta + heat - self.current
                    end
                end
            end
            for k, v in pairs(self.inst.components.inventory.itemslots) do
                if v.components.heater ~= nil then
                    local heat, carriedmult = v.components.heater:GetCarriedHeat()
                    if heat ~= nil and ((heat > self.current and v.components.heater:IsExothermic()) or
                        (heat < self.current and v.components.heater:IsEndothermic())) then
                        self.delta = self.delta + (heat - self.current) * carriedmult
                    end
                end
            end
            local overflow = self.inst.components.inventory:GetOverflowContainer()
            if overflow ~= nil then
                for k, v in pairs(overflow.slots) do
                    if v.components.heater ~= nil then
                        local heat, carriedmult = v.components.heater:GetCarriedHeat()
                        if heat ~= nil and ((heat > self.current and v.components.heater:IsExothermic()) or
                            (heat < self.current and v.components.heater:IsEndothermic())) then
                            self.delta = self.delta + (heat - self.current) * carriedmult
                        end
                    end
                end
            end
        end

        -- print(self.delta + self.current, "after carried/equipped")

        -- Recently eaten temperatured food is inherently equipped heat/cold
        if self.bellytemperaturedelta ~= nil and
            ((self.bellytemperaturedelta > 0 and self.current < TUNING.HOT_FOOD_WARMING_THRESHOLD) or
                (self.bellytemperaturedelta < 0 and self.current > TUNING.COLD_FOOD_CHILLING_THRESHOLD)) then
            self.delta = self.delta + self.bellytemperaturedelta
        end

        -- print(self.delta + self.current, "after belly")

        -- If very hot (basically only when have overheating screen effect showing) and under shelter, cool slightly
        if self.sheltered and self.current > TUNING.TREE_SHADE_COOLING_THRESHOLD then
            self.delta = self.delta - (self.current - TUNING.TREE_SHADE_COOLER)
        end

        -- print(self.delta + self.current, "after shelter")
        if not inside_pocket_container then
            for i, v in ipairs(ents) do
                if v ~= self.inst and not v:IsInLimbo() and v.components.heater ~= nil and
                    (v.components.heater:IsExothermic() or v.components.heater:IsEndothermic()) then

                    local heat = v.components.heater:GetHeat(self.inst)
                    if heat ~= nil then
                        -- This produces a gentle falloff from 1 to zero.
                        local heatfactor = 1 - self.inst:GetDistanceSqToInst(v) / ZERO_DISTSQ
                        if self.inst:GetIsWet() then
                            heatfactor = heatfactor * TUNING.WET_HEAT_FACTOR_PENALTY
                        end

                        if v.components.heater:IsExothermic() then
                            -- heating heatfactor is relative to 0 (freezing)
                            local warmingtemp = heat * heatfactor
                            if warmingtemp > self.current then
                                self.delta = self.delta + warmingtemp - self.current
                            end
                            self.externalheaterpower = self.externalheaterpower + warmingtemp
                        else -- if v.components.heater:IsEndothermic() then
                            -- cooling heatfactor is relative to overheattemp
                            local coolingtemp = (heat - self.overheattemp) * heatfactor + self.overheattemp
                            if coolingtemp < self.current then
                                self.delta = self.delta + coolingtemp - self.current
                            end
                        end
                    end
                end
            end
        end

        -- print(self.delta + self.current, "after heaters")

        -- Winter insulation only affects you when it's cold out, summer insulation only helps when it's warm
        if ambient_temperature >= TUNING.STARTING_TEMP then
            -- it's warm out
            if self.delta > 0 then
                -- If the player is heating up, defend using insulation.
                local winterInsulation, summerInsulation = self:GetInsulation()
                self.rate = math.min(self.delta, TUNING.SEG_TIME / (TUNING.SEG_TIME + summerInsulation))
            else
                -- If they are cooling, do it at full speed, and faster if they're overheated
                self.rate = math.max(self.delta, self.current >= self.overheattemp and -TUNING.THAW_DEGREES_PER_SEC or
                    -TUNING.WARM_DEGREES_PER_SEC)
            end
            -- it's cold out
        elseif self.delta < 0 then
            -- If the player is cooling, defend using insulation.
            local winterInsulation, summerInsulation = self:GetInsulation()
            self.rate = math.max(self.delta, -TUNING.SEG_TIME / (TUNING.SEG_TIME + winterInsulation))
        else
            -- If they are heating up, do it at full speed, and faster if they're freezing
            self.rate = math.min(self.delta,
                self.current <= 0 and TUNING.THAW_DEGREES_PER_SEC or TUNING.WARM_DEGREES_PER_SEC)
        end

        -- print(self.delta + self.current, "after insulation")
        -- print(self.rate, "final rate\n\n")
    end

    self.rate = self.rate * 2
    self:SetTemperature(math.clamp(self.current + self.rate * dt, mintemp, maxtemp))

    -- applyhealthdelta nil defaults to true
    if applyhealthdelta ~= false and self.inst.components.health ~= nil then
        if self.current < 0 then
            self.inst.components.health:DoDelta(-self.hurtrate * dt, true, "cold")
        elseif self.current > self.overheattemp then
            self.inst.components.health:DoDelta(-(self.overheathurtrate or self.hurtrate) * dt, true, "hot")
        end
    end
end

-- This initializes for the server only. Components are added here.
local master_postinit = function(inst)
    inst.Physics:ClearCollidesWith(COLLISION.LAND_OCEAN_LIMITS)
    inst.Physics:ClearCollidesWith(COLLISION.OBSTACLES)
    inst.Physics:ClearCollidesWith(COLLISION.BOAT_LIMITS)
    inst.Physics:ClearCollidesWith(COLLISION.CHARACTERS)
    inst.Physics:ClearCollidesWith(COLLISION.GIANTS)
    -- inst.Physics:ClearCollisionMask()
    inst.components.drownable.enabled = false
    -- Set starting inventory
    inst.starting_inventory = start_inv[TheNet:GetServerGameMode()] or start_inv.default

    -- choose which sounds this character will play
    inst.soundsname = "Willow"

    -- Uncomment if "wathgrithr"(Wigfrid) or "webber" voice is used
    -- inst.talker_path_override = "dontstarve_DLC001/characters/"

    -- Stats	
    inst.components.health:SetMaxHealth(TUNING.WILI_HEALTH)
    inst.components.hunger:SetMax(TUNING.WILI_HUNGER)
    inst.components.sanity:SetMax(TUNING.WILI_SANITY)

    inst.components.builder.science_bonus = 3
    inst.components.builder.magic_bonus = 3
    inst.components.builder.ancient_bonus = 4

    -- move
    inst.components.locomotor:SetExternalSpeedMultiplier(inst, "wili_speed_mod", 2.25)

    -- Damage multiplier (optional)
    inst.components.combat.damagemultiplier = 2
    inst.components.combat.min_attack_period = 0.5
    inst.components.combat:SetAttackPeriod(0.5)

    -- Hunger rate (optional)
    inst.components.hunger.hungerrate = 0.25 * TUNING.WILSON_HUNGER_RATE

    -- hurtrate
    inst.components.temperature.hurtrate = 0.25

    inst.components.temperature.OnUpdate = OnUpdate

    -- Emit light at night
    inst.components.sanity.night_drain_mult = 0.1
    inst.components.sanity.neg_aura_mult = 0.1
    local light = inst.entity:AddLight()
    inst.Light:Enable(true)
    inst.Light:SetRadius(13)
    inst.Light:SetFalloff(0.75)
    inst.Light:SetIntensity(.6)
    inst.Light:SetColour(235 / 255, 12 / 255, 12 / 255)

    inst:ListenForEvent("onattackother", changedamage)
    inst:ListenForEvent("equip", changeweapon)
    inst:ListenForEvent("unequip", recoverweapon)

    inst.OnLoad = onload
    inst.OnNewSpawn = onload

end

return MakePlayerCharacter("wili", prefabs, assets, common_postinit, master_postinit, start_inv)
