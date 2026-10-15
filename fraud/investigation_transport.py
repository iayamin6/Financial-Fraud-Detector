"""Same services as the authenticated API, scoped to one synthetic demo session."""
from .cases import Cases, CaseCreate, CaseUpdate, Question, Review, event
from .workflows import Investigations
from .monitoring import monitor


def dispatch_investigation(engine,method,path,body):
    parts=path.strip('/').split('/'); cases=Cases(engine); workflow=Investigations(engine);actor='demo-analyst'
    try:
        if method=='GET' and path=='/monitoring': return monitor(engine)
        if path=='/cases':
            if method=='GET': return cases.list()
            if method=='POST': return cases.create(CaseCreate.model_validate(body).transaction_id,actor)
        if parts[0]=='cases' and len(parts)>=2:
            cid=parts[1]
            if len(parts)==2:
                if method=='GET': return cases.get(cid)
                if method=='PATCH': return cases.update(cid,CaseUpdate.model_validate(body),actor)
            if method=='POST' and len(parts)==3:
                if parts[2]=='investigate': return workflow.start(cid,actor)
                if parts[2]=='ask':
                    cases.get(cid);question=Question.model_validate(body).question
                    with engine.lock: answer=workflow.knowledge().answer(question)
                    with engine.store.connect() as db: event(db,cid,actor,'guidance_requested',{'question':question,'answer':answer})
                    return answer
        if parts[0]=='investigations' and len(parts)>=2:
            if method=='GET' and len(parts)==2: return workflow.get(parts[1])
            if method=='POST' and len(parts)==3:
                if parts[2]=='resume': return workflow.resume(parts[1],Review.model_validate(body),actor)
                if parts[2]=='retry': return workflow.execute(parts[1],actor)
        raise ValueError('Unknown investigation operation')
    except ValueError as exc: raise RuntimeError(str(exc)) from exc
