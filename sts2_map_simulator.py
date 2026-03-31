
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional, Set, Tuple


# ---------- StringHelper ----------

def deterministic_hash_code(s: str) -> int:
    num = 352654597
    num2 = num
    for i in range(0, len(s), 2):
        num = ((num << 5) + num) ^ ord(s[i])
        num &= 0xFFFFFFFF
        if i == len(s) - 1:
            break
        num2 = ((num2 << 5) + num2) ^ ord(s[i + 1])
        num2 &= 0xFFFFFFFF
    result = (num + num2 * 1566083941) & 0xFFFFFFFF
    # convert to signed 32-bit int like C#
    if result >= 0x80000000:
        result -= 0x100000000
    return result


# ---------- .NET-compatible seeded Random(int) ----------

MBIG = 2147483647
MSEED = 161803398


class DotNetRandom:
    """
    Compatible with the classic seeded System.Random(int seed) behavior used by
    seeded Random instances for deterministic sequences.
    """

    def __init__(self, seed: int):
        self.inext = 0
        self.inextp = 21
        self.seed_array = [0] * 56

        subtraction = abs(seed)
        if subtraction == 2147483648:
            subtraction = MBIG
        mj = MSEED - subtraction
        if mj < 0:
            mj += MBIG
        self.seed_array[55] = mj
        mk = 1
        for i in range(1, 55):
            ii = (21 * i) % 55
            self.seed_array[ii] = mk
            mk = mj - mk
            if mk < 0:
                mk += MBIG
            mj = self.seed_array[ii]
        for _ in range(4):
            for i in range(1, 56):
                self.seed_array[i] -= self.seed_array[1 + (i + 30) % 55]
                if self.seed_array[i] < 0:
                    self.seed_array[i] += MBIG

    def _internal_sample(self) -> int:
        loc_inext = self.inext + 1
        if loc_inext >= 56:
            loc_inext = 1
        loc_inextp = self.inextp + 1
        if loc_inextp >= 56:
            loc_inextp = 1

        ret = self.seed_array[loc_inext] - self.seed_array[loc_inextp]
        if ret == MBIG:
            ret -= 1
        if ret < 0:
            ret += MBIG

        self.seed_array[loc_inext] = ret
        self.inext = loc_inext
        self.inextp = loc_inextp
        return ret

    def sample(self) -> float:
        return self._internal_sample() * (1.0 / MBIG)

    def next(self, *args: int) -> int:
        if len(args) == 0:
            return self._internal_sample()
        if len(args) == 1:
            max_exclusive = args[0]
            if max_exclusive < 0:
                raise ValueError("maxExclusive must be non-negative")
            return int(self.sample() * max_exclusive)
        if len(args) == 2:
            min_inclusive, max_exclusive = args
            if min_inclusive >= max_exclusive:
                raise ValueError("minInclusive must be lower than maximum")
            diff = max_exclusive - min_inclusive
            return int(self.sample() * diff) + min_inclusive
        raise TypeError("next() takes 0, 1, or 2 integer arguments")

    def next_double(self) -> float:
        return self.sample()


# ---------- RNG ----------

class Rng:
    def __init__(self, seed: int = 0, counter: int = 0, name: Optional[str] = None):
        if name is not None:
            seed = (seed + deterministic_hash_code(name)) & 0xFFFFFFFF
        self.counter = 0
        self.seed = seed & 0xFFFFFFFF
        signed_seed = self.seed if self.seed < 0x80000000 else self.seed - 0x100000000
        self._random = DotNetRandom(signed_seed)
        self.fast_forward_counter(counter)

    def fast_forward_counter(self, target_count: int) -> None:
        if self.counter > target_count:
            raise ValueError("Cannot fast-forward an Rng counter to a lower number")
        while self.counter < target_count:
            self.counter += 1
            self._random.next()

    def next_bool(self) -> bool:
        self.counter += 1
        return self._random.next(2) == 0

    def next_int(self, *args: int) -> int:
        self.counter += 1
        return self._random.next(*args)

    def next_double(self, min_val: Optional[float] = None, max_val: Optional[float] = None) -> float:
        self.counter += 1
        if min_val is None and max_val is None:
            return self._random.next_double()
        if min_val is None or max_val is None:
            raise ValueError("Provide both min and max or neither")
        if min_val > max_val:
            raise ValueError("Minimum must not be higher than maximum")
        return self._random.next_double() * (max_val - min_val) + min_val

    def next_gaussian_int(self, mean: int, std_dev: int, min_val: int, max_val: int) -> int:
        while True:
            d = 1.0 - self._random.next_double()
            num = 1.0 - self._random.next_double()
            num2 = math.sqrt(-2.0 * math.log(d)) * math.sin(math.pi * 2.0 * num)
            a = mean + std_dev * num2
            n = int(round(a))
            if min_val <= n <= max_val:
                return n


# ---------- Map model ----------

class MapPointType(IntEnum):
    Unassigned = 0
    Unknown = 1
    Shop = 2
    Treasure = 3
    RestSite = 4
    Monster = 5
    Elite = 6
    Boss = 7
    Ancient = 8


@dataclass(order=True, frozen=False)
class MapCoord:
    col: int
    row: int


@dataclass
class MapPoint:
    coord: MapCoord
    can_be_modified: bool = True
    point_type: MapPointType = MapPointType.Unassigned
    parents: Set["MapPoint"] = field(default_factory=set)
    children: Set["MapPoint"] = field(default_factory=set)

    def __hash__(self) -> int:
        return hash((self.coord.col, self.coord.row))

    def add_child(self, child: "MapPoint") -> None:
        self.children.add(child)
        child.parents.add(self)

    def remove_child(self, child: "MapPoint") -> None:
        if child in self.children:
            self.children.remove(child)
            child.parents.discard(self)

    def bfs_find_path(self, target: "MapPoint") -> List["MapPoint"]:
        queue = [self]
        parent: Dict[MapPoint, MapPoint] = {}
        idx = 0
        while idx < len(queue):
            cur = queue[idx]
            idx += 1
            if cur == target:
                return self._build_path(parent, target)
            for child in cur.children:
                if child not in parent:
                    parent[child] = cur
                    queue.append(child)
        return []

    def _build_path(self, parent: Dict["MapPoint", "MapPoint"], target: "MapPoint") -> List["MapPoint"]:
        path = []
        cur = target
        while cur != self:
            path.append(cur)
            cur = parent[cur]
        path.append(self)
        path.reverse()
        return path


# ---------- Shuffle helpers ----------

def unstable_shuffle(lst: List, rng: Rng) -> List:
    num = len(lst)
    while num > 1:
        num -= 1
        num2 = rng.next_int(num + 1)
        lst[num2], lst[num] = lst[num], lst[num2]
    return lst


def _stable_sort_key(x):
    if isinstance(x, MapPoint):
        return (x.coord.col, x.coord.row)
    if isinstance(x, MapCoord):
        return (x.col, x.row)
    return x

def stable_shuffle(lst: List, rng: Rng) -> List:
    lst2 = list(lst)
    lst2.sort(key=_stable_sort_key)
    for i in range(len(lst)):
        lst[i] = lst2[i]
    return unstable_shuffle(lst, rng)


# ---------- Counts / acts ----------

@dataclass
class MapPointTypeCounts:
    num_of_elites: int
    num_of_shops: int
    num_of_unknowns: int
    num_of_rests: int
    ignore_rules_for: Set[MapPointType] = field(default_factory=set)

    @classmethod
    def base(cls, rng: Rng, swarming_elites: bool = False) -> "MapPointTypeCounts":
        elites = round(5.0 * (1.6 if swarming_elites else 1.0))
        return cls(
            num_of_elites=int(elites),
            num_of_shops=3,
            num_of_unknowns=rng.next_gaussian_int(12, 1, 10, 14),
            num_of_rests=rng.next_gaussian_int(5, 1, 3, 6),
        )

    def should_ignore_rules(self, point_type: MapPointType) -> bool:
        return point_type in self.ignore_rules_for


@dataclass
class ActSpec:
    name: str
    base_rooms: int
    bosses: List[str]

    def get_number_of_rooms(self, is_multiplayer: bool) -> int:
        n = self.base_rooms
        if is_multiplayer:
            n -= 1
        return n

    def get_map_point_types(
        self, map_rng: Rng, gloom: bool = False, swarming_elites: bool = False
    ) -> MapPointTypeCounts:
        if self.name in ("Overgrowth", "Underdocks"):
            num = map_rng.next_gaussian_int(7, 1, 6, 7)
            if gloom:
                num -= 1
            counts = MapPointTypeCounts.base(map_rng, swarming_elites=swarming_elites)
            counts.num_of_rests = num
            return counts

        if self.name == "Hive":
            rng_copy = Rng(map_rng.seed, map_rng.counter)
            baseline = MapPointTypeCounts.base(rng_copy, swarming_elites=swarming_elites)
            num = map_rng.next_gaussian_int(6, 1, 6, 7)
            if gloom:
                num -= 1
            counts = MapPointTypeCounts.base(map_rng, swarming_elites=swarming_elites)
            counts.num_of_unknowns = baseline.num_of_unknowns - 1
            counts.num_of_rests = num
            return counts

        if self.name == "Glory":
            rng_copy = Rng(map_rng.seed, map_rng.counter)
            baseline = MapPointTypeCounts.base(rng_copy, swarming_elites=swarming_elites)
            num = map_rng.next_int(5, 7)
            if gloom:
                num -= 1
            counts = MapPointTypeCounts.base(map_rng, swarming_elites=swarming_elites)
            counts.num_of_unknowns = baseline.num_of_unknowns - 1
            counts.num_of_rests = num
            return counts

        raise ValueError(f"Unsupported act: {self.name}")


ACTS: Dict[str, ActSpec] = {
    "overgrowth": ActSpec("Overgrowth", 15, [
        "VantomBoss",
        "CeremonialBeastBoss",
        "TheKinBoss",
    ]),
    "underdocks": ActSpec("Underdocks", 15, [
        "WaterfallGiantBoss",
        "SoulFyshBoss",
        "LagavulinMatriarchBoss",
    ]),
    "hive": ActSpec("Hive", 14, [
        "TheInsatiableBoss",
        "KnowledgeDemonBoss",
        "KaiserCrabBoss",
    ]),
    "glory": ActSpec("Glory", 13, [
        "QueenBoss",
        "TestSubjectBoss",
        "DoormakerBoss",
    ]),
}


# ---------- StandardActMap ----------

LOWER_RESTRICT = {MapPointType.RestSite, MapPointType.Elite}
UPPER_RESTRICT = {MapPointType.RestSite}
PARENT_RESTRICT = {MapPointType.Elite, MapPointType.RestSite, MapPointType.Treasure, MapPointType.Shop}
CHILD_RESTRICT = {MapPointType.Elite, MapPointType.RestSite, MapPointType.Treasure, MapPointType.Shop}
SIBLING_RESTRICT = {MapPointType.RestSite, MapPointType.Monster, MapPointType.Unknown, MapPointType.Elite, MapPointType.Shop}


class StandardActMap:
    def __init__(
        self,
        map_rng: Rng,
        act: ActSpec,
        is_multiplayer: bool = False,
        replace_treasure_with_elites: bool = False,
        has_second_boss: bool = False,
        gloom: bool = False,
        swarming_elites: bool = False,
        enable_pruning: bool = True,
    ):
        self._map_length = act.get_number_of_rooms(is_multiplayer) + 1
        self.grid: List[List[Optional[MapPoint]]] = [[None for _ in range(self._map_length)] for _ in range(7)]
        self._rng = map_rng
        self._point_type_counts = act.get_map_point_types(map_rng, gloom=gloom, swarming_elites=swarming_elites)
        self.should_replace_treasure_with_elites = replace_treasure_with_elites
        self.start_map_points: Set[MapPoint] = set()
        self.boss_map_point = MapPoint(MapCoord(self.get_column_count() // 2, self.get_row_count()), point_type=MapPointType.Unassigned)
        self.starting_map_point = MapPoint(MapCoord(self.get_column_count() // 2, 0), point_type=MapPointType.Unassigned)
        self.second_boss_map_point = (
            MapPoint(MapCoord(self.get_column_count() // 2, self.get_row_count() + 1), point_type=MapPointType.Unassigned)
            if has_second_boss else None
        )

        self.generate_map()
        self.assign_point_types()
        if enable_pruning:
            prune_duplicate_segments(self.grid, self.start_map_points, self.starting_map_point, self._rng)
        self.grid = center_grid(self.grid)
        self.grid = spread_adjacent_map_points(self.grid)
        self.grid = straighten_paths(self.grid)

    def get_column_count(self) -> int:
        return len(self.grid)

    def get_row_count(self) -> int:
        return len(self.grid[0])

    def get_all_map_points(self) -> List[MapPoint]:
        out = []
        for c in range(self.get_column_count()):
            for r in range(self.get_row_count()):
                p = self.grid[c][r]
                if p is not None:
                    out.append(p)
        return out

    def get_point(self, col: int, row: int) -> Optional[MapPoint]:
        if (col, row) == (self.boss_map_point.coord.col, self.boss_map_point.coord.row):
            return self.boss_map_point
        if self.second_boss_map_point and (col, row) == (self.second_boss_map_point.coord.col, self.second_boss_map_point.coord.row):
            return self.second_boss_map_point
        if (col, row) == (self.starting_map_point.coord.col, self.starting_map_point.coord.row):
            return self.starting_map_point
        if 0 <= col < self.get_column_count() and 0 <= row < self.get_row_count():
            return self.grid[col][row]
        return None

    def get_or_create_point(self, col: int, row: int) -> MapPoint:
        p = self.get_point(col, row)
        if p is not None:
            return p
        p = MapPoint(MapCoord(col, row))
        self.grid[col][row] = p
        return p

    def path_generate(self, starting_point: MapPoint) -> None:
        p = starting_point
        while p.coord.row < self._map_length - 1:
            coord = self.generate_next_coord(p)
            nxt = self.get_or_create_point(coord.col, coord.row)
            p.add_child(nxt)
            p = nxt

    def generate_next_coord(self, current: MapPoint) -> MapCoord:
        col = current.coord.col
        left = max(0, col - 1)
        right = min(col + 1, 6)
        dirs = [-1, 0, 1]
        stable_shuffle(dirs, self._rng)
        for item in dirs:
            row = current.coord.row + 1
            target = left if item == -1 else col if item == 0 else right
            if not self.has_invalid_crossover(current, target):
                return MapCoord(target, row)
        raise RuntimeError(f"Cannot find next node: seed={self._rng.seed}")

    def has_invalid_crossover(self, current: MapPoint, target_x: int) -> bool:
        delta = target_x - current.coord.col
        if delta == 0 or delta == 7:
            return False
        p = self.grid[target_x][current.coord.row]
        if p is None:
            return False
        for child in p.children:
            delta2 = child.coord.col - p.coord.col
            if delta2 == -delta:
                return True
        return False

    def generate_map(self) -> None:
        for i in range(7):
            p = self.get_or_create_point(self._rng.next_int(0, 7), 1)
            if i == 1:
                while p in self.start_map_points:
                    p = self.get_or_create_point(self._rng.next_int(0, 7), 1)
            self.start_map_points.add(p)
            self.path_generate(p)

        for x in self.points_in_row(self.get_row_count() - 1):
            x.add_child(self.boss_map_point)
        if self.second_boss_map_point is not None:
            self.boss_map_point.add_child(self.second_boss_map_point)
        for x in self.points_in_row(1):
            self.starting_map_point.add_child(x)

    def points_in_row(self, row_index: int) -> List[MapPoint]:
        out = []
        for i in range(self.get_column_count()):
            p = self.grid[i][row_index]
            if p is not None:
                out.append(p)
        return out

    def assign_point_types(self) -> None:
        for p in self.points_in_row(self.get_row_count() - 1):
            p.point_type = MapPointType.RestSite
            p.can_be_modified = False

        special_row = self.get_row_count() - 7
        for p in self.points_in_row(special_row):
            p.point_type = MapPointType.Elite if self.should_replace_treasure_with_elites else MapPointType.Treasure
            p.can_be_modified = False

        for p in self.points_in_row(1):
            p.point_type = MapPointType.Monster

        items: List[MapPointType] = []
        items += [MapPointType.RestSite] * self._point_type_counts.num_of_rests
        items += [MapPointType.Shop] * self._point_type_counts.num_of_shops
        items += [MapPointType.Elite] * self._point_type_counts.num_of_elites
        items += [MapPointType.Unknown] * self._point_type_counts.num_of_unknowns
        queue = items[:]
        self.assign_remaining_types_to_random_points(queue)

        for p in self.get_all_map_points():
            if p.point_type == MapPointType.Unassigned:
                p.point_type = MapPointType.Monster

        self.boss_map_point.point_type = MapPointType.Boss
        self.starting_map_point.point_type = MapPointType.Ancient
        if self.second_boss_map_point is not None:
            self.second_boss_map_point.point_type = MapPointType.Boss

    def assign_remaining_types_to_random_points(self, queue: List[MapPointType]) -> None:
        pts = self.get_all_map_points()
        stable_shuffle(pts, self._rng)
        for p in [x for x in pts if x.point_type == MapPointType.Unassigned]:
            p.point_type = self.get_next_valid_point_type(queue, p)

    def get_next_valid_point_type(self, queue: List[MapPointType], map_point: MapPoint) -> MapPointType:
        original_count = len(queue)
        for _ in range(original_count):
            t = queue.pop(0)
            if self._point_type_counts.should_ignore_rules(t):
                return t
            if self.is_valid_point_type(t, map_point):
                return t
            queue.append(t)
        return MapPointType.Unassigned

    def is_valid_point_type(self, point_type: MapPointType, map_point: MapPoint) -> bool:
        return (
            self.is_valid_for_upper(point_type, map_point)
            and self.is_valid_for_lower(point_type, map_point)
            and self.is_valid_with_parents(point_type, map_point)
            and self.is_valid_with_children(point_type, map_point)
            and self.is_valid_with_siblings(point_type, map_point)
        )

    @staticmethod
    def is_valid_for_lower(point_type: MapPointType, map_point: MapPoint) -> bool:
        return point_type not in LOWER_RESTRICT if map_point.coord.row < 5 else True

    def is_valid_for_upper(self, point_type: MapPointType, map_point: MapPoint) -> bool:
        return point_type not in UPPER_RESTRICT if map_point.coord.row >= self._map_length - 3 else True

    @staticmethod
    def is_valid_with_parents(point_type: MapPointType, map_point: MapPoint) -> bool:
        if point_type in PARENT_RESTRICT:
            return all(point_type != p.point_type for p in list(map_point.parents) + list(map_point.children))
        return True

    @staticmethod
    def is_valid_with_children(point_type: MapPointType, map_point: MapPoint) -> bool:
        if point_type in CHILD_RESTRICT:
            return all(point_type != p.point_type for p in map_point.children)
        return True

    @staticmethod
    def get_siblings(map_point: MapPoint) -> List[MapPoint]:
        result = []
        for parent in map_point.parents:
            for child in parent.children:
                if child != map_point:
                    result.append(child)
        return result

    @classmethod
    def is_valid_with_siblings(cls, point_type: MapPointType, map_point: MapPoint) -> bool:
        if point_type in SIBLING_RESTRICT:
            return all(point_type != p.point_type for p in cls.get_siblings(map_point))
        return True


# ---------- Post-processing ----------

def center_grid(grid: List[List[Optional[MapPoint]]]) -> List[List[Optional[MapPoint]]]:
    width = len(grid)
    height = len(grid[0])

    def is_column_empty(col: int) -> bool:
        for r in range(height):
            if grid[col][r] is not None:
                return False
        return True

    left_empty = is_column_empty(0) and is_column_empty(1)
    right_empty = is_column_empty(width - 1) and is_column_empty(width - 2)
    shift = -1 if left_empty and not right_empty else 1 if (not left_empty and right_empty) else 0
    if shift == 0:
        return grid

    if shift > 0:
        for r in range(height):
            for c in range(width - 1, -1, -1):
                p = grid[c][r]
                grid[c][r] = None
                nc = c + shift
                if nc < width:
                    grid[nc][r] = p
                    if p is not None:
                        p.coord.col = nc
    else:
        for r in range(height):
            for c in range(width):
                p = grid[c][r]
                grid[c][r] = None
                nc = c + shift
                if nc >= 0:
                    grid[nc][r] = p
                    if p is not None:
                        p.coord.col = nc
    return grid


def straighten_paths(grid: List[List[Optional[MapPoint]]]) -> List[List[Optional[MapPoint]]]:
    width = len(grid)
    height = len(grid[0])
    for r in range(height):
        for c in range(width):
            p = grid[c][r]
            if p is None or len(p.parents) != 1 or len(p.children) != 1:
                continue
            parent = next(iter(p.parents))
            child = next(iter(p.children))
            left_extreme = p.coord.col < child.coord.col and p.coord.col < parent.coord.col
            right_extreme = p.coord.col > child.coord.col and p.coord.col > parent.coord.col
            if left_extreme and c < width - 1:
                nc = c + 1
                if grid[nc][r] is None:
                    p.coord.col = nc
                    grid[c][r] = None
                    grid[nc][r] = p
            if right_extreme and c > 0:
                nc = c - 1
                if grid[nc][r] is None:
                    p.coord.col = nc
                    grid[c][r] = None
                    grid[nc][r] = p
    return grid


def get_neighbor_allowed_positions(column: int, total_columns: int) -> Set[int]:
    return {column + i for i in (-1, 0, 1) if 0 <= column + i < total_columns}


def get_allowed_positions(node: MapPoint, total_columns: int) -> Set[int]:
    allowed = set(range(total_columns))
    for parent in node.parents:
        allowed &= get_neighbor_allowed_positions(parent.coord.col, total_columns)
    for child in node.children:
        allowed &= get_neighbor_allowed_positions(child.coord.col, total_columns)
    return allowed


def compute_gap(candidate_col: int, row_nodes: List[MapPoint], current_node: MapPoint) -> int:
    best = None
    for node in row_nodes:
        if node != current_node:
            gap = abs(candidate_col - node.coord.col)
            best = gap if best is None else min(best, gap)
    return best if best is not None else 2**31 - 1


def spread_adjacent_map_points(grid: List[List[Optional[MapPoint]]]) -> List[List[Optional[MapPoint]]]:
    width = len(grid)
    height = len(grid[0])
    for r in range(height):
        row_nodes: List[MapPoint] = [grid[c][r] for c in range(width) if grid[c][r] is not None]
        changed = True
        while changed:
            changed = False
            for item in row_nodes:
                col = item.coord.col
                allowed = get_allowed_positions(item, width)
                best_col = col
                best_gap = compute_gap(col, row_nodes, item)
                for candidate in allowed:
                    if candidate != col and (grid[candidate][r] is None or grid[candidate][r] == item):
                        gap = compute_gap(candidate, row_nodes, item)
                        if gap > best_gap:
                            best_col = candidate
                            best_gap = gap
                if best_col != col:
                    grid[col][r] = None
                    grid[best_col][r] = item
                    item.coord.col = best_col
                    changed = True
    return grid


# ---------- Path pruning ----------

def find_all_paths(current: MapPoint) -> List[List[MapPoint]]:
    if current.point_type == MapPointType.Boss:
        return [[current]]
    out: List[List[MapPoint]] = []
    for child in current.children:
        child_paths = find_all_paths(child)
        for path in child_paths:
            out.append([current] + path)
    return out


def is_valid_segment_start_map_point(start: MapPoint) -> bool:
    return start.coord.row == 0 if len(start.children) <= 1 else True


def is_valid_segment_end_map_point(end: MapPoint) -> bool:
    return len(end.parents) >= 2


def overlapping_segment(a: List[MapPoint], b: List[MapPoint]) -> bool:
    if len(a) < 3 or len(b) < 3:
        return False
    for i in range(1, len(a) - 1):
        if a[i] == b[i]:
            return True
    return False


def any_overlapping_segments(existing: List[List[MapPoint]], seg: List[MapPoint]) -> bool:
    return any(overlapping_segment(x, seg) for x in existing)


def generate_segment_key(segment: List[MapPoint]) -> str:
    start = segment[0]
    end = segment[-1]
    if start.coord.row == 0:
        prefix = f"{start.coord.row}-{end.coord.col},{end.coord.row}-"
    else:
        prefix = f"{start.coord.col},{start.coord.row}-{end.coord.col},{end.coord.row}-"
    return prefix + ",".join(str(int(p.point_type)) for p in segment)


def add_segments_to_dict(path: List[MapPoint], segments: Dict[str, List[List[MapPoint]]]) -> None:
    for i in range(len(path) - 1):
        if not is_valid_segment_start_map_point(path[i]):
            continue
        for j in range(2, len(path) - i):
            end = path[i + j]
            if is_valid_segment_end_map_point(end):
                arr = path[i:i + j + 1]
                key = generate_segment_key(arr)
                if key not in segments:
                    segments[key] = [arr]
                elif not any_overlapping_segments(segments[key], arr):
                    segments[key].append(arr)


def find_matching_segments(starting_map_point: MapPoint) -> List[List[List[MapPoint]]]:
    all_paths = find_all_paths(starting_map_point)
    segs: Dict[str, List[List[MapPoint]]] = {}
    for path in all_paths:
        add_segments_to_dict(path, segs)
    return [v for v in segs.values() if len(v) > 1]


def is_in_map(grid: List[List[Optional[MapPoint]]], p: MapPoint) -> bool:
    if grid[p.coord.col][p.coord.row] is None and p.point_type != MapPointType.Ancient:
        return p.point_type == MapPointType.Boss
    return True


def is_removed(grid: List[List[Optional[MapPoint]]], p: MapPoint) -> bool:
    return grid[p.coord.col][p.coord.row] is None


def remove_point(grid: List[List[Optional[MapPoint]]], start_map_points: Set[MapPoint], p: MapPoint) -> None:
    grid[p.coord.col][p.coord.row] = None
    start_map_points.discard(p)
    for child in list(p.children):
        p.remove_child(child)
    for parent in list(p.parents):
        parent.remove_child(p)


def prune_segment(grid: List[List[Optional[MapPoint]]], start_map_points: Set[MapPoint], segment: List[MapPoint]) -> bool:
    result = False
    for i in range(len(segment) - 1):
        p = segment[i]
        if not is_in_map(grid, p):
            return True
        if len(p.children) > 1 or len(p.parents) > 1 or any(len(n.children) == 1 and not is_removed(grid, n) for n in p.parents):
            continue
        source = segment[i:]
        if not any(len(n.children) > 1 and len(n.parents) == 1 for n in source):
            if len(segment[-1].parents) == 1:
                return False
            if not any((c not in segment) and len(c.parents) == 1 for c in p.children):
                remove_point(grid, start_map_points, p)
                result = True
    return result


def prune_all_but_last(grid: List[List[Optional[MapPoint]]], start_map_points: Set[MapPoint], matches: List[List[MapPoint]]) -> int:
    count = 0
    for idx, match in enumerate(matches):
        if idx == len(matches) - 1:
            return count
        if prune_segment(grid, start_map_points, match):
            count += 1
    return count


def break_parent_child_in_segment(segment: List[MapPoint]) -> bool:
    result = False
    for i in range(len(segment) - 1):
        p = segment[i]
        if len(p.children) >= 2:
            nxt = segment[i + 1]
            if len(nxt.parents) != 1:
                p.remove_child(nxt)
                result = True
    return result


def break_parent_child_in_any_segment(matches: List[List[MapPoint]]) -> bool:
    for match in matches:
        if break_parent_child_in_segment(match):
            return True
    return False


def prune_paths(
    grid: List[List[Optional[MapPoint]]],
    start_map_points: Set[MapPoint],
    matching_segments: List[List[List[MapPoint]]],
    rng: Rng,
) -> bool:
    for matching in matching_segments:
        unstable_shuffle(matching, rng)
        if prune_all_but_last(grid, start_map_points, matching) != 0:
            return True
        if break_parent_child_in_any_segment(matching):
            return True
    return False


def prune_duplicate_segments(
    grid: List[List[Optional[MapPoint]]],
    start_map_points: Set[MapPoint],
    starting_map_point: MapPoint,
    rng: Rng,
) -> None:
    loops = 0
    matches = find_matching_segments(starting_map_point)
    while prune_paths(grid, start_map_points, matches, rng):
        loops += 1
        if loops > 50:
            raise RuntimeError(f"Unable to prune matching segments in {loops} iterations")
        matches = find_matching_segments(starting_map_point)


# ---------- Seed helpers / rendering ----------

def run_seed_from_string(seed_str: str) -> int:
    return deterministic_hash_code(seed_str) & 0xFFFFFFFF


POINT_CHAR = {
    MapPointType.Unassigned: "?",
    MapPointType.Unknown: "?",
    MapPointType.Shop: "$",
    MapPointType.Treasure: "T",
    MapPointType.RestSite: "R",
    MapPointType.Monster: "M",
    MapPointType.Elite: "E",
    MapPointType.Boss: "B",
    MapPointType.Ancient: "A",
}

POINT_LABEL = {
    MapPointType.Unassigned: "Unassigned",
    MapPointType.Unknown: "Unknown",
    MapPointType.Shop: "Shop",
    MapPointType.Treasure: "Treasure",
    MapPointType.RestSite: "RestSite",
    MapPointType.Monster: "Monster",
    MapPointType.Elite: "Elite",
    MapPointType.Boss: "Boss",
    MapPointType.Ancient: "Ancient",
}


def render_ascii(m: StandardActMap) -> str:
    lines = []
    rows = m.get_row_count()

    lines.append("Legend: A=Ancient(start)  M=Monster  ?=Unknown  $=Shop  T=Treasure  R=RestSite  E=Elite  B=Boss  .=empty")
    lines.append(f"Special nodes: start=({m.starting_map_point.coord.col},{m.starting_map_point.coord.row}), boss=({m.boss_map_point.coord.col},{m.boss_map_point.coord.row})")
    if m.second_boss_map_point is not None:
        lines.append(f"               second_boss=({m.second_boss_map_point.coord.col},{m.second_boss_map_point.coord.row})")
    lines.append("")
    for r in range(0, rows):
        cells = []
        for c in range(7):
            if r == 0 and c == m.starting_map_point.coord.col:
                cells.append("A")  # ← 关键这一行
            else:
                p = m.grid[c][r]
                cells.append(POINT_CHAR[p.point_type] if p else ".")
        prefix = f"row {r:02d}"
        if r == 0:
            prefix += " (start row)"
        elif r == 1:
            prefix += " (first playable row)"
        elif r == rows - 7:
            prefix += " (special row)"
        elif r == rows - 1:
            prefix += " (pre-boss row)"
        lines.append(f"{prefix:<24} " + " ".join(cells))
    boss_cells = ["."] * 7
    boss_cells[m.boss_map_point.coord.col] = "B"
    lines.append(f"row {m.boss_map_point.coord.row:02d} (boss row)      " + " ".join(boss_cells))
    if m.second_boss_map_point is not None:
        boss2_cells = ["."] * 7
        boss2_cells[m.second_boss_map_point.coord.col] = "B"
        lines.append(f"row {m.second_boss_map_point.coord.row:02d} (2nd boss row) " + " ".join(boss2_cells))
    return "\n".join(lines)


def render_paths(m: StandardActMap) -> str:
    edges_by_row = {}
    pts = [m.starting_map_point] + m.get_all_map_points() + [m.boss_map_point]
    if m.second_boss_map_point is not None:
        pts.append(m.second_boss_map_point)
    for p in pts:
        for child in sorted(p.children, key=lambda x: (x.coord.row, x.coord.col)):
            edges_by_row.setdefault(p.coord.row, []).append((p.coord.col, child.coord.col, child.coord.row))
    lines = ["", "Connections by row:"]
    for row in sorted(edges_by_row):
        segs = []
        for a, b, child_row in edges_by_row[row]:
            segs.append(f"({a},{row})->({b},{child_row})")
        lines.append(f"row {row:02d}: " + ", ".join(segs))
    return "\n".join(lines)


def export_edges(m: StandardActMap) -> List[Tuple[Tuple[int, int], Tuple[int, int], str]]:
    pts = [m.starting_map_point] + m.get_all_map_points() + [m.boss_map_point]
    if m.second_boss_map_point:
        pts.append(m.second_boss_map_point)
    seen = set()
    out = []
    for p in pts:
        for child in p.children:
            key = ((p.coord.col, p.coord.row), (child.coord.col, child.coord.row))
            if key not in seen:
                seen.add(key)
                out.append((key[0], key[1], child.point_type.name))
    out.sort()
    return out




def resolve_first_act(seed_string: str, underdocks_available: bool = True, first_time_underdocks: bool = False, is_multiplayer: bool = False) -> str:
    """
    Mirror ActModel.GetRandomList(seed, unlockState, isMultiplayer) as far as the
    uploaded code allows. Default assumption: Underdocks is available.
    """
    # Default act list is [Overgrowth, Hive, Glory].
    # If Underdocks is available and either "first time" or rng.NextBool(), replace act 1.
    if not underdocks_available:
        return "overgrowth"
    if first_time_underdocks:
        return "underdocks"
    rng = Rng(run_seed_from_string(seed_string))
    return "underdocks" if rng.next_bool() else "overgrowth"


def resolve_act_for_layer(
    seed_string: str,
    layer: int,
    underdocks_available: bool = True,
    first_time_underdocks: bool = False,
    is_multiplayer: bool = False,
) -> tuple[str, int]:
    if layer == 1:
        return resolve_first_act(
            seed_string,
            underdocks_available=underdocks_available,
            first_time_underdocks=first_time_underdocks,
            is_multiplayer=is_multiplayer,
        ), 1
    if layer == 2:
        return "hive", 2
    if layer == 3:
        return "glory", 3
    raise ValueError("layer must be 1, 2, or 3")

def pick_boss_simple(seed_string: str, act_name: str) -> str:
    run_seed = run_seed_from_string(seed_string)
    rng = Rng(run_seed)
    bosses = ACTS[act_name.lower()].bosses
    return bosses[rng.next_int(0, len(bosses))]

def build_map(
    seed_string: str,
    act_name: Optional[str] = None,
    act_index: Optional[int] = None,
    layer: Optional[int] = None,
    is_multiplayer: bool = False,
    replace_treasure_with_elites: bool = False,
    has_second_boss: bool = False,
    gloom: bool = False,
    swarming_elites: bool = False,
    underdocks_available: bool = True,
    first_time_underdocks: bool = False,
) -> tuple[StandardActMap, str, int]:
    if layer is not None:
        act_name, act_index = resolve_act_for_layer(
            seed_string,
            layer,
            underdocks_available=underdocks_available,
            first_time_underdocks=first_time_underdocks,
            is_multiplayer=is_multiplayer,
        )
    if act_name is None or act_index is None:
        raise ValueError("Provide either layer or both act_name and act_index")

    run_seed = run_seed_from_string(seed_string)
    rng = Rng(run_seed, name=f"act_{act_index}_map")
    act = ACTS[act_name.lower()]
    m = StandardActMap(
        rng,
        act,
        is_multiplayer=is_multiplayer,
        replace_treasure_with_elites=replace_treasure_with_elites,
        has_second_boss=has_second_boss,
        gloom=gloom,
        swarming_elites=swarming_elites,
    )
    return m, act_name, act_index


def main() -> None:
    parser = argparse.ArgumentParser(description="STS2 map simulator")
    parser.add_argument("seed", help="8-char alnum seed string")
    parser.add_argument("--layer", type=int, choices=[1, 2, 3], help="Output map for layer 1/2/3. Layer 1 resolves to Overgrowth or Underdocks from the seed.")
    parser.add_argument("--act", choices=["overgrowth", "hive", "glory", "underdocks"], help="Manual act override")
    parser.add_argument("--act-index", type=int, choices=[1, 2, 3, 4], help="Manual act index override")
    parser.add_argument("--multiplayer", action="store_true")
    parser.add_argument("--underdocks-available", dest="underdocks_available", action="store_true", default=True, help="Allow layer 1 to resolve to Underdocks (default: on)")
    parser.add_argument("--no-underdocks-available", dest="underdocks_available", action="store_false", help="Force layer 1 to stay Overgrowth")
    parser.add_argument("--first-time-underdocks", action="store_true", help="Force layer 1 to Underdocks like the first-discovery branch in ActModel.GetRandomList")
    parser.add_argument("--replace-treasure-with-elites", action="store_true")
    parser.add_argument("--second-boss", action="store_true")
    parser.add_argument("--gloom", dest="gloom", action="store_true", default=True, help="Enable AscensionLevel.Gloom effects (default: on)")
    parser.add_argument("--no-gloom", dest="gloom", action="store_false", help="Disable AscensionLevel.Gloom effects")
    parser.add_argument("--swarming-elites", dest="swarming_elites", action="store_true", default=True, help="Enable AscensionLevel.SwarmingElites effects (default: on)")
    parser.add_argument("--no-swarming-elites", dest="swarming_elites", action="store_false", help="Disable AscensionLevel.SwarmingElites effects")
    parser.add_argument("--show-edges", action="store_true")
    args = parser.parse_args()

    if args.layer is None and (args.act is None or args.act_index is None):
        args.layer = 1

    m, resolved_act_name, resolved_act_index = build_map(
        seed_string=args.seed,
        act_name=args.act,
        act_index=args.act_index,
        layer=args.layer,
        is_multiplayer=args.multiplayer,
        replace_treasure_with_elites=args.replace_treasure_with_elites,
        has_second_boss=args.second_boss,
        gloom=args.gloom,
        swarming_elites=args.swarming_elites,
        underdocks_available=args.underdocks_available,
        first_time_underdocks=args.first_time_underdocks,
    )

    print(f"seed_string={args.seed}")
    if args.layer is not None:
        print(f"requested_layer={args.layer}")
    print(f"resolved_act={resolved_act_name}")
    print(f"resolved_act_index={resolved_act_index}")
    print(f"simple_random_boss={pick_boss_simple(args.seed, resolved_act_name)}")
    print(f"run_seed_uint={run_seed_from_string(args.seed)}")
    print(f"act_rng_seed_uint={(run_seed_from_string(args.seed) + deterministic_hash_code(f'act_{resolved_act_index}_map')) & 0xFFFFFFFF}")
    print(render_ascii(m))
    print(render_paths(m))

    if args.show_edges:
        print("\nEdges:")
        for a, b, t in export_edges(m):
            print(f"{a} -> {b} [{t}]")

if __name__ == "__main__":
    main()
