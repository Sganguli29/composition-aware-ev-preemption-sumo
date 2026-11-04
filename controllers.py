"""Phase 1 emergency-priority and post-EV recovery policies.

All parameters are explicit demonstration heuristics, NOT validated control laws.
Eastbound corridor ambulance only. Junction approaches are identified by edge IDs.
"""
from dataclasses import dataclass, field
from collections import Counter
import math

CLASS_WEIGHTS = {'two_wheeler': 0.90, 'car': 2.20, 'auto': 1.70,
                 'bus': 4.70, 'truck': 4.40}


def approach_edge(junction):
    return 'W_J1' if junction == 1 else f'J{junction-1}_J{junction}'


def cross_edges(junction):
    return (f'N{junction}_J{junction}', f'S{junction}_J{junction}')


def queued_vehicles(traci, edges, stop_speed=2.0, inspect_m=140.0):
    """Collect slow vehicles on incoming edges, close to their downstream signals."""
    out = []
    for edge in edges:
        try:
            edge_length = traci.lane.getLength(edge + '_0')
            ids = traci.edge.getLastStepVehicleIDs(edge)
        except Exception:
            continue
        for vid in ids:
            try:
                distance = edge_length - traci.vehicle.getLanePosition(vid)
                speed = traci.vehicle.getSpeed(vid)
                if 0 <= distance <= inspect_m and speed <= stop_speed:
                    out.append((vid, traci.vehicle.getTypeID(vid),
                                traci.vehicle.getLateralLanePosition(vid), distance))
            except Exception:
                pass
    return out


def queue_estimates(traci, junction):
    """Fixed-class P2 and composition-aware P3 queue discharge predictions."""
    q = queued_vehicles(traci, [approach_edge(junction)])
    n = len(q)
    bikes = sum(typ == 'two_wheeler' for _, typ, _, _ in q)
    share = bikes / n if n else 0
    laterally_offset = (sum(typ == 'two_wheeler' and abs(lat) > 0.35
                            for _, typ, lat, _ in q) / max(bikes, 1))
    # P2: assume ideal lane-discipline discharge per physical lane.
    p2 = 3.0 + 2.0 * n / 3
    # P3: equivalent discharge work, modified by empirically testable seepage proxy.
    work = sum(CLASS_WEIGHTS.get(typ, 2.2) for _, typ, _, _ in q) / 3
    impedance = 1 + 0.65 * share ** 2 + 0.35 * laterally_offset * share
    p3 = 3.0 + work * impedance
    return dict(n=n, bike_share=share, lateral_share=laterally_offset,
                p2_clearance_s=p2, p3_clearance_s=p3, ids={v[0] for v in q})


def choose_approach_green(traci, tlid, incoming_edge):
    """Find a network-defined phase serving the EV edge, masking all other greens."""
    links = traci.trafficlight.getControlledLinks(tlid)
    indices = {i for i, group in enumerate(links)
               if any(link and link[0].startswith(incoming_edge + '_')
                      for link in (group or []))}
    if not indices:
        raise ValueError(f'No signal-controlled links from {incoming_edge} at {tlid}')
    logics = traci.trafficlight.getAllProgramLogics(tlid)
    if not logics:
        raise ValueError(f'No traffic-light program at {tlid}')
    logic = logics[0]
    best = None
    for phase in logic.phases:
        state = phase.state
        score = sum(state[i] in 'gG' for i in indices)
        if score and (best is None or score > best[0]):
            best = (score, state)
    if best is None:
        raise ValueError(f'No eastbound green at {tlid}')
    state = ''.join(c if i in indices and c in 'gG' else 'r'
                    for i, c in enumerate(best[1]))
    return state


def base_phase_at(logic, elapsed_s):
    """Phase index and remaining seconds for global fixed-time clock at t=0."""
    durations = [float(p.duration) for p in logic.phases]
    cycle = sum(durations)
    if cycle <= 0:
        return 0, 1.0
    within = elapsed_s % cycle
    for i, duration in enumerate(durations):
        if within < duration:
            return i, max(0.2, duration - within)
        within -= duration
    return 0, durations[0]


@dataclass
class Junction:
    index: int
    tlid: str
    program_id: str
    logic: object
    green: str
    state: str = 'base'
    preempt_start: float = -1
    pass_time: float = -1
    recovery_end: float = -1
    recovery_until: float = -1
    queued_at_start: set = field(default_factory=set)
    cleared_at: float = -1
    prediction: dict = field(default_factory=dict)
    green_seconds: float = 0.0


class Controller:
    def __init__(self, traci, scenario, p='P3', r='R3', ev_id='EV_001'):
        if p not in ('P0', 'P1', 'P2', 'P3') or r not in ('R0', 'R1', 'R2', 'R3'):
            raise ValueError('Controller must be P0-P3 and R0-R3')
        self.traci, self.scenario, self.p, self.r, self.ev_id = traci, scenario, p, r, ev_id
        self.nodes = []
        for j in range(1, scenario.intersections + 1):
            tlid = f'J{j}'
            logic = traci.trafficlight.getAllProgramLogics(tlid)[0]
            green = choose_approach_green(traci, tlid, approach_edge(j))
            self.nodes.append(Junction(j, tlid, logic.programID, logic, green))
        self.ev_seen = False
        self.ev_arrived = False
        self.ev_stop_count = 0
        self.ev_prev_stopped = False
        self.ev_trace = []
        self.events = []

    def restore_base(self, node, now):
        """Rejoin the original program at the phase implied by the global clock."""
        t = self.traci.trafficlight
        phase, remain = base_phase_at(node.logic, now)
        t.setProgram(node.tlid, node.program_id)
        t.setPhase(node.tlid, phase)
        t.setPhaseDuration(node.tlid, remain)
        node.recovery_end = now
        node.state = 'done'
        self.events.append((now, node.tlid, 'base_restored', self.p, self.r, ''))

    def set_ev_green(self, node):
        self.traci.trafficlight.setRedYellowGreenState(node.tlid, node.green)

    def recovery_seconds(self, node):
        if self.r == 'R0':
            return 0.0
        if self.r == 'R1':
            return 8.0  # Simple fixed transition baseline.
        cross = queued_vehicles(self.traci, cross_edges(node.index))
        if self.r == 'R2':
            return min(24.0, max(5.0, len(cross) * 1.5 / 3.0))
        mix_work = sum(CLASS_WEIGHTS.get(c[1], 2.2) for c in cross) / 3.0
        bikeshare = sum(c[1] == 'two_wheeler' for c in cross) / max(1, len(cross))
        return min(24.0, max(5.0, mix_work * (1 + 0.4 * bikeshare ** 2)))

    def _enter_recovery(self, node, now):
        node.pass_time = now
        self.events.append((now, node.tlid, 'ev_passed', self.p, self.r, ''))
        seconds = self.recovery_seconds(node)
        if seconds == 0:
            self.restore_base(node, now)
            return
        node.state = 'recover'
        node.recovery_until = now + seconds
        # Recovery creates an all-red safety interval before the next phase.
        self.traci.trafficlight.setRedYellowGreenState(node.tlid,
                                                       'r' * len(node.green))
        self.events.append((now, node.tlid, 'recovery_begin', self.p, self.r,
                            f'{seconds:.2f}'))

    def _recover_step(self, node, now):
        """Serve a safe cross-street phase from the original program after clearance."""
        if now >= node.recovery_until:
            self.restore_base(node, now)
            return
        if now < node.pass_time + 2.0:
            self.traci.trafficlight.setRedYellowGreenState(node.tlid,
                                                           'r' * len(node.green))
            return
        # Select an existing program phase that serves cross streets and not the EV.
        link_groups = self.traci.trafficlight.getControlledLinks(node.tlid)
        cross = set(cross_edges(node.index))
        cross_ids = {i for i, links in enumerate(link_groups) if any(
            ln and ln[0].rsplit('_', 1)[0] in cross for ln in (links or []))}
        best = None
        for ph in node.logic.phases:
            score = sum(ph.state[i] in 'gG' for i in cross_ids)
            if best is None or score > best[0]:
                best = (score, ph.state)
        if best and best[0]:
            # Preserve only cross-approach greens to avoid unsafe conflicts.
            state = ''.join(ch if i in cross_ids and ch in 'gG' else 'r'
                            for i, ch in enumerate(best[1]))
            self.traci.trafficlight.setRedYellowGreenState(node.tlid, state)

    def step(self, now):
        t = self.traci
        active = self.ev_id in t.vehicle.getIDList()
        if active:
            self.ev_seen = True
            speed = t.vehicle.getSpeed(self.ev_id)
            x, y = t.vehicle.getPosition(self.ev_id)
            stopped = speed < 0.5
            if stopped and not self.ev_prev_stopped:
                self.ev_stop_count += 1
            self.ev_prev_stopped = stopped
            self.ev_trace.append((round(now, 2), round(x, 2), round(y, 2),
                                  round(speed, 3), t.vehicle.getRoadID(self.ev_id)))
        elif self.ev_seen:
            self.ev_arrived = True
        for node in self.nodes:
            if node.state == 'done':
                continue
            xj = node.index * self.scenario.spacing_m
            dx = xj - x if active else float('inf')
            if node.state == 'recover':
                self._recover_step(node, now)
                continue
            if node.state == 'preempt':
                # Two-second all-red transition prevents abrupt conflicting green.
                if now - node.preempt_start < 2.0:
                    t.trafficlight.setRedYellowGreenState(node.tlid, 'r' * len(node.green))
                else:
                    self.set_ev_green(node)
                # Track when vehicles initially queued ahead have exited the edge.
                if node.cleared_at < 0 and node.queued_at_start:
                    existing = set(t.edge.getLastStepVehicleIDs(approach_edge(node.index)))
                    if not (node.queued_at_start & existing):
                        node.cleared_at = now
                if active and dx < -18:
                    self._enter_recovery(node, now)
                elif not active and self.ev_arrived:
                    self._enter_recovery(node, now)
                continue
            if self.p == 'P0' or not active or dx < 0 or dx > 500:
                continue
            queue = queue_estimates(t, node.index)
            # Estimate approach travel time using free-running EV speed, not a queued zero.
            eta = dx / max(10.0, min(20.0, speed))
            if self.p == 'P1':
                trigger = dx <= 170 and eta <= 12.0
            elif self.p == 'P2':
                trigger = eta <= queue['p2_clearance_s'] + 4.0
            else:
                trigger = eta <= queue['p3_clearance_s'] + 4.0
            if trigger:
                node.state = 'preempt'
                node.preempt_start = now
                node.prediction = queue
                node.queued_at_start = queue['ids']
                if not queue['ids']:
                    node.cleared_at = now
                # Start with all-red rather than switching instantly from an incompatible phase.
                t.trafficlight.setRedYellowGreenState(node.tlid, 'r' * len(node.green))
                self.events.append((now, node.tlid, 'preempt_begin', self.p, self.r,
                                    f"n={queue['n']};bike={queue['bike_share']:.3f};"
                                    f"p2={queue['p2_clearance_s']:.2f};"
                                    f"p3={queue['p3_clearance_s']:.2f}"))
