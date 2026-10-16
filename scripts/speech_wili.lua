-- Inherit the current game's translated speech instead of an outdated English copy.
-- Native talker:Say broadcasts the server's text unchanged to connected clients.
local function CopySpeech(source)
    local copy = {}
    for key, value in pairs(source) do
        copy[key] = type(value) == "table" and CopySpeech(value) or value
    end
    return copy
end

local speech = CopySpeech(STRINGS.CHARACTERS.GENERIC)
local language = LOC.GetLocaleCode()
local function LocalizedText(english, simplified, traditional)
    return language == "zht" and traditional or
               (language == "zh" or language == "zhr") and simplified or english
end

speech.ANNOUNCE_WILI_REVENGE = LocalizedText("Time To Revenge!", "反击的时候到了！", "反擊的時候到了！")
speech.ANNOUNCE_WILI_COUP_DE_GRACE = LocalizedText("Give you relief!", "给你一个解脱！", "給你一個解脫！")
speech.ANNOUNCE_WILI_NO_FOLLOWERS = LocalizedText("no follower I need", "我不需要追随者。", "我不需要追隨者。")
speech.ANNOUNCE_WILI_REJECTED = LocalizedText("get rejected", "它拒绝了我。", "它拒絕了我。")
speech.DESCRIBE.SCIMITAR = LocalizedText("Source of wealth!", "财富之源！", "財富之源！")

return speech
