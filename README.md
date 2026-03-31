# sts2-map-simulator
+ Can be used to generate map for RL/other training.

### Usage
```bash
sts2_map_simulator.py [-h] [--layer {1,2,3}] [--act {overgrowth,hive,glory,underdocks}] [--act-index {1,2,3,4}] [--multiplayer]
                             [--underdocks-available] [--no-underdocks-available] [--first-time-underdocks] [--replace-treasure-with-elites] [--second-boss]
                             [--gloom] [--no-gloom] [--swarming-elites] [--no-swarming-elites] [--show-edges]
                             seed
```

For example, python sts2_map_simulator.py ABCD1234EF --layer 1

### Example
```bash
$python sts2_map_simulator.py JDCBM5RFB8 --layer 2

seed_string=JDCBM5RFB8
requested_layer=2
resolved_act=hive
resolved_act_index=2
simple_random_boss=KaiserCrabBoss(**Wrong**)
run_seed_uint=1372849817
act_rng_seed_uint=3167602395
Legend: A=Ancient(start)  M=Monster  ?=Unknown  $=Shop  T=Treasure  R=RestSite  E=Elite  B=Boss  .=empty
Special nodes: start=(3,0), boss=(3,15)

row 00 (start row)       . . . A . . .
row 01 (first playable row) . M . M . . M
row 02                   ? . M . . ? M
row 03                   M . ? . M . M
row 04                   M . . M M . ?
row 05                   E M E ? M . M
row 06                   $ . M M . R .
row 07                   M . R M ? M E
row 08 (special row)     T . T . T T T
row 09                   $ . M E M M M
row 10                   R . M . R E M
row 11                   M . . ? . ? R
row 12                   M . ? M ? . E
row 13                   E . . E . $ ?
row 14 (pre-boss row)    R . . R . R R
row 15 (boss row)      . . . B . . .

Connections by row:
row 00: (3,0)->(1,1), (3,0)->(3,1), (3,0)->(6,1)
row 01: (1,1)->(0,2), (3,1)->(2,2), (6,1)->(5,2), (6,1)->(6,2)
row 02: (0,2)->(0,3), (2,2)->(2,3), (5,2)->(4,3), (6,2)->(6,3)
row 03: (0,3)->(0,4), (2,3)->(3,4), (4,3)->(3,4), (4,3)->(4,4), (6,3)->(6,4)
row 04: (0,4)->(0,5), (0,4)->(1,5), (3,4)->(2,5), (3,4)->(3,5), (4,4)->(4,5), (6,4)->(6,5)
row 05: (0,5)->(0,6), (1,5)->(2,6), (2,5)->(3,6), (3,5)->(3,6), (4,5)->(5,6), (6,5)->(5,6)
row 06: (0,6)->(0,7), (2,6)->(2,7), (3,6)->(3,7), (3,6)->(4,7), (5,6)->(5,7), (5,6)->(6,7)
row 07: (0,7)->(0,8), (2,7)->(2,8), (3,7)->(4,8), (4,7)->(5,8), (5,7)->(6,8), (6,7)->(6,8)
row 08: (0,8)->(0,9), (2,8)->(2,9), (4,8)->(3,9), (4,8)->(4,9), (5,8)->(5,9), (6,8)->(6,9)
row 09: (0,9)->(0,10), (2,9)->(2,10), (3,9)->(2,10), (4,9)->(4,10), (5,9)->(5,10), (6,9)->(5,10), (6,9)->(6,10)
row 10: (0,10)->(0,11), (2,10)->(3,11), (4,10)->(5,11), (5,10)->(5,11), (6,10)->(6,11)
row 11: (0,11)->(0,12), (3,11)->(2,12), (3,11)->(3,12), (5,11)->(4,12), (5,11)->(6,12), (6,11)->(6,12)
row 12: (0,12)->(0,13), (2,12)->(3,13), (3,12)->(3,13), (4,12)->(3,13), (4,12)->(5,13), (6,12)->(5,13), (6,12)->(6,13)
row 13: (0,13)->(0,14), (3,13)->(3,14), (5,13)->(5,14), (6,13)->(6,14)
row 14: (0,14)->(3,15), (3,14)->(3,15), (5,14)->(3,15), (6,14)->(3,15)
```

### TODO
+ fix Boss Rng selector
+ add interface
+ add Deck Potion Monster and Relic sequence interface
