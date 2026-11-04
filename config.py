"""Phase 0 scenario parameters. All times in seconds, distances in metres."""
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / 'build'
RESULTS = ROOT / 'results'

@dataclass(frozen=True)
class Scenario:
    intersections: int = 5                 # Five signal-controlled corridor junctions.
    spacing_m: float = 300.0               # Centre-to-centre junction spacing.
    arms_m: float = 240.0                  # Length of each side street approach.
    lanes_per_direction: int = 3           # Three conventional lanes each direction.
    lane_width_m: float = 3.6              # Divides evenly into 0.3 m sublanes.
    lateral_resolution_m: float = 0.3      # Enable SUMO SL2015 sublane decisions.
    step_s: float = 0.2                    # Resolves lateral movement and overtakes.
    duration_s: int = 900                  # Background demand generation horizon.
    clearance_s: int = 240                # Extra time to let late vehicles clear.
    ev_depart_s: float = 360.0             # Same emergency vehicle departure time.
    two_wheeler_share: float = 0.55        # Share of background vehicles, not EV.
    flow_level: str = 'high'               # low, medium, or high.
    seed: int = 42                         # Reproducible Poisson demand and type mix.
    lefthand: bool = True                  # Indian left-hand traffic.

FLOW_VPH_PER_DIRECTION = {                 # Mainline total vehicle departures per hour.
    'low': 450,
    'medium': 750,
    'high': 1050,
}
CROSS_FRACTION = 0.42                      # Cross flow per side approach vs mainline.
OTHER_MIX = {                              # Conditional proportions when not two-wheeler.
    'car': 0.70,
    'auto': 0.16,
    'bus': 0.08,
    'truck': 0.06,
}

# Approximate demonstration assumptions, not a calibrated Indian fleet.
# The lateral parameters intentionally favour visible filtering at queues.
VEHICLE_TYPES = {
    'car': dict(vClass='passenger', length=4.4, width=1.8, minGap=2.0,
                minGapLat=0.35, maxSpeedLat=0.8, lcSublane=0.6, lcPushy=0.0,
                accel=2.1, decel=4.5, maxSpeed=16.7, color='40,120,230'),
    'two_wheeler': dict(vClass='motorcycle', length=1.9, width=0.65, minGap=0.45,
                minGapLat=0.12, maxSpeedLat=1.7, lcSublane=1.0, lcPushy=0.6,
                accel=3.0, decel=5.2, maxSpeed=17.0, color='255,155,0'),
    'auto': dict(vClass='passenger', length=3.0, width=1.4, minGap=1.0,
                minGapLat=0.25, maxSpeedLat=1.0, lcSublane=0.8, lcPushy=0.15,
                accel=1.7, decel=4.0, maxSpeed=13.0, color='240,210,30'),
    'bus': dict(vClass='bus', length=10.5, width=2.5, minGap=2.2,
                minGapLat=0.5, maxSpeedLat=0.5, lcSublane=0.3, lcPushy=0.0,
                accel=1.1, decel=3.5, maxSpeed=13.0, color='85,185,80'),
    'truck': dict(vClass='truck', length=8.0, width=2.5, minGap=2.5,
                minGapLat=0.5, maxSpeedLat=0.5, lcSublane=0.3, lcPushy=0.0,
                accel=1.0, decel=3.5, maxSpeed=13.0, color='140,95,75'),
    'ambulance': dict(vClass='emergency', length=5.0, width=2.0, minGap=1.0,
                minGapLat=0.25, maxSpeedLat=1.1, lcSublane=0.8, lcPushy=0.2,
                accel=2.8, decel=5.0, maxSpeed=22.2, speedFactor=1.25,
                color='245,40,65'),
}
