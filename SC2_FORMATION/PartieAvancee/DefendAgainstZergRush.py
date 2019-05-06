import sc2
from sc2 import run_game, maps, Race, Difficulty, position, Result
from sc2.player import Bot, Computer, Human
from sc2.constants import SCV, COMMANDCENTER, REFINERY, SUPPLYDEPOT, BARRACKS, MARINE, BARRACKSTECHLAB, \
    SUPPLYDEPOTLOWERED, MORPH_SUPPLYDEPOT_LOWER, MORPH_SUPPLYDEPOT_RAISE, SMART, BARRACKSREACTOR, FACTORYREACTOR, \
    STARPORTREACTOR, REACTOR, FACTORYTECHLAB, STARPORTTECHLAB, TECHLAB

from SC2_FORMATION.PartieAvancee import BotZerg
import random


class BotTerran(sc2.BotAI):

    def __init__(self):

        self.attacking = False
        self.attacking_units = []
        self.defend_base = False

    async def on_step(self, iteration):
        """
        Choose an action to do for this step in the game.

        :param iteration: in game iteration number. There are approximately 165 iteration per minute.
        :return: execute an action.
        """

        # This a a function of sc2 Bot So we don't need to create the complex function that manages the workers.
        await self.distribute_workers()

        await self.build_workers()

        await self.ramp_wall_build()
        await self.manage_supply_depot()
        await self.supply_depots()
        await self.build_refineries()

        await self.finish_repair_building()
        await self.repair_damage_building()

        await self.expand()

        await self.build_barracks()
        await self.create_army()

        # /!\ The order is really important !!! first attack and then defend !!!

        await self.attack()

        await self.defend()

    async def build_workers(self):

        if self.units(SCV).amount < self.units(COMMANDCENTER).amount*16:
            for command_center in self.units(COMMANDCENTER).ready.noqueue:
                if self.can_afford(SCV):
                    await self.do(command_center.train(SCV))

    async def ramp_wall_build(self):
        """
        Build a ramp wall to avoid early enemy_attack.
        ==> code taken from https://github.com/Dentosal/python-sc2/blob/master/examples/terran/ramp_wall.py it has been
        slightly modified to work here.

        :return: a wall ramp constituted of a barrack and 2 supply depots.
        """
        depot_placement_positions = self.main_base_ramp.corner_depots
        # Uncomment the following if you want to build 3 supplydepots in the wall instead of a barracks in the middle +
        # 2 depots in the corner
        depot_placement_positions = self.main_base_ramp.corner_depots | {self.main_base_ramp.depot_in_middle}

        barracks_placement_position = None
        # barracks_placement_position = self.main_base_ramp.barracks_correct_placement
        # If you prefer to have the barracks in the middle without room for addons, use the following instead
        # barracks_placement_position = self.main_base_ramp.barracks_in_middle

        supply_depots = self.units(SUPPLYDEPOT) | self.units(SUPPLYDEPOTLOWERED)

        # Filter locations close to finished supply depots
        if supply_depots:
            depot_placement_positions = {d for d in depot_placement_positions if supply_depots.closest_distance_to(d) > 1}

        # Build depots
        if self.can_afford(SUPPLYDEPOT) and not self.already_pending(SUPPLYDEPOT):
            if len(depot_placement_positions) == 0:
                return
            # Choose any depot location
            target_depot_location = depot_placement_positions.pop()
            ws = self.workers.gathering
            if ws:  # if workers were found
                w = ws.random
                await self.do(w.build(SUPPLYDEPOT, target_depot_location))

        # Build barracks
        if supply_depots.ready.exists and self.can_afford(BARRACKS) and not self.already_pending(BARRACKS):
            if self.units(BARRACKS).amount + self.already_pending(BARRACKS) > 0:
                return
            ws = self.workers.gathering
            if ws and barracks_placement_position:  # if workers were found
                w = ws.random
                await self.do(w.build(BARRACKS, barracks_placement_position))

    async def manage_supply_depot(self):
        """
        Raise a depot if enemy nearby, lower it else.
        :return:
        """

        if self.defend_base:
            for supply_depot in self.units(SUPPLYDEPOT).ready:
                await self.do(supply_depot(MORPH_SUPPLYDEPOT_LOWER))

        else:
            # Raise depos when enemies are nearby
            for supply_depot in self.units(SUPPLYDEPOT).ready:
                enemy_nearby = False
                for unit in self.known_enemy_units.not_structure:
                    if unit.position.to2.distance_to(supply_depot.position.to2) < 10:
                        enemy_nearby = True

                if not enemy_nearby:
                    await self.do(supply_depot(MORPH_SUPPLYDEPOT_LOWER))

            # Lower depos when no enemies are nearby
            for supply_depot in self.units(SUPPLYDEPOTLOWERED).ready:
                for unit in self.known_enemy_units.not_structure:
                    if unit.position.to2.distance_to(supply_depot.position.to2) < 10:
                        await self.do(supply_depot(MORPH_SUPPLYDEPOT_RAISE))
                        break

    async def supply_depots(self):

        # supply_left = how many population can I produce more.
        if self.supply_left < 5 and not self.already_pending(SUPPLYDEPOT):
            command_centers = self.units(COMMANDCENTER).ready  # a command center that already exists
            if command_centers.exists:
                if self.can_afford(SUPPLYDEPOT):
                    await self.build(SUPPLYDEPOT, near=command_centers.first)  # specify build + where.

    async def build_refineries(self):

        for command_center in self.units(COMMANDCENTER).ready:
            vaspenes = self.state.vespene_geyser.closer_than(15.0, command_center)  # tells us where the geysers are.
            for vaspene in vaspenes:
                if not self.can_afford(REFINERY):
                    break
                worker = self.select_build_worker(vaspene.position)
                if worker is None:
                    break
                if not self.units(REFINERY).closer_than(1.0, vaspene).exists:  # if there is not a refinery that exists
                    # close to that vaspene already,
                    await self.do(worker.build(REFINERY, vaspene))

    async def finish_repair_building(self):
        """
        If a scv dies while constructing a building, another scv will be sent to finish it. big problem before because
        a supply was never finished, no other would never have been build.
        :return:
        """

        REACTORS = {BARRACKSREACTOR, FACTORYREACTOR,
                    STARPORTREACTOR, REACTOR}

        TECHLABS = {BARRACKSTECHLAB, FACTORYTECHLAB,
                    STARPORTTECHLAB, TECHLAB}

        TECHLABS_AND_REACTORS = REACTORS.union(TECHLABS)

        scv_constructing = self.units.filter(lambda unit: unit.is_constructing_scv)

        scv_tags = {scv.add_on_tag for scv in scv_constructing}

        if self.units.structure.not_ready.exclude_type(TECHLABS_AND_REACTORS).amount > scv_constructing.amount:

            for building in self.units.structure.not_ready.exclude_type(TECHLABS_AND_REACTORS):

                if building.name != 'BarracksTechLab':  # reaper grenades are structure.

                    if self.units(SCV).amount > 0:

                        if building.add_on_tag not in scv_tags:
                            scv = self.units(SCV).ready.random
                            await self.do(scv(SMART, building))

    async def repair_damage_building(self):

        scv_constructing = self.units.filter(lambda unit: unit.is_repairing)

        scv_tags = {scv.add_on_tag for scv in scv_constructing}

        for building in self.units.structure.ready:

            if building.health_percentage < 1:

                if self.units(SCV).amount > 0:

                    if building.add_on_tag not in scv_tags:
                        scv = self.units(SCV).ready.random
                        await self.do(scv(SMART, building))

    async def expand(self):
        """
        Expand the base by creating a new command center (use a function of bot_ai).

        :return: self.expand_now()
        """

        # We will be 4 bases maximum
        if self.units(COMMANDCENTER).amount < 4:
            # We plan to build a base every 5 min + self.time is in SECOND
            if self.units(COMMANDCENTER).amount < ((self.time / 60)/5):
                if self.can_afford(COMMANDCENTER) and not self.already_pending(COMMANDCENTER):

                    await self.expand_now()

    async def build_barracks(self):

        if self.units(SUPPLYDEPOT).ready.exists or self.units(SUPPLYDEPOTLOWERED).ready.exists:

            # create 2 BARRACKS maximum
            if self.units(BARRACKS).amount < 2:

                if self.can_afford(BARRACKS) and not self.already_pending(BARRACKS):
                    cc = self.units(COMMANDCENTER).ready.random
                    # position = cc.position.towards(self.game_info.map_center, 7)
                    # pos = cc.position.towards_with_random_angle(self.game_info.map_center, 7)

                    pos = cc.position.random_on_distance(10)

                    if await self.can_place(BARRACKS, pos):
                        await self.build(BARRACKS, near=pos)

        if self.units(BARRACKS).ready.exists and self.units(BARRACKSTECHLAB).amount < 1:

                tech_lab_tags = {techlab.tag for techlab in self.units(BARRACKSTECHLAB)}

                for barrack in self.units(BARRACKS).ready.noqueue:
                    if barrack.add_on_tag not in tech_lab_tags:
                        if self.can_afford(BARRACKSTECHLAB):
                            await self.do(barrack.build(BARRACKSTECHLAB))

    async def create_army(self):
        if self.units(BARRACKS).ready.exists:

            for barrack in self.units(BARRACKS).ready.noqueue:

                if self.can_afford(MARINE) and self.supply_left > 0:

                    await self.do(barrack.train(MARINE))

    async def defend(self):

        ramp = self.main_base_ramp.depot_in_middle
        # print(ramp.depot_in_middle)

        if self.units(COMMANDCENTER).not_ready.exists:

            self.defend_base = True

            # cc = self.units(COMMANDCENTER).not_ready.first
            for marine in self.units(MARINE):

                # if marine.position.to2.distance_to(cc.position) > 8:
                if marine.position.to2.distance_to(ramp.towards(self.game_info.map_center, 10)) > 8:
                    # await self.do(marine.move(cc.position))
                    await self.do(marine.move(ramp.towards(self.game_info.map_center, 10)))

        else:

            self.defend_base = False

            if self.units(MARINE).amount < 20 and self.units(MARINE).idle.amount > 0:

                for marine in self.units(MARINE).idle:

                    if marine.position.to2.distance_to(ramp.towards(self.game_info.map_center, -3)) > 5:
                        # await self.do(marine.hold_position())
                        await self.do(marine.move(ramp.towards(self.game_info.map_center, -3)))

                    else:
                        if len(self.known_enemy_units) > 0:

                            await self.do(marine.hold_position())
                            # enemy_unit = self.known_enemy_units.closest_to(marine.position)
                            # await self.do(marine.attack(enemy_unit))

    async def attack(self):

        if self.units(MARINE).idle.amount > 20:

            for marine in self.units(MARINE).idle.random_group_of(20):

                enemy_location = self.enemy_start_locations[0]
                await self.do(marine.attack(enemy_location))

        # Because when the marine are perpetually in attack mode (due to the Zerg rush), we force the attack by taking
        # some marine even if they are doing something.
        # after firing their guns, the marines need few second of rest before passing to IDLE mode.
        elif not self.attacking and self.units(MARINE).amount > 30:

            self.attacking = True

            for marine in self.units(MARINE).prefer_idle.random_group_of(20):

                self.attacking_units.append(marine.tag)
                enemy_location = self.enemy_start_locations[0]
                await self.do(marine.attack(enemy_location))

    def check_attack_status(self):

        marine_tags = {marine.tag for marine in self.units(MARINE)}

        for marine in self.attacking_units:
            if marine not in marine_tags:
                self.attacking_units.remove(marine)

        if len(self.attacking_units) == 0:

            self.attacking = False


if __name__ == "__main__":

    # To run several instances just execute several time this code
    # ==> /!\ each instances multiply the processor needs and memory needs.
    # specify run speed at TRUE = normal speed and FAlSE = ultra fast speed.

    # to play against a bot, the human player must be player 1 and placed before the bot ! else it won't work
    # [Human(sc2.Race.Zerg), Bot(sc2.Race.Terran, MeatBot())]

    run_game(
        maps.get("AbyssalReefLE"),
        [
            # Human(sc2.Race.Zerg),
            Bot(Race.Terran, BotTerran()),
            # Computer(Race.Zerg, Difficulty.Easy)
            Bot(Race.Zerg, BotZerg.BotZerg())
        ],
        realtime=False)  # time in second : 1800sec = 30 min
