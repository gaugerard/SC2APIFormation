import sc2
from sc2 import run_game, maps, Race, Difficulty, position, Result
from sc2.player import Bot, Computer
from sc2.constants import SCV, COMMANDCENTER, REFINERY, SUPPLYDEPOT

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

    async def build_workers(self):
        """
        Build worker under certain conditions related to the number of command center and related to the max number of
        worker.

        :return: execute action self.do(command_center.train(SCV)).
        """
        if self.units(SCV).amount < self.units(COMMANDCENTER).amount*16:
            for command_center in self.units(COMMANDCENTER).ready.noqueue:
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