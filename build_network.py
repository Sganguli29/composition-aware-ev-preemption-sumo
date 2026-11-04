"""Create an original five-junction corridor using SUMO plain XML + netconvert."""
import argparse
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from config import BUILD, Scenario


def write_xml(element, path):
    ET.indent(element, space='  ')
    ET.ElementTree(element).write(path, encoding='utf-8', xml_declaration=True)


def generate_network(s: Scenario):
    BUILD.mkdir(parents=True, exist_ok=True)
    nodes = ET.Element('nodes')
    edges = ET.Element('edges')
    xs = {f'J{i}': (i * s.spacing_m, 0.0) for i in range(1, s.intersections + 1)}
    xs['W'] = (0.0, 0.0)
    xs['E'] = ((s.intersections + 1) * s.spacing_m, 0.0)
    for i in range(1, s.intersections + 1):
        x, _ = xs[f'J{i}']
        xs[f'N{i}'] = (x, s.arms_m)
        xs[f'S{i}'] = (x, -s.arms_m)
    for name, (x, y) in xs.items():
        attributes = dict(id=name, x=str(x), y=str(y))
        if name.startswith('J'):
            attributes['type'] = 'traffic_light'
        ET.SubElement(nodes, 'node', attributes)

    def make_edge(a, b):
        ET.SubElement(edges, 'edge', dict(
            id=f'{a}_{b}', **{'from': a, 'to': b},
            numLanes=str(s.lanes_per_direction),
            speed='16.67', width=str(s.lane_width_m), priority='3'))

    spine = ['W'] + [f'J{i}' for i in range(1, s.intersections + 1)] + ['E']
    for a, b in zip(spine, spine[1:]):
        make_edge(a, b)
        make_edge(b, a)
    for i in range(1, s.intersections + 1):
        for side in ('N', 'S'):
            make_edge(f'{side}{i}', f'J{i}')
            make_edge(f'J{i}', f'{side}{i}')
    node_file = BUILD / 'corridor.nod.xml'
    edge_file = BUILD / 'corridor.edg.xml'
    net_file = BUILD / 'corridor.net.xml'
    write_xml(nodes, node_file)
    write_xml(edges, edge_file)
    exe = shutil.which('netconvert')
    if not exe:
        raise SystemExit('netconvert not found. Install SUMO and put its bin directory on PATH.')
    cmd = [exe, '--node-files', str(node_file), '--edge-files', str(edge_file),
           '--output-file', str(net_file), '--no-turnarounds', 'true',
           '--tls.default-type', 'static',
           '--tls.green.time', '35', '--tls.yellow.time', '3',
           '--junctions.corner-detail', '5', '--geometry.remove', 'false']
    if s.lefthand:
        cmd += ['--lefthand', 'true']
    subprocess.run(cmd, check=True)
    net = ET.parse(net_file).getroot()
    observed = {x.attrib['id'] for x in net.findall('tlLogic')}
    expected = {f'J{i}' for i in range(1, s.intersections + 1)}
    if observed != expected:
        raise RuntimeError(f'TLS IDs mismatch: expected {expected}, observed {observed}')
    print('Network written:', net_file)
    print('Traffic lights:', ', '.join(sorted(observed)))
    return net_file


if __name__ == '__main__':
    generate_network(Scenario())
