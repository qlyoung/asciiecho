#!/usr/bin/python3

from asciimatics.paths import DynamicPath
from asciimatics.screen import Screen
from asciimatics.scene import Scene
from asciimatics.effects import (
    Cycle,
    Stars,
    Sprite,
    Effect,
    Print,
    Snow,
    Matrix,
    BannerText,
)
from asciimatics.renderers import (
    FigletText,
    StaticRenderer,
    Box,
    Fire,
    DynamicRenderer,
    Plasma,
)
from asciimatics.particles import (
    StarFirework,
    PalmFirework,
    ShotEmitter,
    DropScreen,
    Explosion,
    ParticleEffect,
    StarExplosion,
    RingExplosion,
    Rain,
)
from asciimatics.exceptions import NextScene
from time import sleep
from json.decoder import JSONDecodeError
from random import randint
from collections import namedtuple
import aiohttp
from aiohttp.client_exceptions import ClientConnectorError, ContentTypeError
import asyncio

Point = namedtuple("Point", ["x", "y"])

GLOBALOFFSETS = Point(21, 1)
TEAM_BLUE = 0
TEAM_ORANGE = 1

ARENA_DIMMS = Point(82, 32)

FRAMERATE = 20

# frame cache
lastframe = None
last_score = None

# screen
screen = None

# scenes
scenes = {"main": None}


async def api_update():
    """
    Asynchronous infinite loop that continually fetches new frame data from the
    Echo VR API.
    """
    global lastframe

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get("http://127.0.0.1:6721/session") as resp:
                    lastframe = await resp.json()
                await asyncio.sleep(1 / FRAMERATE)
            except ClientConnectorError as e:
                print("Contacting API failed: {}".format(str(e)))
                await asyncio.sleep(3)
            except ContentTypeError as e:
                print("Ignoring API response with non-JSON mimetype")


class GoalFirework(ParticleEffect):
    """
    Firework effect for goals
    """

    def __init__(self, color, **kwargs):
        self.color = color
        super().__init__(**kwargs)

    def _make_explosion(self):
        """
        Make StarExplosion effect for this goal firework
        """
        explosion = StarExplosion(
            self._screen,
            self._x,
            self._y,
            self._life_time,
            randint(6, 20),
            on_each=self._trail,
        )
        explosion._colour = self.color
        return explosion

    def reset(self):
        self._active_systems = []
        self._active_systems.append(self._make_explosion())

    def _next(self, parent):
        self._active_systems.append(self._make_explosion())

    def _trail(self, parent):
        if len(self._active_systems) < 150 and randint(0, 100) < 50:
            self._active_systems.append(self._make_explosion())


class TriggerEvents(DynamicRenderer):
    """
    Dummy renderer; renders nothing, but checks the current state to see if any
    special events occurred that should trigger effects.

    Should come first in effects chain.
    """

    def _render_now(self):
        """
        In a typical DynamicRenderer, normally you would compute your scene and
        return it here. Instead we check if a goal just occurred and trigger
        goal effects if it did.
        """
        global lastframe
        global scores
        global last_score

        try:
            if not lastframe:
                raise Exception("No frame to render")

            # check if goal just occurred
            if (
                last_score
                and last_score["distance_thrown"]
                != lastframe["last_score"]["distance_thrown"]
            ):
                xpos = (
                    8
                    if lastframe["last_score"]["team"] == "blue"
                    else ARENA_DIMMS.x - 8
                )

                color = (
                    Screen.COLOUR_BLUE
                    if lastframe["last_score"]["team"] == "blue"
                    else Screen.COLOUR_RED
                )
                explode = GoalFirework(
                    color=color,
                    screen=screen,
                    x=GLOBALOFFSETS.x + xpos,
                    y=GLOBALOFFSETS.y + 15,
                    life_time=70,
                    delete_count=70,
                    start_frame=screen._frame,
                )
                scenes["main"].add_effect(explode)

            last_score = lastframe["last_score"]
        except KeyError:
            pass
        except Exception:
            pass

        return StaticRenderer(images=[""]).rendered_text


class GeometryRenderer(StaticRenderer):
    """
    Dynamic renderer for arena geometry
    """

    def __init__(self):
        super().__init__()

        txt = "|" + " " * (ARENA_DIMMS.x - 10) + "|\n"
        txt *= 3
        self._images = [txt]


class ScoreText(DynamicRenderer):
    """
    Dynamic renderer for current team score.
    """

    def __init__(self, team, font="ogre"):
        """
        team - team index, 0 for blue 1 for orange
        font - Figlet font to use (default 'ogre')
        """
        self.font = font
        self.team = team
        super().__init__(8, 13)

    def _render_now(self):
        try:
            score = (
                0
                if lastframe is None
                else lastframe["teams"][self.team]["stats"]["points"]
            )

            return FigletText(str(score).rjust(2, "0"), font=self.font).rendered_text
        except:
            return FigletText(str(0), font=self.font).rendered_text


class ClockText(DynamicRenderer):
    """
    Dynamic renderer for current game clock.
    """

    def __init__(self):
        """
        team - team index, 0 for blue 1 for orange
        """
        super().__init__(8, 8)

    def _render_now(self):
        clocktext = "00:00.00"
        try:
            clocktext = (
                clocktext if lastframe is None else lastframe["game_clock_display"]
            )
        except:
            pass

        return StaticRenderer(images=[clocktext]).rendered_text


class PlayerNameText(DynamicRenderer):
    """
    Dynamic renderer for a single player name.
    """

    def __init__(self, team, player):
        """
        team - team index, 0 for blue 1 for orange
        player - player index within team, valid 0-3
        """
        self.rjust = team == 1
        self.team = team
        self.player = player
        super().__init__(8, 8)

    def _render_now(self):
        try:
            playername = lastframe["teams"][self.team]["players"][self.player]["name"]
            if self.rjust:
                playername = playername.rjust(16)
            else:
                playername = playername.ljust(16)
        except:
            playername = "-" * 16

        return StaticRenderer(images=[playername]).rendered_text


class DiscPath(DynamicPath):
    """
    Path for disc sprite. Position is pulled from frame cache.
    """

    def __init__(self, screen, x, y):
        super().__init__(screen, x, y)
        self.x = x
        self.y = y

    def is_finished(self):
        return False

    def next_pos(self):
        try:
            x = 80 - int(lastframe["disc"]["position"][2] + 40)
            y = int(lastframe["disc"]["position"][0] + 15)
            return (GLOBALOFFSETS.x + x, GLOBALOFFSETS.y + y)
        except Exception as e:
            return (GLOBALOFFSETS.x + self.x, GLOBALOFFSETS.y + self.y)

    def process_event(self, event):
        return None


class PlayerPath(DynamicPath):
    """
    Path for player sprite. Position is pulled from frame cache.
    """

    def __init__(self, screen, x, y, team, player):
        """
        x - starting x position
        y - starting y position
        team - team index, 0 for blue, 1 for orange
        player - player index within team, valid 0-3
        """
        super().__init__(screen, x, y)
        self.team = team
        self.player = player
        self.x = x
        self.y = y

    def is_finished(self):
        return False

    def next_pos(self):
        try:
            x = 80 - int(
                lastframe["teams"][self.team]["players"][self.player]["head"][
                    "position"
                ][2]
                + 40
            )
            y = int(
                lastframe["teams"][self.team]["players"][self.player]["head"][
                    "position"
                ][0]
                + 15
            )
            return (GLOBALOFFSETS.x + x, GLOBALOFFSETS.y + y)
        except Exception as e:
            return (0, 0)

    def process_event(self, event):
        return None


def create_scenes(screen):
    spacerect = " " * (ARENA_DIMMS.x - 2) + "\n"
    spacerect *= ARENA_DIMMS.y - 2

    effects = [
        Stars(screen, (screen.width + screen.height) // 2 + 45, delete_count=1),
        # Blackout
        Print(
            screen,
            renderer=StaticRenderer(images=[spacerect]),
            colour=Screen.COLOUR_BLACK,
            x=GLOBALOFFSETS.x + 1,
            y=GLOBALOFFSETS.y + 1,
            transparent=False,
            delete_count=2,
        ),
        # Print(screen, renderer=Plasma(screen.height, screen.width, 8), y=0),
        # frame update
        Print(screen, renderer=TriggerEvents(0, 0), colour=Screen.COLOUR_RED, y=0),
        # Arena geo
        Print(
            screen,
            renderer=Box(ARENA_DIMMS.x, ARENA_DIMMS.y, uni=True),
            y=GLOBALOFFSETS.y,
            x=GLOBALOFFSETS.x,
        ),
        Print(
            screen,
            renderer=GeometryRenderer(),
            colour=Screen.COLOUR_WHITE,
            x=GLOBALOFFSETS.x + 4,
            y=GLOBALOFFSETS.y + 14,
        ),
        # clock
        Print(
            screen,
            renderer=ClockText(),
            colour=Screen.COLOUR_CYAN,
            x=GLOBALOFFSETS.x + 38,
            y=GLOBALOFFSETS.y,
            transparent=False,
        ),
        # scores
        Print(
            screen,
            renderer=ScoreText(TEAM_ORANGE),
            colour=Screen.COLOUR_RED,
            x=GLOBALOFFSETS.x - 14,
            y=GLOBALOFFSETS.y,
            speed=20,
            transparent=False,
        ),
        Print(
            screen,
            renderer=ScoreText(TEAM_BLUE),
            colour=Screen.COLOUR_BLUE,
            x=GLOBALOFFSETS.x + ARENA_DIMMS.x + 1,
            y=GLOBALOFFSETS.y,
            speed=20,
            transparent=False,
        ),
        # disc sprite
        Sprite(
            screen,
            {"default": StaticRenderer(images=["()"])},
            path=DiscPath(screen, 5, 5),
            colour=Screen.COLOUR_GREEN,
        ),
        # players
        Sprite(
            screen,
            {"default": StaticRenderer(images=["•"])},
            path=PlayerPath(screen, 5, 5, TEAM_BLUE, 0),
            colour=Screen.COLOUR_BLUE,
        ),
        Print(
            screen,
            renderer=PlayerNameText(TEAM_BLUE, 0),
            colour=Screen.COLOUR_BLUE,
            x=GLOBALOFFSETS.x + ARENA_DIMMS.x + 1,
            y=GLOBALOFFSETS.y + 24,
            speed=20,
            transparent=False,
        ),
        Sprite(
            screen,
            {"default": StaticRenderer(images=["•"])},
            path=PlayerPath(screen, 5, 5, TEAM_BLUE, 1),
            colour=Screen.COLOUR_BLUE,
        ),
        Print(
            screen,
            renderer=PlayerNameText(TEAM_BLUE, 1),
            colour=Screen.COLOUR_BLUE,
            x=GLOBALOFFSETS.x + ARENA_DIMMS.x + 1,
            y=GLOBALOFFSETS.y + 26,
            speed=20,
            transparent=False,
        ),
        Sprite(
            screen,
            {"default": StaticRenderer(images=["•"])},
            path=PlayerPath(screen, 5, 5, TEAM_BLUE, 2),
            colour=Screen.COLOUR_BLUE,
        ),
        Print(
            screen,
            renderer=PlayerNameText(TEAM_BLUE, 2),
            colour=Screen.COLOUR_BLUE,
            x=GLOBALOFFSETS.x + ARENA_DIMMS.x + 1,
            y=GLOBALOFFSETS.y + 28,
            speed=20,
            transparent=False,
        ),
        Sprite(
            screen,
            {"default": StaticRenderer(images=["•"])},
            path=PlayerPath(screen, 5, 5, TEAM_BLUE, 3),
            colour=Screen.COLOUR_BLUE,
        ),
        Print(
            screen,
            renderer=PlayerNameText(TEAM_BLUE, 3),
            colour=Screen.COLOUR_BLUE,
            x=GLOBALOFFSETS.x + ARENA_DIMMS.x + 1,
            y=GLOBALOFFSETS.y + 30,
            speed=20,
            transparent=False,
        ),
        Sprite(
            screen,
            {"default": StaticRenderer(images=["•"])},
            path=PlayerPath(screen, 5, 5, TEAM_ORANGE, 0),
            colour=Screen.COLOUR_RED,
        ),
        Print(
            screen,
            renderer=PlayerNameText(TEAM_ORANGE, 0),
            colour=Screen.COLOUR_RED,
            y=GLOBALOFFSETS.y + 24,
            x=GLOBALOFFSETS.x - 17,
            speed=20,
            transparent=False,
        ),
        Sprite(
            screen,
            {"default": StaticRenderer(images=["•"])},
            path=PlayerPath(screen, 5, 5, TEAM_ORANGE, 1),
            colour=Screen.COLOUR_RED,
        ),
        Print(
            screen,
            renderer=PlayerNameText(TEAM_ORANGE, 1),
            colour=Screen.COLOUR_RED,
            x=GLOBALOFFSETS.x - 17,
            y=GLOBALOFFSETS.y + 26,
            speed=20,
            transparent=False,
        ),
        Sprite(
            screen,
            {"default": StaticRenderer(images=["•"])},
            path=PlayerPath(screen, 5, 5, TEAM_ORANGE, 2),
            colour=Screen.COLOUR_RED,
        ),
        Print(
            screen,
            renderer=PlayerNameText(TEAM_ORANGE, 2),
            colour=Screen.COLOUR_RED,
            x=GLOBALOFFSETS.x - 17,
            y=GLOBALOFFSETS.y + 28,
            speed=20,
            transparent=False,
        ),
        Sprite(
            screen,
            {"default": StaticRenderer(images=["•"])},
            path=PlayerPath(screen, 5, 5, TEAM_ORANGE, 3),
            colour=Screen.COLOUR_RED,
        ),
        Print(
            screen,
            renderer=PlayerNameText(TEAM_ORANGE, 3),
            colour=Screen.COLOUR_RED,
            x=GLOBALOFFSETS.x - 17,
            y=GLOBALOFFSETS.y + 30,
            speed=20,
            transparent=False,
        ),
        # Hotness
        Print(
            screen,
            renderer=Fire(8, 125, "*" * 110, 0.8, 20, screen.colours),
            y=GLOBALOFFSETS.y + ARENA_DIMMS.y,
            x=0,
        ),
        # Title
        Print(
            screen,
            renderer=FigletText("Echo Arena", font="big"),
            y=GLOBALOFFSETS.y + ARENA_DIMMS.y,
            x=GLOBALOFFSETS.x + 12,
        ),
        Print(
            screen,
            renderer=StaticRenderer(images=["by qlyoung"]),
            colour=Screen.COLOUR_YELLOW,
            y=GLOBALOFFSETS.y + ARENA_DIMMS.y,
            x=GLOBALOFFSETS.x + 50,
        ),
    ]

    return Scene(effects, -1, clear=True)


def update_screen(loop, screen):
    screen.draw_next_frame()
    loop.call_later(1.0 / FRAMERATE, update_screen, loop, screen)


screen = Screen.open()
scenes["main"] = create_scenes(screen)
screen.set_scenes([scenes["main"]])

loop = asyncio.get_event_loop()
loop.call_soon(update_screen, loop, screen)
loop.create_task(api_update())

try:
    loop.run_forever()
except KeyboardInterrupt:
    print("Exiting.")
loop.close()
screen.close()
