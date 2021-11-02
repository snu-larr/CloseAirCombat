import numpy as np
from gym import spaces
from .task_base import BaseTask
from ..core.catalog import Catalog as c
from ..reward_functions import AltitudeReward, HeadingReward
from ..termination_conditions import ExtremeState, LowAltitude, Overload, Timeout, UnreachHeading, UnreachHeadingAndAltitude
from ..utils.utils import lonlat2dis


class HeadingTask(BaseTask):
    '''
    Control target heading with discrete action space
    '''
    def __init__(self, config):
        self.config = config
        self.num_fighters = getattr(self.config, 'num_fighters', 2)
        assert self.num_fighters == 1, "Heading task only support one fighter!"
        self.num_agents = self.num_fighters

        self.reward_functions = [
            HeadingReward(self.config),
            AltitudeReward(self.config),
        ]

        self.termination_conditions = [
            UnreachHeading(self.config),
            ExtremeState(self.config),
            Overload(self.config),
            LowAltitude(self.config),
            Timeout(self.config),
        ]

        self.load_variables()
        self.load_observation_space()
        self.load_action_space()

    def load_variables(self):
        self.state_var = [
            c.delta_altitude,                   #  0. delta_h   (unit: feet)
            c.delta_heading,                    #  1.           (unit: degree)
            c.attitude_roll_rad,                #  2. roll      (unit: rad)
            c.attitude_pitch_rad,               #  3. pitch     (unit: rad)
            c.velocities_v_north_fps,           #  4. v_north   (unit: fps)
            c.velocities_v_east_fps,            #  5. v_east    (unit: fps)
            c.velocities_v_down_fps,            #  6. v_down    (unit: fps)
            c.velocities_vc_fps,                #  7. vc        (unit: fps)
        ]
        self.action_var = [
            c.fcs_aileron_cmd_norm,             # [-1., 1.]
            c.fcs_elevator_cmd_norm,            # [-1., 1.]
            c.fcs_rudder_cmd_norm,              # [-1., 1.]
            c.fcs_throttle_cmd_norm,            # [0.4, 0.9]
        ]
        self.render_var = [
            c.position_long_gc_deg,
            c.position_lat_geod_deg,
            c.position_h_sl_ft,
            c.attitude_roll_rad,
            c.attitude_pitch_rad,
            c.attitude_heading_true_rad,
        ]

    def load_observation_space(self):
        self.observation_space = [spaces.Box(low=-10, high=10., shape=(8,)) for _ in range(self.num_agents)]

    def load_action_space(self):
        # aileron, elevator, rudder, throttle
        self.action_space = [spaces.MultiDiscrete([41, 41, 41, 30]) for _ in range(self.num_agents)]

    def normalize_observation(self, env, obsersvations: list):
        ego_obs_list = obsersvations[0]
        observation = np.zeros(8)
        observation[0] = ego_obs_list[0] * 0.304 / 1000     #  0. ego delta altitude  (unit: 1km)
        observation[1] = ego_obs_list[1] / 180 * np.pi      #  1. ego delta heading   (unit rad)
        observation[2] = ego_obs_list[2]                    #  2. ego_roll    (unit: rad)
        observation[3] = ego_obs_list[3]                    #  3. ego_pitch   (unit: rad)
        observation[4] = ego_obs_list[4] * 0.304 / 340      #  4. ego_v_north        (unit: mh)
        observation[5] = ego_obs_list[5] * 0.304 / 340      #  5. ego_v_east        (unit: mh)
        observation[6] = ego_obs_list[6] * 0.304 / 340      #  6. ego_v_down        (unit: mh)
        observation[7] = ego_obs_list[7] * 0.304 / 340      #  7. ego_vc        (unit: mh)
        observation = np.expand_dims(observation, axis=0)    # dim: (1,8)
        return observation

    def normalize_action(self, env, actions: list):
        """Convert discrete action index into continuous value.
        """
        def _normalize(action):
            action_norm = np.zeros(4)
            action_norm[0] = action[0] * 2. / (self.action_space[0].nvec[0] - 1.) - 1.
            action_norm[1] = action[1] * 2. / (self.action_space[0].nvec[1] - 1.) - 1.
            action_norm[2] = action[2] * 2. / (self.action_space[0].nvec[2] - 1.) - 1.
            action_norm[3] = action[3] * 0.5 / (self.action_space[0].nvec[3] - 1.) + 0.4
            return action_norm

        norm_act = np.zeros((self.num_fighters, 4))
        for agent_id in range(self.num_fighters):
            norm_act[agent_id] = _normalize(actions[agent_id])
        return norm_act

    def reset(self, env):
        """Task-specific reset, include reward function reset.

        Must call it after `env.get_observation()`
        """
        return super().reset(env)

    def get_reward(self, env, agent_id, info={}):
        """
        Must call it after `env.get_observation()`
        """
        return super().get_reward(env, agent_id, info)

    def get_termination(self, env, agent_id, info={}):
        return super().get_termination(env, agent_id, info)


class HeadingContinuousTask(HeadingTask):
    '''
    Control target heading with continuous action space
    '''
    def __init__(self, config):
        super().__init__(config)
    
    def load_action_space(self):
        # aileron, elevator, rudder, throttle
        self.action_space = [spaces.Box(
                                        low=np.array([-1.0, -1.0, -1.0, 0.4]), 
                                        high=np.array([1.0, 1.0, 1.0, 0.9])
                                         ) for _ in range(self.num_agents)]

    def normalize_action(self, env, actions: list):
        """Clip continuous value into proper value.
        """
        def _normalize(action):
            return np.clip(action, [-1.0, -1.0, -1.0, 0.4], [1.0, 1.0, 1.0, 0.9])

        norm_act = np.zeros((self.num_fighters, 4))
        for agent_id in range(self.num_fighters):
            norm_act[agent_id] = _normalize(actions[agent_id])
        return norm_act


class HeadingAndAltitudeTask(HeadingTask):
    '''
    Control target heading and target altitude with discrete action space
    '''
    def __init__(self, config):
        super().__init__(config)
        self.termination_conditions = [
            UnreachHeadingAndAltitude(self.config),
            ExtremeState(self.config),
            Overload(self.config),
            LowAltitude(self.config),
            Timeout(self.config),
        ]