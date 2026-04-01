"""test_isaac_franka.py — Isaac Sim 5.1 Franka robot smoke test.

Run with Isaac Sim's Python interpreter:
    ~/.local/share/ov/pkg/isaac-sim-5.1.0/python.sh \
        SystemCode/tests/test_isaac_franka.py
"""

# SimulationApp MUST be created before any omni.isaac imports
from isaacsim import SimulationApp
simulation_app = SimulationApp({"headless": True})

from omni.isaac.core import World
from omni.isaac.franka import Franka

world = World()
franka = world.scene.add(
    Franka(prim_path="/World/Franka", name="franka")
)
world.reset()

print("Franka joints:", franka.num_dof)
print("Isaac Sim Franka test OK")

simulation_app.close()
