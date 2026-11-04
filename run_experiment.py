"""Run reproducible P0-P3 x R0-R3 SUMO experiments from Phase 0 assets.

Example: python run_experiment.py --share 0.7 --flow high --seed 42 --p P3 --r R3 --gui
"""
import argparse
import csv
import json
import shutil
from dataclasses import replace
from pathlib import Path

from config import BUILD, RESULTS, Scenario
from build_network import generate_network
from generate_demand import generate_routes
from verify_seepage import load_traci
from controllers import Controller
from metrics import Metrics, write_dict_csv


def run_one(s, p, r, gui=False, replay=True):
    traci = load_traci()
    binary = shutil.which('sumo-gui' if gui else 'sumo')
    if not binary:
        raise RuntimeError('SUMO not found on PATH')
    tag = f'share_{int(s.two_wheeler_share*100):02d}_flow_{s.flow_level}_seed_{s.seed}_{p}_{r}'
    folder = RESULTS / tag
    folder.mkdir(parents=True, exist_ok=True)
    command = [binary, '-n', str(BUILD/'corridor.net.xml'),
               '-r', str(BUILD/'demand.rou.xml'),
               '--step-length', str(s.step_s),
               '--lateral-resolution', str(s.lateral_resolution_m),
               '--seed', str(s.seed), '--time-to-teleport', '-1',
               '--collision.action', 'warn', '--no-step-log', 'true',
               '--end', str(s.duration_s+s.clearance_s),
               '--tripinfo-output', str(folder/'tripinfo.xml')]
    if gui:
        command += ['--start', 'true', '--quit-on-end', 'true', '--delay', '20']
    traci.start(command)
    states, trace, queues = [], [], []
    try:
        ctrl = Controller(traci, s, p, r)
        mt = Metrics(traci, s)
        while traci.simulation.getTime() < s.duration_s + s.clearance_s:
            traci.simulationStep()
            now = traci.simulation.getTime()
            ctrl.step(now)
            mt.step(now)
            if replay:
                for tlid in traci.trafficlight.getIDList():
                    states.append((round(now, 2), tlid,
                                   traci.trafficlight.getRedYellowGreenState(tlid)))
                # Lightweight replay records all vehicles at 1-second resolution.
                if round(now / s.step_s) % max(1, round(1/s.step_s)) == 0:
                    for vid in traci.vehicle.getIDList():
                        x, y = traci.vehicle.getPosition(vid)
                        trace.append((round(now, 2), vid,
                                      traci.vehicle.getTypeID(vid),
                                      round(x, 2), round(y, 2),
                                      round(traci.vehicle.getSpeed(vid), 2),
                                      round(traci.vehicle.getLateralLanePosition(vid), 2)))
            # Background vehicles may persist beyond end; final result is censored.
        result = mt.summary(ctrl, p, r, s)
        result['tag'] = tag
        result['ev_completed'] = int(ctrl.ev_arrived)
        result['sim_end_s'] = s.duration_s + s.clearance_s
        # Report recovery POLICY duration only; baseline-relative recovery requires
        # comparison against P0 queue histories in analysis.py.
        with (folder/'controller_events.csv').open('w', newline='') as f:
            w=csv.writer(f)
            w.writerow(['time_s','junction','event','preemption','recovery','details'])
            w.writerows(ctrl.events)
        with (folder/'ev_trace.csv').open('w', newline='') as f:
            w=csv.writer(f)
            w.writerow(['time_s','x','y','speed_mps','edge'])
            w.writerows(ctrl.ev_trace)
        with (folder/'queue_series.csv').open('w', newline='') as f:
            w=csv.writer(f)
            w.writerow(['time_s']+[f'J{j}_queue' for j in range(1,s.intersections+1)])
            w.writerows(mt.queue_series)
        if replay:
            with (folder/'signals.csv').open('w', newline='') as f:
                w=csv.writer(f); w.writerow(['time_s','junction','state']); w.writerows(states)
            with (folder/'positions.csv').open('w', newline='') as f:
                w=csv.writer(f)
                w.writerow(['time_s','vehicle','type','x','y','speed_mps','lateral_m'])
                w.writerows(trace)
        (folder/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        return result
    finally:
        traci.close()


def main():
    a=argparse.ArgumentParser()
    a.add_argument('--share',type=float,default=.7)
    a.add_argument('--flow',choices=['low','medium','high'],default='high')
    a.add_argument('--seed',type=int,default=42)
    a.add_argument('--ev-time',type=float,default=360)
    a.add_argument('--p',choices=['P0','P1','P2','P3'],default='P3')
    a.add_argument('--r',choices=['R0','R1','R2','R3'],default='R3')
    a.add_argument('--gui',action='store_true')
    a.add_argument('--no-replay',action='store_true')
    args=a.parse_args()
    s=replace(Scenario(),two_wheeler_share=args.share,flow_level=args.flow,
              seed=args.seed,ev_depart_s=args.ev_time)
    generate_network(s)
    generate_routes(s)
    result=run_one(s,args.p,args.r,args.gui,not args.no_replay)
    write_dict_csv(RESULTS/'latest_run.csv',[result])
    print(json.dumps(result,indent=2))
    print('Run folder:',RESULTS/result['tag'])

if __name__=='__main__':
    main()
