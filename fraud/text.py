import re
import unicodedata
from pathlib import Path
import joblib
import numpy as np


def rule_signals(text, cfg):
    text=unicodedata.normalize('NFKC',text)
    hits=[]
    # Suppress only a local safety advisory, never the entire message.
    clauses=re.split(r'[.!?;\n]+', text.lower())
    for rule in cfg['nlp']['rules']:
        for clause in clauses:
            for match in re.finditer(rule['pattern'],clause,re.I):
                prefix=clause[max(0,match.start()-35):match.start()]
                if re.search(r'(?:never|do not|don\x27t|will never|must not|কখনো|কখনও)\s*(?:ever\s*)?$',prefix):
                    continue
                if re.match(r'\s*(?:না|na)\b',clause[match.end():],re.I):
                    continue
                hits.append({'name':rule['name'],'score':rule['score'],'evidence':match.group(0)})
    urgency=[p for p in cfg['nlp']['urgency_patterns'] if re.search(p,text,re.I)]
    return hits, min(1.,len(urgency)/3)

def script_signal(text,cfg):
    counts={}
    for char in text:
        if not char.isalpha(): continue
        script=unicodedata.name(char,'UNKNOWN').split(' ')[0]
        counts[script]=counts.get(script,0)+1
    total=sum(counts.values())
    scripts=sorted(k for k,v in counts.items() if v/max(total,1)>=cfg['nlp']['mixed_script_min_fraction'])
    allowed=[sorted(p) for p in cfg['nlp']['allowed_script_pairs']]
    return {'scripts':scripts,'unusual_mix':len(scripts)>1 and scripts not in allowed,
            'note':'Context signal only; multilingual text is not evidence of fraud.'}

class TextLayer:
    def __init__(self,cfg):
        import torch
        import spacy
        from transformers import AutoTokenizer,AutoModelForSequenceClassification
        from sentence_transformers import SentenceTransformer
        self.cfg=cfg; self.torch=torch
        path=Path(cfg['paths']['models'])
        self.baseline=joblib.load(path/'text_baseline.joblib')
        self.tokenizer=AutoTokenizer.from_pretrained(path/'bert',local_files_only=True)
        self.model=AutoModelForSequenceClassification.from_pretrained(path/'bert',local_files_only=True).eval()
        torch.set_num_threads(4)
        self.embedding=SentenceTransformer(str(path/'embeddings'),local_files_only=True,device='cpu')
        self.examples=cfg['nlp']['known_scams']
        self.example_vectors=self.embedding.encode(self.examples,normalize_embeddings=True)
        self.ner=spacy.load(cfg['nlp']['spacy_model'])
        ruler=self.ner.add_pipe('entity_ruler',after='ner')
        ruler.add_patterns([{'label':'ROLE','pattern':[{'LOWER':'agent'}]},
                            {'label':'ACCOUNT_NUMBER','pattern':[{'TEXT':{'REGEX':r'^\d{8,18}$'}}]},
                            *[{'label':'SENSITIVE_INFO','pattern':[{'LOWER':w}]} for w in ['otp','pin','password']]])

    def bert_probabilities(self,texts):
        batches=[]
        for start in range(0,len(texts),self.cfg['nlp']['batch_size']):
            tokens=self.tokenizer(list(texts[start:start+self.cfg['nlp']['batch_size']]),padding=True,truncation=True,
                                  max_length=self.cfg['nlp']['max_length'],return_tensors='pt')
            with self.torch.inference_mode():
                batches.append(self.model(**tokens).logits.softmax(-1).cpu().numpy())
        return np.concatenate(batches)

    def score(self,text):
        if not text or not text.strip():
            return dict(score=0.,rules=0.,signals=[],route='no_text',available=False,urgency=0.,entities=[],script={'scripts':[],'unusual_mix':False})
        text=unicodedata.normalize('NFKC',text).strip()
        hits,urgency=rule_signals(text,self.cfg); rule=max([h['score'] for h in hits],default=0.)
        scripts=script_signal(text,self.cfg)
        entities=[{'text':e.text,'label':e.label_} for e in self.ner(text).ents]
        signals=[{'name':h['name'],'detail':h['evidence'],'value':h['score']} for h in hits]
        if urgency: signals.append({'name':'urgency','detail':'Pressure or urgency language detected','value':urgency})
        if scripts['unusual_mix']: signals.append({'name':'mixed_scripts','detail':', '.join(scripts['scripts']),'value':0.})
        result=dict(confidence_note='Uncalibrated risk evidence; English classifier. Bangla coverage is limited to configured rules.',rules=rule,signals=signals,urgency=urgency,entities=entities,script=scripts,available=True)
        if rule>=self.cfg['nlp']['rule_short_circuit']:
            return dict(**result,classifier_confidence=None,score=rule,route='rule_short_circuit',baseline=None,bert=None,semantic=None)
        p=float(self.baseline.predict_proba([text])[0,1]); bert=None
        if p<=self.cfg['nlp']['prefilter_low'] or p>=self.cfg['nlp']['prefilter_high']:
            route='baseline'; model_score=p
        else:
            bert=float(1-self.bert_probabilities([text])[0,0]); model_score=self.cfg['nlp']['model_weights']['baseline']*p+self.cfg['nlp']['model_weights']['bert']*bert; route='bert'
        vector=self.embedding.encode([text],normalize_embeddings=True)
        similarities=(vector@self.example_vectors.T)[0]; idx=int(np.argmax(similarities)); similarity=float(similarities[idx])
        semantic=max(0.,min(1.,(similarity-self.cfg['nlp']['semantic_floor'])/self.cfg['nlp']['semantic_span']))
        # Semantic/urgency evidence adjusts model output but cannot dominate alone.
        w=self.cfg['nlp']['score_weights']
        combined=max(rule,w['model']*model_score+w['semantic']*semantic+w['urgency']*urgency)
        signals.append({'name':'text_classifier','detail':f'{route} scam evidence','value':model_score})
        signals.append({'name':'semantic_match','detail':self.examples[idx],'value':similarity})
        return dict(**result,classifier_confidence={'value':max(model_score,1-model_score),'calibrated':False,'label':'scam' if model_score>=.5 else 'legitimate'},score=float(combined),route=route,baseline=p,bert=bert,semantic=semantic)
