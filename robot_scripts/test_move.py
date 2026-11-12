#! /usr/bin/env python3
from picasso_robot import PicassoRobot

with PicassoRobot(node_name='test_move') as robot:
    robot.send_urscript('movej(pose_add(get_actual_tcp_pose(), p[0.05, 0, 0, 0, 0, 0]), a=0.3, v=0.2)')
    robot.wait_until_stopped()