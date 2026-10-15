from fastapi import APIRouter, Request, Query
from fraud.cases import Cases, CaseCreate, CaseUpdate, Question, Review, event, CaseSummary, CaseDetail, RunResponse, GuidanceResponse
from fraud.workflows import Investigations
from fraud.monitoring import monitor


def router(app,call):
    r=APIRouter()
    def engine(): return app.state.engine
    def actor(request): return request.state.identity['actor']
    @r.get('/cases',response_model=list[CaseSummary])
    def cases(limit:int=Query(100,ge=1,le=1000)): return Cases(engine()).list(limit)
    @r.post('/cases',response_model=CaseDetail)
    def create(body:CaseCreate,request:Request): return call(Cases(engine()).create,body.transaction_id,actor(request))
    @r.get('/cases/{cid}',response_model=CaseDetail)
    def get(cid:str): return call(Cases(engine()).get,cid)
    @r.patch('/cases/{cid}',response_model=CaseDetail)
    def update(cid:str,body:CaseUpdate,request:Request): return call(Cases(engine()).update,cid,body,actor(request))
    @r.post('/cases/{cid}/ask',response_model=GuidanceResponse)
    def ask(cid:str,body:Question,request:Request):
        call(Cases(engine()).get,cid)
        with engine().lock: answer=call(Investigations(engine()).knowledge().answer,body.question)
        with engine().store.connect() as db: event(db,cid,actor(request),'guidance_requested',{'question':body.question,'answer':answer})
        return answer
    @r.post('/cases/{cid}/investigate',response_model=RunResponse)
    def start(cid:str,request:Request): return call(Investigations(engine()).start,cid,actor(request))
    @r.get('/investigations/{rid}',response_model=RunResponse)
    def run(rid:str): return call(Investigations(engine()).get,rid)
    @r.post('/investigations/{rid}/resume',response_model=RunResponse)
    def resume(rid:str,body:Review,request:Request): return call(Investigations(engine()).resume,rid,body,actor(request))
    @r.post('/investigations/{rid}/retry',response_model=RunResponse)
    def retry(rid:str,request:Request): return call(Investigations(engine()).execute,rid,actor(request))
    @r.get('/monitoring')
    def monitoring(): return call(monitor,engine())
    return r
