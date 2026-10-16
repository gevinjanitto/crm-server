"""Validate vector drawings alongside existing whiteboard notes, without changing old data."""
import math
import re
from fastapi import HTTPException
from workspace_common import record

NOTE_COLORS = ['#fff5cd', '#e6f0ff', '#e4f8ec', '#ffe7ef', '#ffffff']


def coordinate(value):
    return type(value) in (int, float) and math.isfinite(value) and abs(value) <= 1000000


async def clean_nodes(pid, items):
    nodes, seen, note_ids = [], set(), set()
    for item in items:
        nid, pos, data = item.get('id'), item.get('position', {}), item.get('data', {})
        kind = item.get('type', 'note')
        if not isinstance(nid, str) or not 1 <= len(nid) <= 100 or nid in seen:
            raise HTTPException(400, 'ID node tidak valid atau duplikat.')
        if not isinstance(pos, dict) or not all(coordinate(pos.get(k)) for k in ['x', 'y']):
            raise HTTPException(400, 'Posisi node tidak valid.')
        if not isinstance(data, dict):
            raise HTTPException(400, 'Data whiteboard tidak valid.')
        if kind == 'drawing':
            points, color, width = data.get('points'), data.get('color'), data.get('width')
            if not isinstance(points, list) or not 1 <= len(points) <= 2000:
                raise HTTPException(400, 'Gambar harus memiliki 1–2000 titik.')
            if not all(isinstance(point, list) and len(point) == 2 and all(coordinate(v) for v in point) for point in points):
                raise HTTPException(400, 'Titik gambar tidak valid.')
            if not isinstance(color, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
                raise HTTPException(400, 'Warna gambar tidak valid.')
            if not coordinate(width) or not 1 <= width <= 24:
                raise HTTPException(400, 'Ketebalan pena harus antara 1 dan 24.')
            clean = {'points': points, 'color': color.lower(), 'width': width}
        elif kind == 'note':
            text, color, task_id = data.get('label', ''), data.get('color', NOTE_COLORS[0]), data.get('task_id', '')
            if not isinstance(text, str) or len(text) > 2000:
                raise HTTPException(400, 'Catatan maksimal 2000 karakter.')
            if color not in NOTE_COLORS:
                raise HTTPException(400, 'Warna tidak valid.')
            if not isinstance(task_id, str):
                raise HTTPException(400, 'Task tidak valid.')
            if task_id:
                await record('tasks', pid, task_id)
            clean = {'label': text, 'color': color, 'task_id': task_id}
            note_ids.add(nid)
        else:
            raise HTTPException(400, 'Jenis objek whiteboard tidak valid.')
        nodes.append({'id': nid, 'type': kind, 'position': {k: pos[k] for k in ['x', 'y']}, 'data': clean})
        seen.add(nid)
    return nodes, note_ids