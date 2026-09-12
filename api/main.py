import fraud  # Configure native numerical runtimes before model imports.
import csv
import io
import logging
from contextlib import asynccontextmanager
from time import perf_counter
from fastapi import FastAPI,HTTPException,UploadFile,File,Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from fraud.config import load_config
from fraud.engine import Engine,Conflict,NotFound
from fraud.schemas import Transaction,BatchRequest,Feedback,ScoreResponse,FeedbackResponse,ExplanationResponse,HealthResponse,MetricsResponse,PolicyResponse

logger=logging.getLogger('fraud.http')
logging.basicConfig(level=logging.INFO,format='%(asctime)s %(name)s %(levelname)s %(message)s')
def create_app(config=None):
    cfg=config or load_config()
    @asynccontextmanager
    async def lifespan(app):
        app.state.engine=Engine(cfg)
        yield
    app=FastAPI(title='Fraud Signals',version='0.1.0',description='Local synthetic-data research demo; risk recommendations, not bank enforcement.',lifespan=lifespan)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request,exc):
        # Avoid echoing sensitive payloads or non-JSON values such as Infinity.
        return JSONResponse(status_code=422,content={'detail':[
            {k:e[k] for k in ('loc','msg','type')} for e in exc.errors()]})

    @app.middleware('http')
    async def latency(request,call_next):
        start=perf_counter(); response=await call_next(request); elapsed=(perf_counter()-start)*1000
        response.headers['X-Process-Time-Ms']=f'{elapsed:.3f}'
        logger.info('http_latency_ms method=%s path=%s elapsed=%.3f',request.method,request.url.path,elapsed)
        return response

    def call(fn,*args):
        try: return fn(*args)
        except NotFound as exc: raise HTTPException(404,str(exc)) from exc
        except Conflict as exc: raise HTTPException(409,str(exc)) from exc
        except ValueError as exc: raise HTTPException(422,str(exc)) from exc

    @app.get('/health',response_model=HealthResponse)
    def health(): return {'status':'ready','model_version':app.state.engine.version}

    @app.post('/score',response_model=ScoreResponse)
    def score(tx:Transaction): return call(app.state.engine.score_many,[tx])[0]

    @app.post('/score/batch',response_model=list[ScoreResponse])
    def batch(body:BatchRequest|list[Transaction]):
        return call(app.state.engine.score_many,body.transactions if isinstance(body,BatchRequest) else body)

    @app.post('/score/batch/csv',response_model=list[ScoreResponse])
    async def batch_csv(file:UploadFile=File(...)):
        try:
            raw=await file.read(cfg['api']['csv_max_bytes']+1)
            if len(raw)>cfg['api']['csv_max_bytes']: raise HTTPException(413,'CSV exceeds configured byte limit')
            reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
            if not reader.fieldnames or len(reader.fieldnames)!=len(set(reader.fieldnames)): raise HTTPException(422,'CSV needs unique column headers')
            records=[]
            for row in reader:
                if len(records)>=cfg['api']['batch_limit']: raise HTTPException(422,'CSV exceeds batch limit')
                records.append(Transaction.model_validate({k:(None if v=='' else v) for k,v in row.items()}))
            return await run_in_threadpool(call,app.state.engine.score_many,records)
        except (UnicodeError,csv.Error,ValidationError,TypeError) as exc:
            raise HTTPException(422,'Invalid UTF-8 CSV or transaction fields; use the documented schema') from exc
        finally: await file.close()

    @app.post('/explain/{transaction_id}',response_model=ExplanationResponse)
    def explain(transaction_id:str): return call(app.state.engine.explain,transaction_id)

    @app.post('/feedback',response_model=FeedbackResponse)
    def feedback(body:Feedback): return call(app.state.engine.feedback,body)

    @app.get('/transactions',response_model=list[ScoreResponse])
    def recent(limit:int=Query(default=100,ge=1,le=1000)): return app.state.engine.recent(limit)

    @app.get('/metrics',response_model=MetricsResponse)
    def metrics(): return app.state.engine.metrics()

    @app.get('/policy',response_model=PolicyResponse)
    def policy(): return cfg['fusion']
    return app

app=create_app()
