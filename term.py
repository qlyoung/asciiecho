from asciimatics.paths import DynamicPath
from asciimatics.screen import Screen
from asciimatics.scene import Scene
from asciimatics.effects import Cycle, Stars, Sprite, Effect, Print, Snow, Matrix, BannerText
from asciimatics.renderers import FigletText, StaticRenderer, Box, Fire, DynamicRenderer
from asciimatics.particles import StarFirework, PalmFirework, StarExplosion, ShotEmitter, DropScreen
from asciimatics.exceptions import NextScene
from time import sleep
import requests

GLOBALOFFSETS = (21, 1)
TEAM_BLUE = 0
TEAM_ORANGE = 1

# frame cache
lastframe = None
last_score = None


def globaloffset(x, y):
    return (x + GLOBALOFFSETS[0], y + GLOBALOFFSETS[1])


class UpdateFrame(DynamicRenderer):
    """
    Dummy renderer; renders nothing, but updates the frame cache. Should come
    first in effects chain.
    """
    def _render_now(self):
        global lastframe
        global scores
        global last_score

        try:
            resp = requests.get("http://127.0.0.1:6721/session")
            lastframe = resp.json()

            # check if goal just occurred
            if last_score and last_score['distance_thrown'] != lastframe['last_score']['distance_thrown']:
                last_score = None
                raise NextScene()

            last_score = lastframe['last_score']
        except NextScene as e:
            raise e
        except Exception:
            pass

        return StaticRenderer(images=[""]).rendered_text


class ScoreText(DynamicRenderer):
    """
    Dynamic renderer for current team score
    """
    def __init__(self, team):
        """
        team - team index, 0 for blue 1 for orange
        """
        self.team = team
        super().__init__(8, 8)

    def _render_now(self):
        try:
            score = 0 if lastframe is None else lastframe["teams"][self.team]["stats"]["points"]
            return FigletText(str(score), font="small").rendered_text
        except:
            return FigletText(str(0), font="small").rendered_text


class ClockText(DynamicRenderer):
    """
    Dynamic renderer for current team score
    """
    def __init__(self):
        """
        team - team index, 0 for blue 1 for orange
        """
        super().__init__(8, 8)

    def _render_now(self):
        clocktext = "00:00.00"
        try:
            clocktext = clocktext if lastframe is None else lastframe["game_clock_display"]
        except:
            pass

        return StaticRenderer(images=[clocktext]).rendered_text


class PlayerNameText(DynamicRenderer):
    """
    Dynamic renderer for player name
    """
    def __init__(self, team, player, rjust=False):
        """
        team - team index, 0 for blue 1 for orange
        player - player index within team, valid 0-3
        """
        self.rjust = rjust
        self.team = team
        self.player = player
        super().__init__(8, 8)

    def _render_now(self):
        try:
            playername = lastframe['teams'][self.team]['players'][self.player]['name']
            if self.rjust:
                playername = playername.rjust(16)
        except:
            playername = '-' * 16

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
            return globaloffset(x, y)
        except Exception:
            return globaloffset(self.x, self.y)

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
                lastframe["teams"][self.team]["players"][self.player]["position"][2]
                + 40
            )
            y = int(
                lastframe["teams"][self.team]["players"][self.player]["position"][0]
                + 15
            )
            return globaloffset(x, y)
        except Exception as e:
            return (0, 0)

    def process_event(self, event):
        return None

scenes = {
    'main': None
}

def play(screen):
    effects = [
        # Stars(screen, (screen.width + screen.height) // 2),
        # frame update
        Print(
            screen,
            renderer=UpdateFrame(0, 0),
            colour=Screen.COLOUR_RED,
            y=0,
        ),
        # arena box
        Print(
            screen,
            renderer=Box(82, 32, uni=True),
            y=GLOBALOFFSETS[1],
            x=GLOBALOFFSETS[0],
        ),
        # clock
        Print(
            screen,
            renderer=ClockText(),
            colour=Screen.COLOUR_CYAN,
            y=GLOBALOFFSETS[1],
            x=GLOBALOFFSETS[0] + 38,
            transparent=False,
        ),
        # scores
        Print(
            screen,
            renderer=ScoreText(TEAM_ORANGE),
            colour=Screen.COLOUR_RED,
            y=GLOBALOFFSETS[1],
            x=GLOBALOFFSETS[0] - 10,
            transparent=False,
        ),
        Print(
            screen,
            renderer=ScoreText(TEAM_BLUE),
            colour=Screen.COLOUR_BLUE,
            y=GLOBALOFFSETS[1],
            x=GLOBALOFFSETS[0] + 83,
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
            y=GLOBALOFFSETS[1] + 24,
            x=GLOBALOFFSETS[0] + 83,
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
            y=GLOBALOFFSETS[1] + 26,
            x=GLOBALOFFSETS[0] + 83,
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
            y=GLOBALOFFSETS[1] + 28,
            x=GLOBALOFFSETS[0] + 83,
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
            y=GLOBALOFFSETS[1] + 30,
            x=GLOBALOFFSETS[0] + 83,
        ),
        Sprite(
            screen,
            {"default": StaticRenderer(images=["•"])},
            path=PlayerPath(screen, 5, 5, TEAM_ORANGE, 0),
            colour=Screen.COLOUR_RED,
        ),
        Print(
            screen,
            renderer=PlayerNameText(TEAM_ORANGE, 0, rjust=True),
            colour=Screen.COLOUR_RED,
            y=GLOBALOFFSETS[1] + 24,
            x=GLOBALOFFSETS[0] - 17,
        ),
        Sprite(
            screen,
            {"default": StaticRenderer(images=["•"])},
            path=PlayerPath(screen, 5, 5, TEAM_ORANGE, 1),
            colour=Screen.COLOUR_RED,
        ),
        Print(
            screen,
            renderer=PlayerNameText(TEAM_ORANGE, 1, rjust=True),
            colour=Screen.COLOUR_RED,
            y=GLOBALOFFSETS[1] + 26,
            x=GLOBALOFFSETS[0] - 17,
        ),
        Sprite(
            screen,
            {"default": StaticRenderer(images=["•"])},
            path=PlayerPath(screen, 5, 5, TEAM_ORANGE, 2),
            colour=Screen.COLOUR_RED,
        ),
        Print(
            screen,
            renderer=PlayerNameText(TEAM_ORANGE, 2, rjust=True),
            colour=Screen.COLOUR_RED,
            y=GLOBALOFFSETS[1] + 28,
            x=GLOBALOFFSETS[0] - 17,
        ),
        Sprite(
            screen,
            {"default": StaticRenderer(images=["•"])},
            path=PlayerPath(screen, 5, 5, TEAM_ORANGE, 3),
            colour=Screen.COLOUR_RED,
        ),
        Print(
            screen,
            renderer=PlayerNameText(TEAM_ORANGE, 3, rjust=True),
            colour=Screen.COLOUR_RED,
            y=GLOBALOFFSETS[1] + 30,
            x=GLOBALOFFSETS[0] - 17,
        ),
        # Hotness
        Print(
            screen,
            renderer=Fire(10, 120, "*" * 110, 0.8, 20, screen.colours),
            y=GLOBALOFFSETS[1] + 32,
            x=0, #GLOBALOFFSETS[0],
        ),
        # Title
        Print(
            screen,
            renderer=FigletText("Echo Arena", font="big"),
            y=GLOBALOFFSETS[1] + 32,
            x=GLOBALOFFSETS[0] + 9,
        ),
        Print(
            screen,
            renderer=StaticRenderer(images=["by qlyoung"]),
            colour=Screen.COLOUR_YELLOW,
            y=GLOBALOFFSETS[1] + 32,
            x=GLOBALOFFSETS[0] + 50,
        ),
    ]

    scenes['main'] = Scene(effects, -1, clear=True)

    goal_effects = effects.copy()
    goal_effects.append(StarFirework(screen, GLOBALOFFSETS[0] + 40, GLOBALOFFSETS[1] + 15, 70))

    screen.play([Scene(effects, -1, clear=True), Scene(goal_effects, 70, clear=False)])
    sleep(10)


Screen.wrapper(demo)
