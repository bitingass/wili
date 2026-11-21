-- Both Wili's scimitar and her other blink weapons call this on the server.
local MIN_TRAVEL = 2.5
local CONTACT_MARGIN = 0.75
local SOUND_INTERVAL = 0.40
local BLINK_SOUND = "wili_blink/sfx/blink"

local function BlinkOnHit(weapon, owner, target)
    if not TheWorld.ismastersim or not owner or not owner:IsValid()
        or not target or not target:IsValid() then
        return false
    end

    local x, y, z = owner.Transform:GetWorldPosition()
    local tx, ty, tz = target.Transform:GetWorldPosition()
    local facing = owner.Transform:GetRotation()
    owner.Transform:SetPosition(tx, ty, tz)

    -- Test the displacement for this hit, before a later swing can move the owner.
    -- A wide boss can put its centre several units from Wili even in contact.
    local dx, dz = tx - x, tz - z
    if owner.prefab ~= "wili" or dx * dx + dz * dz <= MIN_TRAVEL * MIN_TRAVEL then
        return true
    end
    local ex, ey, ez = owner.Transform:GetWorldPosition()
    dx, dz = ex - x, ez - z
    local threshold = math.max(MIN_TRAVEL, owner:GetPhysicsRadius(0) + target:GetPhysicsRadius(0) + CONTACT_MARGIN)
    if dx * dx + dz * dz <= threshold * threshold then
        return true
    end

    local trail = SpawnPrefab("wili_blink_trail")
    if trail then
        trail:SetRoute(x, y, z, dx, ey - y, dz, facing, weapon.prefab == "scimitar")
    end

    local now = GetTime()
    if owner.SoundEmitter and now >= (owner._wili_next_blink_sound or 0) then
        owner._wili_next_blink_sound = now + SOUND_INTERVAL
        owner.SoundEmitter:PlaySound(BLINK_SOUND)
    end
    return true
end

return BlinkOnHit
