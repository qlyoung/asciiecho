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
import requests

GLOBALOFFSETS = (21, 1)
TEAM_BLUE = 0
TEAM_ORANGE = 1

ARENA_DIMMS = (82, 32)

# frame cache
lastframe = None
last_score = None

# screen
screen = None

# scenes
scenes = {"main": None}


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


class UpdateFrame(DynamicRenderer):
    """
    Dummy renderer; renders nothing, but updates the frame cache. Should come
    first in effects chain.
    """

    def _render_now(self):
        """
        In a typical DynamicRenderer, normally you would compute your scene and
        return it here. Instead we just fetch a new frame from the game API and
        cache it in a global, as well as checking if a goal just occurred and
        triggering goal effects if it did.
        """
        global lastframe
        global scores
        global last_score

        try:
            resp = requests.get("http://127.0.0.1:6721/session")
            lastframe = resp.json()

            # check if goal just occurred
            if (
                last_score
                and last_score["distance_thrown"]
                != lastframe["last_score"]["distance_thrown"]
            ):
                xpos = (
                    8
                    if lastframe["last_score"]["team"] == "blue"
                    else ARENA_DIMMS[0] - 8
                )
                color = (
                    Screen.COLOUR_BLUE
                    if lastframe["last_score"]["team"] == "blue"
                    else Screen.COLOUR_RED
                )
                explode = GoalFirework(
                    color=color,
                    screen=screen,
                    x=GLOBALOFFSETS[0] + xpos,
                    y=GLOBALOFFSETS[1] + 15,
                    life_time=70,
                    delete_count=70,
                    start_frame=screen._frame,
                )
                scenes["main"].add_effect(explode)

            last_score = lastframe["last_score"]
        except JSONDecodeError:
            pass
        except KeyError:
            pass
        except Exception as e:
            raise e

        return StaticRenderer(images=[""]).rendered_text


class GeometryRenderer(StaticRenderer):
    """
    Dynamic renderer for arena geometry
    """

    def __init__(self):
        super().__init__()

        txt = "|" + " " * (ARENA_DIMMS[0] - 10) + "|\n"
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
            return (GLOBALOFFSETS[0] + x, GLOBALOFFSETS[1] + y)
        except Exception as e:
            return (GLOBALOFFSETS[0] + self.x, GLOBALOFFSETS[1] + self.y)

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
            return (GLOBALOFFSETS[0] + x, GLOBALOFFSETS[1] + y)
        except Exception as e:
            return (0, 0)

    def process_event(self, event):
        return None


def play(_screen):
    global screen

    screen = _screen
    spacerect = " " * (ARENA_DIMMS[0] - 2) + "\n"
    spacerect *= ARENA_DIMMS[1] - 2

    effects = [
        Stars(screen, (screen.width + screen.height) // 2 + 45, delete_count=1),
        # Blackout
        Print(
            screen,
            renderer=StaticRenderer(images=[spacerect]),
            colour=Screen.COLOUR_BLACK,
            x=GLOBALOFFSETS[0] + 1,
            y=GLOBALOFFSETS[1] + 1,
            transparent=False,
            delete_count=1,
        ),
        # Print(screen, renderer=Plasma(screen.height, screen.width, 8), y=0),
        # frame update
        Print(screen, renderer=UpdateFrame(0, 0), colour=Screen.COLOUR_RED, y=0),
        # Arena geo
        Print(
            screen,
            renderer=Box(ARENA_DIMMS[0], ARENA_DIMMS[1], uni=True),
            y=GLOBALOFFSETS[1],
            x=GLOBALOFFSETS[0],
        ),
        Print(
            screen,
            renderer=GeometryRenderer(),
            colour=Screen.COLOUR_WHITE,
            x=GLOBALOFFSETS[0] + 4,
            y=GLOBALOFFSETS[1] + 14,
        ),
        # clock
        Print(
            screen,
            renderer=ClockText(),
            colour=Screen.COLOUR_CYAN,
            x=GLOBALOFFSETS[0] + 38,
            y=GLOBALOFFSETS[1],
            transparent=False,
        ),
        # scores
        Print(
            screen,
            renderer=ScoreText(TEAM_ORANGE),
            colour=Screen.COLOUR_RED,
            x=GLOBALOFFSETS[0] - 14,
            y=GLOBALOFFSETS[1],
            speed=20,
            transparent=False,
        ),
        Print(
            screen,
            renderer=ScoreText(TEAM_BLUE),
            colour=Screen.COLOUR_BLUE,
            x=GLOBALOFFSETS[0] + ARENA_DIMMS[0] + 1,
            y=GLOBALOFFSETS[1],
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
            x=GLOBALOFFSETS[0] + ARENA_DIMMS[0] + 1,
            y=GLOBALOFFSETS[1] + 24,
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
            x=GLOBALOFFSETS[0] + ARENA_DIMMS[0] + 1,
            y=GLOBALOFFSETS[1] + 26,
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
            x=GLOBALOFFSETS[0] + ARENA_DIMMS[0] + 1,
            y=GLOBALOFFSETS[1] + 28,
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
            x=GLOBALOFFSETS[0] + ARENA_DIMMS[0] + 1,
            y=GLOBALOFFSETS[1] + 30,
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
            y=GLOBALOFFSETS[1] + 24,
            x=GLOBALOFFSETS[0] - 17,
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
            x=GLOBALOFFSETS[0] - 17,
            y=GLOBALOFFSETS[1] + 26,
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
            x=GLOBALOFFSETS[0] - 17,
            y=GLOBALOFFSETS[1] + 28,
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
            x=GLOBALOFFSETS[0] - 17,
            y=GLOBALOFFSETS[1] + 30,
            speed=20,
            transparent=False,
        ),
        # Hotness
        Print(
            screen,
            renderer=Fire(8, 125, "*" * 110, 0.8, 20, screen.colours),
            y=GLOBALOFFSETS[1] + ARENA_DIMMS[1],
            x=0,
        ),
        # Title
        Print(
            screen,
            renderer=FigletText("Echo Arena", font="big"),
            y=GLOBALOFFSETS[1] + ARENA_DIMMS[1],
            x=GLOBALOFFSETS[0] + 9,
        ),
        Print(
            screen,
            renderer=StaticRenderer(images=["by qlyoung"]),
            colour=Screen.COLOUR_YELLOW,
            y=GLOBALOFFSETS[1] + ARENA_DIMMS[1],
            x=GLOBALOFFSETS[0] + 50,
        ),
    ]

    scenes["main"] = Scene(effects, -1, clear=True)

    screen.play([scenes["main"]])
    sleep(10)


Screen.wrapper(play)
