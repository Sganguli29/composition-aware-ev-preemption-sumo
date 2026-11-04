"""Convenient single command to build, seed and execute Phase 0."""
import argparse
from dataclasses import replace
from config import Scenario
from build_network import generate_network
from generate_demand import generate_routes
from verify_seepage import simulate

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--share', type=float, default=0.55)
    p.add_argument('--flow', choices=['low', 'medium', 'high'], default='high')
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--ev-time', type=float, default=360.0)
    p.add_argument('--gui', action='store_true')
    p.add_argument('--limit', type=float)
    a = p.parse_args()
    s = replace(Scenario(), two_wheeler_share=a.share, flow_level=a.flow,
                seed=a.seed, ev_depart_s=a.ev_time)
    generate_network(s)
    generate_routes(s)
    simulate(a.gui, s, a.limit)
