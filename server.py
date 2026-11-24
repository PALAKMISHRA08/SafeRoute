"""SafeRoute demo API. Python 3.10+, standard library only."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen
import hashlib, hmac, json, os, secrets, sqlite3, time

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get('SAFEROUTE_DB', ROOT.parent / 'saferoute.db'))
TOKENS = {}  # in-memory bearer sessions; restart invalidates sessions

def connect():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    return db

def init_db():
    with connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, salt TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'user', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS incidents(id TEXT PRIMARY KEY, user_id INTEGER REFERENCES users(id), type TEXT NOT NULL, description TEXT NOT NULL, place TEXT, latitude REAL, longitude REAL, status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS contacts(id TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, name TEXT NOT NULL, phone TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS emergency_info(user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, payload TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sos_alerts(id TEXT PRIMARY KEY, user_id INTEGER REFERENCES users(id), payload TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, actor_id INTEGER REFERENCES users(id), action TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        ''')
        admin = os.environ.get('SAFEROUTE_ADMIN_EMAIL','admin@saferoute.local').lower()
        if not db.execute('SELECT 1 FROM users WHERE email=?',(admin,)).fetchone():
            salt=secrets.token_hex(16); pw=os.environ.get('SAFEROUTE_ADMIN_PASSWORD','ChangeMe123!')
            digest=hashlib.pbkdf2_hmac('sha256',pw.encode(),salt.encode(),180000).hex()
            db.execute('INSERT INTO users(name,email,password_hash,salt,role) VALUES(?,?,?,?,?)',('SafeRoute Admin',admin,digest,salt,'admin'))

def stamp(): return time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
def pw_hash(password,salt): return hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),180000).hex()

def fetch_overpass_elements(lat,lon,radius=5000):
    radius=max(500,min(10000,int(radius)))
    query=f'[out:json][timeout:20];(node[amenity=police](around:{radius},{lat},{lon});way[amenity=police](around:{radius},{lat},{lon});relation[amenity=police](around:{radius},{lat},{lon});node[amenity=hospital](around:{radius},{lat},{lon});way[amenity=hospital](around:{radius},{lat},{lon});relation[amenity=hospital](around:{radius},{lat},{lon});node[amenity=clinic](around:{radius},{lat},{lon});way[amenity=clinic](around:{radius},{lat},{lon}););out center tags;'
    errors=[]
    for endpoint in ('https://overpass-api.de/api/interpreter','https://overpass.kumi.systems/api/interpreter'):
        try:
            request=Request(endpoint,data=urlencode({'data':query}).encode(),headers={'Content-Type':'application/x-www-form-urlencoded','User-Agent':'SafeRouteClassroomDemo/1.0'})
            with urlopen(request,timeout=12) as response: payload=json.loads(response.read().decode())
            return payload.get('elements',[])
        except Exception as exc: errors.append(str(exc))
    raise RuntimeError(errors[-1] if errors else 'No response from nearby places service')

def search_osm(query,lat=None,lon=None):
    search={'format':'jsonv2','q':query,'limit':'5','addressdetails':'1','accept-language':'en'}
    if lat is not None and lon is not None and -90<=lat<=90 and -180<=lon<=180:
        search['viewbox']=f'{lon-0.15},{lat+0.15},{lon+0.15},{lat-0.15}'; search['bounded']='0'
    request=Request('https://nominatim.openstreetmap.org/search?'+urlencode(search),headers={'User-Agent':'SafeRouteClassroomDemo/1.0 (local destination search)','Accept':'application/json'})
    with urlopen(request,timeout=12) as response: return json.loads(response.read().decode())

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs): super().__init__(*args,directory=str(ROOT),**kwargs)
    def log_message(self, fmt,*args): print('%s - %s' % (self.address_string(),fmt%args))
    def send_json(self,code,obj):
        raw=json.dumps(obj).encode(); self.send_response(code); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(raw))); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(raw)
    def body(self):
        n=int(self.headers.get('Content-Length','0'))
        if n>1000000: raise ValueError('Request too large')
        return json.loads(self.rfile.read(n) or b'{}')
    def user(self,admin=False):
        token=self.headers.get('Authorization','').removeprefix('Bearer ').strip(); uid=TOKENS.get(token)
        if not uid: return None
        with connect() as db: row=db.execute('SELECT id,name,email,role FROM users WHERE id=?',(uid,)).fetchone()
        if not row or (admin and row['role']!='admin'): return None
        return dict(row)
    def do_GET(self):
        parsed=urlparse(self.path)
        path=parsed.path
        if path.startswith('/api/'):
            if path=='/api/location/nearby':
                params=parse_qs(parsed.query)
                try:
                    lat=float(params.get('lat',[''])[0]); lon=float(params.get('lon',[''])[0])
                    radius=max(500,min(10000,int(params.get('radius',['5000'])[0])))
                    if not (-90<=lat<=90 and -180<=lon<=180): raise ValueError()
                except (ValueError,TypeError): return self.send_json(400,{'error':'Valid lat and lon coordinates are required'})
                try: return self.send_json(200,{'elements':fetch_overpass_elements(lat,lon,radius)})
                except Exception as exc: return self.send_json(502,{'error':'Nearby places service is unavailable','detail':str(exc)})
            if path=='/api/location/search':
                params=parse_qs(parsed.query); query=params.get('q',[''])[0].strip()
                if len(query)<3: return self.send_json(400,{'error':'Enter at least 3 characters for the destination'})
                lat=lon=None
                try:
                    lat=float(params.get('lat',[''])[0]); lon=float(params.get('lon',[''])[0])
                except (ValueError,TypeError): pass
                try:
                    return self.send_json(200,{'results':search_osm(query,lat,lon)})
                except Exception as exc: return self.send_json(502,{'error':'Destination search service is unavailable','detail':str(exc)})
            user=self.user()
            if path=='/api/health': return self.send_json(200,{'ok':True,'database':'sqlite','service':'SafeRoute API'})
            if path=='/api/auth/me': return self.send_json(200,{'user':user}) if user else self.send_json(401,{'error':'Authentication required'})
            if path=='/api/safety/incidents':
                with connect() as db:
                    rows=db.execute("SELECT i.*,u.name AS reporter FROM incidents i LEFT JOIN users u ON u.id=i.user_id WHERE i.status!='hidden' ORDER BY i.created_at DESC LIMIT 100").fetchall()
                return self.send_json(200,{'incidents':[dict(x) for x in rows]})
            if path.startswith('/api/safety/') and path not in ['/api/safety/incidents']:
                if not user: return self.send_json(401,{'error':'Sign in required'})
                if path=='/api/safety/contacts':
                    with connect() as db: rows=db.execute('SELECT id,name,phone,updated_at AS updatedAt FROM contacts WHERE user_id=?',(user['id'],)).fetchall()
                    return self.send_json(200,{'contacts':[dict(x) for x in rows]})
                if path=='/api/safety/emergency-info':
                    with connect() as db: row=db.execute('SELECT payload FROM emergency_info WHERE user_id=?',(user['id'],)).fetchone()
                    return self.send_json(200,json.loads(row['payload']) if row else {})
            if path.startswith('/api/admin/'):
                admin=self.user(True)
                if not admin: return self.send_json(403,{'error':'Administrator access required'})
                with connect() as db:
                    if path=='/api/admin/summary':
                        return self.send_json(200,{'users':db.execute('SELECT COUNT(*) FROM users').fetchone()[0],'incidents':db.execute('SELECT COUNT(*) FROM incidents').fetchone()[0],'pending':db.execute("SELECT COUNT(*) FROM incidents WHERE status='pending'").fetchone()[0],'sos':db.execute('SELECT COUNT(*) FROM sos_alerts').fetchone()[0]})
                    if path=='/api/admin/users': return self.send_json(200,{'users':[dict(x) for x in db.execute('SELECT id,name,email,role,created_at FROM users ORDER BY id DESC LIMIT 250')]})
                    if path=='/api/admin/incidents': return self.send_json(200,{'incidents':[dict(x) for x in db.execute('SELECT i.*,u.name reporter FROM incidents i LEFT JOIN users u ON u.id=i.user_id ORDER BY i.created_at DESC LIMIT 250')]})
                    if path=='/api/admin/network': return self.send_json(200,network_state())
            return self.send_json(404,{'error':'API endpoint not found'})
        return super().do_GET()
    def do_POST(self):
        path=urlparse(self.path).path
        try: data=self.body()
        except Exception as e: return self.send_json(400,{'error':str(e)})
        if path=='/api/auth/register':
            name=str(data.get('name','')).strip(); email=str(data.get('email','')).strip().lower(); password=str(data.get('password',''))
            if len(name)<2 or len(email)>254 or '@' not in email or len(password)<10: return self.send_json(400,{'error':'Enter a name, valid email, and password of at least 10 characters'})
            salt=secrets.token_hex(16)
            try:
                with connect() as db: cur=db.execute('INSERT INTO users(name,email,password_hash,salt) VALUES(?,?,?,?)',(name,email,pw_hash(password,salt),salt)); uid=cur.lastrowid
            except sqlite3.IntegrityError: return self.send_json(409,{'error':'An account with that email already exists'})
            token=secrets.token_urlsafe(32); TOKENS[token]=uid
            return self.send_json(201,{'token':token,'user':{'id':uid,'name':name,'email':email,'role':'user'}})
        if path=='/api/auth/login':
            email=str(data.get('email','')).strip().lower(); password=str(data.get('password',''))
            with connect() as db: row=db.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
            if not row or not hmac.compare_digest(pw_hash(password,row['salt']),row['password_hash']): return self.send_json(401,{'error':'Email or password is incorrect'})
            token=secrets.token_urlsafe(32); TOKENS[token]=row['id']; return self.send_json(200,{'token':token,'user':{'id':row['id'],'name':row['name'],'email':row['email'],'role':row['role']}})
        if path=='/api/network/simulate': return self.send_json(200,simulate_network(data))
        user=self.user()
        if path.startswith('/api/') and not user: return self.send_json(401,{'error':'Sign in to save data'})
        if path=='/api/auth/logout':
            TOKENS.pop(self.headers.get('Authorization','').removeprefix('Bearer ').strip(),None); return self.send_json(200,{'ok':True})
        if path=='/api/safety/incidents':
            typ=str(data.get('type','Other'))[:80]; desc=str(data.get('description','')).strip()[:1500]
            if not desc: return self.send_json(400,{'error':'Incident description is required'})
            loc=data.get('location') or {}; lat=loc.get('latitude'); lng=loc.get('longitude')
            with connect() as db: db.execute('INSERT INTO incidents(id,user_id,type,description,place,latitude,longitude,created_at) VALUES(?,?,?,?,?,?,?,?)',(str(data.get('id') or secrets.token_hex(12)),user['id'],typ,desc,str(data.get('place',''))[:200],lat,lng,str(data.get('createdAt') or stamp())))
            return self.send_json(201,{'connected':True})
        if path=='/api/safety/contacts':
            cid=str(data.get('id') or secrets.token_hex(12)); name=str(data.get('name','')).strip()[:100]; phone=str(data.get('phone','')).strip()[:30]
            if not name or not phone: return self.send_json(400,{'error':'Contact name and phone are required'})
            with connect() as db: db.execute('INSERT INTO contacts(id,user_id,name,phone,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,phone=excluded.phone,updated_at=excluded.updated_at WHERE user_id=excluded.user_id',(cid,user['id'],name,phone,stamp()))
            return self.send_json(201,{'connected':True})
        if path=='/api/safety/emergency-info':
            with connect() as db: db.execute('INSERT INTO emergency_info(user_id,payload,updated_at) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at',(user['id'],json.dumps(data),stamp()))
            return self.send_json(200,{'connected':True})
        if path=='/api/safety/sos':
            sid=str(data.get('id') or secrets.token_hex(12))
            with connect() as db: db.execute('INSERT INTO sos_alerts(id,user_id,payload,created_at) VALUES(?,?,?,?)',(sid,user['id'],json.dumps(data),stamp()))
            return self.send_json(201,{'connected':True,'message':'Alert stored. No notification was sent.'})
        if path.startswith('/api/admin/'):
            admin=self.user(True)
            if not admin: return self.send_json(403,{'error':'Administrator access required'})
            if path=='/api/admin/incidents/status':
                iid=str(data.get('id','')); status=str(data.get('status',''))
                if status not in ('pending','reviewed','resolved','hidden'): return self.send_json(400,{'error':'Invalid incident status'})
                with connect() as db: db.execute('UPDATE incidents SET status=? WHERE id=?',(status,iid)); db.execute('INSERT INTO audit(actor_id,action,detail) VALUES(?,?,?)',(admin['id'],'incident.status',iid+':'+status))
                return self.send_json(200,{'ok':True})
        return self.send_json(404,{'error':'API endpoint not found'})
    def do_DELETE(self):
        path=urlparse(self.path).path
        user=self.user()
        if not user: return self.send_json(401,{'error':'Sign in required'})
        if path.startswith('/api/safety/contacts/'):
            cid=path.rsplit('/',1)[-1]
            with connect() as db: db.execute('DELETE FROM contacts WHERE id=? AND user_id=?',(cid,user['id']))
            return self.send_json(200,{'ok':True})
        return self.send_json(404,{'error':'API endpoint not found'})
    def do_PUT(self): self.do_POST()

# Simple deterministic campus graph for routing/failure/recovery demonstration.
EDGES=[{'from':'A','to':'B','cost':1},{'from':'B','to':'C','cost':1},{'from':'A','to':'D','cost':2},{'from':'D','to':'C','cost':2},{'from':'C','to':'E','cost':1},{'from':'D','to':'E','cost':5}]
def network_state(): return {'nodes':['A','B','C','D','E'],'edges':EDGES,'source':'A','destination':'E','failed_edge':None,'recovered':False,'route':['A','B','C','E'],'cost':3}
def shortest(edges,src,dst):
    nodes={src}; [nodes.update([e['from'],e['to']]) for e in edges]; dist={n:float('inf') for n in nodes}; prev={}; dist[src]=0; todo=set(nodes)
    while todo:
        u=min(todo,key=lambda n:dist[n]); todo.remove(u)
        if dist[u]==float('inf') or u==dst: break
        for e in edges:
            if e['from']==u: v=e['to']
            elif e['to']==u: v=e['from']
            else: continue
            alt=dist[u]+e['cost']
            if alt<dist[v]: dist[v]=alt; prev[v]=u
    if dist.get(dst,float('inf'))==float('inf'): return [],None
    path=[dst]
    while path[-1]!=src: path.append(prev[path[-1]])
    return path[::-1],dist[dst]
def simulate_network(data):
    src=str(data.get('source','A')); dst=str(data.get('destination','E')); fail=data.get('failed_edge')
    active=[e for e in EDGES if not fail or {e['from'],e['to']}!={str(fail.get('from')),str(fail.get('to'))}]
    original,cost=shortest(EDGES,src,dst); route,new_cost=shortest(active,src,dst)
    return {'nodes':['A','B','C','D','E'],'edges':EDGES,'source':src,'destination':dst,'initial_route':original,'initial_cost':cost,'failed_edge':fail,'route_after_failure':route,'cost_after_failure':new_cost,'recovered':bool(fail and route),'status':'recovered' if fail and route else ('unreachable' if not route else 'normal')}

if __name__=='__main__':
    init_db(); host=os.environ.get('SAFEROUTE_HOST','127.0.0.1'); port=int(os.environ.get('SAFEROUTE_PORT','8000'))
    print(f'SafeRoute on http://{host}:{port} | SQLite: {DB_PATH}')
    print('Demo admin: admin@saferoute.local / ChangeMe123! (change before sharing)')
    ThreadingHTTPServer((host,port),Handler).serve_forever()


