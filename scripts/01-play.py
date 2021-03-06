from collections import deque
import argparse
import time
import matplotlib
import gym
import SEVN_gym # noqa
import numpy as np
from gym import logger
import pygame
from SEVN_gym.envs.utils import ActionsWithNOOP

try:
    matplotlib.use('TkAgg')
    import matplotlib.pyplot as plt
except ImportError as e:
    logger.warn('failed to set matplotlib backend,' +
                ' plotting will not work: %s' % str(e))
    plt = None
from pygame.locals import VIDEORESIZE


def display_arr(screen, arr, video_size, transpose):
    # need to reformat and (possibly) transpose the image for pygame
    arr_min, arr_max = arr.min(), arr.max()
    arr = 255.0 * (arr - arr_min) / (arr_max - arr_min)
    arr = arr.astype("int8")
    arr = arr.swapaxes(0, 2) if transpose else arr
    arr = np.transpose(arr, (1, 0, 2))
    pyg_img = pygame.surfarray.make_surface(arr)
    pyg_img = pygame.transform.scale(pyg_img, video_size)
    screen.blit(pyg_img, (0, 0))


def display_text(screen, text, video_size):
    textSurface = pygame.font.Font(
        'freesansbold.ttf', 30).render(text, True, (0, 0, 0))
    textRect = textSurface.get_rect()
    textRect.center = (video_size[0]/10, video_size[1]/10)
    screen.blit(textSurface, textRect)
    pygame.display.update()


def display_bb(screen, rel_coords, text, video_size):
    textSurface = pygame.font.Font(
        'freesansbold.ttf', 30).render(text, True, (0, 0, 0))
    textRect = textSurface.get_rect()
    BLUE = (0, 0, 255)
    pygame.draw.rect(screen, BLUE, rel_coords)
    textRect.center = (video_size[0]/10, video_size[1]/10)
    screen.blit(textSurface, textRect)
    pygame.display.update()


def play(env, transpose=True, fps=30, zoom=0.5, high_res=False,
         callback=None, keys_to_action=None):
    obs = env.reset()
    env.unwrapped._action_set = ActionsWithNOOP
    rendered = env.render(mode='rgb_array')
    if keys_to_action is None:
        if hasattr(env, 'get_keys_to_action'):
            keys_to_action = env.get_keys_to_action()
        elif hasattr(env.unwrapped, 'get_keys_to_action'):
            keys_to_action = env.unwrapped.get_keys_to_action()
        else:
            assert False, env.spec.id + ' does not have explicit key to' + \
                          ' action mapping, please specify one manually'
    relevant_keys = set(sum(map(list, keys_to_action.keys()), []))

    # Take the two spatial dimensions of the rendered image to be displayed
    video_size = [rendered.shape[1], rendered.shape[2]]
    if zoom is not None:
        video_size = int(video_size[0] * zoom), int(video_size[1] * zoom)

    pressed_keys = []
    running = True
    env_done = True

    pygame.font.init()
    screen = pygame.display.set_mode(video_size)
    clock = pygame.time.Clock()
    pygame.display.set_caption('NAVI')

    info = None
    f = 0
    start = time.time()
    while running:
        f += 1
        if time.time() - start > 1:
            start = time.time()
            f = 0
        if env_done:
            env_done = False
            obs = env.reset()
        else:
            # If no key pressed, then NOOP it out
            action = keys_to_action.get(tuple(sorted(pressed_keys)), ActionsWithNOOP.NOOP)
            prev_obs = obs
            obs, rew, env_done, info = env.step(action)

            if callback is not None:
                callback(prev_obs, obs, action, rew, env_done, info)

        if obs is not None:
            rendered = env.render(mode='rgb_array')
            display_arr(screen, rendered,
                        transpose=transpose, video_size=video_size)
        if info is not None:
            info.get('achieved_goal')

        # process pygame events
        for event in pygame.event.get():
            # test events, set key states
            if event.type == pygame.KEYDOWN:
                if event.key in relevant_keys:
                    pressed_keys.append(event.key)
                elif event.key == 27:
                    running = False
            elif event.type == pygame.KEYUP:
                if event.key in relevant_keys:
                    pressed_keys.remove(event.key)
            elif event.type == pygame.QUIT:
                running = False
            elif event.type == VIDEORESIZE:
                video_size = event.size
                screen = pygame.display.set_mode(video_size)

        pygame.display.flip()
        clock.tick(fps)
    pygame.quit()


class PlayPlot(object):
    def __init__(self, callback, horizon_timesteps, plot_names):
        self.data_callback = callback
        self.horizon_timesteps = horizon_timesteps
        self.plot_names = plot_names

        assert plt is not None, 'matplotlib backend failed, plotting will' + \
                                ' not work'

        num_plots = len(self.plot_names)
        self.fig, self.ax = plt.subplots(num_plots)
        if num_plots == 1:
            self.ax = [self.ax]
        for axis, name in zip(self.ax, plot_names):
            axis.set_title(name)
        self.t = 0
        self.cur_plot = [None for _ in range(num_plots)]
        self.data = [deque(maxlen=horizon_timesteps) for _ in range(num_plots)]

    def callback(self, obs_t, obs_tp1, action, rew, done, info):
        points = self.data_callback(obs_t, obs_tp1, action, rew, done, info)
        for point, data_series in zip(points, self.data):
            data_series.append(point)
        self.t += 1

        xmin, xmax = max(0, self.t - self.horizon_timesteps), self.t

        for i, plot in enumerate(self.cur_plot):
            if plot is not None:
                plot.remove()
            self.cur_plot[i] = self.ax[i].scatter(
                range(xmin, xmax), list(self.data[i]), c='blue')
            self.ax[i].set_xlim(xmin, xmax)
        plt.pause(0.000001)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--env',
                        type=str, default='SEVN-Play-v1',
                        help='Define Environment')
    parser.add_argument('--high-res', action="store_true",
                        help='Use high-resolution images')
    parser.add_argument('--fps', type=int, default=6,
                        help='Set upper limit of FPS')
    args = parser.parse_args()
    if args.high_res:
        zoom = 0.5
    else:
        zoom = 4
    env = gym.make(args.env)
    play(env, zoom=zoom, fps=6)


if __name__ == '__main__':
    main()