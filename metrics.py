"""Common per-run accumulators and CSV serialization for all controller pairs."""
import csv
from collections import defaultdict


class Metrics:
    def __init__(self, traci, s):
        self.traci, self.s = traci, s
        self.last_wait = {}
        self.wait_sum = defaultdict(float)
        self.stops = defaultdict(int)
        self.prev_stopped = {}
        self.types = {}
        self.arrived = 0
        self.max_queue = defaultdict(int)
        self.queue_series = []
        self.ev_first = None
        self.ev_last = None
        self.ev_junction_cross = {}
        self.ev_junction_delay = defaultdict(float)

    def step(self, now):
        t = self.traci
        self.arrived += t.simulation.getArrivedNumber()
        queue_counts = {}
        ids = t.vehicle.getIDList()
        for vid in ids:
            typ = t.vehicle.getTypeID(vid)
            self.types[vid] = typ
            if typ == 'ambulance':
                if self.ev_first is None:
                    self.ev_first = now
                self.ev_last = now
                x = t.vehicle.getPosition(vid)[0]
                speed = t.vehicle.getSpeed(vid)
                for j in range(1, self.s.intersections + 1):
                    center = j * self.s.spacing_m
                    if center - 150 <= x <= center + 25 and speed < 8.0:
                        self.ev_junction_delay[j] += self.s.step_s * (1 - speed / 8.0)
                    if x >= center + 18 and j not in self.ev_junction_cross:
                        self.ev_junction_cross[j] = now
            else:
                self.wait_sum[vid] += self.s.step_s * max(0.0, 1 - t.vehicle.getSpeed(vid) / 13.9)
                stopped = t.vehicle.getSpeed(vid) < 0.5
                if stopped and not self.prev_stopped.get(vid, False):
                    self.stops[vid] += 1
                self.prev_stopped[vid] = stopped
        for j in range(1, self.s.intersections + 1):
            edge = 'W_J1' if j == 1 else f'J{j-1}_J{j}'
            count = 0
            try:
                count = sum(t.vehicle.getSpeed(v) < 2.0
                            for v in t.edge.getLastStepVehicleIDs(edge))
            except Exception:
                pass
            queue_counts[j] = count
            self.max_queue[j] = max(self.max_queue[j], count)
        self.queue_series.append((round(now, 2), *[queue_counts[j]
                                                    for j in sorted(queue_counts)]))

    def summary(self, controller, p, r, s):
        by_kind = defaultdict(list)
        stops = 0
        for vid, d in self.wait_sum.items():
            by_kind[self.types.get(vid, 'unknown')].append(d)
            stops += self.stops.get(vid, 0)
        all_delay = [v for group in by_kind.values() for v in group]
        two = by_kind['two_wheeler']
        other = [v for typ, group in by_kind.items()
                 if typ != 'two_wheeler' for v in group]
        result = dict(p=p, r=r, seed=s.seed, share=s.two_wheeler_share,
                      flow=s.flow_level, ev_depart=s.ev_depart_s,
                      ev_travel_s=(round(self.ev_last - self.ev_first, 2)
                                   if self.ev_first is not None and controller.ev_arrived else ''),
                      ev_stops=controller.ev_stop_count,
                      vehicles_observed=len(self.wait_sum),
                      arrived=self.arrived,
                      mean_bg_proxy_delay_s=sum(all_delay)/len(all_delay) if all_delay else 0,
                      mean_two_wheeler_proxy_delay_s=sum(two)/len(two) if two else 0,
                      mean_other_proxy_delay_s=sum(other)/len(other) if other else 0,
                      bg_stops=stops,
                      max_queue_vehicles=max(self.max_queue.values(), default=0))
        for node in controller.nodes:
            j = node.index
            result[f'J{j}_preempt_s'] = node.preempt_start if node.preempt_start >= 0 else ''
            result[f'J{j}_clearance_s'] = (round(node.cleared_at - node.preempt_start, 2)
                                               if node.cleared_at >= 0 and node.preempt_start >= 0 else '')
            result[f'J{j}_recovery_policy_s'] = (round(node.recovery_end - node.pass_time, 2)
                                             if node.recovery_end >= 0 and node.pass_time >= 0 else '')
            result[f'J{j}_ev_delay_proxy_s'] = round(self.ev_junction_delay[j], 2)
            result[f'J{j}_pass_s'] = self.ev_junction_cross.get(j, '')
        return result


def write_dict_csv(path, rows):
    if not rows:
        return
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with open(path, 'w', newline='', encoding='utf-8') as f:
        out = csv.DictWriter(f, fields)
        out.writeheader()
        out.writerows(rows)
