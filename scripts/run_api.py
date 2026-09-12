import fraud
import uvicorn
from fraud.config import load_config
cfg=load_config()
uvicorn.run('api.main:app',host=cfg['api']['host'],port=cfg['api']['port'],workers=1,log_level='info')
