import base64,hmac,hashlib,json,os,time,secrets
from fastapi import HTTPException,Request
from .db import connect

ROLES={"owner","admin","project_manager","engineer","accountant","site_manager","viewer"}
PERMISSIONS={
 "owner":{"*"},
 "admin":{"*"},
 "project_manager":{"projects","boq","tasks","reports","workers","attendance","equipment","materials","purchases","subcontractors","billings","cashflow","costs","bim","payroll","documents","issues"},
 "engineer":{"projects","boq","tasks","reports","bim","documents","issues"},
 "accountant":{"projects","billings","cashflow","costs","purchases","payroll"},
 "site_manager":{"projects","tasks","reports","workers","attendance","equipment","materials","issues"},
 "viewer":{"projects","boq","tasks","reports","workers","equipment","materials","purchases","subcontractors","billings","cashflow","costs","bim","payroll","documents","issues"},
}
def _hash(password,salt):
 return hashlib.pbkdf2_hmac("sha256",password.encode(),salt,210000).hex()
def create_password(password):
 salt=secrets.token_bytes(16)
 return salt.hex()+"$"+_hash(password,salt)
def verify_password(password,stored):
 try:
  sh,hh=stored.split("$",1); return hmac.compare_digest(_hash(password,bytes.fromhex(sh)),hh)
 except Exception:return False
def _secret():
 return os.getenv("TAYEB_AUTH_SECRET") or os.getenv("TAYEB_API_TOKEN") or "change-this-in-production"
def issue_token(user_id,role):
 payload={"sub":user_id,"role":role,"exp":int(time.time())+43200}
 raw=json.dumps(payload,separators=(",",":"),sort_keys=True).encode()
 sig=hmac.new(_secret().encode(),raw,hashlib.sha256).hexdigest()
 return base64.urlsafe_b64encode(raw).decode().rstrip("=")+"."+sig
def verify_token(token):
 try:
  p,s=token.split(".",1); raw=base64.urlsafe_b64decode(p+"="*(-len(p)%4)); expected=hmac.new(_secret().encode(),raw,hashlib.sha256).hexdigest()
  if not hmac.compare_digest(s,expected):return None
  data=json.loads(raw); 
  if int(data.get("exp",0))<int(time.time()):return None
  return data
 except Exception:return None
def current_user(request:Request):
 auth=request.headers.get("authorization","")
 if not auth.startswith("Bearer "): return None
 return verify_token(auth[7:].strip())
def require_permission(request:Request,permission):
 user=current_user(request)
 if user is None: raise HTTPException(401,"Authentication required")
 if user.get("role") not in ROLES: raise HTTPException(403,"Invalid role")
 if "*" not in PERMISSIONS[user["role"]] and permission not in PERMISSIONS[user["role"]]: raise HTTPException(403,"Permission denied")
 return user
def bootstrap_owner():
 if not os.getenv("TAYEB_BOOTSTRAP_PASSWORD"): return
 with connect() as c:
  if c.execute("SELECT 1 FROM users WHERE username='owner'").fetchone(): return
  c.execute("INSERT INTO users(username,password_hash,role,active) VALUES('owner',?,?,1)",(create_password(os.environ["TAYEB_BOOTSTRAP_PASSWORD"]),"owner"))
