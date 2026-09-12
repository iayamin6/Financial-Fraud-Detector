import fraud
import os
import sys
from fraud.config import load_config,ROOT
cfg=load_config()
os.chdir(ROOT)
os.execv(sys.executable,[sys.executable,'-m','streamlit','run','dashboard/app.py','--server.port',str(cfg['api']['dashboard_port']),'--server.address',cfg['api']['host']])
