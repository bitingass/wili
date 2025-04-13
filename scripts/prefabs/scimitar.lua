local assets = {Asset("ANIM", "anim/scimitar.zip"), Asset("ANIM", "anim/swap_scimitar.zip"),
                Asset("ATLAS", "images/inventoryimages/scimitar.xml"),
                Asset("IMAGE", "images/inventoryimages/scimitar.tex")}

local function onequip(inst, owner)
    if owner.prefab ~= "wili" then
        if owner.components.talker then
            owner.components.talker:Say("get rejected")
        end
        owner:DoTaskInTime(0, function()
            owner.components.inventory:Unequip(EQUIPSLOTS.HANDS)
            owner.components.inventory:GiveItem(inst)
        end)
        return
    end

    owner.AnimState:OverrideSymbol("swap_object", "swap_scimitar", "swap_spear")
    owner.AnimState:Show("ARM_carry")
    owner.AnimState:Hide("ARM_normal")
end

local function onunequip(inst, owner)
    owner.AnimState:Hide("ARM_carry")
    owner.AnimState:Show("ARM_normal")
end

local gem = {"redgem", "bluegem", "purplegem", "greengem", "orangegem", "yellowgem", "opalpreciousgem"}
-- local gem = {"opalpreciousgem"}
local function better_random_seed()
    local time_seed = tonumber(tostring(os.time()):reverse():sub(1, 6))
    local line_seed = tonumber(tostring(debug.getinfo(1).currentline):reverse())
    return time_seed + line_seed
end

math.randomseed(better_random_seed())

local gem_gen_rate = TUNING.CHARACTER_PREFAB_MODCONFIGDATA["gemGenRate"]
local GEM_DROP_CHANCE = 1 + (-1.0) * gem_gen_rate -- x%
local GEM_OFFSET_RADIUS = 2
local GEM_OFFSET_ATTEMPTS = 3

local function onattack(inst, owner, target)
    owner.Transform:SetPosition(target.Transform:GetWorldPosition())

    -- 宝石掉落逻辑
    if math.random() >= GEM_DROP_CHANCE then
        local gem_to_spawn = gem[math.random(#gem)]
        local pt = target:GetPosition()
        local st_pt = FindWalkableOffset(pt, math.random() * 2 * math.pi, GEM_OFFSET_RADIUS, GEM_OFFSET_ATTEMPTS)
        if st_pt then
            st_pt = st_pt + pt
            local st = SpawnPrefab(gem_to_spawn)
            st.Transform:SetPosition(st_pt.x, st_pt.y, st_pt.z)
        end
    end
end

local function fn()
    local inst = CreateEntity()
    local trans = inst.entity:AddTransform()
    local anim = inst.entity:AddAnimState()
    inst.entity:AddSoundEmitter()
    inst.entity:AddNetwork()
    MakeInventoryPhysics(inst)

    inst.AnimState:SetBank("nightmaresword")
    inst.AnimState:SetBuild("scimitar")
    inst.AnimState:PlayAnimation("idle")

    inst:AddTag("sharp")

    if not TheWorld.ismastersim then
        return inst
    end

    inst:AddComponent("inspectable")

    inst:AddComponent("inventoryitem")
    inst.components.inventoryitem.atlasname = "images/inventoryimages/scimitar.xml"

    inst:AddComponent("equippable")
    inst.components.equippable:SetOnEquip(onequip)
    inst.components.equippable:SetOnUnequip(onunequip)

    inst:AddComponent("weapon")
    inst.components.weapon:SetDamage(44)
    inst.components.weapon:SetRange(TUNING.BOOMERANG_DISTANCE, TUNING.BOOMERANG_DISTANCE + 1)
    inst.components.weapon.onattack = onattack

    return inst
end

return Prefab("common/inventory/scimitar", fn, assets)
