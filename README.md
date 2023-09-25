# FireQuadTreeTest
This is a quick python program I wrote to work on a quadtree based model for fuel and temperature.
I aim to use this in a game for a fire propogation system, and the quadtree structure is used so that higher detail can be placed around areas of interest.

The quadtree structure is randomised when the script is ran.
## Requirements
- Pygame (`pip3 install pygame`)
- [Vector2D.py](https://github.com/oxi-dev0/vector2d.py/) (`pip3 install vector2d.py`)

## Controls
Click - Ignite a cell
Tab - Switch visual mode

### Visual Modes
Temperature - Cells become red as they approach the ignition temperature
Fuel - Cells become less green as they burn fuel