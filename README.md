## 饥荒联机版角色Wili

月影刺客葳丽（Wili）的饥荒联机版人物 Mod。

## 1.2.3 更新日志（2026-10-27）

- 银月弯刀采用冷银与深墨蓝配色，中央残月的暗面由暗色宝石薄片紧密拼接；手持、地面和物品栏使用同一张设计源图。
- 地面动画改用独立的 `scimitar` 动画库并覆盖所有朝向，校准刀尖接地位置，修正旧资源可能在部分朝向不显示的问题。
- 根据游戏截图反馈，将手持武器放大 35%、地面武器放大 65%，保持握点和接地点；地面单独加入原版法杖使用的手绘线条部件，增强贴地感。
- 地面姿势进一步改为下段约三分之一刀身入土：隐藏地面以下的刀身，将宽截面与接地线条居中对齐，手持大小不变。
- 简化刀面与缠柄的细碎纹理、加强墨线和大色块，保留残月及暗色宝石拼花，提高游戏内辨识度。
- 已完成贴图编译、动画引用、握点与接地位置检查；最终插地姿势仍待游戏内复测。

## 1.2.2 更新日志（2026-10-23）

- 修复正面面罩、侧面下巴、后脑发梢及特殊表情下颌的横向截断：原稿第一排头部越过了两行等分的切片边界。
- 从现有原稿恢复缺失末端，保持原有五官、头发的像素位置及缩放；戴帽头部不变。
- 已校验源图与编译资源，待游戏内复测。复现方法见 [美术说明](art/说明.txt)。

## 1.2.1 更新日志（2026-10-21）

- 重制月下刺客造型，更新角色动画部件、幽灵、头像、立绘、选人页、存档页、小地图和 Mod 图标。
- 银月弯刀采用反握造型，手持、地面及物品栏图标使用一致的刀形。
- 修正五官与面罩中线偏移、侧眼朝向和多余鼻线，并校正戴帽及特殊表情贴图。
- 清理旧稿、重复解包、测试输出和备份；当前可编辑源图保存在 `art/source`，打包工具保存在 `art/tools`，使用方法见 [美术说明](art/说明.txt)。
- 新美术及面部修复已于 2026-10-20 完成用户游戏内测试；源图重建结果与运行资源内容一致。本次更新保持人物能力不变。

## 1.2.0 更新日志（2026-10-17）

### 战斗与防御

- 攻速加成固定为 1.5 倍，仅对葳丽生效，其他人物不再受影响。
- 移速统一为 2.25 倍，出生、读档和复活后保持一致。
- “复仇”的无敌触发概率可在 Mod 设置中选择：0%–100%，每档 1%，默认 13%；每次触发持续 13 秒。
- 无敌期间，穿戴的护甲、头盔等防具不因受击损失耐久，中途换装同样生效；无敌结束后恢复正常损耗。触发无敌的第一击仍正常结算，武器主动攻击的耐久消耗及装备随时间消耗的燃料不受影响。
- 普通受击不再产生硬直，并免疫攻击造成的击退、击飞和击倒，覆盖梦魇疯猪的飞扑与砸地。伤害及无敌触发仍正常结算；电击麻痹、睡眠唤醒，以及被吞噬或悬挂后的脱身流程保留原机制。
- 银月弯刀加入秒杀白名单，保留原有瞬移、攻击距离和宝石生成效果。

### 黑蓝夜视

- 将人物的大范围光源改为鼹鼠帽同类的个人夜视，采用偏暗的黑蓝色，最终颜色值为 RGB `(0.16, 0.29, 0.60)`。
- 地表仅在黑夜（含满月）自动启用；白天和黄昏保持原版画面，不叠加颜色。洞穴中全天启用。
- 夜视只影响葳丽自己的画面，不为队友提供照明；生效时保留原版查理免疫。死亡后使用原生幽灵视野，复活后根据所在环境恢复。

### 台词与语言

- 取消进入暗处、明处时的 “It's so dark!” 和 “I can see again!” 两句自动提示，保留其他台词。
- 检查和普通台词继承当前游戏的完整译文，角色、技能及专武的专属文本支持简体中文、繁体中文和英文。
- 联机台词遵循原版规则：由房主／服务器的游戏语言决定并原样广播，客户端不单独翻译，玩家手打聊天保持原样。
- 移除新增的 `wili_localization` 模块依赖，修复替换 Mod 文件后因找不到该模块而无法启动的问题。

### 性能与状态恢复

- 攻速状态监听仅注册给葳丽；及时清理计时任务，结束或中断攻击后只恢复一次动画速度与攻击间隔。
- 装备处理仅响应手持槽变化，并正确保存、恢复武器原始攻击回调及攻击距离，避免戴帽子或换护甲时重复修改武器。
- 碰撞设置只在需要变化时写入，秒杀白名单改为直接查表；保留原名单与随机判定顺序。
- 移除温度更新中的重复光源设置，夜视改为随环境及角色状态变化更新。

本版已进行 Lua 5.1 语法检查和模拟回归检查，尚未完成游戏内实测及帧率测量。

## 历史更新

最近上船之后发现想杀点水蜘蛛真的很折磨（按一下f就落水，破防了），所以给人物添加了水上行走~

先前更新：
在mod设置中添加了对秒杀武器秒杀和宝石掉落的概率（可选择4个档位，可以关闭了现在，二者概率可分别自定义）
修复了一些可以瞬移武器的特效和音效不显示问题（因为一个遗留的屎山）
修复了暗影槌的升级效果，此前不会触发
现在wili可以直接制作暗影/月亮相关道具（绝望石、纯粹恐惧、暗影碎布、月石、(注能)月亮碎片、纯粹辉煌）
优化了所有的随机概率
修复了舞台剧佩戴面具会崩溃的bug,
目前人物在攻击方面的属性过强，已将可触发瞬移和秒杀的近战攻击武器限制在：与暗影/月亮有关的近战武器（以及专武）

这个mod的源作者不是我，原作者为
代码部分 作者：七夜大师 邮箱：826010478@qq.com
美工部分 作者：INN 邮箱：774045241@qq.com，我只是在原版的基础上重构了代码将其移植过来并对人物的技能做了一些修改，该操作以经过美工以及代码作者许可，以下是人物介绍：

This mod is not designed originally by me, I rewrite the code and plant the mod to DST and modify some ability to
correspond to character description.

This second-modify has been Authorized by both of the original code contributor and character artist
---------------------------------------------------------------------------

Original Author's words:
If it's crash when chose character. Please close Small Textures.
English is not my first language, so if you can not understand Wili's features, just point it out.
Code part made by Nanaya Master. Email:826010478@qq.com
Art part made by INN. Email:774045241@qq.com

Mod Name:Moon Shadow Assassin

Name:Wili
----------------------------------------------------------------------------

Wili come from a female assassin Alliance.
She come here because she was framed by friends.

health:88
hungry:132
sanity:176
attack-muti: 2.0
attack speed:1.5 (Wili only)
move speed:2.25

1. Wili has a configurable chance to instantly kill enemies, including bosses, when attacking with eligible shadow/moon melee weapons or her Silver Moon Scimitar.
2. Wili can blink to the target when attacking with those weapons.
3. Revenge grants 13 seconds of invincibility after being attacked. Its trigger chance is configurable from 0% to 100% in 1% steps, with a default of 13%. While invincible, worn armour and helmets do not lose durability from incoming hits; the triggering hit still consumes durability normally.
4. Personal dark-blue night vision activates during surface night (including full moons) and at all times in caves. Surface day and dusk keep their normal colours. It does not illuminate the world for other players. Ghost vision remains unchanged, and night vision resumes after resurrection.
5. Ordinary hits do not interrupt Wili, and combat knockback and knockdown are prevented. Damage is still applied normally; electric stun, waking from sleep, and escape from swallowing or suspension retain their normal behaviour.
6. Wili's sanity reduces very slowly, but picking flowers does not restore sanity.
7. Wili's temperature changes twice as quickly as other characters, but she takes less damage from overheating and freezing.
8. Wili cannot befriend pigmen, bunnymen or rock lobsters, or pick up Chester's Eye Bone or Hutch's Star-Sky.

she is very known about the shadow and the moon, can build the shadow/moon material directly

Exclusive Weapon:Silver Moon Scimitar
damage:44
1.The scimitar has a configurable chance to produce a gem on attack (4% by default). It also supports Wili's configured instant-kill chance.
2.It will never be damaged.




mod名：月影刺客

简介：葳丽13岁便加入了一个均为女性的刺客组织，15岁她第一次杀人。随着葳丽完成了一个又一个的暗杀任务，她在刺客组织中的地位也水涨船高。
就在葳丽计划完成这次任务就解甲归田之时，意外发生了，葳丽被组织人员联合设计来到了这个充满未知的世界——饥荒。

属性：
生命：88
饥饿：132
神志：176
攻击力倍率：2.0
攻击速度：1.5 倍（仅葳丽）
移动速度：2.25

技能：
1.恩赐解脱
葳丽擅长抓住敌人的弱点。
使用白名单内的暗影／月亮近战武器或银月弯刀攻击时，有几率秒杀敌人，包括 BOSS；概率由 Mod 设置决定。
2.突袭
葳丽可以出其不意的攻击敌人。
当使用白名单内的月亮／暗影近战武器或银月弯刀攻击时，可以瞬间移动到敌方单位身边，突袭距离为回旋镖的距离。原版武器卸下后恢复原始攻击距离，银月弯刀保留自身射程。
3.复仇
当葳丽受到攻击时，有设定概率开启持续 13 秒的无敌。触发概率可选 0%–100%，每档 1%，默认 13%。无敌期间穿戴防具受击不掉耐久；触发无敌的第一击仍正常结算，主动攻击的武器耐久与随时间消耗的燃料不受影响。
4.夜行者
葳丽更爱在黑暗中杀人，她在夜晚可以看清周围的环境。
鼹鼠帽式夜视：地表黑夜（含满月）及洞穴中自动启用黑蓝色夜视，地表白天和黄昏不加滤镜。仅影响葳丽自己的画面，不为队友提供照明。夜视生效时保留原版查理免疫；死亡使用原生幽灵视野，复活后自动恢复。
5.成熟
没有什么事情能让葳丽感到害怕和高兴。
夜晚神志下降速度为0.1，与怪物战斗神志下降速度为0.1，捡花不恢复神志。
6.冷血者
葳丽为了隐藏自己，防止被敌人发现，她可以更快的融入环境。
其体温变化速率是正常人的两倍。但是在酷暑和严寒中受到的伤害会有所降低。
7.孤独
葳丽在被陷害之后，便不再相信任何人。能和她做朋友的必然有非凡之处。
即使葳丽给猪人、兔人、石虾喂食物，也不会和它们成为朋友。葳丽无法捡起切斯特的眼骨和星空

8.受击保护
普通受击不会产生硬直，免疫攻击造成的击退、击飞和击倒；伤害仍正常结算。电击、睡眠唤醒与被吞噬或悬挂后的脱身流程保留原机制。

现在wili可以直接制作暗影/月亮相关道具


专属武器：银月弯刀
在暗杀一名炼金术士的过程中，葳丽发现这把弯刀，银月弯刀由人的灵魂和稀有的材料锻造而成。
这把武器可以在接触鲜血的过程中凝练宝石，并修复武器的磨损。
攻击力：44
攻击时有几率随机掉落一颗宝石（包括彩虹宝石），默认 4%，可在 Mod 设置中调整；葳丽使用时也可按设定概率触发秒杀。
开局自带，永不磨损

选人崩溃请关掉纹理细节设置，并重启游戏。
