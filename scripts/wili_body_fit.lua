local BODY_BANK = "wili_body_fit"
local native = hash("wilson")
local fitted = hash(BODY_BANK)

local function select_body(inst)
    if inst.AnimState:GetBankHash() == native then
        inst.AnimState:SetBank(BODY_BANK)
        return true
    end
end

local function common_init(inst)
    -- player_common sets the default bank before the character's common init,
    -- and installs the stategraph later. The first pose can use our bank too.
    select_body(inst)
    inst:ListenForEvent("dismounted", select_body)
end

local function master_init(inst)
    -- Revival and skin refresh both call this public player hook. Let native
    -- ghost, mount and other special skins keep any bank the game selected.
    local apply_skin = inst.ApplySkinOverrides
    inst.ApplySkinOverrides = function(player, ...)
        apply_skin(player, ...)
        select_body(player)
    end
end

local function restore_on_exit(state)
    if state == nil then return end
    local leave = state.onexit
    state.onexit = function(inst, ...)
        if leave then leave(inst, ...) end
        if inst.prefab == "wili" then select_body(inst) end
    end
end

local function restore_chair_animation(state, name)
    if state == nil then return end
    local enter = state.onenter
    state.onenter = function(inst, ...)
        enter(inst, ...)
        -- These two chair transitions explicitly select the Wilson bank AND
        -- start a single clip. All native physics and timing have already run.
        if inst.prefab == "wili" and inst.sg.currentstate == state and inst.AnimState:IsCurrentAnimation(name) then
            local time = inst.AnimState:GetCurrentAnimationTime()
            if select_body(inst) then
                inst.AnimState:PlayAnimation(name)
                inst.AnimState:SetTime(time)
            end
        end
    end
end

local function install(sg)
    for _, name in ipairs({"sit_jumpon", "sitting", "stop_sitting", "sit_jumpoff"}) do
        restore_on_exit(sg.states[name])
    end
    restore_chair_animation(sg.states.sit_jumpoff, "sit_jump_off")
    restore_chair_animation(sg.states.stop_sitting_pst, "sit_off_pst")
end

local function is_player_bank(bank)
    return bank == native or bank == fitted
end

return { common_init = common_init, master_init = master_init, install = install, is_player_bank = is_player_bank }
