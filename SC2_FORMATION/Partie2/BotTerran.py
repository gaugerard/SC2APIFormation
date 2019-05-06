import sc2
from sc2 import run_game, maps, Race, Difficulty, position, Result
from sc2.player import Bot, Computer
from sc2.constants import SCV, COMMANDCENTER, REFINERY, SUPPLYDEPOT, BARRACKS, MARINE, SUPPLYDEPOTLOWERED, SMART, \
    BARRACKSREACTOR, FACTORYREACTOR, STARPORTREACTOR, REACTOR, BARRACKSTECHLAB, FACTORYTECHLAB, STARPORTTECHLAB, TECHLAB


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
        await self.supply_depots()
        await self.build_refineries()

        await self.finish_repair_building()
        await self.repair_damage_building()

        await self.expand()

        await self.build_barracks()
        await self.create_army()

    # THE 2 MOST IMPORTANT FUNCTION ! THIS WILL MAKE YOU GO NUTS IF YOU DON'T HAVE THEM !
    # AND GOOD LUCK TO FIND THEM/CREATE THEM ON YOUR OWN IF YOU JUST STARTED LEARNING SC2API

    # ----------------------------------------------------------------------------------------
    # vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv

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
                            # SMART = right clicking
                            await self.do(scv(SMART, building))

    async def repair_damage_building(self):

        scv_constructing = self.units.filter(lambda unit: unit.is_repairing)

        scv_tags = {scv.add_on_tag for scv in scv_constructing}

        for building in self.units.structure.ready:

            if building.health_percentage < 1:

                if self.units(SCV).amount > 0:

                    if building.add_on_tag not in scv_tags:
                        scv = self.units(SCV).ready.random
                        # SMART = right clicking
                        await self.do(scv(SMART, building))

    # ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    # ----------------------------------------------------------------------------------------

    async def build_workers(self):
        """
        Build worker under certain conditions related to the number of command center.

        :return: execute action self.do(command_center.train(SCV)).
        """

        # this condition checks that there is not more than 16 workers (SCV) by base (COMMANDCENTER).
        if self.units(SCV).amount < self.units(COMMANDCENTER).amount * 16:
            # We go through all all command center that is ready and that has no unit to produce (in his queue).
            for command_center in self.units(COMMANDCENTER).ready.noqueue:
                # If we have enough minerals and vespene gas, we will build an worker with the selected command center.
                if self.can_afford(SCV):
                    await self.do(command_center.train(SCV))

    async def supply_depots(self):
        """
        Build supply depot under certain conditions related to the amount of supply_left (the amount of unit that we can
        produce before achieving max number of unit.)

        :return: execute action self.build(SUPPLYDEPOT, near=command_centers.first).
        """

        # supply_left = how many population can I produce more.
        if self.supply_left < 5 and not self.already_pending(SUPPLYDEPOT):
            command_centers = self.units(COMMANDCENTER).ready  # a command center that already exists
            if command_centers.exists:
                if self.can_afford(SUPPLYDEPOT):
                    await self.build(SUPPLYDEPOT, near=command_centers.first)  # specify build + where.

    async def build_refineries(self):
        """
        Build a refinery if we can afford it and if we have at least a worker.

        :return: execute action self.do(worker.build(REFINERY, vaspene)).
        """

        for command_center in self.units(COMMANDCENTER).ready:
            # This return all the places where there is a vaspene geyser.
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

    async def expand(self):
        """
        Expand the base by creating a new command center (use a function of bot_ai).

        :return: self.expand_now()
        """

        # We will be 2 bases maximum
        if self.units(COMMANDCENTER).amount < 2:
            # We plan to build a base every 3 min + self.time is in SECOND
            if self.units(COMMANDCENTER).amount < ((self.time / 60)/3):
                if self.can_afford(COMMANDCENTER) and not self.already_pending(COMMANDCENTER):
                    await self.expand_now()

    async def build_barracks(self):
        """
        Build a barrack if we can afford it and if we have at least a supply_depot (see terran tech tree).

        :return: execute action self.build(BARRACKS, near=pos).
        """

        # to be able to build a barrack, we need at lest 1 supply_depot ==> see TECH TREE of Terran.
        if self.units(SUPPLYDEPOT).ready.exists or self.units(SUPPLYDEPOTLOWERED).ready.exists:
            # create 3 BARRACKS maximum
            if self.units(BARRACKS).amount < 3:
                # self.already_pending(BARRACKS) checks if a barrack already is under construction .
                if self.can_afford(BARRACKS) and not self.already_pending(BARRACKS):
                    # we select a random command_center (to build our barrack near it)
                    cc = self.units(COMMANDCENTER).ready.random
                    # we build a barrack near the command_center TOWARDS the center of the map at a distance of 7.
                    # position = cc.position.towards(self.game_info.map_center, 7)
                    pos = cc.position.towards_with_random_angle(self.game_info.map_center, 7)

                    if await self.can_place(BARRACKS, pos):
                        await self.build(BARRACKS, near=pos)

    async def create_army(self):
        """
        Build an army of marines

        :return: execute action self.do(barrack.train(MARINE)).
        """

        if self.units(BARRACKS).ready.exists:

            for barrack in self.units(BARRACKS).ready.noqueue:

                if self.can_afford(MARINE) and self.supply_left > 0:

                    # We build (train) a marine in that barrack.
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
        realtime=True)  # Set realtime = False ==> makes the game run faster.
