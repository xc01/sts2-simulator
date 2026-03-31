"# sts2-map-simulator" 
+ Can be used to generate map for RL/other training.

### Usage
sts2_map_simulator.py [-h] [--layer {1,2,3}] [--act {overgrowth,hive,glory,underdocks}] [--act-index {1,2,3,4}] [--multiplayer]
                             [--underdocks-available] [--no-underdocks-available] [--first-time-underdocks] [--replace-treasure-with-elites] [--second-boss]
                             [--gloom] [--no-gloom] [--swarming-elites] [--no-swarming-elites] [--show-edges]
                             seed

For example, python sts2_map_simulator.py ABCD1234EF --layer 1