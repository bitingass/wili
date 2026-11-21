local BANK = "wili_blink_afterimage"
local assets = {
    Asset("ANIM", "anim/wili_blink_afterimage.zip"),
    Asset("SOUNDPACKAGE", "sound/wili_blink.fev"),
    Asset("SOUND", "sound/wili_blink_bank.fsb"),
}

-- These silhouettes are local, short-lived drawings. Only the route is networked.
local function SpawnAfterimage(x, y, z, facing, clip, opacity)
    local echo = CreateEntity()
    echo.entity:AddTransform()
    echo.entity:AddAnimState()
    echo.entity:SetCanSleep(false)
    echo:AddTag("FX")
    echo:AddTag("NOCLICK")
    echo.persists = false
    echo.Transform:SetFourFaced()
    echo.Transform:SetPosition(x, y, z)
    echo.Transform:SetRotation(facing)
    echo.AnimState:SetBank(BANK)
    echo.AnimState:SetBuild(BANK)
    echo.AnimState:SetMultColour(1, 1, 1, opacity)
    echo:ListenForEvent("animover", echo.Remove)
    echo.AnimState:PlayAnimation(clip)
end

local function DrawTrail(inst)
    inst._draw_pending = nil
    local kind = inst._kind:value()
    if kind == 0 or inst._drawn then
        return
    end
    inst._drawn = true
    local x, y, z = inst.Transform:GetWorldPosition()
    local facing = inst.Transform:GetRotation()
    local dx, dy, dz = inst._dx:value(), inst._dy:value(), inst._dz:value()
    local count = dx * dx + dz * dz >= 25 and 3 or 2
    local clip = kind == 2 and "blink_scimitar" or "blink"
    for i = 0, count - 1 do
        local along = i / count
        SpawnAfterimage(x + along * dx, y + along * dy, z + along * dz,
            facing, clip, 0.60 + 0.36 * i / (count - 1))
    end
end

local function QueueTrail(inst)
    if not inst._draw_pending and not inst._drawn then
        inst._draw_pending = inst:DoTaskInTime(0, DrawTrail)
    end
end

local function SetRoute(inst, x, y, z, dx, dy, dz, facing, scimitar)
    inst.Transform:SetPosition(x, y, z)
    inst.Transform:SetRotation(facing)
    inst._dx:set(dx)
    inst._dy:set(dy)
    inst._dz:set(dz)
    inst._kind:set(scimitar and 2 or 1)
    if not TheNet:IsDedicated() then
        QueueTrail(inst)
    end
end

local function fn()
    local inst = CreateEntity()
    inst.entity:AddTransform()
    inst.entity:AddNetwork()
    inst.Transform:SetFourFaced()
    inst:AddTag("FX")
    inst:AddTag("NOCLICK")
    inst._dx = net_float(inst.GUID, "wili_blink_trail.dx")
    inst._dy = net_float(inst.GUID, "wili_blink_trail.dy")
    inst._dz = net_float(inst.GUID, "wili_blink_trail.dz")
    -- Zero until the origin, rotation and all offsets have been set.
    inst._kind = net_tinybyte(inst.GUID, "wili_blink_trail.kind", "wilitrailready")
    inst.entity:SetPristine()

    if not TheWorld.ismastersim then
        inst:ListenForEvent("wilitrailready", QueueTrail)
        QueueTrail(inst)
        return inst
    end

    inst.persists = false
    inst.SetRoute = SetRoute
    inst:DoTaskInTime(1, inst.Remove)
    return inst
end

return Prefab("wili_blink_trail", fn, assets)
