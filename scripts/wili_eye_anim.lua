-- Client-side silky idle eye controller for Wili.
-- Keeps Wili's pupils centered during normal play (walking, running, combat)
-- and adds smooth multi-step left/right glances (5 horizontal gaze positions)
-- and 30 FPS 3-stage hand-drawn blinks while standing idle.

local EYE_BUILD = "wili_eye_anim"
local TICK_INTERVAL = 0.10
local IDLE_START_DELAY = 0.85
local GLIDE_STEP_DT = 0.036

-- Ordered left (-2) -> center (0) -> right (+2) for smooth multi-step gliding
local GAZE_SYMS = {
    [-2] = "face_look_left",
    [-1] = "face_mid_left",
    [ 0] = "face_center",
    [ 1] = "face_mid_right",
    [ 2] = "face_look_right",
}

local function rand_range(lo, hi)
    return lo + math.random() * (hi - lo)
end

local function apply_face(inst, sym)
    if inst._wili_eye_sym == sym then
        return
    end
    inst._wili_eye_sym = sym
    if sym == nil then
        inst.AnimState:ClearOverrideSymbol("face")
    else
        inst.AnimState:OverrideSymbol("face", EYE_BUILD, sym)
    end
end

local function cancel_anim_tasks(inst)
    if inst._wili_blink_tasks ~= nil then
        for _, task in ipairs(inst._wili_blink_tasks) do
            task:Cancel()
        end
        inst._wili_blink_tasks = nil
    end
    if inst._wili_glide_tasks ~= nil then
        for _, task in ipairs(inst._wili_glide_tasks) do
            task:Cancel()
        end
        inst._wili_glide_tasks = nil
    end
    inst._wili_eye_blinking = false
    inst._wili_eye_gliding = false
end

local function glide_gaze_to(inst, target_idx)
    if inst._wili_glide_tasks ~= nil then
        for _, task in ipairs(inst._wili_glide_tasks) do
            task:Cancel()
        end
        inst._wili_glide_tasks = nil
    end
    local cur_idx = inst._wili_eye_idx or 0
    if cur_idx == target_idx then
        inst._wili_eye_gliding = false
        apply_face(inst, GAZE_SYMS[target_idx] or "face_center")
        return
    end

    local step = target_idx > cur_idx and 1 or -1
    local steps = {}
    local idx = cur_idx
    while idx ~= target_idx do
        idx = idx + step
        table.insert(steps, idx)
    end

    inst._wili_eye_gliding = true
    local tasks = {}
    inst._wili_glide_tasks = tasks
    for i, next_idx in ipairs(steps) do
        local is_last = (i == #steps)
        local delay = (i - 1) * GLIDE_STEP_DT
        if delay <= 0 then
            inst._wili_eye_idx = next_idx
            if not inst._wili_eye_blinking then
                apply_face(inst, GAZE_SYMS[next_idx] or "face_center")
            end
            if is_last then
                inst._wili_eye_gliding = false
                inst._wili_glide_tasks = nil
            end
        else
            tasks[#tasks + 1] = inst:DoTaskInTime(delay, function()
                if not inst:IsValid() or inst:HasTag("playerghost") or not inst._wili_eye_gliding then return end
                inst._wili_eye_idx = next_idx
                if not inst._wili_eye_blinking then
                    apply_face(inst, GAZE_SYMS[next_idx] or "face_center")
                end
                if is_last then
                    inst._wili_eye_gliding = false
                    inst._wili_glide_tasks = nil
                end
            end)
        end
    end
end

local function start_blink(inst, on_done)
    cancel_anim_tasks(inst)
    inst._wili_eye_blinking = true
    apply_face(inst, "face_blink_1")
    local tasks = {}
    inst._wili_blink_tasks = tasks

    -- 30 FPS 6-stage silky eyelid close & open (blink_1 -> blink_2 -> blink_3 -> blink_2 -> blink_1 -> open)
    tasks[1] = inst:DoTaskInTime(0.033, function()
        if not inst:IsValid() or inst:HasTag("playerghost") or not inst._wili_eye_blinking then return end
        apply_face(inst, "face_blink_2")
    end)
    tasks[2] = inst:DoTaskInTime(0.066, function()
        if not inst:IsValid() or inst:HasTag("playerghost") or not inst._wili_eye_blinking then return end
        apply_face(inst, "face_blink_3")
    end)
    tasks[3] = inst:DoTaskInTime(0.132, function()
        if not inst:IsValid() or inst:HasTag("playerghost") or not inst._wili_eye_blinking then return end
        apply_face(inst, "face_blink_2")
    end)
    tasks[4] = inst:DoTaskInTime(0.165, function()
        if not inst:IsValid() or inst:HasTag("playerghost") or not inst._wili_eye_blinking then return end
        apply_face(inst, "face_blink_1")
    end)
    tasks[5] = inst:DoTaskInTime(0.198, function()
        if not inst:IsValid() then return end
        inst._wili_blink_tasks = nil
        inst._wili_eye_blinking = false
        if inst:HasTag("playerghost") then
            apply_face(inst, nil)
            return
        end
        if on_done ~= nil then
            on_done()
        else
            apply_face(inst, GAZE_SYMS[inst._wili_eye_idx or 0] or "face_center")
        end
    end)
end

local function pick_next_gaze(inst)
    local cur = inst._wili_eye_target or 0
    if cur == 0 then
        local last_side = inst._wili_eye_last_side
        local next_side
        if last_side == -2 then
            next_side = math.random() < 0.78 and 2 or -2
        elseif last_side == 2 then
            next_side = math.random() < 0.78 and -2 or 2
        else
            next_side = math.random() < 0.5 and -2 or 2
        end
        inst._wili_eye_last_side = next_side
        return next_side, rand_range(1.1, 2.2)
    else
        -- Either return smoothly to center (65%) or sweep directly across to the opposite side (35%)
        if math.random() < 0.65 then
            return 0, rand_range(1.4, 3.0)
        end
        local opp = (cur < 0) and 2 or -2
        inst._wili_eye_last_side = opp
        return opp, rand_range(1.0, 2.0)
    end
end

local function on_tick(inst)
    if not inst:IsValid() then
        return
    end
    if inst:HasTag("playerghost") then
        cancel_anim_tasks(inst)
        inst._wili_idle_time = 0
        inst._wili_eye_idx = 0
        inst._wili_eye_target = 0
        apply_face(inst, nil)
        return
    end

    local is_idle = inst.AnimState:IsCurrentAnimation("idle_loop")
    local now = GetTime()

    if not is_idle then
        cancel_anim_tasks(inst)
        inst._wili_idle_time = 0
        inst._wili_eye_idx = 0
        inst._wili_eye_target = 0
        inst._wili_next_gaze_t = nil
        inst._wili_next_blink_t = nil
        apply_face(inst, "face_center")
        return
    end

    inst._wili_idle_time = (inst._wili_idle_time or 0) + TICK_INTERVAL
    if inst._wili_idle_time < IDLE_START_DELAY then
        if not inst._wili_eye_blinking then
            apply_face(inst, "face_center")
        end
        return
    end

    if inst._wili_next_gaze_t == nil then
        inst._wili_next_gaze_t = now + rand_range(0.6, 1.5)
    end
    if inst._wili_next_blink_t == nil then
        inst._wili_next_blink_t = now + rand_range(1.8, 3.8)
    end

    if inst._wili_eye_blinking or inst._wili_eye_gliding then
        return
    end

    if now >= inst._wili_next_blink_t then
        local double_blink = math.random() < 0.18
        inst._wili_next_blink_t = now + (double_blink and 0.36 or rand_range(3.0, 6.0))
        start_blink(inst)
        return
    end

    if now >= inst._wili_next_gaze_t then
        local next_target, hold = pick_next_gaze(inst)
        inst._wili_eye_target = next_target
        inst._wili_next_gaze_t = now + hold
        -- Occasionally blink naturally right as the gaze sweeps across
        if math.random() < 0.22 then
            inst._wili_next_blink_t = now + rand_range(3.0, 5.8)
            start_blink(inst, function()
                inst._wili_eye_idx = next_target
                apply_face(inst, GAZE_SYMS[next_target] or "face_center")
            end)
        else
            glide_gaze_to(inst, next_target)
        end
    else
        apply_face(inst, GAZE_SYMS[inst._wili_eye_idx or 0] or "face_center")
    end
end

local function install(inst)
    if TheNet ~= nil and TheNet:IsDedicated() then
        return
    end
    inst._wili_eye_idx = 0
    inst._wili_eye_target = 0
    inst._wili_idle_time = 0
    if not inst:HasTag("playerghost") then
        apply_face(inst, "face_center")
    end
    inst._wili_eye_tick = inst:DoPeriodicTask(TICK_INTERVAL, on_tick)
    inst:ListenForEvent("ms_respawnedfromghost", function()
        inst._wili_eye_sym = nil
        inst._wili_eye_idx = 0
        inst._wili_eye_target = 0
        if inst:IsValid() and not inst:HasTag("playerghost") then
            apply_face(inst, "face_center")
        end
    end)
    inst:ListenForEvent("onremove", function()
        cancel_anim_tasks(inst)
        if inst._wili_eye_tick ~= nil then
            inst._wili_eye_tick:Cancel()
            inst._wili_eye_tick = nil
        end
    end)
end

return {
    BUILD = EYE_BUILD,
    install = install,
}
