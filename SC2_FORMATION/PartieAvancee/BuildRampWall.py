import sc2
from sc2 import run_game, maps, Race, Difficulty, position, Result
from sc2.player import Bot, Computer
from sc2.constants import SCV, COMMANDCENTER, REFINERY, SUPPLYDEPOT, BARRACKS, MARINE, BARRACKSTECHLAB, \
    SUPPLYDEPOTLOWERED, MORPH_SUPPLYDEPOT_LOWER, MORPH_SUPPLYDEPOT_RAISE

class BotTerran(sc2.BotAI):

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

        await self.build_barracks()
        await self.create_army()

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
        # Raise depos when enemies are nearby
        for supply_depot in self.units(SUPPLYDEPOT).ready:
            for unit in self.known_enemy_units.not_structure:
                if unit.position.to2.distance_to(supply_depot.position.to2) < 25:
                    break
            else:
                await self.do(supply_depot(MORPH_SUPPLYDEPOT_LOWER))

        # Lower depos when no enemies are nearby
        for supply_depot in self.units(SUPPLYDEPOTLOWERED).ready:
            for unit in self.known_enemy_units.not_structure:
                if unit.position.to2.distance_to(supply_depot.position.to2) < 15:
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

    async def build_barracks(self):

        if self.units(SUPPLYDEPOT).ready.exists:

            # create 3 BARRACKS maximum
            if self.units(BARRACKS).amount < 3:
                if self.can_afford(BARRACKS) and not self.already_pending(BARRACKS):
                    cc = self.units(COMMANDCENTER).ready.random
                    await self.build(BARRACKS, near=cc.position.towards(self.game_info.map_center, 8))

    async def create_army(self):
        if self.units(BARRACKS).ready.exists:

            for barrack in self.units(BARRACKS).ready.noqueue:

                if self.can_afford(MARINE) and self.supply_left > 0:

                    await self.do(barrack.train(MARINE))


if __name__ == "__main__":

    # To run several instances just execute several time this code
    # ==> /!\ each instances multiply the processor needs and memory needs.
    # specify run speed at TRUE = normal speed and FAlSE = ultra fast speed.

    # to play against a bot, the human player must be player 1 and placed before the bot ! else it won't work
    # [Human(sc2.Race.Zerg), Bot(sc2.Race.Terran, MeatBot())]

    run_game(
        maps.get("AbyssalReefLE"),
        [
            Bot(Race.Terran, BotTerran()),
            Computer(Race.Zerg, Difficulty.Easy)
        ],
        realtime=False)  # time in second : 1800sec = 30 min
