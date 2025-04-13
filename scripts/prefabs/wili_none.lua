local assets =
{
	Asset( "ANIM", "anim/wili.zip" ),
	Asset( "ANIM", "anim/ghost_wili_build.zip" ),
}

local skins =
{
	normal_skin = "wili",
	ghost_skin = "ghost_wili_build",
}

return CreatePrefabSkin("wili_none",
{
	base_prefab = "wili",
	-- type = "base",
	assets = assets,
	skins = skins, 
	skin_tags = {"WILI", "CHARACTER", "BASE"},
	build_name_override = "wili",
	rarity = "Character",
})