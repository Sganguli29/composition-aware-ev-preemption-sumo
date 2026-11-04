"""Generate seeded mixed-traffic arrivals, plus one fixed-route ambulance."""
import argparse
import csv
import math
import random
import xml.etree.ElementTree as ET
from dataclasses import replace
from config import (BUILD, CROSS_FRACTION, FLOW_VPH_PER_DIRECTION,
                    OTHER_MIX, Scenario, VEHICLE_TYPES)


def weighted_class(rng, share):
    if rng.random() < share:
        return 'two_wheeler'
    u = rng.random()
    running = 0.0
    for name, prob in OTHER_MIX.items():
        running += prob
        if u < running:
            return name
    return 'car'


def poisson_departures(rng, rate_per_hour, duration):
    t = 0.0
    while rate_per_hour > 0:
        t += rng.expovariate(rate_per_hour / 3600.0)
        if t >= duration:
            break
        yield t


def route_edges(s, i, direction):
    if direction == 'east':
        nodes = ['W'] + [f'J{j}' for j in range(1, s.intersections + 1)] + ['E']
    elif direction == 'west':
        nodes = ['E'] + [f'J{j}' for j in range(s.intersections, 0, -1)] + ['W']
    elif direction == 'ns':
        nodes = [f'N{i}', f'J{i}', f'S{i}']
    else:
        nodes = [f'S{i}', f'J{i}', f'N{i}']
    return ' '.join(f'{a}_{b}' for a, b in zip(nodes, nodes[1:]))


def generate_routes(s):
    if not 0 <= s.two_wheeler_share <= 1:
        raise ValueError('two_wheeler_share must be between 0 and 1')
    if s.flow_level not in FLOW_VPH_PER_DIRECTION:
        raise ValueError(f'unknown flow level: {s.flow_level}')
    BUILD.mkdir(parents=True, exist_ok=True)
    rng = random.Random(s.seed)
    root = ET.Element('routes')
    for name, attrs in VEHICLE_TYPES.items():
        params = {k: str(v) for k, v in attrs.items()}
        params.update(id=name, carFollowModel='Krauss', laneChangeModel='SL2015')
        ET.SubElement(root, 'vType', params)
    paths = {'east': route_edges(s, 0, 'east'),
             'west': route_edges(s, 0, 'west')}
    for i in range(1, s.intersections + 1):
        for direction in ('ns', 'sn'):
            paths[f'{direction}{i}'] = route_edges(s, i, direction)
    for name, edges in paths.items():
        ET.SubElement(root, 'route', id=name, edges=edges)
    volume = FLOW_VPH_PER_DIRECTION[s.flow_level]
    all_vehicles = []
    for direction in ('east', 'west'):
        for t in poisson_departures(rng, volume, s.duration_s):
            all_vehicles.append((t, direction, weighted_class(rng, s.two_wheeler_share)))
    for i in range(1, s.intersections + 1):
        for direction in ('ns', 'sn'):
            for t in poisson_departures(rng, volume * CROSS_FRACTION, s.duration_s):
                all_vehicles.append((t, f'{direction}{i}', weighted_class(rng, s.two_wheeler_share)))
    all_vehicles.append((s.ev_depart_s, 'east', 'ambulance'))
    all_vehicles.sort(key=lambda item: (item[0], item[2] != 'ambulance'))
    manifest = BUILD / 'departures.csv'
    with manifest.open('w', newline='', encoding='utf-8') as fp:
        wr = csv.writer(fp)
        wr.writerow(['id', 'depart_s', 'route', 'type'])
        for j, (t, route, kind) in enumerate(all_vehicles):
            veh_id = 'EV_001' if kind == 'ambulance' else f'bg_{j:07d}'
            ET.SubElement(root, 'vehicle', dict(id=veh_id, type=kind, route=route,
                          depart=f'{t:.2f}', departLane='best', departSpeed='max'))
            wr.writerow([veh_id, f'{t:.2f}', route, kind])
    route_file = BUILD / 'demand.rou.xml'
    ET.indent(root, space='  ')
    ET.ElementTree(root).write(route_file, encoding='utf-8', xml_declaration=True)
    print('Routes written:', route_file, '| demand rows:', len(all_vehicles))
    return route_file


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--share', type=float, default=0.55)
    p.add_argument('--flow', choices=list(FLOW_VPH_PER_DIRECTION), default='high')
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--ev-time', type=float, default=360.0)
    a = p.parse_args()
    generate_routes(replace(Scenario(), two_wheeler_share=a.share, flow_level=a.flow,
                            seed=a.seed, ev_depart_s=a.ev_time))
