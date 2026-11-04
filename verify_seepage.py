"""Run Phase 0 P0 fixed-time simulation and log lateral filtering evidence."""
import argparse
import csv
import json
import os
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from config import BUILD, RESULTS, Scenario


def load_traci():
    # Use SUMO's supported Python tooling with or without pip traci installed.
    try:
        import traci
        return traci
    except ImportError:
        home = os.environ.get('SUMO_HOME')
        if not home:
            raise SystemExit('Install `pip install traci` or set SUMO_HOME.')
        sys.path.insert(0, str(Path(home) / 'tools'))
        import traci
        return traci


def simulate(gui, s, limit=None):
    traci = load_traci()
    exe = shutil.which('sumo-gui' if gui else 'sumo')
    if not exe:
        raise SystemExit('SUMO executable missing from PATH (sumo or sumo-gui).')
    RESULTS.mkdir(parents=True, exist_ok=True)
    pos_path = RESULTS / 'positions.csv'
    signal_path = RESULTS / 'signals.csv'
    events_path = RESULTS / 'seepage_events.csv'
    summary_path = RESULTS / 'seepage_summary.json'
    cmd = [exe, '-n', str(BUILD / 'corridor.net.xml'),
           '-r', str(BUILD / 'demand.rou.xml'),
           '--step-length', str(s.step_s),
           '--lateral-resolution', str(s.lateral_resolution_m),
           '--seed', str(s.seed),
           '--time-to-teleport', '-1',
           '--collision.action', 'warn',
           '--no-step-log', 'true',
           '--end', str(s.duration_s + s.clearance_s),
           '--tripinfo-output', str(RESULTS / 'tripinfo.xml')]
    if gui:
        cmd += ['--start', 'true', '--quit-on-end', 'true', '--delay', '40']
    traci.start(cmd)
    summary = Counter()
    # Pair memory tracks order reversal of each bike/car pair on the same edge.
    previous_order = {}
    counted_pairs = set()
    seen_offset = set()
    seen_bikes = set()
    try:
        with (pos_path.open('w', newline='') as pf,
              signal_path.open('w', newline='') as sf,
              events_path.open('w', newline='') as ef):
            pos = csv.writer(pf)
            tls = csv.writer(sf)
            events = csv.writer(ef)
            pos.writerow(['time_s', 'vehicle_id', 'type', 'edge', 'lane',
                          'lane_position_m', 'lateral_position_m', 'speed_mps',
                          'x', 'y'])
            tls.writerow(['time_s', 'tls_id', 'phase', 'state'])
            events.writerow(['time_s', 'bike_id', 'car_id', 'edge',
                             'bike_lane', 'car_lane', 'bike_lateral_m',
                             'car_lateral_m', 'evidence'])
            end = limit or (s.duration_s + s.clearance_s)
            while traci.simulation.getTime() < end:
                traci.simulationStep()
                now = traci.simulation.getTime()
                for tlid in traci.trafficlight.getIDList():
                    tls.writerow([round(now, 2), tlid,
                                  traci.trafficlight.getPhase(tlid),
                                  traci.trafficlight.getRedYellowGreenState(tlid)])
                edge_vehicles = defaultdict(lambda: {'two_wheeler': [], 'car': []})
                current_pairs = set()
                for vid in traci.vehicle.getIDList():
                    kind = traci.vehicle.getTypeID(vid)
                    edge = traci.vehicle.getRoadID(vid)
                    lane = traci.vehicle.getLaneID(vid)
                    longitudinal = traci.vehicle.getLanePosition(vid)
                    lateral = traci.vehicle.getLateralLanePosition(vid)
                    speed = traci.vehicle.getSpeed(vid)
                    x, y = traci.vehicle.getPosition(vid)
                    pos.writerow([round(now, 2), vid, kind, edge, lane,
                                  round(longitudinal, 3), round(lateral, 3),
                                  round(speed, 3), round(x, 3), round(y, 3)])
                    if kind == 'two_wheeler':
                        seen_bikes.add(vid)
                        if abs(lateral) >= 0.35:
                            seen_offset.add(vid)
                        if speed >= 0.8 and abs(lateral) >= 0.35:
                            summary['moving_laterally_offset_observations'] += 1
                    if kind in ('two_wheeler', 'car') and not edge.startswith(':'):
                        edge_vehicles[edge][kind].append((vid, lane, longitudinal,
                                                           lateral, speed))
                # Compare bikes and cars on each edge; same-lane reversals are
                # conservative evidence of filtering, rather than mere lane changes.
                for edge, kinds in edge_vehicles.items():
                    for bike in kinds['two_wheeler']:
                        for car in kinds['car']:
                            bid, blane, bpos, blat, bspeed = bike
                            cid, clane, cpos, clat, cspeed = car
                            if blane != clane or abs(bpos - cpos) > 18:
                                continue
                            key = (bid, cid, edge)
                            current_pairs.add(key)
                            old = previous_order.get(key)
                            diff = bpos - cpos
                            if (old is not None and old < -0.1 and diff > 0.1
                                    and key not in counted_pairs):
                                counted_pairs.add(key)
                                summary['same_lane_motorcycle_car_passes'] += 1
                                events.writerow([round(now, 2), bid, cid, edge,
                                                blane, clane, round(blat, 3),
                                                round(clat, 3), 'order_reversal'])
                            previous_order[key] = diff
                # Keep pair state briefly across steps but discard pairs once gone.
                previous_order = {key: val for key, val in previous_order.items()
                                  if key in current_pairs}
    finally:
        traci.close()
    summary['motorcycles_seen'] = len(seen_bikes)
    summary['motorcycles_with_035m_lateral_offset'] = len(seen_offset)
    summary['same_lane_pass_events'] = len(counted_pairs)
    summary['sublane_resolution_m'] = s.lateral_resolution_m
    summary_path.write_text(json.dumps(dict(summary), indent=2), encoding='utf-8')
    print(json.dumps(dict(summary), indent=2))
    print('Trace:', pos_path)
    print('Signals:', signal_path)
    print('Seepage events:', events_path)
    if not counted_pairs:
        print('NOTE: no conservative same-lane pass was detected; inspect trace/GUI '
              'and tune demand and calibration before claiming seepage is verified.')
    return summary


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--gui', action='store_true')
    p.add_argument('--limit', type=float, default=None)
    args = p.parse_args()
    simulate(args.gui, Scenario(), args.limit)
