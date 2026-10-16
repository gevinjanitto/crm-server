"""MySQL document store exposing the subset of the Motor (MongoDB) API used by this app."""
import os
import re
import json
import time
import uuid
import asyncio
from datetime import datetime, timezone
import aiomysql
import pymysql

_MISSING = object()
_KEY_FIELDS = ['id', 'project_id', 'user_id', 'task_id']
_DATE_FMT = '%Y-%m-%dT%H:%M:%S.%f+00:00'


class DuplicateKeyError(Exception):
    pass


class _Result:
    def __init__(self, **kw): self.__dict__.update(kw); self.acknowledged = True


# ---------- value normalisation (datetimes are kept naive UTC, like Motor defaults) ----------
def _norm(v):
    if isinstance(v, datetime):
        return v.astimezone(timezone.utc).replace(tzinfo=None) if v.tzinfo else v
    if isinstance(v, dict): return {k: _norm(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)): return [_norm(x) for x in v]
    return v


def _enc(v):
    if isinstance(v, datetime): return {'$date': v.strftime(_DATE_FMT)}
    if isinstance(v, dict): return {k: _enc(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)): return [_enc(x) for x in v]
    return v


def _dec(v):
    if isinstance(v, dict):
        if len(v) == 1 and '$date' in v:
            return datetime.fromisoformat(v['$date']).astimezone(timezone.utc).replace(tzinfo=None)
        return {k: _dec(x) for k, x in v.items()}
    if isinstance(v, list): return [_dec(x) for x in v]
    return v


def _dump(doc): return json.dumps(_enc(doc), ensure_ascii=False, default=str)
def _load(text): return _dec(json.loads(text))


# ---------- query matching ----------
def _values(doc, path):
    parts = path.split('.')

    def walk(v, i):
        if i == len(parts): return [v]
        if isinstance(v, dict):
            return walk(v[parts[i]], i + 1) if parts[i] in v else [_MISSING]
        if isinstance(v, list):
            if parts[i].isdigit():
                idx = int(parts[i])
                return walk(v[idx], i + 1) if idx < len(v) else [_MISSING]
            out = [r for x in v if isinstance(x, (dict, list)) for r in walk(x, i) if r is not _MISSING]
            return out or [_MISSING]
        return [_MISSING]
    return walk(doc, 0)


def _expand(vals):
    out = []
    for v in vals:
        if isinstance(v, list): out.extend(v)
        out.append(v)
    return out


def _eq(a, b):
    if b is None: return a is None or a is _MISSING
    if a is _MISSING: return False
    if isinstance(a, bool) != isinstance(b, bool): return False
    return a == b


def _kind(v):
    if isinstance(v, bool): return 'bool'
    if isinstance(v, (int, float)): return 'num'
    if isinstance(v, str): return 'str'
    if isinstance(v, datetime): return 'date'
    return None


def _compare(a, b, op):
    if a is _MISSING or _kind(a) is None or _kind(a) != _kind(b): return False
    return {'$gt': a > b, '$gte': a >= b, '$lt': a < b, '$lte': a <= b}[op]


_TYPES = {'string': str, 'date': datetime, 'bool': bool, 'object': dict, 'array': list, 'double': float, 'int': int, 'number': (int, float)}


def _regex(cond):
    pattern, opts = cond['$regex'], cond.get('$options', '')
    if isinstance(pattern, re.Pattern): return pattern
    flags = 0
    for ch, fl in (('i', re.I), ('m', re.M), ('s', re.S), ('x', re.X)):
        if ch in opts: flags |= fl
    return re.compile(pattern, flags)


def _match_ops(vals, cond):
    expanded = _expand(vals)
    for op, arg in cond.items():
        if op == '$options': continue
        arg = _norm(arg)
        if op == '$eq': ok = any(_eq(v, arg) for v in expanded)
        elif op == '$ne': ok = not any(_eq(v, arg) for v in expanded)
        elif op == '$in': ok = any(_eq(v, a) for a in arg for v in expanded)
        elif op == '$nin': ok = not any(_eq(v, a) for a in arg for v in expanded)
        elif op == '$exists': ok = any(v is not _MISSING for v in vals) == bool(arg)
        elif op in ('$gt', '$gte', '$lt', '$lte'): ok = any(_compare(v, arg, op) for v in expanded)
        elif op == '$regex':
            rx = _regex(cond); ok = any(isinstance(v, str) and rx.search(v) for v in expanded)
        elif op == '$type':
            types = arg if isinstance(arg, list) else [arg]
            ok = any(v is not _MISSING and ((t == 'null' and v is None) or (t in _TYPES and isinstance(v, _TYPES[t]) and not (t != 'bool' and isinstance(v, bool)))) for t in types for v in vals)
        elif op == '$not': ok = not _match_ops(vals, arg if isinstance(arg, dict) else {'$regex': arg})
        elif op == '$size': ok = any(isinstance(v, list) and len(v) == arg for v in vals)
        elif op == '$all': ok = all(any(_eq(v, a) for v in expanded) for a in arg)
        elif op == '$elemMatch':
            ok = any(isinstance(v, list) and any(_match(x, arg) if isinstance(x, dict) else _match_ops([x], arg) for x in v) for v in vals)
        else: raise ValueError(f'Operator query tidak didukung: {op}')
        if not ok: return False
    return True


def _is_ops(v): return isinstance(v, dict) and v and all(k.startswith('$') for k in v)


def _match(doc, query):
    for key, cond in (query or {}).items():
        if key == '$and':
            if not all(_match(doc, q) for q in cond): return False
        elif key == '$or':
            if not any(_match(doc, q) for q in cond): return False
        elif key == '$nor':
            if any(_match(doc, q) for q in cond): return False
        elif _is_ops(cond):
            if not _match_ops(_values(doc, key), cond): return False
        elif isinstance(cond, re.Pattern):
            if not _match_ops(_values(doc, key), {'$regex': cond}): return False
        else:
            cond = _norm(cond)
            if not any(_eq(v, cond) for v in _expand(_values(doc, key))): return False
    return True


# ---------- projection / sort ----------
def _copy_path(src, dst, parts):
    if not isinstance(src, dict) or parts[0] not in src: return
    key, sub = parts[0], src[parts[0]]
    if len(parts) == 1: dst[key] = sub
    elif isinstance(sub, dict): _copy_path(sub, dst.setdefault(key, {}), parts[1:])
    elif isinstance(sub, list):
        items = [x for x in sub if isinstance(x, dict)]
        target = dst.get(key) if isinstance(dst.get(key), list) else [{} for _ in items]
        for x, d in zip(items, target): _copy_path(x, d, parts[1:])
        dst[key] = target


def _del_path(doc, parts):
    if isinstance(doc, list):
        for x in doc: _del_path(x, parts)
    elif isinstance(doc, dict) and parts[0] in doc:
        if len(parts) == 1: doc.pop(parts[0])
        else: _del_path(doc[parts[0]], parts[1:])


def _project(doc, projection):
    if not projection: return doc
    if isinstance(projection, (list, tuple)): projection = {k: 1 for k in projection}
    proj = dict(projection)
    keep_id = proj.pop('_id', 1)
    include = [k for k, v in proj.items() if v]
    if include:
        out = {'_id': doc['_id']} if keep_id and '_id' in doc else {}
        for k in include: _copy_path(doc, out, k.split('.'))
        return out
    if not keep_id: doc.pop('_id', None)
    for k in proj: _del_path(doc, k.split('.'))
    return doc


_RANK = {None: 1, 'num': 2, 'str': 3, 'date': 9, 'bool': 8}


def _sort_key(doc, path):
    vals = [v for v in _values(doc, path) if v is not _MISSING]
    v = vals[0] if vals else None
    if isinstance(v, list): v = v[0] if v else None
    if v is None: return (1, 0)
    k = _kind(v)
    if k is None: return (5, json.dumps(_enc(v), sort_keys=True, default=str))
    return (_RANK[k], v)


def _sort(docs, spec):
    for key, direction in reversed(spec):
        docs.sort(key=lambda d: _sort_key(d, key), reverse=direction < 0)
    return docs


def _sort_spec(key, direction=None):
    if isinstance(key, str): return [(key, direction if direction is not None else 1)]
    if isinstance(key, dict): return list(key.items())
    return [tuple(x) for x in key]


# ---------- updates ----------
def _parent(doc, path, create=True):
    parts = path.split('.')
    cur = doc
    for p in parts[:-1]:
        if isinstance(cur, list) and p.isdigit():
            cur = cur[int(p)]; continue
        if p not in cur or not isinstance(cur[p], (dict, list)):
            if not create: return None, parts[-1]
            cur[p] = {}
        cur = cur[p]
    return cur, parts[-1]


def _get(doc, path):
    cur, key = _parent(doc, path, create=False)
    if cur is None: return _MISSING
    if isinstance(cur, list):
        return cur[int(key)] if key.isdigit() and int(key) < len(cur) else _MISSING
    return cur.get(key, _MISSING)


def _set(doc, path, value):
    cur, key = _parent(doc, path)
    if isinstance(cur, list): cur[int(key)] = value
    else: cur[key] = value


def _pull_match(item, cond):
    if _is_ops(cond): return _match_ops([item], cond)
    if isinstance(cond, dict) and isinstance(item, dict) and not isinstance(cond, re.Pattern): return _match(item, cond)
    return _eq(item, cond)


def _apply_update(doc, update, inserting=False):
    update = _norm(update)
    for op, fields in update.items():
        if op == '$setOnInsert' and not inserting: continue
        for path, val in fields.items():
            cur = _get(doc, path)
            if op in ('$set', '$setOnInsert'): _set(doc, path, val)
            elif op == '$unset':
                parent, key = _parent(doc, path, create=False)
                if isinstance(parent, dict): parent.pop(key, None)
            elif op == '$inc': _set(doc, path, (0 if cur is _MISSING else cur) + val)
            elif op == '$max':
                if cur is _MISSING or cur is None or _compare(val, cur, '$gt'): _set(doc, path, val)
            elif op == '$min':
                if cur is _MISSING or cur is None or _compare(val, cur, '$lt'): _set(doc, path, val)
            elif op in ('$push', '$addToSet'):
                arr = [] if cur is _MISSING or cur is None else cur
                items = val['$each'] if isinstance(val, dict) and '$each' in val else [val]
                for it in items:
                    if op == '$push' or not any(_eq(x, it) and _eq(it, x) for x in arr): arr.append(it)
                _set(doc, path, arr)
            elif op == '$pull':
                if isinstance(cur, list): _set(doc, path, [x for x in cur if not _pull_match(x, val)])
            elif op == '$pop':
                if isinstance(cur, list) and cur: cur.pop(0 if val < 0 else -1)
            elif op == '$rename':
                if cur is not _MISSING:
                    parent, key = _parent(doc, path, create=False); parent.pop(key, None); _set(doc, val, cur)
            else: raise ValueError(f'Operator update tidak didukung: {op}')
    return doc


def _upsert_base(query):
    doc = {}
    for k, v in (query or {}).items():
        if k == '$and':
            for q in v: doc.update(_upsert_base(q))
        elif not k.startswith('$') and not _is_ops(v): _set(doc, k, _norm(v))
        elif _is_ops(v) and '$eq' in v: _set(doc, k, _norm(v['$eq']))
    return doc


def _pushdown(query):
    """SQL pre-filter on indexed key columns. Python matching always re-checks every row."""
    clauses, params = [], []
    items = list((query or {}).items())
    for q in (query or {}).get('$and', []): items += list(q.items())
    for key, cond in items:
        if key not in _KEY_FIELDS: continue
        col = f'`k_{key}`'
        if isinstance(cond, str) and len(cond) < 255:
            clauses.append(f"({col} = %s OR {col} LIKE '[%%')"); params.append(cond)
        elif isinstance(cond, dict) and set(cond) == {'$in'} and all(isinstance(x, str) and len(x) < 255 for x in cond['$in']):
            if not cond['$in']: return None, None
            clauses.append(f"({col} IN ({','.join(['%s'] * len(cond['$in']))}) OR {col} LIKE '[%%')"); params += cond['$in']
    return clauses, params


def _json_col(path): return f"LEFT(JSON_UNQUOTE(JSON_EXTRACT(`doc`, '$.{path}')), 255)"


# ---------- connection ----------
class MySQLClient:
    def __init__(self):
        self._cfg = dict(host=os.environ['MYSQL_HOST'], port=int(os.environ.get('MYSQL_PORT') or 3306), user=os.environ['MYSQL_USER'],
                         password=os.environ['MYSQL_PASSWORD'], db=os.environ['MYSQL_DATABASE'], charset='utf8mb4', autocommit=True)
        self._pool = None
        self._pool_lock = None
        self.db = Database(self)

    def __getitem__(self, name): return self.db

    async def pool(self):
        if self._pool is None:
            if self._pool_lock is None: self._pool_lock = asyncio.Lock()
            async with self._pool_lock:
                if self._pool is None:
                    self._pool = await aiomysql.create_pool(minsize=1, maxsize=int(os.environ.get('MYSQL_POOL_SIZE') or 10), pool_recycle=3600, **self._cfg)
        return self._pool

    def close(self):
        if self._pool: self._pool.close()


class Database:
    def __init__(self, client):
        self._client = client
        self._collections = {}

    def __getattr__(self, name):
        if name.startswith('_'): raise AttributeError(name)
        return self[name]

    def __getitem__(self, name):
        if name not in self._collections: self._collections[name] = Collection(self._client, name)
        return self._collections[name]

    async def list_collection_names(self):
        pool = await self._client.pool()
        async with pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute('SHOW TABLES')
            return [r[0] for r in await cur.fetchall()]


class Cursor:
    def __init__(self, coll, query, projection, sort=None, skip=0, limit=0):
        self._coll, self._query, self._projection = coll, query, projection
        self._sort, self._skip, self._limit = (_sort_spec(sort) if sort else None), skip, limit

    def sort(self, key, direction=None): self._sort = _sort_spec(key, direction); return self
    def skip(self, n): self._skip = n; return self
    def limit(self, n): self._limit = n; return self

    async def _run(self):
        docs = await self._coll._find_docs(self._query)
        if self._sort: _sort(docs, self._sort)
        docs = docs[self._skip:]
        if self._limit: docs = docs[:self._limit]
        return [_project(d, self._projection) for d in docs]

    async def to_list(self, length=None):
        docs = await self._run()
        return docs[:length] if length else docs

    def __aiter__(self): return self._iter()

    async def _iter(self):
        for d in await self._run(): yield d


class _AggCursor:
    def __init__(self, coll, pipeline): self._coll, self._pipeline = coll, pipeline
    async def to_list(self, length=None):
        docs = await self._coll._aggregate(self._pipeline)
        return docs[:length] if length else docs
    def __aiter__(self): return self._iter()
    async def _iter(self):
        for d in await self._coll._aggregate(self._pipeline): yield d


def _expr(doc, e):
    if isinstance(e, str) and e.startswith('$'):
        v = [x for x in _values(doc, e[1:]) if x is not _MISSING]
        return v[0] if v else None
    if isinstance(e, dict) and not _is_ops(e): return {k: _expr(doc, x) for k, x in e.items()}
    return e


def _group(docs, spec):
    groups = {}
    for d in docs:
        gid = _expr(d, spec['_id'])
        key = json.dumps(_enc(gid), sort_keys=True, default=str)
        groups.setdefault(key, (gid, []))[1].append(d)
    out = []
    for gid, rows in groups.values():
        r = {'_id': gid}
        for field, acc in spec.items():
            if field == '_id': continue
            (op, arg), = acc.items()
            vals = [_expr(x, arg) for x in rows]
            nums = [v for v in vals if _kind(v) == 'num']
            present = [v for v in vals if v is not None]
            if op == '$sum': r[field] = sum(nums)
            elif op == '$avg': r[field] = sum(nums) / len(nums) if nums else None
            elif op == '$min': r[field] = min(present, key=lambda v: _sort_key({'v': v}, 'v')) if present else None
            elif op == '$max': r[field] = max(present, key=lambda v: _sort_key({'v': v}, 'v')) if present else None
            elif op == '$first': r[field] = vals[0] if vals else None
            elif op == '$last': r[field] = vals[-1] if vals else None
            elif op == '$push': r[field] = vals
            elif op == '$addToSet':
                r[field] = []
                for v in vals:
                    if not any(_eq(x, v) for x in r[field]): r[field].append(v)
            else: raise ValueError(f'Akumulator tidak didukung: {op}')
        out.append(r)
    return out


class Collection:
    def __init__(self, client, name):
        if not re.fullmatch(r'[A-Za-z0-9_]{1,60}', name): raise ValueError(f'Nama koleksi tidak valid: {name}')
        self._client, self.name = client, name
        self._table = f'`{name}`'
        self._ready = False
        self._lock = None
        self._ttl = None
        self._last_purge = 0.0

    # ---- infrastructure ----
    async def _conn(self):
        pool = await self._client.pool()
        if not self._ready:
            async with pool.acquire() as conn, conn.cursor() as cur:
                cols = ',\n'.join(f'`k_{f}` VARCHAR(255) AS ({_json_col(f)}) STORED, INDEX `ix_{f}` (`k_{f}`)' for f in _KEY_FIELDS)
                await cur.execute(f'CREATE TABLE IF NOT EXISTS {self._table} (`pk` BIGINT AUTO_INCREMENT PRIMARY KEY, `_id` VARCHAR(64) NOT NULL, `doc` LONGTEXT NOT NULL, {cols}, UNIQUE KEY `ux__id` (`_id`)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin')
            self._ready = True
        return pool

    def _write_lock(self):
        if self._lock is None: self._lock = asyncio.Lock()
        return self._lock

    async def _exec(self, cur, sql, params=None):
        try: await cur.execute(sql, params)
        except pymysql.err.IntegrityError as e:
            if e.args and e.args[0] == 1062: raise DuplicateKeyError(str(e)) from e
            raise

    async def _purge_ttl(self):
        if not self._ttl or time.monotonic() - self._last_purge < 30: return
        self._last_purge = time.monotonic()
        field, seconds = self._ttl
        cutoff = datetime.fromtimestamp(time.time() - seconds, timezone.utc).strftime(_DATE_FMT)
        pool = await self._conn()
        async with pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(f"DELETE FROM {self._table} WHERE JSON_UNQUOTE(JSON_EXTRACT(`doc`, '$.{field}.\"$date\"')) < %s", (cutoff,))

    async def _select(self, cur, query, for_update=False):
        clauses, params = _pushdown(query)
        if clauses is None: return []
        sql = f'SELECT `pk`, `doc` FROM {self._table}' + (' WHERE ' + ' AND '.join(clauses) if clauses else '') + ' ORDER BY `pk`' + (' FOR UPDATE' if for_update else '')
        await cur.execute(sql, params)
        out = []
        for pk, text in await cur.fetchall():
            doc = _load(text)
            if _match(doc, query): out.append((pk, doc))
        return out

    async def _find_docs(self, query):
        await self._purge_ttl()
        pool = await self._conn()
        async with pool.acquire() as conn, conn.cursor() as cur:
            return [d for _, d in await self._select(cur, query)]

    async def _write(self, fn):
        pool = await self._conn()
        async with self._write_lock():
            async with pool.acquire() as conn:
                await conn.begin()
                try:
                    async with conn.cursor() as cur: result = await fn(cur)
                    await conn.commit()
                    return result
                except BaseException:
                    await conn.rollback(); raise

    async def _insert(self, cur, doc):
        if '_id' not in doc: doc['_id'] = uuid.uuid4().hex[:24]
        stored = _norm(doc)
        await self._exec(cur, f'INSERT INTO {self._table} (`_id`, `doc`) VALUES (%s, %s)', (str(stored['_id']), _dump(stored)))
        return doc['_id']

    async def _update(self, query, update, upsert=False, many=False, sort=None):
        async def run(cur):
            rows = await self._select(cur, query, for_update=True)
            if sort: rows = self._sorted_rows(rows, sort)
            if not many: rows = rows[:1]
            modified, before_after = 0, []
            for pk, doc in rows:
                before = _dump(doc)
                new = _apply_update(_load(before), update)
                after = _dump(new)
                if after != before:
                    await self._exec(cur, f'UPDATE {self._table} SET `doc` = %s WHERE `pk` = %s', (after, pk))
                    modified += 1
                before_after.append((doc, new))
            upserted = None
            if not rows and upsert:
                new = _apply_update(_upsert_base(query), update, inserting=True)
                upserted = await self._insert(cur, new)
                before_after.append((None, new))
            return len(rows), modified, upserted, before_after
        return await self._write(run)

    @staticmethod
    def _sorted_rows(rows, sort):
        docs = _sort([d for _, d in rows], _sort_spec(sort))
        order = {id(d): i for i, d in enumerate(docs)}
        return sorted(rows, key=lambda r: order[id(r[1])])

    # ---- public Motor-like API ----
    async def create_index(self, keys, unique=False, expireAfterSeconds=None, partialFilterExpression=None, **_):
        spec = _sort_spec(keys)
        if expireAfterSeconds is not None: self._ttl = (spec[0][0], expireAfterSeconds)
        if not unique: return
        if len(spec) != 1: raise ValueError('Unique index gabungan tidak didukung.')
        field = spec[0][0]
        expr = _json_col(field)
        name = 'u_' + re.sub(r'\W', '_', field)
        if partialFilterExpression:
            conds = ' AND '.join(f"JSON_UNQUOTE(JSON_EXTRACT(`doc`, '$.{k}'))  = '{pymysql.converters.escape_string(str(v))}'" for k, v in partialFilterExpression.items())
            expr = f'IF({conds}, {expr}, NULL)'
            name += '_partial'
        pool = await self._conn()
        async with pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(f'SHOW COLUMNS FROM {self._table} LIKE %s', (name,))
            if not await cur.fetchone():
                await cur.execute(f'ALTER TABLE {self._table} ADD COLUMN `{name}` VARCHAR(255) AS ({expr}) STORED, ADD UNIQUE KEY `ux_{name}` (`{name}`)')
        return name

    def find(self, filter=None, projection=None, sort=None, skip=0, limit=0, **_):
        return Cursor(self, filter or {}, projection, sort, skip, limit)

    async def find_one(self, filter=None, projection=None, sort=None, **_):
        docs = await Cursor(self, filter or {}, projection, sort, 0, 1).to_list(1)
        return docs[0] if docs else None

    async def count_documents(self, filter=None, **_):
        return len(await self._find_docs(filter or {}))

    async def estimated_document_count(self): return await self.count_documents({})

    async def distinct(self, key, filter=None):
        out = []
        for d in await self._find_docs(filter or {}):
            for v in _expand(_values(d, key)):
                if v is _MISSING or isinstance(v, list): continue
                if not any(_eq(x, v) and type(x) is type(v) for x in out): out.append(v)
        return out

    def aggregate(self, pipeline, **_): return _AggCursor(self, pipeline)

    async def _aggregate(self, pipeline):
        stages = list(pipeline)
        query = stages.pop(0)['$match'] if stages and '$match' in stages[0] else {}
        docs = await self._find_docs(query)
        for st in stages:
            (op, arg), = st.items()
            if op == '$match': docs = [d for d in docs if _match(d, arg)]
            elif op == '$group': docs = _group(docs, arg)
            elif op == '$sort': docs = _sort(docs, _sort_spec(arg))
            elif op == '$limit': docs = docs[:arg]
            elif op == '$skip': docs = docs[arg:]
            elif op == '$project': docs = [_project(d, arg) for d in docs]
            elif op == '$count': docs = [{arg: len(docs)}]
            else: raise ValueError(f'Tahap aggregate tidak didukung: {op}')
        return docs

    async def insert_one(self, doc, **_):
        async def run(cur): return await self._insert(cur, doc)
        return _Result(inserted_id=await self._write(run))

    async def insert_many(self, docs, **_):
        async def run(cur): return [await self._insert(cur, d) for d in docs]
        return _Result(inserted_ids=await self._write(run))

    async def update_one(self, filter, update, upsert=False, **_):
        matched, modified, upserted, _ba = await self._update(filter, update, upsert)
        return _Result(matched_count=matched, modified_count=modified, upserted_id=upserted)

    async def update_many(self, filter, update, upsert=False, **_):
        matched, modified, upserted, _ba = await self._update(filter, update, upsert, many=True)
        return _Result(matched_count=matched, modified_count=modified, upserted_id=upserted)

    async def find_one_and_update(self, filter, update, projection=None, return_document=False, upsert=False, sort=None, **_):
        _m, _mod, _u, pairs = await self._update(filter, update, upsert, sort=sort)
        if not pairs: return None
        before, after = pairs[0]
        doc = after if return_document else before
        return _project(doc, projection) if doc is not None else None

    async def replace_one(self, filter, replacement, upsert=False, **_):
        async def run(cur):
            rows = (await self._select(cur, filter, for_update=True))[:1]
            if rows:
                pk, old = rows[0]
                new = _norm({**replacement, '_id': old['_id']})
                await self._exec(cur, f'UPDATE {self._table} SET `doc` = %s WHERE `pk` = %s', (_dump(new), pk))
                return _Result(matched_count=1, modified_count=int(_dump(new) != _dump(old)), upserted_id=None)
            if upsert: return _Result(matched_count=0, modified_count=0, upserted_id=await self._insert(cur, dict(replacement)))
            return _Result(matched_count=0, modified_count=0, upserted_id=None)
        return await self._write(run)

    async def _delete(self, filter, many):
        async def run(cur):
            rows = await self._select(cur, filter or {}, for_update=True)
            if not many: rows = rows[:1]
            for pk, _d in rows: await cur.execute(f'DELETE FROM {self._table} WHERE `pk` = %s', (pk,))
            return len(rows)
        return _Result(deleted_count=await self._write(run))

    async def delete_one(self, filter, **_): return await self._delete(filter, False)
    async def delete_many(self, filter, **_): return await self._delete(filter, True)

    async def find_one_and_delete(self, filter, projection=None, **_):
        doc = await self.find_one(filter)
        if doc: await self.delete_one({'_id': doc['_id']})
        return _project(doc, projection) if doc else None

    async def drop(self):
        pool = await self._conn()
        async with pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(f'DROP TABLE IF EXISTS {self._table}')
        self._ready = False
