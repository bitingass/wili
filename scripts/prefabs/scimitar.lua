local BlinkOnHit = require "wili_blink"

local BANK = "wili_eclipse_shiv"
local EDGE_FX = "wili_eclipse_shiv_edge_fx"
local HIT_FX = "wili_eclipse_hit_fx"
-- Mod asset registration resolves file paths in place. Give each prefab its own Asset.
local edge_assets = {Asset("ANIM", "anim/wili_eclipse_shiv.zip")}
local hit_assets = {Asset("ANIM", "anim/wili_eclipse_hit_fx.zip")}
local assets = {Asset("ANIM", "anim/wili_eclipse_shiv.zip"), Asset("ANIM", "anim/scimitar.zip"), Asset("ANIM", "anim/swap_scimitar.zip"),
                Asset("ATLAS", "images/inventoryimages/scimitar.xml"),
                Asset("IMAGE", "images/inventoryimages/scimitar.tex")}

-- FollowSymbol uses an exclusive end frame, as on the native lunar plant sword.
local held_frames = {
    { clip = "held_a_", first = 0, stop = 3 },
    { clip = "held_b_", first = 5, stop = 8 },
}
local MOON_PHASES = {
    "new", "waxing_quarter", "waxing_half", "waxing_threequarter",
    "full", "waning_threequarter", "waning_half", "waning_quarter",
}
local MOON_PHASE_ID = {}
for i, phase in ipairs(MOON_PHASES) do
    MOON_PHASE_ID[phase] = i
end
local moonlight = {
    new = 0.03, waxing_quarter = 0.10, waxing_half = 0.18, waxing_threequarter = 0.24,
    full = 0.32, waning_threequarter = 0.20, waning_half = 0.13, waning_quarter = 0.07,
}
-- Let the animated Phase Eye pulse, blade veins and moon shards read clearly in dusk/night
-- while keeping the solid blade grounded in ambient world lighting.
local glint_light = {
    new = 0.26, waxing_quarter = 0.34, waxing_half = 0.46, waxing_threequarter = 0.56,
    full = 0.68, waning_threequarter = 0.50, waning_half = 0.38, waning_quarter = 0.28,
}
-- Keep the blade-current hit slash readable in daylight, night and caves.
local hit_light = {
    new = 0.30, waxing_quarter = 0.45, waxing_half = 0.62, waxing_threequarter = 0.75,
    full = 0.90, waning_threequarter = 0.65, waning_half = 0.50, waning_quarter = 0.35,
}

-- Independent network proxy keeps playing even if the victim dies on the same frame.
local function spawn_hit_fx(inst, owner, data)
    if data == nil or data.weapon ~= inst or not (data.target and data.target:IsValid()) then return end
    local target = data.target
    local fx = SpawnPrefab(HIT_FX)
    if fx == nil then return end

    local tx, ty, tz = target.Transform:GetWorldPosition()
    local radius = target.GetPhysicsRadius ~= nil and target:GetPhysicsRadius(0) or 0
    local y_offset = math.min(1.8, 0.55 + radius * 0.55)
    local scale = math.min(1.55, 0.92 + radius * 0.22)
    local facing = 0
    if owner ~= nil and owner:IsValid() and owner.Transform ~= nil then
        local ox, _, oz = owner.Transform:GetWorldPosition()
        local dx, dz = tx - ox, tz - oz
        if dx * dx + dz * dz > 0.01 then
            facing = math.atan2(-dz, dx) * RADIANS
        else
            facing = owner.Transform:GetRotation()
        end
    end
    fx:Setup(tx, ty + y_offset, tz, facing, inst._moon, scale)
end

local EYE_GAZE_POSES = { "up", "down", "left", "right", "center" }

local function eye_light_for(phase, pose)
    local base = moonlight[phase] or 0.03
    local glow = glint_light[phase] or base
    if pose == "closed" then
        return base
    elseif pose == "half_blink" then
        return (base + glow) * 0.5
    end
    return glow
end

local function apply_eye_to_fx(fx, phase, pose)
    if fx == nil or not fx:IsValid() then return end
    fx.AnimState:OverrideSymbol("shiv_eye", BANK, "shiv_eye_" .. phase .. "_" .. pose)
    fx.AnimState:SetSymbolLightOverride("shiv_eye", eye_light_for(phase, pose))
end

local function apply_eye_pose(inst, pose)
    local phase = inst._moon or "new"
    pose = pose or inst._eye_gaze or "center"
    inst._eye_pose = pose
    inst.AnimState:OverrideSymbol("shiv_ground_eye", BANK, "shiv_ground_eye_" .. phase .. "_" .. pose)
    inst.AnimState:SetSymbolLightOverride("shiv_ground_eye", eye_light_for(phase, pose))
    if inst._edges ~= nil then
        for _, fx in ipairs(inst._edges) do
            apply_eye_to_fx(fx, phase, pose)
        end
    end
end

local function cancel_eye_blink_steps(inst)
    if inst._eye_blink_steps ~= nil then
        for _, task in ipairs(inst._eye_blink_steps) do
            task:Cancel()
        end
        inst._eye_blink_steps = nil
    end
    inst._eye_blinking = false
end

local function stop_eye_ai(inst)
    cancel_eye_blink_steps(inst)
    if inst._eye_gaze_task ~= nil then
        inst._eye_gaze_task:Cancel()
        inst._eye_gaze_task = nil
    end
    if inst._eye_blink_task ~= nil then
        inst._eye_blink_task:Cancel()
        inst._eye_blink_task = nil
    end
end

local function pick_next_eye_gaze(current)
    -- Prefer active directional glances (up/down/left/right) and avoid repeating the same pose back-to-back.
    local choices = {}
    for _, p in ipairs(EYE_GAZE_POSES) do
        if p ~= current then
            table.insert(choices, p)
            if p ~= "center" then
                table.insert(choices, p)
            end
        end
    end
    return choices[math.random(#choices)] or "center"
end

local schedule_eye_gaze
local schedule_eye_blink

schedule_eye_gaze = function(inst)
    if inst._eye_gaze_task ~= nil then
        inst._eye_gaze_task:Cancel()
    end
    inst._eye_gaze_task = inst:DoTaskInTime(1.5 + math.random() * 2.1, function()
        inst._eye_gaze_task = nil
        if not inst:IsValid() then return end
        local next_gaze = pick_next_eye_gaze(inst._eye_gaze)
        inst._eye_gaze = next_gaze
        if not inst._eye_blinking then
            apply_eye_pose(inst, next_gaze)
        end
        schedule_eye_gaze(inst)
    end)
end

schedule_eye_blink = function(inst)
    if inst._eye_blink_task ~= nil then
        inst._eye_blink_task:Cancel()
    end
    -- Occasional unhurried blink every 5.5 - 11.0 seconds.
    inst._eye_blink_task = inst:DoTaskInTime(5.5 + math.random() * 5.5, function()
        inst._eye_blink_task = nil
        if not inst:IsValid() then return end
        cancel_eye_blink_steps(inst)
        inst._eye_blinking = true
        apply_eye_pose(inst, "half_blink")
        local steps = {}
        inst._eye_blink_steps = steps
        steps[1] = inst:DoTaskInTime(0.045, function()
            if not inst:IsValid() or not inst._eye_blinking then return end
            apply_eye_pose(inst, "closed")
        end)
        steps[2] = inst:DoTaskInTime(0.165, function()
            if not inst:IsValid() or not inst._eye_blinking then return end
            apply_eye_pose(inst, "half_blink")
        end)
        steps[3] = inst:DoTaskInTime(0.210, function()
            inst._eye_blink_steps = nil
            inst._eye_blinking = false
            if not inst:IsValid() then return end
            if math.random() < 0.5 then
                inst._eye_gaze = pick_next_eye_gaze(inst._eye_gaze)
            end
            apply_eye_pose(inst, inst._eye_gaze or "center")
            schedule_eye_blink(inst)
        end)
    end)
end

local function start_eye_ai(inst)
    if not inst:IsValid() then return end
    stop_eye_ai(inst)
    inst._eye_gaze = inst._eye_gaze or "center"
    apply_eye_pose(inst, inst._eye_gaze)
    schedule_eye_gaze(inst)
    schedule_eye_blink(inst)
end

local function play_edge(fx, slot, phase, eye_pose)
    fx.AnimState:SetSymbolLightOverride("shiv_glint_" .. phase, glint_light[phase] or moonlight[phase])
    fx.AnimState:PlayAnimation(slot.clip .. phase, true)
    apply_eye_to_fx(fx, phase, eye_pose or "center")
end

local function show_weapon(owner, phase)
    -- The ring, wrapped grip, guard, eye and point are one owner-drawn sprite.
    -- The two native follower slots carry changing light, loose crystals and the living Phase Eye.
    owner.AnimState:OverrideSymbol("swap_object", BANK, "shiv_weapon_" .. phase)
    owner.AnimState:SetSymbolLightOverride("swap_object", moonlight[phase])
end

local function update_moon(inst)
    local state = TheWorld.state
    local phase = state[inst._moon_key] or "new"
    if phase ~= "new" and phase ~= "full" then
        phase = (state[inst._wax_key] and "waxing_" or "waning_") .. phase
    end
    if not moonlight[phase] then phase = "new" end
    if inst._moon == phase then return end
    inst._moon = phase
    inst.AnimState:SetSymbolLightOverride("shiv_planted_" .. phase, moonlight[phase])
    inst.AnimState:SetSymbolLightOverride("shiv_ground_glint_" .. phase, glint_light[phase] or moonlight[phase])
    inst.AnimState:PlayAnimation("ground_" .. phase, true)
    if inst._edge_owner ~= nil then
        show_weapon(inst._edge_owner, phase)
    end
    if inst._edges ~= nil then
        for i, fx in ipairs(inst._edges) do
            play_edge(fx, held_frames[i], phase, inst._eye_pose)
        end
    end
    apply_eye_pose(inst, inst._eye_pose or inst._eye_gaze or "center")
end

local function clear_followers(inst)
    local edges, owner = inst._edges, inst._edge_owner
    inst._edges = nil
    if edges ~= nil then
        for _, fx in ipairs(edges) do
            if fx:IsValid() then
                if owner ~= nil and owner:IsValid() and owner.components.colouradder ~= nil then
                    owner.components.colouradder:DetachChild(fx)
                end
                fx:Remove()
            end
        end
    end
end

local function remove_edges(inst)
    clear_followers(inst)
    local owner = inst._edge_owner
    if owner ~= nil then
        inst:RemoveEventCallback("onremove", inst._on_edge_owner_removed, owner)
        inst:RemoveEventCallback("onattackother", inst._on_owner_hit, owner)
        local inventory = owner:IsValid() and owner.components.inventory or nil
        local current = inventory ~= nil and inventory:GetEquippedItem(EQUIPSLOTS.HANDS) or nil
        if inventory ~= nil and (current == nil or current == inst) then
            owner.AnimState:ClearOverrideSymbol("swap_object")
            owner.AnimState:SetSymbolLightOverride("swap_object", 0)
        end
        inst._edge_owner = nil
    end
end

local function attach_edges(inst, owner)
    remove_edges(inst)
    local edges = {}
    inst._edges, inst._edge_owner = edges, owner
    inst:ListenForEvent("onremove", inst._on_edge_owner_removed, owner)
    -- This combat event follows the native hit-range test and precedes damage,
    -- destruction of the victim and Wili's existing weapon blink callback.
    inst:ListenForEvent("onattackother", inst._on_owner_hit, owner)
    show_weapon(owner, inst._moon)
    for i, slot in ipairs(held_frames) do
        local fx = SpawnPrefab(EDGE_FX)
        if fx == nil then
            clear_followers(inst)
            return
        end
        edges[i] = fx
        fx.entity:SetParent(owner.entity)
        fx.Follower:FollowSymbol(owner.GUID, "swap_object", nil, nil, nil, true, nil, slot.first, slot.stop)
        fx.components.highlightchild:SetOwner(owner)
        if owner.components.colouradder ~= nil then
            owner.components.colouradder:AttachChild(fx)
        end
        play_edge(fx, slot, inst._moon, inst._eye_pose)
    end
end

local function onequip(inst, owner)
    if owner.prefab ~= "wili" then
        if owner.components.talker then
            owner.components.talker:Say(STRINGS.CHARACTERS.WILI.ANNOUNCE_WILI_REJECTED)
        end
        owner:DoTaskInTime(0, function()
            local inv = owner.components.inventory
            if inv ~= nil and inv:GetEquippedItem(EQUIPSLOTS.HANDS) == inst then
                inv:Unequip(EQUIPSLOTS.HANDS)
                inv:GiveItem(inst)
            end
        end)
        return
    end

    attach_edges(inst, owner)
    start_eye_ai(inst)
    owner.AnimState:Show("ARM_carry")
    owner.AnimState:Hide("ARM_normal")
end

local function onunequip(inst, owner)
    remove_edges(inst)
    stop_eye_ai(inst)
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
local GEM_DROP_SOUND = "aqol/new_test/gem"

local function onattack(inst, owner, target)
    if not BlinkOnHit(inst, owner, target) then
        return
    end

    -- 宝石掉落逻辑
    if math.random() >= GEM_DROP_CHANCE then
        local gem_to_spawn = gem[math.random(#gem)]
        local pt = target:GetPosition()
        local st_pt = FindWalkableOffset(pt, math.random() * 2 * math.pi, GEM_OFFSET_RADIUS, GEM_OFFSET_ATTEMPTS)
        if st_pt then
            st_pt = st_pt + pt
            local st = SpawnPrefab(gem_to_spawn)
            if st ~= nil then
                st.Transform:SetPosition(st_pt.x, st_pt.y, st_pt.z)
                if st.SoundEmitter ~= nil then
                    st.SoundEmitter:PlaySound(PICKUPSOUNDS ~= nil and PICKUPSOUNDS[st.pickupsound or "gem"] or GEM_DROP_SOUND)
                end
            end
        end
    end
end

local function fn()
    local inst = CreateEntity()
    inst.entity:AddTransform()
    inst.entity:AddAnimState()
    inst.entity:AddSoundEmitter()
    inst.entity:AddNetwork()
    MakeInventoryPhysics(inst)

    inst.AnimState:SetBank(BANK)
    inst.AnimState:SetBuild(BANK)
    inst.AnimState:PlayAnimation("ground_new", true)

    inst:AddTag("sharp")
    inst.entity:SetPristine()

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

    local cave = TheWorld:HasTag("cave")
    inst._moon_key = cave and "cavemoonphase" or "moonphase"
    inst._wax_key = cave and "iscavewaxingmoon" or "iswaxingmoon"
    inst:WatchWorldState(inst._moon_key, update_moon)
    inst:WatchWorldState(inst._wax_key, update_moon)
    inst._on_edge_owner_removed = function()
        remove_edges(inst)
        if inst.components.inventoryitem == nil or inst.components.inventoryitem:IsHeld() then
            stop_eye_ai(inst)
        end
    end
    inst._on_owner_hit = function(owner, data) spawn_hit_fx(inst, owner, data) end
    update_moon(inst)
    start_eye_ai(inst)
    inst:ListenForEvent("onputininventory", function()
        if inst._edge_owner == nil then
            stop_eye_ai(inst)
        end
    end)
    inst:ListenForEvent("ondropped", function()
        remove_edges(inst)
        start_eye_ai(inst)
    end)
    inst:ListenForEvent("onremove", function()
        stop_eye_ai(inst)
        remove_edges(inst)
    end)
    inst.OnEntitySleep = function(ent)
        if ent._edge_owner == nil then
            stop_eye_ai(ent)
        end
    end
    inst.OnEntityWake = function(ent)
        if ent._edge_owner ~= nil or (ent.components.inventoryitem ~= nil and not ent.components.inventoryitem:IsHeld()) then
            start_eye_ai(ent)
        end
    end
    return inst
end

local function edge_fn()
    local inst = CreateEntity()
    inst.entity:AddTransform()
    inst.entity:AddAnimState()
    inst.entity:AddFollower()
    inst.entity:AddNetwork()
    inst:AddTag("FX")
    inst:AddTag("NOCLICK")
    inst.AnimState:SetBank(BANK)
    inst.AnimState:SetBuild(BANK)
    inst:AddComponent("highlightchild")
    inst.entity:SetPristine()
    if TheWorld.ismastersim then
        inst:AddComponent("colouradder")
        inst.persists = false
    end
    return inst
end

-- Client-side one-shot slash FX; only the impact position, direction, scale and phase are networked.
local function SpawnLocalHitFX(x, y, z, facing, phase, scale)
    local fx = CreateEntity()
    fx.entity:AddTransform()
    fx.entity:AddAnimState()
    fx.entity:SetCanSleep(false)
    fx:AddTag("FX")
    fx:AddTag("NOCLICK")
    fx.persists = false
    fx.Transform:SetPosition(x, y, z)
    fx.AnimState:SetBank(HIT_FX)
    fx.AnimState:SetBuild(HIT_FX)
    fx.AnimState:SetFinalOffset(1)
    fx.AnimState:SetLightOverride(hit_light[phase] or 0.5)

    -- Mirror horizontally when Wili strikes left-to-right on this client's screen
    -- so the crescent blade-current sweeps along the attack direction.
    local rad = facing * DEGREES
    local right = TheCamera ~= nil and TheCamera.GetRightVec ~= nil and TheCamera:GetRightVec() or nil
    local flip = right ~= nil and (math.cos(rad) * right.x - math.sin(rad) * right.z) > 0
    fx.AnimState:SetScale(flip and -scale or scale, scale)

    fx:ListenForEvent("animover", fx.Remove)
    fx.AnimState:PlayAnimation("hit_" .. phase)
end

local function PlayHitFX(inst)
    inst._play_pending = nil
    local phase_id = inst._phase:value()
    if phase_id == 0 or inst._played then
        return
    end
    local phase = MOON_PHASES[phase_id]
    if phase == nil then
        return
    end
    inst._played = true
    local x, y, z = inst.Transform:GetWorldPosition()
    local facing = inst.Transform:GetRotation()
    local raw_scale = inst._scale:value()
    local scale = raw_scale > 0 and (raw_scale / 50) or 1
    SpawnLocalHitFX(x, y, z, facing, phase, scale)
end

local function QueueHitFX(inst)
    if not inst._play_pending and not inst._played then
        inst._play_pending = inst:DoTaskInTime(0, PlayHitFX)
    end
end

local function SetupHitFX(inst, x, y, z, facing, phase, scale)
    inst.Transform:SetPosition(x, y, z)
    inst.Transform:SetRotation(facing)
    inst._scale:set(math.clamp(math.floor((scale or 1) * 50 + 0.5), 1, 255))
    inst._phase:set(MOON_PHASE_ID[phase] or 1)
    if not TheNet:IsDedicated() then
        QueueHitFX(inst)
    end
end

local function hit_fn()
    local inst = CreateEntity()
    inst.entity:AddTransform()
    inst.entity:AddNetwork()
    inst:AddTag("FX")
    inst:AddTag("NOCLICK")
    inst._scale = net_byte(inst.GUID, "wili_eclipse_hit_fx.scale")
    -- Zero until position, rotation and scale have been set.
    inst._phase = net_smallbyte(inst.GUID, "wili_eclipse_hit_fx.phase", "wilieclipsehitready")
    inst.entity:SetPristine()

    if not TheWorld.ismastersim then
        inst:ListenForEvent("wilieclipsehitready", QueueHitFX)
        QueueHitFX(inst)
        return inst
    end

    inst.persists = false
    inst.Setup = SetupHitFX
    inst:DoTaskInTime(1, inst.Remove)
    return inst
end

return Prefab("common/inventory/scimitar", fn, assets, { EDGE_FX, HIT_FX }),
       Prefab(EDGE_FX, edge_fn, edge_assets),
       Prefab(HIT_FX, hit_fn, hit_assets)
